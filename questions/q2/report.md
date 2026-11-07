# Q2. Monte Carlo pricing and transaction-cost hedging

## Data, model and reproducible protocol

The committed snapshots contain IF0 and CU0 continuous futures daily closes, CSI 300 reference-index observations and eight-tenor SHIBOR fixings obtained through AKShare.
The [manifest](data/metadata.json) records query, retrieval date, source, schema, hashes and units.
Calibration uses 2020-01-02 through 2025-12-31, with 1,455 closes and 1,454 log returns per contract.
IF0 and CU0 are Sina continuous main-contract series; vendor-selected contract rolls are retained without an independently reconstructed roll calendar or back adjustment.
Roll jumps may affect estimated volatility and drift.
For $x_t=\log(S_t/S_{t-1})$, $\hat\sigma=\sqrt{252}s_x$ and $\hat\mu=252\bar x+\hat\sigma^2/2$.
Historical drift is reported but does not replace the risk-neutral drift in pricing.
At the 2025-12-31 valuation date, the one-year SHIBOR quote 1.65% becomes $r=\log(1+0.0165)=0.0163653541$.
The rate helper interpolates the available simple quotes by tenor before conversion; at this exact one-year tenor no interpolation is needed.

| Contract | S0 | Annual sigma | Annual mu | Log drift |
| --- | --- | --- | --- | --- |
| IF0 | 4599.8 | 0.2031 | 0.038026 | 0.017401 |
| CU0 | 98240 | 0.1787 | 0.13571 | 0.11975 |

Both engines implement exact GBM steps $S_{i+1}=S_i\exp[(r-\sigma^2/2)\Delta t+\sigma\sqrt{\Delta t}Z_i]$, with $Z_i$ independent standard normal and $m=\lceil252T\rceil$, $\Delta t=T/m$.
This is the assignment's GBM approximation to a futures-price input; it does not model margined futures settlement or a full commodity term structure.
The strike is $K=S_0$, maturity one year, and each pricing engine uses 100,000 paths on 252 daily steps.
The Asian payoff is $(m^{-1}\sum_{i=1}^m S_i-K)^+$, the barrier payoff is $(S_T-K)^+1_{\max_i S_i<1.5S_0}$ with daily monitoring and zero rebate, and the digital pays $1_{S_T>K}$.
Each price is the discounted sample mean and its standard error is the sample standard deviation divided by the square root of the number of independent observations.
SeedSequence-derived training, validation and testing streams are separate; NumPy testing further separates headline prices, estimator comparisons, Greeks and convergence analysis.
No seed is selected for favorable outcomes.

## Pricing and Black-Scholes verification

For the European call, $C_{BS}=S_0\Phi(d_1)-Ke^{-rT}\Phi(d_2)$ with $d_1=[\log(S_0/K)+(r+\sigma^2/2)T]/(\sigma\sqrt T)$ and $d_2=d_1-\sigma\sqrt T$.
The reported headline z-score is computed from that same price and standard error; NumPy's separate validation run has its own z-score.

| Contract | Run | Price | SE | Black-Scholes | z |
| --- | --- | --- | --- | --- | --- |
| IF0 | NumPy headline | 405.55 | 2.0152 | 407.57 | -1.0012 |
| IF0 | NumPy independent validation | 403.63 | 2.005 | 407.57 | -1.964 |
| IF0 | Torch headline | 406.79 | 2.0242 | 407.57 | -0.38412 |
| CU0 | NumPy headline | 7815.2 | 37.76 | 7763.8 | 1.3602 |
| CU0 | NumPy independent validation | 7784.4 | 37.701 | 7763.8 | 0.54487 |
| CU0 | Torch headline | 7748.1 | 37.71 | 7763.8 | -0.41738 |

All displayed European checks satisfy $|z|\le3$.

| Contract | Engine | Asian price / SE | Up-and-out price / SE | Digital price / SE |
| --- | --- | --- | --- | --- |
| IF0 | NumPy | 230.81 / 1.114 | 313.06 / 1.5397 | 0.48311 / 0.0015552 |
| IF0 | Torch | 232.33 / 1.1187 | 311.82 / 1.5404 | 0.48111 / 0.0015551 |
| CU0 | NumPy | 4436.8 / 21.019 | 6729.1 / 31.908 | 0.49473 / 0.0015555 |
| CU0 | Torch | 4416.9 / 20.921 | 6704.5 / 31.975 | 0.49003 / 0.0015555 |

## Variance reduction, Greeks and convergence

Antithetic estimates average the discounted payoffs from $Z$ and $-Z$ before computing their standard errors.
At the same total simulated path count, the variance reduction ratio is $SE_{plain}^2/SE_{method}^2$.
For the Asian control, $\hat C=\bar X-\hat\beta(\bar Y-EY)$, with $\hat\beta=\widehat{\mathrm{Cov}}(X,Y)/\widehat{\mathrm{Var}}(Y)$ computed using consistent sample normalization.
Here $Y$ is the discounted geometric-Asian payoff.
For $t_i=i\Delta t$, geometric log mean is $a=\log S_0+(r-\sigma^2/2)\Delta t(m+1)/2$ and variance is $v=\sigma^2\Delta t(m+1)(2m+1)/(6m)$.
The closed form is $EY=e^{-rT}[e^{a+v/2}\Phi(d_1)-K\Phi(d_2)]$, where $d_2=(a-\log K)/\sqrt v$ and $d_1=d_2+\sqrt v$.
The estimated control coefficient has finite-sample uncertainty; this same-sample fit is not an exact unbiased oracle coefficient.

| Contract | Payoff | Antithetic variance ratio | Geometric-CV variance ratio |
| --- | --- | --- | --- |
| IF0 | european | 1.7431 | n/a |
| IF0 | asian | 1.7787 | 1388 |
| IF0 | up_and_out | 1.6922 | n/a |
| IF0 | digital | 30.225 | n/a |
| CU0 | european | 1.7636 | n/a |
| CU0 | asian | 1.8561 | 1760 |
| CU0 | up_and_out | 1.789 | n/a |
| CU0 | digital | 291.19 | n/a |

For European pathwise delta, the path contribution is $e^{-rT}1_{S_T>K}S_T/S_0$; vega is $e^{-rT}1_{S_T>K}S_T(\sqrt T Z-\sigma T)$.
For the Asian call, replace terminal derivatives by the average of each monitored state's derivative and use the Asian in-the-money indicator.
Central finite differences use common random numbers, $[P(x+h)-P(x-h)]/(2h)$.
Spot bumps are $0.1S_0,0.01S_0,0.001S_0$; vega bumps are absolute volatility increments 0.005, 0.002 and 0.001, because volatility and spot have different units.
Pathwise estimates are reported for continuous call payoffs; no invalid pathwise derivative is claimed for the discontinuous digital or barrier.

| Contract | Payoff | Greek | Method / bump | Estimate | SE | Analytic vanilla |
| --- | --- | --- | --- | --- | --- | --- |
| IF0 | european | delta | pathwise | 0.56913 | 0.0026463 | 0.57226 |
| IF0 | european | delta | 10.000% | 0.56405 | 0.0023897 | 0.57226 |
| IF0 | european | delta | 1.000% | 0.56943 | 0.0026229 | 0.57226 |
| IF0 | european | delta | 0.100% | 0.56915 | 0.0026443 | 0.57226 |
| IF0 | asian | delta | pathwise | 0.54323 | 0.0024404 | n/a |
| IF0 | asian | delta | 10.000% | 0.53379 | 0.0019527 | n/a |
| IF0 | asian | delta | 1.000% | 0.5429 | 0.0023954 | n/a |
| IF0 | asian | delta | 0.100% | 0.5432 | 0.0024362 | n/a |
| IF0 | european | vega | pathwise | 1803.9 | 15.315 | 1804.9 |
| IF0 | european | vega | 0.005 | 1803.9 | 15.314 | 1804.9 |
| IF0 | european | vega | 0.002 | 1803.9 | 15.314 | 1804.9 |
| IF0 | european | vega | 0.001 | 1803.9 | 15.314 | 1804.9 |
| IF0 | asian | vega | pathwise | 1050.6 | 8.2357 | n/a |
| IF0 | asian | vega | 0.005 | 1050.6 | 8.2356 | n/a |
| IF0 | asian | vega | 0.002 | 1050.6 | 8.2357 | n/a |
| IF0 | asian | vega | 0.001 | 1050.6 | 8.2357 | n/a |
| CU0 | european | delta | pathwise | 0.57015 | 0.0025836 | 0.57179 |
| CU0 | european | delta | 10.000% | 0.56269 | 0.0022862 | 0.57179 |
| CU0 | european | delta | 1.000% | 0.5699 | 0.0025574 | 0.57179 |
| CU0 | european | delta | 0.100% | 0.57006 | 0.0025812 | 0.57179 |
| CU0 | asian | delta | pathwise | 0.54214 | 0.0024088 | n/a |
| CU0 | asian | delta | 10.000% | 0.53201 | 0.0018506 | n/a |
| CU0 | asian | delta | 1.000% | 0.5425 | 0.0023565 | n/a |
| CU0 | asian | delta | 0.100% | 0.54217 | 0.0024037 | n/a |
| CU0 | european | vega | pathwise | 38260 | 314.8 | 38556 |
| CU0 | european | vega | 0.005 | 38262 | 314.79 | 38556 |
| CU0 | european | vega | 0.002 | 38261 | 314.79 | 38556 |
| CU0 | european | vega | 0.001 | 38260 | 314.8 | 38556 |
| CU0 | asian | vega | pathwise | 22273 | 171.12 | n/a |
| CU0 | asian | vega | 0.005 | 22273 | 171.12 | n/a |
| CU0 | asian | vega | 0.002 | 22273 | 171.12 | n/a |
| CU0 | asian | vega | 0.001 | 22273 | 171.12 | n/a |

Large spot bumps smooth the payoff kink and introduce visible truncation bias, especially for the Asian delta.
The smaller common-random-number bumps converge to the pathwise estimates within the displayed Monte Carlo errors; small bumps do not eliminate sampling uncertainty.
The Asian has no claimed analytic Greek benchmark.

| Contract | RMSE series | Log-log slope | Fitted RMSE at N=1000 |
| --- | --- | --- | --- |
| IF0 | plain_european | -0.48307 | 20.996 |
| IF0 | antithetic_european | -0.52154 | 15.625 |
| IF0 | plain_asian | -0.47092 | 11.757 |
| IF0 | antithetic_asian | -0.48331 | 8.7617 |
| IF0 | cv_asian | -0.52356 | 0.29087 |
| CU0 | plain_european | -0.50078 | 378.33 |
| CU0 | antithetic_european | -0.47397 | 293.7 |
| CU0 | plain_asian | -0.48166 | 213 |
| CU0 | antithetic_asian | -0.49759 | 156.32 |
| CU0 | cv_asian | -0.48285 | 5.0552 |

The path-count grid is 100, 300, 1,000, 3,000, 10,000 and 30,000, with 4,096, 1,024, 512, 256, 64 and 32 independent replications respectively.
The Asian reference is an independent one-million-pair antithetic plus geometric-control estimate, with the coefficient and standard error computed on independent pair averages.
Its finite uncertainty is retained below rather than treating an ordinary noisy MC estimate as exact truth.
Slopes near -0.5 support the expected Monte Carlo order over this finite range; they do not constitute an asymptotic proof.

| Contract | Asian reference | Reference SE | Scalar seconds | Vectorized seconds | Speedup |
| --- | --- | --- | --- | --- | --- |
| IF0 | 232.46 | 0.0066694 | 0.041625 | 0.0027069 | 15.377 |
| CU0 | 4419.9 | 0.11104 | 0.041767 | 0.0027429 | 15.227 |

The timing comparison uses 1,024 paths on the same daily grid, and cProfile identifies the scalar normal-draw/exponential loop as the hot path.
Machine-dependent timings are evidence of this run, rather than fixed performance guarantees.
Profiles: [IF0](results/approach1/if0/performance_profile.txt), [CU0](results/approach1/cu0/performance_profile.txt).

## Deep hedging protocol and held-out results

The hedge sells one at-the-money European call; Asian, barrier and digital prices above do not imply that those payoffs were separately hedged.
A one-hidden-layer width-16 MLP maps $(S_t/S_0,t)$ to a bounded position.
The experiment uses the assignment's terminal accounting $V_T=\sum_t e^{r(T-t)}\Delta_t(S_{t+\Delta t}-S_t)-\kappa\sum_t|\Delta_t-\Delta_{t-1}|S_t-(S_T-K)^+$.
Entry trade cost is charged with $\Delta_{-1}=0$; no option premium is added and no terminal stock liquidation cost is charged under this stated convention.
Negative expected P&L therefore includes the sold claim's value and must not be interpreted as a premium-inclusive trading loss.
The empirical training loss is the mean of the worst 5% sample losses, a quantile-tail CVaR95 approximation.
Each cost/frequency case trains on at least $2^{17}=131,072$ paths, validates on 8,192 independent paths and tests on 32,768 held-out paths.
Adam uses learning rate 0.003 and batches of 4,096, with at most 100 epochs.
Checkpoint selection uses only S0-normalized validation CVaR, patience ten and minimum improvement $10^{-5}$.
The table reports actual trained epochs, best validation epoch and termination reason; reaching the epoch cap is not proof of convergence.
The Black-Scholes hedge and learned hedge share the same held-out paths for each case.

| Contract | Days | Cost bp | Learned CVaR | BS CVaR | Learned mean | BS mean | Learned variance | BS variance | Epochs / best | Stop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IF0 | 1 | 0 | 434.45 | 427.18 | -371.6 | -370.23 | 1984.3 | 936.6 | 100 / 98 | max_epochs_reached |
| IF0 | 1 | 10 | 459.81 | 458.98 | -394.53 | -395.91 | 2152.4 | 1045.1 | 100 / 99 | max_epochs_reached |
| IF0 | 1 | 50 | 549.99 | 611.74 | -474.97 | -498.61 | 2798.6 | 2974.2 | 100 / 99 | max_epochs_reached |
| IF0 | 5 | 0 | 475.2 | 478.15 | -371.5 | -370.39 | 3739.2 | 2464.4 | 100 / 100 | max_epochs_reached |
| IF0 | 5 | 10 | 488.07 | 495.13 | -383.03 | -383.4 | 3862.7 | 2525.1 | 100 / 100 | max_epochs_reached |
| IF0 | 5 | 50 | 537.31 | 567.13 | -426.81 | -435.4 | 4350.6 | 3070.5 | 100 / 100 | max_epochs_reached |
| IF0 | 21 | 0 | 567.96 | 584.74 | -370.41 | -369.5 | 10546 | 8568.7 | 100 / 99 | max_epochs_reached |
| IF0 | 21 | 10 | 575.44 | 594.2 | -376.9 | -376.89 | 10699 | 8656.3 | 100 / 99 | max_epochs_reached |
| IF0 | 21 | 50 | 604.83 | 632.54 | -402.29 | -406.42 | 11300 | 9057.4 | 100 / 99 | max_epochs_reached |
| CU0 | 1 | 0 | 8191.9 | 8074.8 | -6984.7 | -6952.5 | 7.4543e+05 | 3.7225e+05 | 100 / 100 | max_epochs_reached |
| CU0 | 1 | 10 | 8731.3 | 8742.3 | -7469 | -7500.9 | 8.1724e+05 | 4.2459e+05 | 100 / 100 | max_epochs_reached |
| CU0 | 1 | 50 | 10638 | 12023 | -9153.1 | -9694.5 | 1.0961e+06 | 1.3151e+06 | 100 / 99 | max_epochs_reached |
| CU0 | 5 | 0 | 8957.1 | 9013.5 | -6986.1 | -6955.9 | 1.378e+06 | 9.1184e+05 | 100 / 100 | max_epochs_reached |
| CU0 | 5 | 10 | 9230.2 | 9372 | -7231.6 | -7233.6 | 1.4266e+06 | 9.3925e+05 | 100 / 100 | max_epochs_reached |
| CU0 | 5 | 50 | 10275 | 10912 | -8152.2 | -8344.2 | 1.6343e+06 | 1.1866e+06 | 100 / 98 | max_epochs_reached |
| CU0 | 21 | 0 | 10694 | 11005 | -6965.4 | -6939 | 3.7779e+06 | 3.067e+06 | 100 / 99 | max_epochs_reached |
| CU0 | 21 | 10 | 10853 | 11207 | -7104.2 | -7096.7 | 3.8341e+06 | 3.1032e+06 | 100 / 99 | max_epochs_reached |
| CU0 | 21 | 50 | 11474 | 12024 | -7642.9 | -7727.3 | 4.0621e+06 | 3.271e+06 | 100 / 99 | max_epochs_reached |

The learned strategy has lower held-out CVaR in 15 of 18 cases; no claim of universal outperformance is supported.
Transaction costs penalize frequent position changes, so the interaction with rebalancing frequency matters more than a single headline score.
Only seed 42 is the primary experiment; robustness across training seeds and confidence intervals for CVaR differences remain limitations, not assignment-required results that have been silently assumed.
Seeded CPU training uses two threads and can retain last-bit differences across platforms.
Figures and validation histories: [NumPy IF0](results/approach1/if0/figures.html), [NumPy CU0](results/approach1/cu0/figures.html), [hedging IF0](results/approach2/if0/figures.html), [hedging CU0](results/approach2/cu0/figures.html) and [comparison](results/comparison.html).

## Statement of work: group direction and agent contribution

### Q2 work division

**Group direction and decisions.**
The group supplied the Q2 repository for integration and requested a full requirements audit and repair while retaining the IF0/CU0 pricing and transaction-cost hedging study.
The group is responsible for justifying the GBM approximation and continuous-contract calibration convention, interpreting estimator efficiency and Greek uncertainty, and assessing the economic meaning of the reported hedge P&L and CVaR.

**Coding-agent implementation and verification.**
The coding agent corrected the headline and validation z-scores, covariance normalization, maturity grid and Asian-reference uncertainty, added validation-based hedge checkpoint selection and stopping, reran the pricing and hedging experiments, and generated comparison tables, profiles, figures and regression checks.

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
