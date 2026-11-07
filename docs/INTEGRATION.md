# Integration notes

This milestone integrates the layout and execution of the group's Advanced Programming repository.
It does not claim new scientific validation, and it does not close any original session-export gap described below; those remain for group review.

## Directory tree

```
.
├── AGENTS.md                 root contract for Q1/Q2/Q4
├── README.md                 quick commands, points here
├── run.py                    stdlib launcher: verify, run, index
├── sources.json              import provenance per question
├── docs/INTEGRATION.md       this file
├── report.md                 combined report (imported texts)
├── SESSION.md                index of the real per-question session exports
└── questions/
    ├── q1/  code/ data/ results/ README.md report.md SESSION.md pyproject.toml uv.lock
    ├── q2/  code/ data/ results/ README.md report.md SESSION.md pyproject.toml uv.lock
    └── q4/  code/ data/ results/ README.md report.md SESSION.md pyproject.toml uv.lock
```

## Commands

Run from the repository root:

```sh
python3 run.py all --stage verify      # stdlib-only snapshot verification
python3 run.py q2 --stage approach1    # one stage of one question
python3 run.py q2 --offline            # all stages of q2 without network
python3 run.py all --offline           # every question, all execution stages
python3 run.py all --stage index       # rebuild root results/comparison.html from saved outputs
python3 run.py all --dry-run           # print verification and planned commands only
```

CLI: `python3 run.py {q1,q2,q4,all} [--stage {verify,approach1,approach2,compare,all,index}] [--seed 42] [--offline] [--dry-run]`.
Every selected execution stage verifies the committed snapshots first; `--stage verify` and `--stage index` need no uv.
`--offline` requires each question's dependencies to be installed already; omitting it lets uv install dependencies but never refreshes vendor data.

Inside a question directory the question's own documented commands still work with that question's pinned lockfile, for example from `questions/q2/`:

```sh
uv sync --locked --python 3.13
uv run --locked python code/approach1_q2.py --seed 42
```

## Isolated environments and unchanged locks

Each question keeps its original `pyproject.toml` and locked `uv.lock`; no dependency versions were merged or upgraded.
`run.py` executes each script in a fresh subprocess with the working directory set to the question directory, so question-local packages (`common.py`, a `code/` package) cannot collide.
The launcher sets `UV_CACHE_DIR` to `.cache/uv`, `UV_PYTHON_INSTALL_DIR` to `.cache/uv/python`, and `UV_PROJECT_ENVIRONMENT` to that question's own `.venv/`, so all caches and environments stay inside this repository.

## What the launcher verifies

- Q2 (`questions/q2/data/metadata.json`): for each dataset's `clean` entry, the launcher checks the SHA-256, the row count, the header order against the schema, strictly increasing unique ISO dates, and coverage of `first_date`/`last_date`.
- Q1 and Q4 (`questions/qN/data/clean/metadata.json`): every declared artifact's SHA-256 and byte length; empty manifests, missing artifacts and paths escaping the question folder are rejected.
Verification uses only standard-library hashing and CSV parsing, no uv and no third-party imports.

## Cross-question index

Each question's own `compare.py` writes `results/comparison.html` inside that question and ranks only experiments comparable within that question.
A successful `compare` or `all` stage regenerates the root `results/comparison.html`, and `--stage index` rebuilds it from saved outputs without uv.
The root page only links to saved per-question comparisons and counts their saved `metrics.json` files.
It never ranks across questions because Q1, Q2 and Q4 metrics are not comparable with each other; linked pages are explicitly labeled as saved outputs.

## Source provenance

Imported question sources are recorded in `sources.json`:

- Q1: git@github.com:micheal021/ap26-q1-vol-surface.git, commit 58fbb2d33e7f53dd6948a1ae636621c265e7f8c7.
- Q2: existing repository git@github.com:Cassidy1416/mqf-q2.git, commit 7a99293f923c7370e1cfad9a7ea003a63437047f.
- Q4: git@github.com:micheal021/ap26-q4-trade-network.git, commit 5020b6f43bf9c1731a9b8bbf1d2d40bf665c58ed.

The full Q1 and Q4 Git histories are preserved as merge ancestors of this repository; no submodule setup or extra clones are needed.

## Session-export status (honest record)

- The Q1 and Q4 `SESSION.md` files under their question folders are upstream milestone summaries, not full coding-session transcripts.
- The Q2 original session export explicitly omits its later Codex completion work.
- Root `SESSION.md` includes the actual sanitized OpenCode integration transcripts.
- Original question-session gaps and Codex orchestration history are not reconstructed by those exports.
- Scientific completeness (all approaches executed and verified by the group) also remains for group review.
