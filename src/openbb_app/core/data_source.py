from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from openbb import obb

logger = logging.getLogger(__name__)

class DataSource(ABC):
    """数据源基类"""
    
    @abstractmethod
    def get_historical_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> List[Dict]:
        """获取历史数据"""
        pass

class AkShareDataSource(DataSource):
    """AkShare 数据源"""
    
    def get_historical_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> List[Dict]:
        """从 AkShare 获取历史数据"""
        try:
            logger.info(f"Fetching data from AkShare for {symbol}")
            
            # 转换时间间隔
            obb_interval = self._convert_interval(interval)
            
            # 使用 OpenBB 的 AkShare 提供商获取数据
            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=obb_interval,
                provider="akshare"
            )
            
            # 转换数据格式
            return self._format_data(result.to_dict(), interval)
        except Exception as e:
            logger.error(f"Error fetching data from AkShare: {e}")
            raise
    
    def _convert_interval(self, interval: str) -> str:
        """转换时间间隔"""
        interval_map = {
            '1d': '1d',
            '1w': '1w',
            '1m': '1m'
        }
        return interval_map.get(interval, '1d')
    
    def _format_data(self, data: Dict, interval: str) -> List[Dict]:
        """格式化数据"""
        formatted_data = []
        # Data is in columnar format, convert to row-based format
        if not data or not any(isinstance(v, list) for v in data.values()):
            return formatted_data
        
        # Get the number of rows from the first list
        num_rows = len(next((v for v in data.values() if isinstance(v, list)), []))
        
        for i in range(num_rows):
            formatted_item = {
                'date': data.get('date', [None])[i] if i < len(data.get('date', [])) else None,
                'open': data.get('open', [None])[i] if i < len(data.get('open', [])) else None,
                'high': data.get('high', [None])[i] if i < len(data.get('high', [])) else None,
                'low': data.get('low', [None])[i] if i < len(data.get('low', [])) else None,
                'close': data.get('close', [None])[i] if i < len(data.get('close', [])) else None,
                'volume': data.get('volume', [None])[i] if i < len(data.get('volume', [])) else None,
                'amount': data.get('amount', [None])[i] if i < len(data.get('amount', [])) else None,
                'interval': interval
            }
            formatted_data.append(formatted_item)
        return formatted_data

class YFinanceDataSource(DataSource):
    """YFinance 数据源"""
    
    def get_historical_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> List[Dict]:
        """从 YFinance 获取历史数据"""
        try:
            logger.info(f"Fetching data from YFinance for {symbol}")
            
            # 转换时间间隔
            obb_interval = self._convert_interval(interval)
            
            # 使用 OpenBB 的 YFinance 提供商获取数据
            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=obb_interval,
                provider="yfinance"
            )
            
            # 转换数据格式
            return self._format_data(result.to_dict(), interval)
        except Exception as e:
            logger.error(f"Error fetching data from YFinance: {e}")
            raise
    
    def _convert_interval(self, interval: str) -> str:
        """转换时间间隔"""
        interval_map = {
            '1d': '1d',
            '1w': '1w',
            '1m': '1m'
        }
        return interval_map.get(interval, '1d')
    
    def _format_data(self, data: Dict, interval: str) -> List[Dict]:
        """格式化数据"""
        formatted_data = []
        # Data is in columnar format, convert to row-based format
        if not data or not any(isinstance(v, list) for v in data.values()):
            return formatted_data
        
        # Get the number of rows from the first list
        num_rows = len(next((v for v in data.values() if isinstance(v, list)), []))
        
        for i in range(num_rows):
            formatted_item = {
                'date': data.get('date', [None])[i] if i < len(data.get('date', [])) else None,
                'open': data.get('open', [None])[i] if i < len(data.get('open', [])) else None,
                'high': data.get('high', [None])[i] if i < len(data.get('high', [])) else None,
                'low': data.get('low', [None])[i] if i < len(data.get('low', [])) else None,
                'close': data.get('close', [None])[i] if i < len(data.get('close', [])) else None,
                'volume': data.get('volume', [None])[i] if i < len(data.get('volume', [])) else None,
                'amount': data.get('amount', [None])[i] if i < len(data.get('amount', [])) else None,
                'interval': interval
            }
            formatted_data.append(formatted_item)
        return formatted_data

class TushareDataSource(DataSource):
    """Tushare 数据源"""
    
    def get_historical_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> List[Dict]:
        """从 Tushare 获取历史数据"""
        try:
            logger.info(f"Fetching data from Tushare for {symbol}")
            
            # 转换时间间隔
            obb_interval = self._convert_interval(interval)
            
            # 使用 OpenBB 的 Tushare 提供商获取数据
            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=obb_interval,
                provider="tushare"
            )
            
            # 转换数据格式
            return self._format_data(result.to_dict(), interval)
        except Exception as e:
            logger.error(f"Error fetching data from Tushare: {e}")
            raise
    
    def _convert_interval(self, interval: str) -> str:
        """转换时间间隔"""
        interval_map = {
            '1d': '1d',
            '1w': '1w',
            '1m': '1m'
        }
        return interval_map.get(interval, '1d')
    
    def _format_data(self, data: Dict, interval: str) -> List[Dict]:
        """格式化数据"""
        formatted_data = []
        # Data is in columnar format, convert to row-based format
        if not data or not any(isinstance(v, list) for v in data.values()):
            return formatted_data
        
        # Get the number of rows from the first list
        num_rows = len(next((v for v in data.values() if isinstance(v, list)), []))
        
        for i in range(num_rows):
            formatted_item = {
                'date': data.get('date', [None])[i] if i < len(data.get('date', [])) else None,
                'open': data.get('open', [None])[i] if i < len(data.get('open', [])) else None,
                'high': data.get('high', [None])[i] if i < len(data.get('high', [])) else None,
                'low': data.get('low', [None])[i] if i < len(data.get('low', [])) else None,
                'close': data.get('close', [None])[i] if i < len(data.get('close', [])) else None,
                'volume': data.get('volume', [None])[i] if i < len(data.get('volume', [])) else None,
                'amount': data.get('amount', [None])[i] if i < len(data.get('amount', [])) else None,
                'interval': interval
            }
            formatted_data.append(formatted_item)
        return formatted_data

class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self):
        """初始化数据源管理器"""
        self.data_sources = {
            'akshare': AkShareDataSource(),
            'yfinance': YFinanceDataSource(),
            'tushare': TushareDataSource()
        }
        self.priority_order = ['akshare', 'yfinance', 'tushare']
    
    def get_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> tuple[List[Dict], str]:
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
