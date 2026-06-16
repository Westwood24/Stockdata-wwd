"""主入口：编排数据拉取与存储流程。"""

import argparse
from datetime import datetime, timedelta

import pandas as pd

from config import Config
from fetcher import StockFetcher
from storage import save_to_parquet, read_parquet


def cmd_daily(args: argparse.Namespace) -> None:
    """获取日线行情并存储。"""
    fetcher = StockFetcher()

    start_date = args.start or (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    end_date = args.end or datetime.now().strftime("%Y%m%d")

    print(f"正在获取日线行情: {start_date} ~ {end_date}")
    if args.code:
        print(f"股票代码: {args.code}")

    df = fetcher.fetch_daily(
        ts_code=args.code or "",
        start_date=start_date,
        end_date=end_date,
    )

    if df.empty:
        print("未获取到数据")
        return

    print(f"获取到 {len(df)} 条记录")

    path = save_to_parquet(df, "daily", partition_col="trade_date")
    print(f"已保存至: {path}")


def cmd_basic(args: argparse.Namespace) -> None:
    """获取股票基本信息并存储。"""
    fetcher = StockFetcher()

    print("正在获取股票基本信息...")
    df = fetcher.fetch_stock_basic(exchange=args.exchange or "", list_status=args.status)

    if df.empty:
        print("未获取到数据")
        return

    print(f"获取到 {len(df)} 条记录")
    path = save_to_parquet(df, "stock_basic")
    print(f"已保存至: {path}")


def cmd_trade_cal(args: argparse.Namespace) -> None:
    """获取交易日历并存储。"""
    fetcher = StockFetcher()
    this_year = datetime.now().year

    start_date = args.start or f"{this_year}0101"
    end_date = args.end or f"{this_year}1231"

    print(f"正在获取交易日历: {start_date} ~ {end_date}")
    df = fetcher.fetch_trade_cal(start_date=start_date, end_date=end_date)

    if df.empty:
        print("未获取到数据")
        return

    print(f"获取到 {len(df)} 条记录")
    path = save_to_parquet(df, "trade_cal")
    print(f"已保存至: {path}")


def cmd_query(args: argparse.Namespace) -> None:
    """查询本地Parquet数据。"""
    columns = args.columns.split(",") if args.columns else None

    filters = None
    if args.filter_start and args.filter_end:
        filters = [
            ("trade_date", ">=", pd.Timestamp(args.filter_start)),
            ("trade_date", "<=", pd.Timestamp(args.filter_end)),
        ]
    elif args.filter_start:
        filters = [("trade_date", ">=", pd.Timestamp(args.filter_start))]

    df = read_parquet(args.table, filters=filters, columns=columns)
    print(f"查询结果: {len(df)} 条记录")
    print(df.head(args.limit) if args.limit else df.to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="股票数据获取与存储工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 日线行情
    daily_parser = subparsers.add_parser("daily", help="获取日线行情")
    daily_parser.add_argument("--code", "-c", default="", help="股票代码，如 000001.SZ")
    daily_parser.add_argument("--start", "-s", default="", help="开始日期 YYYYMMDD")
    daily_parser.add_argument("--end", "-e", default="", help="结束日期 YYYYMMDD")

    # 股票基本信息
    basic_parser = subparsers.add_parser("basic", help="获取股票基本信息")
    basic_parser.add_argument("--exchange", default="", help="交易所: SSE/SZSE")
    basic_parser.add_argument("--status", default="L", help="上市状态: L/D/P")

    # 交易日历
    cal_parser = subparsers.add_parser("calendar", help="获取交易日历")
    cal_parser.add_argument("--start", "-s", default="", help="开始日期 YYYYMMDD")
    cal_parser.add_argument("--end", "-e", default="", help="结束日期 YYYYMMDD")

    # 本地查询
    query_parser = subparsers.add_parser("query", help="查询本地Parquet数据")
    query_parser.add_argument("--table", "-t", required=True, help="表名: daily/stock_basic/trade_cal")
    query_parser.add_argument("--columns", default="", help="查询列，逗号分隔")
    query_parser.add_argument("--filter-start", default="", help="起始日期 YYYY-MM-DD")
    query_parser.add_argument("--filter-end", default="", help="结束日期 YYYY-MM-DD")
    query_parser.add_argument("--limit", "-n", type=int, default=20, help="显示行数")

    args = parser.parse_args()

    if args.command == "daily":
        cmd_daily(args)
    elif args.command == "basic":
        cmd_basic(args)
    elif args.command == "calendar":
        cmd_trade_cal(args)
    elif args.command == "query":
        cmd_query(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()