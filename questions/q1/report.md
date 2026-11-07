# Q1. Implied volatility surface

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

| Diagnostic | Result |
| --- | --- |
| Filtered / successful IV / divergences | 1496 / 1473 / 23 |
| Dates / expiries / fitted date-expiry groups | 62 / 12 / 86 |
| Matched parity pairs | 454 |
| Parity mean / RMSE / P95 absolute (points) | 1.7439 / 9.8791 / 18.383 |
| Butterfly violations / constrained solver failures | 0 / 0 |
| Calendar / negative forward-variance grid points | 696 / 696 |
| Median of group median quote errors (different statistic) | 0.029624 |
| Median / P95 of date maximum quote errors | 0.379 / 2.4674 |

The indicative median repricing target below 2% is not achieved on this expanded snapshot.
Zero classical butterfly violations on the tested grid is achieved; finite-grid tests are not a proof over all real strikes.
The 696 calendar crossings show that separate butterfly-constrained expiry fits do not ensure a globally arbitrage-free term structure.
The large date maxima make this surface unsuitable for unqualified production pricing.
Divergent quotes are retained in [iv_divergences.csv](results/approach1/market/iv_divergences.csv), matched parity residuals in [parity_residuals.csv](results/approach1/market/parity_residuals.csv), and negative forward-variance locations in [metrics.json](results/approach1/market/metrics.json).

### Calibration table across all fitted dates and expiries

| Date | Expiry | Quotes | a,b,rho,m,eta | Initial a,b,rho,m,eta | MSE | Seconds | Max relative error | Butterfly |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-07-28 | 2023-10-20 | 5 | 1.991e-39, 0.004685, 0.999, -0.2817, 0.8712 | 0.005347, 0.2, 0, 0.03383, 0.1 | 6.9943e-09 | 0.036988 | 0.017072 | 0 |
| 2023-10-23 | 2023-11-17 | 25 | 9.639e-34, 0.03205, -0.005004, -0.01396, 0.07869 | 0.002598, 0.2, 0, -0.00142, 0.1 | 1.365e-08 | 0.0069856 | 0.33306 | 0 |
| 2023-10-23 | 2023-12-15 | 24 | 0.005082, 0.004491, 0.7688, -0.07186, 0.0646 | 0.005118, 0.2, 0, -0.003117, 0.1 | 3.1829e-07 | 0.059492 | 0.36753 | 0 |
| 2023-10-23 | 2024-01-19 | 6 | 0.007243, 0.05433, 0.6947, 0.06371, 0.0001 | 0.007898, 0.2, 0, 0.001754, 0.1 | 1.7479e-08 | 0.010012 | 0.018304 | 0 |
| 2023-10-23 | 2024-03-15 | 11 | 0.001694, 0.1026, 0.6622, 0.1198, 0.1375 | 0.01224, 0.2, 0, -0.002009, 0.1 | 4.9631e-08 | 0.0086975 | 0.025126 | 0 |
| 2023-10-23 | 2024-06-21 | 7 | 0.01017, 0.03952, 0.4654, 0.5315, 0.0001 | 0.02074, 0.2, 0, -0.03773, 0.1 | 7.0511e-07 | 0.0054801 | 0.065821 | 0 |
| 2023-10-23 | 2024-09-20 | 13 | 0.02306, 0.008134, -0.1916, -0.7747, 0.0001064 | 0.0254, 0.2, 0, -0.0009872, 0.1 | 6.3083e-06 | 0.0046445 | 0.14117 | 0 |
| 2023-10-24 | 2023-11-17 | 25 | 3.534e-32, 0.02724, -0.03239, -0.01547, 0.08075 | 0.002275, 0.2, 0, -0.005096, 0.1 | 1.9153e-09 | 0.0072432 | 0.25997 | 0 |
| 2023-10-24 | 2023-12-15 | 23 | 2.157e-34, 0.04295, 0.1536, 0.0002067, 0.1058 | 0.004531, 0.2, 0, -0.006771, 0.1 | 8.9891e-09 | 0.0074815 | 0.045048 | 0 |
| 2023-10-24 | 2024-03-15 | 9 | 0.01084, 0.0006503, 0.1083, -1.147, 0.008146 | 0.01104, 0.2, 0, -0.005693, 0.1 | 4.7894e-07 | 0.058633 | 0.098424 | 0 |
| 2023-10-24 | 2024-06-21 | 7 | 0.01632, 0.0356, -0.3014, 0.02387, 0.0001 | 0.0167, 0.2, 0, -0.01243, 0.1 | 4.4979e-07 | 0.0038133 | 0.049406 | 0 |
| 2023-10-25 | 2023-11-17 | 25 | 0.001348, 0.01374, -0.4064, -0.02607, 0.02561 | 0.001707, 0.2, 0, 0.004267, 0.1 | 7.3315e-09 | 0.01018 | 0.15842 | 0 |
| 2023-10-25 | 2023-12-15 | 22 | 0.002476, 0.02716, 0.288, 0.01435, 0.05534 | 0.003966, 0.2, 0, 0.002608, 0.1 | 2.7232e-09 | 0.009729 | 0.029552 | 0 |
| 2023-10-25 | 2024-03-15 | 8 | 0.01027, 0.008271, -0.1878, -0.04169, 0.0001 | 0.01036, 0.2, 0, -0.02512, 0.1 | 7.7079e-09 | 0.0053947 | 0.0393 | 0 |
| 2023-10-26 | 2023-11-17 | 24 | 3.742e-31, 0.01798, 0.001214, 0.00275, 0.0831 | 0.001526, 0.2, 0, 0.001618, 0.1 | 7.1456e-09 | 0.008288 | 0.29502 | 0 |
| 2023-10-26 | 2023-12-15 | 22 | 2.452e-34, 0.03759, -0.1756, -0.03072, 0.09655 | 0.003637, 0.2, 0, -9.424e-05, 0.1 | 1.4517e-08 | 0.0097981 | 0.27644 | 0 |
| 2023-10-26 | 2024-03-15 | 5 | 0.008016, 0.02787, 0.9584, 0.07787, 0.1325 | 0.009841, 0.2, 0, 0.04222, 0.1 | 2.4918e-08 | 0.017731 | 0.018382 | 0 |
| 2023-10-27 | 2023-11-17 | 23 | 0.0009423, 0.01284, 0.1928, 0.0158, 0.01891 | 0.001229, 0.2, 0, 0.002134, 0.1 | 4.8774e-09 | 0.0078568 | 0.50413 | 0 |
| 2023-10-27 | 2023-12-15 | 22 | 0.002792, 0.01983, 0.5843, 0.02958, 0.02374 | 0.003202, 0.2, 0, 0.0004182, 0.1 | 1.5894e-08 | 0.0050577 | 0.13224 | 0 |
| 2023-10-27 | 2024-01-19 | 7 | 0.0008592, 0.004639, -0.7269, 0.5289, 0.0001001 | 0.004587, 0.2, 0, -0.03752, 0.1 | 4.6375e-07 | 0.005354 | 0.087301 | 0 |
| 2023-10-27 | 2024-03-15 | 12 | 0.009062, 0.05877, 0.9676, 0.06391, 0.0001 | 0.0088, 0.2, 0, 0.001233, 0.1 | 1.6749e-07 | 0.010485 | 0.10965 | 0 |
| 2023-10-27 | 2024-06-21 | 9 | 0.01457, 0.02545, -0.3408, 0.02784, 0.0001 | 0.01478, 0.2, 0, -0.005515, 0.1 | 1.1902e-07 | 0.0044003 | 0.055845 | 0 |
| 2023-10-30 | 2023-11-17 | 25 | 5.617e-37, 0.02102, 0.3263, 0.03765, 0.05064 | 0.001106, 0.2, 0, -0.003628, 0.1 | 1.413e-08 | 0.0075844 | 0.68937 | 0 |
| 2023-10-30 | 2023-12-15 | 22 | 0.00232, 0.02244, 0.5523, 0.03082, 0.0375 | 0.003032, 0.2, 0, 0.001619, 0.1 | 2.5157e-08 | 0.0062109 | 0.10048 | 0 |
| 2023-10-30 | 2024-03-15 | 8 | 0.006943, 0.0322, 0.09607, -0.03249, 0.03771 | 0.008241, 0.2, 0, -0.004577, 0.1 | 1.6773e-07 | 0.01388 | 0.047643 | 0 |
| 2023-10-31 | 2023-11-17 | 22 | 5.232e-34, 0.01685, 0.2184, 0.01818, 0.05944 | 0.001029, 0.2, 0, -0.0004608, 0.1 | 3.5784e-09 | 0.0060947 | 0.379 | 0 |
| 2023-10-31 | 2023-12-15 | 21 | 0.000329, 0.04646, 0.7519, 0.08854, 0.08931 | 0.003059, 0.2, 0, -0.00216, 0.1 | 2.0153e-08 | 0.0066171 | 0.10427 | 0 |
| 2023-10-31 | 2024-03-15 | 8 | 0.008408, 0.0389, -0.5799, -0.07627, 0.0001 | 0.008898, 0.2, 0, -0.001394, 0.1 | 6.0189e-08 | 0.034568 | 0.064325 | 0 |
| 2023-11-01 | 2023-11-17 | 23 | 3.583e-36, 0.01802, 0.2254, 0.02031, 0.05003 | 0.000955, 0.2, 0, 2.117e-05, 0.1 | 5.5192e-09 | 0.0070979 | 0.4442 | 0 |
| 2023-11-01 | 2023-12-15 | 21 | 0.002732, 0.01369, 0.4676, 0.01364, 0.01379 | 0.002934, 0.2, 0, -0.001679, 0.1 | 8.242e-09 | 0.0075686 | 0.13488 | 0 |
| 2023-11-01 | 2024-03-15 | 7 | 0.000629, 0.08477, -0.5727, -0.1111, 0.117 | 0.008577, 0.2, 0, 0.01277, 0.1 | 5.1697e-08 | 0.18428 | 0.041157 | 0 |
| 2023-11-02 | 2023-11-17 | 23 | 0.0003997, 0.01413, 0.3143, 0.03267, 0.02566 | 0.0008006, 0.2, 0, 0.004998, 0.1 | 9.3919e-09 | 0.0062371 | 1.2591 | 0 |
| 2023-11-02 | 2023-12-15 | 19 | 5.094e-31, 0.02752, 0.1006, 0.0006685, 0.09683 | 0.0027, 0.2, 0, 0.003115, 0.1 | 7.3998e-09 | 0.0078309 | 0.052801 | 0 |
| 2023-11-02 | 2024-03-15 | 5 | 0.007139, 0.03057, 0.9846, 0.1312, 0.1443 | 0.008878, 0.2, 0, 0.03124, 0.1 | 7.5664e-09 | 0.023197 | 0.011686 | 0 |
| 2023-11-03 | 2023-11-17 | 24 | 0.0001815, 0.01784, -0.03566, 0.01176, 0.02458 | 0.0007196, 0.2, 0, -0.003305, 0.1 | 8.8413e-08 | 0.0050187 | 2.7694 | 0 |
| 2023-11-03 | 2023-12-15 | 21 | 0.001263, 0.03484, 0.734, 0.06766, 0.05487 | 0.002534, 0.2, 0, 0.00869, 0.1 | 2.5965e-08 | 0.0046058 | 0.15486 | 0 |
| 2023-11-03 | 2024-03-15 | 5 | 0.008734, 0.06478, 0.9978, 0.07698, 0.02323 | 0.008844, 0.2, 0, 0.02291, 0.1 | 1.2039e-08 | 0.0086979 | 0.010321 | 0 |
| 2023-11-06 | 2023-11-17 | 25 | 7.977e-37, 0.01756, -0.4251, -0.03289, 0.04304 | 0.000718, 0.2, 0, -0.002681, 0.1 | 1.0891e-08 | 0.007444 | 0.62559 | 0 |
| 2023-11-06 | 2023-12-15 | 23 | 0.001668, 0.02175, 0.5228, 0.02793, 0.04394 | 0.002505, 0.2, 0, 0.00235, 0.1 | 1.8639e-08 | 0.0062847 | 0.22124 | 0 |
| 2023-11-06 | 2024-01-19 | 15 | 4.116e-22, 0.03591, -0.1447, -0.04851, 0.1394 | 0.004882, 0.2, 0, 0.006761, 0.1 | 6.6485e-08 | 0.019412 | 0.070599 | 0 |
| 2023-11-06 | 2024-03-15 | 9 | 0.006467, 0.08228, -0.9107, -0.3522, 0.0001001 | 0.008336, 0.2, 0, -0.004042, 0.1 | 1.7111e-07 | 0.30168 | 0.10821 | 0 |
| 2023-11-07 | 2023-11-17 | 23 | 0.0003549, 0.02274, -0.7242, -0.02516, 0.02094 | 0.0006052, 0.2, 0, 0.0009049, 0.1 | 5.1745e-08 | 0.010885 | 8.0188 | 0 |
| 2023-11-07 | 2023-12-15 | 23 | 0.002393, 0.01597, 0.6816, 0.03358, 0.006786 | 0.002491, 0.2, 0, -0.0009356, 0.1 | 3.7456e-08 | 0.0044089 | 0.33621 | 0 |
| 2023-11-07 | 2024-01-19 | 8 | 0.00514, 0.01949, 0.999, 0.05972, 0.0001 | 0.004649, 0.2, 0, 0.01717, 0.1 | 1.1102e-07 | 0.26142 | 0.14784 | 0 |
| 2023-11-07 | 2024-03-15 | 7 | 0.007869, 0.02667, -0.3832, -0.08855, 0.0001 | 0.008221, 0.2, 0, 0.01325, 0.1 | 4.5002e-08 | 0.046025 | 0.031951 | 0 |
| 2023-11-08 | 2023-11-17 | 21 | 2.339e-36, 0.01394, -0.09214, -0.002969, 0.03519 | 0.0005655, 0.2, 0, 0.003364, 0.1 | 9.411e-09 | 0.007218 | 0.63852 | 0 |
| 2023-11-08 | 2023-12-15 | 22 | 0.001124, 0.01844, -0.0111, -0.02569, 0.06609 | 0.002373, 0.2, 0, 0.001537, 0.1 | 1.6405e-08 | 0.0098714 | 0.065299 | 0 |
| 2023-11-08 | 2024-01-19 | 11 | 0.004194, 0.00847, 0.1657, -0.03593, 0.0002025 | 0.004311, 0.2, 0, 0.01284, 0.1 | 1.7473e-08 | 0.38362 | 0.072035 | 0 |
| 2023-11-08 | 2024-03-15 | 8 | 2.604e-25, 0.06784, -0.3868, -0.1044, 0.1234 | 0.007754, 0.2, 0, 0.01571, 0.1 | 6.3947e-08 | 0.010518 | 0.03057 | 0 |
| 2023-11-09 | 2023-11-17 | 21 | 2.684e-36, 0.01407, -0.01957, 0.003061, 0.0312 | 0.0005072, 0.2, 0, -0.003962, 0.1 | 1.0354e-08 | 0.0066035 | 0.99773 | 0 |
| 2023-11-09 | 2023-12-15 | 22 | 0.001937, 0.0152, 0.6012, 0.02605, 0.03855 | 0.002398, 0.2, 0, 0.00112, 0.1 | 5.9746e-09 | 0.005916 | 0.10924 | 0 |
| 2023-11-09 | 2024-01-19 | 5 | 0.004895, 0.01468, -0.4049, 0.002481, 0.0001 | 0.004986, 0.2, 0, 0.0459, 0.1 | 1.7456e-08 | 0.030862 | 0.041144 | 0 |
| 2023-11-09 | 2024-03-15 | 5 | 9.235e-18, 0.066, 0.729, 0.1423, 0.187 | 0.008636, 0.2, 0, 0.04195, 0.1 | 1.8675e-09 | 0.021488 | 0.0064692 | 0 |
| 2023-11-10 | 2023-11-17 | 21 | 7.733e-37, 0.01582, -0.3372, -0.0225, 0.02268 | 0.0004218, 0.2, 0, 0.00341, 0.1 | 4.5586e-09 | 0.0061497 | 0.44809 | 0 |
| 2023-11-10 | 2023-12-15 | 24 | 6.83e-33, 0.02376, 0.2222, 0.01292, 0.1019 | 0.002407, 0.2, 0, 0.001605, 0.1 | 4.7018e-09 | 0.0092775 | 0.11824 | 0 |
| 2023-11-10 | 2024-01-19 | 6 | 0.004919, 0.006842, 0.999, 0.02355, 0.01355 | 0.004985, 0.2, 0, 0.04004, 0.1 | 1.0334e-09 | 0.010568 | 0.019997 | 0 |
| 2023-11-10 | 2024-03-15 | 9 | 0.007649, 0.01668, 0.1357, -0.02358, 0.0001 | 0.007879, 0.2, 0, -0.004741, 0.1 | 1.7882e-09 | 0.012264 | 0.023941 | 0 |
| 2023-11-10 | 2024-06-21 | 5 | 0.01373, 0.02451, -0.4739, 0.01594, 0.0001 | 0.01391, 0.2, 0, 0.0158, 0.1 | 1.6795e-07 | 0.38387 | 0.037261 | 0 |
| 2023-11-10 | 2024-09-20 | 10 | 0.01862, 0.08199, 0.6657, 0.07807, 0.0001 | 0.01906, 0.2, 0, 0.009428, 0.1 | 1.1143e-06 | 0.012151 | 0.11647 | 0 |
| 2023-11-13 | 2023-12-15 | 23 | 0.001469, 0.02955, 0.8527, 0.09826, 0.05685 | 0.002155, 0.2, 0, -0.003219, 0.1 | 4.1975e-08 | 0.010047 | 0.34927 | 0 |
| 2023-11-13 | 2024-01-19 | 8 | 0.004963, 0, 0.9622, 0.2596, 0.06983 | 0.004698, 0.2, 0, 0.04223, 0.1 | 7.2652e-08 | 0.045352 | 0.15248 | 0 |
| 2023-11-14 | 2023-12-15 | 23 | 0.000846, 0.02754, 0.6039, 0.05649, 0.05583 | 0.002104, 0.2, 0, -0.003893, 0.1 | 4.4195e-09 | 0.005567 | 0.18204 | 0 |
| 2023-11-14 | 2024-03-15 | 6 | 0.006971, 0.01985, 0.1397, -0.03852, 0.0001 | 0.00723, 0.2, 0, -0.003614, 0.1 | 3.3173e-10 | 0.0037243 | 0.0033561 | 0 |
| 2023-11-15 | 2023-12-15 | 23 | 0.001796, 0.01365, 0.5774, 0.03579, 0.01589 | 0.002011, 0.2, 0, 0.003057, 0.1 | 6.8455e-09 | 0.0066657 | 0.26173 | 0 |
| 2023-11-15 | 2024-01-19 | 9 | 0.00379, 0.01212, -0.2483, -0.03188, 0.0001 | 0.003972, 0.2, 0, -0.006193, 0.1 | 6.1502e-09 | 0.0051557 | 0.030297 | 0 |
| 2023-11-15 | 2024-03-15 | 8 | 0.00582, 0.02473, 0.2262, -0.02584, 0.05884 | 0.007385, 0.2, 0, 0.01723, 0.1 | 1.4829e-09 | 0.005123 | 0.029699 | 0 |
| 2023-11-15 | 2024-06-21 | 8 | 0.01445, 1.482e-18, 0.7744, 0.006085, 0.1236 | 0.01279, 0.2, 0, 0.0237, 0.1 | 2.8318e-06 | 0.025635 | 0.17633 | 0 |
| 2023-11-16 | 2023-12-15 | 24 | 5.835e-35, 0.02137, 0.03835, 0.02304, 0.08269 | 0.001808, 0.2, 0, -0.001056, 0.1 | 2.6949e-08 | 0.010066 | 0.33848 | 0 |
| 2023-11-16 | 2024-01-19 | 8 | 0.0002027, 0.04384, -0.6721, -0.2605, 0.0001 | 0.003527, 0.2, 0, 0.02419, 0.1 | 3.6181e-08 | 0.0078178 | 0.059317 | 0 |
| 2023-11-16 | 2024-03-15 | 5 | 0.006098, 0.02127, 0.969, 0.05609, 0.1116 | 0.007363, 0.2, 0, 0.02701, 0.1 | 4.4993e-09 | 0.029721 | 0.01146 | 0 |
| 2023-11-17 | 2023-12-15 | 27 | 0.0007571, 0.03038, 0.6699, 0.04895, 0.03411 | 0.001596, 0.2, 0, 0.0001914, 0.1 | 4.2808e-08 | 0.0073201 | 0.62203 | 0 |
| 2023-11-17 | 2024-01-19 | 19 | 1.612e-27, 0.04027, -0.3885, -0.06039, 0.09694 | 0.00362, 0.2, 0, -0.002135, 0.1 | 8.1077e-09 | 0.0093298 | 0.044032 | 0 |
| 2023-11-17 | 2024-03-15 | 9 | 0.006243, 0.06288, -0.6898, -0.05407, 0.007969 | 0.006859, 0.2, 0, 0.01456, 0.1 | 1.7394e-08 | 0.036328 | 0.041189 | 0 |
| 2023-11-17 | 2024-09-20 | 7 | 1.19e-05, 0.01611, 0.849, -0.5468, 0.0001003 | 0.01354, 0.2, 0, 0.02837, 0.1 | 4.4846e-06 | 0.0072803 | 0.23369 | 0 |
| 2023-11-20 | 2023-12-15 | 26 | 0.0007493, 0.02464, 0.7406, 0.07289, 0.04454 | 0.001382, 0.2, 0, -0.001944, 0.1 | 4.3316e-08 | 0.0080523 | 0.4503 | 0 |
| 2023-11-20 | 2024-01-19 | 20 | 6.251e-29, 0.03174, -0.1242, -0.03559, 0.1022 | 0.003226, 0.2, 0, 0.002765, 0.1 | 2.562e-09 | 0.0085957 | 0.038465 | 0 |
| 2023-11-20 | 2024-03-15 | 6 | 1.251e-20, 0.01938, 0.999, 0.5833, 0.7732 | 0.006703, 0.2, 0, 0.01246, 0.1 | 1.5033e-07 | 0.090756 | 0.09059 | 0 |
| 2023-11-20 | 2024-06-21 | 6 | 0.01254, 0.02439, 0.3809, 0.0453, 0.0001 | 0.01216, 0.2, 0, 0.0056, 0.1 | 1.498e-06 | 0.056797 | 0.085573 | 0 |
| 2023-11-21 | 2023-12-15 | 22 | 1.665e-35, 0.01757, -0.08862, -0.01103, 0.07068 | 0.001289, 0.2, 0, -0.00322, 0.1 | 8.7435e-09 | 0.0098774 | 0.31896 | 0 |
| 2023-11-21 | 2024-01-19 | 20 | 4.03e-31, 0.04354, 0.6358, 0.08443, 0.09292 | 0.00314, 0.2, 0, 0.001511, 0.1 | 6.3981e-08 | 0.0067605 | 0.10014 | 0 |
| 2023-11-21 | 2024-03-15 | 11 | 5.952e-24, 0.06782, 0.6396, 0.08822, 0.1263 | 0.00653, 0.2, 0, -0.002494, 0.1 | 1.7571e-08 | 0.014377 | 0.025646 | 0 |
| 2023-11-21 | 2024-06-21 | 6 | 0.01251, 0.05037, -0.9664, -0.07178, 0.02258 | 0.0126, 0.2, 0, -0.00936, 0.1 | 7.2035e-08 | 0.037739 | 0.089092 | 0 |
| 2023-11-22 | 2023-12-15 | 23 | 7.003e-36, 0.02056, -0.3139, -0.03442, 0.06388 | 0.001311, 0.2, 0, 0.0001044, 0.1 | 1.7456e-08 | 0.009603 | 0.36992 | 0 |
| 2023-11-22 | 2024-01-19 | 16 | 0.002724, 0.01406, 0.2173, -0.00133, 0.03518 | 0.003256, 0.2, 0, 0.01876, 0.1 | 5.1279e-09 | 0.0144 | 0.038461 | 0 |
| 2023-11-22 | 2024-03-15 | 7 | 0.003216, 0.02783, -0.4972, -0.1841, 0.1451 | 0.006851, 0.2, 0, 0.02156, 0.1 | 3.8112e-08 | 0.1769 | 0.054278 | 0 |
| 2025-11-24 | 2026-02-20 | 5 | 0.006691, 0.02348, -0.2684, 0.04405, 0.0001 | 0.006866, 0.2, 0, 0.0298, 0.1 | 1.9996e-07 | 0.0048477 | 0.064866 | 0 |

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

| Penalty b,t | Median relative error | P95 | Butterfly | Calendar | Final price MSE | Seconds |
| --- | --- | --- | --- | --- | --- | --- |
| lambda_b=0,lambda_t=0 | 0.11482 | 0.55485 | 0 | 6 | 114.93 | 0.4986 |
| lambda_b=1e+08,lambda_t=0 | 0.11482 | 0.55485 | 0 | 6 | 114.93 | 0.34407 |
| lambda_b=0,lambda_t=1e+08 | 0.10715 | 0.54904 | 0 | 0 | 114.94 | 0.29986 |
| lambda_b=1e+08,lambda_t=1e+08 | 0.10715 | 0.54904 | 0 | 0 | 114.94 | 0.33818 |

A seeded random split removes 442 of 1473 usable IV quotes (30%, rounded), leaving 1031 for training.
Both methods are evaluated on the identical 348 quote IDs, using the market-price denominator.
The other 94 held-out quotes lack a supported SVI training group and are listed explicitly, so these results are conditional on common support.
The common-set SHA-256 is `a74eba595b1f20e8602bf33344fe078b5ec4a4f58fdb1903cf51114f4128dfdd`.

| Method | Common rows | Median relative error | P95 |
| --- | --- | --- | --- |
| SVI refit | 348 | 0.046995 | 0.47412 |
| Neural extrapolation | 348 | 0.085962 | 0.72969 |

### Optimizer comparison on the shared calibration groups

| Date/expiry | SciPy MSE | Torch MSE | SciPy seconds | Torch seconds | SciPy evaluations to target | Torch updates to target |
| --- | --- | --- | --- | --- | --- | --- |
| 2023-07-28/2023-10-20 | 6.9943e-09 | 3.49e-07 | 0.031121 | 0.067509 | 38 | not reached |
| 2023-10-23/2023-11-17 | 1.365e-08 | 1.1646e-07 | 0.0072152 | 0.039252 | 31 | not reached |
| 2023-10-23/2023-12-15 | 7.0587e-08 | 4.9533e-07 | 0.037021 | 0.040633 | 31 | not reached |
| 2023-10-23/2024-01-19 | 1.7479e-08 | 2.3698e-07 | 0.0098531 | 0.044523 | 33 | not reached |
| 2023-10-23/2024-03-15 | 4.9631e-08 | 1.0102e-06 | 0.0088318 | 0.039575 | 31 | not reached |
| 2023-10-23/2024-06-21 | 7.0511e-07 | 1.1086e-06 | 0.004481 | 0.038277 | not reached | not reached |
| 2023-10-23/2024-09-20 | 6.3083e-06 | 6.9212e-06 | 0.0044057 | 0.037814 | not reached | not reached |
| 2023-10-24/2023-11-17 | 1.9153e-09 | 7.8631e-08 | 0.0067283 | 0.040952 | 31 | 245 |
| 2023-10-24/2023-12-15 | 8.9891e-09 | 3.3162e-07 | 0.0070862 | 0.040994 | 31 | not reached |
| 2023-10-24/2024-03-15 | 9.2144e-08 | 8.2464e-07 | 0.049402 | 0.042305 | 332 | not reached |
| 2023-10-24/2024-06-21 | 4.4979e-07 | 5.8966e-07 | 0.0060885 | 0.040293 | not reached | not reached |
| 2023-10-25/2023-11-17 | 7.3315e-09 | 8.0766e-08 | 0.0093835 | 0.03928 | 31 | 270 |
| 2023-10-25/2023-12-15 | 2.7232e-09 | 2.6208e-07 | 0.0092135 | 0.040162 | 31 | not reached |
| 2023-10-25/2024-03-15 | 7.7079e-09 | 4.9018e-07 | 0.0052229 | 0.040376 | 25 | not reached |
| 2023-10-26/2023-11-17 | 7.1456e-09 | 5.1338e-08 | 0.0079782 | 0.038299 | 31 | 255 |
| 2023-10-26/2023-12-15 | 1.4517e-08 | 2.4103e-07 | 0.0098678 | 0.041485 | 31 | not reached |
| 2023-10-26/2024-03-15 | 1.0134e-08 | 6.841e-07 | 0.015493 | 0.038362 | 31 | not reached |
| 2023-10-27/2023-11-17 | 4.8774e-09 | 6.3029e-08 | 0.0073517 | 0.040712 | 31 | 268 |
| 2023-10-27/2023-12-15 | 1.5894e-08 | 1.711e-07 | 0.0048733 | 0.04139 | 31 | not reached |
| 2023-10-27/2024-01-19 | 4.6375e-07 | 1.2968e-06 | 0.0054155 | 0.041514 | not reached | not reached |
| 2023-10-27/2024-03-15 | 1.6645e-07 | 1.0433e-06 | 0.0049311 | 0.038952 | not reached | not reached |
| 2023-10-27/2024-06-21 | 1.1902e-07 | 2.7848e-07 | 0.0040675 | 0.038606 | not reached | not reached |
| 2023-10-30/2023-11-17 | 1.413e-08 | 8.8726e-08 | 0.007432 | 0.041163 | 31 | 290 |
| 2023-10-30/2023-12-15 | 2.5157e-08 | 1.6996e-07 | 0.0057969 | 0.040051 | 31 | not reached |
| 2023-10-30/2024-03-15 | 1.6773e-07 | 6.0222e-07 | 0.012579 | 0.0398 | not reached | not reached |
| 2023-10-31/2023-11-17 | 3.5784e-09 | 9.5411e-08 | 0.006385 | 0.040208 | 31 | 297 |
| 2023-10-31/2023-12-15 | 1.9196e-08 | 1.9594e-07 | 0.0044074 | 0.040832 | 31 | not reached |
| 2023-10-31/2024-03-15 | 6.0189e-08 | 7.9035e-07 | 0.035402 | 0.039368 | 70 | not reached |
| 2023-11-01/2023-11-17 | 5.5192e-09 | 1.0804e-07 | 0.0059325 | 0.039137 | 31 | not reached |
| 2023-11-01/2023-12-15 | 8.242e-09 | 1.7135e-07 | 0.0077115 | 0.039648 | 31 | not reached |
| 2023-11-01/2024-03-15 | 3.9168e-09 | 4.3391e-07 | 0.17865 | 0.042099 | 25 | not reached |
| 2023-11-02/2023-11-17 | 9.3919e-09 | 1.3435e-07 | 0.0052589 | 0.040185 | 31 | not reached |
| 2023-11-02/2023-12-15 | 7.3998e-09 | 1.4747e-07 | 0.0078632 | 0.040944 | 31 | not reached |
| 2023-11-02/2024-03-15 | 4.6847e-09 | 5.3012e-07 | 0.020005 | 0.044099 | 31 | not reached |
| 2023-11-03/2023-11-17 | 8.8413e-08 | 2.5541e-07 | 0.0057207 | 0.039458 | 74 | not reached |
| 2023-11-03/2023-12-15 | 2.5965e-08 | 1.2682e-07 | 0.0038952 | 0.039013 | 31 | not reached |
| 2023-11-03/2024-03-15 | 1.1791e-08 | 3.7329e-07 | 0.0047594 | 0.038583 | 37 | not reached |
| 2023-11-06/2023-11-17 | 1.0891e-08 | 1.838e-07 | 0.026746 | 0.04658 | 31 | not reached |
| 2023-11-06/2023-12-15 | 1.8639e-08 | 1.2629e-07 | 0.0077291 | 0.051334 | 31 | not reached |
| 2023-11-06/2024-01-19 | 6.6485e-08 | 2.4278e-07 | 0.019357 | 0.041194 | 31 | not reached |
| 2023-11-06/2024-03-15 | 4.0114e-08 | 1.3799e-06 | 0.30168 | 0.044304 | 37 | not reached |
| 2023-11-07/2023-11-17 | 2.5119e-08 | 4.7584e-07 | 0.0044655 | 0.039618 | 80 | not reached |
| 2023-11-07/2023-12-15 | 3.7456e-08 | 1.2496e-07 | 0.0045269 | 0.043854 | 31 | not reached |
| 2023-11-07/2024-01-19 | 1.1102e-07 | 3.7048e-07 | 0.26192 | 0.039352 | not reached | not reached |
| 2023-11-07/2024-03-15 | 4.5002e-08 | 1.0706e-06 | 0.044814 | 0.042427 | 51 | not reached |
| 2023-11-08/2023-11-17 | 9.411e-09 | 2.2524e-07 | 0.0064946 | 0.041649 | 31 | not reached |
| 2023-11-08/2023-12-15 | 1.6405e-08 | 2.0235e-07 | 0.009576 | 0.039515 | 31 | not reached |
| 2023-11-08/2024-01-19 | 1.7473e-08 | 5.6666e-07 | 0.395 | 0.037847 | 37 | not reached |
| 2023-11-08/2024-03-15 | 6.3947e-08 | 7.6024e-07 | 0.010615 | 0.038581 | 37 | not reached |
| 2023-11-09/2023-11-17 | 1.0354e-08 | 2.5947e-07 | 0.0065669 | 0.040804 | 31 | not reached |
| 2023-11-09/2023-12-15 | 5.9746e-09 | 1.3539e-07 | 0.006522 | 0.038922 | 31 | not reached |
| 2023-11-09/2024-01-19 | 1.7456e-08 | 3.046e-07 | 0.031888 | 0.039871 | 38 | not reached |
| 2023-11-09/2024-03-15 | 1.8675e-09 | 4.876e-07 | 0.026879 | 0.040741 | 39 | not reached |
| 2023-11-10/2023-11-17 | 4.5586e-09 | 2.9811e-07 | 0.0054683 | 0.041002 | 31 | not reached |
| 2023-11-10/2023-12-15 | 4.7018e-09 | 1.1213e-07 | 0.0093757 | 0.040414 | 31 | not reached |
| 2023-11-10/2024-01-19 | 1.0334e-09 | 2.0888e-07 | 0.010545 | 0.041329 | 31 | not reached |
| 2023-11-10/2024-03-15 | 1.7882e-09 | 8.6006e-07 | 0.0119 | 0.040776 | 25 | not reached |
| 2023-11-10/2024-06-21 | 1.6797e-07 | 4.1442e-07 | 0.38793 | 0.039647 | not reached | not reached |
| 2023-11-10/2024-09-20 | 1.1143e-06 | 1.2546e-06 | 0.012496 | 0.041405 | not reached | not reached |
| 2023-11-13/2023-12-15 | 1.5208e-08 | 5.0535e-08 | 0.0057728 | 0.040192 | 31 | 229 |
| 2023-11-13/2024-01-19 | 1.0864e-08 | 1.5939e-07 | 0.0451 | 0.03764 | 31 | not reached |
| 2023-11-14/2023-12-15 | 4.4195e-09 | 3.7853e-08 | 0.0053558 | 0.040804 | 31 | 226 |
| 2023-11-14/2024-03-15 | 3.3173e-10 | 4.8101e-07 | 0.0034597 | 0.03975 | 46 | not reached |
| 2023-11-15/2023-12-15 | 6.8455e-09 | 5.5015e-08 | 0.00608 | 0.039374 | 31 | 241 |
| 2023-11-15/2024-01-19 | 6.1502e-09 | 6.5269e-07 | 0.0048374 | 0.045576 | 25 | not reached |
| 2023-11-15/2024-03-15 | 1.4829e-09 | 5.5529e-07 | 0.0044368 | 0.039424 | 33 | not reached |
| 2023-11-15/2024-06-21 | 1.3664e-07 | 1.9645e-07 | 0.022596 | 0.040169 | not reached | not reached |
| 2023-11-16/2023-12-15 | 2.6949e-08 | 4.4151e-08 | 0.0092737 | 0.044393 | 31 | 235 |
| 2023-11-16/2024-01-19 | 3.6181e-08 | 2.1704e-07 | 0.0071988 | 0.039726 | 31 | not reached |
| 2023-11-16/2024-03-15 | 2.486e-10 | 4.8704e-07 | 0.076415 | 0.052223 | 37 | not reached |
| 2023-11-17/2023-12-15 | 3.5864e-08 | 5.9963e-08 | 0.0032102 | 0.048109 | 31 | 256 |
| 2023-11-17/2024-01-19 | 8.1077e-09 | 2.8223e-07 | 0.010219 | 0.043553 | 31 | not reached |
| 2023-11-17/2024-03-15 | 1.5086e-08 | 4.2642e-07 | 0.028707 | 0.047952 | 37 | not reached |
| 2023-11-17/2024-09-20 | 4.4846e-06 | 6.303e-06 | 0.0065809 | 0.044295 | not reached | not reached |
| 2023-11-20/2023-12-15 | 2.0191e-08 | 5.4105e-08 | 0.0033596 | 0.04084 | 31 | 259 |
| 2023-11-20/2024-01-19 | 2.562e-09 | 1.7066e-07 | 0.0078567 | 0.040526 | 31 | not reached |
| 2023-11-20/2024-03-15 | 3.7994e-08 | 5.5025e-07 | 0.086173 | 0.04176 | 43 | not reached |
| 2023-11-20/2024-06-21 | 1.498e-06 | 1.7248e-06 | 0.057017 | 0.039155 | not reached | not reached |
| 2023-11-21/2023-12-15 | 8.7435e-09 | 6.8448e-08 | 0.010332 | 0.040306 | 31 | 274 |
| 2023-11-21/2024-01-19 | 6.3981e-08 | 1.9982e-07 | 0.0062712 | 0.040705 | 31 | not reached |
| 2023-11-21/2024-03-15 | 1.7571e-08 | 7.289e-07 | 0.014284 | 0.040766 | 25 | not reached |
| 2023-11-21/2024-06-21 | 5.8448e-08 | 3.2881e-07 | 0.038794 | 0.041573 | 972 | not reached |
| 2023-11-22/2023-12-15 | 1.7456e-08 | 7.8007e-08 | 0.0093762 | 0.039647 | 31 | 275 |
| 2023-11-22/2024-01-19 | 5.1279e-09 | 1.5283e-07 | 0.013583 | 0.04116 | 31 | not reached |
| 2023-11-22/2024-03-15 | 1.1407e-08 | 4.2708e-07 | 0.17414 | 0.047197 | 37 | not reached |
| 2025-11-24/2026-02-20 | 1.9996e-07 | 2.6345e-07 | 0.0047019 | 0.041316 | not reached | not reached |

The full Torch-SVI and neural arbitrage checks, including violation locations, remain in [differentiable metrics](results/approach2/differentiable/metrics.json).
Figures: [classical surface](results/approach1/market/svi_surface.html), [arbitrage diagnostics](results/approach1/market/arbitrage_diagnostics.html), [objective profiles](results/approach2/differentiable/objective_profiles.html), [neural ablation](results/approach2/differentiable/neural_ablation.html) and [comparable holdout ranking](results/comparison.html).
Seed 42 governs quote dropout and Torch initialization; seeded CPU floating-point results can vary slightly by platform.

## Statement of work: group direction and agent contribution

### Q1 work division

**Group direction and decisions.**
The group supplied the Q1 repository and authorized expanding the option snapshot to monthly daily chains, preserving the original snapshots and using a tenor-interpolated SHIBOR curve.
The group is responsible for evaluating the zero-dividend carry approximation, interpreting parity and arbitrage diagnostics, and assessing the repricing and robustness results against the stated objectives.

**Coding-agent implementation and verification.**
The coding agent integrated the expanded data, implemented and checked the rate conversion and past-fixing joins, amended classical and differentiable calibration, aligned the quote-drop comparison on identical held-out quotes, and generated the calibration tables, diagnostics, figures and regression checks.

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
