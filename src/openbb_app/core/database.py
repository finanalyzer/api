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
