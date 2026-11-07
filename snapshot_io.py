"""Standard-library verification shared by the separated question pipelines."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError(f"Artifact path escapes its question: {relative}")
    return target


def verify_manifest(base: Path, manifest: Path | dict) -> dict[str, Path]:
    data = manifest if isinstance(manifest, dict) else json.loads(manifest.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError(f"No artifacts declared in {manifest}")
    verified = {}
    for relative, spec in artifacts.items():
        path = safe_path(base, relative)
        if sha256(path) != spec["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {path}")
        if path.stat().st_size != spec["bytes"]:
            raise ValueError(f"Byte-length mismatch: {path}")
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(spec["schema"]):
                raise ValueError(f"Schema/header mismatch: {path}")
            rows = list(reader)
        if len(rows) != spec["rows"]:
            raise ValueError(f"Row-count mismatch: {path}")
        for row in rows:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row in {path}")
            for field, kind in spec["schema"].items():
                value = row[field]
                if kind.startswith("date"):
                    if date.fromisoformat(value).isoformat() != value:
                        raise ValueError(f"Non-ISO date in {path}: {value}")
                elif kind.startswith("int"):
                    int(value)
                elif kind.startswith("float") and not math.isfinite(float(value)):
                    raise ValueError(f"Nonfinite value in {path}: {field}")
        if rows and "date" in rows[0]:
            dates = [row["date"] for row in rows]
            if min(dates) != spec["first_date"] or max(dates) != spec["last_date"]:
                raise ValueError(f"Date coverage mismatch: {path}")
            if dates != sorted(dates):
                raise ValueError(f"Dates are not ascending: {path}")
        if rows and "year" in rows[0] and sorted({int(r["year"]) for r in rows}) != spec["years"]:
            raise ValueError(f"Year coverage mismatch: {path}")
        keys = spec.get("unique_key", [])
        if keys and len({tuple(row[key] for key in keys) for row in rows}) != len(rows):
            raise ValueError(f"Duplicate observation key in {path}")
        verified[relative] = path
    return verified


def enrich_manifest(base: Path, manifest: Path) -> None:
    """Add factual schema/coverage fields without changing source provenance."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for relative, spec in data["artifacts"].items():
        path = safe_path(base, relative)
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise ValueError(f"Empty snapshot: {path}")
        strings = {"contract_base", "contract_symbol", "option_type", "node_name", "region", "flow", "source"}
        integers = {"year", "node_code", "reporter_code", "partner_code", "is_china"}
        spec.update(sha256=sha256(path), bytes=path.stat().st_size, rows=len(rows))
        spec["schema"] = {key: "date (YYYY-MM-DD)" if key in ("date", "expiry") else "string" if key in strings else "int64" if key in integers else "float64" for key in rows[0]}
        if "date" in rows[0]:
            spec.update(first_date=min(r["date"] for r in rows), last_date=max(r["date"] for r in rows))
            spec["unique_key"] = ["date", "expiry", "strike", "option_type"] if "expiry" in rows[0] else ["date"]
        elif "year" in rows[0]:
            spec["years"] = sorted({int(r["year"]) for r in rows})
            spec["unique_key"] = ["year", "reporter_code", "partner_code"]
        else:
            spec["unique_key"] = ["node_code"]
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
