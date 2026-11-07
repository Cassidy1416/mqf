"""Fetch and verify the Q2 data snapshots for the MQF project.

Offline mode (the default) verifies the committed clean snapshots under
data/clean/q2 against data/metadata.json: SHA-256, row count, header,
and strictly ascending unique dates, over the manifest window.

Online mode uses the exact AKShare functions and parameters recorded in
the manifest to refresh the raw vendor tables under data/raw/q2. It never
replaces an existing raw file and never touches the committed clean
snapshots.

All paths are resolved relative to this file so the module also works
when imported by file path from code/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = REPO_ROOT / "data" / "metadata.json"

console = Console()


class VerificationError(RuntimeError):
    """A snapshot or the manifest does not match the recorded metadata."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("q2"), dict):
        raise VerificationError("manifest has no 'q2' section")
    datasets = manifest["q2"].get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise VerificationError("manifest 'q2.datasets' is missing or empty")
    for name, spec in datasets.items():
        missing = [key for key in ("label", "access", "raw", "clean") if key not in spec]
        if missing:
            raise VerificationError(f"{name}: manifest entry missing {', '.join(missing)}")
        access = spec["access"]
        for key in ("package", "function", "parameters"):
            if key not in access:
                raise VerificationError(f"{name}: manifest access entry missing '{key}'")
        if access["package"] != "akshare":
            raise VerificationError(f"{name}: online mode only supports 'akshare', found '{access['package']}'")
        if not isinstance(access["parameters"], dict):
            raise VerificationError(f"{name}: manifest access parameters must be an object")
        for stage in ("raw", "clean"):
            for key in ("path", "sha256", "rows"):
                if key not in spec[stage]:
                    raise VerificationError(f"{name}: manifest {stage} entry missing '{key}'")
        clean = spec["clean"]
        for key in ("schema", "first_date", "last_date"):
            if key not in clean:
                raise VerificationError(f"{name}: manifest clean entry missing '{key}'")
        if not isinstance(clean["schema"], dict) or not clean["schema"]:
            raise VerificationError(f"{name}: manifest clean schema is empty")


def load_manifest(path: Path = METADATA_PATH) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VerificationError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(f"manifest {path} is not valid JSON: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        rows = [row for row in reader if row]
    if header is None:
        raise VerificationError(f"{path} is empty")
    return header, rows


def _verify_clean_dataset(name: str, spec: dict) -> dict:
    clean = spec["clean"]
    path = REPO_ROOT / clean["path"]
    if not path.is_file():
        raise VerificationError(f"{name}: clean snapshot missing, expected {path}")
    actual_sha = sha256_file(path)
    if actual_sha != clean["sha256"]:
        raise VerificationError(
            f"{name}: SHA-256 mismatch for {clean['path']}:\n"
            f"  expected {clean['sha256']}\n"
            f"  found   {actual_sha}\n"
            "the file no longer matches the committed snapshot; restore it before calibrating"
        )
    header, rows = _read_csv(path)
    expected_header = list(clean["schema"])
    if header != expected_header:
        raise VerificationError(f"{name}: header mismatch in {clean['path']}: expected {expected_header}, found {header}")
    if len(rows) != clean["rows"]:
        raise VerificationError(f"{name}: {clean['path']} holds {len(rows)} data rows, manifest declares {clean['rows']}")
    try:
        dates = [date.fromisoformat(row[0]) for row in rows]
    except (ValueError, IndexError) as exc:
        raise VerificationError(f"{name}: column 0 of {clean['path']} is not an ISO date (YYYY-MM-DD) throughout: {exc}") from exc
    if any(next_day <= day for day, next_day in zip(dates, dates[1:])):
        raise VerificationError(f"{name}: dates in {clean['path']} are not strictly ascending and unique")
    first, last = dates[0].isoformat(), dates[-1].isoformat()
    if first != clean["first_date"] or last != clean["last_date"]:
        raise VerificationError(
            f"{name}: coverage mismatch in {clean['path']}: manifest declares "
            f"{clean['first_date']}..{clean['last_date']}, file holds {first}..{last}"
        )
    close_idx = header.index("close") if "close" in header else None
    if close_idx is not None:
        for line_no, row in enumerate(rows, start=2):
            try:
                close = float(row[close_idx])
            except (ValueError, IndexError) as exc:
                raise VerificationError(f"{name}: non-numeric close at {clean['path']} line {line_no}: {exc}") from exc
            if not close > 0.0:
                raise VerificationError(f"{name}: nonpositive close at {clean['path']} line {line_no}")
    return {"path": path, "dates": dates}


def _verify_cross_dataset_checks(manifest: dict, results: dict[str, dict]) -> None:
    checks = manifest["q2"].get("verification", {})
    datasets = manifest["q2"]["datasets"]
    market_names = [name for name in results if "close" in datasets[name]["clean"]["schema"]]
    count = checks.get("market_trading_dates")
    if isinstance(count, int):
        for name in market_names:
            if len(results[name]["dates"]) != count:
                raise VerificationError(f"{name}: {len(results[name]['dates'])} market dates, manifest declares {count}")
    if checks.get("market_calendars_match") and len(market_names) >= 2:
        reference = results[market_names[0]]["dates"]
        for name in market_names[1:]:
            if results[name]["dates"] != reference:
                first_diff = next((day for day, other in zip(reference, results[name]["dates"]) if day != other), None)
                raise VerificationError(
                    f"{name}: market calendar differs from {market_names[0]} (first difference near {first_diff})"
                )
    if checks.get("shibor_complete_on_market_dates") and market_names:
        market_days = set()
        for name in market_names:
            market_days.update(results[name]["dates"])
        shibor_days = set()
        for name, result in results.items():
            if name not in market_names:
                shibor_days.update(result["dates"])
        missing = sorted(market_days - shibor_days)
        if missing:
            head = ", ".join(day.isoformat() for day in missing[:5])
            tail = " ..." if len(missing) > 5 else ""
            raise VerificationError(f"shibor has no fixing on market date(s) {head}{tail}")


def verify_q2_snapshots(manifest: dict | None = None) -> dict[str, Path]:
    manifest = load_manifest() if manifest is None else manifest
    paths: dict[str, Path] = {}
    results: dict[str, dict] = {}
    for name, spec in manifest["q2"]["datasets"].items():
        result = _verify_clean_dataset(name, spec)
        results[name] = result
        paths[name] = result["path"]
    _verify_cross_dataset_checks(manifest, results)
    return paths


def print_coverage(manifest: dict) -> None:
    table = Table(title="Q2 committed snapshot coverage")
    for column in ("Dataset", "Label", "Rows", "First date", "Last date"):
        table.add_column(column)
    for name, spec in manifest["q2"]["datasets"].items():
        clean = spec["clean"]
        table.add_row(name, spec["label"], str(clean["rows"]), clean["first_date"], clean["last_date"])
    console.print(table)


def fetch_online(manifest: dict) -> None:
    try:
        import akshare as ak
    except ImportError as exc:
        console.print(f"[yellow]--online cannot import akshare ({exc}); using the committed offline snapshots instead.[/]")
        return
    expected = {spec["access"].get("version") for spec in manifest["q2"]["datasets"].values()}
    for version in sorted(filter(None, expected)):
        if ak.__version__ != version:
            console.print(f"[yellow]warning: akshare {ak.__version__} is installed, the manifest expects {version}[/]")
    for name, spec in manifest["q2"]["datasets"].items():
        access = spec["access"]
        function = getattr(ak, access["function"], None)
        if function is None:
            raise VerificationError(f"{name}: akshare {ak.__version__} has no function '{access['function']}'")
        raw_path = REPO_ROOT / spec["raw"]["path"]
        if raw_path.is_file():
            console.print(f"[cyan]reuse  [/] {raw_path.relative_to(REPO_ROOT)} already exists, not replacing")
            continue
        try:
            table = function(**access["parameters"])
        except Exception as exc:
            console.print(f"[yellow]problem:[/] {access['function']} failed for {name}: {exc}")
            console.print("[yellow]falling back to the committed offline snapshots.[/]")
            return
        if table is None or len(table) == 0:
            console.print(f"[yellow]problem:[/] {access['function']} returned no rows for {name}; using offline snapshots.[/]")
            return
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(raw_path, index=False)
        console.print(f"[green]fetched[/] {name}: {len(table)} rows -> {raw_path.relative_to(REPO_ROOT)}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch (online) or verify (offline, default) the Q2 data snapshots.")
    parser.add_argument("--question", choices=("q2",), default="q2", help="dataset bundle to handle")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="verify the committed clean snapshots (default)")
    mode.add_argument("--online", action="store_true", help="refresh raw vendor tables, then verify the committed clean snapshots")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        manifest = load_manifest()
    except VerificationError as error:
        console.print(f"[red]manifest error:[/] {error}")
        raise SystemExit(2)
    if args.online:
        fetch_online(manifest)
    try:
        verify_q2_snapshots(manifest)
    except VerificationError as error:
        console.print(f"[red]verification failed:[/] {error}")
        raise SystemExit(1)
    print_coverage(manifest)


if __name__ == "__main__":
    main()
