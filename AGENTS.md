# MQF Advanced Programming project contract

## Objective

Complete both approaches for each of Q2, Q3, and Q4 in one reproducible repository.
Q2 compares Monte Carlo estimators and transaction-cost hedges on a GBM model calibrated from Chinese futures data.
Q3 compares classical and recurrent macroeconomic models using information available at each forecast date.
Q4 compares classical graph analytics and learned embeddings on a Chinese ownership or trade network.
The group owns the mathematical choices, verifies the results, and writes the report.
Confirm any methodological ambiguity with the group before making it part of the experiment.

## Environment and commands

Use Python 3.13 and `uv` with dependencies declared in `pyproject.toml` and pinned in `uv.lock`.
Run from the repository root.
These are the target commands for the project entry points.
Update the commands and the README together as each milestone becomes runnable.

```sh
export UV_CACHE_DIR="$PWD/.cache/uv"
uv sync --locked --python 3.13
uv run --locked python data/fetch.py --question q2 --offline
uv run --locked python code/approach1_q2.py --seed 42
uv run --locked python code/approach2_q2.py --seed 42
uv run --locked python code/approach1_q3.py --seed 42
uv run --locked python code/approach2_q3.py --seed 42
uv run --locked python code/approach1_q4.py --seed 42
uv run --locked python code/approach2_q4.py --seed 42
uv run --locked python code/compare.py
```

## Data and experiments

Commit offline fallback snapshots for every external source used.
Use `data/fetch.py` for retrieval and offline verification, and record source, query, retrieval date, schema, and SHA-256 in `data/metadata.json`.
Validate files before using them, and preserve the committed snapshots during experiment runs.
Q2 uses the fixed IF0, CU0, CSI 300, and SHIBOR snapshots for 2020 through 2025.
Use daily closes for Q2 calibration, document the continuous-contract roll convention, and keep simulation seeds for training, validation, and testing separate.
For Q3, use expanding-window validation, apply publication lags, and fit preprocessing within each training window.
For Q4, split link-prediction edges 80/10/10 before computing training graph features or embeddings.

Default to `--seed 42`, seed each stochastic step, and record residual nondeterminism.
Each approach exposes an argparse CLI and writes `results/approachN/<dataset>/metrics.json` using question-specific dataset names and the keys `params`, `metrics`, `fit_seconds`, and `history`.
Use Rich for terminal summaries and embed Plotly JavaScript in the saved HTML.
The comparison script writes `results/comparison.html` and ranks only comparable experiments.

## Session and Git rules

Use an approved OpenCode-compatible terminal agent for implementation.
Keep all writes and tool caches within the repository, and ignore local caches, environments, and credentials.
Obtain explicit approval in the coding session before destructive or irreversible operations.
Keep documented commands reproducible from a clean clone.
Commit completed milestones separately using conventional prefixes such as `data:`, `feat:`, `exp:`, and `report:`.
Export the complete coding session, redact secrets, and include the Markdown transcript in `SESSION.md`.
Tag the final reviewed commit `submission`.
