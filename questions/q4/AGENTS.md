# Q4 agent contract

## Goal and ownership

Follow the combined [project contract](../../AGENTS.md) and this question's [mathematical protocol](report.md).
Implement and verify both approaches for Q4 with the documented data, metrics, seeds and limitations.
The group directs methodology and must review the final report and results.
The user's current repair-task exception permits direct Codex implementation after OpenCode exhausted its quota; preserve actual agent provenance in session evidence.

## Environment and exact commands

Use Python 3.13 with this folder's pinned `pyproject.toml` and `uv.lock`.
From the combined repository root run:

```sh
python3 run.py q4 --seed 42
python3 run.py q4 --stage test --offline
```

After installation, add `--offline` to the full run for network-free reproduction.
From this folder the equivalent command is `python3 ../../run.py q4 --offline --seed 42`.
The launcher isolates the working directory, uv environment and in-repository caches.

## Conventions and session rules

Use seed 42 by default and record split, initialization and training seeds.
Verify immutable snapshots against the manifest before experiments; retain original data archives and provenance.
Expose argparse CLIs, Rich summaries and standalone Plotly HTML.
Write question-local metrics with `params`, `metrics`, `fit_seconds` and `history`.
Use held-out evaluation and validation-only model selection; preserve all failure and exclusion diagnostics.
Keep all writes and caches in the repository, never commit credentials and obtain approval before destructive operations.
Make conventional milestone commits and keep authentic readable session evidence.
Do not rewrite historical summaries into invented implementation transcripts.
Reserve the `submission` tag for final group review.
