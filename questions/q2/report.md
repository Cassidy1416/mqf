# Q2. Monte Carlo pricing and hedging on Chinese futures

I first checked that the simulator could reproduce a Black-Scholes price.
Then I used the same daily grid to compare pricing estimators and test whether the learned hedge reduced losses after trading costs.

## Data and setup

I used daily IF0 and CU0 futures closes from Sina Finance, the CSI 300 cash index from Eastmoney, and SHIBOR fixings from Jin10, all retrieved through AKShare.
The calibration window was January 2, 2020 through December 31, 2025, with 1,455 closes and 1,454 log returns per contract.
The loader verifies the committed snapshots against the [data manifest](data/metadata.json).
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
The IF0 [profile](results/approach1/if0/performance_profile.txt) identifies the scalar normal generator as the main cost inside the Python loop.
The [IF0](results/approach1/if0/estimators.html) and [CU0](results/approach1/cu0/estimators.html) figures show the convergence and Greek checks.

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
The [comparison page](results/comparison.html) contains the full ranking, and the [IF0](results/approach2/if0/figures.html) and [CU0](results/approach2/cu0/figures.html) charts show the cost and frequency effects.

## Limits

The continuous futures series use vendor rolls without a separate roll adjustment, so roll moves can affect calibration.
The simulation follows the assignment's GBM convention with a constant rate for the chosen maturity and tests hedges on simulated paths.
The Greek and RMSE comparisons focus on European and arithmetic Asian calls.
All 18 learned policies selected the final epoch on validation, so the five-epoch run leaves training convergence open.
The hedge result applies to the European call and this experiment setup.
Use the [README command](README.md) to regenerate the tables and figures from the saved snapshots.
