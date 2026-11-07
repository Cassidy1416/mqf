"""Unified immutable-snapshot manifest and retrieval entrypoint."""
from __future__ import annotations
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from snapshot_io import sha256, safe_path, verify_manifest as verify_csv


def build_manifest(root=ROOT):
    result = {"schema_version": 1, "questions": {}, "artifacts": {}}
    for q in ("q1", "q2", "q4"):
        base = root / "questions" / q
        path = base / ("data/metadata.json" if q == "q2" else "data/clean/metadata.json")
        meta = json.loads(path.read_text())
        result["questions"][q] = {"manifest": str(path.relative_to(root)), "sha256": sha256(path),
                                  "source": meta.get("source", {k: v["access"] for k, v in meta.get("q2", {}).get("datasets", {}).items()})}
        specs = {v["clean"]["path"]: dict(v["clean"], source=v["access"], retrieval_date=v["retrieval_date"], units=v.get("clean_value_units")) for v in meta["q2"]["datasets"].values()} if q == "q2" else meta["artifacts"]
        for relative, declared in specs.items():
            file = safe_path(base, relative)
            if sha256(file) != declared["sha256"]:
                raise ValueError(f"Child manifest does not match bytes: {file}")
            spec = dict(declared)
            spec.pop("path", None)
            spec.update(bytes=file.stat().st_size, question=q)
            spec.setdefault("source", meta.get("source"))
            spec.setdefault("retrieval_date", meta.get("retrieved_at", meta.get("retrieved_at_utc")))
            spec.setdefault("unique_key", ["date"] if "date" in spec.get("schema", {}) else [])
            result["artifacts"][str(file.relative_to(root))] = spec
    return result


def verify_manifest(root=ROOT, manifest=None, questions=("q1", "q2", "q4")):
    data = manifest if manifest is not None else json.loads((root / "data/metadata.json").read_text())
    if not data.get("artifacts"):
        raise ValueError("The root manifest is empty")
    for q in questions:
        entry = data["questions"][q]
        child = safe_path(root, entry["manifest"])
        if sha256(child) != entry["sha256"]:
            raise ValueError(f"Question metadata changed: {q}; rebuild the root manifest after reviewing the change")
        verify_csv(root, {"artifacts": {p: a for p, a in data["artifacts"].items() if a["question"] == q}})
        if q == "q1":
            spec = importlib.util.spec_from_file_location("q1_snapshot_checks", root / "questions/q1/data/fetch.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.verify_snapshots(root / "questions/q1/data/clean")
        for relative, artifact in data["artifacts"].items():
            if artifact["question"] == q and sha256(safe_path(root, relative)) != artifact["sha256"]:
                raise ValueError(f"Root artifact hash mismatch: {relative}")
        print(f"{q.upper()}: root and question manifests verified")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", choices=("q1", "q2", "q4", "all"), default="all")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--online", action="store_true")
    parser.add_argument("--rebuild-manifest", action="store_true")
    args = parser.parse_args(argv)
    if args.rebuild_manifest:
        (ROOT / "data/metadata.json").write_text(json.dumps(build_manifest(), indent=2, ensure_ascii=False) + "\n")
        print("Rebuilt root metadata from verified question manifests; no data was changed.")
    if args.online:
        if args.question == "all":
            parser.error("Online refresh must select one question explicitly")
        base = ROOT / "questions" / args.question
        import os
        env = dict(os.environ, UV_CACHE_DIR=str(ROOT / ".cache/uv"), UV_PROJECT_ENVIRONMENT=str(base / ".venv"))
        subprocess.run(["uv", "run", "--locked", "--python", "3.13", "python", "data/fetch.py", "--online"], cwd=base, env=env, check=True)
    return verify_manifest(questions=("q1", "q2", "q4") if args.question == "all" else (args.question,))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Data verification failed: {error}")
