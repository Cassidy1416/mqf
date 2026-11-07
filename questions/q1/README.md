# Q1: MQF Advanced Programming
Classical SVI and differentiable implied-volatility surfaces on CSI 300 options.
From the combined repository root, run the isolated pinned environment:
```sh
python3 run.py q1 --seed 42
```
After dependency installation, add `--offline`; snapshots always use verified committed data unless an explicit online refresh is requested.
From this question directory, the equivalent launcher is `python3 ../../run.py q1 --offline --seed 42`.
Use root stages `--stage verify`, `--stage test`, `--stage approach1`, `--stage approach2`, or `--stage compare`.
See [report](report.md), [session evidence](SESSION.md) and [root reproduction contract](../../AGENTS.md).
