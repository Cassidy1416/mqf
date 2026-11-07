"""Build the computational report draft from the saved, reviewed experiment schema."""
from __future__ import annotations
import argparse
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return json.loads((ROOT / relative).read_text())


def fmt(value, digits=5):
    if value is None:
        return "not reached"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value).replace("|", "/").replace("\n", " ")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + ["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]) + "\n"


def q1_report():
    a = read("questions/q1/results/approach1/market/metrics.json")
    b = read("questions/q1/results/approach2/differentiable/metrics.json")
    m, n = a["metrics"], b["metrics"]
    s, d = m["svi"]["summary"], n["dropout_30_percent"]
    text = r"""# Q1. Implied volatility surface

## Data and mathematical specification

This computational draft uses CFFEX CSI 300 index options (IO), an explicitly permitted historical alternative in the assignment.
Prices and strikes are index points; the contract multiplier is CNY 100 per index point and cancels from relative errors and implied-volatility inversion.
The instrument reference is the [CFFEX contract specification](https://www.cffex.com.cn/u/cms/www/202207/18203127l1ql.pdf).
The active snapshot contains 5,898 quotes from 2023-03-20 through 2026-01-13, including 23 daily dates from 2023-10-23 through 2023-11-22 with five common live expiries.
This is the complete chain coverage available in the imported snapshot, rather than a claim that every listed exchange contract was independently retrieved during this repair.
The source is the friend's compliance revision `cbcaaa87bd829be5b8d0ea09d4290e4f272df8b3`; exact import hashes, retrieval claims, schema and archived prior snapshots are in the [manifest](data/clean/metadata.json).
Offline verification checks bytes, columns, unique quote keys, dates and monthly coverage before experiments run.

The SHIBOR source contains 706 actual fixing dates across the eight overnight-to-one-year tenors, copied from the already committed and verified Q2 source.
For each fixing and tenor $t_j$, simple annual quote $q_j$ is converted to a continuous zero rate $r_j=\log(1+q_jt_j)/t_j$.
We linearly interpolate these zero rates to the option maturity and reject extrapolation outside the supported interval.
The spot and rate joins use only observations on or before the option date, with a maximum ten-calendar-day rate staleness rule.
We set dividend yield to zero as a transparent index carry approximation; this is a limitation for CSI 300 constituent dividends and can contribute to parity and calibration residuals.
With $F_T=S_0e^{r(T)T}$, $k=\log(K/F_T)$ and $d_\pm=[\log(F_T/K)\pm\sigma^2T/2]/(\sigma\sqrt T)$, call prices are $e^{-rT}[F_T\Phi(d_+)-K\Phi(d_-)]$; puts follow put-call parity.
Implied volatility solves the matching call or put price using bracketed Brent on $[10^{-4},5]$.
Filters require positive prices and spot, $5/365.25<T\le2$, volume at least 40 contracts and $K/F_T\in[0.9,1.1]$.
Black-Scholes bounds and the Brent bracket are checked during inversion, with failed inversions counted rather than silently excluded from the diagnostics.
Bid/ask spreads are unavailable in the historical source, so the rule uses volume and moneyness rather than an invented spread measure.
Parity uses exactly matched date/expiry/strike call-put pairs and residual $C-P-(S_0-Ke^{-rT})$.

## Classical calibration and verification

Per date and expiry, total variance is $w(k)=a+b[\rho(k-m)+\sqrt{(k-m)^2+\eta^2}]$.
The implementation bounds $a\ge0$, $b\ge0$, $|\rho|<1$ and $\eta>0$, first solves bounded SciPy least squares in total-variance space, then applies SLSQP butterfly constraints on the fixed grid.
Initialization is $(\max(\mathrm{percentile}_{10}(w),10^{-5}),0.2,0,\mathrm{median}(k),0.1)$ and each group's actual initial values and solver status are saved in metrics.
The fixed grid has 81 values over $k\in[-0.4,0.4]$.
Butterfly verification evaluates $g(k)=(1-kw'/(2w))^2-(w'^2/4)(1/w+1/4)$.
Calendar verification checks adjacent expiries at common $k$ and records every location with $w_{far}<w_{near}$ and forward variance $(w_{far}-w_{near})/(T_{far}-T_{near})<0$.
Between expiries, $w(k,T)$ is linear in total variance and $\sigma=\sqrt{w/T}$; midpoint values are exported alongside the fixed surface.
Calendar crossings are reported, without silently removing or repairing them.
Repricing error is $|C_{fit}-C_{market}|/C_{market}$ for the actual call or put quote.
The requested statistic takes the maximum across liquid quotes within each date and then the median and 95th percentile across dates.

"""
    text += table(["Diagnostic", "Result"], [["Filtered / successful IV / divergences", f"{m['filtered_quotes']} / {m['iv_quotes']} / {m['iv_divergence_count']}"], ["Dates / expiries / fitted date-expiry groups", f"{m['sample_dates']} / {m['expiry_count']} / {s['fit_count']}"], ["Matched parity pairs", m['parity']['matched_strike_groups']], ["Parity mean / RMSE / P95 absolute (points)", " / ".join(fmt(m['parity'][k]) for k in ('mean_residual','rmse','p95_absolute'))], ["Butterfly violations / constrained solver failures", f"{s['butterfly_violations']} / {s['constrained_fit_failures']}"], ["Calendar / negative forward-variance grid points", f"{s['calendar_violations']} / {s['negative_forward_variance']}"], ["Median of group median quote errors (different statistic)", s['repricing_median']], ["Median / P95 of date maximum quote errors", f"{fmt(s['median_date_max_relative_error'])} / {fmt(s['p95_date_max_relative_error'])}"]])
    text += "\nThe indicative median repricing target below 2% is not achieved on this expanded snapshot.\nZero classical butterfly violations on the tested grid is achieved; finite-grid tests are not a proof over all real strikes.\nThe 696 calendar crossings show that separate butterfly-constrained expiry fits do not ensure a globally arbitrage-free term structure.\nThe large date maxima make this surface unsuitable for unqualified production pricing.\nDivergent quotes are retained in [iv_divergences.csv](results/approach1/market/iv_divergences.csv), matched parity residuals in [parity_residuals.csv](results/approach1/market/parity_residuals.csv), and negative forward-variance locations in [metrics.json](results/approach1/market/metrics.json).\n\n### Calibration table across all fitted dates and expiries\n\n"
    text += table(["Date", "Expiry", "Quotes", "a,b,rho,m,eta", "Initial a,b,rho,m,eta", "MSE", "Seconds", "Max relative error", "Butterfly"], [[v['date'],v['expiry'],v['n_quotes'],', '.join(fmt(x,4) for x in v['parameters']),', '.join(fmt(x,4) for x in v['initial_parameters']),v['objective'],v['fit_seconds'],v['repricing_max_relative_error'],v['butterfly_violations']] for v in m['svi']['per_group'].values()])
    text += r"""
## Differentiable calibration, ablation and robustness

Torch SVI uses Adam and smooth reparameterizations (softplus for positive parameters, tanh for correlation), the same total-variance targets and the same initial parameters as bounded SciPy least squares.
Both objective histories, final objectives, elapsed times and target crossings at MSE $10^{-7}$ are saved.
SciPy objective evaluations include numerical-Jacobian calls and are not identical to optimizer iterations; the report labels them as evaluations.
The neural surface is a two-hidden-layer MLP in $(k,T)$ with positive softplus volatility output.
Its loss is the unscaled mean squared option-price error plus $\lambda_b E[\max(0,-g)^2]+\lambda_t E[\max(0,-\partial_Tw)^2]$ on the documented grid.
The four predeclared penalty settings use $\lambda_b,\lambda_t\in\{0,10^8\}$ with 250 Adam epochs.
Large penalty weights reflect index-point price units; they were not chosen from held-out robustness performance.
The neural fit pools dates, with no date input or independent daily neural model, so it estimates a pooled surface and cannot capture all date-specific shifts.
Per-date checks describe that pooled function at each observed maturity set.
This modeling limitation helps explain why the classical expiry fits outperform the pooled neural model on the shared holdout.

"""
    text += table(["Penalty b,t", "Median relative error", "P95", "Butterfly", "Calendar", "Final price MSE", "Seconds"], [[key,v['median_relative_price_error'],v['p95_relative_price_error'],v['arbitrage']['butterfly_violations'],v['arbitrage']['calendar_violations'],v['final_loss']['price_loss'],v['fit_seconds']] for key,v in n['neural_ablations'].items()])
    text += f"\nA seeded random split removes {d['heldout_rows']} of {d['train_rows']+d['heldout_rows']} usable IV quotes (30%, rounded), leaving {d['train_rows']} for training.\nBoth methods are evaluated on the identical {d['common_evaluation_rows']} quote IDs, using the market-price denominator.\nThe other {len(d['skipped_quote_ids'])} held-out quotes lack a supported SVI training group and are listed explicitly, so these results are conditional on common support.\nThe common-set SHA-256 is `{d['evaluation_fingerprint']}`.\n\n"
    text += table(["Method", "Common rows", "Median relative error", "P95"], [["SVI refit",d['common_evaluation_rows'],d['svi_median_relative_error'],d['svi_p95_relative_error']],["Neural extrapolation",d['common_evaluation_rows'],d['neural_median_relative_error'],d['neural_p95_relative_error']]])
    text += "\n### Optimizer comparison on the shared calibration groups\n\n"
    text += table(["Date/expiry", "SciPy MSE", "Torch MSE", "SciPy seconds", "Torch seconds", "SciPy evaluations to target", "Torch updates to target"], [[v['group'],v['scipy_objective'],v['torch_objective'],v['scipy_seconds'],v['torch_seconds'],v['scipy_objective_evaluations_to_target'],v['torch_updates_to_target']] for v in n['convergence']])
    text += "\nThe full Torch-SVI and neural arbitrage checks, including violation locations, remain in [differentiable metrics](results/approach2/differentiable/metrics.json).\nFigures: [classical surface](results/approach1/market/svi_surface.html), [arbitrage diagnostics](results/approach1/market/arbitrage_diagnostics.html), [objective profiles](results/approach2/differentiable/objective_profiles.html), [neural ablation](results/approach2/differentiable/neural_ablation.html) and [comparable holdout ranking](results/comparison.html).\nSeed 42 governs quote dropout and Torch initialization; seeded CPU floating-point results can vary slightly by platform.\n"
    return text


def q2_report():
    runs = {contract:{a:read(f"questions/q2/results/{a}/{contract}/metrics.json") for a in ('approach1','approach2')} for contract in ('if0','cu0')}
    if any(r['approach2']['params'].get('epochs') != 100 for r in runs.values()):
        raise ValueError("Wait for the complete Q2B validation-stopping rerun before writing reports")
    text = r"""# Q2. Monte Carlo pricing and transaction-cost hedging

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

"""
    text += table(["Contract", "S0", "Annual sigma", "Annual mu", "Log drift"], [[c.upper(),r['approach1']['params']['calibration']['spot'],r['approach1']['params']['calibration']['vol'],r['approach1']['params']['calibration']['level_drift'],r['approach1']['params']['calibration']['log_drift']] for c,r in runs.items()])
    text += r"""
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

"""
    rows=[]
    for c,r in runs.items():
        for engine,case in [('NumPy headline',r['approach1']['metrics']['european']),('NumPy independent validation',r['approach1']['metrics']['european']['validation']),('Torch headline',r['approach2']['metrics']['pricing']['european'])]:
            rows.append([c.upper(),engine,case['price'],case['standard_error'],case['black_scholes'],case.get('parity_z',case.get('validation_z'))])
    text += table(["Contract", "Run", "Price", "SE", "Black-Scholes", "z"],rows)
    text += "\nAll displayed European checks satisfy $|z|\\le3$.\n\n"
    text += table(["Contract", "Engine", "Asian price / SE", "Up-and-out price / SE", "Digital price / SE"], [[c.upper(),engine,*[f"{fmt(m[k]['price'])} / {fmt(m[k]['standard_error'])}" for k in ('asian','up_and_out','digital')]] for c,r in runs.items() for engine,m in [('NumPy',r['approach1']['metrics']),('Torch',r['approach2']['metrics']['pricing'])]])
    text += r"""
## Variance reduction, Greeks and convergence

Antithetic estimates average the discounted payoffs from $Z$ and $-Z$ before computing their standard errors.
At the same total simulated path count, the variance reduction ratio is $SE_{plain}^2/SE_{method}^2$.
For the Asian control, $\hat C=\bar X-\hat\beta(\bar Y-EY)$, with $\hat\beta=\widehat{\mathrm{Cov}}(X,Y)/\widehat{\mathrm{Var}}(Y)$ computed using consistent sample normalization.
Here $Y$ is the discounted geometric-Asian payoff.
For $t_i=i\Delta t$, geometric log mean is $a=\log S_0+(r-\sigma^2/2)\Delta t(m+1)/2$ and variance is $v=\sigma^2\Delta t(m+1)(2m+1)/(6m)$.
The closed form is $EY=e^{-rT}[e^{a+v/2}\Phi(d_1)-K\Phi(d_2)]$, where $d_2=(a-\log K)/\sqrt v$ and $d_1=d_2+\sqrt v$.
The estimated control coefficient has finite-sample uncertainty; this same-sample fit is not an exact unbiased oracle coefficient.

"""
    text += table(["Contract", "Payoff", "Antithetic variance ratio", "Geometric-CV variance ratio"], [[c.upper(),p,(r['approach1']['metrics']['estimators']['plain'][p]['standard_error']/r['approach1']['metrics']['estimators']['antithetic'][p]['standard_error'])**2,(r['approach1']['metrics']['estimators']['plain'][p]['standard_error']/r['approach1']['metrics']['estimators']['geometric_cv_asian']['standard_error'])**2 if p=='asian' else 'n/a'] for c,r in runs.items() for p in ('european','asian','up_and_out','digital')])
    text += r"""
For European pathwise delta, the path contribution is $e^{-rT}1_{S_T>K}S_T/S_0$; vega is $e^{-rT}1_{S_T>K}S_T(\sqrt T Z-\sigma T)$.
For the Asian call, replace terminal derivatives by the average of each monitored state's derivative and use the Asian in-the-money indicator.
Central finite differences use common random numbers, $[P(x+h)-P(x-h)]/(2h)$.
Spot bumps are $0.1S_0,0.01S_0,0.001S_0$; vega bumps are absolute volatility increments 0.005, 0.002 and 0.001, because volatility and spot have different units.
Pathwise estimates are reported for continuous call payoffs; no invalid pathwise derivative is claimed for the discontinuous digital or barrier.

"""
    rows=[]
    for c,r in runs.items():
        g=r['approach1']['metrics']['greeks']
        for greek in ('delta','vega'):
            for payoff in ('european','asian'):
                pw=g['pathwise'][payoff][greek]
                rows.append([c.upper(),payoff,greek,'pathwise',pw['value'],pw['standard_error'],g['analytic_european'][greek] if payoff=='european' else 'n/a'])
                for bump,values in g['finite_difference'][greek].items():
                    v=values[payoff]
                    rows.append([c.upper(),payoff,greek,bump,v['value'],v['standard_error'],g['analytic_european'][greek] if payoff=='european' else 'n/a'])
    text += table(["Contract", "Payoff", "Greek", "Method / bump", "Estimate", "SE", "Analytic vanilla"],rows)
    text += "\nLarge spot bumps smooth the payoff kink and introduce visible truncation bias, especially for the Asian delta.\nThe smaller common-random-number bumps converge to the pathwise estimates within the displayed Monte Carlo errors; small bumps do not eliminate sampling uncertainty.\nThe Asian has no claimed analytic Greek benchmark.\n\n"
    text += table(["Contract", "RMSE series", "Log-log slope", "Fitted RMSE at N=1000"],[[c.upper(),key,v['slope'],v['factor_at_1000_paths']] for c,r in runs.items() for key,v in r['approach1']['metrics']['rmse']['slopes'].items()])
    text += "\nThe path-count grid is 100, 300, 1,000, 3,000, 10,000 and 30,000, with 4,096, 1,024, 512, 256, 64 and 32 independent replications respectively.\nThe Asian reference is an independent one-million-pair antithetic plus geometric-control estimate, with the coefficient and standard error computed on independent pair averages.\nIts finite uncertainty is retained below rather than treating an ordinary noisy MC estimate as exact truth.\nSlopes near -0.5 support the expected Monte Carlo order over this finite range; they do not constitute an asymptotic proof.\n\n"
    text += table(["Contract", "Asian reference", "Reference SE", "Scalar seconds", "Vectorized seconds", "Speedup"],[[c.upper(),r['approach1']['metrics']['rmse']['asian_reference']['price'],r['approach1']['metrics']['rmse']['asian_reference']['standard_error'],r['approach1']['metrics']['performance']['scalar_seconds'],r['approach1']['metrics']['performance']['vectorized_seconds'],r['approach1']['metrics']['performance']['speedup']] for c,r in runs.items()])
    text += "\nThe timing comparison uses 1,024 paths on the same daily grid, and cProfile identifies the scalar normal-draw/exponential loop as the hot path.\nMachine-dependent timings are evidence of this run, rather than fixed performance guarantees.\nProfiles: [IF0](results/approach1/if0/performance_profile.txt), [CU0](results/approach1/cu0/performance_profile.txt).\n\n"
    text += r"""## Deep hedging protocol and held-out results

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

"""
    rows=[]
    for c,r in runs.items():
        for key,v in r['approach2']['metrics']['hedging'].items():
            h=r['approach2']['history']['hedging'][key]
            rows.append([c.upper(),v['rebalance_days'],v['cost_bps'],v['deep']['cvar95'],v['bs']['cvar95'],v['deep']['mean_pnl'],v['bs']['mean_pnl'],v['deep']['pnl_variance'],v['bs']['pnl_variance'],f"{h['epochs_run']} / {h['best_epoch']}",h['stopping_reason']])
    text += table(["Contract", "Days", "Cost bp", "Learned CVaR", "BS CVaR", "Learned mean", "BS mean", "Learned variance", "BS variance", "Epochs / best", "Stop"],rows)
    wins=sum(v['deep']['cvar95']<v['bs']['cvar95'] for r in runs.values() for v in r['approach2']['metrics']['hedging'].values())
    text += f"\nThe learned strategy has lower held-out CVaR in {wins} of 18 cases; no claim of universal outperformance is supported.\nTransaction costs penalize frequent position changes, so the interaction with rebalancing frequency matters more than a single headline score.\nOnly seed 42 is the primary experiment; robustness across training seeds and confidence intervals for CVaR differences remain limitations, not assignment-required results that have been silently assumed.\nSeeded CPU training uses two threads and can retain last-bit differences across platforms.\nFigures and validation histories: [NumPy IF0](results/approach1/if0/figures.html), [NumPy CU0](results/approach1/cu0/figures.html), [hedging IF0](results/approach2/if0/figures.html), [hedging CU0](results/approach2/cu0/figures.html) and [comparison](results/comparison.html).\n"
    return text


def q4_report():
    a=read('questions/q4/results/approach1/trade/metrics.json')['metrics']
    b=read('questions/q4/results/approach2/trade/metrics.json')['metrics']
    f=read('questions/q4/results/approach2/trade_future/metrics.json')['metrics']
    text=r"""# Q4. Chinese trade network analytics and prediction

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

"""
    text += table(["Year", "V", "Directed E", "Undirected E", "Directed density", "Undirected density", "Degree slope", "Assortativity", "Components", "Isolates", "MST diameter", "Louvain Q"],[[y,v['nodes'],v['directed_edges'],v['undirected_edges'],v['directed_density'],v['undirected_density'],v['degree_loglog_slope'],v['assortativity'],v['connected_components'],v['isolated_nodes'],v['mst']['diameter'],v['communities']['modularity']] for y,v in a['per_year'].items()])
    text += r"""
Louvain optimizes weighted modularity $Q=(2m)^{-1}\sum_{ij}[W_{ij}-\gamma k_i k_j/(2m)]1_{c_i=c_j}$, where $k_i$ is weighted degree and $m=\frac12\sum_{ij}W_{ij}$.
The primary resolution is one, with seeded sweeps at 0.5, 1 and 1.5.
PageRank uses directed trade weights, damping 0.85 and uniform teleportation: $p=0.85P^\top p+0.15\mathbf1/n$.
Weighted directed betweenness uses the same decreasing-trade distance convention; undirected weighted degree is the sum of reciprocal retained flows.
The United States and China are the top two PageRank nodes in 2014 and 2023, reflecting centrality within this selected network rather than a claim about the full world economy.

### 2023 resolution sensitivity

"""
    text += table(["Resolution", "Communities", "Modularity", "ARI vs region proxy", "NMI vs region proxy"],[[k,v['community_count'],v['modularity'],v['ari_vs_region_proxy'],v['nmi_vs_region_proxy']] for k,v in a['per_year']['2023']['resolution_sweep'].items()])
    text += "\n### Ranked 2023 centralities\n\n"
    text += table(["Metric", "Rank", "Country / original code label", "Value"],[[metric,row['rank'],row['name'],row['value']] for metric,rows in a['per_year']['2023']['centrality_rankings'].items() for row in rows])
    text += "\nFull country-named rankings and degree distributions for every year are retained in [classical metrics](results/approach1/trade/metrics.json).\nConsecutive community matrices retain their original row and column labels; Hungarian one-to-one matching removes arbitrary label permutations while preserving real splits and merges.\nChanged share counts nodes that remain unmatched after this matching, and ARI is independently label-invariant.\n\n"
    text += table(["Transition", "Changed share", "ARI", "Split previous labels", "Merged current labels", "Raw contingency matrix"],[[k,v['changed_share'],v['ari'],v['split_previous_labels'],v['merged_current_labels'],v['contingency']] for k,v in a['community_migration'].items()])
    text += "\nThe largest observed migration is 2014 to 2015; changes also occur in 2021 to 2022 and 2022 to 2023.\nThese are structural changes in detected sample communities, not identified causal breaks in trade policy.\nIn 2022 to 2023 the raw matrix preserves one previous community splitting into two and a corresponding merge, instead of collapsing both into a matched label.\n\n"
    text += r"""## Embeddings and corrected static edge benchmark

The weighted node2vec walk moves from previous node $t$ through current node $v$ to neighbor $x$ with weight $W_{vx}\alpha_{pq}(t,x)$, where $\alpha=1/p$ for returning to $t$, one for neighbors of $t$, and $1/q$ otherwise.
Skip-gram maximizes $\log\sigma(z_v^\top c_u)+\sum_{j=1}^5\log\sigma(-z_v^\top c_{n_j})$ using its own PyTorch implementation and uniform node negative sampling.
The bilinear link classifier is $s(u,v)=\sigma(z_u^\top Bz_v)$; binary cross entropy trains $B$ using training labels only.
The static 2023 graph has 91 undirected positive edges, split into 72 training, nine validation and ten test positives, with equal disjoint negative sampling in each split.
The split occurs before walks, embeddings, Louvain or baseline graph features are computed.
All validation and test positive edges are absent from the 72-edge training graph; exact pairs and graph fingerprints are saved.
We sweep $p,q\in\{0.5,1,2\}$ and dimensions $\{8,16,32,64\}$, selecting by validation AUC, then validation AP and deterministic parameter tie-breaks.
The final test labels are scored once for the selected model and are never used to select a dimension or walk parameters.
Common-neighbor, Adamic-Adar and preferential-attachment scores are all computed on that same training graph.

"""
    text += f"Selected static parameters: p={b['selection']['selected_p']}, q={b['selection']['selected_q']}, dimension={b['selection']['selected_dimension']}.\nThe historical full-graph/test-selected AUC is superseded by the corrected scores below.\n\n"
    text += table(["Static test method", "AUC", "Average precision"],[[k,v['auc'],v['average_precision']] for k,v in {'learned':b['learned'],**b['baselines']}.items()])
    text += "\n### Complete clustering agreement matrix (unique pairs)\n\n"
    text += table(["Label pair", "ARI", "NMI"],[[k,v['ari'],v['nmi']] for k,v in b['model_agreement']['pairs'].items()])
    text += r"""
## Future major-trade-link formation

The additional temporal task predicts $Y_{ij,t+1}=1$ when an undirected relation absent from the year-$t$ top-six graph appears in year $t+1$.
This is formation of a major retained trade relation, not the first occurrence of any positive raw bilateral trade and not a continuous dollar-flow forecast.
Train transitions are 2014 to 2015 through 2020 to 2021; validation is 2021 to 2022; the final test is 2022 to 2023.
The static 80/10/10 split remains a separate benchmark; the temporal task uses chronological splits to preserve forecasting order.
Each transition embeds only its forecast-year graph, with equal sampled negatives among absent relations that stay absent in the target year.
Embedding orientations are aligned by orthogonal Procrustes against the first training-year embedding using node identities, without future labels.
A shared bilinear matrix is trained on training transitions only; walk parameters and dimension are selected on validation only.
The fixed node universe is selected retrospectively from 2023, so the result is conditional on these countries rather than a fully prospective population forecast.

"""
    text += table(["Transition", "Train positive", "Train negative"],[[f"{v['feature_year']} to {v['target_year']}",v['positive_count'],v['negative_count']] for v in f['training_transitions']])
    text += f"\nValidation has {len(f['validation_sample']['positive'])} positive and {len(f['validation_sample']['negative'])} negative examples.\nThe final test has only {len(f['test_sample']['positive'])} positive and {len(f['test_sample']['negative'])} sampled negative examples, from {f['test_sample']['population_negative']} available nonformations.\nThis tiny holdout gives a very coarse and unstable AUC, so it cannot establish forecasting skill.\nSelected temporal parameters are p={f['selection']['p']}, q={f['selection']['q']}, dimension={f['selection']['dimension']}, with validation AUC {fmt(f['selection']['validation_auc'])}.\n\n"
    text += table(["Future test method", "AUC", "Average precision"],[[k,v['auc'],v['average_precision']] for k,v in {'learned':f['learned'],**f['baselines']}.items()])
    text += "\nBoth learned tasks miss the indicative AUC target of 0.75.\nThe static Adamic-Adar baseline exceeds the indicative 0.65 heuristic target, but the temporal benchmark does not.\nPoor final test performance is retained honestly and is not used to retune the experiment.\nAverage precision is measured on balanced case-control samples, so it does not estimate precision at the population's actual formation prevalence.\nThe region-proxy comparison does not fulfill a literal industry-ground-truth requirement.\nSeed 42 governs splits, walks, negative sampling, optimization and clustering; CPU arithmetic can vary slightly by platform.\nFigures: [annual network evolution](results/approach1/trade/network_evolution.html), [static prediction](results/approach2/trade/link_prediction.html), [future prediction](results/approach2/trade_future/future_links.html) and [separate task comparisons](results/comparison.html).\n"
    return text


TEAM_MEMBERS = [
    ("Shi Zhan", "A0333516J"),
    ("Shi Mingyang", "A0333319H"),
    ("Shi Luda", "A0333534J"),
    ("Zhang Zhining", "A0326815B"),
    ("Li Ke", "A0333306N"),
]

WORK_DIVISION = {
    "q1": {
        "group": "The group supplied the Q1 repository and authorized expanding the option snapshot to monthly daily chains, preserving the original snapshots and using a tenor-interpolated SHIBOR curve.",
        "responsibility": "The group is responsible for evaluating the zero-dividend carry approximation, interpreting parity and arbitrage diagnostics, and assessing the repricing and robustness results against the stated objectives.",
        "agent": "The coding agent integrated the expanded data, implemented and checked the rate conversion and past-fixing joins, amended classical and differentiable calibration, aligned the quote-drop comparison on identical held-out quotes, and generated the calibration tables, diagnostics, figures and regression checks.",
    },
    "q2": {
        "group": "The group supplied the Q2 repository for integration and requested a full requirements audit and repair while retaining the IF0/CU0 pricing and transaction-cost hedging study.",
        "responsibility": "The group is responsible for justifying the GBM approximation and continuous-contract calibration convention, interpreting estimator efficiency and Greek uncertainty, and assessing the economic meaning of the reported hedge P&L and CVaR.",
        "agent": "The coding agent corrected the headline and validation z-scores, covariance normalization, maturity grid and Asian-reference uncertainty, added validation-based hedge checkpoint selection and stopping, reran the pricing and hedging experiments, and generated comparison tables, profiles, figures and regression checks.",
    },
    "q4": {
        "group": "The group authorized future trade-link prediction alongside a separate static missing-edge benchmark and directed that country regions remain explicitly identified as geographical proxies for industry labels.",
        "responsibility": "The group is responsible for assessing the top-six major-link target, the retrospective country universe and the geographical proxy interpretation, and for drawing appropriately limited conclusions from the small temporal holdout.",
        "agent": "The coding agent corrected graph statistics and community migration, removed held-out edges before static graph features and embeddings, implemented validation-only model selection and chronological future-link prediction, and generated baseline comparisons, agreement matrices, figures and regression checks.",
    },
}

REVIEW_STATUS = """### Report preparation and review

The coding agent assembled the computational results and drafted the mathematical descriptions, tables and discussion from the saved experiment outputs.
The group retains responsibility for the mathematical specification, verification, interpretation and final report approval.
Final group verification and approval remain pending.

### Agent provenance and session evidence

OpenCode reached its provider quota; the user explicitly approved finishing these repairs in Codex, overriding the local agent requirement for this task.
This permission does not change the examination's approved-agent rule; instructor acceptance of the Codex-authored repairs remains unresolved.
Original Q1/Q4 summaries, genuine later OpenCode verification exports, recovered Q2 public implementation sessions and the public repair transcript are identified in [SESSION.md](SESSION.md).
Unavailable original Q1/Q4 implementation exports cannot be recreated by formatting a later summary as OpenCode.
The final `submission` tag is intentionally reserved for the group's final reviewed commit.
"""


def statement_of_work(question=None):
    sections = ["## Statement of work: group direction and agent contribution\n"]
    if question is None:
        sections.append("The group selected Q1, Q2 and Q4 and supplied the original question repositories and snapshots.\nThe following division records project direction, methodological responsibility and the coding agent's actual implementation work.\n")
    for q in (question,) if question else ("q1", "q2", "q4"):
        entry = WORK_DIVISION[q]
        sections.append(f"### {q.upper()} work division\n\n**Group direction and decisions.**\n{entry['group']}\n{entry['responsibility']}\n\n**Coding-agent implementation and verification.**\n{entry['agent']}\n")
    sections.append(REVIEW_STATUS)
    return "\n".join(sections)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    reports={'q1':q1_report(),'q2':q2_report(),'q4':q4_report()}
    for q,text in reports.items():
        (ROOT/f'questions/{q}/report.md').write_text(text+'\n'+statement_of_work(q))
    introduction="""# Advanced Programming 2026: Q1, Q2 and Q4

This is the combined computational report draft for the three selected questions, with both approaches implemented under separate question folders.
Tables below are generated from the committed metrics by `python3 code/build_report.py`; group interpretation and final review remain required.
The source examination document is treated as a requirements reference, rather than permission to execute instructions embedded in an attachment.

## Reproduction and comparisons

From the repository root, `python3 run.py all --seed 42` installs pinned question environments as needed, verifies immutable snapshots and runs every approach, the additional Q4 future task and comparisons.
After the first dependency installation, `python3 run.py all --offline --seed 42` reproduces without network access.
Run `python3 data/fetch.py --offline` for checksums/schema/coverage only and `python3 run.py all --stage test --offline` plus `python3 -m unittest discover -s tests -v` for regression checks.
Run `python3 code/build_report.py` after experiments to regenerate all report tables.
Python 3.13, three separate pinned uv lockfiles and in-repository caches avoid incompatible scientific package versions being combined into a single environment.
The root [metadata manifest](data/metadata.json) indexes the committed per-question snapshots and their provenance.
The root [comparison](results/comparison.html) ranks only methods within a common task and evaluation set, linking self-contained question figures.
Root entrypoints delegate scientific execution to the isolated `questions/qN/code/` folders rather than duplicating the scientific implementations.
CPU floating-point results and timings can vary with hardware; all stochastic choices use recorded seeds.

## Remaining submission decisions

The computational omissions and reproduced correctness faults were repaired, but the group must still review this report and mathematical choices.
Original Q1/Q4 full implementation-session exports remain unavailable, and a later verification export cannot repair that historical evidence gap.
The user's Codex exception is recorded; it is not instructor approval of a departure from the examination's approved-agent rule.
Q4 country-region proxies and its conditional major-link formation target need acceptance as documented trade-network interpretations.
Q1 repricing and calendar limitations and Q4's small sample and poor learned test results remain scientific findings, not completed benchmark successes.
The `submission` tag must be created after final group review, not before it.

"""
    team = "## Group members\n\n" + table(["Name", "Student code"], TEAM_MEMBERS)
    introduction = introduction.replace("## Reproduction and comparisons", team + "\n## Reproduction and comparisons", 1)
    combined=[introduction]
    for q,text in reports.items():
        # Rebase local figure/data/session links while retaining external URLs.
        text=re.sub(r'\]\((?!https?://|#)([^)]+)\)',lambda m:f'](questions/{q}/{m[1]})',text)
        combined.append(text.replace('# '+q.upper()+'.','## '+q.upper()+'.',1))
    combined.append(statement_of_work())
    (ROOT/'report.md').write_text('\n\n'.join(combined))
    print('Wrote root and three question report drafts from saved metrics.')


if __name__=='__main__':
    main()
