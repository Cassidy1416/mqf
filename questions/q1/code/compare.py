from __future__ import annotations
import importlib.util
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def main():
    spec = importlib.util.spec_from_file_location("root_comparisons", PROJECT / "code/compare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, all_groups = module.comparable_groups(PROJECT)
    groups = {title: rows for title, rows in all_groups.items() if title.startswith(ROOT.name.upper())}
    if not groups:
        raise ValueError("No comparable, audited results found")
    chart = make_subplots(rows=len(groups), cols=1, subplot_titles=list(groups))
    for index, (title, rows) in enumerate(groups.items(), 1):
        table = Table(title=title)
        for name in ("Rank", "Method", "Value"):
            table.add_column(name)
        for rank, (method, value) in enumerate(rows, 1):
            table.add_row(str(rank), method, f"{value:.6g}")
        Console().print(table)
        chart.add_trace(go.Bar(x=[r[0] for r in rows], y=[r[1] for r in rows], showlegend=False), row=index, col=1)
    chart.update_layout(height=max(420, 400*len(groups)), title=ROOT.name.upper() + " comparisons within identical evaluation sets")
    chart.write_html(ROOT / "results/comparison.html", include_plotlyjs=True)


if __name__ == "__main__":
    main()
