# Q4. Chinese trade network analytics and prediction

## Data, graph definition and verification

The committed UN Comtrade preview snapshot covers ten annual periods, 2014 through 2023, for 21 nodes selected from China's 2023 major trading partners.
Queries use annual merchandise exports, HS TOTAL, partner-level USD values, and the fixed reporter/partner set documented in the [manifest](data/clean/metadata.json).
Snapshot verification checks actual hashes, schema, year coverage, unique reporter/partner/year keys and positive finite flow values.
This public preview sample is neither a complete global trade network nor an industry-level dataset.
The 2023-selected country universe is retrospective, even when experiments use earlier graph years.
Country-region labels are geographical proxies, with some original unclassified partner codes retained as Other; they are not industry ground truth.
This is an explicit deviation from the assignment's industry-label comparison and requires group or instructor acceptance for a country-level trade network.

For each year, $T_{ij}$ is reported exports from $i$ to $j$ and only each reporter's six largest positive exports within the sampled universe are retained.
The weighted directed graph has one edge for each retained $T_{ij}>0$, excludes self-loops and retains isolated nodes.
For undirected analysis, $W_{ij}=T_{ij}1_{retained(i,j)}+T_{ji}1_{retained(j,i)}$; verification checks the exact edge union and reciprocal-weight sum.
Distances are $d_{ij}=1/\log(1+W_{ij})$ on existing edges, so larger trade means shorter distance.
This monotone edge dissimilarity need not satisfy the triangle inequality; the Kruskal tree is a minimum spanning tree of the observed connected graph, not a proven Euclidean metric network.
Directed and undirected densities use their respective edge counts and denominators $n(n-1)$ and $n(n-1)/2$.
The descriptive log-log slope regresses log positive degree-frequency counts on log positive degree support without dropping the first bin; 21 nodes do not support a power-law inference.
All annual graphs have zero self-loops, and isolates and connected components are reported explicitly.

## Classical annual statistics and communities

| Year | V | Directed E | Undirected E | Directed density | Undirected density | Degree slope | Assortativity | Components | Isolates | MST diameter | Louvain Q |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014 | 21 | 126 | 96 | 0.3 | 0.45714 | -1.7149 | -0.34156 | 1 | 0 | 6 | 0.26069 |
| 2015 | 21 | 126 | 97 | 0.3 | 0.4619 | -1.2669 | -0.34408 | 1 | 0 | 6 | 0.24073 |
| 2016 | 21 | 126 | 94 | 0.3 | 0.44762 | -1.1667 | -0.3148 | 1 | 0 | 5 | 0.24311 |
| 2017 | 21 | 126 | 96 | 0.3 | 0.45714 | -1.3053 | -0.32467 | 1 | 0 | 6 | 0.2411 |
| 2018 | 21 | 126 | 94 | 0.3 | 0.44762 | -1.1207 | -0.34372 | 1 | 0 | 7 | 0.23608 |
| 2019 | 21 | 126 | 94 | 0.3 | 0.44762 | -0.9937 | -0.29845 | 1 | 0 | 7 | 0.23771 |
| 2020 | 21 | 126 | 97 | 0.3 | 0.4619 | -1.194 | -0.27591 | 1 | 0 | 6 | 0.21412 |
| 2021 | 21 | 126 | 95 | 0.3 | 0.45238 | -1.178 | -0.28322 | 1 | 0 | 6 | 0.2171 |
| 2022 | 21 | 120 | 91 | 0.28571 | 0.43333 | -1.2505 | -0.29159 | 2 | 1 | not reached | 0.22464 |
| 2023 | 21 | 120 | 91 | 0.28571 | 0.43333 | 0.12378 | -0.27686 | 1 | 0 | 6 | 0.23037 |

Louvain optimizes weighted modularity $Q=(2m)^{-1}\sum_{ij}[W_{ij}-\gamma k_i k_j/(2m)]1_{c_i=c_j}$, where $k_i$ is weighted degree and $m=\frac12\sum_{ij}W_{ij}$.
The primary resolution is one, with seeded sweeps at 0.5, 1 and 1.5.
PageRank uses directed trade weights, damping 0.85 and uniform teleportation: $p=0.85P^\top p+0.15\mathbf1/n$.
Weighted directed betweenness uses the same decreasing-trade distance convention; undirected weighted degree is the sum of reciprocal retained flows.
The United States and China are the top two PageRank nodes in 2014 and 2023, reflecting centrality within this selected network rather than a claim about the full world economy.

### 2023 resolution sensitivity

| Resolution | Communities | Modularity | ARI vs region proxy | NMI vs region proxy |
| --- | --- | --- | --- | --- |
| 0.5 | 1 | 1.1102e-16 | 0 | 0 |
| 1.0 | 4 | 0.23037 | 0.33216 | 0.61921 |
| 1.5 | 6 | 0.19784 | 0.43537 | 0.72553 |

### Ranked 2023 centralities

| Metric | Rank | Country / original code label | Value |
| --- | --- | --- | --- |
| pagerank | 1 | United States | 0.24271 |
| pagerank | 2 | China | 0.16715 |
| pagerank | 3 | Mexico | 0.093311 |
| pagerank | 4 | Germany | 0.062466 |
| pagerank | 5 | Japan | 0.059166 |
| pagerank | 6 | Hong Kong | 0.055555 |
| pagerank | 7 | Netherlands | 0.053232 |
| pagerank | 8 | United Kingdom | 0.044924 |
| pagerank | 9 | South Korea | 0.038359 |
| pagerank | 10 | Partner 699 | 0.032249 |
| pagerank | 11 | Vietnam | 0.029168 |
| pagerank | 12 | Partner 490 | 0.018811 |
| pagerank | 13 | Partner 784 | 0.018644 |
| pagerank | 14 | Singapore | 0.015204 |
| pagerank | 15 | Saudi Arabia | 0.01233 |
| pagerank | 16 | Thailand | 0.011656 |
| pagerank | 17 | Malaysia | 0.011153 |
| pagerank | 18 | Indonesia | 0.009224 |
| pagerank | 19 | Australia | 0.0083238 |
| pagerank | 20 | Russia | 0.0082155 |
| pagerank | 21 | Brazil | 0.0081519 |
| betweenness | 1 | United States | 0.21842 |
| betweenness | 2 | China | 0.21316 |
| betweenness | 3 | Partner 699 | 0.11842 |
| betweenness | 4 | Japan | 0.11053 |
| betweenness | 5 | Partner 784 | 0.097368 |
| betweenness | 6 | Singapore | 0.078947 |
| betweenness | 7 | Thailand | 0.057895 |
| betweenness | 8 | Hong Kong | 0.052632 |
| betweenness | 9 | Mexico | 0.047368 |
| betweenness | 10 | Partner 490 | 0.044737 |
| betweenness | 11 | Malaysia | 0.010526 |
| betweenness | 12 | Germany | 0.0078947 |
| betweenness | 13 | Netherlands | 0.0052632 |
| betweenness | 14 | South Korea | 0.0026316 |
| betweenness | 15 | Australia | 0 |
| betweenness | 16 | Brazil | 0 |
| betweenness | 17 | Indonesia | 0 |
| betweenness | 18 | Russia | 0 |
| betweenness | 19 | Saudi Arabia | 0 |
| betweenness | 20 | Vietnam | 0 |
| betweenness | 21 | United Kingdom | 0 |
| weighted_degree | 1 | China | 2.8556e+12 |
| weighted_degree | 2 | United States | 2.7987e+12 |
| weighted_degree | 3 | Hong Kong | 9.3326e+11 |
| weighted_degree | 4 | Japan | 8.7282e+11 |
| weighted_degree | 5 | Mexico | 8.3818e+11 |
| weighted_degree | 6 | Germany | 8.1605e+11 |
| weighted_degree | 7 | South Korea | 6.8138e+11 |
| weighted_degree | 8 | Netherlands | 5.669e+11 |
| weighted_degree | 9 | Vietnam | 4.4097e+11 |
| weighted_degree | 10 | United Kingdom | 4.2905e+11 |
| weighted_degree | 11 | Partner 490 | 4.1245e+11 |
| weighted_degree | 12 | Partner 699 | 3.9265e+11 |
| weighted_degree | 13 | Singapore | 3.7383e+11 |
| weighted_degree | 14 | Malaysia | 2.4628e+11 |
| weighted_degree | 15 | Australia | 2.2825e+11 |
| weighted_degree | 16 | Indonesia | 1.9021e+11 |
| weighted_degree | 17 | Thailand | 1.8484e+11 |
| weighted_degree | 18 | Brazil | 1.8089e+11 |
| weighted_degree | 19 | Partner 784 | 1.5853e+11 |
| weighted_degree | 20 | Saudi Arabia | 6.3507e+10 |
| weighted_degree | 21 | Russia | 4.4924e+09 |

Full country-named rankings and degree distributions for every year are retained in [classical metrics](results/approach1/trade/metrics.json).
Consecutive community matrices retain their original row and column labels; Hungarian one-to-one matching removes arbitrary label permutations while preserving real splits and merges.
Changed share counts nodes that remain unmatched after this matching, and ARI is independently label-invariant.

| Transition | Changed share | ARI | Split previous labels | Merged current labels | Raw contingency matrix |
| --- | --- | --- | --- | --- | --- |
| 2014->2015 | 0.19048 | 0.6979 | [3] | [0, 3] | [[6, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [1, 0, 0, 3], [0, 0, 0, 4]] |
| 2015->2016 | 0 | 1 | [] | [] | [[7, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [0, 0, 0, 7]] |
| 2016->2017 | 0.047619 | 0.83278 | [3] | [0] | [[7, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [1, 0, 0, 6]] |
| 2017->2018 | 0 | 1 | [] | [] | [[8, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [0, 0, 0, 6]] |
| 2018->2019 | 0 | 1 | [] | [] | [[8, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [0, 0, 0, 6]] |
| 2019->2020 | 0.047619 | 0.87696 | [1] | [0] | [[8, 0, 0, 0], [1, 0, 0, 2], [0, 4, 0, 0], [0, 0, 6, 0]] |
| 2020->2021 | 0 | 1 | [] | [] | [[9, 0, 0, 0], [0, 4, 0, 0], [0, 0, 6, 0], [0, 0, 0, 2]] |
| 2021->2022 | 0.14286 | 0.8945 | [1] | [1] | [[9, 0, 0, 0], [0, 3, 0, 1], [0, 0, 6, 0], [0, 2, 0, 0]] |
| 2022->2023 | 0.14286 | 0.85722 | [2] | [3] | [[9, 0, 0, 0], [0, 5, 0, 0], [0, 0, 3, 3], [0, 0, 0, 1]] |

The largest observed migration is 2014 to 2015; changes also occur in 2021 to 2022 and 2022 to 2023.
These are structural changes in detected sample communities, not identified causal breaks in trade policy.
In 2022 to 2023 the raw matrix preserves one previous community splitting into two and a corresponding merge, instead of collapsing both into a matched label.

## Embeddings and corrected static edge benchmark

The weighted node2vec walk moves from previous node $t$ through current node $v$ to neighbor $x$ with weight $W_{vx}\alpha_{pq}(t,x)$, where $\alpha=1/p$ for returning to $t$, one for neighbors of $t$, and $1/q$ otherwise.
Skip-gram maximizes $\log\sigma(z_v^\top c_u)+\sum_{j=1}^5\log\sigma(-z_v^\top c_{n_j})$ using its own PyTorch implementation and uniform node negative sampling.
The bilinear link classifier is $s(u,v)=\sigma(z_u^\top Bz_v)$; binary cross entropy trains $B$ using training labels only.
The static 2023 graph has 91 undirected positive edges, split into 72 training, nine validation and ten test positives, with equal disjoint negative sampling in each split.
The split occurs before walks, embeddings, Louvain or baseline graph features are computed.
All validation and test positive edges are absent from the 72-edge training graph; exact pairs and graph fingerprints are saved.
We sweep $p,q\in\{0.5,1,2\}$ and dimensions $\{8,16,32,64\}$, selecting by validation AUC, then validation AP and deterministic parameter tie-breaks.
The final test labels are scored once for the selected model and are never used to select a dimension or walk parameters.
Common-neighbor, Adamic-Adar and preferential-attachment scores are all computed on that same training graph.

Selected static parameters: p=1.0, q=0.5, dimension=8.
The historical full-graph/test-selected AUC is superseded by the corrected scores below.

| Static test method | AUC | Average precision |
| --- | --- | --- |
| learned | 0.57 | 0.5887 |
| common_neighbors | 0.69 | 0.68958 |
| adamic_adar | 0.715 | 0.71707 |
| preferential_attachment | 0.68 | 0.72027 |

### Complete clustering agreement matrix (unique pairs)

| Label pair | ARI | NMI |
| --- | --- | --- |
| embedding_kmeans/region_geographical_proxy | 0.22784 | 0.53792 |
| embedding_kmeans/training_graph_louvain | 0.58293 | 0.68041 |
| region_geographical_proxy/training_graph_louvain | 0.26908 | 0.56209 |

## Future major-trade-link formation

The additional temporal task predicts $Y_{ij,t+1}=1$ when an undirected relation absent from the year-$t$ top-six graph appears in year $t+1$.
This is formation of a major retained trade relation, not the first occurrence of any positive raw bilateral trade and not a continuous dollar-flow forecast.
Train transitions are 2014 to 2015 through 2020 to 2021; validation is 2021 to 2022; the final test is 2022 to 2023.
The static 80/10/10 split remains a separate benchmark; the temporal task uses chronological splits to preserve forecasting order.
Each transition embeds only its forecast-year graph, with equal sampled negatives among absent relations that stay absent in the target year.
Embedding orientations are aligned by orthogonal Procrustes against the first training-year embedding using node identities, without future labels.
A shared bilinear matrix is trained on training transitions only; walk parameters and dimension are selected on validation only.
The fixed node universe is selected retrospectively from 2023, so the result is conditional on these countries rather than a fully prospective population forecast.

| Transition | Train positive | Train negative |
| --- | --- | --- |
| 2014 to 2015 | 6 | 6 |
| 2015 to 2016 | 6 | 6 |
| 2016 to 2017 | 7 | 7 |
| 2017 to 2018 | 1 | 1 |
| 2018 to 2019 | 6 | 6 |
| 2019 to 2020 | 7 | 7 |
| 2020 to 2021 | 6 | 6 |

Validation has 6 positive and 6 negative examples.
The final test has only 2 positive and 2 sampled negative examples, from 117 available nonformations.
This tiny holdout gives a very coarse and unstable AUC, so it cannot establish forecasting skill.
Selected temporal parameters are p=0.5, q=0.5, dimension=8, with validation AUC 0.69444.

| Future test method | AUC | Average precision |
| --- | --- | --- |
| learned | 0 | 0.41667 |
| common_neighbors | 0.375 | 0.5 |
| adamic_adar | 0.5 | 0.75 |
| preferential_attachment | 0.5 | 0.75 |

Both learned tasks miss the indicative AUC target of 0.75.
The static Adamic-Adar baseline exceeds the indicative 0.65 heuristic target, but the temporal benchmark does not.
Poor final test performance is retained honestly and is not used to retune the experiment.
Average precision is measured on balanced case-control samples, so it does not estimate precision at the population's actual formation prevalence.
The region-proxy comparison does not fulfill a literal industry-ground-truth requirement.
Seed 42 governs splits, walks, negative sampling, optimization and clustering; CPU arithmetic can vary slightly by platform.
Figures: [annual network evolution](results/approach1/trade/network_evolution.html), [static prediction](results/approach2/trade/link_prediction.html), [future prediction](results/approach2/trade_future/future_links.html) and [separate task comparisons](results/comparison.html).

## Statement of work: group direction and agent contribution

### Q4 work division

**Group direction and decisions.**
The group authorized future trade-link prediction alongside a separate static missing-edge benchmark and directed that country regions remain explicitly identified as geographical proxies for industry labels.
The group is responsible for assessing the top-six major-link target, the retrospective country universe and the geographical proxy interpretation, and for drawing appropriately limited conclusions from the small temporal holdout.

**Coding-agent implementation and verification.**
The coding agent corrected graph statistics and community migration, removed held-out edges before static graph features and embeddings, implemented validation-only model selection and chronological future-link prediction, and generated baseline comparisons, agreement matrices, figures and regression checks.

### Report preparation and review

The coding agent assembled the computational results and drafted the mathematical descriptions, tables and discussion from the saved experiment outputs.
The group retains responsibility for the mathematical specification, verification, interpretation and final report approval.
Final group verification and approval remain pending.

### Agent provenance and session evidence

OpenCode reached its provider quota; the user explicitly approved finishing these repairs in Codex, overriding the local agent requirement for this task.
This permission does not change the examination's approved-agent rule; instructor acceptance of the Codex-authored repairs remains unresolved.
Original Q1/Q4 summaries, genuine later OpenCode verification exports, recovered Q2 public implementation sessions and the public repair transcript are identified in [SESSION.md](SESSION.md).
Unavailable original Q1/Q4 implementation exports cannot be recreated by formatting a later summary as OpenCode.
The final `submission` tag is intentionally reserved for the group's final reviewed commit.
