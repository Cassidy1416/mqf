# MQF Advanced Programming project contract

## Objective

Implement both approaches for Q1, Q2 and Q4 in one reproducible repository, with each question clearly separated under `questions/`.
Q1 compares classical SVI and differentiable volatility surfaces; Q2 compares Monte Carlo estimators and transaction-cost hedges; Q4 compares classical trade-network analytics, learned static link recovery and chronological future major-link prediction.
The group owns the mathematical decisions, verifies results and writes or approves the final report.
Confirm unresolved methodological ambiguity with the group before changing the experiment.
The user approved full monthly Q1 chain coverage with a SHIBOR zero curve, a separate future Q4 task alongside static recovery, and explicit geographical proxy labels.

## Environment and exact commands

Use Python 3.13 and uv with the separate pinned `questions/qN/pyproject.toml` and `questions/qN/uv.lock` files.
The root pyproject is a standard-library orchestration environment; do not combine incompatible child dependency pins.
Run from the repository root:

```sh
python3 data/fetch.py --offline
python3 run.py all --seed 42
python3 run.py all --stage test --offline
python3 -m unittest discover -s tests -v
python3 code/build_report.py
```

After dependencies are installed, `python3 run.py all --offline --seed 42` is the full offline reproduction command.
Use `python3 run.py q2 --offline` for one question, `--stage compare` for comparisons and `--stage index` for the root comparison alone.
Q4 also exposes `python3 run.py q4 --stage future --offline`.
The launcher sets each script's working directory and Python environment to its question folder and keeps all caches and environments inside the repository.
Use `--dry-run` to inspect commands without writes.

## Data and experiment conventions

Committed snapshots are immutable during experiment runs.
Explicit online fetches stage vendor outputs under ignored question-local `data/raw/` paths and retain the committed fallback; they do not promote a new dataset automatically.
Root `data/metadata.json` indexes child manifests, hashes, provenance, schemas, row counts and date or year coverage.
After a deliberately reviewed child metadata change, run `python3 data/fetch.py --rebuild-manifest --offline`.
Original Q1 snapshots remain in its archive; imported history remains in Git.
Verify hashes, schemas, keys, coverage and appropriate domain constraints before using data.
Q1 joins only past spot and SHIBOR observations, reports failed IVs and locates arbitrage violations.
Q1 robustness compares identical quote IDs and the same market-price denominator.
Q2 calibrates on 2020-2025 closes, preserves the vendor continuous-contract roll convention, uses at least 252 GBM steps per year and separates training, validation and testing streams.
Compute European z-scores from their own price and standard error, and compute antithetic uncertainty on independent pair averages.
Q2B selects checkpoints and stops using validation CVaR only, preserving test isolation.
Q4 static links split 80/10/10 before graph features or embeddings; validation selects configurations and test labels never do.
Q4 temporal links use chronological train/validation/test targets and forecast-year graphs only; disclose the retrospective node universe and top-six formation target.
Country-region labels are proxies and must never be called industry ground truth.
Default to `--seed 42`, seed every stochastic step and record remaining platform nondeterminism.
Every approach exposes argparse and writes `params`, `metrics`, `fit_seconds` and `history` in question-local metrics files.
Use Rich summaries and standalone Plotly HTML with inline JavaScript.
Root comparisons rank only methods sharing a task, evaluation set and metric definition.
Reports must reflect saved results, including failed indicative benchmarks and modeling limitations.

## Agent, session and Git rules

Use an approved OpenCode-compatible terminal agent for implementation.
For the current repair task only, the user explicitly authorized direct Codex implementation after the OpenCode provider quota was exhausted.
Record that exception honestly; it does not establish instructor acceptance of Codex under the examination rules.
Keep all writes and caches inside this repository and ignore credentials, caches and environments.
Obtain explicit approval before destructive or irreversible operations.
Commit completed milestones separately using conventional prefixes such as `data:`, `feat:`, `exp:` and `report:`.
Preserve authentic historical sessions and export public prompts, responses and tool calls as readable Markdown, redacting credentials.
Never fabricate a missing implementation transcript or relabel Codex work as OpenCode work.
Root `SESSION.md` must include actual public integration and repair transcripts as well as links to per-question evidence.
Exclude private reasoning and automatic approval-review internals from Codex public exports.
Tag `submission` only after the group reviews the final commit.
