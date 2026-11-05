from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
API = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
CHINA = 156

COUNTRY_NAMES = {
    32: "Argentina", 36: "Australia", 40: "Austria", 56: "Belgium",
    76: "Brazil", 124: "Canada", 152: "Chile", 156: "China",
    170: "Colombia", 191: "Croatia", 203: "Czechia", 208: "Denmark",
    246: "Finland", 250: "France", 276: "Germany", 344: "Hong Kong",
    356: "India", 360: "Indonesia", 364: "Iran", 372: "Ireland",
    376: "Israel", 380: "Italy", 392: "Japan", 398: "Kazakhstan",
    410: "South Korea", 458: "Malaysia", 484: "Mexico", 528: "Netherlands",
    554: "New Zealand", 566: "Nigeria", 578: "Norway", 586: "Pakistan",
    604: "Peru", 608: "Philippines", 616: "Poland", 620: "Portugal",
    634: "Qatar", 643: "Russia", 682: "Saudi Arabia", 702: "Singapore",
    710: "South Africa", 724: "Spain", 752: "Sweden", 756: "Switzerland",
    764: "Thailand", 792: "Türkiye", 804: "Ukraine", 826: "United Kingdom",
    834: "Tanzania", 842: "United States", 860: "Uzbekistan", 704: "Vietnam",
}

REGIONS = {
    "East Asia": {156, 344, 392, 410, 704},
    "South Asia": {356, 586},
    "Southeast Asia": {360, 458, 608, 702, 764},
    "Europe": {40, 56, 191, 203, 208, 246, 250, 276, 372, 380, 528, 616, 620, 643, 724, 752, 756, 804, 826},
    "North America": {124, 484, 842},
    "South America": {32, 76, 152, 170, 604},
    "Middle East": {364, 376, 634, 682},
    "Africa": {566, 729, 710, 834},
    "Central Asia": {398, 860},
    "Oceania": {36, 554},
}


def parse_years(value: str) -> list[int]:
    if ":" in value:
        start, end = (int(part) for part in value.split(":", maxsplit=1))
        return list(range(start, end + 1))
    return [int(part) for part in value.split(",")]


def country_name(code: int) -> str:
    return COUNTRY_NAMES.get(code, f"Partner {code}")


def country_region(code: int) -> str:
    for region, codes in REGIONS.items():
        if code in codes:
            return region
    return "Other"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def request_json(params: dict[str, str | int], target: Path, pause: float) -> dict:
    if target.exists():
        return json.loads(target.read_text())
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{API}?{urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": "ap26-q4-trade-network/1.0"})
            with urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            time.sleep(pause)
            return payload
        except Exception as error:
            last_error = error
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade request failed: {url}") from last_error


def rows_for(payload: dict) -> list[dict]:
    return payload.get("data", [])


def value(row: dict) -> float:
    raw = row.get("primaryValue")
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def rank_china_partners(year: int, top_partners: int, pause: float) -> list[int]:
    scores: dict[int, float] = {}
    for flow in ("X", "M"):
        target = RAW / f"china_{year}_{flow}.json"
        payload = request_json(
            {"reporterCode": CHINA, "period": year, "flowCode": flow, "cmdCode": "TOTAL", "partner2Code": 0, "customsCode": "C00"},
            target,
            pause,
        )
        for row in rows_for(payload):
            partner = int(row.get("partnerCode", -1))
            if partner not in {0, CHINA}:
                scores[partner] = scores.get(partner, 0.0) + value(row)
    return [code for code, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_partners]]


def build_snapshot(years: list[int], top_partners: int, pause: float) -> tuple[list[dict], list[int]]:
    anchor_year = max(years)
    partners = rank_china_partners(anchor_year, top_partners, pause)
    nodes = [CHINA, *partners]
    node_set = set(nodes)
    output: list[dict] = []
    for year in years:
        for reporter in nodes:
            target = RAW / f"reporter_{reporter}_{year}_X.json"
            payload = request_json(
                {"reporterCode": reporter, "period": year, "flowCode": "X", "cmdCode": "TOTAL", "partner2Code": 0, "customsCode": "C00"},
                target,
                pause,
            )
            for row in rows_for(payload):
                partner = int(row.get("partnerCode", -1))
                if partner in node_set and partner != reporter:
                    output.append({
                        "year": year,
                        "reporter_code": reporter,
                        "partner_code": partner,
                        "trade_value_usd": value(row),
                        "flow": "exports",
                        "source": "UN Comtrade preview API",
                    })
    return output, nodes


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", default="2014:2023")
    parser.add_argument("--top-partners", type=int, default=20)
    parser.add_argument("--pause", type=float, default=0.12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    years = parse_years(args.years)
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    rows, nodes = build_snapshot(years, args.top_partners, args.pause)
    flow_path = CLEAN / "trade_flows.csv"
    node_path = CLEAN / "node_metadata.csv"
    metadata_path = CLEAN / "metadata.json"
    write_csv(flow_path, rows, ["year", "reporter_code", "partner_code", "trade_value_usd", "flow", "source"])
    node_rows = [{"node_code": code, "node_name": country_name(code), "region": country_region(code), "is_china": int(code == CHINA)} for code in nodes]
    write_csv(node_path, node_rows, ["node_code", "node_name", "region", "is_china"])
    metadata = {
        "source": API,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "years": years,
        "top_partners": args.top_partners,
        "anchor_year": max(years),
        "flow_definition": "Annual reported exports among China and its anchor-year top trade partners; primaryValue in USD.",
        "node_count": len(nodes),
        "edge_rows": len(rows),
        "artifacts": {},
    }
    for path in (flow_path, node_path):
        metadata["artifacts"][str(path.relative_to(ROOT))] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(json.dumps({"years": years, "nodes": len(nodes), "rows": len(rows), "metadata": str(metadata_path)}, indent=2))


if __name__ == "__main__":
    main()
