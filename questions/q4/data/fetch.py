"""Verify committed snapshots offline, or stage an explicit online refresh."""
from __future__ import annotations
import argparse
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
from snapshot_io import verify_manifest


def verify_snapshots(clean_dir=None):
    clean = Path(clean_dir) if clean_dir is not None else ROOT / "data/clean"
    verified = verify_manifest(clean.parents[1], clean / "metadata.json")
    print(f"Verified {len(verified)} committed clean snapshots (hashes, schema, counts and coverage).")
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--offline", action="store_true")
    modes.add_argument("--online", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("seed must be nonnegative")
    if args.online:
        stage = ROOT / "data/raw/refresh" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        spec = importlib.util.spec_from_file_location("vendor_refresh", ROOT / "data/vendor_fetch.py")
        vendor = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(vendor)
            vendor.ROOT, vendor.RAW, vendor.CLEAN = stage, stage / "raw", stage / "clean"
            old = sys.argv
            sys.argv = [str(ROOT / "data/vendor_fetch.py"), "--seed", str(args.seed)]
            if "q1" == ROOT.name:
                sys.argv.append("--refresh")
            try:
                vendor.main()
            finally:
                sys.argv = old
            print(f"Staged refresh at {stage}; committed snapshots were not replaced.")
        except Exception as error:
            print(f"Online source unavailable ({error}); using committed offline snapshots.")
    return verify_snapshots()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Snapshot verification failed: {error}")
