import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
from datetime import datetime
from openbb_app.core.database import DatabaseManager
from fastapi import HTTPException

# Import the functions we need to test
import openbb_app.routes.portfolio as portfolio_module
get_stock_name_by_search = portfolio_module.get_stock_name_by_search
validate_symbol_format = portfolio_module.validate_symbol_format
create_transaction = portfolio_module.create_transaction

class TestPortfolio:
    """Tests for portfolio functionality."""

    @pytest.fixture
    def db_manager(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield DatabaseManager(db_path)

    def test_add_portfolio_stock(self, db_manager):
        """Test adding a new portfolio stock."""
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 15.0,
            'quantity': 100,
            'total_value': 1500.0
        }
        
        result = db_manager.add_portfolio_stock(stock_data)
        assert result is True
        
        # Verify the stock was added
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock is not None
        assert stock['symbol'] == '000001.SZ'
        assert stock['name'] == '平安银行'
        assert stock['avg_cost'] == 15.0
        assert stock['quantity'] == 100
        assert stock['total_value'] == 1500.0
        # Verify dynamically added fields are present
        assert 'current_price' in stock
        assert 'fifty_two_week_low' in stock
        assert 'fifty_two_week_high' in stock
        assert 'dividend_yield' in stock
        assert 'latest_dividend' in stock
        assert 'strategy' in stock
        assert 'tradingview' in stock

    def test_update_portfolio_stock(self, db_manager):
        """Test updating a portfolio stock."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 15.0,
            'quantity': 100,
            'total_value': 1500.0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Update the stock
        update_data = {
            'name': '更新后的平安银行',
            'avg_cost': 16.0,
            'quantity': 200,
            'total_value': 3200.0
        }
        result = db_manager.update_portfolio_stock('000001.SZ', update_data)
        assert result is True
        
        # Verify the update
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock['name'] == '更新后的平安银行'
        assert stock['avg_cost'] == 16.0
        assert stock['quantity'] == 200
        assert stock['total_value'] == 3200.0

    def test_delete_portfolio_stock(self, db_manager):
        """Test deleting a portfolio stock."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 15.0,
            'quantity': 100,
            'total_value': 1500.0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Verify the stock exists
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock is not None
        
        # Delete the stock
        result = db_manager.delete_portfolio_stock('000001.SZ')
        assert result is True
        
        # Verify the stock was deleted
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock is None

    def test_add_transaction_buy(self, db_manager):
        """Test adding a buy transaction."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 0,
            'quantity': 0,
            'total_value': 0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Add a buy transaction
        transaction_data = {
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入'
        }
        result = db_manager.add_transaction(transaction_data)
        assert result is True
        
        # Verify the transaction was added
        transactions = db_manager.get_all_transactions('000001.SZ')
        assert len(transactions) == 1
        assert transactions[0]['transaction_type'] == '买入'
        assert transactions[0]['quantity'] == 100
        
        # Verify the portfolio data was updated
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock['quantity'] == 100
        assert stock['avg_cost'] == 15.0
        assert stock['total_value'] == 1500.0

    def test_add_transaction_sell(self, db_manager):
        """Test adding a sell transaction."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 0,
            'quantity': 0,
            'total_value': 0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Add a buy transaction
        buy_transaction = {
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入'
        }
        db_manager.add_transaction(buy_transaction)
        
        # Add a sell transaction
        sell_transaction = {
            'date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 16.0,
            'quantity': 50,
            'transaction_type': '卖出'
        }
        result = db_manager.add_transaction(sell_transaction)
        assert result is True
        
        # Verify the transaction was added
        transactions = db_manager.get_all_transactions('000001.SZ')
        assert len(transactions) == 2
        assert transactions[0]['transaction_type'] == '卖出'  # Latest first
        assert transactions[0]['quantity'] == 50
        
        # Verify the portfolio data was updated
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock['quantity'] == 50
        assert stock['avg_cost'] == 15.0  # Avg cost remains the same
        assert stock['total_value'] == 750.0

    def test_add_transaction_sell_exceeds_quantity(self, db_manager):
        """Test adding a sell transaction that exceeds current quantity."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 0,
            'quantity': 0,
            'total_value': 0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Add a buy transaction
        buy_transaction = {
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入'
        }
        db_manager.add_transaction(buy_transaction)
        
        # Try to sell more than current quantity
        sell_transaction = {
            'date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 16.0,
            'quantity': 150,  # More than current 100
            'transaction_type': '卖出'
        }
        
        with pytest.raises(ValueError, match="卖出数量150超过当前持有数量100"):
            db_manager.add_transaction(sell_transaction)

    def test_update_transaction(self, db_manager):
        """Test updating a transaction."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 0,
            'quantity': 0,
            'total_value': 0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Add a transaction
        transaction_data = {
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入'
        }
        db_manager.add_transaction(transaction_data)
        
        # Get the transaction ID
        transactions = db_manager.get_all_transactions('000001.SZ')
        transaction_id = transactions[0]['id']
        
        # Update the transaction
        update_data = {
            'quantity': 200,
            'price': 15.5
        }
        result = db_manager.update_transaction(transaction_id, update_data)
        assert result is True
        
        # Verify the transaction was updated
        updated_transaction = db_manager.get_transaction(transaction_id)
        assert updated_transaction['quantity'] == 200
        assert updated_transaction['price'] == 15.5
        
        # Verify the portfolio data was updated
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock['quantity'] == 200
        assert stock['avg_cost'] == 15.5
        assert stock['total_value'] == 3100.0

    def test_delete_transaction(self, db_manager):
        """Test deleting a transaction."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 0,
            'quantity': 0,
            'total_value': 0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Add a transaction
        transaction_data = {
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入'
        }
        db_manager.add_transaction(transaction_data)
        
        # Get the transaction ID
        transactions = db_manager.get_all_transactions('000001.SZ')
        transaction_id = transactions[0]['id']
        
        # Delete the transaction
        result = db_manager.delete_transaction(transaction_id)
        assert result is True
        
        # Verify the transaction was deleted
        transactions = db_manager.get_all_transactions('000001.SZ')
        assert len(transactions) == 0
        
        # Verify the portfolio data was updated
        stock = db_manager.get_portfolio_stock('000001.SZ')
        assert stock['quantity'] == 0
        assert stock['avg_cost'] == 0
        assert stock['total_value'] == 0

    def test_validate_portfolio_data(self, db_manager):
        """Test validating portfolio data consistency."""
        # Add a stock first
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 0,
            'quantity': 0,
            'total_value': 0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Add a transaction
        transaction_data = {
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入'
        }
        db_manager.add_transaction(transaction_data)
        
        # Validate data consistency
        validation_result = db_manager.validate_portfolio_data()
        assert validation_result['consistent'] is True
        assert len(validation_result['inconsistencies']) == 0

    def test_get_all_portfolio_stocks(self, db_manager):
        """Test getting all portfolio stocks."""
        # Add multiple stocks
        stocks = [
            {
                'symbol': '000001.SZ',
                'name': '平安银行',
                'avg_cost': 15.0,
                'quantity': 100,
                'total_value': 1500.0
            },
            {
                'symbol': '600000.SH',
                'name': '浦发银行',
                'avg_cost': 10.0,
                'quantity': 200,
                'total_value': 2000.0
            }
        ]
        
        for stock in stocks:
            db_manager.add_portfolio_stock(stock)
        
        # Get all stocks
        all_stocks = db_manager.get_all_portfolio_stocks()
        assert len(all_stocks) == 2
        symbols = [stock['symbol'] for stock in all_stocks]
        assert '000001.SZ' in symbols
        assert '600000.SH' in symbols
        # Verify dynamically added fields are present for all stocks
        for stock in all_stocks:
            assert 'current_price' in stock
            assert 'fifty_two_week_low' in stock
            assert 'fifty_two_week_high' in stock
            assert 'dividend_yield' in stock
            assert 'latest_dividend' in stock
            assert 'strategy' in stock
            assert 'tradingview' in stock

    def test_get_all_transactions_with_filters(self, db_manager):
        """Test getting transactions with filters."""
        # Add a stock
        stock_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 0,
            'quantity': 0,
            'total_value': 0
        }
        db_manager.add_portfolio_stock(stock_data)
        
        # Add multiple transactions
        transactions = [
            {
                'date': '2024-01-01',
                'symbol': '000001.SZ',
                'name': '平安银行',
                'price': 15.0,
                'quantity': 100,
                'transaction_type': '买入'
            },
            {
                'date': '2024-01-02',
                'symbol': '000001.SZ',
                'name': '平安银行',
                'price': 16.0,
                'quantity': 50,
                'transaction_type': '卖出'
            },
            {
                'date': '2024-01-03',
                'symbol': '000001.SZ',
                'name': '平安银行',
                'price': 15.5,
                'quantity': 100,
                'transaction_type': '买入'
            }
        ]
        
        for transaction in transactions:
            db_manager.add_transaction(transaction)
        
        # Get all transactions
        all_transactions = db_manager.get_all_transactions()
        assert len(all_transactions) == 3
        
        # Get transactions for specific symbol
        symbol_transactions = db_manager.get_all_transactions(symbol='000001.SZ')
        assert len(symbol_transactions) == 3
        
        # Get transactions within date range
        date_range_transactions = db_manager.get_all_transactions(
            start_date='2024-01-01',
            end_date='2024-01-02'
        )
        assert len(date_range_transactions) == 2


class TestStockNameAutoSearch:
    """Tests for automatic stock name search functionality."""

    def test_validate_symbol_format_valid_shenzhen(self):
        """Test validating valid Shenzhen stock symbol."""
        assert validate_symbol_format('000001.SZ') is True
        assert validate_symbol_format('300001.SZ') is True

    def test_validate_symbol_format_valid_shanghai(self):
        """Test validating valid Shanghai stock symbol."""
        assert validate_symbol_format('600000.SH') is True
        assert validate_symbol_format('688001.SH') is True

    def test_validate_symbol_format_valid_hk(self):
        """Test validating valid Hong Kong stock symbol."""
        assert validate_symbol_format('00700.HK') is True
        assert validate_symbol_format('09988.HK') is True

    def test_validate_symbol_format_invalid(self):
        """Test validating invalid stock symbols."""
        assert validate_symbol_format('000001') is False
        assert validate_symbol_format('000001.S') is False
        assert validate_symbol_format('ABC.SZ') is False
        assert validate_symbol_format('12345.SZ') is False  # 5位数字，应该是6位
        assert validate_symbol_format('1234567.SH') is False  # 7位数字，应该是6位
        assert validate_symbol_format('00700.H') is False
        assert validate_symbol_format('00700.SZ') is False  # 港股代码不应该用SZ后缀

    @patch('openbb_app.routes.portfolio.obb')
    def test_get_stock_name_by_search_success(self, mock_obb):
        """Test successful stock name search."""
        # Mock the search result
        import pandas as pd
        
        mock_df = pd.DataFrame({'name': ['平安银行']})
        
        mock_result = MagicMock()
        mock_result.to_dataframe.return_value = mock_df
        mock_obb.equity.search.return_value = mock_result
        
        # Clear cache to ensure fresh call
        get_stock_name_by_search.cache_clear()
        
        # Test the function
        result = get_stock_name_by_search('000001.SZ')
        assert result == '平安银行'
        mock_obb.equity.search.assert_called_once_with(query='000001.SZ', use_cache=True)

    @patch('openbb_app.routes.portfolio.obb')
    def test_get_stock_name_by_search_no_results(self, mock_obb):
        """Test stock name search with no results."""
        # Mock empty result
        import pandas as pd
        
        mock_df = pd.DataFrame()
        
        mock_result = MagicMock()
        mock_result.to_dataframe.return_value = mock_df
        mock_obb.equity.search.return_value = mock_result
        
        # Clear cache to ensure fresh call
        get_stock_name_by_search.cache_clear()
        
        # Test the function
        result = get_stock_name_by_search('000001.SZ')
        assert result is None

    @patch('openbb_app.routes.portfolio.obb')
    def test_get_stock_name_by_search_multiple_results(self, mock_obb):
        """Test stock name search with multiple results."""
        # Mock multiple results
        import pandas as pd
        
        mock_df = pd.DataFrame({'name': ['平安银行', '招商银行']})
        
        mock_result = MagicMock()
        mock_result.to_dataframe.return_value = mock_df
        mock_obb.equity.search.return_value = mock_result
        
        # Clear cache to ensure fresh call
        get_stock_name_by_search.cache_clear()
        
        # Test the function
        result = get_stock_name_by_search('000001.SZ')
        assert result is None

    @patch('openbb_app.routes.portfolio.obb')
    def test_get_stock_name_by_search_api_error(self, mock_obb):
        """Test stock name search with API error."""
        # Mock API error
        mock_obb.equity.search.side_effect = Exception('API Error')
        
        # Clear cache to ensure fresh call
        get_stock_name_by_search.cache_clear()
        
        # Test the function
        result = get_stock_name_by_search('000001.SZ')
        assert result is None

    @patch('openbb_app.routes.portfolio.obb')
    def test_get_stock_name_by_search_cache_hit(self, mock_obb):
        """Test that stock name search uses cache."""
        # Mock the search result
        import pandas as pd
        
        mock_df = pd.DataFrame({'name': ['平安银行']})
        
        mock_result = MagicMock()
        mock_result.to_dataframe.return_value = mock_df
        mock_obb.equity.search.return_value = mock_result
        
        # Clear cache to ensure fresh call
        get_stock_name_by_search.cache_clear()
        
        # First call
        result1 = get_stock_name_by_search('000001.SZ')
        assert result1 == '平安银行'
        assert mock_obb.equity.search.call_count == 1
        
        # Second call should use cache
        result2 = get_stock_name_by_search('000001.SZ')
        assert result2 == '平安银行'
        assert mock_obb.equity.search.call_count == 1  # Should not increase

    @patch('openbb_app.routes.portfolio.obb')
    def test_get_stock_name_by_search_different_name_fields(self, mock_obb):
        """Test stock name search with different name field names."""
        import pandas as pd
        
        # Test with 'short_name' field
        mock_df = pd.DataFrame({'short_name': ['平安银行']})
        
        mock_result = MagicMock()
        mock_result.to_dataframe.return_value = mock_df
        mock_obb.equity.search.return_value = mock_result
        
        # Clear cache to ensure fresh call
        get_stock_name_by_search.cache_clear()
        
        result = get_stock_name_by_search('000001.SZ')
        assert result == '平安银行'

        # Test with 'long_name' field
        mock_df = pd.DataFrame({'long_name': ['平安银行']})
        mock_result.to_dataframe.return_value = mock_df
        
        get_stock_name_by_search.cache_clear()
        
        result = get_stock_name_by_search('000001.SZ')
        assert result == '平安银行'

        # Test with no name field
        mock_df = pd.DataFrame({'symbol': ['000001.SZ'], 'price': [15.0]})
        mock_result.to_dataframe.return_value = mock_df
        
        get_stock_name_by_search.cache_clear()
        
        result = get_stock_name_by_search('000001.SZ')
        assert result is None

    @patch('openbb_app.routes.portfolio.get_db_manager')
    @patch('openbb_app.routes.portfolio.normalize_symbol')
    @patch('openbb_app.routes.portfolio.get_stock_name_by_search')
    def test_create_transaction_with_empty_date(self, mock_get_stock_name, mock_normalize, mock_get_db):
        """Test creating transaction with empty date (should use current date)."""
        # Mock normalize_symbol
        mock_normalize.return_value = ('000001', '000001.SZ', 'SZ')
        
        # Mock stock name search
        mock_get_stock_name.return_value = '平安银行'
        
        # Mock database manager
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock existing stock
        mock_stock = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 15.0,
            'quantity': 100,
            'total_value': 1500.0
        }
        mock_db.get_portfolio_stock.return_value = mock_stock
        
        # Mock transaction data
        mock_transaction = {
            'id': 1,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入',
            'total_value': 1500.0,
            'base_value': 1500.0,
            'transaction_fee': 0.0,
            'created_at': '2024-01-01 00:00:00',
            'updated_at': '2024-01-01 00:00:00'
        }
        mock_db.get_all_transactions.return_value = [mock_transaction]
        
        # Create transaction with empty date
        from openbb_app.routes.portfolio import TransactionCreate
        transaction = TransactionCreate(
            date=None,
            symbol='000001.SZ',
            name=None,
            price=15.0,
            quantity=100,
            transaction_type='买入'
        )
        
        # Call the function
        result = create_transaction(transaction)
        
        # Verify date was set to current date
        assert result is not None
        assert mock_db.add_transaction.called
        call_args = mock_db.add_transaction.call_args[0][0]
        assert call_args['date'] == datetime.now().strftime('%Y-%m-%d')
        
        # Verify stock name was auto-filled
        assert call_args['name'] == '平安银行'

    @patch('openbb_app.routes.portfolio.get_db_manager')
    @patch('openbb_app.routes.portfolio.normalize_symbol')
    @patch('openbb_app.routes.portfolio.get_stock_name_by_search')
    def test_create_transaction_with_invalid_date_format(self, mock_get_stock_name, mock_normalize, mock_get_db):
        """Test creating transaction with invalid date format."""
        # Mock normalize_symbol
        mock_normalize.return_value = ('000001', '000001.SZ', 'SZ')
        
        # Mock database manager
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Create transaction with invalid date format
        from openbb_app.routes.portfolio import TransactionCreate
        transaction = TransactionCreate(
            date='2024/01/01',
            symbol='000001.SZ',
            name='平安银行',
            price=15.0,
            quantity=100,
            transaction_type='买入'
        )
        
        # Call the function and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            create_transaction(transaction)
        
        assert exc_info.value.status_code == 400
        assert 'Invalid date format' in str(exc_info.value.detail)

    @patch('openbb_app.routes.portfolio.get_db_manager')
    @patch('openbb_app.routes.portfolio.normalize_symbol')
    @patch('openbb_app.routes.portfolio.get_stock_name_by_search')
    def test_create_transaction_with_empty_name(self, mock_get_stock_name, mock_normalize, mock_get_db):
        """Test creating transaction with empty name (should auto-fill)."""
        # Mock normalize_symbol
        mock_normalize.return_value = ('000001', '000001.SZ', 'SZ')
        
        # Mock stock name search
        mock_get_stock_name.return_value = '平安银行'
        
        # Mock database manager
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock existing stock
        mock_stock = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 15.0,
            'quantity': 100,
            'total_value': 1500.0
        }
        mock_db.get_portfolio_stock.return_value = mock_stock
        
        # Mock transaction data
        mock_transaction = {
            'id': 1,
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入',
            'total_value': 1500.0,
            'base_value': 1500.0,
            'transaction_fee': 0.0,
            'created_at': '2024-01-01 00:00:00',
            'updated_at': '2024-01-01 00:00:00'
        }
        mock_db.get_all_transactions.return_value = [mock_transaction]
        
        # Create transaction with empty name
        from openbb_app.routes.portfolio import TransactionCreate
        transaction = TransactionCreate(
            date='2024-01-01',
            symbol='000001.SZ',
            name=None,
            price=15.0,
            quantity=100,
            transaction_type='买入'
        )
        
        # Call the function
        result = create_transaction(transaction)
        
        # Verify stock name was auto-filled
        assert result is not None
        assert mock_db.add_transaction.called
        call_args = mock_db.add_transaction.call_args[0][0]
        assert call_args['name'] == '平安银行'
        mock_get_stock_name.assert_called_once_with('000001.SZ')

    @patch('openbb_app.routes.portfolio.get_db_manager')
    @patch('openbb_app.routes.portfolio.normalize_symbol')
    @patch('openbb_app.routes.portfolio.get_stock_name_by_search')
    def test_create_transaction_with_empty_name_search_fails(self, mock_get_stock_name, mock_normalize, mock_get_db):
        """Test creating transaction with empty name when search fails."""
        # Mock normalize_symbol
        mock_normalize.return_value = ('000001', '000001.SZ', 'SZ')
        
        # Mock stock name search to return None (search fails)
        mock_get_stock_name.return_value = None
        
        # Mock database manager
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Create transaction with empty name
        from openbb_app.routes.portfolio import TransactionCreate
        transaction = TransactionCreate(
            date='2024-01-01',
            symbol='000001.SZ',
            name=None,
            price=15.0,
            quantity=100,
            transaction_type='买入'
        )
        
        # Call the function and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            create_transaction(transaction)
        
        assert exc_info.value.status_code == 400
        assert 'Unable to find stock name' in str(exc_info.value.detail)

    @patch('openbb_app.routes.portfolio.get_db_manager')
    @patch('openbb_app.routes.portfolio.normalize_symbol')
    @patch('openbb_app.routes.portfolio.get_stock_name_by_search')
    def test_create_transaction_with_valid_date_and_name(self, mock_get_stock_name, mock_normalize, mock_get_db):
        """Test creating transaction with valid date and name."""
        # Mock normalize_symbol
        mock_normalize.return_value = ('000001', '000001.SZ', 'SZ')
        
        # Mock database manager
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock existing stock
        mock_stock = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'avg_cost': 15.0,
            'quantity': 100,
            'total_value': 1500.0
        }
        mock_db.get_portfolio_stock.return_value = mock_stock
        
        # Mock transaction data
        mock_transaction = {
            'id': 1,
            'date': '2024-01-01',
            'symbol': '000001.SZ',
            'name': '平安银行',
            'price': 15.0,
            'quantity': 100,
            'transaction_type': '买入',
            'total_value': 1500.0,
            'base_value': 1500.0,
            'transaction_fee': 0.0,
            'created_at': '2024-01-01 00:00:00',
            'updated_at': '2024-01-01 00:00:00'
        }
        mock_db.get_all_transactions.return_value = [mock_transaction]
        
        # Create transaction with valid date and name
        from openbb_app.routes.portfolio import TransactionCreate
        transaction = TransactionCreate(
            date='2024-01-01',
            symbol='000001.SZ',
            name='平安银行',
            price=15.0,
            quantity=100,
            transaction_type='买入'
        )
        
        # Call the function
        result = create_transaction(transaction)
        
        # Verify transaction was created correctly
        assert result is not None
        assert mock_db.add_transaction.called
        call_args = mock_db.add_transaction.call_args[0][0]
        assert call_args['date'] == '2024-01-01'
        assert call_args['name'] == '平安银行'
        assert call_args['symbol'] == '000001.SZ'
        assert call_args['price'] == 15.0
        assert call_args['quantity'] == 100
        assert call_args['transaction_type'] == '买入'
        
        # Verify stock name search was not called (name was provided)
        mock_get_stock_name.assert_not_called()