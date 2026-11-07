"""Root launcher for the Q1, Q2 and Q4 Advanced Programming experiments.

Runs each question's scripts inside its own question directory using that
question's locked uv environment, so question packages (common.py, code/)
never collide.

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

QUESTION_SCRIPTS = {
    "q1": {
        "approach1": "code/approach1_market_pipeline.py",
        "approach2": "code/approach2_differentiable.py",
        "compare": "code/compare.py",
    },
    "q2": {
        "approach1": "code/approach1_q2.py",
        "approach2": "code/approach2_q2.py",
        "compare": "code/compare.py",
    },
    "q4": {
        "approach1": "code/approach1_network_analytics.py",
        "approach2": "code/approach2_node_embeddings.py",
        "compare": "code/compare.py",
    },
}

EXECUTION_STAGES = ("approach1", "approach2", "compare")


class VerificationError(RuntimeError):
    """Raised when a manifest or a declared artifact fails verification."""


def verify_q1_q4(question: str) -> str:
    """Verify every declared Q1/Q4 clean artifact (SHA-256 and byte length)."""
    manifest_path = ROOT / "questions" / question / "data" / "clean" / "metadata.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise VerificationError(f"{question}: manifest {manifest_path} declares no artifacts")
    question_root = (ROOT / "questions" / question).resolve()
    checked = 0
    for rel, entry in artifacts.items():
        if not isinstance(entry, dict) or "sha256" not in entry or "bytes" not in entry:
            raise VerificationError(f"{question}: artifact {rel!r} lacks sha256/bytes")
        artifact = (question_root / rel).resolve()
        if not artifact.is_relative_to(question_root):
            raise VerificationError(f"{question}: artifact path {rel!r} escapes the question folder")
        if not artifact.is_file():
            raise VerificationError(f"{question}: missing artifact file {artifact}")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        expected = entry["sha256"]
        size = artifact.stat().st_size
        if digest != expected:
            raise VerificationError(
                f"{question}: SHA-256 mismatch for {rel}: expected {expected}, got {digest}"
            )
        if size != entry["bytes"]:
            raise VerificationError(
                f"{question}: byte-length mismatch for {rel}: expected {entry['bytes']}, got {size}"
            )
        checked += 1
    return f"{question}: verified {checked} clean artifacts (SHA-256 and bytes)"

def _check_clean_csv(question: str, path: Path, entry: dict) -> int:
    """Check a Q2 clean CSV against its manifest entry; return its row count."""
    schema = entry.get("schema")
    if not isinstance(schema, dict) or not schema:
        raise VerificationError(f"{question}: dataset clean entry lacks a schema")
    if not path.is_file():
        raise VerificationError(f"{question}: missing clean snapshot {path}")
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != entry.get("sha256"):
        raise VerificationError(
            f"{question}: SHA-256 mismatch for {path.name}: expected {entry.get('sha256')}, got {digest}"
        )
    text = payload.decode("utf-8")
    reader = csv.reader(text.splitlines())
    try:
        header = next(reader)
    except StopIteration:
        raise VerificationError(f"{question}: {path.name} is empty") from None
    expected_header = list(schema)
    if header != expected_header:
        raise VerificationError(
            f"{question}: header mismatch for {path.name}: expected {expected_header}, got {header}"
        )
    rows = 0
    dates = []
    date_index = 0  # every Q2 clean schema starts with the date column
    for record in reader:
        if not record:
            continue
        rows += 1
        dates.append(record[date_index])
    if rows < 1:
        raise VerificationError(f"{question}: {path.name} declares {rows} data rows")
    wanted_rows = entry.get("rows")
    if rows != wanted_rows:
        raise VerificationError(
            f"{question}: row-count mismatch for {path.name}: manifest says {wanted_rows}, file has {rows}"
        )
    parsed = []
    for row_number, raw in enumerate(dates, start=2):  # header is line 1
        try:
            value = datetime.date.fromisoformat(raw)
        except ValueError as exc:
            raise VerificationError(
                f"{question}: row {row_number} of {path.name} has a non-ISO date {raw!r}"
            ) from exc
        if value.isoformat() != raw:
            raise VerificationError(
                f"{question}: row {row_number} of {path.name} is not an ISO YYYY-MM-DD date: {raw!r}"
            )
        parsed.append(value)
    if any(later <= earlier for earlier, later in zip(parsed, parsed[1:])):
        raise VerificationError(f"{question}: dates in {path.name} are not strictly increasing and unique")
    first_date = entry.get("first_date")
    last_date = entry.get("last_date")
    if first_date and dates[0] != first_date:
        raise VerificationError(
            f"{question}: first-date mismatch for {path.name}: manifest says {first_date}, file starts {dates[0]}"
        )
    if last_date and dates[-1] != last_date:
        raise VerificationError(
            f"{question}: last-date mismatch for {path.name}: manifest says {last_date}, file ends {dates[-1]}"
        )
    return rows


def verify_q2(question: str) -> str:
    """Verify each Q2 clean snapshot against the manifest (hash, rows, header, dates)."""
    manifest_path = ROOT / "questions" / question / "data" / "metadata.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    datasets = manifest.get("q2", {}).get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise VerificationError(f"{question}: manifest {manifest_path} declares no datasets")
    question_root = (ROOT / "questions" / question).resolve()
    details = []
    for name, dataset in datasets.items():
        clean = dataset.get("clean")
        if not isinstance(clean, dict):
            raise VerificationError(f"{question}: dataset {name!r} has no clean entry")
        rel = clean.get("path")
        if not isinstance(rel, str) or not rel:
            raise VerificationError(f"{question}: dataset {name!r} clean entry has no path")
        snapshot = (question_root / rel).resolve()
        if not snapshot.is_relative_to(question_root):
            raise VerificationError(f"{question}: dataset {name!r} path {rel!r} escapes the question folder")
        rows = _check_clean_csv(question, snapshot, clean)
        details.append(f"{name}={rows} rows")
    joined = ", ".join(details)
    return f"{question}: verified {len(datasets)} clean snapshots (SHA-256, rows, header, dates): {joined}"


def verify_all(questions: tuple[str, ...]) -> list[str]:
    """Verify the committed snapshots only for the selected questions."""
    summaries = []
    for question in questions:
        if question == "q2":
            summaries.append(verify_q2(question))
        else:
            summaries.append(verify_q1_q4(question))
    return summaries


def _cache_env(cache_dir: Path, python_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["UV_CACHE_DIR"] = str(cache_dir)
    env["UV_PYTHON_INSTALL_DIR"] = str(python_dir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_question(question: str, script: str, seed: int | None, offline: bool, dry_run: bool) -> None:
    """Run one question script in a fresh subprocess with its own environment."""
    question_dir = ROOT / "questions" / question
    script_path = question_dir / script
    if not script_path.is_file():
        raise FileNotFoundError(f"{question}: script not found: {script_path}")
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError(
            "uv was not found on PATH. Install it (https://docs.astral.sh/uv/) "
            "or run the question scripts manually from questions/" + question + "."
        )
    command = [uv, "run", "--locked", "--python", "3.13"]
    if offline:
        command.append("--offline")
    command.append("python")
    command.append(script)
    if seed is not None:
        command += ["--seed", str(seed)]
    caches = ROOT / ".cache" / "uv"
    python_install = ROOT / ".cache" / "uv" / "python"
    env = _cache_env(caches, python_install)
    env["UV_PROJECT_ENVIRONMENT"] = str(question_dir / ".venv")
    label = f"[{question}]"
    if dry_run:
        print(f"{label} (question directory: {question_dir})")
        print(f"{label} command: " + " ".join(command))
        print(f"{label} cwd: {question_dir}")
        print(f"{label} UV_PROJECT_ENVIRONMENT: {env['UV_PROJECT_ENVIRONMENT']}")
        return
    caches.mkdir(parents=True, exist_ok=True)
    print(f"{label} running: {' '.join(command)}")
    result = subprocess.run(command, cwd=question_dir, env=env)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command)


def _question_dir(question: str) -> Path:
    return ROOT / "questions" / question


def _results_dir(question: str) -> Path:
    return _question_dir(question) / "results"


def _metrics_files(question: str) -> list[str]:
    results = _results_dir(question)
    if not results.is_dir():
        return []
    return sorted(
        str(p.relative_to(results)) for p in results.rglob("metrics.json") if p.is_file()
    )


def build_index() -> Path:
    """Build the root cross-question HTML index from saved outputs."""
    cards = []
    for question in ("q1", "q2", "q4"):
        comparison = _results_dir(question) / "comparison.html"
        if not comparison.is_file():
            cards.append(
                f"<div class='card miss'><h2>{html.escape(question)} (no saved comparison)</h2>"
                "<p>No saved results/comparison.html exists for this question yet.</p></div>"
            )
            continue
        metrics = _metrics_files(question)
        rel = os.path.relpath(comparison, ROOT / "results").replace(os.sep, "/")
        card = [
            f"<div class='card hit'><h2><a href='{html.escape(rel)}'>{html.escape(question)} saved comparison</a></h2>",
            "<p>Saved output from the question's own run; metrics are compared only inside each question.</p>",
            f"<p>{len(metrics)} saved metrics files: "
            + ", ".join(html.escape(m) for m in metrics)
            + "</p>",
        ]
        card.append("</div>")
        cards.append("".join(card))
    body = "\n".join(cards)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AP26 integration index (q1, q2, q4)</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; }}
.card {{ border: 1px solid #ccc; border-radius: 8px; padding: 1rem 1.25rem; margin: 1rem 0; }}
.card.hit {{ border-left: 6px solid #2a7; }}
.card.miss {{ border-left: 6px solid #b96; color: #555; }}
h1 {{ font-size: 1.4rem; }}
a {{ color: #05c; }}
</style>
</head>
<body>
<h1>Advanced Programming project: cross-question index</h1>
<p>This page only links saved per-question comparisons. Results are never ranked across
questions because the metrics of q1, q2 and q4 are not comparable with each other.</p>
{body}
</body>
</html>
"""
    out_dir = ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "comparison.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Q1, Q2 and Q4 experiments from the repository root."
    )
    parser.add_argument("question", choices=("q1", "q2", "q4", "all"))
    parser.add_argument(
        "--stage",
        default="all",
        choices=("verify", "approach1", "approach2", "compare", "all", "index"),
        help="execution stage; index only regenerates the root HTML from saved outputs",
    )
    parser.add_argument("--seed", type=int, default=42, help="random seed for approach scripts")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="run uv with --offline; each question's dependencies must already be installed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the planned verification and commands without running anything",
    )
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("--seed must be a non-negative integer")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    questions = ("q1", "q2", "q4") if args.question == "all" else (args.question,)
    stages = EXECUTION_STAGES if args.stage == "all" else ()
    if args.stage in EXECUTION_STAGES:
        stages = (args.stage,)

    if args.dry_run:
        print("DRY RUN: nothing will be executed and no files will be changed.")
        for question in questions:
            print()
            print(f"=== {question} ===")
            if args.stage in ("verify", "all"):
                print(
                    f"[{question}] verification planned: snapshot hashes/counts against the committed manifests"
                )
            if args.stage == "index":
                print(
                    f"[{question}] index planned: rebuild {ROOT / 'results' / 'comparison.html'} "
                    "from saved outputs, no uv needed"
                )
            for stage in stages:
                seed = args.seed if stage in ("approach1", "approach2") else None
                run_question(question, QUESTION_SCRIPTS[question][stage], seed, args.offline, True)
        return 0

    if stages or args.stage in ("verify", "index"):
        summaries = verify_all(questions)
        for line in summaries:
            print(f"[verify] {line}")

    if args.stage == "verify":
        return 0

    if args.stage == "index":
        out = build_index()
        print(f"[index] wrote {out}")
        return 0

    for question in questions:
        for stage in stages:
            seed = args.seed if stage in ("approach1", "approach2") else None
            run_question(question, QUESTION_SCRIPTS[question][stage], seed, args.offline, False)

    if args.stage in ("compare", "all"):
        out = build_index()
        print(f"[index] wrote {out}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (VerificationError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"error: malformed JSON manifest: {exc}", file=sys.stderr)
        sys.exit(2)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        print(f"error: command failed with status {exc.returncode}: {exc.cmd}", file=sys.stderr)
        sys.exit(exc.returncode)
