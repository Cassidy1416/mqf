This repository integrates the Advanced Programming experiments for Q1, Q2 and Q4 as self-contained question folders.
Run everything from the root with `python3 run.py {q1,q2,q4,all} [--stage {verify,approach1,approach2,compare,all,index}] [--seed 42] [--offline] [--dry-run]`.
Useful commands are `python3 run.py all --stage verify`, `python3 run.py q2 --offline` and `python3 run.py all --offline`.
Verification of committed snapshots needs only the standard library, while experiment stages need `uv` and the per-question locked environments.
`--offline` requires each question's dependencies to be installed already; omitting it allows dependency installation but never vendor-data refresh.
Each question keeps its own pinned `pyproject.toml` and `uv.lock` in its directory and runs with that lock.
See `docs/INTEGRATION.md` for the directory layout, data provenance and session-export status.
