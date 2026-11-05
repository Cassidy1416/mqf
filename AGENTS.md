# Agent Contract

## Goal

Build a reproducible study of China ETF and CSI 300 option implied-volatility surfaces. The project must implement both the classical market pipeline and the differentiable PyTorch calibration pipeline, including Black–Scholes inversion, SVI fitting, neural-surface calibration, no-arbitrage diagnostics, robustness tests, and comparison tables.

## Environment and commands

Use Python 3.13 or 3.14 with `uv`. Install pinned dependencies from `pyproject.toml`. The canonical commands are:

```bash
uv venv --python 3.13
source .venv/bin/activate
uv sync
python data/fetch.py --seed 42
python code/approach1_market_pipeline.py --seed 42
python code/approach2_differentiable.py --seed 42
python code/compare.py
```

## Reproducibility conventions

The default seed is 42 and every stochastic operation accepts `--seed`. Historical snapshots are committed when permitted by the assignment; otherwise fetch scripts, metadata, and SHA-256 checksums are committed. Each approach writes `results/approachN/<dataset>/metrics.json` with keys `params`, `metrics`, `fit_seconds`, and `history`. Figures are self-contained Plotly HTML files.

## Agent rules

Work only inside this repository. Keep caches in ignored in-repository directories. Propose destructive or irreversible actions before performing them. Preserve raw inputs, provenance, and failed-fit diagnostics. Make a conventional Git commit after each milestone. Mathematical choices, assumptions, and limitations must be reviewed by the group and recorded in `report.md`.

