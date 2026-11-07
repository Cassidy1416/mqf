"""Q2 approach 1 - milestone 1: GBM calibration on Chinese futures.

Loads the committed Q2 snapshots through data/fetch.py (which verifies
SHA-256, row counts, headers and date coverage against
data/metadata.json), calibrates per-futures log-return GBM parameters
from closes on or before the valuation date, and reports a
SHIBOR-interpolated continuous discount rate for the requested maturity.

Daily GBM paths (ceil(252 * T) steps per year) feed the Monte Carlo
prices of an at-the-money European call, an arithmetic Asian call, an
up-and-out call, and a cash-or-nothing digital call. The European
headline price is checked against Black-Scholes within three standard
errors (headline parity_z), and an independent validation stream runs
its own parity check (validation_z); the two z-scores are reported
separately and never substituted for each other.

Per the contract, each run writes results/approach1/<dataset>/metrics.json
(keys params, metrics, fit_seconds, history) plus figures.html,
estimators.html and performance_profile.txt under the same directory;
the seed splits into training (reserved, calibration is deterministic),
validation (validation_z parity check), and testing streams
(headline parity_z, estimator comparison, greeks, RMSE analysis).
"""

from __future__ import annotations

import argparse
import cProfile
import importlib.util
import io
import json
import math
import pstats
import random
import sys
import time
import timeit
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from rich.console import Console
from rich.table import Table
from scipy.stats import norm

REPO_ROOT = Path(__file__).resolve().parents[1]
FETCH_PATH = REPO_ROOT / "data" / "fetch.py"
TRADING_DAYS_PER_YEAR = 252
MIN_HISTORY_YEARS = 5
FIRST_DAY_TOLERANCE_DAYS = 10
FUTURES_DATASETS = ("if0", "cu0")
CASH_INDEX = "csi300"

SHIBOR_TENOR_YEARS = (1 / 365, 7 / 365, 14 / 365, 1 / 12, 0.25, 0.5, 0.75, 1.0)
SHIBOR_TENOR_LABELS = ("O/N", "1W", "2W", "1M", "3M", "6M", "9M", "1Y")
SHIBOR_RATE_COLUMNS = ("rate_on", "rate_1w", "rate_2w", "rate_1m", "rate_3m", "rate_6m", "rate_9m", "rate_1y")

MC_PATHS = 100_000
MC_Z_LIMIT = 3.0
STEPS_PER_YEAR = 252
BARRIER_MULTIPLE = 1.5
HISTORY_CHECKPOINTS = 10
RESULTS_ROOT = REPO_ROOT / "results" / "approach1"
REFERENCE_PAIRS = 1_000_000
RMSE_PATH_COUNTS = (100, 300, 1000, 3000, 10000, 30000)
RMSE_REPS = (4096, 1024, 512, 256, 64, 32)
GREEK_PATHS = 50_000
DELTA_BUMPS_REL = (0.10, 0.01, 0.001)
VEGA_BUMPS = (0.005, 0.002, 0.001)
PERF_PATHS = 1024
PERF_SCALAR_REPEATS = 3
PERF_VECTORIZED_REPEATS = 50

console = Console()


def daily_steps(maturity_years: float) -> int:
    """Daily step count for a maturity: ceil(252 * T), at least one step."""
    return max(1, math.ceil(STEPS_PER_YEAR * maturity_years))


def control_coefficient(target: np.ndarray, control: np.ndarray, axis: int = 0) -> np.ndarray:
    """OLS beta of target on control along axis, using matching sample moments.

    Sample covariance and sample variance both use ddof=1 so the ratio equals
    the unbiased affine-control regression coefficient; mixing moment
    normalizations would scale beta by (N-1)/N.
    """
    target, control = np.broadcast_arrays(np.asarray(target, dtype=float), np.asarray(control, dtype=float))
    if target.shape[axis] != control.shape[axis] or target.shape[axis] < 2:
        raise ValueError("control_coefficient needs matched inputs with at least two samples along the axis")
    count = target.shape[axis]
    target_mean = target.mean(axis=axis, keepdims=True)
    control_mean = control.mean(axis=axis, keepdims=True)
    covariance = ((target - target_mean) * (control - control_mean)).sum(axis=axis) / (count - 1)
    variance = ((control - control_mean) ** 2).sum(axis=axis) / (count - 1)
    return np.divide(covariance, variance, out=np.zeros_like(covariance), where=variance > 0)


def load_fetch_module():
    if not FETCH_PATH.is_file():
        raise SystemExit(f"fetch module missing: {FETCH_PATH}")
    spec = importlib.util.spec_from_file_location("mqf_fetch", FETCH_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot build an import spec for {FETCH_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mqf_fetch"] = module
    spec.loader.exec_module(module)
    return module


def load_clean_frames(paths: dict[str, Path]) -> dict[str, pd.DataFrame]:
    frames = {}
    for name, path in paths.items():
        frame = pd.read_csv(path, parse_dates=["date"])
        frame["day"] = frame["date"].dt.date
        frames[name] = frame
    return frames


def calibration_window(frame: pd.DataFrame, valuation: date, dataset: str) -> pd.DataFrame:
    if valuation > frame["day"].iloc[-1]:
        raise ValueError(
            f"{dataset}: valuation date {valuation.isoformat()} is past the end of the data "
            f"(last trading day {frame['day'].iloc[-1].isoformat()})"
        )
    window = frame.loc[frame["day"] <= valuation].sort_values("day")
    if window.empty:
        first = frame["day"].iloc[0]
        raise ValueError(
            f"{dataset}: no snapshot rows on or before {valuation.isoformat()} (data starts {first.isoformat()})"
        )
    last = window["day"].iloc[-1]
    if last < valuation:
        console.print(
            f"[yellow]note:[/] {dataset} has no trading data on {valuation.isoformat()}; "
            f"calibrating through the last earlier close ({last.isoformat()})"
        )
    return window


def require_market_history(days: list[date], dataset: str) -> None:
    first, last = days[0], days[-1]
    span_days = (last - first).days
    minimum_days = MIN_HISTORY_YEARS * 365 - FIRST_DAY_TOLERANCE_DAYS
    if len(days) < 2 or span_days < minimum_days:
        raise ValueError(
            f"{dataset}: {span_days} calendar days between actual trading days "
            f"({first.isoformat()}..{last.isoformat()}) is below the {MIN_HISTORY_YEARS}-year requirement"
        )


def calibrate_gbm(close: pd.Series) -> dict:
    levels = close.to_numpy(dtype=float)
    if levels.size < 2:
        raise ValueError("GBM calibration needs at least two closes")
    log_returns = np.diff(np.log(levels))
    vol = math.sqrt(TRADING_DAYS_PER_YEAR) * float(np.std(log_returns, ddof=1))
    log_drift = TRADING_DAYS_PER_YEAR * float(np.mean(log_returns))
    return {
        "return_observations": int(log_returns.size),
        "vol": vol,
        "log_drift": log_drift,
        "level_drift": log_drift + 0.5 * vol * vol,
    }


def shibor_discount_rate(shibor: pd.DataFrame, valuation: date, maturity_years: float) -> dict:
    lowest, highest = SHIBOR_TENOR_YEARS[0], SHIBOR_TENOR_YEARS[-1]
    if not lowest <= maturity_years <= highest:
        raise ValueError(
            f"maturity of {maturity_years} years lies outside the quoted SHIBOR tenor range "
            f"[{lowest:.4f}, {highest:.0f}] years; interpolation without extrapolation is impossible"
        )
    usable = shibor.loc[shibor["day"] <= valuation].sort_values("day")
    if usable.empty:
        first = shibor["day"].iloc[0]
        raise ValueError(
            f"no SHIBOR fixing on or before {valuation.isoformat()} (fixings start {first.isoformat()})"
        )
    fixing = usable.iloc[-1]
    quotes = np.array([float(fixing[column]) for column in SHIBOR_RATE_COLUMNS])
    if not np.all(np.isfinite(quotes)):
        raise ValueError(f"SHIBOR fixing {fixing['day'].isoformat()} has missing tenor quotes; cannot interpolate")
    simple_quote = float(np.interp(maturity_years, SHIBOR_TENOR_YEARS, quotes))
    discount_rate = math.log1p(simple_quote * maturity_years) / maturity_years
    return {
        "fixing_date": fixing["day"],
        "maturity_years": maturity_years,
        "simple_quote": simple_quote,
        "discount_rate": discount_rate,
    }


def black_scholes_call(spot: float, strike: float, rate: float, vol: float, maturity_years: float) -> float:
    sqrt_t = math.sqrt(maturity_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * maturity_years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    return spot * norm.cdf(d1) - strike * math.exp(-rate * maturity_years) * norm.cdf(d2)


def simulate_gbm_daily(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float, track_geometric: bool = False) -> dict:
    steps = daily_steps(maturity_years)
    dt = maturity_years / steps
    drift = (rate - 0.5 * vol * vol) * dt
    diffusion = vol * math.sqrt(dt)
    prices = np.full(MC_PATHS, spot, dtype=float)
    running_sum = np.zeros(MC_PATHS)
    running_max = np.full(MC_PATHS, spot)
    log_sum = np.zeros(MC_PATHS) if track_geometric else None
    for _ in range(steps):
        prices *= np.exp(drift + diffusion * rng.standard_normal(MC_PATHS))
        running_sum += prices
        np.maximum(running_max, prices, out=running_max)
        if track_geometric:
            log_sum += np.log(prices)
    states = {
        "terminal": prices,
        "average": running_sum / steps,
        "maximum": running_max,
        "steps": steps,
        "dt": dt,
    }
    if track_geometric:
        states["geometric"] = np.exp(log_sum / steps)
    return states


def antithetic_states(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float, n_paths: int = MC_PATHS, track_geometric: bool = False) -> dict:
    pairs = n_paths // 2
    steps = daily_steps(maturity_years)
    dt = maturity_years / steps
    drift = (rate - 0.5 * vol * vol) * dt
    diffusion = vol * math.sqrt(dt)
    plus = np.full(pairs, spot)
    minus = np.full(pairs, spot)
    plus_sum = np.zeros(pairs)
    minus_sum = np.zeros(pairs)
    plus_max = np.full(pairs, spot)
    minus_max = np.full(pairs, spot)
    plus_log = np.zeros(pairs) if track_geometric else None
    minus_log = np.zeros(pairs) if track_geometric else None
    for _ in range(steps):
        z = rng.standard_normal(pairs)
        plus *= np.exp(drift + diffusion * z)
        minus *= np.exp(drift - diffusion * z)
        plus_sum += plus
        minus_sum += minus
        np.maximum(plus_max, plus, out=plus_max)
        np.maximum(minus_max, minus, out=minus_max)
        if track_geometric:
            plus_log += np.log(plus)
            minus_log += np.log(minus)
    states = {
        "terminal": np.concatenate([plus, minus]),
        "average": np.concatenate([plus_sum, minus_sum]) / steps,
        "maximum": np.concatenate([plus_max, minus_max]),
        "pairs": pairs,
        "steps": steps,
        "dt": dt,
    }
    if track_geometric:
        states["geometric"] = np.concatenate([np.exp(plus_log / steps), np.exp(minus_log / steps)])
    return states


def payoff_arrays(terminal: np.ndarray, average: np.ndarray, maximum: np.ndarray, strike: float, barrier: float) -> dict:
    terminal_call = np.maximum(terminal - strike, 0.0)
    return {
        "european": terminal_call,
        "asian": np.maximum(average - strike, 0.0),
        "up_and_out": terminal_call * (maximum < barrier),
        "digital": (terminal > strike).astype(float),
    }


def discounted_stats(payoff: np.ndarray, rate: float, maturity_years: float) -> dict:
    discount = math.exp(-rate * maturity_years)
    discounted = discount * payoff
    return {
        "price": float(discounted.mean()),
        "standard_error": float(discounted.std(ddof=1) / math.sqrt(payoff.size)),
    }


def split_seeds(seed: int) -> dict[str, int]:
    children = np.random.SeedSequence(seed).spawn(3)
    return {
        label: int(child.generate_state(1)[0])
        for label, child in zip(("training", "validation", "testing"), children)
    }


def convergence_history(discounted: np.ndarray) -> dict:
    counts = np.unique(np.ceil(np.linspace(discounted.size / HISTORY_CHECKPOINTS, discounted.size, HISTORY_CHECKPOINTS)).astype(int))
    n = np.arange(1, discounted.size + 1)
    running_mean = np.cumsum(discounted) / n
    sum_squares = np.cumsum(discounted * discounted)
    running_variance = (sum_squares - n * running_mean * running_mean) / np.maximum(n - 1, 1)
    running_standard_error = np.sqrt(running_variance / n)
    return {
        "paths": [int(c) for c in counts],
        "running_price": [float(running_mean[c - 1]) for c in counts],
        "running_standard_error": [float(running_standard_error[c - 1]) for c in counts],
    }


def validate_european(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float) -> dict:
    simulated = simulate_gbm_daily(rng, spot, vol, rate, maturity_years)
    terminal_call = np.maximum(simulated["terminal"] - spot, 0.0)
    discount = math.exp(-rate * maturity_years)
    stats = discounted_stats(terminal_call, rate, maturity_years)
    analytic = float(black_scholes_call(spot, spot, rate, vol, maturity_years))
    z = (stats["price"] - analytic) / stats["standard_error"]
    return {
        "steps": simulated["steps"],
        "price": stats["price"],
        "standard_error": stats["standard_error"],
        "black_scholes": analytic,
        "z": z,
        "history": convergence_history(discount * terminal_call),
    }


def price_payoffs(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float) -> dict:
    strike = spot
    barrier = BARRIER_MULTIPLE * spot
    simulated = simulate_gbm_daily(rng, spot, vol, rate, maturity_years)
    payoffs = payoff_arrays(simulated["terminal"], simulated["average"], simulated["maximum"], strike, barrier)
    estimates = {name: discounted_stats(payoff, rate, maturity_years) for name, payoff in payoffs.items()}
    return {"strike": strike, "barrier": barrier, "simulated": simulated, "estimates": estimates}


def antithetic_estimates(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float) -> dict:
    barrier = BARRIER_MULTIPLE * spot
    states = antithetic_states(rng, spot, vol, rate, maturity_years)
    payoffs = payoff_arrays(states["terminal"], states["average"], states["maximum"], spot, barrier)
    discount = math.exp(-rate * maturity_years)
    pairs = states["pairs"]
    estimates = {}
    for name, payoff in payoffs.items():
        pair_average = 0.5 * (payoff[:pairs] + payoff[pairs:])
        estimates[name] = {
            "price": float(discount * pair_average.mean()),
            "standard_error": float(discount * pair_average.std(ddof=1) / math.sqrt(pairs)),
        }
    return {"estimates": estimates, "pairs": pairs, "steps": states["steps"]}


def geometric_asian_call(spot: float, strike: float, rate: float, vol: float, maturity_years: float, steps: int) -> float:
    dt = maturity_years / steps
    drift_log = (rate - 0.5 * vol * vol) * dt
    mirror_variance = vol * vol * dt * (steps + 1) * (2 * steps + 1) / (6 * steps)
    mean_log = math.log(spot) + drift_log * (steps + 1) / 2
    forward = math.exp(mean_log + 0.5 * mirror_variance)
    d1 = (mean_log + mirror_variance - math.log(strike)) / math.sqrt(mirror_variance)
    d2 = d1 - math.sqrt(mirror_variance)
    return math.exp(-rate * maturity_years) * (forward * norm.cdf(d1) - strike * norm.cdf(d2))


def geometric_cv_asian(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float) -> dict:
    simulated = simulate_gbm_daily(rng, spot, vol, rate, maturity_years, track_geometric=True)
    barrier = BARRIER_MULTIPLE * spot
    payoffs = payoff_arrays(simulated["terminal"], simulated["average"], simulated["maximum"], spot, barrier)
    discount = math.exp(-rate * maturity_years)
    target = discount * payoffs["asian"]
    control = discount * np.maximum(simulated["geometric"] - spot, 0.0)
    analytic_control = geometric_asian_call(spot, spot, rate, vol, maturity_years, simulated["steps"])
    beta = float(control_coefficient(target, control, axis=0))
    adjusted = target - beta * (control - analytic_control)
    return {
        "price": float(adjusted.mean()),
        "standard_error": float(adjusted.std(ddof=1) / math.sqrt(target.size)),
        "beta": beta,
        "control_price": analytic_control,
        "steps": simulated["steps"],
    }


def greek_engine(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float) -> dict:
    steps = daily_steps(maturity_years)
    dt = maturity_years / steps
    strike = spot
    barrier = BARRIER_MULTIPLE * spot
    draws = np.empty((steps, GREEK_PATHS))
    for step in range(steps):
        draws[step] = rng.standard_normal(GREEK_PATHS)

    def simulate(spot_bump: float = 0.0, vol_bump: float = 0.0) -> dict:
        bumped_spot = spot + spot_bump
        bumped_vol = vol + vol_bump
        drift = (rate - 0.5 * bumped_vol * bumped_vol) * dt
        diffusion = bumped_vol * math.sqrt(dt)
        prices = np.full(GREEK_PATHS, bumped_spot)
        running_sum = np.zeros(GREEK_PATHS)
        sens_sum = np.zeros(GREEK_PATHS)
        running_max = np.full(GREEK_PATHS, bumped_spot)
        for step in range(steps):
            prices *= np.exp(drift + diffusion * draws[step])
            running_sum += prices
            running_max = np.maximum(running_max, prices)
            sens_sum += prices * (np.log(prices) - math.log(bumped_spot) - (rate + 0.5 * bumped_vol * bumped_vol) * (step + 1) * dt) / bumped_vol
        terminal_sens = prices * (np.log(prices) - math.log(bumped_spot) - (rate + 0.5 * bumped_vol * bumped_vol) * maturity_years) / bumped_vol
        return {
            "terminal": prices,
            "average": running_sum / steps,
            "maximum": running_max,
            "sens": sens_sum / steps,
            "terminal_sens": terminal_sens,
        }

    discount = math.exp(-rate * maturity_years)
    base = simulate()
    terminal_call = np.maximum(base["terminal"] - strike, 0.0)
    european_payoff = discount * terminal_call
    asian_payoff = discount * np.maximum(base["average"] - strike, 0.0)
    tau_european = (base["terminal"] > strike).astype(float)
    tau_asian = (base["average"] > strike).astype(float)

    def delta_stats(payoff_plus: np.ndarray, payoff_minus: np.ndarray, size: float) -> dict:
        diff = payoff_plus - payoff_minus
        return {
            "value": float(diff.mean() / (2 * size)),
            "standard_error": float(diff.std(ddof=1) / (2 * size * math.sqrt(GREEK_PATHS))),
        }

    def payoff_at(states: dict) -> dict:
        tc = np.maximum(states["terminal"] - strike, 0.0)
        return {"european": discount * tc, "asian": discount * np.maximum(states["average"] - strike, 0.0)}

    pathwise = {}
    for name, tau, level, vega_level in (
        ("european", tau_european, base["terminal"], base["terminal_sens"]),
        ("asian", tau_asian, base["average"], base["sens"]),
    ):
        delta_sample = discount * tau * level / spot
        vega_sample = discount * tau * vega_level
        pathwise[name] = {
            "delta": {"value": float(delta_sample.mean()), "standard_error": float(delta_sample.std(ddof=1) / math.sqrt(GREEK_PATHS))},
            "vega": {"value": float(vega_sample.mean()), "standard_error": float(vega_sample.std(ddof=1) / math.sqrt(GREEK_PATHS))},
        }

    finite_difference = {"delta": {}, "vega": {}}
    for relative_bump in DELTA_BUMPS_REL:
        size = relative_bump * spot
        plus = payoff_at(simulate(spot_bump=size))
        minus = payoff_at(simulate(spot_bump=-size))
        finite_difference["delta"][f"{relative_bump:.3%}"] = {
            name: delta_stats(plus[name], minus[name], size) for name in ("european", "asian")
        }
    for vol_bump in VEGA_BUMPS:
        plus = payoff_at(simulate(vol_bump=vol_bump))
        minus = payoff_at(simulate(vol_bump=-vol_bump))
        finite_difference["vega"][f"{vol_bump:g}"] = {
            name: delta_stats(plus[name], minus[name], vol_bump) for name in ("european", "asian")
        }

    sqrt_t = math.sqrt(maturity_years)
    d1 = math.log(spot / strike) / (vol * sqrt_t) + (rate + 0.5 * vol * vol) * maturity_years / (vol * sqrt_t)
    return {
        "paths": GREEK_PATHS,
        "steps": steps,
        "pathwise": pathwise,
        "finite_difference": finite_difference,
        "analytic_european": {"delta": float(norm.cdf(d1)), "vega": float(spot * norm.pdf(d1) * sqrt_t)},
    }


def fit_log_log_slope(counts: list[int], errors: list[float]) -> dict:
    log_n = np.log(np.asarray(counts, dtype=float))
    log_rmse = np.log(np.asarray(errors, dtype=float))
    slope, intercept = np.polyfit(log_n, log_rmse, 1)
    return {"slope": float(slope), "factor_at_1000_paths": float(math.exp(intercept + slope * math.log(1000)))}


def asian_reference(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float) -> dict:
    """High-precision independent arithmetic-Asian reference.

    Plain antithetic pairs over the full one-million-pair budget are enhanced
    with the analytic geometric-Asian control variate (antithetic + CV), so
    the reference is far more precise than a plain-antithetic estimate, which
    must not be treated as exact. The draw is independent of the RMSE-study
    replicates, which use the same stream only afterwards.
    """
    states = antithetic_states(rng, spot, vol, rate, maturity_years, n_paths=2 * REFERENCE_PAIRS, track_geometric=True)
    discount = math.exp(-rate * maturity_years)
    target = discount * np.maximum(states["average"] - spot, 0.0)
    control = discount * np.maximum(states["geometric"] - spot, 0.0)
    analytic_control = geometric_asian_call(spot, spot, rate, vol, maturity_years, states["steps"])
    pairs = states["pairs"]
    target = 0.5 * (target[:pairs] + target[pairs:])
    control = 0.5 * (control[:pairs] + control[pairs:])
    beta = float(control_coefficient(target, control, axis=0))
    adjusted = target - beta * (control - analytic_control)
    return {
        "price": float(adjusted.mean()),
        "standard_error": float(adjusted.std(ddof=1) / math.sqrt(REFERENCE_PAIRS)),
        "pairs": REFERENCE_PAIRS,
        "steps": states["steps"],
        "beta": beta,
        "control_price": analytic_control,
    }


def rmse_study(rng: np.random.Generator, spot: float, vol: float, rate: float, maturity_years: float, asian_reference_result: dict, european_truth: float) -> dict:
    asian_truth = asian_reference_result["price"]
    steps = daily_steps(maturity_years)
    dt = maturity_years / steps
    drift = (rate - 0.5 * vol * vol) * dt
    diffusion = vol * math.sqrt(dt)
    strike = spot
    discount = math.exp(-rate * maturity_years)
    records = {
        "plain_european": [],
        "antithetic_european": [],
        "plain_asian": [],
        "antithetic_asian": [],
        "cv_asian": [],
    }
    for n_paths, reps in zip(RMSE_PATH_COUNTS, RMSE_REPS):
        shape = (reps, n_paths)
        prices = np.full(shape, spot)
        running_sum = np.zeros(shape)
        log_sum = np.zeros(shape)
        for _ in range(steps):
            prices *= np.exp(drift + diffusion * rng.standard_normal(shape))
            running_sum += prices
            log_sum += np.log(prices)
        average = running_sum / steps
        geometric = np.exp(log_sum / steps)
        control_price = geometric_asian_call(spot, strike, rate, vol, maturity_years, steps)
        target = discount * np.maximum(average - strike, 0.0)
        control = discount * np.maximum(geometric - strike, 0.0)
        mean_target = target.mean(axis=1)
        mean_control = control.mean(axis=1)
        beta = control_coefficient(target, control, axis=1)
        cv_rows = mean_target - beta * (mean_control - control_price)

        pairs = n_paths // 2
        plus = np.full((reps, pairs), spot)
        minus = np.full((reps, pairs), spot)
        plus_sum = np.zeros((reps, pairs))
        minus_sum = np.zeros((reps, pairs))
        for _ in range(steps):
            z = rng.standard_normal((reps, pairs))
            plus *= np.exp(drift + diffusion * z)
            minus *= np.exp(drift - diffusion * z)
            plus_sum += plus
            minus_sum += minus
        plus_average = plus_sum / steps
        minus_average = minus_sum / steps
        a_plus = np.maximum(plus_average - strike, 0.0)
        a_minus = np.maximum(minus_average - strike, 0.0)
        e_plus = np.maximum(plus - strike, 0.0)
        e_minus = np.maximum(minus - strike, 0.0)

        plain_european_rows = (discount * np.maximum(prices - strike, 0.0)).mean(axis=1)
        antithetic_european_rows = (0.5 * discount * (e_plus + e_minus)).mean(axis=1)
        plain_asian_rows = target.mean(axis=1)
        antithetic_asian_rows = (0.5 * discount * (a_plus + a_minus)).mean(axis=1)

        for key, rows in (
            ("plain_european", plain_european_rows),
            ("antithetic_european", antithetic_european_rows),
            ("plain_asian", plain_asian_rows),
            ("antithetic_asian", antithetic_asian_rows),
            ("cv_asian", cv_rows),
        ):
            squared = (rows - asian_truth) ** 2 if "asian" in key else (rows - european_truth) ** 2
            records[key].append(float(math.sqrt(squared.mean())))

    counts = list(RMSE_PATH_COUNTS)
    result = {
        "path_counts": counts,
        "replications": list(RMSE_REPS),
        "european_truth": european_truth,
        "asian_truth": asian_reference_result["price"],
        "asian_reference": {
            "price": asian_reference_result["price"],
            "standard_error": asian_reference_result["standard_error"],
            "pairs": asian_reference_result["pairs"],
            "steps": asian_reference_result["steps"],
            "beta": asian_reference_result["beta"],
            "control_price": asian_reference_result["control_price"],
        },
        "series": {},
        "slopes": {},
    }
    for key, values in records.items():
        result["series"][key] = {"rmse": values}
        result["slopes"][key] = fit_log_log_slope(counts, values)
    return result


def scalar_average_price(spot: float, vol: float, rate: float, steps: int, dt: float, paths: int, seed: int = 0) -> float:
    """Pure-python GBM running-average price, using the same dt = T/steps as every other engine."""
    rng = random.Random(seed)
    drift_step = (rate - 0.5 * vol * vol) * dt
    diffusion_step = vol * math.sqrt(dt)
    accumulator = 0.0
    for _ in range(paths):
        price = spot
        for _ in range(steps):
            price *= math.exp(drift_step + diffusion_step * rng.gauss(0.0, 1.0))
            accumulator += price
    return accumulator / (paths * steps)


def vectorized_average_price(spot: float, vol: float, rate: float, steps: int, dt: float, paths: int, seed: int = 0) -> float:
    """NumPy GBM running-average price sharing the scalar engine's exact step size dt = T/steps."""
    gen = np.random.default_rng(seed)
    prices = np.full(paths, spot)
    accumulator = np.zeros(paths)
    for _ in range(steps):
        step_factor = np.exp((rate - 0.5 * vol * vol) * dt + vol * math.sqrt(dt) * gen.standard_normal(paths))
        prices *= step_factor
        accumulator += prices
    return float(accumulator.mean() / steps)


def performance_comparison(spot: float, vol: float, rate: float, maturity_years: float) -> dict:
    steps = daily_steps(maturity_years)
    dt = maturity_years / steps

    def scalar_run() -> float:
        return scalar_average_price(spot, vol, rate, steps, dt, PERF_PATHS)

    def vectorized_run() -> float:
        return vectorized_average_price(spot, vol, rate, steps, dt, PERF_PATHS)

    profiler = cProfile.Profile()
    profiler.enable()
    scalar_run()
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(6)
    profile_text = stream.getvalue()

    timers = {"scalar_run": scalar_run, "vectorized_run": vectorized_run}
    scalar_seconds = timeit.Timer(stmt="scalar_run()", globals=timers).timeit(PERF_SCALAR_REPEATS) / PERF_SCALAR_REPEATS
    vectorized_seconds = timeit.Timer(stmt="vectorized_run()", globals=timers).timeit(PERF_VECTORIZED_REPEATS) / PERF_VECTORIZED_REPEATS
    return {
        "paths": PERF_PATHS,
        "steps": steps,
        "scalar_seconds": scalar_seconds,
        "vectorized_seconds": vectorized_seconds,
        "speedup": scalar_seconds / max(vectorized_seconds, 1e-12),
        "profile_excerpt": profile_text,
    }


def print_estimator_table(name: str, plain: dict, antithetic: dict, control: dict) -> None:
    table = Table(
        title=f"{name.upper()} estimator comparison - plain vs antithetic vs geometric CV "
        f"({MC_PATHS:,} paths, {STEPS_PER_YEAR} daily steps)"
    )
    for column in ("Payoff", "Plain price", "Plain SE", "Anti price", "Anti SE", "SE ratio", "Var ratio", "CV price", "CV SE", "CV var ratio"):
        table.add_column(column)
    for payoff in ("european", "asian", "up_and_out", "digital"):
        plain_est = plain["estimates"][payoff]
        anti_est = antithetic["estimates"][payoff]
        cv_est = control if payoff == "asian" else None
        se_ratio = plain_est["standard_error"] / anti_est["standard_error"]
        row = [
            payoff.replace("_", " "),
            f"{plain_est['price']:.4f}",
            f"{plain_est['standard_error']:.4f}",
            f"{anti_est['price']:.4f}",
            f"{anti_est['standard_error']:.4f}",
            f"{se_ratio:.3f}",
            f"{se_ratio * se_ratio:.3f}",
        ]
        if cv_est is not None:
            cv_ratio = plain_est["standard_error"] / cv_est["standard_error"]
            row.extend([f"{cv_est['price']:.4f}", f"{cv_est['standard_error']:.4f}", f"{cv_ratio * cv_ratio:.3f}"])
        else:
            row.extend(["", "", ""])
        table.add_row(*row)
    console.print(table)
    console.print(
        f"SE ratio = SE_plain / SE_variant; variance ratio = (SE ratio)^2. "
        f"Geometric control variate for {name.upper()}: beta = {control['beta']:.4f}, "
        f"analytic geometric price = {control['control_price']:.4f}"
    )
    console.print()


def print_greek_table(name: str, greeks: dict) -> None:
    table = Table(title=f"{name.upper()} greeks - pathwise vs central finite difference ({GREEK_PATHS:,} paths)")
    for column, justify in (
        ("Measure", "left"),
        ("Pathwise", "right"),
        ("Pathwise SE", "right"),
        ("FD @ bump 1", "right"),
        ("FD @ bump 2", "right"),
        ("FD @ bump 3", "right"),
        ("Analytic", "right"),
    ):
        table.add_column(column, justify=justify)
    for payoff in ("european", "asian"):
        pathwise = greeks["pathwise"][payoff]
        for greek in ("delta", "vega"):
            fd = greeks["finite_difference"][greek]
            analytic = ""
            if payoff == "european":
                analytic = f"{greeks['analytic_european'][greek]:.4f}"
            bumps_labels = list(fd)
            table.add_row(
                f"{payoff} {greek}",
                f"{pathwise[greek]['value']:.4f}",
                f"{pathwise[greek]['standard_error']:.4f}",
                f"{fd[bumps_labels[0]][payoff]['value']:.4f} ({fd[bumps_labels[0]][payoff]['standard_error']:.4f})",
                f"{fd[bumps_labels[1]][payoff]['value']:.4f} ({fd[bumps_labels[1]][payoff]['standard_error']:.4f})",
                f"{fd[bumps_labels[2]][payoff]['value']:.4f} ({fd[bumps_labels[2]][payoff]['standard_error']:.4f})",
                analytic,
            )
    console.print(
        "FD bump sizes - delta: " + ", ".join(f"{b:.3%}" for b in DELTA_BUMPS_REL)
        + "; vega: " + ", ".join(f"{b:g}" for b in VEGA_BUMPS)
    )
    console.print(table)
    console.print()


def print_rmse_table(rmse: dict) -> None:
    table = Table(title="log-log RMSE convergence (slopes from OLS on log N vs log RMSE)")
    table.add_column("Payoff")
    table.add_column("Estimator")
    table.add_column("Slope")
    table.add_column("RMSE @ " + str(RMSE_PATH_COUNTS[-1]) + " paths")
    for payoff in ("european", "asian"):
        estimators = ("plain", "antithetic") if payoff == "european" else ("plain", "antithetic", "cv")
        for estimator in estimators:
            series = rmse["series"][f"{estimator}_{payoff}"]
            table.add_row(payoff, estimator, f"{rmse['slopes'][f'{estimator}_{payoff}']['slope']:+.3f}", f"{series['rmse'][-1]:.4f}")
    console.print(table)
    reference = rmse["asian_reference"]
    console.print(
        f"Truths: European = Black-Scholes ({rmse['european_truth']:.4f}), "
        f"asian = independent antithetic+geometric-CV reference ({reference['pairs']:,} pairs, "
        f"{reference['steps']} steps): {reference['price']:.4f} with its own standard error "
        f"{reference['standard_error']:.2e}; the plotted RMSE is measured against this uncertain reference"
    )
    console.print()


def print_performance_table(name: str, performance: dict) -> None:
    table = Table(title=f"{name.upper()} python loop vs NumPy ({performance['paths']:,} paths x {performance['steps']} steps)")
    table.add_column("Implementation")
    table.add_column("Seconds")
    table.add_column("Speedup", justify="right")
    table.add_row("pure python loop (math + random.gauss)", f"{performance['scalar_seconds']:.4f}", "1x")
    table.add_row("NumPy vectorized", f"{performance['vectorized_seconds']:.4f}", f"{performance['speedup']:.1f}x")
    console.print(table)
    console.print()


def make_estimator_figure(rmse: dict, greeks: dict) -> go.Figure:
    figure = make_subplots(rows=2, cols=1, vertical_spacing=0.14, subplot_titles=("Asian call log-log RMSE", "European call log-log RMSE"))
    counts = rmse["path_counts"]
    for row, payoff, keys in ((1, "asian", ("plain_asian", "antithetic_asian", "cv_asian")), (2, "european", ("plain_european", "antithetic_european"))):
        for key in keys:
            label = key.replace("_" + payoff, "").replace("_", " ")
            figure.add_trace(
                go.Scatter(
                    x=counts,
                    y=rmse["series"][key]["rmse"],
                    mode="lines+markers",
                    name=f"{label} (slope {rmse['slopes'][key]['slope']:+.3f})",
                    line={"width": 2},
                ),
                row=row,
                col=1,
            )
    figure.update_xaxes(title_text="paths", type="log", row=1, col=1)
    figure.update_xaxes(title_text="paths", type="log", row=2, col=1)
    figure.update_yaxes(title_text="RMSE", type="log", row=1, col=1)
    figure.update_yaxes(title_text="RMSE", type="log", row=2, col=1)
    figure.update_layout(
        title="log-log RMSE convergence - plain vs antithetic vs geometric control variate",
        legend={"orientation": "h"},
        margin={"t": 110},
    )
    return figure


def print_pricing_table(name: str, spot: float, vol: float, rate: float, maturity_years: float, priced: dict, validation: dict) -> None:
    steps = priced["simulated"]["steps"]
    strike_text = f"{priced['strike']:.2f}"
    headline = priced["estimates"]["european"]
    headline_z = (headline["price"] - validation["black_scholes"]) / headline["standard_error"]
    table = Table(
        title=f"{name.upper()} payoffs - {MC_PATHS:,} paths, {steps} daily steps "
        f"(S0 = {spot:.2f}, vol = {vol:.4f}, r = {rate:.6%})"
    )
    for column in ("Payoff", "Settings", "Price", "Std error", "BS price", "parity_z (headline)"):
        table.add_column(column, justify="right" if column in ("Price", "Std error", "BS price", "parity_z (headline)") else "left")
    european = priced["estimates"]["european"]
    table.add_row(
        "European call",
        f"K = S0, terminal payoff",
        f"{european['price']:.4f}",
        f"{european['standard_error']:.4f}",
        f"{validation['black_scholes']:.4f}",
        f"{headline_z:+.3f}",
    )
    asian = priced["estimates"]["asian"]
    table.add_row(
        "Arithmetic Asian call",
        f"K = S0, mean of {steps} daily nodes (dt..T) minus K",
        f"{asian['price']:.4f}",
        f"{asian['standard_error']:.4f}",
        "",
        "",
    )
    up_and_out = priced["estimates"]["up_and_out"]
    table.add_row(
        "Up-and-out call",
        f"K = S0, B = {BARRIER_MULTIPLE:g}*S0 = {priced['barrier']:.2f}, daily monitoring, no rebate",
        f"{up_and_out['price']:.4f}",
        f"{up_and_out['standard_error']:.4f}",
        "",
        "",
    )
    digital = priced["estimates"]["digital"]
    table.add_row(
        "Digital call",
        f"cash-or-nothing, pays 1 if S_T > K = {strike_text}",
        f"{digital['price']:.4f}",
        f"{digital['standard_error']:.4f}",
        "",
        "",
    )
    console.print(table)
    console.print(
        f"European headline check (testing stream) for {name.upper()}: MC {european['price']:.4f} "
        f"(SE {european['standard_error']:.4f}) vs Black-Scholes {validation['black_scholes']:.4f}, "
        f"parity_z = {headline_z:+.3f} "
        f"({'within' if abs(headline_z) <= MC_Z_LIMIT else 'OUTSIDE'} the {MC_Z_LIMIT:.0f}-SE band)"
    )
    console.print(
        f"European validation check (separate validation stream) for {name.upper()}: "
        f"MC {validation['price']:.4f} (SE {validation['standard_error']:.4f}) vs Black-Scholes "
        f"{validation['black_scholes']:.4f}, validation_z = {validation['z']:+.3f} "
        f"({'within' if abs(validation['z']) <= MC_Z_LIMIT else 'OUTSIDE'} the {MC_Z_LIMIT:.0f}-SE band)"
    )
    console.print()


def build_results(
    name: str,
    args: argparse.Namespace,
    seeds: dict[str, int],
    spot: float,
    vol: float,
    calibration_estimates: dict,
    window_start: date,
    window_end: date,
    rate: dict,
    validation: dict,
    priced: dict,
    fit_seconds: float,
) -> dict:
    headline = priced["estimates"]["european"]
    headline_z = (headline["price"] - validation["black_scholes"]) / headline["standard_error"]
    return {
        "params": {
            "question": "q2",
            "approach": "approach1",
            "dataset": name,
            "seed": args.seed,
            "child_seeds": seeds,
            "seed_usage": {
                "training": "GBM calibration from log returns (deterministic, stream reserved)",
                "validation": "European call parity check against Black-Scholes",
                "testing": "four sub-streams: headline prices, estimator comparison, greeks, RMSE study",
            },
            "valuation_date": args.valuation_date.isoformat(),
            "maturity_years": args.maturity_years,
            "paths": MC_PATHS,
            "steps_per_year": STEPS_PER_YEAR,
            "steps": priced["simulated"]["steps"],
            "barrier_multiple": BARRIER_MULTIPLE,
            "barrier": priced["barrier"],
            "calibration": {
                "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
                "return_observations": calibration_estimates["return_observations"],
                "spot": spot,
                "vol": vol,
                "log_drift": calibration_estimates["log_drift"],
                "level_drift": calibration_estimates["level_drift"],
            },
            "discount": {
                "fixing_date": rate["fixing_date"].isoformat(),
                "simple_quote": rate["simple_quote"],
                "continuous_rate": rate["discount_rate"],
            },
        },
        "metrics": {
            "european": {
                "price": priced["estimates"]["european"]["price"],
                "standard_error": priced["estimates"]["european"]["standard_error"],
                "black_scholes": validation["black_scholes"],
                "parity_z": headline_z,
                "within_parity_band": bool(abs(headline_z) <= MC_Z_LIMIT),
                "validation": {
                    "price": validation["price"],
                    "standard_error": validation["standard_error"],
                    "black_scholes": validation["black_scholes"],
                    "validation_z": validation["z"],
                },
            },
            "asian": {
                "price": priced["estimates"]["asian"]["price"],
                "standard_error": priced["estimates"]["asian"]["standard_error"],
            },
            "up_and_out": {
                "price": priced["estimates"]["up_and_out"]["price"],
                "standard_error": priced["estimates"]["up_and_out"]["standard_error"],
            },
            "digital": {
                "price": priced["estimates"]["digital"]["price"],
                "standard_error": priced["estimates"]["digital"]["standard_error"],
            },
        },
        "fit_seconds": fit_seconds,
        "history": validation["history"],
    }


def save_results(name: str, payload: dict, validation: dict, priced: dict, rmse: dict, greeks: dict, performance: dict) -> list[Path]:
    directory = RESULTS_ROOT / name
    directory.mkdir(parents=True, exist_ok=True)
    metrics_path = directory / "metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    figures_path = directory / "figures.html"
    make_figure(name, validation, priced).write_html(
        figures_path, include_plotlyjs=True, full_html=True
    )
    estimators_path = directory / "estimators.html"
    make_estimator_figure(rmse, greeks).write_html(
        estimators_path, include_plotlyjs=True, full_html=True
    )
    profile_path = directory / "performance_profile.txt"
    profile_path.write_text(performance["profile_excerpt"], encoding="utf-8")
    return [metrics_path, figures_path, estimators_path, profile_path]


def make_figure(name: str, validation: dict, priced: dict) -> go.Figure:
    history = validation["history"]
    headline = priced["estimates"]["european"]
    headline_z = (headline["price"] - validation["black_scholes"]) / headline["standard_error"]
    paths = np.array(history["paths"], dtype=float)
    running = np.array(history["running_price"])
    band = 3.0 * np.array(history["running_standard_error"])
    figure = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.58, 0.42],
        vertical_spacing=0.14,
        subplot_titles=(
            "European call: Monte Carlo convergence (validation stream)",
            "Headline payoff prices (testing stream)",
        ),
    )
    figure.add_trace(
        go.Scatter(x=paths, y=running - band, mode="lines", line={"width": 0}, hoverinfo="skip", showlegend=False),
        row=1, col=1,
    )
    figure.add_trace(
        go.Scatter(x=paths, y=running + band, mode="lines", fill="tonexty", fillcolor="rgba(31,119,180,0.18)", line={"width": 0}, hoverinfo="skip", showlegend=False),
        row=1, col=1,
    )
    figure.add_trace(
        go.Scatter(x=paths, y=running, mode="lines+markers", name="running MC price"),
        row=1, col=1,
    )
    figure.add_hline(
        y=validation["black_scholes"], line_dash="dash", annotation_text="Black-Scholes",
        row=1, col=1,
    )
    figure.update_xaxes(title_text="paths", type="log", row=1, col=1)
    figure.update_yaxes(title_text="price", row=1, col=1)
    payoffs = ("european", "asian", "up_and_out", "digital")
    figure.add_trace(
        go.Bar(
            x=[payoff.replace("_", " ") for payoff in payoffs],
            y=[priced["estimates"][payoff]["price"] for payoff in payoffs],
            error_y={
                "type": "data",
                "array": [priced["estimates"][payoff]["standard_error"] for payoff in payoffs],
                "visible": True,
            },
            name="price with standard error",
        ),
        row=2, col=1,
    )
    figure.update_layout(
        title=f"{name.upper()} Q2 approach 1 - {MC_PATHS:,} paths, {priced['simulated']['steps']} daily steps, "
        f"headline parity_z = {headline_z:+.3f} (testing stream), validation_z = {validation['z']:+.3f} (validation stream)",
        showlegend=False,
        margin={"t": 120},
    )
    return figure


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="approach1_q2", description="Q2 approach 1 milestone: GBM calibration on verified snapshots")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed, kept stable and reused by the later simulation milestones")
    parser.add_argument("--valuation-date", type=date.fromisoformat, default=date(2025, 12, 31), help="calibration cut-off (ISO YYYY-MM-DD, inclusive)")
    parser.add_argument("--maturity-years", type=float, default=1.0, help="discount horizon in years, within the quoted SHIBOR tenor range")
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("--seed must be nonnegative")
    if not math.isfinite(args.maturity_years) or args.maturity_years <= 0.0:
        parser.error("--maturity-years must be a positive finite number")
    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    seeds = split_seeds(args.seed)
    testing_streams = {label: int(child.generate_state(1)[0]) for label, child in zip(("headline", "estimators", "greeks", "analysis"), np.random.SeedSequence(seeds["testing"]).spawn(4))}
    console.print(
        f"Seed {args.seed} split - training {seeds['training']} (calibration, deterministic), "
        f"validation {seeds['validation']} (parity check), "
        f"testing streams {json.dumps(testing_streams)}"
    )
    rng_validation = np.random.default_rng(seeds["validation"])
    rng_headline = np.random.default_rng(testing_streams["headline"])
    rng_estimators = np.random.default_rng(testing_streams["estimators"])
    rng_greeks = np.random.default_rng(testing_streams["greeks"])
    rng_analysis = np.random.default_rng(testing_streams["analysis"])

    fetch = load_fetch_module()
    try:
        manifest = fetch.load_manifest()
        paths = fetch.verify_q2_snapshots(manifest)
    except fetch.VerificationError as error:
        console.print(f"[red]snapshot verification failed:[/] {error}")
        raise SystemExit(2)
    fetch.print_coverage(manifest)

    frames = load_clean_frames(paths)
    datasets = manifest["q2"]["datasets"]
    valuation = args.valuation_date

    table = Table(title=f"GBM calibration - log returns of daily closes through {valuation.isoformat()}")
    for column in ("Dataset", "Unit", "Window", "Return obs", "Vol / year", "Log drift mu_log", "Level drift mu"):
        table.add_column(column, justify="right" if column not in ("Dataset", "Unit", "Window") else "left")

    try:
        calibrated = {}
        for name in FUTURES_DATASETS:
            window = calibration_window(frames[name], valuation, name)
            days = window["day"].tolist()
            require_market_history(days, name)
            estimates = calibrate_gbm(window["close"])
            calibrated[name] = {"window": window, "estimates": estimates}
            table.add_row(
                name.upper(),
                datasets[name].get("clean_value_units", ""),
                f"{days[0].isoformat()} .. {days[-1].isoformat()}",
                str(estimates["return_observations"]),
                f"{estimates['vol']:.6f}",
                f"{estimates['log_drift']:.6f}",
                f"{estimates['level_drift']:.6f}",
            )
        console.print(table)

        rate = shibor_discount_rate(frames["shibor"], valuation, args.maturity_years)
        rate_table = Table(title=f"SHIBOR discounting for maturity {args.maturity_years:.6g} years")
        for column in ("Fixing date", "Maturity (years)", "Interpolated simple quote", "Continuous discount rate"):
            rate_table.add_column(column)
        rate_table.add_row(
            rate["fixing_date"].isoformat(),
            f"{rate['maturity_years']:.6g}",
            f"{rate['simple_quote']:.6%}",
            f"{rate['discount_rate']:.6%}",
        )
        console.print(rate_table)
        console.print()

        for name in FUTURES_DATASETS:
            window = calibrated[name]["window"]
            spot = float(window["close"].iloc[-1])
            vol = calibrated[name]["estimates"]["vol"]
            started = time.perf_counter()
            validation = validate_european(rng_validation, spot, vol, rate["discount_rate"], args.maturity_years)
            priced = price_payoffs(rng_headline, spot, vol, rate["discount_rate"], args.maturity_years)
            plain_estimates = price_payoffs(rng_estimators, spot, vol, rate["discount_rate"], args.maturity_years)
            antithetic = antithetic_estimates(rng_estimators, spot, vol, rate["discount_rate"], args.maturity_years)
            control = geometric_cv_asian(rng_estimators, spot, vol, rate["discount_rate"], args.maturity_years)
            reference = asian_reference(rng_analysis, spot, vol, rate["discount_rate"], args.maturity_years)
            rmse = rmse_study(rng_analysis, spot, vol, rate["discount_rate"], args.maturity_years, reference, validation["black_scholes"])
            greeks = greek_engine(rng_greeks, spot, vol, rate["discount_rate"], args.maturity_years)
            performance = performance_comparison(spot, vol, rate["discount_rate"], args.maturity_years)
            fit_seconds = time.perf_counter() - started
            payload = build_results(
                name,
                args,
                seeds,
                spot,
                vol,
                calibrated[name]["estimates"],
                window["day"].iloc[0],
                window["day"].iloc[-1],
                rate,
                validation,
                priced,
                fit_seconds,
            )
            payload["params"]["child_seeds"] = {"testing_streams": testing_streams, **seeds}
            payload["metrics"]["estimators"] = {
                "plain": plain_estimates["estimates"],
                "antithetic": antithetic["estimates"],
                "geometric_cv_asian": control,
                "path_counts_equal": MC_PATHS,
            }
            payload["metrics"]["greeks"] = greeks
            payload["metrics"]["rmse"] = rmse
            performance_record = {key: value for key, value in performance.items() if key != "profile_excerpt"}
            payload["metrics"]["performance"] = performance_record
            saved = save_results(name, payload, validation, priced, rmse, greeks, performance)
            print_pricing_table(name, spot, vol, rate["discount_rate"], args.maturity_years, priced, validation)
            print_estimator_table(name, plain_estimates, antithetic, control)
            print_greek_table(name, greeks)
            print_rmse_table(rmse)
            print_performance_table(name, performance)
            console.print("[green]saved[/] " + ", ".join(str(path.relative_to(REPO_ROOT)) for path in saved))
            headline = priced["estimates"]["european"]
            headline_z = (headline["price"] - validation["black_scholes"]) / headline["standard_error"]
            if abs(headline_z) > MC_Z_LIMIT:
                console.print(
                    f"[red]parity check failed for {name.upper()}:[/] the daily-step Monte Carlo headline price "
                    f"deviates {abs(headline_z):.2f} standard errors from Black-Scholes (limit {MC_Z_LIMIT:.0f}); "
                    f"validation_z = {validation['z']:+.3f}"
                )
                raise SystemExit(3)
        cash = calibration_window(frames[CASH_INDEX], valuation, CASH_INDEX)
        cash_last = cash.iloc[-1]
        console.print(
            f"CSI 300 cash index close as of {cash_last['day'].isoformat()}: {float(cash_last['close']):.2f}"
        )
    except ValueError as error:
        console.print(f"[red]calibration error:[/] {error}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
