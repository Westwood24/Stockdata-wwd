"""存储模块：负责Parquet格式的本地读写。"""

import os
import pandas as pd
from config import Config


def ensure_dir(path: str) -> None:
    """确保目录存在。"""
    os.makedirs(path, exist_ok=True)


def save_to_parquet(df: pd.DataFrame, table_name: str, partition_col: str | None = None) -> str:
    """将DataFrame保存为Parquet文件。

    Args:
        df: 待保存的DataFrame。
        table_name: 表名（如 daily、stock_basic），决定存储子目录。
        partition_col: 分区列名（如 trade_date），若指定则按该列分区存储。

    Returns:
        存储路径。
    """
    save_path = os.path.join(Config.DATA_DIR, table_name)
    ensure_dir(save_path)

    if partition_col and partition_col in df.columns:
        # 按分区列写入多个文件
        for key, group in df.groupby(partition_col):
            # 处理 Timestamp 等日期类型，统一转为 YYYYMMDD 格式
            if hasattr(key, "strftime"):
                key_str = key.strftime("%Y%m%d")
            else:
                key_str = str(key).replace("-", "").replace(":", "").replace(" ", "")
            file_path = os.path.join(save_path, f"{key_str}.parquet")
            group.to_parquet(file_path, index=False)
    else:
        file_path = os.path.join(save_path, f"{table_name}.parquet")
        df.to_parquet(file_path, index=False)

    return save_path


def read_parquet(
    table_name: str,
    filters: list | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """从Parquet文件读取数据。

    Args:
        table_name: 表名。
        filters: pyarrow过滤条件列表。
        columns: 需要读取的列名列表，None表示读取全部列。

    Returns:
        合并后的DataFrame。
    """
    read_path = os.path.join(Config.DATA_DIR, table_name)
    if not os.path.isdir(read_path):
        raise FileNotFoundError(f"数据目录不存在: {read_path}")

    # 使用Parquet的partition-aware读取
    if filters:
        dataset = pd.read_parquet(read_path, filters=filters, columns=columns)
    else:
        dataset = pd.read_parquet(read_path, columns=columns)

    return dataset