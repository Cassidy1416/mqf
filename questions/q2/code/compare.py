"""Summarize saved experiments and rank Q2 hedges within each scenario."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import plotly.graph_objects as go
from rich.console import Console
from rich.table import Table

RESULTS_ROOT = Path(__file__).resolve().parents[1] / "results"
PAYOFFS = ("european", "asian", "up_and_out", "digital")
RANK_HEADERS = ("Dataset", "Days", "Cost (bp)", "Rank", "Hedge", "CVaR95 loss", "Mean P&L", "P&L variance")


def html_table(title, headers, rows):
    figure = go.Figure(go.Table(
        header={"values": headers, "fill_color": "#dce8e7", "align": "left"},
        cells={"values": list(zip(*rows)), "align": "left", "height": 25},
    ))
    figure.update_layout(title=title, height=110 + 26 * len(rows), margin={"l": 15, "r": 15, "t": 65, "b": 10})
    return figure


def q2_scenario(run):
    params = run["params"]
    if params["approach"] == "approach1":
        spot, vol = (params["calibration"][key] for key in ("spot", "vol"))
        rate = params["discount"]["continuous_rate"]
    else:
        spot, vol, rate = params["spot0"], params["calibration"]["vol"], params["discount_rate"]
    return (
        params["dataset"], params["valuation_date"], params["maturity_years"],
        params["steps"], params["barrier"], spot, vol, rate,
    )


def comparison_rows(runs):
    pricing = {}
    ranked = []
    for run in runs:
        params, metrics = run["params"], run["metrics"]
        if params.get("question") != "q2":
            continue
        approach = params["approach"]
        prices = metrics if approach == "approach1" else metrics["pricing"]
        pricing.setdefault(q2_scenario(run), {})[approach] = prices
        for case in metrics.get("hedging", {}).values():
            methods = [("Deep hedge", case["deep"]), ("Black-Scholes", case["bs"])]
            methods.sort(key=lambda item: item[1]["cvar95"])
            for rank, (label, stats) in enumerate(methods, 1):
                ranked.append((
                    params["dataset"].upper(), case["rebalance_days"], case["cost_bps"], rank,
                    label, f"{stats['cvar95']:.6g}", f"{stats['mean_pnl']:.6g}", f"{stats['pnl_variance']:.6g}",
                ))

    paired = []
    for (dataset, valuation, maturity, *_), engines in sorted(pricing.items()):
        if set(engines) != {"approach1", "approach2"}:
            continue
        for payoff in PAYOFFS:
            left, right = (engines[engine][payoff] for engine in ("approach1", "approach2"))
            paired.append((
                dataset.upper(), valuation, maturity, payoff,
                f"{left['price']:.6g}", f"{left['standard_error']:.6g}",
                f"{right['price']:.6g}", f"{right['standard_error']:.6g}",
            ))
    return paired, ranked


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_ROOT)
    args = parser.parse_args(argv)
    paths = sorted(args.results_dir.glob("approach*/*/metrics.json"))
    if not paths:
        parser.error(f"No approach results found under {args.results_dir}")
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    prices, ranked = comparison_rows(runs)
    inventory = [
        (run["params"].get("question", ""), path.relative_to(args.results_dir).as_posix())
        for path, run in zip(paths, runs)
    ]
    figures = [html_table("Saved experiments", ("Question", "Metrics file"), inventory)]
    if prices:
        figures.append(html_table(
            "Q2 prices at matching model inputs",
            ("Dataset", "Valuation date", "Years", "Payoff", "NumPy price", "NumPy SE", "PyTorch price", "PyTorch SE"),
            prices,
        ))
    if ranked:
        title = "Q2 hedge ranking by CVaR95 within each contract, frequency and cost"
        table = Table(title=title)
        for heading in RANK_HEADERS:
            table.add_column(heading)
        for row in ranked:
            table.add_row(*(str(value) for value in row))
        Console().print(table)
        figures.append(html_table(title, RANK_HEADERS, ranked))

    html = "\n".join(
        figure.to_html(full_html=False, include_plotlyjs=index == 0)
        for index, figure in enumerate(figures)
    )
    destination = args.results_dir / "comparison.html"
    destination.write_text(
        f'<!doctype html><html lang="en"><meta charset="utf-8"><title>MQF comparison</title><body>{html}</body></html>',
        encoding="utf-8",
    )
    Console().print(f"Saved {destination}")


if __name__ == "__main__":
    main()
