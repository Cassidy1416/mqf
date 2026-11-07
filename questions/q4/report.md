# Q4 China Financial and Trade Networks

## 1. Executive summary

This project studies an annual directed trade network induced by China’s largest trade partners from 2014–2023. Approach 1 measures network structure, minimum spanning trees, Louvain communities, centrality, and temporal migration. Approach 2 implements node2vec with biased walks, skip-gram negative sampling, a learned bilinear link scorer, and three heuristic baselines. On the fixed 2023 held-out split, the best embedding configuration (`p=2`, `q=0.5`, dimension 64) reaches AUC 0.810 and average precision 0.847, compared with AUC 0.750 for preferential attachment, 0.745 for common neighbors, and 0.705 for Adamic–Adar.

## 2. Data and network construction

The source is the keyless UN Comtrade preview API specified by the assignment. `data/fetch.py` first ranks partners by China’s latest anchor-year imports plus exports, selects 20 partners, and fixes the node set to China plus those partners for every year. It then retrieves reported exports for every induced reporter–partner pair. The committed clean snapshot contains 10 years, 21 country nodes, and 4,160 positive raw edge rows. Raw API responses are cached under the ignored `data/raw/` directory; `data/clean/metadata.json` records the retrieval timestamp, schema, source, and SHA-256 hashes.

For year `t`, the raw directed edge is

\[
T_{ij,t}=\text{primaryValue}_{ij,t},
\]

measured in USD. Because all selected countries report some small positive bilateral flows, the unfiltered induced graph is nearly complete and cannot support equal negative sampling. The analysis graph therefore keeps the six largest export edges per reporter per year. This rule is fixed before evaluation, is applied identically across years, and leaves the unfiltered clean snapshot available for audit. Self-loops are excluded by construction and checked in every run.

The assignment’s stock-industry labels are not defined for country nodes. We therefore use geographical region as a clearly labelled proxy only for community comparison; the primary Q4-B task is held-out trade-edge recovery rather than industry prediction.

## 3. Reproducibility

The environment is Python 3.13 with dependencies pinned in `pyproject.toml` and `uv.lock`. The global default seed is 42. The canonical commands are:

```bash
uv sync
python data/fetch.py --seed 42
python code/approach1_network_analytics.py --seed 42 --top-k 6
python code/approach2_node_embeddings.py --seed 42 --top-k 6
python code/compare.py
```

Each approach uses the required CLI, writes `results/approachN/trade/metrics.json` with `params`, `metrics`, `fit_seconds`, and `history`, and writes self-contained Plotly HTML figures.

## 4. Approach 1: network analytics

The directed graph is converted to an undirected weighted graph by summing reciprocal export weights. The metric used for the Kruskal minimum spanning tree is

\[
d_{ij}=\frac{1}{\log(1+w_{ij})},
\]

so larger trade relationships have shorter distances. We report node count, edge count, density, mean degree, a log–log degree-frequency slope, assortativity, connected components, isolated nodes, and self-loops. Louvain maximizes the weighted modularity

\[
Q=\frac{1}{2m}\sum_{ij}\left(A_{ij}-\frac{k_i k_j}{2m}\right)\mathbf{1}(c_i=c_j).
\]

PageRank uses damping 0.85. Betweenness uses shortest paths, and weighted degree sums trade values. Resolution sensitivity is evaluated at 0.5, 1.0, and 1.5. Consecutive-year migration is reported as an aligned contingency matrix and ARI.

### 4.1 Graph statistics

| Year | Nodes | Undirected edges | Density | Communities | Modularity | MST diameter | Assortativity |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2014 | 21 | 96 | 0.300 | 5 | 0.261 | 6 | -0.342 |
| 2015 | 21 | 97 | 0.300 | 4 | 0.241 | 6 | -0.344 |
| 2016 | 21 | 94 | 0.300 | 4 | 0.243 | 5 | -0.315 |
| 2017 | 21 | 96 | 0.300 | 4 | 0.241 | 6 | -0.325 |
| 2018 | 21 | 94 | 0.300 | 4 | 0.236 | 7 | -0.344 |
| 2019 | 21 | 94 | 0.300 | 4 | 0.238 | 7 | -0.298 |
| 2020 | 21 | 97 | 0.300 | 4 | 0.214 | 6 | -0.276 |
| 2021 | 21 | 95 | 0.300 | 4 | 0.217 | 6 | -0.283 |
| 2022 | 21 | 91 | 0.286 | 4 | 0.225 | disconnected | -0.292 |
| 2023 | 21 | 91 | 0.286 | 4 | 0.230 | 6 | -0.277 |

There are no self-loops. One isolated node is reported in 2022; it is not silently removed. The 2023 top PageRank nodes are the United States, China, Mexico, Germany, and Japan. The 2023 resolution sweep produces 1, 4, and 6 communities at resolutions 0.5, 1.0, and 1.5 respectively.

![Network evolution](results/approach1/trade/network_evolution.html)

## 5. Approach 2: node2vec and link prediction

For a walk with previous node `t`, current node `v`, and candidate next node `x`, the node2vec transition bias is

\[
\alpha_{pq}(t,x)=
\begin{cases}
1/p & x=t,\\
1 & (t,x)\in E,\\
1/q & \text{otherwise},
\end{cases}
\]

multiplied by the observed edge weight before normalization. Walk contexts use a window of two. The skip-gram objective uses positive context pairs and five uniformly sampled negative contexts:

\[
\log\sigma(z_v^\top c_u)+\sum_{r=1}^{5}\log\sigma(-z_v^\top c_{n_r}).
\]

The final-year graph is split into 80/10/10 positive edges and an equal number of negative non-edges: 72/9/10 in train/validation/test. The learned link score is

\[
s(u,v)=\sigma(z_u^\top Wz_v),
\]

where `W` is fitted only on the training split. Baselines are common neighbors, Adamic–Adar, and preferential attachment. We report AUC, average precision, and k-means agreement with Louvain and the region proxy using ARI/NMI.

### 5.1 Dimension comparison at `p=1,q=1`

| Dimension | Learned AUC | Learned AP | Common-neighbor AUC | Adamic–Adar AUC | Preferential-attachment AUC |
|---:|---:|---:|---:|---:|---:|
| 8 | 0.680 | 0.648 | 0.745 | 0.705 | 0.750 |
| 16 | 0.710 | 0.755 | 0.745 | 0.705 | 0.750 |
| 32 | 0.720 | 0.754 | 0.745 | 0.705 | 0.750 |
| 64 | 0.740 | 0.798 | 0.745 | 0.705 | 0.750 |

### 5.2 `p,q` sensitivity

| Configuration | Best dimension | Best AUC |
|---|---:|---:|
| p=0.5, q=0.5 | 8 | 0.790 |
| p=0.5, q=1 | 64 | 0.620 |
| p=0.5, q=2 | 8 | 0.660 |
| p=1, q=0.5 | 8 | 0.700 |
| p=1, q=1 | 64 | 0.740 |
| p=1, q=2 | 8 | 0.680 |
| p=2, q=0.5 | 64 | **0.810** |
| p=2, q=1 | 8 | 0.740 |
| p=2, q=2 | 8 | 0.700 |

At the best configuration, average precision is 0.847. Embedding clusters have ARI 0.069 and NMI 0.249 against Louvain, and ARI 0.016 and NMI 0.293 against the region proxy. Thus the embedding is more useful for edge recovery than for reproducing the classical community partition.

![Link prediction](results/approach2/trade/link_prediction.html)

## 6. Limitations and checks

The preview API provides reported values and does not guarantee a complete reconciled world trade matrix. The fixed 21-node induced network is intentionally manageable and is not a full global network. The top-k rule improves link-prediction identifiability but changes the interpretation from all reported flows to major relationships. Country regions are not industry labels, so region agreement is explicitly a proxy rather than evidence of industry alignment. The test set is small; AUC and AP are reported together and should not be overinterpreted. Future work would use a larger country universe, multiple HS levels, repeated temporal test windows, and bootstrap uncertainty intervals.

## 7. Division of work

The terminal workflow implemented the data retrieval, checksum metadata, graph construction, estimators, benchmarks, figures, and reproducibility scaffolding. The group is responsible for reviewing mathematical definitions, checking the generated results, approving the top-k and proxy-label assumptions, and making the final claims.
