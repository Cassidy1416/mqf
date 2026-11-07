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
    files = sorted(args.results.glob("approach*/**/metrics.json"))
    records = []
    for path in files:
        records.append({"approach": path.parent.parent.name, "path": str(path), "payload": json.loads(path.read_text())})
    table = Table(title="Q4 comparison")
    table.add_column("Approach")
    table.add_column("Fit seconds")
    table.add_column("Headline metric")
    for record in records:
        payload = record["payload"]
        if record["approach"] == "approach1":
            years = payload["metrics"].get("years", [])
            last = payload["metrics"].get("per_year", {}).get(str(max(years)), {}) if years else {}
            headline = f"modularity={last.get('communities', {}).get('modularity', 'n/a')}"
        else:
            dimensions = payload["metrics"].get("dimensions", {})
            best = payload["metrics"].get("best_sweep")
            if best is None:
                best_value = max((item.get("learned", {}).get("auc", 0.0), dimension) for dimension, item in dimensions.items()) if dimensions else (0.0, "n/a")
                headline = f"best learned AUC={best_value[0]:.3f} (d={best_value[1]})"
            else:
                headline = f"best learned AUC={best['auc']:.3f} ({best['configuration']}, d={best['dimension']})"
        table.add_row(record["approach"], f"{payload.get('fit_seconds', 0.0):.2f}", headline)
    Console().print(table)
    figure = go.Figure()
    for record in records:
        if record["approach"] == "approach2":
            dimensions = record["payload"]["metrics"].get("dimensions", {})
            x = sorted(int(value) for value in dimensions)
            figure.add_trace(go.Scatter(x=x, y=[dimensions[str(value)]["learned"]["auc"] for value in x], mode="lines+markers", name="node2vec learned AUC"))
    figure.update_layout(title="Q4 model comparison", xaxis_title="Embedding dimension", yaxis_title="AUC")
    save_plot(figure, args.out)


if __name__ == "__main__":
    main()
