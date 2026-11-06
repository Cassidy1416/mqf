"""Q2 approach 1 - milestone 1: GBM calibration on Chinese futures.

Loads the committed Q2 snapshots through data/fetch.py (which verifies
SHA-256, row counts, headers and date coverage against
data/metadata.json), calibrates per-futures log-return GBM parameters
from closes on or before the valuation date, and reports a
SHIBOR-interpolated continuous discount rate for the requested maturity.

Later milestones add more payoffs, estimators, metrics.json and figures;
nothing under results/ is written yet. The Monte Carlo price of an
at-the-money European call is validated against Black-Scholes within
three standard errors of the estimator.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
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

console = Console()


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


def monte_carlo_call(rng: np.random.Generator, spot: float, strike: float, rate: float, vol: float, maturity_years: float) -> dict:
    z = rng.standard_normal(MC_PATHS)
    terminal = spot * np.exp((rate - 0.5 * vol * vol) * maturity_years + vol * math.sqrt(maturity_years) * z)
    discounted = math.exp(-rate * maturity_years) * np.maximum(terminal - strike, 0.0)
    estimate = float(discounted.mean())
    standard_error = float(discounted.std(ddof=1) / math.sqrt(MC_PATHS))
    return {"paths": MC_PATHS, "estimate": estimate, "standard_error": standard_error}


def pricing_parity_check(rng: np.random.Generator, spot: float, vol: float, rate: dict) -> dict:
    strike = spot
    maturity_years = rate["maturity_years"]
    mc = monte_carlo_call(rng, spot, strike, rate["discount_rate"], vol, maturity_years)
    analytic = black_scholes_call(spot, strike, rate["discount_rate"], vol, maturity_years)
    z = (mc["estimate"] - analytic) / mc["standard_error"]
    return {"strike": strike, "mc": mc, "analytic": analytic, "z": z}


def print_parity_table(parity: dict, rate: dict) -> None:
    mc = parity["mc"]
    table = Table(title="Monte Carlo vs Black-Scholes - European call parity check")
    for column in ("Quantity", "Value"):
        table.add_column(column, justify="right" if column == "Value" else "left")
    table.add_row("Maturity (years)", f"{rate['maturity_years']:.6g}")
    table.add_row("Discount rate", f"{rate['discount_rate']:.6%}")
    table.add_row("Paths", str(mc["paths"]))
    table.add_row("Monte Carlo price", f"{mc['estimate']:.6f}")
    table.add_row("Monte Carlo standard error", f"{mc['standard_error']:.6f}")
    table.add_row("Black-Scholes price", f"{parity['analytic']:.6f}")
    table.add_row("z = (MC - BS) / SE", f"{parity['z']:+.3f}")
    console.print(table)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="approach1_q2", description="Q2 approach 1 milestone: GBM calibration on verified snapshots")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed, kept stable and reused by the later simulation milestones")
    parser.add_argument("--valuation-date", type=date.fromisoformat, default=date(2025, 12, 31), help="calibration cut-off (ISO YYYY-MM-DD, inclusive)")
    parser.add_argument("--maturity-years", type=float, default=1.0, help="discount horizon in years, within the quoted SHIBOR tenor range")
    args = parser.parse_args(argv)
    if not math.isfinite(args.maturity_years) or args.maturity_years <= 0.0:
        parser.error("--maturity-years must be a positive finite number")
    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rng = np.random.default_rng(args.seed)
    console.print(f"RNG seeded with {args.seed} (used by the later Monte Carlo milestones)")

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

        parity = pricing_parity_check(
            rng,
            float(calibrated["if0"]["window"]["close"].iloc[-1]),
            calibrated["if0"]["estimates"]["vol"],
            rate,
        )
        print_parity_table(parity, rate)
        if abs(parity["z"]) > MC_Z_LIMIT:
            console.print(
                f"[red]parity check failed:[/] the Monte Carlo estimate deviates {abs(parity['z']):.2f} "
                f"standard errors from Black-Scholes (limit {MC_Z_LIMIT:.0f})"
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
