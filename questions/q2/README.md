# Q2: MQF Advanced Programming
Monte Carlo variance reduction, Greeks and transaction-cost hedges on IF0 and CU0.
From the combined repository root, run the isolated pinned environment:
```sh
python3 run.py q2 --seed 42
```
After dependency installation, add `--offline`; snapshots always use verified committed data unless an explicit online refresh is requested.
From this question directory, the equivalent launcher is `python3 ../../run.py q2 --offline --seed 42`.
Use root stages `--stage verify`, `--stage test`, `--stage approach1`, `--stage approach2`, or `--stage compare`.
See [report](report.md), [session evidence](SESSION.md) and [root reproduction contract](../../AGENTS.md).
