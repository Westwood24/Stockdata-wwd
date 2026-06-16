"""配置模块：从环境变量读取Tushare Token及其他配置项。"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """项目配置。"""

    TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "")
    # 自定义 API 端点（镜像地址），为空则使用默认地址
    TUSHARE_API_URL: str = os.getenv("TUSHARE_API_URL", "")
    # 数据存储根目录
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "data")

    @classmethod
    def validate(cls) -> None:
        """校验必要配置是否已设置。"""
        if not cls.TUSHARE_TOKEN:
            raise ValueError(
                "未设置 TUSHARE_TOKEN，请在 .env 文件中配置或设置环境变量"
            )