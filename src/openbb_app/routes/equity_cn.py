import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from openbb_app.core.data_source import DataSourceManager
from openbb_app.core.database import DatabaseManager
from openbb_app.core.equity_data import MARKET_SH, EquityData
from openbb_app.core.registry import register_widget
from openbb_core.app.service.user_service import UserService

logger = logging.getLogger(__name__)

# 创建路由器
equity_cn_router = APIRouter()
equity_data = EquityData()


# 初始化数据库管理器
def get_db_manager() -> DatabaseManager:
    """获取数据库管理器"""
    # 读取用户设置
    settings = UserService.read_from_file()
    cache_dir = Path(settings.preferences.cache_directory)

    # 强制使用当前工作目录作为缓存目录，确保有写权限
    # cache_dir = Path.cwd() / "cache"

    logger.info(f"Using cache directory: {cache_dir}")

    # 在数据目录下创建SQLite数据库
    db_path = cache_dir / "appdata/equity.db"
    return DatabaseManager(db_path)


# 初始化数据源管理器
data_source_manager = DataSourceManager()


@equity_cn_router.get("/equity/price/historical")
def get_historical_data(
    symbol: str = Query(..., description="股票代码（如 000001.SZ）"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    interval: str = Query("1d", description="时间间隔: 1d(日), 1w(周), 1m(月)"),
):
    """获取指定股票的历史价格数据（日K线）"""
    from mysharelib.tools import normalize_symbol

    symbol_b, symbol_f, market = normalize_symbol(symbol)
    symbol = symbol_f
    try:
        # 验证时间间隔
        valid_intervals = ["1d", "1w", "1m"]
        if interval not in valid_intervals:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}",
            )

        # 设置默认日期
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        if not start_date:
            # 默认一年前
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        # 验证日期格式
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Must be YYYY-MM-DD"
            )

        # 获取数据库管理器
        db_manager = get_db_manager()

        # 先从数据库获取数据
        cached_data = db_manager.get_price_data(symbol, start_date, end_date, interval)

        # 如果有缓存数据，直接返回
        if cached_data:
            logger.info(f"Returning cached data for {symbol}")
            # 构建响应
            response = {
                "symbol": symbol,
                "interval": interval,
                "data": [
                    {
                        "date": item["date"],
                        "open": item["open"],
                        "high": item["high"],
                        "low": item["low"],
                        "close": item["close"],
                        "volume": item["volume"],
                        "amount": item["amount"],
                    }
                    for item in cached_data
                ],
                "source": "cache",
                "cached_at": datetime.now().isoformat(),
            }
            return response.get("data", [])

        # 数据库未命中，尝试从数据源获取
        logger.info(f"Cache miss for {symbol}, fetching from data sources")
        try:
            data, source = data_source_manager.get_data(
                symbol, start_date, end_date, interval
            )

            # 写入数据库
            if data:
                db_manager.upsert_price_data(symbol, data, source)
                logger.info(f"Wrote {len(data)} records to database for {symbol}")

            # 构建响应
            response = {
                "symbol": symbol,
                "interval": interval,
                "data": [
                    {
                        "date": item["date"],
                        "open": item["open"],
                        "high": item["high"],
                        "low": item["low"],
                        "close": item["close"],
                        "volume": item["volume"],
                        "amount": item["amount"],
                    }
                    for item in data
                ],
                "source": source,
                "cached_at": datetime.now().isoformat(),
            }

            return response.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch data from sources: {e}")
            # 既没有缓存数据，也没有数据源数据，返回错误
            raise

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical data: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch data from all sources"
        )
        raise HTTPException(
            status_code=500, detail="Failed to fetch data from all sources"
        )


@register_widget(
    {
        "name": "股价范围",
        "description": "Get the current stock innformation.",
        "category": "Equity",
        "type": "html",
        "widgetId": "equity/screener",
        "endpoint": "/v1/cn/equity/screener",
        "gridData": {"w": 40, "h": 30},
        "source": "A股",
        "params": [
            {
                "paramName": "is_realized",
                "description": "Whether to include only realized transactions.",
                "label": "包括已卖出交易",
                "type": "boolean",
                "value": False,
            },
            {
                "paramName": "use_cache",
                "description": "Whether to use cache.",
                "label": "使用缓存",
                "type": "boolean",
                "value": True,
            },
            {
                "paramName": "market",
                "description": "Market to use.",
                "value": "HK",
                "label": "市场",
                "type": "text",
                "options": [
                    {"value": "SH", "label": "上海"},
                    {"value": "SZ", "label": "深圳"},
                    {"value": "BJ", "label": "北京"},
                    {"value": "HK", "label": "香港"},
                ],
            },
            {
                "paramName": "strategy_rate",
                "description": "strategy rate",
                "value": "0.05",
                "label": "交易策略",
                "type": "text",
                "options": [
                    {"value": "0.05", "label": "5%"},
                    {"value": "0.1", "label": "10%"},
                    {"value": "0.15", "label": "15%"},
                    {"value": "0.2", "label": "20%"},
                    {"value": "0.25", "label": "25%"},
                ],
            },
        ],
    }
)
@equity_cn_router.get("/equity/screener", response_class=HTMLResponse)
def get_cn_screener(
    is_realized: bool = False,
    use_cache: bool = True,
    market: str = MARKET_SH,
    strategy_rate: str = "0.05",
):
    """
    Get screener data
    """
    return HTMLResponse(
        content=equity_data.get_screener(
            is_realized=is_realized,
            use_cache=use_cache,
            market=market,
            strategy_rate=float(strategy_rate),
        )
    )
