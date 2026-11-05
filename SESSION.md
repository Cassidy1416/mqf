# Session Export


## Session metadata

- Project: Q1 China index-option implied-volatility surface
- Repository: `ap26-q1-vol-surface`
- Default seed: `42`
- Remote visibility: private

## Milestones

### 1. Environment and repository layout

- Added `README.md`, `.gitignore`, `pyproject.toml`, package markers, and required output directories.
- Fixed Python 3.13-compatible dependencies, including `akshare==1.20.34`, SciPy, Plotly, Rich, and PyTorch.
- Commit: `chore: pin Q1 environment and repository layout`.

### 2. Data interface audit

- Verified CFFEX contract discovery through `option_cffex_hs300_spot_sina`.
- Verified historical call/put daily OHLCV through `option_cffex_hs300_daily_sina`.
- Verified CSI 300 historical prices through the Sina index interface and historical 3M SHIBOR through `macro_china_shibor_all`.
- Added a retrying snapshot pipeline with raw cache, clean CSVs, metadata, and SHA-256 checksums.
- Commit: `data: add historical China option snapshot pipeline`.

### 3. Classical implementation

- Implemented forward Black–Scholes pricing, Brent IV inversion, parity residuals, SVI, fixed-grid surface output, SLSQP butterfly constraints, calendar checks, forward-variance checks, repricing diagnostics, and Plotly figures.
- Iterated on liquidity rules after comparing volume and moneyness sensitivity. The final rule is volume at least 40 and `0.9 <= K/F <= 1.1`.
- Added a shared-date block across four expiry codes so calendar verification is executable rather than vacuous.

### 4. Differentiable implementation

- Implemented reparameterized Torch-SVI and convergence comparison with SciPy.
- Implemented a two-hidden-layer price-space neural surface with butterfly and calendar penalties.
- Added penalty ablation and 30% quote-dropout robustness comparison against SVI refitting.
- Fixed a post-training plotting bug and reran the complete experiment.

### 5. Validation outcomes

- Approach 1: 225 filtered quotes, 224 IVs, 12 SVI groups, zero butterfly violations, 20 calendar/forward-variance violations explicitly recorded, and 1.67% median repricing.
- Approach 2: 12 Torch-SVI groups; mean Torch/SciPy objectives approximately `1.97e-08`; dropout SVI median error 0.067% and neural median error 0.204%.
- Generated self-contained HTML figures, comparison output, and the fixed-grid surface CSV.

## Reproduction commands

```bash
uv sync
python data/fetch.py --seed 42
python code/approach1_market_pipeline.py --seed 42
python code/approach2_differentiable.py --seed 42
python code/compare.py
```

## Sensitive information

No credentials, tokens, private keys, or browser authorization data are recorded.
