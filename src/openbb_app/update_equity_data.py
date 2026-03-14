#!/usr/bin/env python3
"""
股票历史数据增量更新脚本

该脚本用于维护应用中的股票观察列表，执行每日定期数据更新。
首次运行时从股票上市日期开始获取完整历史数据，后续仅获取增量数据。
"""

import sqlite3
import logging
import time
import argparse
import configparser
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from openbb_app.core.database import DatabaseManager
from openbb_app.core.data_source import DataSourceManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_equity_data.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class EquityDataUpdater:
    """股票数据更新器"""
    
    def __init__(self, db_path: Optional[Path] = None, config_file: Optional[Path] = None):
        """初始化股票数据更新器"""
        # 如果没有提供数据库路径，使用默认路径
        if db_path is None:
            from openbb_core.app.service.user_service import UserService
            settings = UserService.read_from_file()
            cache_dir = Path(settings.preferences.cache_directory)
            db_path = cache_dir / "appdata/equity.db"
        
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.data_source_manager = DataSourceManager()
        self.update_interval = 1  # 默认抓取间隔为1秒
        
        # 加载配置
        self._load_config(config_file)
    
    def _load_config(self, config_file: Optional[Path] = None):
        """加载配置文件"""
        if config_file and config_file.exists():
            config = configparser.ConfigParser()
            config.read(config_file)
            
            if 'General' in config:
                if 'update_interval' in config['General']:
                    try:
                        self.update_interval = float(config['General']['update_interval'])
                        logger.info(f"从配置文件加载抓取间隔: {self.update_interval} 秒")
                    except ValueError:
                        logger.warning("配置文件中的update_interval格式错误，使用默认值")
        else:
            logger.info("未指定配置文件或配置文件不存在，使用默认配置")
    
    def get_watchlist(self) -> List[str]:
        """从portfolio_stocks表中获取股票观察列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT symbol FROM portfolio_stocks")
            symbols = [row[0] for row in cursor.fetchall()]
            logger.info(f"从portfolio_stocks表中获取到{len(symbols)}只股票")
            return symbols
        except Exception as e:
            logger.error(f"获取观察列表失败: {e}")
            return []
        finally:
            conn.close()
    
    def get_list_date(self, symbol: str) -> str:
        """获取股票的上市日期"""
        default_date = "2000-01-01"
        
        try:
            metadata = self.db_manager.get_equity_metadata(symbol)
            
            if metadata and metadata.get('list_date'):
                list_date = metadata['list_date']
                if list_date and list_date.strip():
                    logger.debug(f"从 equity_metadata 表获取到股票 {symbol} 的上市日期: {list_date}")
                    return list_date
            
            logger.debug(f"股票 {symbol} 在 equity_metadata 表中无有效的 list_date 或记录不存在，使用默认值: {default_date}")
            return default_date
        except Exception as e:
            logger.warning(f"获取股票 {symbol} 的上市日期时发生异常: {e}，使用默认值: {default_date}")
            return default_date
    
    def update_stock_data(self, symbol: str) -> bool:
        """更新单个股票的数据"""
        try:
            # 获取最新数据日期
            latest_date = self.db_manager.get_latest_date(symbol)
            
            if latest_date:
                # 增量更新
                start_date = (datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                logger.info(f"为股票 {symbol} 执行增量更新，从 {start_date} 开始")
            else:
                # 首次更新
                start_date = self.get_list_date(symbol)
                logger.info(f"为股票 {symbol} 执行首次更新，从 {start_date} 开始")
            
            end_date = datetime.now().strftime("%Y-%m-%d")
            
            # 如果开始日期大于结束日期，跳过更新
            if start_date > end_date:
                logger.info(f"股票 {symbol} 数据已是最新，跳过更新")
                return True
            
            # 获取数据
            data, source = self.data_source_manager.get_data(symbol, start_date, end_date)
            
            if data:
                # 写入数据库
                self.db_manager.upsert_price_data(symbol, data, source)
                logger.info(f"成功更新股票 {symbol} 的数据，共 {len(data)} 条记录，来源: {source}")
                return True
            else:
                logger.warning(f"未获取到股票 {symbol} 的数据")
                return False
        except Exception as e:
            logger.error(f"更新股票 {symbol} 数据失败: {e}")
            return False
    
    def run(self):
        """运行数据更新"""
        logger.info("开始执行股票数据更新任务")
        start_time = time.time()
        
        # 获取观察列表
        watchlist = self.get_watchlist()
        
        if not watchlist:
            logger.warning("观察列表为空，跳过更新")
            return
        
        # 统计信息
        total = len(watchlist)
        success_count = 0
        failed_stocks = []
        
        # 逐个更新股票数据
        for symbol in watchlist:
            logger.info(f"开始更新股票: {symbol} ({watchlist.index(symbol) + 1}/{total})")
            if self.update_stock_data(symbol):
                success_count += 1
            else:
                failed_stocks.append(symbol)
            
            # 添加抓取间隔
            time.sleep(self.update_interval)
        
        # 生成执行报告
        end_time = time.time()
        duration = end_time - start_time
        
        report = {
            "total_stocks": total,
            "success_count": success_count,
            "failed_count": len(failed_stocks),
            "failed_stocks": failed_stocks,
            "duration": round(duration, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"股票数据更新任务完成")
        logger.info(f"报告: {report}")
        
        # 输出执行报告
        print("\n执行报告:")
        print(f"总股票数: {total}")
        print(f"成功更新: {success_count}")
        print(f"失败更新: {len(failed_stocks)}")
        if failed_stocks:
            print(f"失败的股票: {failed_stocks}")
        print(f"执行时间: {round(duration, 2)} 秒")
        print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 2. The CLI Entry Point
def start():
    from openbb_app.core.utils import check_api_keys

    check_api_keys()

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='股票历史数据增量更新脚本')
    parser.add_argument('--config', type=Path, help='配置文件路径')
    parser.add_argument('--db-path', type=Path, help='数据库路径')
    parser.add_argument('--interval', type=float, help='抓取间隔（秒）')
    
    args = parser.parse_args()
    
    # 创建更新器
    updater = EquityDataUpdater(db_path=args.db_path, config_file=args.config)
    
    # 如果命令行指定了抓取间隔，覆盖配置文件的值
    if args.interval:
        updater.update_interval = args.interval
        logger.info(f"从命令行参数设置抓取间隔: {updater.update_interval} 秒")
    
    # 运行更新
    updater.run()


if __name__ == "__main__":
    start()