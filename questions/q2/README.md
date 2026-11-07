# MQF Advanced Programming
Q2 prices options on IF0 and CU0 with NumPy and PyTorch and compares transaction-cost hedges.
From the repo root, run the following command with Python 3.13 and uv.
```sh
export UV_CACHE_DIR="$PWD/.cache/uv"; uv sync --locked --python 3.13 && uv run --locked python data/fetch.py --question q2 --offline && uv run --locked python code/approach1_q2.py --seed 42 && uv run --locked python code/approach2_q2.py --seed 42 && uv run --locked python code/compare.py
```
The runs use committed snapshots and write metrics and standalone HTML to `results/`.
After installing dependencies, add `--offline` to each uv command to reproduce without network access.
