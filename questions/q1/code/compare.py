from __future__ import annotations

import argparse
import json
from pathlib import Path

import plotly.graph_objects as go
from rich.console import Console
from rich.table import Table

from common import ROOT, save_plot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "comparison.html")
    args = parser.parse_args()
    paths = [args.results / "approach1" / "market" / "metrics.json", args.results / "approach2" / "differentiable" / "metrics.json"]
    payloads = {path.parent.parent.name: json.loads(path.read_text()) for path in paths if path.exists()}
    table = Table(title="Q1 comparison")
    table.add_column("Approach")
    table.add_column("Fit seconds")
    table.add_column("Headline")
    if "approach1" in payloads:
        metrics = payloads["approach1"]["metrics"]
        table.add_row("approach1", f"{payloads['approach1']['fit_seconds']:.2f}", f"median repricing={metrics['svi']['summary']['repricing_median']:.4f}; butterfly={metrics['svi']['summary']['butterfly_violations']}")
    if "approach2" in payloads:
        metrics = payloads["approach2"]["metrics"]
        table.add_row("approach2", f"{payloads['approach2']['fit_seconds']:.2f}", f"dropout SVI={metrics['dropout_30_percent']['svi_median_relative_error']:.4f}; neural={metrics['dropout_30_percent']['neural_median_relative_error']:.4f}")
    Console().print(table)
    figure = go.Figure()
    if "approach1" in payloads:
        summary = payloads["approach1"]["metrics"]["svi"]["summary"]
        figure.add_trace(go.Bar(x=["SVI repricing median", "SVI repricing p95"], y=[summary["repricing_median"], summary["repricing_p95"]], name="Approach 1"))
    if "approach2" in payloads:
        dropout = payloads["approach2"]["metrics"]["dropout_30_percent"]
        figure.add_trace(go.Bar(x=["SVI dropout median", "Neural dropout median"], y=[dropout["svi_median_relative_error"], dropout["neural_median_relative_error"]], name="Approach 2"))
    figure.update_layout(title="Q1 calibration comparison", yaxis_title="Relative price error")
    save_plot(figure, args.out)


if __name__ == "__main__":
    main()
