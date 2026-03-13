import pytest
from pathlib import Path
from openbb_app.update_equity_data import EquityDataUpdater
from openbb_app.core.database import DatabaseManager
import tempfile
import os


class TestGetListDate:
    """Tests for get_list_date method in EquityDataUpdater."""

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield Path(path)
        os.unlink(path)

    @pytest.fixture
    def db_manager(self, temp_db_path):
        """创建数据库管理器实例"""
        return DatabaseManager(temp_db_path)

    @pytest.fixture
    def updater(self, temp_db_path):
        """创建 EquityDataUpdater 实例"""
        return EquityDataUpdater(db_path=temp_db_path)

    def test_get_list_date_with_valid_metadata(self, db_manager, updater):
        """测试从 equity_metadata 表正常读取 list_date"""
        symbol = "000001.SZ"
        list_date = "1991-04-03"
        
        db_manager.add_equity_metadata({
            'symbol': symbol,
            'name': '平安银行',
            'market': 'SZ',
            'list_date': list_date
        })
        
        result = updater.get_list_date(symbol)
        
        assert result == list_date

    def test_get_list_date_with_empty_list_date(self, db_manager, updater):
        """测试当 list_date 为空时使用默认值"""
        symbol = "000002.SZ"
        default_date = "2000-01-01"
        
        db_manager.add_equity_metadata({
            'symbol': symbol,
            'name': '万科A',
            'market': 'SZ',
            'list_date': None
        })
        
        result = updater.get_list_date(symbol)
        
        assert result == default_date

    def test_get_list_date_with_missing_list_date_field(self, db_manager, updater):
        """测试当 list_date 字段不存在时使用默认值"""
        symbol = "000003.SZ"
        default_date = "2000-01-01"
        
        db_manager.add_equity_metadata({
            'symbol': symbol,
            'name': '国农科技',
            'market': 'SZ'
        })
        
        result = updater.get_list_date(symbol)
        
        assert result == default_date

    def test_get_list_date_with_no_metadata_record(self, updater):
        """测试当 equity_metadata 表中不存在该股票记录时使用默认值"""
        symbol = "999999.SZ"
        default_date = "2000-01-01"
        
        result = updater.get_list_date(symbol)
        
        assert result == default_date

    def test_get_list_date_with_empty_string_list_date(self, db_manager, updater):
        """测试当 list_date 为空字符串时使用默认值"""
        symbol = "000004.SZ"
        default_date = "2000-01-01"
        
        db_manager.add_equity_metadata({
            'symbol': symbol,
            'name': '国华网安',
            'market': 'SZ',
            'list_date': ''
        })
        
        result = updater.get_list_date(symbol)
        
        assert result == default_date

    def test_get_list_date_with_whitespace_list_date(self, db_manager, updater):
        """测试当 list_date 为空白字符时使用默认值"""
        symbol = "000005.SZ"
        default_date = "2000-01-01"
        
        db_manager.add_equity_metadata({
            'symbol': symbol,
            'name': '世纪星源',
            'market': 'SZ',
            'list_date': '   '
        })
        
        result = updater.get_list_date(symbol)
        
        assert result == default_date
