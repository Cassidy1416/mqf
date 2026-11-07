# Combined report: Q1, Q2 and Q4

This document concatenates the three original question reports as text for group review.
The imported scientific claims were not rewritten, reassigned, or revalidated, so this merged file is a convenience copy rather than a rewrite.
The only integration change inside each text is that relative link targets are prefixed with `questions/qN/` so figures and data links resolve from the repository root, and Markdown image embeds that point to `.html` figures became normal links because HTML cannot be embedded as an image.

# Q1 Implied Volatility Surface of China Index Options

## 1. Executive summary

This project estimates China CSI 300 option implied-volatility surfaces using public CFFEX historical contract data.
Approach 1 performs quote filtering, Black–Scholes inversion, put–call parity diagnostics, constrained SVI calibration, repricing, and no-arbitrage checks.
Approach 2 compares differentiable PyTorch SVI calibration with SciPy and trains a price-space neural surface with butterfly/calendar penalties.
The liquid quote pipeline retains 225 quotes, successfully inverts 224, fits 12 SVI groups, obtains zero butterfly-grid violations, and has 1.67% median liquid-strike repricing error.
Under a 30% quote-drop experiment, SVI obtains 0.067% median relative price error on held-out quotes and the neural surface obtains 0.204%.

## 2. Data and provenance

The data pipeline uses the assignment-approved `akshare` interfaces: `option_cffex_hs300_spot_sina` and `option_cffex_hs300_daily_sina` for contract strikes and daily OHLCV, `stock_zh_index_daily(symbol="sh000300")` for the CSI 300 index, and `macro_china_shibor_all` for the historical 3M SHIBOR rate.
The snapshot contains nine expiry months, 1,134 raw call/put quote rows, 177 observed dates, and a date range from 2023-03-20 to 2026-01-13.
A shared October 2023 block contains four expiries on five dates, enabling calendar diagnostics.

For every selected contract, the fetcher keeps the first five trading dates within a 31-calendar-day window and 13 evenly spaced strikes.
It also keeps a common 2023-10-23 through 2023-10-27 block for four overlapping expiries when the contract traded on those dates.
Raw responses are cached in ignored `data/raw/`; clean snapshots and SHA-256 hashes are committed in `data/clean/metadata.json`.

The formal liquid-quote rule is volume at least 40 and forward moneyness `0.9 <= K/F <= 1.1`.
The rule is declared before calibration and is exposed through CLI parameters.
The underlying dividend yield is set to zero because the primary instrument is the CSI 300 index option rather than an ETF; this assumption is a limitation and is not hidden.

## 3. Market definitions

For quote date `t`, spot `S`, continuously compounded rate `r`, time to expiry `T`, and zero dividend yield, the forward is

\[
F=S e^{rT}, \qquad D=e^{-rT}.
\]

For volatility `sigma`,

\[
d_1=\frac{\log(F/K)+\frac12\sigma^2T}{\sigma\sqrt{T}},
\qquad d_2=d_1-\sigma\sqrt{T}.
\]

The Black–Scholes forward prices are

\[
C=D(FN(d_1)-KN(d_2)),
\qquad P=D(KN(-d_2)-FN(-d_1)).
\]

Implied volatility is obtained separately for every call and put using bracketed Brent root finding on `[10^-4, 5]`.
Five of 225 filtered quotes fail the admissible price bracket and are reported as divergence cases rather than silently removed.

Put–call parity is evaluated as

\[
\epsilon_{PC}=C-P-(S-Ke^{-rT}).
\]

There are 166 matched strike groups after filtering.
The mean residual is 0.0165 index points, RMSE is 14.4405, and the 95th percentile absolute residual is 19.0721.
The large dispersion is retained as a data-quality finding because daily closes are not executable bid/ask mids.

## 4. Approach 1: classical market pipeline

For each date/expiry group, total variance is `w(k)=sigma_IV^2 T` and log-moneyness is `k=log(K/F)`.
SVI is

\[
w(k)=a+b\left[\rho(k-m)+\sqrt{(k-m)^2+\eta^2}\right],
\]

with `b >= 0`, `|rho| < 1`, and `eta > 0`.
The implementation first obtains a bounded least-squares initialization and then uses SLSQP with inequality constraints `g(k)>=0` on an 81-point interior grid.
The objective remains squared total-variance error; constraint failure is reported.

The Gatheral butterfly diagnostic is

\[
g(k)=\left(1-\frac{kw'(k)}{2w(k)}\right)^2-
\frac{w'(k)^2}{4}\left(\frac1{w(k)}+\frac14\right).
\]

Calendar checks compare fitted total variance at the same `k` for increasing expiries.
Forward variance is the finite difference of total variance divided by the maturity difference.
The surface is delivered on an 81-point fixed grid in `results/approach1/market/surface_grid.csv`.

### 4.1 Results

| Quantity | Result |
|---|---:|
| Filtered quotes | 225 |
| Successful IV quotes | 224 |
| SVI groups | 12 |
| IV divergence cases | 1 |
| Butterfly violations | 0 |
| Calendar violations | 20 |
| Negative forward-variance locations | 20 |
| Median repricing relative error | 1.67% |
| 95th percentile of group p95 repricing | 39.21% |

Calendar and forward-variance violations occur on 2023-10-23 and 2023-10-24; they are counted and located in `metrics.json`.
No violations are silently dropped.
The high group-level p95 is consistent with sparse daily close data and is discussed as a limitation.

[SVI surface](questions/q1/results/approach1/market/svi_surface.html)

[Arbitrage diagnostics](questions/q1/results/approach1/market/arbitrage_diagnostics.html)

## 5. Approach 2: differentiable calibration

### 5.1 Differentiable SVI

The PyTorch SVI implementation uses reparameterization:

\[
a=\operatorname{softplus}(u_a),\quad b=\operatorname{softplus}(u_b),\quad
\rho=0.999\tanh(u_\rho),\quad \eta=\operatorname{softplus}(u_\eta).
\]

Adam runs for 300 epochs on each of the 12 groups.
The mean SciPy objective is `1.97e-08`, while the mean Torch objective is `1.97e-08`; mean wall time is 0.0087 seconds for SciPy and 0.0374 seconds for Torch on this small dataset.
This comparison separates optimizer overhead from statistical fit quality.

### 5.2 Neural surface

The neural surface is an MLP with two hidden tanh layers and a positive softplus volatility output.
Inputs are `(k,T)`.
The loss is normalized option-price squared error plus arbitrage penalties:

\[
\mathcal L=\operatorname{MSE}\left(\frac{\hat C-C_{mkt}}{F}\right)
 +\lambda_b\operatorname{mean}[\max(0,-g(k))^2]
 +\lambda_T\operatorname{mean}[\max(0,-\partial_Tw)^2].
\]

The ablation grid is `(lambda_b,lambda_T)` in `{(0,0),(1,0),(0,1),(1,1)}`.
All four trained surfaces have zero grid-level butterfly and calendar violations; their median in-sample relative price error is 0.173%.
The equality of the ablation results is itself informative: the filtered training region was already smooth enough that the penalties were inactive.

### 5.3 Robustness

Thirty percent of liquid quotes are randomly dropped with seed 42.
The remaining 156 quotes train the models and 68 independent dropped quotes form the evaluation set.

| Model | Median relative error | P95 relative error |
|---|---:|---:|
| SVI refit | 0.067% | 0.182% |
| Neural surface | 0.204% | 0.941% |

The SVI refit is more accurate on this small, structured snapshot, while the neural model provides a smooth differentiable surface and remains competitive under missing quotes.

[Differentiable calibration](questions/q1/results/approach2/differentiable/svi_convergence.html)

[Neural ablation](questions/q1/results/approach2/differentiable/neural_ablation.html)

## 6. Reproducibility and validation

The environment is Python 3.13 with dependencies pinned in `pyproject.toml` and `uv.lock`.
The default seed is 42.
The canonical commands are:

```bash
uv sync
python data/fetch.py --seed 42
python code/approach1_market_pipeline.py --seed 42
python code/approach2_differentiable.py --seed 42
python code/compare.py
```

Both approaches expose `argparse` CLIs, write the required `metrics.json` schema, use self-contained Plotly HTML, and preserve quote filtering, divergence cases, parity residuals, no-arbitrage counts, convergence information, and dropout results.

## 7. Limitations

The source supplies daily OHLCV closes rather than synchronized bid/ask mids, so parity residuals and repricing tails reflect stale and asynchronous quotes.
Zero dividend yield is a simplifying assumption.
The snapshot uses a manageable set of CFFEX contracts rather than every listed ETF chain.
The calendar block has only a few overlapping expiry dates after the strict liquidity filter, which is why calendar violations are reported as diagnostics rather than interpreted as a definitive market-arbitrage claim.
A production surface would use bid/ask intervals, dividend forecasts, more contracts, and constrained price-space calibration across all maturities.

## 8. Division of work

The terminal workflow implemented the data retrieval, checksum metadata, numerical estimators, constrained calibration, neural calibration, robustness experiments, figures, and reproducibility scaffolding.
The group is responsible for reviewing assumptions, checking the mathematics, approving the quote filter and dividend convention, and making final claims.


---

# Q2. Monte Carlo pricing and hedging on Chinese futures

I first checked that the simulator could reproduce a Black-Scholes price.
Then I used the same daily grid to compare pricing estimators and test whether the learned hedge reduced losses after trading costs.

## Data and setup

I used daily IF0 and CU0 futures closes from Sina Finance, the CSI 300 cash index from Eastmoney, and SHIBOR fixings from Jin10, all retrieved through AKShare.
The calibration window was January 2, 2020 through December 31, 2025, with 1,455 closes and 1,454 log returns per contract.
The loader verifies the committed snapshots against the [data manifest](questions/q2/data/metadata.json).
The CSI 300 cash index is a reference series.
The model inputs come from the futures closes.

For daily log returns $x_t=\log(S_t/S_{t-1})$, I estimated annualized volatility as $\hat\sigma=\sqrt{252}\,s_x$ and historical GBM drift as $\hat\mu=252\,\bar x+\hat\sigma^2/2$.

| Contract | Last close | Annual volatility | Annual GBM drift |
|---|---:|---:|---:|
| IF0 | 4,599.80 | 20.31% | 3.80% |
| CU0 | 98,240.00 | 17.87% | 13.57% |

I valued the options on December 31, 2025 with a one-year maturity.
I interpolate SHIBOR simple quotes by tenor and convert the selected quote $q$ to $r=\log(1+qT)/T$.
The one-year fixing of 1.65% gives $r=1.6365\%$.
Under the assignment's pricing model, each daily step is

$$
S_{i+1}=S_i\exp\!\left[(r-\hat\sigma^2/2)\Delta t+\hat\sigma\sqrt{\Delta t}\,Z_i\right],
\qquad Z_i\overset{\mathrm{iid}}{\sim}N(0,1).
$$

Both engines use 252 steps, 100,000 paths for pricing, and seed 42 with separate random streams.
The strike is $K=S_0$.
The arithmetic Asian pays $(\bar S-K)^+$, averaging the 252 observations after time zero.
The up-and-out pays $(S_T-K)^+$ if the price stays below $1.5S_0$ at every monitoring date, with zero rebate.
The digital pays one unit if $S_T>K$.
All prices are discounted sample means.

## Q2A. Pricing accuracy and efficiency

I tested the European call first using $z=(\widehat C_{\mathrm{MC}}-C_{\mathrm{BS}})/\mathrm{SE}$.
All four checks passed the assignment's $|z|\leq3$ threshold.
The NumPy validation stream is separate from its headline pricing run.

| Contract | Engine | European validation price ± SE | Black-Scholes | z |
|---|---|---:|---:|---:|
| IF0 | NumPy | 403.63 ± 2.01 | 407.57 | -1.964 |
| IF0 | PyTorch | 406.79 ± 2.02 | 407.57 | -0.384 |
| CU0 | NumPy | 7,784.36 ± 37.70 | 7,763.82 | +0.545 |
| CU0 | PyTorch | 7,748.08 ± 37.71 | 7,763.82 | -0.417 |

The entries below are price ± one Monte Carlo standard error.

| Contract | Engine | Arithmetic Asian | Up-and-out | Digital |
|---|---|---:|---:|---:|
| IF0 | NumPy | 230.81 ± 1.11 | 313.06 ± 1.54 | 0.4831 ± 0.0016 |
| IF0 | PyTorch | 232.33 ± 1.12 | 311.82 ± 1.54 | 0.4811 ± 0.0016 |
| CU0 | NumPy | 4,436.75 ± 21.02 | 6,729.13 ± 31.91 | 0.4947 ± 0.0016 |
| CU0 | PyTorch | 4,416.94 ± 20.92 | 6,704.53 ± 31.97 | 0.4900 ± 0.0016 |

At equal path counts, I compared the plain estimator with averages of the paired shocks $Z$ and $-Z$.
I computed antithetic standard errors from the pair averages and report variance ratios as squared standard-error ratios.
For the arithmetic Asian I also used the discounted geometric Asian payoff $Y$ as a control, with $\widehat C_{\mathrm{CV}}=\bar X-\hat\beta(\bar Y-E[Y])$ and $\hat\beta=\widehat{\mathrm{Cov}}(X,Y)/\widehat{\mathrm{Var}}(Y)$.
Here $X$ is the discounted arithmetic Asian payoff and $E[Y]$ is the lognormal call value on the geometric mean over the same observation dates.
For $m$ dates $t_i=i\Delta t$, the geometric mean has log mean $a=\log S_0+(r-\sigma^2/2)\Delta t(m+1)/2$ and log variance $v=\sigma^2\Delta t(m+1)(2m+1)/(6m)$.
The control value is $E[Y]=e^{-rT}[e^{a+v/2}\Phi(d_1)-K\Phi(d_2)]$, where $d_2=(a-\log K)/\sqrt v$ and $d_1=d_2+\sqrt v$.

| Contract | Asian antithetic variance ratio | Asian control variance ratio | Control price ± SE |
|---|---:|---:|---:|
| IF0 | 1.78× | 1,388× | 232.50 ± 0.03 |
| CU0 | 1.86× | 1,760× | 4,419.86 ± 0.50 |

The geometric control reduced variance the most because the two averages use the same paths and fixing dates.
I measured RMSE from 100 to 30,000 paths using repeated runs, with Black-Scholes as the European reference and an independent 1,000,000-pair estimate as the Asian reference.
The log–log slopes ranged from −0.534 to −0.471, close to the expected −0.5.

I checked delta and vega for the European and arithmetic Asian calls on 50,000 paths.
Writing $L=S_T$ or $L=\bar S$, the pathwise samples are $e^{-rT}1_{L>K}L/S_0$ for delta and $e^{-rT}1_{L>K}\partial_\sigma L$ for vega, with $\partial_\sigma S_t=S_t(W_t-\sigma t)$.
The central differences use the same shocks for both bumps, with the strike held fixed.
Delta bumps were 10%, 1%, and 0.1% of spot, and vega bumps were 0.005, 0.002, and 0.001 in volatility units.
For example, IF0 European delta was 0.5691 pathwise versus 0.5694 at the 1% bump, with standard errors near 0.0026.
The larger bump smooths more of the strike kink and can add bias, while shared shocks kept sampling noise similar across the bump sizes.

The loop and NumPy benchmark used the same workload of 1,024 paths × 252 steps.
The mean `timeit` runtimes were 40.5 ms for the loop and 2.8 ms for NumPy on IF0, and 40.3 ms for the loop and 2.6 ms for NumPy on CU0.
The IF0 [profile](questions/q2/results/approach1/if0/performance_profile.txt) identifies the scalar normal generator as the main cost inside the Python loop.
The [IF0](questions/q2/results/approach1/if0/estimators.html) and [CU0](questions/q2/results/approach1/cu0/estimators.html) figures show the convergence and Greek checks.

## Q2B. Hedging after transaction costs

I used a short at-the-money European call for the hedge comparison because it has an exact Black-Scholes delta.
The PyTorch engine also prices the three exotic options above.
The hedge is a one-hidden-layer MLP with 16 units, tanh activation, and a sigmoid output, taking $S_t/S_0$ and $t$ as inputs.
I used the assignment's terminal P&L, with gains accrued to expiry, the fee charged on each change in position including entry, and the call payoff deducted at maturity.

$$
V_T=\sum_j e^{r(T-t_j)}\Delta_j(S_{t_{j+1}}-S_{t_j})
-\kappa\sum_j|\Delta_j-\Delta_{j-1}|S_{t_j}-(S_T-K)^+,
\qquad \Delta_{-1}=0.
$$

I trained a separate model for each contract, frequency, and cost.
Each fit used Adam at 0.003 for five epochs on 131,072 paths in batches of 4,096, minimizing the mean of the worst 5% of simulated losses $-V_T$.
I selected the epoch on 8,192 validation paths and compared both strategies on the same 32,768 fresh test paths.

Each cell reports **learned hedge / Black-Scholes delta** in the instrument's price units, with squared price units for variance.

| Contract | Days | Cost (bp) | 95% CVaR of loss | Mean P&L | P&L variance |
|---|---:|---:|---:|---:|---:|
| IF0 | 1 | 0 | 694.21 / 427.18 | -370.38 / -370.23 | 27,657 / 937 |
| IF0 | 1 | 10 | 709.42 / 458.98 | -383.91 / -395.91 | 27,786 / 1,045 |
| IF0 | 1 | 50 | 768.19 / 611.74 | -435.90 / -498.61 | 28,476 / 2,974 |
| IF0 | 5 | 0 | 704.67 / 478.15 | -370.47 / -370.39 | 28,795 / 2,464 |
| IF0 | 5 | 10 | 713.74 / 495.13 | -378.08 / -383.40 | 28,963 / 2,525 |
| IF0 | 5 | 50 | 746.11 / 567.13 | -407.62 / -435.40 | 29,201 / 3,070 |
| IF0 | 21 | 0 | 743.88 / 584.74 | -370.19 / -369.50 | 33,249 / 8,569 |
| IF0 | 21 | 10 | 749.56 / 594.20 | -374.99 / -376.89 | 33,348 / 8,656 |
| IF0 | 21 | 50 | 768.66 / 632.54 | -394.05 / -406.42 | 33,352 / 9,057 |
| CU0 | 1 | 0 | 14,022.37 / 8,074.83 | -6,959.38 / -6,952.55 | 11,793,391 / 372,250 |
| CU0 | 1 | 10 | 14,313.21 / 8,742.25 | -7,216.54 / -7,500.95 | 11,849,531 / 424,588 |
| CU0 | 1 | 50 | 15,510.04 / 12,022.63 | -8,177.63 / -9,694.54 | 12,290,241 / 1,315,118 |
| CU0 | 5 | 0 | 14,171.01 / 9,013.55 | -6,961.05 / -6,955.90 | 12,106,748 / 911,837 |
| CU0 | 5 | 10 | 14,324.81 / 9,371.98 | -7,106.96 / -7,233.56 | 12,106,774 / 939,247 |
| CU0 | 5 | 50 | 15,007.45 / 10,911.71 | -7,677.95 / -8,344.24 | 12,311,450 / 1,186,636 |
| CU0 | 21 | 0 | 14,732.41 / 11,005.20 | -6,954.94 / -6,938.98 | 13,357,217 / 3,066,979 |
| CU0 | 21 | 10 | 14,823.66 / 11,206.51 | -7,052.27 / -7,096.65 | 13,339,678 / 3,103,163 |
| CU0 | 21 | 50 | 15,298.18 / 12,024.23 | -7,433.46 / -7,727.34 | 13,537,197 / 3,271,041 |

Black-Scholes had lower test CVaR in all 18 cases.
For example, at daily rebalancing on IF0, raising costs from 0 to 50 bp increased the learned hedge's CVaR from 694.21 to 768.19 and the benchmark's from 427.18 to 611.74.
The learned hedge's mean P&L was better at 50 bp in that case, but the extra dispersion left its tail loss higher.
The [comparison page](questions/q2/results/comparison.html) contains the full ranking, and the [IF0](questions/q2/results/approach2/if0/figures.html) and [CU0](questions/q2/results/approach2/cu0/figures.html) charts show the cost and frequency effects.

## Limits

The continuous futures series use vendor rolls without a separate roll adjustment, so roll moves can affect calibration.
The simulation follows the assignment's GBM convention with a constant rate for the chosen maturity and tests hedges on simulated paths.
The Greek and RMSE comparisons focus on European and arithmetic Asian calls.
All 18 learned policies selected the final epoch on validation, so the five-epoch run leaves training convergence open.
The hedge result applies to the European call and this experiment setup.
Use the [README command](questions/q2/README.md) to regenerate the tables and figures from the saved snapshots.


---

# Q4 China Financial and Trade Networks

## 1. Executive summary

This project studies an annual directed trade network induced by China’s largest trade partners from 2014–2023.
Approach 1 measures network structure, minimum spanning trees, Louvain communities, centrality, and temporal migration.
Approach 2 implements node2vec with biased walks, skip-gram negative sampling, a learned bilinear link scorer, and three heuristic baselines.
On the fixed 2023 held-out split, the best embedding configuration (`p=2`, `q=0.5`, dimension 64) reaches AUC 0.810 and average precision 0.847, compared with AUC 0.750 for preferential attachment, 0.745 for common neighbors, and 0.705 for Adamic–Adar.

## 2. Data and network construction

The source is the keyless UN Comtrade preview API specified by the assignment. `data/fetch.py` first ranks partners by China’s latest anchor-year imports plus exports, selects 20 partners, and fixes the node set to China plus those partners for every year.
It then retrieves reported exports for every induced reporter–partner pair.
The committed clean snapshot contains 10 years, 21 country nodes, and 4,160 positive raw edge rows.
Raw API responses are cached under the ignored `data/raw/` directory; `data/clean/metadata.json` records the retrieval timestamp, schema, source, and SHA-256 hashes.

For year `t`, the raw directed edge is

\[
T_{ij,t}=\text{primaryValue}_{ij,t},
\]

measured in USD.
Because all selected countries report some small positive bilateral flows, the unfiltered induced graph is nearly complete and cannot support equal negative sampling.
The analysis graph therefore keeps the six largest export edges per reporter per year.
This rule is fixed before evaluation, is applied identically across years, and leaves the unfiltered clean snapshot available for audit.
Self-loops are excluded by construction and checked in every run.

The assignment’s stock-industry labels are not defined for country nodes.
We therefore use geographical region as a clearly labelled proxy only for community comparison; the primary Q4-B task is held-out trade-edge recovery rather than industry prediction.

## 3. Reproducibility

The environment is Python 3.13 with dependencies pinned in `pyproject.toml` and `uv.lock`.
The global default seed is 42.
The canonical commands are:

```bash
uv sync
python data/fetch.py --seed 42
python code/approach1_network_analytics.py --seed 42 --top-k 6
python code/approach2_node_embeddings.py --seed 42 --top-k 6
python code/compare.py
```

Each approach uses the required CLI, writes `results/approachN/trade/metrics.json` with `params`, `metrics`, `fit_seconds`, and `history`, and writes self-contained Plotly HTML figures.

## 4. Approach 1: network analytics

The directed graph is converted to an undirected weighted graph by summing reciprocal export weights.
The metric used for the Kruskal minimum spanning tree is

\[
d_{ij}=\frac{1}{\log(1+w_{ij})},
\]

so larger trade relationships have shorter distances.
We report node count, edge count, density, mean degree, a log–log degree-frequency slope, assortativity, connected components, isolated nodes, and self-loops.
Louvain maximizes the weighted modularity

\[
Q=\frac{1}{2m}\sum_{ij}\left(A_{ij}-\frac{k_i k_j}{2m}\right)\mathbf{1}(c_i=c_j).
\]

PageRank uses damping 0.85.
Betweenness uses shortest paths, and weighted degree sums trade values.
Resolution sensitivity is evaluated at 0.5, 1.0, and 1.5.
Consecutive-year migration is reported as an aligned contingency matrix and ARI.

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

There are no self-loops.
One isolated node is reported in 2022; it is not silently removed.
The 2023 top PageRank nodes are the United States, China, Mexico, Germany, and Japan.
The 2023 resolution sweep produces 1, 4, and 6 communities at resolutions 0.5, 1.0, and 1.5 respectively.

[Network evolution](questions/q4/results/approach1/trade/network_evolution.html)

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

multiplied by the observed edge weight before normalization.
Walk contexts use a window of two.
The skip-gram objective uses positive context pairs and five uniformly sampled negative contexts:

\[
\log\sigma(z_v^\top c_u)+\sum_{r=1}^{5}\log\sigma(-z_v^\top c_{n_r}).
\]

The final-year graph is split into 80/10/10 positive edges and an equal number of negative non-edges: 72/9/10 in train/validation/test.
The learned link score is

\[
s(u,v)=\sigma(z_u^\top Wz_v),
\]

where `W` is fitted only on the training split.
Baselines are common neighbors, Adamic–Adar, and preferential attachment.
We report AUC, average precision, and k-means agreement with Louvain and the region proxy using ARI/NMI.

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

At the best configuration, average precision is 0.847.
Embedding clusters have ARI 0.069 and NMI 0.249 against Louvain, and ARI 0.016 and NMI 0.293 against the region proxy.
Thus the embedding is more useful for edge recovery than for reproducing the classical community partition.

[Link prediction](questions/q4/results/approach2/trade/link_prediction.html)

## 6. Limitations and checks

The preview API provides reported values and does not guarantee a complete reconciled world trade matrix.
The fixed 21-node induced network is intentionally manageable and is not a full global network.
The top-k rule improves link-prediction identifiability but changes the interpretation from all reported flows to major relationships.
Country regions are not industry labels, so region agreement is explicitly a proxy rather than evidence of industry alignment.
The test set is small; AUC and AP are reported together and should not be overinterpreted.
Future work would use a larger country universe, multiple HS levels, repeated temporal test windows, and bootstrap uncertainty intervals.

## 7. Division of work

The terminal workflow implemented the data retrieval, checksum metadata, graph construction, estimators, benchmarks, figures, and reproducibility scaffolding.
The group is responsible for reviewing mathematical definitions, checking the generated results, approving the top-k and proxy-label assumptions, and making the final claims.

