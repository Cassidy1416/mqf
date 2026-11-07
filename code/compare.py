"""Aggregate saved results and rank only methods sharing an evaluation set."""
from __future__ import annotations
import argparse
import html
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def comparable_groups(root=ROOT):
    groups, inventory = {}, []
    for path in sorted((root / "questions").glob("*/results/approach*/*/metrics.json")):
        run = json.loads(path.read_text())
        if not {"params", "metrics", "fit_seconds", "history"} <= run.keys():
            raise ValueError(f"Invalid metrics schema: {path}")
        q = path.relative_to(root / "questions").parts[0]
        inventory.append(str(path.relative_to(root)))
        metrics = run["metrics"]
        if q == "q2":
            for key, case in metrics.get("hedging", {}).items():
                group = f"Q2 {path.parent.name} {key}: CVaR95 (lower is better)"
                groups[group] = [("learned", case["deep"]["cvar95"]), ("Black-Scholes", case["bs"]["cvar95"])]
        elif q == "q1" and "dropout_30_percent" in metrics:
            case = metrics["dropout_30_percent"]
            ids = case.get("evaluation_quote_ids", [])
            fingerprint = hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()
            if ids and len(set(ids)) == len(ids) == case.get("common_evaluation_rows") and fingerprint == case.get("evaluation_fingerprint"):
                groups["Q1 identical held-out quotes: price-relative median error (lower is better)"] = [
                    ("SVI refit", case["svi_median_relative_error"]), ("Neural surface", case["neural_median_relative_error"])]
        elif q == "q4" and "learned" in metrics and "baselines" in metrics:
            # Reject the historical leaky schema, which had no train-graph or temporal audit.
            audit = metrics.get("split_audit", {})
            static = audit.get("validation_test_positive_absent_from_training_graph") and audit.get("evaluation_fingerprint") and metrics.get("selection", {}).get("validation_only")
            audit = metrics.get("information_audit", {})
            temporal = audit.get("test_labels_used_for_selection") is False and audit.get("embeddings_use_only_forecast_graph") and metrics.get("evaluation_fingerprint")
            if static or temporal:
                groups[f"Q4 {path.parent.name}: final test AUC (higher is better)"] = [(name, case["auc"]) for name, case in {"learned": metrics["learned"], **metrics["baselines"]}.items()]
    for title, methods in groups.items():
        if any(value is None or not math.isfinite(value) for _, value in methods):
            raise ValueError(f"Nonfinite or missing comparison value in {title}")
        groups[title] = sorted(methods, key=lambda row: (-row[1] if "higher is better" in title else row[1], row[0]))
    return inventory, groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    inventory, groups = comparable_groups(args.root)
    if not inventory:
        raise ValueError("No saved metrics found")
    sections = ["<h1>Q1, Q2 and Q4 experiment comparisons</h1><p>Rankings apply only within each named task and evaluation set. Scientific HTML figures are linked below.</p>"]
    for q in ("q1", "q2", "q4"):
        sections.append(f'<p><a href="../questions/{q}/results/comparison.html">{q.upper()} detailed figures and comparisons</a></p>')
    for title, rows in groups.items():
        print(title)
        sections.append(f"<h2>{html.escape(title)}</h2><table><tr><th>Rank</th><th>Method</th><th>Value</th></tr>")
        for rank, (method, value) in enumerate(rows, 1):
            print(f"  {rank}. {method}: {value:.6g}")
            sections.append(f"<tr><td>{rank}</td><td>{html.escape(method)}</td><td>{value:.6g}</td></tr>")
        sections.append("</table>")
    sections.append("<h2>Metrics inventory</h2><ul>" + "".join(f"<li>{html.escape(p)}</li>" for p in inventory) + "</ul>")
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><title>MQF comparisons</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px}table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:8px 16px;text-align:left}</style><body>' + "\n".join(sections) + '</body></html>'
    target = args.root / "results/comparison.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page)
    return target


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Comparison failed: {error}")
