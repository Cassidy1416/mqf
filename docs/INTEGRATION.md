# Combined repository integration

Q1, Q2 and Q4 are clearly separated under `questions/qN/`, with independent scientific code, snapshots, results, reports, session evidence, dependency manifests and lockfiles.
The root provides stdlib orchestration, a unified snapshot manifest, comparable-task aggregation and the combined computational report.
The original imported commit SHAs are recorded in `sources.json` and remain ancestors of this repository.
The later Q1 compliance revision supplies the expanded quote snapshot and selected reference code; prior snapshots remain archived byte-for-byte.

## Reproduction

From the root, run `python3 run.py all --seed 42` to verify data, install pinned environments as needed, execute all approaches including future Q4 links and rebuild comparisons.
Use `--offline` after dependencies have been installed, `--stage verify` for verification only and `--stage test` for native regression tests.
Run `python3 -m unittest discover -s tests -v` for the shared manifest and comparison checks.
Run `python3 code/build_report.py` after all metrics are final to regenerate the combined and per-question computational report tables.
Each child runs in its own working directory and uv environment, keeping module names and conflicting dependency versions isolated.
Root `data/fetch.py --offline` verifies hashes, schemas, counts, unique keys and coverage without scientific dependencies.
An explicit online request stages vendor outputs in ignored paths and verifies the committed fallback; snapshots are not silently replaced.

## Correctness and methodological changes

The integration initially preserved scientific inputs and outputs.
During the subsequent authorized repair task, Q1 monthly chain coverage and SHIBOR curves were expanded, Q1 comparable evaluation and diagnostics corrected, Q2 Monte Carlo uncertainty and training repaired, and Q4 leakage, graph statistics and temporal prediction corrected.
The old preserved-output claim therefore applies to the initial integration commit, not the present repaired experiments.
See [the full requirements audit](REQUIREMENTS_AUDIT.md) for all repaired items and residual limitations.
Root comparisons rank within shared tasks and datasets, never across unrelated questions.
All saved figures include their Plotly JavaScript, and numeric report tables are generated from actual saved metrics.

## Evidence and submission status

Original question Git histories and original session documents are preserved.
The Q1/Q4 `SESSION.original.md` files are milestone summaries; genuine later OpenCode verification exports do not recreate their original implementation conversations.
Q2's previously omitted public Codex completion traces were recovered from local session records and are linked from its session document.
The user explicitly approved direct Codex completion after the OpenCode provider quota failed; the actual public repair trace records this exception.
A user exception does not establish instructor acceptance under the examination's approved-agent requirement.
Root and per-question session documents identify provenance and gaps without relabeling Codex as OpenCode.
The report is a computational draft for the group to verify and approve.
The final `submission` tag remains reserved for the reviewed submission commit.
