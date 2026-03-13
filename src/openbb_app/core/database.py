import sqlite3
from pathlib import Path
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: Path):
        """初始化数据库管理器"""
        self.db_path = db_path
        self._ensure_directory()
        self._init_db()
    
    def _ensure_directory(self):
        """确保数据库目录存在"""
        logger.info(f"Creating directory for database: {self.db_path.parent}")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory created successfully: {self.db_path.parent}")
    
    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建历史价格表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS equity_price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            interval TEXT NOT NULL DEFAULT '1d',
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            amount REAL,
            source TEXT DEFAULT 'akshare',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, date, interval)
        )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_symbol_date ON equity_price_history(symbol, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_date ON equity_price_history(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_interval ON equity_price_history(interval)')
        
        # 创建元数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS equity_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            name TEXT,
            market TEXT,
            list_date TEXT,
            last_fetched TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建元数据索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_symbol ON equity_metadata(symbol)')
        
        # 创建自选股表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_stocks (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            current_price REAL NOT NULL DEFAULT 0,
            fifty_two_week_low REAL DEFAULT 0,
            fifty_two_week_high REAL DEFAULT 0,
            dividend_yield REAL DEFAULT 0,
            latest_dividend REAL DEFAULT 0,
            strategy TEXT DEFAULT '持有',
            avg_cost REAL DEFAULT 0,
            quantity INTEGER DEFAULT 0,
            total_value REAL DEFAULT 0,
            tradingview TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建交易记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES portfolio_stocks(symbol) ON DELETE CASCADE
        )
        ''')
        
        # 创建交易记录索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)')
        
        # 应用优化配置
        self._apply_optimizations(conn)
        
        conn.commit()
        conn.close()
    
    def _apply_optimizations(self, conn):
        """应用数据库优化配置"""
        cursor = conn.cursor()
        
        # 启用 WAL 模式，提升并发读写性能
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        # 设置同步模式为 NORMAL，平衡性能和数据安全
        cursor.execute("PRAGMA synchronous=NORMAL;")
        
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys=ON;")
        
        # 设置缓存大小（负数表示 KB）
        cursor.execute("PRAGMA cache_size=-64000;")  # 64MB
        
        # 启用内存映射 I/O
        cursor.execute("PRAGMA mmap_size=268435456;")  # 256MB
    
    def execute_with_retry(self, sql: str, params: tuple = (), max_retries: int = 3):
        """带重试机制的数据库执行"""
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
                conn.close()
                return True
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.1
                    time.sleep(wait_time)
                    continue
                logger.error(f"Database error: {e}")
                raise
        return False
    
    def upsert_price_data(self, symbol: str, price_data: list[dict], source: str = "akshare"):
        """增量更新历史价格数据"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        sql = """
        INSERT INTO equity_price_history 
            (symbol, date, interval, open, high, low, close, volume, amount, source, updated_at)
        VALUES 
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, date, interval) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            amount = excluded.amount,
            source = excluded.source,
            updated_at = excluded.updated_at
        """
        
        try:
            for row in price_data:
                cursor.execute(sql, (
                    symbol,
                    row['date'],
                    row.get('interval', '1d'),
                    row.get('open'),
                    row.get('high'),
                    row.get('low'),
                    row.get('close'),
                    row.get('volume'),
                    row.get('amount'),
                    source,
                    now
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error upserting price data: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_price_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d'):
        """获取指定股票的历史价格数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = """
        SELECT * FROM equity_price_history 
        WHERE symbol = ? AND date >= ? AND date <= ? AND interval = ? 
        ORDER BY date
        """
        
        cursor.execute(sql, (symbol, start_date, end_date, interval))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_latest_date(self, symbol: str, interval: str = '1d'):
        """获取股票最新交易日期"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(date) FROM equity_price_history WHERE symbol = ? AND interval = ?",
            (symbol, interval)
        )
        result = cursor.fetchone()[0]
        conn.close()
        return result
    
    def get_equity_metadata(self, symbol: str):
        """获取股票元数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM equity_metadata WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def add_equity_metadata(self, metadata: dict):
        """添加或更新股票元数据"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        sql = """
        INSERT INTO equity_metadata 
            (symbol, name, market, list_date, last_fetched, updated_at)
        VALUES 
            (?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            name = excluded.name,
            market = excluded.market,
            list_date = excluded.list_date,
            last_fetched = excluded.last_fetched,
            updated_at = excluded.updated_at
        """
        
        try:
            cursor.execute(sql, (
                metadata['symbol'],
                metadata.get('name'),
                metadata.get('market'),
                metadata.get('list_date'),
                metadata.get('last_fetched', now),
                now
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding equity metadata: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def update_equity_metadata(self, symbol: str, metadata: dict):
        """更新股票元数据"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        set_clauses = []
        params = []
        
        for key, value in metadata.items():
            if key != 'symbol':
                set_clauses.append(f"{key} = ?")
                params.append(value)
        
        if set_clauses:
            set_clauses.append("updated_at = ?")
            params.append(now)
            params.append(symbol)
            
            sql = f"UPDATE equity_metadata SET {', '.join(set_clauses)} WHERE symbol = ?"
            
            try:
                cursor.execute(sql, params)
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"Error updating equity metadata: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()
        return False
    
    def maintenance(self):
        """数据库维护任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 分析表，优化查询计划
            cursor.execute("ANALYZE;")
            
            # 清理空白页，重建数据库
            cursor.execute("VACUUM;")
            
            conn.commit()
            logger.info("Database maintenance completed")
        except Exception as e:
            logger.error(f"Error during maintenance: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    # Portfolio stocks methods
    def get_all_portfolio_stocks(self):
        """获取所有自选股"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM portfolio_stocks ORDER BY symbol")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_portfolio_stock(self, symbol: str):
        """获取单个自选股"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM portfolio_stocks WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def add_portfolio_stock(self, stock_data: dict):
        """添加新的自选股"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        sql = """
        INSERT INTO portfolio_stocks 
            (symbol, name, current_price, fifty_two_week_low, fifty_two_week_high, 
             dividend_yield, latest_dividend, strategy, avg_cost, quantity, total_value, tradingview, updated_at)
        VALUES 
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            name = excluded.name,
            current_price = excluded.current_price,
            fifty_two_week_low = excluded.fifty_two_week_low,
            fifty_two_week_high = excluded.fifty_two_week_high,
            dividend_yield = excluded.dividend_yield,
            latest_dividend = excluded.latest_dividend,
            strategy = excluded.strategy,
            avg_cost = excluded.avg_cost,
            quantity = excluded.quantity,
            total_value = excluded.total_value,
            tradingview = excluded.tradingview,
            updated_at = excluded.updated_at
        """
        
        try:
            cursor.execute(sql, (
                stock_data['symbol'],
                stock_data['name'],
                stock_data.get('current_price', 0),
                stock_data.get('fifty_two_week_low', 0),
                stock_data.get('fifty_two_week_high', 0),
                stock_data.get('dividend_yield', 0),
                stock_data.get('latest_dividend', 0),
                stock_data.get('strategy', '持有'),
                stock_data.get('avg_cost', 0),
                stock_data.get('quantity', 0),
                stock_data.get('total_value', 0),
                stock_data.get('tradingview'),
                now
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding portfolio stock: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def update_portfolio_stock(self, symbol: str, stock_data: dict):
        """更新自选股信息"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # 构建更新语句
        set_clauses = []
        params = []
        
        for key, value in stock_data.items():
            if key != 'symbol':
                set_clauses.append(f"{key} = ?")
                params.append(value)
        
        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(symbol)
        
        sql = f"UPDATE portfolio_stocks SET {', '.join(set_clauses)} WHERE symbol = ?"
        
        try:
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating portfolio stock: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def delete_portfolio_stock(self, symbol: str):
        """删除自选股"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM portfolio_stocks WHERE symbol = ?", (symbol,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting portfolio stock: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # Transactions methods
    def get_all_transactions(self, symbol: str = None, start_date: str = None, end_date: str = None):
        """获取交易记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        
        sql += " ORDER BY date DESC"
        
        cursor.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_transaction(self, transaction_id: int):
        """获取单个交易记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def add_transaction(self, transaction_data: dict):
        """添加交易记录并更新持仓数据"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            # 开始事务
            conn.execute('BEGIN TRANSACTION')
            
            # 验证卖出交易数量
            if transaction_data['transaction_type'] == '卖出':
                # 获取当前持有数量
                cursor.execute("SELECT quantity FROM portfolio_stocks WHERE symbol = ?", (transaction_data['symbol'],))
                stock = cursor.fetchone()
                if stock:
                    current_quantity = stock[0]
                    if transaction_data['quantity'] > current_quantity:
                        raise ValueError(f"卖出数量{transaction_data['quantity']}超过当前持有数量{current_quantity}")
            
            # 插入交易记录
            sql = """
            INSERT INTO transactions 
                (date, symbol, name, price, quantity, transaction_type, updated_at)
            VALUES 
                (?, ?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(sql, (
                transaction_data['date'],
                transaction_data['symbol'],
                transaction_data['name'],
                transaction_data['price'],
                transaction_data['quantity'],
                transaction_data['transaction_type'],
                now
            ))
            
            # 更新持仓数据
            self._update_portfolio_data(conn, transaction_data['symbol'])
            
            # 提交事务
            conn.commit()
            return True
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            conn.rollback()
            raise
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def update_transaction(self, transaction_id: int, transaction_data: dict):
        """更新交易记录并重新计算持仓数据"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            # 获取原交易记录以确定股票代码和类型
            cursor.execute("SELECT symbol, transaction_type, quantity FROM transactions WHERE id = ?", (transaction_id,))
            old_transaction = cursor.fetchone()
            if not old_transaction:
                return False
            
            old_symbol, old_type, old_quantity = old_transaction
            
            # 确定新的交易类型和数量
            new_type = transaction_data.get('transaction_type', old_type)
            new_quantity = transaction_data.get('quantity', old_quantity)
            new_symbol = transaction_data.get('symbol', old_symbol)
            
            # 开始事务
            conn.execute('BEGIN TRANSACTION')
            
            # 验证卖出交易数量
            if new_type == '卖出':
                # 计算当前持有数量（考虑原交易的影响）
                cursor.execute("SELECT quantity FROM portfolio_stocks WHERE symbol = ?", (new_symbol,))
                stock = cursor.fetchone()
                if stock:
                    current_quantity = stock[0]
                    # 如果原交易也是卖出，需要先加回原数量再验证
                    if old_type == '卖出' and old_symbol == new_symbol:
                        current_quantity += old_quantity
                    if new_quantity > current_quantity:
                        raise ValueError(f"卖出数量{new_quantity}超过当前持有数量{current_quantity}")
            
            # 构建更新语句
            set_clauses = []
            params = []
            
            for key, value in transaction_data.items():
                if key != 'id':
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            
            set_clauses.append("updated_at = ?")
            params.append(now)
            params.append(transaction_id)
            
            sql = f"UPDATE transactions SET {', '.join(set_clauses)} WHERE id = ?"
            
            cursor.execute(sql, params)
            
            # 如果股票代码改变，需要更新两个股票的持仓数据
            if 'symbol' in transaction_data and transaction_data['symbol'] != old_symbol:
                self._update_portfolio_data(conn, old_symbol)
                self._update_portfolio_data(conn, transaction_data['symbol'])
            else:
                self._update_portfolio_data(conn, new_symbol)
            
            # 提交事务
            conn.commit()
            return cursor.rowcount > 0
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            conn.rollback()
            raise
        except Exception as e:
            logger.error(f"Error updating transaction: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def delete_transaction(self, transaction_id: int):
        """删除交易记录并重新计算持仓数据"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        try:
            # 获取交易记录以确定股票代码
            cursor.execute("SELECT symbol FROM transactions WHERE id = ?", (transaction_id,))
            transaction = cursor.fetchone()
            if not transaction:
                return False
            
            symbol = transaction[0]
            
            # 开始事务
            conn.execute('BEGIN TRANSACTION')
            
            # 删除交易记录
            cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
            
            # 更新持仓数据
            self._update_portfolio_data(conn, symbol)
            
            # 提交事务
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting transaction: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _update_portfolio_data(self, conn, symbol: str):
        """更新指定股票的持仓数据"""
        cursor = conn.cursor()
        
        # 获取所有交易记录
        cursor.execute("SELECT price, quantity, transaction_type FROM transactions WHERE symbol = ? ORDER BY date", (symbol,))
        transactions = cursor.fetchall()
        
        # 计算持仓数据
        total_buy_cost = 0
        total_buy_quantity = 0
        total_sell_quantity = 0
        
        for price, quantity, transaction_type in transactions:
            if transaction_type == '买入':
                total_buy_cost += price * quantity
                total_buy_quantity += quantity
            elif transaction_type == '卖出':
                total_sell_quantity += quantity
        
        # 计算当前持有数量
        current_quantity = total_buy_quantity - total_sell_quantity
        
        # 计算持仓均价（基于买入成本）
        avg_cost = total_buy_cost / total_buy_quantity if total_buy_quantity > 0 else 0
        
        # 计算市值
        total_value = avg_cost * current_quantity
        
        # 更新持仓数据
        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE portfolio_stocks SET avg_cost = ?, quantity = ?, total_value = ?, updated_at = ? WHERE symbol = ?",
            (avg_cost, current_quantity, total_value, now, symbol)
        )
    
    def validate_portfolio_data(self):
        """验证持仓数据与交易记录的一致性"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取所有自选股
            cursor.execute("SELECT symbol, avg_cost, quantity, total_value FROM portfolio_stocks")
            stocks = cursor.fetchall()
            
            inconsistencies = []
            
            for symbol, db_avg_cost, db_quantity, db_total_value in stocks:
                # 重新计算持仓数据
                total_buy_cost = 0
                total_buy_quantity = 0
                total_sell_quantity = 0
                
                cursor.execute("SELECT price, quantity, transaction_type FROM transactions WHERE symbol = ? ORDER BY date", (symbol,))
                transactions = cursor.fetchall()
                
                for price, quantity, transaction_type in transactions:
                    if transaction_type == '买入':
                        total_buy_cost += price * quantity
                        total_buy_quantity += quantity
                    elif transaction_type == '卖出':
                        total_sell_quantity += quantity
                
                # 计算当前持有数量
                calc_quantity = total_buy_quantity - total_sell_quantity
                
                # 计算持仓均价（基于买入成本）
                calc_avg_cost = total_buy_cost / total_buy_quantity if total_buy_quantity > 0 else 0
                
                # 计算市值
                calc_total_value = calc_avg_cost * calc_quantity
                
                # 检查一致性
                if abs(calc_avg_cost - db_avg_cost) > 0.001 or calc_quantity != db_quantity or abs(calc_total_value - db_total_value) > 0.001:
                    inconsistencies.append({
                        'symbol': symbol,
                        'db_avg_cost': db_avg_cost,
                        'calc_avg_cost': calc_avg_cost,
                        'db_quantity': db_quantity,
                        'calc_quantity': calc_quantity,
                        'db_total_value': db_total_value,
                        'calc_total_value': calc_total_value
                    })
            
            return {
                'consistent': len(inconsistencies) == 0,
                'inconsistencies': inconsistencies
            }
        finally:
            conn.close()
