# China Trade Network
Builds annual China-partner trade graphs from the public UN Comtrade API.
Approach 1 evaluates MST, Louvain communities, centrality, and temporal migration.
Approach 2 implements node2vec, link prediction, and heuristic baselines in PyTorch.
Requires Python 3.13/3.14 and `uv`; all stochastic runs default to seed 42.
Run: `uv sync && python data/fetch.py --seed 42 && python code/approach1_network_analytics.py --seed 42 && python code/approach2_node_embeddings.py --seed 42 && python code/compare.py`.
