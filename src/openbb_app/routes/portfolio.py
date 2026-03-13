from fastapi import APIRouter, Query, HTTPException, Path as FastAPIPath
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import logging
from pydantic import BaseModel, Field
from openbb_core.app.service.user_service import UserService
from openbb_app.core.database import DatabaseManager
from openbb import obb
from mysharelib.tools import normalize_symbol

logger = logging.getLogger(__name__)

# 创建路由器
portfolio_router = APIRouter()

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
class StockBase(BaseModel):
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    current_price: float = Field(default=0, ge=0, description="当前市场价格")
    fifty_two_week_low: float = Field(default=0, ge=0, description="52周最低价格")
    fifty_two_week_high: float = Field(default=0, ge=0, description="52周最高价格")
    dividend_yield: float = Field(default=0, ge=0, le=100, description="股息率")
    latest_dividend: float = Field(default=0, ge=0, description="最近股息")
    strategy: str = Field(default="持有", description="策略建议")
    tradingview: Optional[str] = Field(None, description="Tradingview链接")

class StockCreate(StockBase):
    pass

class StockUpdate(BaseModel):
    name: Optional[str] = Field(None, description="股票名称")
    current_price: Optional[float] = Field(None, ge=0, description="当前市场价格")
    fifty_two_week_low: Optional[float] = Field(None, ge=0, description="52周最低价格")
    fifty_two_week_high: Optional[float] = Field(None, ge=0, description="52周最高价格")
    dividend_yield: Optional[float] = Field(None, ge=0, le=100, description="股息率")
    latest_dividend: Optional[float] = Field(None, ge=0, description="最近股息")
    strategy: Optional[str] = Field(None, description="策略建议")
    tradingview: Optional[str] = Field(None, description="Tradingview链接")

class StockResponse(StockBase):
    avg_cost: float = Field(..., description="持仓均价")
    quantity: int = Field(..., description="持有数量")
    total_value: float = Field(..., description="市值总计")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True

# 交易记录模型
class TransactionBase(BaseModel):
    date: str = Field(..., description="交易日期")
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., gt=0, description="成交价格")
    quantity: int = Field(..., gt=0, description="成交数量")
    transaction_type: str = Field(..., description="交易类型")

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    date: Optional[str] = Field(None, description="交易日期")
    symbol: Optional[str] = Field(None, description="股票代码")
    name: Optional[str] = Field(None, description="股票名称")
    price: Optional[float] = Field(None, gt=0, description="成交价格")
    quantity: Optional[int] = Field(None, gt=0, description="成交数量")
    transaction_type: Optional[str] = Field(None, description="交易类型")

class TransactionResponse(TransactionBase):
    id: int = Field(..., description="交易记录ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True

# 自选股管理API
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
        symbol_b, symbol_f, market = normalize_symbol(stock.symbol)
        stock.symbol = symbol_f
        db_manager = get_db_manager()
        stock_data = stock.model_dump()
        stock_data.setdefault('avg_cost', 0)
        stock_data.setdefault('quantity', 0)
        stock_data.setdefault('total_value', 0)
        
        try:
            logger.info(f"Fetching equity profile for {stock.symbol} from AkShare")
            profile_data = obb.equity.profile(
                symbol=stock.symbol,
                provider='akshare',
                use_cache=True
            )
            
            logger.info(f"Converting profile data to DataFrame for {stock.symbol}")
            df = profile_data.to_dataframe()
            
            if not df.empty:
                logger.info(f"Extracting listing date from profile data for {stock.symbol}")
                latest_record = df.tail(1)
                
                list_date = None
                if '上市日期' in latest_record.columns:
                    list_date_value = latest_record['上市日期'].iloc[0]
                    if list_date_value:
                        list_date = str(list_date_value)
                        logger.info(f"Found listing date for {stock.symbol}: {list_date}")
                
                if list_date:
                    existing_metadata = db_manager.get_equity_metadata(stock.symbol)
                    metadata = {
                        'symbol': stock.symbol,
                        'name': stock.name,
                        'list_date': list_date
                    }
                    
                    if existing_metadata:
                        logger.info(f"Updating equity metadata for {stock.symbol}")
                        db_manager.update_equity_metadata(stock.symbol, {'list_date': list_date})
                    else:
                        logger.info(f"Creating new equity metadata for {stock.symbol}")
                        db_manager.add_equity_metadata(metadata)
                    
                    updated_metadata = db_manager.get_equity_metadata(stock.symbol)
                    if updated_metadata and updated_metadata.get('list_date') == list_date:
                        logger.info(f"Successfully verified listing date for {stock.symbol}: {list_date}")
                    else:
                        logger.warning(f"Failed to verify listing date for {stock.symbol}")
                else:
                    logger.warning(f"No listing date found in profile data for {stock.symbol}")
            else:
                logger.warning(f"Empty profile data returned for {stock.symbol}")
                
        except Exception as api_error:
            logger.error(f"Error fetching equity profile for {stock.symbol}: {api_error}")
            logger.info(f"Proceeding with stock creation without listing date for {stock.symbol}")
        
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
def update_stock(stock: StockUpdate, symbol: str = FastAPIPath(..., description="股票代码")):
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

@portfolio_router.delete("/portfolio/stocks/{symbol}")
def delete_stock(symbol: str = FastAPIPath(..., description="股票代码")):
    """删除自选股"""
    try:
        symbol_b, symbol_f, market = normalize_symbol(symbol)
        symbol = symbol_f
        db_manager = get_db_manager()
        success = db_manager.delete_portfolio_stock(symbol)
        if not success:
            raise HTTPException(status_code=404, detail="Stock not found")
        return {"message": "Stock deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting stock: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete stock")

# 交易记录管理API
@portfolio_router.get("/portfolio/transactions", response_model=List[TransactionResponse])
def get_all_transactions(
    symbol: Optional[str] = Query(None, description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
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

@portfolio_router.get("/portfolio/transactions/{transaction_id}", response_model=TransactionResponse)
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
        # 验证股票是否存在
        stock = db_manager.get_portfolio_stock(transaction.symbol)
        if not stock:
            # 如果股票不存在，自动创建
            stock_data = {
                'symbol': transaction.symbol,
                'name': transaction.name,
                'current_price': transaction.price,
                'avg_cost': 0,
                'quantity': 0,
                'total_value': 0
            }
            db_manager.add_portfolio_stock(stock_data)
        
        transaction_data = transaction.model_dump()
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
        raise HTTPException(status_code=500, detail="Failed to create transaction")

@portfolio_router.put("/portfolio/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(transaction: TransactionUpdate, transaction_id: int = FastAPIPath(..., description="交易记录ID")):
    """更新交易记录"""
    try:
        db_manager = get_db_manager()
        existing_transaction = db_manager.get_transaction(transaction_id)
        if not existing_transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        transaction_data = transaction.model_dump(exclude_unset=True)
        if 'symbol' in transaction_data:
            symbol_b, symbol_f, market = normalize_symbol(transaction_data['symbol'])
            transaction_data['symbol'] = symbol_f
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
def delete_transaction(transaction_id: int = FastAPIPath(..., description="交易记录ID")):
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