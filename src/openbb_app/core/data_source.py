import logging
from abc import ABC, abstractmethod
from typing import Any

from openbb import obb

try:
    from mysharelib.tools import normalize_symbol
except ImportError:
    normalize_symbol = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)


def normalize_symbol_for_yfinance(symbol: str) -> str:
    """Convert stock symbols for Yahoo Finance format."""
    if normalize_symbol is None:
        logger.warning("mysharelib not available, using original symbol")
        return symbol

    try:
        symbol_f, *_ = normalize_symbol(symbol)
        if not symbol_f or "." not in symbol_f:
            return symbol_f if symbol_f else symbol

        parts = symbol_f.split(".")
        if len(parts) != 2:
            return symbol_f

        prefix, suffix = parts[0], parts[1]

        if suffix == "SH":
            return f"{prefix}.SS"
        elif suffix == "HK" and len(prefix) == 5:
            return f"{prefix[1:]}.HK"

        return symbol_f
    except Exception as e:
        logger.warning("Error normalizing symbol %s: %s", symbol, e)
        return symbol


class DataSource(ABC):
    """数据源基类"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return data source provider name."""
        pass

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        """获取历史数据"""
        try:
            # Allow subclasses to transform symbol if needed
            processed_symbol = self._normalize_symbol(symbol)
            logger.info(
                "Fetching data from %s for %s (original: %s)",
                self.provider_name,
                processed_symbol,
                symbol,
            )

            # 转换时间间隔
            obb_interval = self._convert_interval(interval)

            # 使用 OpenBB 获取数据
            result = obb.equity.price.historical(
                symbol=processed_symbol,
                start_date=start_date,
                end_date=end_date,
                interval=obb_interval,
                provider=self.provider_name,  # type: ignore[arg-type]
            )

            # 转换数据格式
            result_dict = result.to_dict()
            if not isinstance(result_dict, dict):
                result_dict = {}
            return self._format_data(result_dict, interval)
        except Exception as e:
            logger.error(f"Error fetching data from {self.provider_name}: {e}")
            raise

    def _normalize_symbol(self, symbol: str) -> str:
        """符号标准化钩子，子类可覆盖此方法"""
        return symbol

    def _convert_interval(self, interval: str) -> str:
        """转换时间间隔"""
        interval_map = {"1d": "1d", "1w": "1w", "1m": "1m"}
        return interval_map.get(interval, "1d")

    def _format_data(
        self,
        data: dict[Any, Any],
        interval: str,
    ) -> list[dict[str, Any]]:
        """格式化数据"""
        formatted_data: list[dict[str, Any]] = []
        # Data is in columnar format, convert to row-based format
        if not data or not any(isinstance(v, list) for v in data.values()):
            return formatted_data

        # Get the number of rows from the first list
        num_rows = len(next((v for v in data.values() if isinstance(v, list)), []))

        for i in range(num_rows):
            formatted_item = {
                "date": (
                    data.get("date", [None])[i]
                    if i < len(data.get("date", []))
                    else None
                ),
                "open": (
                    data.get("open", [None])[i]
                    if i < len(data.get("open", []))
                    else None
                ),
                "high": (
                    data.get("high", [None])[i]
                    if i < len(data.get("high", []))
                    else None
                ),
                "low": (
                    data.get("low", [None])[i] if i < len(data.get("low", [])) else None
                ),
                "close": (
                    data.get("close", [None])[i]
                    if i < len(data.get("close", []))
                    else None
                ),
                "volume": (
                    data.get("volume", [None])[i]
                    if i < len(data.get("volume", []))
                    else None
                ),
                "amount": (
                    data.get("amount", [None])[i]
                    if i < len(data.get("amount", []))
                    else None
                ),
                "interval": interval,
            }
            formatted_data.append(formatted_item)
        return formatted_data


class AkShareDataSource(DataSource):
    """AkShare 数据源"""

    @property
    def provider_name(self) -> str:
        return "akshare"


class YFinanceDataSource(DataSource):
    """YFinance 数据源"""

    @property
    def provider_name(self) -> str:
        return "yfinance"

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert stock symbols for Yahoo Finance format."""
        return normalize_symbol_for_yfinance(symbol)


class TushareDataSource(DataSource):
    """Tushare 数据源"""

    @property
    def provider_name(self) -> str:
        return "tushare"


class DataSourceManager:
    """数据源管理器"""

    def __init__(self):
        """初始化数据源管理器"""
        self.data_sources = {
            "akshare": AkShareDataSource(),
            "yfinance": YFinanceDataSource(),
            "tushare": TushareDataSource(),
        }
        self.priority_order = ["akshare", "yfinance", "tushare"]

    def get_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> tuple[list[dict[str, Any]], str]:
        """获取数据，按优先级尝试不同的数据源"""
        for source_name in self.priority_order:
            try:
                data = self.data_sources[source_name].get_historical_data(
                    symbol, start_date, end_date, interval
                )
                if data:
                    return data, source_name
            except Exception as e:
                logger.warning(f"Failed to get data from {source_name}: {e}")
                continue

        raise Exception("Failed to fetch data from all sources")
