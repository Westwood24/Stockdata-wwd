# -*- coding: utf-8 -*-
"""前复权计算脚本：基于 adj_factor 将日线数据转换为前复权价格。

前复权公式：
    adj_price = price * adj_factor / latest_adj_factor

其中 latest_adj_factor 是该股票在数据集内最新交易日的复权因子。
"""

import sys
import os
import time
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, "d:/Trae test/stock data")
from config import Config

DAILY_DIR = os.path.join(Config.DATA_DIR, "daily")
QFQ_DIR = os.path.join(Config.DATA_DIR, "daily_qfq")

# 需要复权的价格列
PRICE_COLS = ["open", "high", "low", "close", "pre_close"]


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


def compute_latest_adj_factors(daily_dir: str) -> pd.Series:
    """扫描所有日线数据，计算每只股票的最新（最大）复权因子。

    Returns:
        Series: index=ts_code, value=latest_adj_factor
    """
    log("Step 1: Scanning all parquet files to find latest adj_factor per stock...")
    dataset = pq.ParquetDataset(daily_dir)

    # 读取所有 ts_code + trade_date + adj_factor
    all_data = dataset.read(columns=["ts_code", "trade_date", "adj_factor"])
    df = all_data.to_pandas()
    log(f"  Total rows: {len(df)}")

    # 过滤掉没有 adj_factor 的行
    df_valid = df.dropna(subset=["adj_factor"])
    log(f"  Rows with adj_factor: {len(df_valid)}")

    if df_valid.empty:
        log("  WARNING: No adj_factor data found, cannot compute adjusted prices.")
        return pd.Series(dtype=float)

    # 每个股票取 trade_date 最大（最新）的 adj_factor
    latest = df_valid.groupby("ts_code").apply(
        lambda g: g.loc[g["trade_date"].idxmax(), "adj_factor"],
        include_groups=False,
    )
    latest = latest.astype(float)
    log(f"  Unique stocks with adj_factor: {len(latest)}")
    return latest


def process_file(file_path: str, latest_adj: pd.Series, output_dir: str) -> int:
    """处理单个 parquet 文件，计算前复权价格并保存。

    Returns:
        处理的行数。
    """
    df = pd.read_parquet(file_path)

    if df.empty or "adj_factor" not in df.columns:
        return 0

    # 只处理有 adj_factor 的行
    mask = df["adj_factor"].notna()
    if not mask.any():
        return len(df)

    # 获取每只股票的最新复权因子
    stock_latest = df.loc[mask, "ts_code"].map(latest_adj)
    stock_latest = stock_latest.astype(float)

    # 计算复权比例
    ratio = df.loc[mask, "adj_factor"].astype(float) / stock_latest

    # 前复权价格列
    for col in PRICE_COLS:
        if col in df.columns:
            adj_col = f"{col}_adj"
            # 先拷贝原列
            df[adj_col] = df[col].astype(float)
            df.loc[mask, adj_col] = df.loc[mask, col].astype(float) * ratio

    # 保存
    rel_path = os.path.relpath(file_path, DAILY_DIR)
    out_path = os.path.join(output_dir, rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_parquet(out_path, index=False)

    return len(df)


def main():
    start_time = time.time()

    if not os.path.isdir(DAILY_DIR):
        log(f"ERROR: Daily data directory not found: {DAILY_DIR}")
        sys.exit(1)

    # Step 1: 计算每只股票的最新复权因子
    latest_adj = compute_latest_adj_factors(DAILY_DIR)
    if latest_adj.empty:
        log("Cannot proceed without adj_factor data.")
        sys.exit(1)

    log(f"\nStep 2: Computing adjusted prices for each file...")

    # Step 2: 遍历所有 parquet 文件，计算前复权
    total_rows = 0
    parquet_files = []
    for root, dirs, files in os.walk(DAILY_DIR):
        for f in files:
            if f.endswith(".parquet"):
                parquet_files.append(os.path.join(root, f))

    parquet_files.sort()
    total_files = len(parquet_files)
    log(f"  Files to process: {total_files}")

    for i, file_path in enumerate(parquet_files, 1):
        try:
            rows = process_file(file_path, latest_adj, QFQ_DIR)
            total_rows += rows
            if i % 500 == 0 or i == total_files:
                elapsed = time.time() - start_time
                log(f"  [{i}/{total_files}] {total_rows} rows processed "
                    f"(elapsed: {elapsed:.0f}s)")
        except Exception as e:
            log(f"  [{i}/{total_files}] ERROR {file_path}: {e}")

    elapsed = time.time() - start_time
    log(f"\n===== Done =====")
    log(f"Total rows processed: {total_rows}")
    log(f"Output: {QFQ_DIR}")
    log(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
