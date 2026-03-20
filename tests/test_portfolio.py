import pytest
import tempfile
from pathlib import Path
from openbb_app.core.database import DatabaseManager

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