# Q2 question contract

`questions/q2` implements the Q2 experiment unchanged; see the root `AGENTS.md` for the repository-wide contract and integration rules.

## Scope of this folder

Q2 compares Monte Carlo estimators and transaction-cost hedges on a GBM model calibrated from Chinese futures data.
The model conventions are unchanged: GBM calibration from daily closes of the fixed IF0, CU0, CSI 300 and SHIBOR snapshots for 2020 through 2025.
The continuous main-contract series carries no per-row contract ID and no roll adjustment is applied; the snapshots are committed and must not be regenerated during experiment runs.
Simulation seeds for training, validation, and testing stay separate, and the default seed is 42.
European prices are verified against Black-Scholes in both engines and the z-scores are reported.
Q2A saves estimator results, convergence plots, and profiles beside its metrics; Q2B reports hedged payoff, CVaR, mean P&L, and P&amp;L variance per frequency and cost on held-out paths.

## Running Q2

Nothing here needs to be run from the repository root except through the launcher.
The root launcher verifies the Q2 snapshots and executes the scripts with the working directory set to this folder:

```sh
python3 run.py q2 --offline
```

Equivalent per-question commands (run from `questions/q2/`, unchanged from the imported snapshot):

```sh
uv sync --locked --python 3.13
uv run --locked python data/fetch.py --question q2 --offline
uv run --locked python code/approach1_q2.py --seed 42
uv run --locked python code/approach2_q2.py --seed 42
uv run --locked python code/compare.py
```

Do not upgrade the pins in `pyproject.toml` and `uv.lock`; the launcher uses `uv run --locked --python 3.13` inside this folder.
Scientific scripts, manifests, snapshots, saved metrics and figures, `README.md` and `SESSION.md` are preserved and must not be edited from the root.
