import sqlite3
from pathlib import Path
from datetime import datetime
import logging
import time
from .utils import BUY, SELL

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
            avg_cost REAL DEFAULT 0,
            quantity INTEGER DEFAULT 0,
            total_value REAL DEFAULT 0
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
            base_value REAL NOT NULL DEFAULT 0,
            transaction_fee REAL NOT NULL DEFAULT 0,
            total_value REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES portfolio_stocks(symbol) ON DELETE CASCADE
        )
        ''')
        
        # 创建交易记录索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)')
        
        # 创建仪表盘表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dashboards (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            widgets TEXT DEFAULT '[]',
            tabs TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建仪表盘索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dashboards_id ON dashboards(id)')
        
        # 迁移：为现有数据库添加新列
        self._migrate_transactions_table(cursor)
        self._migrate_portfolio_stocks_table(cursor)
        self._migrate_dashboards_table(cursor)
        
        # 应用优化配置
        self._apply_optimizations(conn)
        
        conn.commit()
        conn.close()
    
    def _migrate_transactions_table(self, cursor):
        """迁移交易记录表，添加新列"""
        try:
            cursor.execute("PRAGMA table_info(transactions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'base_value' not in columns:
                cursor.execute("ALTER TABLE transactions ADD COLUMN base_value REAL NOT NULL DEFAULT 0")
                logger.info("Added base_value column to transactions table")
            
            if 'transaction_fee' not in columns:
                cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_fee REAL NOT NULL DEFAULT 0")
                logger.info("Added transaction_fee column to transactions table")
            
            if 'total_value' not in columns:
                cursor.execute("ALTER TABLE transactions ADD COLUMN total_value REAL NOT NULL DEFAULT 0")
                logger.info("Added total_value column to transactions table")
        except Exception as e:
            logger.warning(f"Migration warning: {e}")
    
    def _migrate_portfolio_stocks_table(self, cursor):
        """迁移自选股表，重构为新 schema"""
        try:
            cursor.execute("PRAGMA table_info(portfolio_stocks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # 检查是否需要迁移（如果表包含旧字段）
            if 'current_price' in columns or 'strategy' in columns or 'tradingview' in columns:
                logger.info("Migrating portfolio_stocks table to new schema")
                
                # 创建新表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio_stocks_new (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    avg_cost REAL DEFAULT 0,
                    quantity INTEGER DEFAULT 0,
                    total_value REAL DEFAULT 0
                )
                ''')
                
                # 复制数据
                cursor.execute('''
                INSERT INTO portfolio_stocks_new (symbol, name, avg_cost, quantity, total_value)
                SELECT symbol, name, avg_cost, quantity, total_value FROM portfolio_stocks
                ''')
                
                # 重命名表
                cursor.execute("DROP TABLE IF EXISTS portfolio_stocks_old")
                cursor.execute("ALTER TABLE portfolio_stocks RENAME TO portfolio_stocks_old")
                cursor.execute("ALTER TABLE portfolio_stocks_new RENAME TO portfolio_stocks")
                
                # 删除旧表
                cursor.execute("DROP TABLE IF EXISTS portfolio_stocks_old")
                
                logger.info("Successfully migrated portfolio_stocks table to new schema")
        except Exception as e:
            logger.warning(f"Migration warning for portfolio_stocks: {e}")

    def _migrate_dashboards_table(self, cursor):
        """迁移仪表盘表，添加 tabs 列"""
        try:
            cursor.execute("PRAGMA table_info(dashboards)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'tabs' not in columns:
                logger.info("Adding tabs column to dashboards table")
                cursor.execute("ALTER TABLE dashboards ADD COLUMN tabs TEXT DEFAULT '[]'")
                logger.info("Successfully added tabs column to dashboards table")
        except Exception as e:
            logger.warning(f"Migration warning for dashboards tabs: {e}")

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
    
    def fetch_all_portfolio_stocks_from_db(self) -> list[dict]:
        """Fetch all portfolio stocks from database without any transformations."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM portfolio_stocks ORDER BY symbol")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return rows
    
    def get_all_portfolio_stocks(self):
        """获取所有自选股"""
        from .utils import get_stock_quote, get_strategies, get_tvlink
        
        rows = self.fetch_all_portfolio_stocks_from_db()
        
        # Add dynamically retrieved and calculated fields
        for row in rows:
            # Get stock quote data
            quote_data = get_stock_quote(row['symbol'])
            row.update(quote_data)
            
            # Calculate strategy
            row['strategy'] = get_strategies(row['fifty_two_week_low'], row['fifty_two_week_high'], row['current_price'], 0.05)
            
            # Generate TradingView link
            row['tradingview'] = get_tvlink(row['symbol'])
        
        return rows
    
    def get_portfolio_stock(self, symbol: str):
        """获取单个自选股"""
        from .utils import get_stock_quote, get_strategies, get_tvlink
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM portfolio_stocks WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            row_dict = dict(row)
            
            # Get stock quote data
            quote_data = get_stock_quote(row_dict['symbol'])
            row_dict.update(quote_data)
            
            # Calculate strategy
            row_dict['strategy'] = get_strategies(row_dict['fifty_two_week_low'], row_dict['fifty_two_week_high'], row_dict['current_price'], 0.05)
            
            # Generate TradingView link
            row_dict['tradingview'] = get_tvlink(row_dict['symbol'])
            
            return row_dict
        
        return None
    
    def add_portfolio_stock(self, stock_data: dict):
        """添加新的自选股"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        sql = """
        INSERT INTO portfolio_stocks 
            (symbol, name, avg_cost, quantity, total_value)
        VALUES 
            (?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            name = excluded.name,
            avg_cost = excluded.avg_cost,
            quantity = excluded.quantity,
            total_value = excluded.total_value
        """
        
        try:
            cursor.execute(sql, (
                stock_data['symbol'],
                stock_data['name'],
                stock_data.get('avg_cost', 0),
                stock_data.get('quantity', 0),
                stock_data.get('total_value', 0)
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
        
        # 构建更新语句
        set_clauses = []
        params = []
        
        for key, value in stock_data.items():
            if key != 'symbol':
                set_clauses.append(f"{key} = ?")
                params.append(value)
        
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
        """删除自选股（支持级联删除关联交易记录）"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        try:
            # 启用外键约束（SQLite默认禁用）
            cursor.execute("PRAGMA foreign_keys=ON;")
            
            # 开始事务
            conn.execute('BEGIN TRANSACTION')
            logger.info(f"Starting transaction to delete portfolio stock: {symbol}")
            
            # 查询关联的交易记录
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE symbol = ?", (symbol,))
            transaction_count = cursor.fetchone()[0]
            logger.info(f"Found {transaction_count} associated transactions for symbol: {symbol}")
            
            # 如果有交易记录，先记录详细信息
            if transaction_count > 0:
                cursor.execute("SELECT id, date, transaction_type, quantity, price FROM transactions WHERE symbol = ?", (symbol,))
                transactions = cursor.fetchall()
                logger.info(f"Transactions to be deleted for {symbol}:")
                for trans in transactions:
                    logger.info(f"  - Transaction ID: {trans[0]}, Date: {trans[1]}, Type: {trans[2]}, Quantity: {trans[3]}, Price: {trans[4]}")
            
            # 删除自选股记录（会触发级联删除交易记录）
            cursor.execute("DELETE FROM portfolio_stocks WHERE symbol = ?", (symbol,))
            stock_deleted = cursor.rowcount > 0
            
            if stock_deleted:
                logger.info(f"Successfully deleted portfolio stock: {symbol}")
                # 验证交易记录是否被级联删除
                cursor.execute("SELECT COUNT(*) FROM transactions WHERE symbol = ?", (symbol,))
                remaining_transactions = cursor.fetchone()[0]
                if remaining_transactions == 0:
                    logger.info(f"All {transaction_count} associated transactions have been cascading deleted")
                else:
                    logger.warning(f"WARNING: {remaining_transactions} transactions still remain after cascading delete for {symbol}")
            
            # 提交事务
            conn.commit()
            logger.info(f"Transaction committed successfully for deleting stock: {symbol}")
            
            return {
                'success': stock_deleted,
                'symbol': symbol,
                'transactions_deleted': transaction_count
            }
        except Exception as e:
            # 回滚事务
            conn.rollback()
            logger.error(f"Error deleting portfolio stock {symbol}: {e}")
            logger.info(f"Transaction rolled back for deleting stock: {symbol}")
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
            # 验证数值输入
            price = float(transaction_data['price'])
            quantity = int(transaction_data['quantity'])
            
            if price <= 0:
                raise ValueError("价格必须大于0")
            if quantity <= 0:
                raise ValueError("数量必须大于0")
            
            # 计算基础价值（价格 × 数量）
            base_value = price * quantity
            
            # 处理交易手续费和总额
            if 'total_value' in transaction_data and transaction_data['total_value'] is not None:
                total_value = float(transaction_data['total_value'])
                if total_value <= 0:
                    raise ValueError("交易总额必须大于0")
                # 计算交易手续费 = 提供的总额 - 基础价值
                # 买入: total_value = base_value + fee (fee为正)
                # 卖出: total_value = base_value - fee (fee为负)
                transaction_fee = total_value - base_value
            else:
                # 如果未提供总额，手续费为0，总额等于基础价值
                transaction_fee = 0.0
                total_value = base_value
            
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
                (date, symbol, name, price, quantity, transaction_type, base_value, transaction_fee, total_value, updated_at)
            VALUES 
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(sql, (
                transaction_data['date'],
                transaction_data['symbol'],
                transaction_data['name'],
                price,
                quantity,
                transaction_data['transaction_type'],
                base_value,
                transaction_fee,
                total_value,
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
            cursor.execute("SELECT symbol, transaction_type, quantity, price, base_value, transaction_fee, total_value FROM transactions WHERE id = ?", (transaction_id,))
            old_transaction = cursor.fetchone()
            if not old_transaction:
                return False
            
            old_symbol, old_type, old_quantity, old_price, old_base_value, old_transaction_fee, old_total_value = old_transaction
            
            # 确定新的交易类型和数量
            new_type = transaction_data.get('transaction_type', old_type)
            new_quantity = transaction_data.get('quantity', old_quantity)
            new_symbol = transaction_data.get('symbol', old_symbol)
            new_price = transaction_data.get('price', old_price)
            
            # 验证数值输入
            if 'price' in transaction_data:
                new_price = float(transaction_data['price'])
                if new_price <= 0:
                    raise ValueError("价格必须大于0")
            
            if 'quantity' in transaction_data:
                new_quantity = int(transaction_data['quantity'])
                if new_quantity <= 0:
                    raise ValueError("数量必须大于0")
            
            # 计算新的基础价值
            new_base_value = new_price * new_quantity
            
            # 处理交易手续费和总额
            if 'total_value' in transaction_data and transaction_data['total_value'] is not None:
                new_total_value = float(transaction_data['total_value'])
                if new_total_value < 0:
                    raise ValueError("交易总额不能为负数")
                # 计算交易手续费 = 提供的总额 - 基础价值
                new_transaction_fee = new_total_value - new_base_value
            else:
                # 如果未提供总额，保持原有的手续费和总额关系，或重新计算
                if 'price' in transaction_data or 'quantity' in transaction_data:
                    # 如果价格或数量改变，但未提供总额，则手续费为0，总额等于基础价值
                    new_transaction_fee = 0.0
                    new_total_value = new_base_value
                else:
                    # 保持原有值
                    new_transaction_fee = old_transaction_fee
                    new_total_value = old_total_value
            
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
                if key != 'id' and key != 'total_value':
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            
            # 总是更新计算字段
            set_clauses.extend(['base_value = ?', 'transaction_fee = ?', 'total_value = ?'])
            params.extend([new_base_value, new_transaction_fee, new_total_value])
            
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
        cursor.execute("SELECT price, quantity, transaction_type, total_value FROM transactions WHERE symbol = ? ORDER BY date", (symbol,))
        transactions = cursor.fetchall()
        
        # 计算持仓数据
        total_buy_cost = 0
        total_buy_quantity = 0
        total_sell_quantity = 0
        
        for price, quantity, transaction_type, total_value in transactions:
            if transaction_type == BUY:
                # 使用总额（含手续费）作为买入成本
                total_buy_cost += total_value
                total_buy_quantity += quantity
            elif transaction_type == SELL:
                total_sell_quantity += quantity
        
        # 计算当前持有数量
        current_quantity = total_buy_quantity - total_sell_quantity
        
        # 计算持仓均价（基于买入总额，包含手续费）
        # 平均成本保持不变，不受卖出交易影响
        avg_cost = total_buy_cost / total_buy_quantity if total_buy_quantity > 0 else 0
        
        # 计算市值
        total_value = avg_cost * current_quantity
        
        # 更新持仓数据
        cursor.execute(
            "UPDATE portfolio_stocks SET avg_cost = ?, quantity = ?, total_value = ? WHERE symbol = ?",
            (avg_cost, current_quantity, total_value, symbol)
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
                
                cursor.execute("SELECT price, quantity, transaction_type, total_value FROM transactions WHERE symbol = ? ORDER BY date", (symbol,))
                transactions = cursor.fetchall()
                
                for price, quantity, transaction_type, total_value in transactions:
                    if transaction_type == BUY:
                        # 使用总额（含手续费）作为买入成本
                        total_buy_cost += total_value
                        total_buy_quantity += quantity
                    elif transaction_type == SELL:
                        total_sell_quantity += quantity
                
                # 计算当前持有数量
                calc_quantity = total_buy_quantity - total_sell_quantity
                
                # 计算持仓均价（基于买入总额，包含手续费）
                # 平均成本保持不变，不受卖出交易影响
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
    
    # Dashboard methods
    
    def get_all_dashboards(self):
        """获取所有仪表盘"""
        import json
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM dashboards ORDER BY created_at")
        rows = cursor.fetchall()
        conn.close()
        
        # 解析widgets JSON
        dashboards = []
        for row in rows:
            dashboard = dict(row)
            dashboard['widgets'] = json.loads(dashboard.get('widgets', '[]'))
            dashboard['tabs'] = json.loads(dashboard.get('tabs', '[]'))
            dashboards.append(dashboard)
        
        return dashboards
    
    def get_dashboard(self, dashboard_id: str):
        """获取单个仪表盘"""
        import json
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM dashboards WHERE id = ?", (dashboard_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            dashboard = dict(row)
            dashboard['widgets'] = json.loads(dashboard.get('widgets', '[]'))
            dashboard['tabs'] = json.loads(dashboard.get('tabs', '[]'))
            return dashboard
        return None
    
    def add_dashboard(self, dashboard_data: dict):
        """添加新的仪表盘"""
        import json
        
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        sql = """
        INSERT INTO dashboards 
            (id, name, description, widgets, tabs, created_at, updated_at)
        VALUES 
            (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            widgets = excluded.widgets,
            tabs = excluded.tabs,
            updated_at = excluded.updated_at
        """
        
        try:
            cursor.execute(sql, (
                dashboard_data['id'],
                dashboard_data['name'],
                dashboard_data.get('description'),
                json.dumps(dashboard_data.get('widgets', [])),
                json.dumps(dashboard_data.get('tabs', [])),
                now,
                now
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding dashboard: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def update_dashboard(self, dashboard_id: str, dashboard_data: dict):
        """更新仪表盘信息"""
        import json
        
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        set_clauses = []
        params = []
        
        for key, value in dashboard_data.items():
            if key == 'widgets':
                set_clauses.append("widgets = ?")
                params.append(json.dumps(value))
            elif key == 'tabs':
                set_clauses.append("tabs = ?")
                params.append(json.dumps(value))
            elif key != 'id':
                set_clauses.append(f"{key} = ?")
                params.append(value)
        
        if set_clauses:
            set_clauses.append("updated_at = ?")
            params.append(now)
            params.append(dashboard_id)
            
            sql = f"UPDATE dashboards SET {', '.join(set_clauses)} WHERE id = ?"
            
            try:
                cursor.execute(sql, params)
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"Error updating dashboard: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()
        return False
    
    def delete_dashboard(self, dashboard_id: str):
        """删除仪表盘"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM dashboards WHERE id = ?", (dashboard_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting dashboard: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
