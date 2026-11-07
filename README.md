# MQF Advanced Programming: Q1, Q2 and Q4
One repository, with isolated code, data, results and pinned environments under `questions/q1`, `questions/q2` and `questions/q4`.
Requires Python 3.13 and uv; run all approaches and comparisons from this root:
```sh
python3 run.py all --seed 42
```
After installation, use `python3 run.py all --offline --seed 42` for one-command offline reproduction.
Verify snapshots: `python3 data/fetch.py --offline`; test: `python3 run.py all --stage test --offline` and `python3 -m unittest discover -s tests -v`.
Rebuild report tables: `python3 code/build_report.py`; see [report](report.md), [audit](docs/REQUIREMENTS_AUDIT.md), [comparisons](results/comparison.html) and [session evidence](SESSION.md).
The report is a computational draft pending group review; Q1/Q4 historical session gaps and the approved Codex exception are documented.
