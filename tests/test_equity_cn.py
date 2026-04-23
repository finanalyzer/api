import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime
from fastapi import HTTPException
from openbb_app.routes.equity_cn import get_historical_data


class TestGetHistoricalData:
    """Tests for get_historical_data endpoint."""

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_valid_interval_1d(self, mock_normalize, mock_get_db_manager):
        """Test with valid interval 1d."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = ([], "test_source")
            result = get_historical_data(symbol="000001", start_date=None, end_date=None, interval="1d")
            assert result == []

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_valid_interval_1w(self, mock_normalize, mock_get_db_manager):
        """Test with valid interval 1w."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = ([], "test_source")
            result = get_historical_data(symbol="000001", start_date=None, end_date=None, interval="1w")
            assert result == []

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_valid_interval_1m(self, mock_normalize, mock_get_db_manager):
        """Test with valid interval 1m."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = ([], "test_source")
            result = get_historical_data(symbol="000001", start_date=None, end_date=None, interval="1m")
            assert result == []

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_invalid_interval(self, mock_normalize, mock_get_db_manager):
        """Test with invalid interval."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager

        with pytest.raises(HTTPException) as exc_info:
            get_historical_data(symbol="000001", start_date=None, end_date=None, interval="invalid")

        assert exc_info.value.status_code == 400
        assert "Invalid interval" in exc_info.value.detail

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_default_dates(self, mock_normalize, mock_get_db_manager):
        """Test with default dates (start_date and end_date not provided)."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = ([], "test_source")
            result = get_historical_data(symbol="000001", start_date=None, end_date=None, interval="1d")
            
            mock_db_manager.get_price_data.assert_called_once()
            call_args = mock_db_manager.get_price_data.call_args
            assert call_args[0][0] == "000001.SZ"
            assert call_args[0][3] == "1d"

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_custom_dates(self, mock_normalize, mock_get_db_manager):
        """Test with custom start_date and end_date."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = ([], "test_source")
            result = get_historical_data(
                symbol="000001", start_date="2024-01-01", end_date="2024-12-31", interval="1d"
            )

            mock_db_manager.get_price_data.assert_called_once()
            call_args = mock_db_manager.get_price_data.call_args
            assert call_args[0][1] == "2024-01-01"
            assert call_args[0][2] == "2024-12-31"

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_invalid_date_format(self, mock_normalize, mock_get_db_manager):
        """Test with invalid date format."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        mock_db_manager = MagicMock()
        mock_get_db_manager.return_value = mock_db_manager

        with pytest.raises(HTTPException) as exc_info:
            get_historical_data(
                symbol="000001", start_date="2024/01/01", end_date="2024-12-31", interval="1d"
            )

        assert exc_info.value.status_code == 400
        assert "Invalid date format" in exc_info.value.detail

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_cache_hit(self, mock_normalize, mock_get_db_manager):
        """Test when data is found in cache."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        
        cached_data = [
            {
                "date": "2024-01-01",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 1000000,
                "amount": 10500000.0,
            }
        ]
        
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = cached_data
        mock_get_db_manager.return_value = mock_db_manager

        result = get_historical_data(symbol="000001", start_date="2024-01-01", end_date="2024-01-01", interval="1d")

        assert len(result) == 1
        assert result[0]["date"] == "2024-01-01"
        assert result[0]["open"] == 10.0
        assert result[0]["close"] == 10.5

        mock_db_manager.get_price_data.assert_called_once()
        mock_db_manager.upsert_price_data.assert_not_called()

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_cache_miss_successful_fetch(self, mock_normalize, mock_get_db_manager):
        """Test when cache miss and data source fetch is successful."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        
        fetched_data = [
            {
                "date": "2024-01-01",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 1000000,
                "amount": 10500000.0,
            }
        ]
        
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = (fetched_data, "akshare")
            result = get_historical_data(symbol="000001", start_date="2024-01-01", end_date="2024-01-01", interval="1d")

            assert len(result) == 1
            assert result[0]["date"] == "2024-01-01"
            assert result[0]["open"] == 10.0

            mock_db_manager.get_price_data.assert_called_once()
            mock_db_manager.upsert_price_data.assert_called_once_with("000001.SZ", fetched_data, "akshare")
            mock_get_data.assert_called_once_with("000001.SZ", "2024-01-01", "2024-01-01", "1d")

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_cache_miss_fetch_failure(self, mock_normalize, mock_get_db_manager):
        """Test when cache miss and data source fetch fails."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.side_effect = Exception("Data source error")
            
            with pytest.raises(HTTPException) as exc_info:
                get_historical_data(symbol="000001", start_date="2024-01-01", end_date="2024-01-01", interval="1d")

            assert exc_info.value.status_code == 500
            assert "Failed to fetch data from all sources" in exc_info.value.detail

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_symbol_normalization(self, mock_normalize, mock_get_db_manager):
        """Test that symbol is normalized correctly."""
        mock_normalize.return_value = ("600000", "600000.SH", "SH")
        
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = ([], "test_source")
            result = get_historical_data(symbol="600000", start_date=None, end_date=None, interval="1d")

            mock_normalize.assert_called_once_with("600000")
            mock_db_manager.get_price_data.assert_called_once_with("600000.SH", ANY, ANY, "1d")
            mock_get_data.assert_called_once_with("600000.SH", ANY, ANY, "1d")

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_empty_data_from_source(self, mock_normalize, mock_get_db_manager):
        """Test when data source returns empty data."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = []
        mock_db_manager.upsert_price_data.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        with patch("openbb_app.routes.equity_cn.data_source_manager.get_data") as mock_get_data:
            mock_get_data.return_value = ([], "akshare")
            result = get_historical_data(symbol="000001", start_date=None, end_date=None, interval="1d")

            assert result == []
            mock_db_manager.upsert_price_data.assert_not_called()

    @patch("openbb_app.routes.equity_cn.get_db_manager")
    @patch("mysharelib.tools.normalize_symbol")
    def test_multiple_data_points(self, mock_normalize, mock_get_db_manager):
        """Test with multiple data points."""
        mock_normalize.return_value = ("000001", "000001.SZ", "SZ")
        
        cached_data = [
            {
                "date": "2024-01-01",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 1000000,
                "amount": 10500000.0,
            },
            {
                "date": "2024-01-02",
                "open": 10.5,
                "high": 11.5,
                "low": 10.0,
                "close": 11.0,
                "volume": 1100000,
                "amount": 11500000.0,
            },
        ]
        
        mock_db_manager = MagicMock()
        mock_db_manager.get_price_data.return_value = cached_data
        mock_get_db_manager.return_value = mock_db_manager

        result = get_historical_data(symbol="000001", start_date="2024-01-01", end_date="2024-01-02", interval="1d")

        assert len(result) == 2
        assert result[0]["date"] == "2024-01-01"
        assert result[1]["date"] == "2024-01-02"
        assert result[0]["close"] == 10.5
        assert result[1]["close"] == 11.0
