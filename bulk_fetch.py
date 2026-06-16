# -*- coding: utf-8 -*-
"""分批拉取日线行情+复权因子（2010年1月 ~ 2026年6月）。
每批3天，保证稳定性。失败批次自动重试。
"""

import sys
import time
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, "d:/Trae test/stock data")

from fetcher import StockFetcher
from storage import save_to_parquet

START_DATE = datetime(2010, 1, 1)
END_DATE = datetime(2026, 6, 30)
CHUNK_DAYS = 3
MAX_ROUNDS = 3


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


def date_ranges():
    current = START_DATE
    while current <= END_DATE:
        batch_end = min(current + timedelta(days=CHUNK_DAYS - 1), END_DATE)
        label = f"{current.strftime('%Y%m%d')}-{batch_end.strftime('%Y%m%d')}"
        yield current.strftime("%Y%m%d"), batch_end.strftime("%Y%m%d"), label
        current = batch_end + timedelta(days=1)


def fetch_and_save(fetcher, start_date, end_date, label) -> int:
    """拉取并保存一批数据。"""
    df = fetcher.fetch_daily(start_date=start_date, end_date=end_date)
    if df.empty:
        return 0

    # 尝试拉复权因子
    try:
        df_adj = fetcher.fetch_adj_factor(start_date=start_date, end_date=end_date)
        if not df_adj.empty:
            df = df.merge(
                df_adj[["ts_code", "trade_date", "adj_factor"]],
                on=["ts_code", "trade_date"],
                how="left",
            )
        else:
            df["adj_factor"] = None
    except Exception:
        df["adj_factor"] = None

    save_to_parquet(df, "daily", partition_col="trade_date")
    return len(df)


def process_batches(batches, fetcher, total_records, round_num):
    total = len(batches)
    failed = []

    for i, (start_date, end_date, label) in enumerate(batches, 1):
        try:
            count = fetch_and_save(fetcher, start_date, end_date, label)
            if count == 0:
                log(f"[R{round_num}][{i}/{total}] [{label}] no data")
                continue
            total_records += count
            log(f"[R{round_num}][{i}/{total}] [{label}] OK {count} recs "
                f"(total: {total_records})")
        except Exception as e:
            log(f"[R{round_num}][{i}/{total}] [{label}] FAIL {type(e).__name__}")
            failed.append((start_date, end_date, label))
            time.sleep(1)

    return total_records, failed


def main():
    fetcher = StockFetcher()
    total_records = 0
    start_time = time.time()

    all_batches = list(date_ranges())
    log(f"Total batches: {len(all_batches)} ({CHUNK_DAYS} days each, max {MAX_ROUNDS} rounds)")

    remaining = all_batches
    for round_num in range(1, MAX_ROUNDS + 1):
        if not remaining:
            break
        log(f"\n--- Round {round_num}: {len(remaining)} batches ---")
        total_records, remaining = process_batches(
            remaining, fetcher, total_records, round_num
        )
        if remaining:
            log(f"  Failed: {len(remaining)}, retrying after pause...")
            time.sleep(5)

    elapsed = time.time() - start_time
    log(f"\n===== Done =====")
    log(f"Total records: {total_records}")
    log(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    if remaining:
        log(f"Still failed ({len(remaining)}):")
        for _, _, label in remaining[:10]:
            log(f"  {label}")


if __name__ == "__main__":
    main()
