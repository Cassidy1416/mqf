# Q1 Implied Volatility Surface of China Index Options

## 1. Executive summary

This project estimates China CSI 300 option implied-volatility surfaces using public CFFEX historical contract data. Approach 1 performs quote filtering, Black–Scholes inversion, put–call parity diagnostics, constrained SVI calibration, repricing, and no-arbitrage checks. Approach 2 compares differentiable PyTorch SVI calibration with SciPy and trains a price-space neural surface with butterfly/calendar penalties. The liquid quote pipeline retains 225 quotes, successfully inverts 224, fits 12 SVI groups, obtains zero butterfly-grid violations, and has 1.67% median liquid-strike repricing error. Under a 30% quote-drop experiment, SVI obtains 0.067% median relative price error on held-out quotes and the neural surface obtains 0.204%.

## 2. Data and provenance

The data pipeline uses the assignment-approved `akshare` interfaces: `option_cffex_hs300_spot_sina` and `option_cffex_hs300_daily_sina` for contract strikes and daily OHLCV, `stock_zh_index_daily(symbol="sh000300")` for the CSI 300 index, and `macro_china_shibor_all` for the historical 3M SHIBOR rate. The snapshot contains nine expiry months, 1,134 raw call/put quote rows, 177 observed dates, and a date range from 2023-03-20 to 2026-01-13. A shared October 2023 block contains four expiries on five dates, enabling calendar diagnostics.

For every selected contract, the fetcher keeps the first five trading dates within a 31-calendar-day window and 13 evenly spaced strikes. It also keeps a common 2023-10-23 through 2023-10-27 block for four overlapping expiries when the contract traded on those dates. Raw responses are cached in ignored `data/raw/`; clean snapshots and SHA-256 hashes are committed in `data/clean/metadata.json`.

The formal liquid-quote rule is volume at least 40 and forward moneyness `0.9 <= K/F <= 1.1`. The rule is declared before calibration and is exposed through CLI parameters. The underlying dividend yield is set to zero because the primary instrument is the CSI 300 index option rather than an ETF; this assumption is a limitation and is not hidden.

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

Implied volatility is obtained separately for every call and put using bracketed Brent root finding on `[10^-4, 5]`. Five of 225 filtered quotes fail the admissible price bracket and are reported as divergence cases rather than silently removed.

Put–call parity is evaluated as

\[
\epsilon_{PC}=C-P-(S-Ke^{-rT}).
\]

There are 166 matched strike groups after filtering. The mean residual is 0.0165 index points, RMSE is 14.4405, and the 95th percentile absolute residual is 19.0721. The large dispersion is retained as a data-quality finding because daily closes are not executable bid/ask mids.

## 4. Approach 1: classical market pipeline

For each date/expiry group, total variance is `w(k)=sigma_IV^2 T` and log-moneyness is `k=log(K/F)`. SVI is

\[
w(k)=a+b\left[\rho(k-m)+\sqrt{(k-m)^2+\eta^2}\right],
\]

with `b >= 0`, `|rho| < 1`, and `eta > 0`. The implementation first obtains a bounded least-squares initialization and then uses SLSQP with inequality constraints `g(k)>=0` on an 81-point interior grid. The objective remains squared total-variance error; constraint failure is reported.

The Gatheral butterfly diagnostic is

\[
g(k)=\left(1-\frac{kw'(k)}{2w(k)}\right)^2-
\frac{w'(k)^2}{4}\left(\frac1{w(k)}+\frac14\right).
\]

Calendar checks compare fitted total variance at the same `k` for increasing expiries. Forward variance is the finite difference of total variance divided by the maturity difference. The surface is delivered on an 81-point fixed grid in `results/approach1/market/surface_grid.csv`.

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

Calendar and forward-variance violations occur on 2023-10-23 and 2023-10-24; they are counted and located in `metrics.json`. No violations are silently dropped. The high group-level p95 is consistent with sparse daily close data and is discussed as a limitation.

![SVI surface](results/approach1/market/svi_surface.html)

![Arbitrage diagnostics](results/approach1/market/arbitrage_diagnostics.html)

## 5. Approach 2: differentiable calibration

### 5.1 Differentiable SVI

The PyTorch SVI implementation uses reparameterization:

\[
a=\operatorname{softplus}(u_a),\quad b=\operatorname{softplus}(u_b),\quad
\rho=0.999\tanh(u_\rho),\quad \eta=\operatorname{softplus}(u_\eta).
\]

Adam runs for 300 epochs on each of the 12 groups. The mean SciPy objective is `1.97e-08`, while the mean Torch objective is `1.97e-08`; mean wall time is 0.0087 seconds for SciPy and 0.0374 seconds for Torch on this small dataset. This comparison separates optimizer overhead from statistical fit quality.

### 5.2 Neural surface

The neural surface is an MLP with two hidden tanh layers and a positive softplus volatility output. Inputs are `(k,T)`. The loss is normalized option-price squared error plus arbitrage penalties:

\[
\mathcal L=\operatorname{MSE}\left(\frac{\hat C-C_{mkt}}{F}\right)
 +\lambda_b\operatorname{mean}[\max(0,-g(k))^2]
 +\lambda_T\operatorname{mean}[\max(0,-\partial_Tw)^2].
\]

The ablation grid is `(lambda_b,lambda_T)` in `{(0,0),(1,0),(0,1),(1,1)}`. All four trained surfaces have zero grid-level butterfly and calendar violations; their median in-sample relative price error is 0.173%. The equality of the ablation results is itself informative: the filtered training region was already smooth enough that the penalties were inactive.

### 5.3 Robustness

Thirty percent of liquid quotes are randomly dropped with seed 42. The remaining 156 quotes train the models and 68 independent dropped quotes form the evaluation set.

| Model | Median relative error | P95 relative error |
|---|---:|---:|
| SVI refit | 0.067% | 0.182% |
| Neural surface | 0.204% | 0.941% |

The SVI refit is more accurate on this small, structured snapshot, while the neural model provides a smooth differentiable surface and remains competitive under missing quotes.

![Differentiable calibration](results/approach2/differentiable/svi_convergence.html)

![Neural ablation](results/approach2/differentiable/neural_ablation.html)

## 6. Reproducibility and validation

The environment is Python 3.13 with dependencies pinned in `pyproject.toml` and `uv.lock`. The default seed is 42. The canonical commands are:

```bash
uv sync
python data/fetch.py --seed 42
python code/approach1_market_pipeline.py --seed 42
python code/approach2_differentiable.py --seed 42
python code/compare.py
```

Both approaches expose `argparse` CLIs, write the required `metrics.json` schema, use self-contained Plotly HTML, and preserve quote filtering, divergence cases, parity residuals, no-arbitrage counts, convergence information, and dropout results.

## 7. Limitations

The source supplies daily OHLCV closes rather than synchronized bid/ask mids, so parity residuals and repricing tails reflect stale and asynchronous quotes. Zero dividend yield is a simplifying assumption. The snapshot uses a manageable set of CFFEX contracts rather than every listed ETF chain. The calendar block has only a few overlapping expiry dates after the strict liquidity filter, which is why calendar violations are reported as diagnostics rather than interpreted as a definitive market-arbitrage claim. A production surface would use bid/ask intervals, dividend forecasts, more contracts, and constrained price-space calibration across all maturities.

## 8. Division of work

The terminal workflow implemented the data retrieval, checksum metadata, numerical estimators, constrained calibration, neural calibration, robustness experiments, figures, and reproducibility scaffolding. The group is responsible for reviewing assumptions, checking the mathematics, approving the quote filter and dividend convention, and making final claims.
