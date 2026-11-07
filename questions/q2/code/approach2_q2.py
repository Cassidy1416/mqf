"""Q2B: PyTorch option pricing and CVaR hedging of a short European call.

The three exotic payoffs use the same daily monitoring and strikes as Q2A.
The hedge experiment uses a vanilla call so its benchmark is the exact
Black-Scholes delta. Trading gains accrue to expiry as in the exam equation.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date

import plotly.graph_objects as go
import torch
from plotly.subplots import make_subplots
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from torch import nn

from approach1_q2 import (
    BARRIER_MULTIPLE,
    FUTURES_DATASETS,
    MC_PATHS,
    MC_Z_LIMIT,
    REPO_ROOT,
    STEPS_PER_YEAR,
    black_scholes_call,
    calibrate_gbm,
    calibration_window,
    load_clean_frames,
    load_fetch_module,
    require_market_history,
    shibor_discount_rate,
    split_seeds,
)

TRAIN_PATHS = 2**17
VALIDATION_PATHS = 8192
TEST_PATHS = 32768
BATCH_SIZE = 4096
EPOCHS = 5
HIDDEN_WIDTH = 16
LEARNING_RATE = 0.003
REBALANCE_DAYS = (1, 5, 21)
COST_BPS = (0, 10, 50)
CVAR_ALPHA = 0.95
PAYOFF_NAMES = ("european", "asian", "up_and_out", "digital")
RESULTS_ROOT = REPO_ROOT / "results" / "approach2"
console = Console()


def generator(seed: int) -> torch.Generator:
    return torch.Generator().manual_seed(seed)


def gbm_paths(rng, spot, vol, rate, maturity, steps, count, dtype=torch.float32):
    dt = maturity / steps
    log_moves = torch.randn(count, steps, generator=rng, dtype=dtype)
    log_moves.mul_(vol * math.sqrt(dt)).add_((rate - vol**2 / 2) * dt)
    relatives = log_moves.cumsum(dim=1).exp_().mul_(spot)
    return torch.cat((torch.full((count, 1), spot, dtype=dtype), relatives), dim=1)


def payoff_tensors(paths, strike, barrier):
    terminal = paths[:, -1]
    european = (terminal - strike).clamp_min(0)
    return {
        "european": european,
        "asian": (paths[:, 1:].mean(dim=1) - strike).clamp_min(0),
        "up_and_out": european * (paths.amax(dim=1) < barrier),
        "digital": (terminal > strike).to(paths.dtype),
    }


def price_options(rng, spot, vol, rate, maturity, steps):
    samples = {name: [] for name in PAYOFF_NAMES}
    discount = math.exp(-rate * maturity)
    for start in range(0, MC_PATHS, BATCH_SIZE):
        count = min(BATCH_SIZE, MC_PATHS - start)
        paths = gbm_paths(rng, spot, vol, rate, maturity, steps, count, torch.float64)
        for name, payoff in payoff_tensors(paths, spot, BARRIER_MULTIPLE * spot).items():
            samples[name].append(discount * payoff)

    estimates = {}
    for name, batches in samples.items():
        discounted = torch.cat(batches)
        estimates[name] = {
            "price": float(discounted.mean()),
            "standard_error": float(discounted.std()) / math.sqrt(MC_PATHS),
        }
    european = estimates["european"]
    benchmark = float(black_scholes_call(spot, spot, rate, vol, maturity))
    european["black_scholes"] = benchmark
    european["parity_z"] = (european["price"] - benchmark) / european["standard_error"]
    return estimates


class HedgeNet(nn.Sequential):
    def __init__(self):
        super().__init__(
            nn.Linear(2, HIDDEN_WIDTH),
            nn.Tanh(),
            nn.Linear(HIDDEN_WIDTH, 1),
            nn.Sigmoid(),
            nn.Flatten(start_dim=1),
        )


def hedge_inputs(paths, maturity, rebalance_days):
    """Prepare the decision grid and the short-call payoff in units of S0."""
    steps = paths.shape[1] - 1
    indices = list(range(0, steps, rebalance_days))
    prices = paths[:, indices + [steps]] / paths[:, :1]
    times = torch.tensor(indices, dtype=paths.dtype) * (maturity / steps)
    features = torch.stack((prices[:, :-1], times.expand_as(prices[:, :-1])), dim=-1)
    return features, prices, (prices[:, -1] - 1).clamp_min(0)


def hedge_pnl(positions, prices, payoff, growth, cost):
    """Terminal P&L divided by S0, with positions in units of the underlying."""
    changes = torch.diff(positions, dim=1, prepend=torch.zeros_like(positions[:, :1]))
    gains = (positions * torch.diff(prices, dim=1) * growth).sum(dim=1)
    fees = cost * (changes.abs() * prices[:, :-1]).sum(dim=1)
    return gains - fees - payoff


def black_scholes_delta(features, rate, vol, maturity):
    relative_price, time = features.unbind(dim=-1)
    remaining = maturity - time
    d1 = (relative_price.log() + (rate + vol**2 / 2) * remaining) / (vol * remaining.sqrt())
    return torch.special.ndtr(d1)


def cvar(losses):
    # Average the worst 5%, with a fractional weight at the empirical cutoff.
    tail_count = losses.numel() * (1 - CVAR_ALPHA)
    worst = losses.topk(math.ceil(tail_count), sorted=True).values
    return (worst.sum() - (worst.numel() - tail_count) * worst[-1]) / tail_count


def train_hedge(training, validation, growth, cost, model_seed, shuffle_seed):
    torch.manual_seed(model_seed)
    model = HedgeNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    shuffle = generator(shuffle_seed)
    features, prices, payoff = training
    valid_features, valid_prices, valid_payoff = validation
    best_loss = math.inf
    best_epoch = 0
    best_weights = None
    history = []

    for epoch in range(1, EPOCHS + 1):
        for indices in torch.randperm(len(payoff), generator=shuffle).split(BATCH_SIZE):
            optimizer.zero_grad(set_to_none=True)
            pnl = hedge_pnl(model(features[indices]), prices[indices], payoff[indices], growth, cost)
            cvar(-pnl).backward()
            optimizer.step()

        with torch.no_grad():
            loss = float(cvar(-hedge_pnl(model(valid_features), valid_prices, valid_payoff, growth, cost)))
        history.append(loss)
        if loss < best_loss:
            best_loss = loss
            best_epoch = epoch
            best_weights = {name: value.detach().clone() for name, value in model.state_dict().items()}

    if best_weights is None:
        raise ValueError("Hedge training produced no finite validation CVaR")
    model.load_state_dict(best_weights)
    model.eval()
    return model, {"validation_cvar_per_s0": history, "best_epoch": best_epoch}


def pnl_stats(pnl, spot):
    pnl = pnl.double() * spot
    return {
        "cvar95": float(cvar(-pnl)),
        "mean_pnl": float(pnl.mean()),
        "pnl_variance": float(pnl.var()),
    }


def run_hedges(name, spot, vol, rate, maturity, steps, seeds):
    paths = [
        gbm_paths(generator(seeds[split]), spot, vol, rate, maturity, steps, count)
        for split, count in (
            ("training", TRAIN_PATHS),
            ("validation", VALIDATION_PATHS),
            ("testing", TEST_PATHS),
        )
    ]
    cases = {}
    histories = {}
    for days in REBALANCE_DAYS:
        training, validation, testing = [hedge_inputs(batch, maturity, days) for batch in paths]
        test_features, test_prices, test_payoff = testing
        growth = torch.exp(rate * (maturity - test_features[0, :, 1]))
        baseline = black_scholes_delta(test_features, rate, vol, maturity)

        for bps in COST_BPS:
            key = f"h{days}_c{bps}"
            cost = bps * 1e-4
            started = time.perf_counter()
            model, history = train_hedge(
                training, validation, growth, cost, seeds["training"], seeds["training"] + 1
            )
            with torch.no_grad():
                positions = torch.cat([model(batch) for batch in test_features.split(BATCH_SIZE)])
                deep = pnl_stats(hedge_pnl(positions, test_prices, test_payoff, growth, cost), spot)
                bs = pnl_stats(hedge_pnl(baseline, test_prices, test_payoff, growth, cost), spot)
            cases[key] = {"rebalance_days": days, "cost_bps": bps, "deep": deep, "bs": bs}
            histories[key] = history
            console.print(
                f"{name.upper():3}  {days:2} days  {bps:2} bp  "
                f"CVaR {deep['cvar95']:.4f} vs {bs['cvar95']:.4f}  "
                f"({time.perf_counter() - started:.1f}s)"
            )
    return cases, histories


def print_results(name, prices, cases):
    pricing = Table(title=f"{name.upper()} PyTorch option prices")
    for heading in ("Payoff", "Price", "SE", "Black-Scholes", "z"):
        pricing.add_column(heading)
    for payoff, result in prices.items():
        benchmark = f"{result['black_scholes']:.6g}" if payoff == "european" else ""
        z = f"{result['parity_z']:+.3f}" if payoff == "european" else ""
        pricing.add_row(payoff, f"{result['price']:.6g}", f"{result['standard_error']:.6g}", benchmark, z)
    console.print(pricing)

    hedging = Table(title=f"{name.upper()} short European call hedges on fresh test paths")
    for heading in ("Days", "Cost (bp)", "Method", "CVaR95 loss", "Mean P&L", "P&L variance"):
        hedging.add_column(heading)
    for case in cases.values():
        for key, method in (("deep", "Deep hedge"), ("bs", "Black-Scholes")):
            result = case[key]
            hedging.add_row(
                str(case["rebalance_days"]), str(case["cost_bps"]), method,
                f"{result['cvar95']:.5g}", f"{result['mean_pnl']:.5g}", f"{result['pnl_variance']:.5g}",
            )
    console.print(hedging)


def save_results(name, payload):
    folder = RESULTS_ROOT / name
    folder.mkdir(parents=True, exist_ok=True)
    cases = list(payload["metrics"]["hedging"].values())
    labels = [f"{case['rebalance_days']}d, {case['cost_bps']} bp" for case in cases]
    chart = make_subplots(rows=3, cols=1, subplot_titles=("CVaR95 loss", "Mean P&L", "P&L variance"))
    for row, metric in enumerate(("cvar95", "mean_pnl", "pnl_variance"), start=1):
        for key, label, color in (("deep", "Deep hedge", "#09676b"), ("bs", "Black-Scholes", "#a14a2d")):
            chart.add_trace(
                go.Bar(
                    x=labels, y=[case[key][metric] for case in cases], name=label,
                    marker_color=color, legendgroup=key, showlegend=row == 1,
                ),
                row=row, col=1,
            )
    chart.update_layout(title=f"{name.upper()} hedge comparison", height=900, barmode="group")
    chart.write_html(folder / "figures.html", include_plotlyjs=True)
    (folder / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    console.print(f"Saved {folder.relative_to(REPO_ROOT)}/metrics.json and figures.html")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--valuation-date", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--maturity-years", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.seed < 0 or not math.isfinite(args.maturity_years) or args.maturity_years <= 0:
        parser.error("Provide a nonnegative seed and a positive finite maturity.")
    torch.set_num_threads(2)
    maturity = args.maturity_years
    steps = math.ceil(STEPS_PER_YEAR * maturity)
    seeds = split_seeds(args.seed)
    fetch = load_fetch_module()
    console.print(Panel("Q2B PyTorch pricing and deep hedging", title="MQF"))
    try:
        manifest = fetch.load_manifest()
        frames = load_clean_frames(fetch.verify_q2_snapshots(manifest))
        fetch.print_coverage(manifest)
        curve = shibor_discount_rate(frames["shibor"], args.valuation_date, maturity)
        rate = curve["discount_rate"]

        for name in FUTURES_DATASETS:
            window = calibration_window(frames[name], args.valuation_date, name)
            require_market_history(window["day"].tolist(), name)
            calibration = calibrate_gbm(window["close"])
            spot = float(window["close"].iloc[-1])
            vol = calibration["vol"]
            prices = price_options(generator(seeds["validation"]), spot, vol, rate, maturity, steps)
            z = prices["european"]["parity_z"]
            console.print(f"{name.upper()} PyTorch European pricing check: z = {z:+.3f}")
            if not math.isfinite(z) or abs(z) > MC_Z_LIMIT:
                raise ValueError(f"{name.upper()} PyTorch European price outside the three-SE band")

            started = time.perf_counter()
            cases, histories = run_hedges(name, spot, vol, rate, maturity, steps, seeds)
            seconds = time.perf_counter() - started
            print_results(name, prices, cases)
            save_results(name, {
                "params": {
                    "question": "q2", "approach": "approach2", "dataset": name, "seed": args.seed,
                    "streams": seeds, "model_seed": seeds["training"],
                    "shuffle_seed": seeds["training"] + 1, "torch_threads": torch.get_num_threads(),
                    "torch_version": torch.__version__,
                    "valuation_date": args.valuation_date.isoformat(),
                    "calibration_start": window["day"].iloc[0].isoformat(),
                    "calibration_end": window["day"].iloc[-1].isoformat(),
                    "calibration": calibration, "maturity_years": maturity, "steps": steps,
                    "spot0": spot, "strike": spot, "barrier": BARRIER_MULTIPLE * spot,
                    "discount_rate": rate, "shibor_fixing_date": curve["fixing_date"].isoformat(),
                    "pricing_paths": MC_PATHS, "train_paths": TRAIN_PATHS,
                    "validation_paths": VALIDATION_PATHS, "test_paths": TEST_PATHS,
                    "epochs": EPOCHS, "batch_size": BATCH_SIZE, "learning_rate": LEARNING_RATE,
                    "hidden_width": HIDDEN_WIDTH, "cvar_alpha": CVAR_ALPHA,
                    "rebalance_days": REBALANCE_DAYS, "cost_bps": COST_BPS,
                    "hedged_payoff": "at-the-money European call",
                    "pnl_convention": "Exam terminal P&L, with financing on hedge gains and costs on scheduled trades including entry",
                    "residual_nondeterminism": "CPU runs use seeded generators and two threads. Floating-point results may vary across platforms.",
                },
                "metrics": {"pricing": prices, "hedging": cases},
                "fit_seconds": seconds,
                "history": {"hedging": histories},
            })
    except (fetch.VerificationError, ValueError) as error:
        parser.exit(2, f"Q2B failed: {error}\n")


if __name__ == "__main__":
    main()
