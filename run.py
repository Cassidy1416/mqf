"""Reproduce separated Q1/Q2/Q4 experiments through locked environments."""
from __future__ import annotations
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
QUESTION_SCRIPTS = {
    "q1": {"approach1": "code/approach1_market_pipeline.py", "approach2": "code/approach2_differentiable.py", "compare": "code/compare.py"},
    "q2": {"approach1": "code/approach1_q2.py", "approach2": "code/approach2_q2.py", "compare": "code/compare.py"},
    "q4": {"approach1": "code/approach1_network_analytics.py", "approach2": "code/approach2_node_embeddings.py", "future": "code/approach2_future_links.py", "compare": "code/compare.py"},
}


def load_entrypoint(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_all(questions=("q1", "q2", "q4")):
    return load_entrypoint("suite_fetch", "data/fetch.py").verify_manifest(questions=questions)


def build_index():
    return load_entrypoint("suite_compare", "code/compare.py").main([])


def run_question(question, script, seed=None, offline=False, dry_run=False):
    folder = ROOT / "questions" / question
    uv = shutil.which("uv") or "uv"
    command = [uv, "run", "--locked", "--python", "3.13"] + (["--offline"] if offline else [])
    command += ["python"] + (["-m", "unittest", "discover", "-s", "tests", "-v"] if script == "test" else [script])
    if seed is not None:
        command += ["--seed", str(seed)]
    print(f"[{question}] cwd: {folder}\n[{question}] command: {' '.join(command)}", flush=True)
    if dry_run:
        return
    if not shutil.which("uv"):
        raise RuntimeError("Install uv before running scientific stages")
    env = dict(os.environ, UV_CACHE_DIR=str(ROOT / ".cache/uv"), UV_PYTHON_INSTALL_DIR=str(ROOT / ".cache/uv/python"),
               UV_PROJECT_ENVIRONMENT=str(folder / ".venv"), PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(folder / "code"), LOKY_MAX_CPU_COUNT=str(os.cpu_count() or 1))
    subprocess.run(command, cwd=folder, env=env, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", choices=("q1", "q2", "q4", "all"))
    parser.add_argument("--stage", choices=("verify", "test", "approach1", "approach2", "future", "compare", "index", "all"), default="all")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("seed must be nonnegative")
    questions = ("q1", "q2", "q4") if args.question == "all" else (args.question,)
    if not args.dry_run:
        verify_all(questions)
    else:
        print("DRY RUN: snapshot verification planned; no files or environments will change.")
    if args.stage == "verify":
        return
    if args.stage == "index":
        if not args.dry_run:
            build_index()
        return
    for question in questions:
        stages = tuple(QUESTION_SCRIPTS[question]) if args.stage == "all" else (args.stage,)
        for stage in stages:
            if stage == "future" and question != "q4":
                continue
            script = "test" if stage == "test" else QUESTION_SCRIPTS[question][stage]
            run_question(question, script, args.seed if stage in ("approach1", "approach2", "future") else None, args.offline, args.dry_run)
    if args.stage in ("compare", "all") and not args.dry_run:
        build_index()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Reproduction failed: {error}")
