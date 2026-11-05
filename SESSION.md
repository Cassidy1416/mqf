# Session Export


## Session metadata

- Project: Q4 China trade network
- Repository: `ap26-q4-trade-network`
- Default seed: `42`
- Remote visibility: private

## Milestones

### 1. Repository contract

- Added `AGENTS.md` with the mathematical objective, environment, commands, reproducibility conventions, and agent rules.
- Commit: `chore: add project agent contract`

### 2. Data pipeline

- Added `pyproject.toml`, `.gitignore`, `README.md`, package markers, and `data/fetch.py`.
- The fetcher uses UN Comtrade preview data, raw-cache reuse, retry fallback, top-partner selection, SHA-256 metadata, and a clean CSV snapshot.
- Commit: `data: add reproducible Comtrade snapshot pipeline`

### 3. Analysis implementation

- Added shared graph utilities, classical network analytics, node2vec/link prediction, comparison tooling, and report scaffolding.
- The first validation run identified that the unfiltered induced graph was nearly complete, which made equal negative sampling impossible.
- Added and documented a fixed top-six-export-per-reporter construction rule, preserving the unfiltered clean snapshot for audit.
- Added Louvain resolution sensitivity and node2vec `p,q` sweeps.

### 4. Data validation

- Retrieved and cached 10 annual periods from 2014 through 2023.
- Final clean snapshot: 21 nodes and 4,160 positive raw edge rows.
- Verified no self-loops in the analysis graphs and reported the one isolated node in 2022 rather than dropping it.
- Committed SHA-256 metadata for the clean artifacts.

### 5. Experiment validation

- Approach 1 completed for all ten years with graph statistics, MST diagnostics, Louvain communities, centrality, resolution sensitivity, and migration metrics.
- Approach 2 completed with dimensions 8/16/32/64, `p,q` values 0.5/1/2, equal negative sampling, AUC/AP metrics, and heuristic baselines.
- Best observed learned AUC: 0.810 at `p=2,q=0.5`, dimension 64; best heuristic AUC: 0.750.
- Generated self-contained Plotly HTML figures and the comparison table.

## Reproduction commands

```bash
uv sync
python data/fetch.py --seed 42
python code/approach1_network_analytics.py --seed 42 --top-k 6
python code/approach2_node_embeddings.py --seed 42 --top-k 6
python code/compare.py
```

## Sensitive information

No credentials, tokens, private keys, or browser authorization data are recorded.
