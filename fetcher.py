"""数据获取模块：通过Tushare Pro API拉取股票数据。"""

import time
from typing import Any

import pandas as pd
import tushare as ts
import requests
from config import Config

# 最大重试次数（减少以加快失败速度，由批量脚本统一重试）
MAX_RETRIES = 3
# 基础重试间隔（秒），指数退避
BASE_RETRY_DELAY = 2


class StockFetcher:
    """Tushare数据获取器。"""

    def __init__(self) -> None:
        Config.validate()
        self._pro = ts.pro_api(Config.TUSHARE_TOKEN)
        # 如果配置了自定义 API 端点，则使用镜像地址
        if Config.TUSHARE_API_URL:
            self._pro._DataApi__http_url = Config.TUSHARE_API_URL
        # 增加 HTTP 超时时间（默认可能太短）
        self._pro._DataApi__timeout = 60

    def _api_call(self, method: str, **kwargs: Any) -> pd.DataFrame:
        """封装API调用，加入速率控制和重试机制。

        Args:
            method: Tushare API方法名。
            **kwargs: 传递给API的参数。

        Returns:
            API返回的DataFrame。

        Raises:
            RuntimeError: 所有重试均失败。
        """
        time.sleep(0.3)
        func = getattr(self._pro, method)

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result: pd.DataFrame = func(**kwargs)
                return result
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
                OSError,
            ) as e:
                last_error = e
                err_type = type(e).__name__
                if attempt < MAX_RETRIES:
                    wait = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    print(f"  [Retry {attempt}/{MAX_RETRIES}] {err_type}, waiting {wait}s...", flush=True)
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"API调用失败（已重试 {MAX_RETRIES} 次）: {err_type}: {e}"
                    ) from e

        # 理论上不会到这里
        raise RuntimeError(f"API调用失败: {last_error}")

    def fetch_daily(
        self,
        ts_code: str = "",
        trade_date: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        """获取日线行情。

        Args:
            ts_code: 股票代码，如 '000001.SZ'。为空则获取全部。
            trade_date: 交易日期，格式 YYYYMMDD。
            start_date: 开始日期。
            end_date: 结束日期。

        Returns:
            日线行情DataFrame。
        """
        kwargs: dict[str, Any] = {}
        if ts_code:
            kwargs["ts_code"] = ts_code
        if trade_date:
            kwargs["trade_date"] = trade_date
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date

        df = self._api_call("daily", **kwargs)
        if not df.empty:
            # 将trade_date转为datetime类型便于后续处理
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        return df

    def fetch_adj_factor(
        self,
        ts_code: str = "",
        trade_date: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        """获取复权因子。

        Args:
            ts_code: 股票代码。为空则获取全部。
            trade_date: 交易日期，格式 YYYYMMDD。
            start_date: 开始日期。
            end_date: 结束日期。

        Returns:
            复权因子DataFrame，包含 ts_code, trade_date, adj_factor。
        """
        kwargs: dict[str, Any] = {}
        if ts_code:
            kwargs["ts_code"] = ts_code
        if trade_date:
            kwargs["trade_date"] = trade_date
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date

        df = self._api_call("adj_factor", **kwargs)
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        return df

    def fetch_daily_with_adj(
        self,
        ts_code: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        """获取日线行情并合并复权因子。

        将 daily 与 adj_factor 按 ts_code + trade_date 左连接，
        结果包含所有日线字段 + adj_factor 列。

        Args:
            ts_code: 股票代码。为空则获取全部。
            start_date: 开始日期。
            end_date: 结束日期。

        Returns:
            合并后的DataFrame。
        """
        # 并行获取日线和复权因子
        df_daily = self.fetch_daily(
            ts_code=ts_code, start_date=start_date, end_date=end_date
        )
        if df_daily.empty:
            return df_daily

        df_adj = self.fetch_adj_factor(
            ts_code=ts_code, start_date=start_date, end_date=end_date
        )

        if df_adj.empty:
            # 没有复权因子，添加空列
            df_daily["adj_factor"] = None
            return df_daily

        # 合并
        df_merged = df_daily.merge(
            df_adj[["ts_code", "trade_date", "adj_factor"]],
            on=["ts_code", "trade_date"],
            how="left",
        )
        return df_merged

    def fetch_stock_basic(self, exchange: str = "", list_status: str = "L") -> pd.DataFrame:
        """获取股票基本信息。

        Args:
            exchange: 交易所代码，如 'SZSE'（深交所）、'SSE'（上交所）。
            list_status: 上市状态：L上市、D退市、P暂停上市。

        Returns:
            股票基本信息DataFrame。
        """
        kwargs: dict[str, Any] = {"list_status": list_status}
        if exchange:
            kwargs["exchange"] = exchange
        return self._api_call("stock_basic", **kwargs)

    def fetch_trade_cal(
        self, exchange: str = "SSE", start_date: str = "", end_date: str = ""
    ) -> pd.DataFrame:
        """获取交易日历。

        Args:
            exchange: 交易所 SSE上交所 SZSE深交所。
            start_date: 开始日期。
            end_date: 结束日期。

        Returns:
            交易日历DataFrame。
        """
        kwargs: dict[str, Any] = {"exchange": exchange}
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        return self._api_call("trade_cal", **kwargs)