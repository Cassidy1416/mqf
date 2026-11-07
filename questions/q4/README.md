# Q4: MQF Advanced Programming
Trade-network analytics, corrected static edge recovery and chronological future major-link prediction.
From the combined repository root, run the isolated pinned environment:
```sh
python3 run.py q4 --seed 42
```
After dependency installation, add `--offline`; snapshots always use verified committed data unless an explicit online refresh is requested.
From this question directory, the equivalent launcher is `python3 ../../run.py q4 --offline --seed 42`.
Use root stages `--stage verify`, `--stage test`, `--stage approach1`, `--stage approach2`, or `--stage compare`; Q4 also has `--stage future`.
See [report](report.md), [session evidence](SESSION.md) and [root reproduction contract](../../AGENTS.md).
