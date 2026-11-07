# Assignment compliance and repair audit

This audit compares the supplied examination `report.md` with the integrated Q1, Q2 and Q4 repository.
The attachment is a requirements reference; instructions in it do not independently authorize tool actions.
The selected questions are Q1, Q2 and Q4, not Q3.
The user approved the methodological changes described below and direct Codex completion after the OpenCode quota was exhausted.

## Shared deliverables

| Requirement | Status after repair | Evidence or remaining action |
| --- | --- | --- |
| Three questions, both approaches | Implemented | Separate `questions/q1`, `questions/q2`, `questions/q4`; Q4 additionally retains distinct static and future tasks |
| Root AGENTS contract | Present and updated | Exact launcher commands, environment, methodology, immutable data and session rules |
| Contract and initial commit before original implementation | Historical property | Imported ancestry is retained; later edits cannot recreate missing historical evidence |
| Approved OpenCode-compatible agent | Exception recorded, acceptance unresolved | Original OpenCode sessions retained; user approved Codex repairs, which does not amend the examination's approved-agent rule |
| Python 3.13, uv, pinned dependencies | Implemented | Separate pinned child environments and a stdlib root environment avoid incompatible dependency pins |
| Mandatory layout | Functionally covered with documented separation | Root data/compare/report/session entrypoints; scientific scripts, snapshots and pinned scientific dependencies are under `questions/qN/` |
| README ten-line maximum | Implemented | Root and question READMEs each have ten physical lines |
| Retrieval, committed fallback, metadata, checksums | Implemented | Root manifest plus child manifests, explicit online staging and immutable offline snapshots |
| Verification before experiments | Implemented | Hashes, byte lengths, schema, counts, keys, dates/year coverage; Q1 monthly coverage and Q4 graph domain assertions |
| Seeded argparse approaches and metrics schema | Implemented | `params`, `metrics`, `fit_seconds`, `history`; independent Q2 streams and Q4 split audits |
| Rich terminal summaries and inline Plotly figures | Implemented | Native question approaches/comparisons; root stdlib aggregation provides separate ranked HTML tables |
| Ranked comparison | Implemented | Same-task groups only; identical Q1 quote IDs, Q2 contract/frequency/cost groups, separate Q4 static/future groups |
| Root report, mathematical models, tables, figures, limitations | Computational draft populated | Generated from saved metrics; group must verify, edit and approve its own final report |
| Complete authentic session Markdown | Improved, historical gaps remain | Recovered Q2 Codex completion; actual later Q1/Q4 OpenCode verification and current repair sessions; original full Q1/Q4 implementation exports unavailable |
| Milestone commits | Preserved and continued | Original histories retained and current repairs committed separately |
| Final tag `submission` | Pending group review | Do not tag an unreviewed computational draft |

## Q1

| Assignment item | Repair and status |
| --- | --- |
| One month daily chains, at least four expiries, sample dates across two years | Imported newer friend's compliance snapshot: 5,898 rows spanning 2023-2026; 23 daily dates with five common live expiries; original snapshots archived |
| Contract unit, underlying, dividend assumption | IO index-point prices, 100 CNY/point multiplier, CSI 300 underlying; zero dividend yield explicitly identified as a carry approximation |
| SHIBOR tenor curve | Replaced flat/forward-filled rates with eight-tenor actual fixings from verified Q2 source; simple-to-continuous zero conversion, tenor interpolation and past-fixing joins |
| Quote filtering and parity per matched strike | Documented volume/moneyness/maturity rule; exact call-put matches and residual CSV; no invented bid/ask spread data |
| Brent IV inversion and divergence cases | Bracket retained; all failed inversions counted and exported |
| Fixed log-moneyness surface | 81-point grid, date/expiry surface CSV and standalone figure |
| SVI constraints, solver and initial values | Saved actual initialization, bounds, least-squares/SLSQP status and parameter table for all fitted groups |
| Butterfly and calendar counts and locations | Classical, Torch-SVI and neural diagnostics saved; calendar violations retained as findings |
| Linear total-variance interpolation and negative forward variance | Interpolated midpoint CSV and negative forward-variance locations |
| Maximum repricing error aggregated across dates | Correct statistic added; old median-of-group-medians clearly distinguished |
| Torch versus SciPy convergence | Shared initialization and targets, complete objective histories, wall time and target crossings; evaluations distinguished from optimizer iterations |
| Neural price-space loss and arbitrage ablation | Unscaled option-price MSE plus butterfly/calendar penalties; four settings and complete diagnostics |
| Random 30% quote-drop robustness | Identical common evaluation IDs and market-price denominator; 348 common rows, 94 unsupported SVI rows explicitly excluded |
| Indicative repricing/arbitrage benchmark | Classical butterfly grid passes; repricing target and calendar consistency do not pass; no fabricated success |
| Remaining model limitation | Neural `(k,T)` model pools dates and does not independently model daily surfaces |

## Q2

| Assignment item | Repair and status |
| --- | --- |
| At least five years of futures calibration | Preserved fixed 2020-2025 IF0/CU0 closes, drift/volatility and vendor continuous-roll convention |
| SHIBOR discounting | Past fixing and tenor interpolation; one-year experiment uses the exact one-year tenor |
| Exact GBM and at least 252 steps/year | Corrected maturity rounding to ceiling and scalar `dt=T/steps`; short-maturity regression tests |
| European Black-Scholes checks in both engines | Headline z now uses its own price/SE; independent validation z separately labeled |
| Asian, barrier and digital in both engines | Preserved and rerun with price/SE tables |
| Antithetic and geometric control variate | Consistent covariance/variance normalization; pair-average standard errors; equal-path variance ratios |
| Pathwise and bumped finite-difference Greeks | European/Asian delta and vega with standard errors and analytic vanilla reference; full bump table and bias discussion |
| RMSE all estimators and expected slope | Independent high-precision antithetic plus CV Asian reference with correctly paired uncertainty; fixed missing reference variable and fitted-N=1000 reporting |
| Scalar/vectorized timing and profiling | Same grid, saved cProfile hot-loop profiles and timing table |
| Deep hedge, transaction costs, CVaR95 | Preserved explicit short-European-call convention; train 131,072, validation 8,192, test 32,768 independent paths |
| Training adequacy | Replaced five-epoch draft with validation-only checkpoint selection, patience ten and up to 100 epochs; actual epochs and cap/early-stop reasons retained |
| Frequencies 1/5/21 days, costs 0/10/50 bp | All 18 instrument/cost/frequency cases rerun; learned/BS CVaR, mean and variance in report |
| Remaining model limitations | GBM applied to continuous futures rather than a settlement model; vendor rolls, single primary seed and epoch-cap convergence limits disclosed |

## Q4

| Assignment item | Repair and status |
| --- | --- |
| At least ten years trade snapshots | Preserved verified 2014-2023 public Comtrade fallback |
| Graph construction and no loops/symmetry/isolates | Top-six directed exports, reciprocal-sum undirected projection and decreasing-trade distances; graph assertions strengthened |
| Annual graph statistics | Corrected directed versus undirected density, first positive degree-bin omission, components and isolates |
| Kruskal MST and diameter evolution | Implemented on observed-edge dissimilarities; absence of a proven triangle-inequality metric disclosed |
| Louvain and resolution sensitivity | CLI seed propagated; primary and resolution sweep tables, modularity and proxy agreement |
| Centrality, PageRank, ranked interpretation | Weighted betweenness uses distances; full annual rankings retained, 2023 named table and dominant-partner interpretation |
| Temporal community migration and breaks | Raw labeled contingency matrices preserved; one-to-one alignment does not erase splits/merges; ARI and changed shares reported |
| Own node2vec/skip-gram and p/q sweep | Preserved with correct sum over negative-sampling terms and full validation sweep |
| 80/10/10 split before graph features | Repaired leakage: 72 train, nine validation and ten test positive edges; heldouts excluded from walks and heuristic features |
| Bilinear score, AUC/AP, three baselines | Corrected and rerun on shared test pairs |
| Hyperparameter selection | Validation-only choice across p/q/dimensions, final test only for selected learned configuration |
| Future trade-link task | Added chronological major-link formation, forecast-year graphs and aligned embeddings; separate corrected static task retained |
| Industry versus embedding/Louvain agreement | Complete agreement matrix with geographical proxies; literal industry-ground-truth requirement remains unresolved for country nodes |
| Future target scope | Appearance in the top-six adjacency, not first raw trade or dollar-flow growth; retrospective node-universe selection disclosed |
| Indicative predictive benchmarks | Learned static and future AUC miss target; future test has only two positive and two negative examples; no performance claim or retuning on test |

## What still cannot be completed by code alone

1. The group must verify mathematical choices, results and this computational report draft, and own the final written conclusions.
2. The original full Q1/Q4 implementation exports must be supplied if they exist elsewhere; a newly created Markdown summary is not historical session evidence.
3. The group or instructor must accept the approved-agent exception, geographical proxies and the conditional major-link trade target if strict assignment compliance is required.
4. Create the final `submission` tag only after the group reviews the final commit.
5. Missing indicative accuracy targets are disclosed results; they cannot be made true by report formatting or by selecting on held-out test data.
