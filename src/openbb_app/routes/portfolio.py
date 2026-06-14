import logging
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi import Path as FastAPIPath
from fastapi import Query
from mysharelib.tools import normalize_symbol
from openbb import obb
from openbb_app.core.database import DatabaseManager
from openbb_app.core.registry import register_widget
from openbb_core.app.service.user_service import UserService
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 创建路由器
portfolio_router = APIRouter()


# 股票名称缓存（使用LRU缓存）
@lru_cache(maxsize=128)
def get_stock_name_by_search(symbol: str) -> Optional[str]:
    """
    通过股票代码搜索股票名称

    Args:
        symbol: 股票代码

    Returns:
        股票名称，如果找不到或找到多个结果则返回None
    """
    try:
        logger.info(f"Searching stock name for symbol: {symbol}")
        result = obb.equity.search(query=symbol, use_cache=True)
        df = result.to_dataframe()
        df = df[df["symbol"] == symbol]

        if df.empty:
            logger.warning(f"No search results found for symbol: {symbol}")
            return None

        # 检查是否有多个匹配结果
        if len(df) > 1:
            logger.warning(
                f"Multiple search results found for symbol: {symbol}, count: {len(df)}"
            )
            return None

        # 提取股票名称
        name = None
        if "name" in df.columns:
            name = df["name"].iloc[0]
        elif "short_name" in df.columns:
            name = df["short_name"].iloc[0]
        elif "long_name" in df.columns:
            name = df["long_name"].iloc[0]

        if name:
            logger.info(f"Found stock name for {symbol}: {name}")
            return name
        else:
            logger.warning(
                f"No name field found in search results for symbol: {symbol}"
            )
            return None

    except Exception as e:
        logger.error(f"Error searching stock name for {symbol}: {e}")
        return None


def validate_symbol_format(symbol: str) -> bool:
    """
    验证股票代码格式

    Args:
        symbol: 股票代码

    Returns:
        格式是否有效
    """
    # A股格式：000001.SZ 或 600000.SH
    a_share_pattern = r"^\d{6}\.(SZ|SH|BJ)$"
    # 港股格式：00700.HK 或 09988.HK（4-5位数字）
    hk_pattern = r"^\d{4,5}\.HK$"

    return bool(re.match(a_share_pattern, symbol) or re.match(hk_pattern, symbol))


# 初始化数据库管理器
def get_db_manager() -> DatabaseManager:
    """获取数据库管理器"""
    # 读取用户设置
    settings = UserService.read_from_file()
    cache_dir = Path(settings.preferences.cache_directory)

    logger.info(f"Using cache directory: {cache_dir}")

    # 在数据目录下创建SQLite数据库
    db_path = cache_dir / "appdata/equity.db"
    return DatabaseManager(db_path)


# Pydantic模型
class StockPersistentFields(BaseModel):
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    avg_cost: float = Field(default=0, ge=0, description="持仓均价")
    quantity: int = Field(default=0, ge=0, description="持有数量")
    total_value: float = Field(default=0, ge=0, description="市值总计")


class StockDynamicFields(BaseModel):
    current_price: float = Field(default=0, ge=0, description="当前市场价格")
    fifty_two_week_low: float = Field(default=0, ge=0, description="52周最低价格")
    fifty_two_week_high: float = Field(default=0, ge=0, description="52周最高价格")
    dividend_yield: float = Field(default=0, ge=0, le=100, description="股息率")
    latest_dividend: float = Field(default=0, ge=0, description="最近股息")
    strategy: str = Field(default="持有", description="策略建议")
    tradingview: Optional[str] = Field(None, description="Tradingview链接")


class StockBase(StockPersistentFields, StockDynamicFields):
    pass


class StockCreate(StockBase):
    name: Optional[str] = Field(None, description="股票名称（可选，为空时自动检索）")


class StockUpdate(BaseModel):
    name: Optional[str] = Field(None, description="股票名称")
    avg_cost: Optional[float] = Field(None, ge=0, description="持仓均价")
    quantity: Optional[int] = Field(None, ge=0, description="持有数量")
    total_value: Optional[float] = Field(None, ge=0, description="市值总计")


class StockResponse(StockBase):
    class Config:
        from_attributes = True


class StockDeleteRequest(BaseModel):
    symbol: str = Field(..., description="股票代码")


class StockDeleteResponse(BaseModel):
    message: str = Field(..., description="操作结果消息")
    symbol: str = Field(..., description="被删除的股票代码")
    transactions_deleted: int = Field(0, description="级联删除的交易记录数量")


# 交易记录模型
class TransactionBase(BaseModel):
    date: str = Field(..., description="交易日期")
    symbol: str = Field(..., description="股票代码")
    name: Optional[str] = Field(None, description="股票名称（可选，为空时自动检索）")
    price: float = Field(..., gt=0, description="成交价格")
    quantity: int = Field(..., gt=0, description="成交数量")
    transaction_type: str = Field(..., description="交易类型")
    total_value: Optional[float] = Field(None, ge=0, description="交易总额（含手续费）")


class TransactionCreate(TransactionBase):
    date: Optional[str] = Field(
        None, description="交易日期（可选，为空时使用当前日期）"
    )


class TransactionUpdate(BaseModel):
    date: Optional[str] = Field(None, description="交易日期")
    symbol: Optional[str] = Field(None, description="股票代码")
    name: Optional[str] = Field(None, description="股票名称")
    price: Optional[float] = Field(None, gt=0, description="成交价格")
    quantity: Optional[int] = Field(None, gt=0, description="成交数量")
    transaction_type: Optional[str] = Field(None, description="交易类型")
    total_value: Optional[float] = Field(None, ge=0, description="交易总额（含手续费）")


class TransactionResponse(TransactionBase):
    id: int = Field(..., description="交易记录ID")
    base_value: float = Field(..., description="基础价值（价格×数量）")
    transaction_fee: float = Field(..., description="交易手续费")
    total_value: float = Field(..., description="交易总额（含手续费）")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# 自选股管理API
@register_widget(
    {
        "name": "自选股",
        "description": "Manage and view your portfolio stocks",
        "type": "table",
        "category": "Equity",
        "widgetId": "portfolio/stocks",
        "endpoint": "/v1/portfolio/stocks",
        "runButton": True,
        "gridData": {"w": 50, "h": 20},
        "data": {
            "dataKey": "",
            "table": {
                "showAll": True,
                "enableAdvanced": True,
                "columnsDefs": [
                    {
                        "field": "symbol",
                        "headerName": "股票代码",
                        "headerTooltip": "股票代码（例如：000001.SZ,600000.SH）",
                        "cellDataType": "text",
                        "pinned": "left",
                        "renderFn": "cellOnClick",
                        "renderFnParams": {
                            "actionType": "groupBy",
                            "groupByParamName": "symbol",
                        },
                    },
                    {
                        "field": "name",
                        "headerName": "股票名称",
                        "headerTooltip": "股票名称",
                        "cellDataType": "text",
                    },
                    {
                        "field": "current_price",
                        "headerName": "当前价格",
                        "headerTooltip": "当前市场价格",
                        "cellDataType": "number",
                    },
                    {
                        "field": "avg_cost",
                        "headerName": "平均成本",
                        "headerTooltip": "平均成本",
                        "cellDataType": "number",
                    },
                    {
                        "field": "quantity",
                        "headerName": "持仓数量",
                        "headerTooltip": "持仓数量",
                        "cellDataType": "number",
                    },
                    {
                        "field": "total_value",
                        "headerName": "持仓总价值",
                        "headerTooltip": "持仓总价值",
                        "cellDataType": "number",
                    },
                    {
                        "field": "fifty_two_week_low",
                        "headerName": "52周最低价",
                        "headerTooltip": "52周最低价",
                        "cellDataType": "number",
                    },
                    {
                        "field": "fifty_two_week_high",
                        "headerName": "52周最高价",
                        "headerTooltip": "52周最高价",
                        "cellDataType": "number",
                    },
                    {
                        "field": "dividend_yield",
                        "headerName": "分红收益率",
                        "headerTooltip": "分红收益率",
                        "formatterFn": "percent",
                        "cellDataType": "number",
                        "renderFn": "columnColor",
                        "renderFnParams": {
                            "colorRules": [
                                {
                                    "condition": "between",
                                    "range": {"min": 3, "max": 5},
                                    "color": "blue",
                                },
                                {"condition": "gt", "value": 5, "color": "green"},
                            ]
                        },
                    },
                    {
                        "field": "latest_dividend",
                        "headerName": "最新分红金额",
                        "headerTooltip": "最新分红金额",
                        "cellDataType": "number",
                    },
                    {
                        "field": "strategy",
                        "headerName": "投资策略",
                        "headerTooltip": "投资策略",
                        "cellDataType": "text",
                        "renderFn": "columnColor",
                        "renderFnParams": {
                            "colorRules": [
                                {
                                    "condition": "contains",
                                    "value": "卖出",
                                    "color": "green",
                                },
                                {
                                    "condition": "contains",
                                    "value": "买入",
                                    "color": "red",
                                },
                            ]
                        },
                    },
                    {
                        "field": "tradingview",
                        "headerName": "TradingView",
                        "headerTooltip": "TradingView chart link",
                        "cellDataType": "text",
                    },
                ],
            },
        },
        "source": ["Portfolio"],
        "params": [
            {
                "paramName": "symbol",
                "description": "Filter by stock symbol",
                "type": "text",
                "value": "600325.SH",
                "label": "股票代码",
                "type": "endpoint",
                "optionsEndpoint": "/v1/portfolio/stocks",
                "multiSelect": False,
                "show": True,
            },
            {
                "paramName": "添加",
                "description": "添加股票到组合",
                "type": "form",
                "endpoint": "/v1/portfolio/stocks",
                "inputParams": [
                    {
                        "paramName": "symbol",
                        "type": "text",
                        "value": "",
                        "label": "股票代码",
                        "description": "股票代码",
                    },
                    {
                        "paramName": "name",
                        "type": "text",
                        "value": "",
                        "label": "股票名称",
                        "description": "股票名称",
                    },
                    {
                        "paramName": "add_stock",
                        "type": "button",
                        "value": True,
                        "label": "添加",
                        "description": "Add a new stock to the portfolio",
                    },
                ],
            },
            {
                "paramName": "删除",
                "description": "删除股票从组合",
                "type": "form",
                "endpoint": "/v1/portfolio/delete-stock",
                "inputParams": [
                    {
                        "paramName": "symbol",
                        "type": "text",
                        "value": "",
                        "label": "股票代码",
                        "description": "股票代码",
                        "validation": {
                            "required": True,
                            "pattern": r"^\d{6}\.(SZ|SH|BJ)$|^\d{4,5}\.HK$",
                            "patternMessage": "股票代码格式无效，示例：000001.SZ、600000.SH、00700.HK",
                        },
                    },
                    {
                        "paramName": "delete_stock",
                        "type": "button",
                        "value": True,
                        "label": "删除",
                        "description": "删除股票从组合",
                    },
                    {
                        "paramName": "cancel",
                        "type": "button",
                        "value": False,
                        "label": "取消",
                        "description": "取消删除操作",
                    },
                ],
                "successMessage": "股票删除成功，列表已刷新",
                "errorMessages": {
                    "404": "股票代码不存在于自选股中",
                    "400": "股票代码格式无效",
                    "500": "删除股票时发生错误，请稍后重试",
                },
            },
        ],
    }
)
@portfolio_router.get("/portfolio/stocks", response_model=List[StockResponse])
def get_all_stocks():
    """获取所有自选股"""
    try:
        db_manager = get_db_manager()
        stocks = db_manager.get_all_portfolio_stocks()
        return stocks
    except Exception as e:
        logger.error(f"Error getting all stocks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stocks")


@portfolio_router.get("/portfolio/stocks/{symbol}", response_model=StockResponse)
def get_stock(symbol: str = FastAPIPath(..., description="股票代码")):
    """获取单个自选股"""
    try:
        symbol_b, symbol_f, market = normalize_symbol(symbol)
        symbol = symbol_f
        db_manager = get_db_manager()
        stock = db_manager.get_portfolio_stock(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        return stock
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stock: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stock")


@portfolio_router.post("/portfolio/stocks", response_model=StockResponse)
def create_stock(stock: StockCreate):
    """创建新的自选股"""
    try:
        # 验证股票代码格式
        symbol_b, symbol_f, market = normalize_symbol(stock.symbol)
        stock.symbol = symbol_f

        if not validate_symbol_format(stock.symbol):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid symbol format: {stock.symbol}. Expected format: 000001.SZ, 600000.SH, or 00700.HK",
            )

        # 如果股票名称为空，自动检索
        if not stock.name or not stock.name.strip():
            logger.info(f"Stock name is empty, searching for symbol: {stock.symbol}")
            stock_name = get_stock_name_by_search(symbol_b)

            if not stock_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to find stock name for symbol: {stock.symbol}. Please provide the stock name manually or check the symbol format.",
                )

            stock.name = stock_name
            logger.info(f"Auto-filled stock name for {stock.symbol}: {stock.name}")

        db_manager = get_db_manager()
        stock_data = stock.model_dump()
        stock_data.setdefault("avg_cost", 0)
        stock_data.setdefault("quantity", 0)
        stock_data.setdefault("total_value", 0)

        try:
            logger.info(f"Fetching equity profile for {stock.symbol} from AkShare")
            profile_data = obb.equity.profile(
                symbol=stock.symbol, provider="akshare", use_cache=True
            )

            logger.info(f"Converting profile data to DataFrame for {stock.symbol}")
            df = profile_data.to_dataframe()

            if not df.empty:
                logger.info(
                    f"Extracting listing date from profile data for {stock.symbol}"
                )
                latest_record = df.tail(1)

                list_date = None
                if "上市日期" in latest_record.columns:
                    list_date_value = latest_record["上市日期"].iloc[0]
                    if list_date_value:
                        list_date = str(list_date_value)
                        logger.info(
                            f"Found listing date for {stock.symbol}: {list_date}"
                        )

                if list_date:
                    existing_metadata = db_manager.get_equity_metadata(stock.symbol)
                    metadata = {
                        "symbol": stock.symbol,
                        "name": stock.name,
                        "list_date": list_date,
                    }

                    if existing_metadata:
                        logger.info(f"Updating equity metadata for {stock.symbol}")
                        db_manager.update_equity_metadata(
                            stock.symbol, {"list_date": list_date}
                        )
                    else:
                        logger.info(f"Creating new equity metadata for {stock.symbol}")
                        db_manager.add_equity_metadata(metadata)

                    updated_metadata = db_manager.get_equity_metadata(stock.symbol)
                    if (
                        updated_metadata
                        and updated_metadata.get("list_date") == list_date
                    ):
                        logger.info(
                            f"Successfully verified listing date for {stock.symbol}: {list_date}"
                        )
                    else:
                        logger.warning(
                            f"Failed to verify listing date for {stock.symbol}"
                        )
                else:
                    logger.warning(
                        f"No listing date found in profile data for {stock.symbol}"
                    )
            else:
                logger.warning(f"Empty profile data returned for {stock.symbol}")

        except Exception as api_error:
            logger.error(
                f"Error fetching equity profile for {stock.symbol}: {api_error}"
            )
            logger.info(
                f"Proceeding with stock creation without listing date for {stock.symbol}"
            )

        db_manager.add_portfolio_stock(stock_data)
        created_stock = db_manager.get_portfolio_stock(stock.symbol)
        if not created_stock:
            raise HTTPException(status_code=500, detail="Failed to create stock")
        return created_stock
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating stock: {e}")
        raise HTTPException(status_code=500, detail="Failed to create stock")


@portfolio_router.put("/portfolio/stocks/{symbol}", response_model=StockResponse)
def update_stock(
    stock: StockUpdate, symbol: str = FastAPIPath(..., description="股票代码")
):
    """更新自选股信息"""
    try:
        symbol_b, symbol_f, market = normalize_symbol(symbol)
        symbol = symbol_f
        db_manager = get_db_manager()
        existing_stock = db_manager.get_portfolio_stock(symbol)
        if not existing_stock:
            raise HTTPException(status_code=404, detail="Stock not found")

        stock_data = stock.model_dump(exclude_unset=True)
        db_manager.update_portfolio_stock(symbol, stock_data)
        updated_stock = db_manager.get_portfolio_stock(symbol)
        if not updated_stock:
            raise HTTPException(status_code=500, detail="Failed to update stock")
        return updated_stock
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating stock: {e}")
        raise HTTPException(status_code=500, detail="Failed to update stock")


def _delete_stock_by_symbol(symbol: str) -> dict:
    """
    删除自选股的业务逻辑（包含级联删除关联交易记录）

    Args:
        symbol: 股票代码

    Returns:
        删除结果字典，包含：
        - success: 是否成功删除
        - symbol: 被删除的股票代码
        - transactions_deleted: 级联删除的交易记录数量

    Raises:
        HTTPException: 当股票不存在或删除失败时抛出异常
    """
    symbol_b, symbol_f, market = normalize_symbol(symbol)
    normalized_symbol = symbol_f
    logger.info(f"Preparing to delete portfolio stock: {normalized_symbol}")
    
    db_manager = get_db_manager()
    result = db_manager.delete_portfolio_stock(normalized_symbol)
    
    if not result['success']:
        logger.warning(f"Stock not found in portfolio: {normalized_symbol}")
        raise HTTPException(
            status_code=404,
            detail=f"Stock with symbol {normalized_symbol} not found in portfolio",
        )
    
    logger.info(f"Successfully deleted portfolio stock: {normalized_symbol}")
    logger.info(f"Associated transactions deleted: {result['transactions_deleted']}")
    
    return result


@portfolio_router.delete("/portfolio/stocks/{symbol}")
def delete_stock(symbol: str = FastAPIPath(..., description="股票代码")):
    """删除自选股（通过DELETE方法）"""
    try:
        result = _delete_stock_by_symbol(symbol)
        message = f"Stock {result['symbol']} deleted successfully"
        if result['transactions_deleted'] > 0:
            message += f", including {result['transactions_deleted']} associated transactions"
        logger.info(message)
        return {
            "message": message,
            "symbol": result['symbol'],
            "transactions_deleted": result['transactions_deleted']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting stock: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete stock")


@portfolio_router.post(
    "/portfolio/delete-stock",
    response_model=StockDeleteResponse,
    summary="删除自选股",
    description="通过POST方法删除自选股，提供与DELETE方法相同的功能，但使用请求体传递股票代码",
    responses={
        200: {"description": "股票删除成功"},
        400: {"description": "股票代码格式无效"},
        404: {"description": "股票不存在于自选股中"},
        500: {"description": "服务器内部错误"},
    },
)
def delete_stock_post(request: StockDeleteRequest):
    """
    删除自选股（通过POST方法）

    此端点提供与DELETE方法相同的功能，但允许通过HTML表单提交。
    适用于需要通过Input Form进行删除操作的场景。
    删除股票时会自动级联删除关联的交易记录。

    Args:
        request: 包含待删除股票代码的请求体

    Returns:
        StockDeleteResponse: 包含操作结果消息、被删除的股票代码和级联删除的交易记录数量
    """
    try:
        if not validate_symbol_format(request.symbol):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid symbol format: {request.symbol}. Expected format: 000001.SZ, 600000.SH, or 00700.HK",
            )
        logger.info(f"Deleting stock via POST: {request.symbol}")
        result = _delete_stock_by_symbol(request.symbol)
        
        message = f"Stock {result['symbol']} deleted successfully"
        if result['transactions_deleted'] > 0:
            message += f", including {result['transactions_deleted']} associated transactions"
        
        return StockDeleteResponse(
            message=message,
            symbol=result['symbol'],
            transactions_deleted=result['transactions_deleted'],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting stock via POST: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete stock")


# 交易记录管理API
@register_widget(
    {
        "name": "交易记录管理",
        "description": "Manage and view your portfolio transactions",
        "type": "table",
        "category": "Equity",
        "widgetId": "portfolio/transactions",
        "endpoint": "/v1/portfolio/transactions",
        "runButton": True,
        "gridData": {"w": 50, "h": 20},
        "data": {
            "dataKey": "",
            "table": {
                "showAll": True,
                "enableAdvanced": True,
                "columnsDefs": [
                    {
                        "field": "id",
                        "pinned": "left",
                        "headerName": "ID",
                        "headerTooltip": "Transaction ID",
                        "cellDataType": "number",
                    },
                    {
                        "field": "date",
                        "headerName": "Date",
                        "headerTooltip": "Transaction date",
                        "cellDataType": "dateString",
                    },
                    {
                        "field": "symbol",
                        "headerName": "Symbol",
                        "headerTooltip": "Stock symbol code",
                        "cellDataType": "text",
                    },
                    {
                        "field": "name",
                        "headerName": "Name",
                        "headerTooltip": "Stock name",
                        "cellDataType": "text",
                    },
                    {
                        "field": "transaction_type",
                        "headerName": "Type",
                        "headerTooltip": "Transaction type (买入/卖出)",
                        "cellDataType": "text",
                        "renderFn": "columnColor",
                        "renderFnParams": {
                            "colorRules": [
                                {
                                    "condition": "contains",
                                    "value": "卖出",
                                    "color": "green",
                                },
                                {
                                    "condition": "contains",
                                    "value": "买入",
                                    "color": "red",
                                },
                            ]
                        },
                    },
                    {
                        "field": "price",
                        "headerName": "Price",
                        "headerTooltip": "Transaction price per share",
                        "cellDataType": "number",
                    },
                    {
                        "field": "quantity",
                        "headerName": "Quantity",
                        "headerTooltip": "Number of shares traded",
                        "cellDataType": "number",
                    },
                    {
                        "field": "base_value",
                        "headerName": "Base Value",
                        "headerTooltip": "Base value (price × quantity)",
                        "cellDataType": "number",
                    },
                    {
                        "field": "transaction_fee",
                        "headerName": "Fee",
                        "headerTooltip": "Transaction fee",
                        "cellDataType": "number",
                    },
                    {
                        "field": "total_value",
                        "headerName": "Total Value",
                        "headerTooltip": "Total transaction value including fees",
                        "cellDataType": "number",
                    },
                    {
                        "field": "created_at",
                        "headerName": "Created At",
                        "headerTooltip": "Record creation time",
                        "cellDataType": "text",
                    },
                    {
                        "field": "updated_at",
                        "headerName": "Updated At",
                        "headerTooltip": "Record update time",
                        "cellDataType": "text",
                    },
                ],
            },
        },
        "source": ["Portfolio"],
        "params": [
            {
                "paramName": "symbol",
                "description": "Filter by stock symbol",
                "type": "text",
                "value": "600325.SH",
                "label": "Symbol",
                "type": "endpoint",
                "optionsEndpoint": "/v1/portfolio/stocks",
                "multiSelect": False,
                "show": True,
            },
            {
                "paramName": "start_date",
                "description": "Filter by start date",
                "type": "text",
                "value": "",
                "label": "Start Date",
                "optional": True,
            },
            {
                "paramName": "end_date",
                "description": "Filter by end date",
                "type": "text",
                "value": "",
                "label": "End Date",
                "optional": True,
            },
            {
                "paramName": "添加",
                "description": "添加交易记录",
                "type": "form",
                "endpoint": "/v1/portfolio/transactions",
                "inputParams": [
                    {
                        "paramName": "date",
                        "type": "text",
                        "value": "",
                        "label": "日期",
                        "description": "交易日期（例如：2024-01-01）",
                    },
                    {
                        "paramName": "symbol",
                        "type": "text",
                        "value": "",
                        "label": "股票代码",
                        "description": "股票代码（例如：000001.SZ, 600000.SH）",
                    },
                    {
                        "paramName": "name",
                        "type": "text",
                        "value": "",
                        "label": "股票名称",
                        "description": "股票名称",
                    },
                    {
                        "paramName": "price",
                        "type": "number",
                        "value": 0,
                        "label": "价格",
                        "description": "股票价格",
                    },
                    {
                        "paramName": "quantity",
                        "type": "number",
                        "value": 0,
                        "label": "数量",
                        "description": "股票数量",
                    },
                    {
                        "paramName": "total_value",
                        "type": "number",
                        "value": 0,
                        "label": "总价值",
                        "description": "总价值",
                    },
                    {
                        "paramName": "transaction_type",
                        "type": "text",
                        "value": "买入",
                        "label": "交易类型",
                        "description": "交易类型（买入/卖出）",
                        "options": [
                            {"label": "买入", "value": "买入"},
                            {"label": "卖出", "value": "卖出"},
                        ],
                    },
                    {
                        "paramName": "添加",
                        "type": "button",
                        "value": True,
                        "label": "添加",
                        "description": "添加交易记录",
                    },
                ],
            },
        ],
    }
)
@portfolio_router.get(
    "/portfolio/transactions", response_model=List[TransactionResponse]
)
def get_all_transactions(
    symbol: Optional[str] = Query(None, description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
):
    """获取交易记录"""
    try:
        if symbol:
            symbol_b, symbol_f, market = normalize_symbol(symbol)
            symbol = symbol_f
        db_manager = get_db_manager()
        transactions = db_manager.get_all_transactions(symbol, start_date, end_date)
        return transactions
    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get transactions")


@portfolio_router.get(
    "/portfolio/transactions/{transaction_id}", response_model=TransactionResponse
)
def get_transaction(transaction_id: int = FastAPIPath(..., description="交易记录ID")):
    """获取单个交易记录"""
    try:
        db_manager = get_db_manager()
        transaction = db_manager.get_transaction(transaction_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return transaction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to get transaction")


@portfolio_router.post("/portfolio/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate):
    """创建新的交易记录"""
    try:
        symbol_b, symbol_f, market = normalize_symbol(transaction.symbol)
        transaction.symbol = symbol_f
        db_manager = get_db_manager()

        # 日期验证与处理
        if not transaction.date or not transaction.date.strip():
            transaction.date = datetime.now().strftime("%Y-%m-%d")
            logger.info(
                f"Transaction date is empty, using current date: {transaction.date}"
            )
        else:
            try:
                datetime.strptime(transaction.date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {transaction.date}. Expected format: YYYY-MM-DD",
                )

        # 股票名称处理
        if not transaction.name or not transaction.name.strip():
            logger.info(
                f"Stock name is empty, searching for symbol: {transaction.symbol}"
            )
            stock_name = get_stock_name_by_search(symbol_b)

            if not stock_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to find stock name for symbol: {transaction.symbol}. Please provide the stock name manually or check the symbol format.",
                )

            transaction.name = stock_name
            logger.info(
                f"Auto-filled stock name for {transaction.symbol}: {transaction.name}"
            )

        # 验证股票是否存在
        stock = db_manager.get_portfolio_stock(transaction.symbol)
        if not stock:
            # 如果股票不存在，自动创建
            stock_data = {
                "symbol": transaction.symbol,
                "name": transaction.name,
                "current_price": transaction.price,
                "avg_cost": 0,
                "quantity": 0,
                "total_value": 0,
            }
            db_manager.add_portfolio_stock(stock_data)
            logger.info(f"Auto-created portfolio stock for {transaction.symbol}")

        # 使用 model_dump(exclude_none=False) 确保包含所有字段，包括 None 值
        transaction_data = transaction.model_dump(exclude_none=False)
        db_manager.add_transaction(transaction_data)

        # 获取最新的交易记录（由于没有返回ID，需要查询）
        transactions = db_manager.get_all_transactions(transaction.symbol)
        if transactions:
            return transactions[0]
        raise HTTPException(status_code=500, detail="Failed to create transaction")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create transaction: {str(e)}"
        )


@portfolio_router.put(
    "/portfolio/transactions/{transaction_id}", response_model=TransactionResponse
)
def update_transaction(
    transaction: TransactionUpdate,
    transaction_id: int = FastAPIPath(..., description="交易记录ID"),
):
    """更新交易记录"""
    try:
        db_manager = get_db_manager()
        existing_transaction = db_manager.get_transaction(transaction_id)
        if not existing_transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        transaction_data = transaction.model_dump(exclude_unset=True)
        if "symbol" in transaction_data:
            symbol_b, symbol_f, market = normalize_symbol(transaction_data["symbol"])
            transaction_data["symbol"] = symbol_f
        success = db_manager.update_transaction(transaction_id, transaction_data)
        if not success:
            raise HTTPException(status_code=404, detail="Transaction not found")

        updated_transaction = db_manager.get_transaction(transaction_id)
        if not updated_transaction:
            raise HTTPException(status_code=500, detail="Failed to update transaction")
        return updated_transaction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")


@portfolio_router.delete("/portfolio/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int = FastAPIPath(..., description="交易记录ID")
):
    """删除交易记录"""
    try:
        db_manager = get_db_manager()
        success = db_manager.delete_transaction(transaction_id)
        if not success:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"message": "Transaction deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting transaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete transaction")


# 数据一致性校验API
@portfolio_router.get("/portfolio/validate")
def validate_portfolio_data():
    """验证持仓数据与交易记录的一致性"""
    try:
        db_manager = get_db_manager()
        validation_result = db_manager.validate_portfolio_data()
        return validation_result
    except Exception as e:
        logger.error(f"Error validating portfolio data: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate portfolio data")


@portfolio_router.get("/symbols")
def get_portfolio_symbols():
    """Get available stock tickers for A-share market"""
    from openbb_app.core.utils import get_symbols

    return get_symbols()


@register_widget(
    {
        "name": "基本信息",
        "description": "Get key company information.",
        "category": "Equity",
        "type": "markdown",
        "widgetId": "portfolio/key_metrics",
        "endpoint": "/v1/portfolio/key_metrics",
        "gridData": {"w": 10, "h": 12},
        "data": {
            "table": {
                "showAll": True,
                "columns": [
                    {"field": "fact", "headerName": "Fact", "width": 200},
                    {"field": "value", "headerName": "Value", "width": 200},
                ],
            }
        },
        "source": "A股",
        "params": [
            {
                "type": "endpoint",
                "paramName": "symbol",
                "label": "Symbol",
                "value": "600325.SH",
                "description": "Symbol to get company facts",
                "optionsEndpoint": "/v1/portfolio/stocks",
            }
        ],
    }
)
@portfolio_router.get("/portfolio/key_metrics")
def get_cn_key_metrics(symbol: str):
    """Get company facts for a symbol"""
    from mysharelib.tools import normalize_symbol
    from openbb_app.core.utils import get_info

    symbol_b, _, _ = normalize_symbol(symbol)
    key_metrics = get_info(symbol)
    key_metrics.name = get_stock_name_by_search(symbol_b)
    return key_metrics.to_markdown()


@register_widget(
    {
        "name": "相关新闻",
        "description": "Get recent news articles for stocks.",
        "category": "Equity",
        "type": "table",
        "widgetId": "portfolio/news",
        "endpoint": "/v1/portfolio/news",
        "gridData": {"w": 40, "h": 8},
        "data": {
            "table": {
                "showAll": True,
                "columnsDefs": [
                    {
                        "field": "date",
                        "headerName": "Date",
                        "width": 180,
                        "cellDataType": "text",
                        "pinned": "left",
                    },
                    {
                        "field": "title",
                        "headerName": "Title",
                        "width": 300,
                        "cellDataType": "text",
                    },
                    {
                        "field": "source",
                        "headerName": "Source",
                        "width": 150,
                        "cellDataType": "text",
                    },
                    {
                        "field": "author",
                        "headerName": "Author",
                        "width": 150,
                        "cellDataType": "text",
                    },
                    {
                        "field": "sentiment",
                        "headerName": "Sentiment",
                        "width": 120,
                        "cellDataType": "text",
                    },
                    {
                        "field": "url",
                        "headerName": "URL",
                        "width": 200,
                        "cellDataType": "text",
                    },
                ],
            }
        },
        "source": "A股",
        "params": [
            {
                "type": "endpoint",
                "paramName": "symbol",
                "label": "Symbol",
                "value": "600325.SH",
                "description": "Stock symbol to get news",
                "multiSelect": False,
                "optionsEndpoint": "/v1/portfolio/stocks",
            },
            {
                "type": "number",
                "paramName": "limit",
                "label": "Number of Articles",
                "value": "10",
                "description": "Maximum number of news articles to display",
            },
        ],
    }
)
@portfolio_router.get("/portfolio/news")
async def get_cn_news(
    symbol: str = Query(..., description="Stock symbol"), limit: int = 10
):
    """Get news articles for a stock"""
    from openbb_app.core.utils import get_news

    return get_news(symbol, limit).to_dict(orient="records")
