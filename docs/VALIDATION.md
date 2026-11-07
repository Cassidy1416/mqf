# Repair validation

All nine scientific result files were regenerated with seed 42 after the repairs, including both Q1 approaches, both Q2 engines for IF0 and CU0, Q4 classical analytics, corrected static link prediction and chronological future-link prediction.
Q2B trained all 18 cost/frequency/instrument cases with validation checkpoint selection and a maximum of 100 epochs; each run reached the cap, which is reported rather than called convergence.
The long Q2B run completed successfully in the working repository and was not repeated solely for clean-archive validation.

| Check | Result |
| --- | --- |
| Root snapshot verification | Q1/Q2/Q4 child and root hashes, schema, keys and coverage pass |
| Root regression tests | 5 pass |
| Q1 regression tests | 5 pass |
| Q2 regression tests | 33 pass |
| Q4 regression tests | 6 pass |
| Total regression checks | 49 pass |
| All native comparisons and root aggregation | Pass; Q1 common holdout and Q4 static/future separated |
| Report artifact links | All generated report links resolve locally |
| Numeric result scan | No nonfinite floats in saved metrics |
| Plotly HTML inspection | No external script-source tags in saved question figures |
| Python source parsing and Git whitespace checks | Pass |

The documented launcher initially exposed a standard-library import collision in Q1/Q4 because their empty `code/__init__.py` markers shadowed Python's `code` module during PyTorch import.
The unused markers were removed and all documented environment tests passed afterward.
The macOS sandbox causes uv's system-configuration lookup to panic, so uv commands were run with the approved host permission while keeping environments and caches inside the repository.

The combined report and audit distinguish implementation completion from benchmark success and submission review.
Q1 expanded-data repricing and calendar consistency and Q4 learned predictive targets are not claimed to pass when they do not.
The group still needs to verify its report, resolve documented compliance interpretations and review the final commit before a `submission` tag is appropriate.
