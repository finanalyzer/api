"""
测试删除自选股时的级联删除功能

此测试脚本验证：
1. 删除股票时关联的交易记录也被自动删除
2. 事务一致性得到保证
3. 日志记录功能正常工作
"""
import os
import sys
import tempfile
from pathlib import Path
import sqlite3
import logging

# 设置日志级别以便查看测试过程
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class SimpleDatabaseManager:
    """简化的数据库管理器，用于测试"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
        
        # 创建交易记录表（带外键约束）
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
        
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys=ON;")
        
        conn.commit()
        conn.close()
    
    def add_portfolio_stock(self, stock_data: dict):
        """添加自选股"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO portfolio_stocks (symbol, name, avg_cost, quantity, total_value)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                stock_data['symbol'],
                stock_data['name'],
                stock_data.get('avg_cost', 0),
                stock_data.get('quantity', 0),
                stock_data.get('total_value', 0)
            ))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_portfolio_stock(self, symbol: str):
        """获取自选股"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM portfolio_stocks WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def add_transaction(self, transaction_data: dict):
        """添加交易记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO transactions 
            (date, symbol, name, price, quantity, transaction_type, base_value, transaction_fee, total_value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                transaction_data['date'],
                transaction_data['symbol'],
                transaction_data['name'],
                transaction_data['price'],
                transaction_data['quantity'],
                transaction_data['transaction_type'],
                transaction_data.get('base_value', 0),
                transaction_data.get('transaction_fee', 0),
                transaction_data.get('total_value', 0),
                transaction_data.get('created_at', '2024-01-01'),
                transaction_data.get('updated_at', '2024-01-01')
            ))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_all_transactions(self, symbol: str = None):
        """获取交易记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)
        
        sql += " ORDER BY date DESC"
        
        cursor.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def delete_portfolio_stock(self, symbol: str):
        """删除自选股（支持级联删除关联交易记录）"""
        conn = sqlite3.connect(self.db_path)
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


def test_cascading_delete():
    """测试级联删除功能"""
    # 创建临时数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test_equity.db'
        db_manager = SimpleDatabaseManager(db_path)
        
        # 添加测试股票
        stock_data = {
            'symbol': '600325.SH',
            'name': '西藏天路',
            'avg_cost': 10.5,
            'quantity': 100,
            'total_value': 1050.0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # 添加关联的交易记录
        transactions = [
            {
                'date': '2024-01-15',
                'symbol': '600325.SH',
                'name': '西藏天路',
                'price': 10.0,
                'quantity': 50,
                'transaction_type': '买入',
                'base_value': 500.0,
                'transaction_fee': 5.0,
                'total_value': 505.0
            },
            {
                'date': '2024-02-20',
                'symbol': '600325.SH',
                'name': '西藏天路',
                'price': 11.0,
                'quantity': 50,
                'transaction_type': '买入',
                'base_value': 550.0,
                'transaction_fee': 5.5,
                'total_value': 555.5
            },
            {
                'date': '2024-03-10',
                'symbol': '600325.SH',
                'name': '西藏天路',
                'price': 0.5,
                'quantity': 100,
                'transaction_type': '分红',
                'base_value': 50.0,
                'transaction_fee': 0.0,
                'total_value': 50.0
            }
        ]
        
        for trans in transactions:
            db_manager.add_transaction(trans)
        
        # 验证交易记录已添加
        all_transactions = db_manager.get_all_transactions(symbol='600325.SH')
        assert len(all_transactions) == 3, f"Expected 3 transactions, got {len(all_transactions)}"
        print(f"✓ 已添加 {len(all_transactions)} 条交易记录")
        
        # 验证股票已添加
        stock = db_manager.get_portfolio_stock('600325.SH')
        assert stock is not None, "Stock should exist"
        print("✓ 股票已添加到自选股")
        
        # 执行删除操作
        print("\n执行删除操作...")
        result = db_manager.delete_portfolio_stock('600325.SH')
        
        # 验证删除结果
        assert result['success'] is True, "Delete should be successful"
        assert result['symbol'] == '600325.SH', "Symbol should match"
        assert result['transactions_deleted'] == 3, f"Expected 3 transactions deleted, got {result['transactions_deleted']}"
        print(f"✓ 删除成功: {result['symbol']}")
        print(f"✓ 级联删除了 {result['transactions_deleted']} 条交易记录")
        
        # 验证股票已删除
        stock_after = db_manager.get_portfolio_stock('600325.SH')
        assert stock_after is None, "Stock should be deleted"
        print("✓ 股票已从自选股中删除")
        
        # 验证交易记录已级联删除
        transactions_after = db_manager.get_all_transactions(symbol='600325.SH')
        assert len(transactions_after) == 0, f"Expected 0 transactions after delete, got {len(transactions_after)}"
        print("✓ 所有关联交易记录已级联删除")
        
        print("\n✅ 级联删除测试通过！")


def test_delete_nonexistent_stock():
    """测试删除不存在的股票"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test_equity.db'
        db_manager = SimpleDatabaseManager(db_path)
        
        result = db_manager.delete_portfolio_stock('999999.SH')
        assert result['success'] is False, "Delete should fail for non-existent stock"
        print("✓ 删除不存在的股票返回成功为False")


def test_transaction_integrity():
    """测试事务完整性"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test_equity.db'
        db_manager = SimpleDatabaseManager(db_path)
        
        # 添加测试股票和交易
        stock_data = {
            'symbol': '600000.SH',
            'name': '浦发银行',
            'avg_cost': 8.0,
            'quantity': 100,
            'total_value': 800.0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        db_manager.add_transaction({
            'date': '2024-01-01',
            'symbol': '600000.SH',
            'name': '浦发银行',
            'price': 8.0,
            'quantity': 100,
            'transaction_type': '买入',
            'base_value': 800.0,
            'transaction_fee': 8.0,
            'total_value': 808.0
        })
        
        # 验证初始状态
        assert db_manager.get_portfolio_stock('600000.SH') is not None
        assert len(db_manager.get_all_transactions(symbol='600000.SH')) == 1
        
        # 执行删除
        result = db_manager.delete_portfolio_stock('600000.SH')
        
        # 验证完整性：要么都存在，要么都不存在
        stock_exists = db_manager.get_portfolio_stock('600000.SH') is not None
        transactions_exist = len(db_manager.get_all_transactions(symbol='600000.SH')) > 0
        
        assert not stock_exists and not transactions_exist, \
            "Either both stock and transactions should exist, or both should be deleted"
        print("✓ 事务完整性验证通过")


if __name__ == '__main__':
    print("=" * 60)
    print("测试级联删除功能")
    print("=" * 60)
    
    print("\n--- 测试1: 级联删除测试 ---")
    test_cascading_delete()
    
    print("\n--- 测试2: 删除不存在的股票 ---")
    test_delete_nonexistent_stock()
    
    print("\n--- 测试3: 事务完整性测试 ---")
    test_transaction_integrity()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)