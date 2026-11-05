# Agent Contract

## Goal

Build a reproducible China trade-network study using annual bilateral flows. The project must implement both network analytics and a PyTorch node-embedding/link-prediction pipeline, including graph construction verification, graph statistics, MST, Louvain communities, centrality, temporal community migration, node2vec, negative sampling, heuristic baselines, and embedding comparisons.

## Environment and commands

Use Python 3.13 or 3.14 with `uv`. Install pinned dependencies from `pyproject.toml`. The canonical commands are:

```bash
uv venv --python 3.13
source .venv/bin/activate
uv sync
python data/fetch.py --seed 42
python code/approach1_network_analytics.py --seed 42
python code/approach2_node_embeddings.py --seed 42
python code/compare.py
```

## Reproducibility conventions

The default seed is 42 and every stochastic operation accepts `--seed`. Temporal splits, negative-sampling streams, walk generation, and embedding initialization are recorded. Each approach writes `results/approachN/<dataset>/metrics.json` with keys `params`, `metrics`, `fit_seconds`, and `history`. Figures are self-contained Plotly HTML files.

## Agent rules

Work only inside this repository. Keep caches in ignored in-repository directories. Propose destructive or irreversible actions before performing them. Preserve raw inputs, graph-construction metadata, and failed-run diagnostics. Make a conventional Git commit after each milestone. Mathematical choices, proxy labels, and limitations must be reviewed by the group and recorded in `report.md`.

