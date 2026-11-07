from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import time
from datetime import date, datetime
from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
CONTRACTS = ["io2310", "io2311", "io2312", "io2401", "io2403", "io2511", "io2512", "io2601", "io2602"]
COMMON_CALENDAR_BASES = {"io2311", "io2312", "io2401", "io2403"}
COMMON_CALENDAR_DATES = {date(2023, 10, day) for day in range(23, 28)}


def third_friday(year: int, month: int) -> date:
    month_calendar = calendar.monthcalendar(year, month)
    fridays = [week[calendar.FRIDAY] for week in month_calendar if week[calendar.FRIDAY]]
    return date(year, month, fridays[2])


def expiry_from_base(base: str) -> date:
    return third_friday(2000 + int(base[2:4]), int(base[4:6]))


def numeric(value) -> float:
    return float(pd.to_numeric(value, errors="coerce"))


def load_or_fetch(path: Path, fetcher):
    if path.exists():
        return pd.read_csv(path)
    frame = fetcher()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    time.sleep(0.25)
    return frame


def select_strikes(spot: pd.DataFrame, limit: int) -> pd.DataFrame:
    columns = ["行权价", "看涨合约-标识", "看跌合约-标识"]
    selected = spot[columns].copy()
    selected["行权价"] = pd.to_numeric(selected["行权价"], errors="coerce")
    selected = selected.dropna().sort_values("行权价")
    if len(selected) <= limit:
        return selected
    positions = np.linspace(0, len(selected) - 1, limit).round().astype(int)
    return selected.iloc[sorted(set(positions))]


def fetch_contract_quotes(base: str, strikes_per_expiry: int, sleep_seconds: float) -> tuple[pd.DataFrame, list[str]]:
    spot_path = RAW / f"spot_{base}.csv"
    spot = load_or_fetch(spot_path, lambda: ak.option_cffex_hs300_spot_sina(symbol=base))
    selected = select_strikes(spot, strikes_per_expiry)
    expiry = expiry_from_base(base)
    records: list[pd.DataFrame] = []
    symbols: list[str] = []
    for _, row in selected.iterrows():
        for option_type, symbol_column in (("call", "看涨合约-标识"), ("put", "看跌合约-标识")):
            symbol = str(row[symbol_column])
            symbols.append(symbol)
            raw_path = RAW / f"daily_{symbol}.csv"
            try:
                daily = load_or_fetch(raw_path, lambda symbol=symbol: ak.option_cffex_hs300_daily_sina(symbol=symbol))
            except Exception as error:
                print(f"skip {symbol}: {type(error).__name__}: {error}")
                continue
            if daily.empty:
                continue
            daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
            daily["close"] = pd.to_numeric(daily["close"], errors="coerce")
            daily["volume"] = pd.to_numeric(daily["volume"], errors="coerce")
            daily = daily.dropna(subset=["date", "close"])
            first_date = daily["date"].min()
            window_dates = sorted(daily.loc[daily["date"] <= first_date + pd.Timedelta(days=31), "date"].dt.date.unique())
            available_dates = set(daily["date"].dt.date.unique())
            common_dates = sorted(available_dates & COMMON_CALENDAR_DATES) if base in COMMON_CALENDAR_BASES else []
            sample_dates = common_dates if len(common_dates) >= 3 else (window_dates[:5] if len(window_dates) >= 5 else sorted(available_dates)[:5])
            daily = daily[daily["date"].dt.date.isin(sample_dates)].copy()
            daily["contract_base"] = base
            daily["contract_symbol"] = symbol
            daily["option_type"] = option_type
            daily["strike"] = numeric(row["行权价"])
            daily["expiry"] = expiry.isoformat()
            records.append(daily[["date", "contract_base", "contract_symbol", "option_type", "strike", "expiry", "close", "volume"]])
            time.sleep(sleep_seconds)
    return (pd.concat(records, ignore_index=True) if records else pd.DataFrame()), symbols


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strikes-per-expiry", type=int, default=13)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()
    np.random.seed(args.seed)
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    option_frames = []
    symbols: list[str] = []
    for base in CONTRACTS:
        print(f"fetching {base}")
        frame, contract_symbols = fetch_contract_quotes(base, args.strikes_per_expiry, args.sleep)
        if not frame.empty:
            option_frames.append(frame)
        symbols.extend(contract_symbols)
    if not option_frames:
        raise RuntimeError("No historical option quotes were retrieved")
    options = pd.concat(option_frames, ignore_index=True)
    options["date"] = pd.to_datetime(options["date"]).dt.strftime("%Y-%m-%d")
    options = options.sort_values(["date", "expiry", "strike", "option_type"])
    options_path = CLEAN / "option_quotes.csv"
    options.to_csv(options_path, index=False)
    min_date = options["date"].min()
    max_date = options["date"].max()
    min_date_dt = pd.to_datetime(min_date)
    max_date_dt = pd.to_datetime(max_date)
    underlying_path = RAW / "underlying_csi300.csv"
    underlying = load_or_fetch(underlying_path, lambda: ak.stock_zh_index_daily(symbol="sh000300"))
    underlying["date"] = pd.to_datetime(underlying["date"], errors="coerce")
    underlying["close"] = pd.to_numeric(underlying["close"], errors="coerce")
    underlying = underlying.dropna(subset=["date", "close"])
    underlying = underlying[(underlying["date"] >= min_date_dt) & (underlying["date"] <= max_date_dt)][["date", "close"]]
    underlying["date"] = underlying["date"].dt.strftime("%Y-%m-%d")
    underlying.to_csv(CLEAN / "underlying.csv", index=False)
    rates_path = RAW / "shibor_all.csv"
    rates = load_or_fetch(rates_path, ak.macro_china_shibor_all)
    rates["日期"] = pd.to_datetime(rates["日期"], errors="coerce")
    rates["3M"] = pd.to_numeric(rates["3M-定价"], errors="coerce")
    rates = rates.dropna(subset=["日期", "3M"])[["日期", "3M"]]
    rates = rates[(rates["日期"] >= min_date_dt) & (rates["日期"] <= max_date_dt)]
    rates.columns = ["date", "shibor_3m_percent"]
    rates["date"] = rates["date"].dt.strftime("%Y-%m-%d")
    rates.to_csv(CLEAN / "rates.csv", index=False)
    metadata = {
        "source": {
            "options": "ak.option_cffex_hs300_spot_sina + ak.option_cffex_hs300_daily_sina",
            "underlying": "ak.stock_zh_index_daily(symbol='sh000300')",
            "rates": "ak.macro_china_shibor_all",
        },
        "retrieved_at": datetime.now().astimezone().isoformat(),
        "contracts": CONTRACTS,
        "sample_rule": "First five trading dates within 31 calendar days of each selected contract's first observation, plus a shared 2023-10-23 through 2023-10-27 calendar block for four overlapping expiries when available; thirteen evenly spaced strikes and both call and put daily closes.",
        "calendar_block": sorted(date_value.isoformat() for date_value in COMMON_CALENDAR_DATES),
        "date_range": [min_date, max_date],
        "expiry_count": int(options["expiry"].nunique()),
        "sample_date_count": int(options["date"].nunique()),
        "quote_rows": int(len(options)),
        "artifacts": {},
    }
    for filename in ["option_quotes.csv", "underlying.csv", "rates.csv"]:
        path = CLEAN / filename
        metadata["artifacts"][f"data/clean/{filename}"] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    (CLEAN / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(json.dumps({"quote_rows": len(options), "expiry_count": options["expiry"].nunique(), "sample_date_count": options["date"].nunique(), "date_range": [min_date, max_date]}, indent=2))


if __name__ == "__main__":
    main()
