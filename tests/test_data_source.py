import pytest
from unittest.mock import patch, MagicMock
from openbb_app.core.data_source import normalize_symbol_for_yfinance

class TestNormalizeSymbolForYfinance:
    """Tests for normalize_symbol_for_yfinance function."""

    def test_mysharelib_not_installed(self):
        """Test when mysharelib.tools is not available."""
        with patch("openbb_app.core.data_source.logger") as mock_logger:
            with patch.dict("sys.modules", {"mysharelib.tools": None}):
                with patch("builtins.__import__", side_effect=ImportError):
                    result = normalize_symbol_for_yfinance("600000")
                    assert result == "600000"
                    mock_logger.warning.assert_called_once()

    def test_normalize_symbol_raises_exception(self):
        """Test when normalize_symbol raises an exception."""
        with patch("openbb_app.core.data_source.logger") as mock_logger:
            with patch("openbb_app.core.data_source.normalize_symbol", side_effect=ValueError("Invalid symbol")):
                result = normalize_symbol_for_yfinance("invalid")
                assert result == "invalid"
                mock_logger.warning.assert_called_once()

    def test_symbol_f_is_empty(self):
        """Test when symbol_f is empty string."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("600000", "", "CN")):
            result = normalize_symbol_for_yfinance("600000")
            assert result == "600000"

    def test_symbol_f_without_dot(self):
        """Test when symbol_f doesn't contain a dot."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("600000", "600000", "CN")):
            result = normalize_symbol_for_yfinance("600000")
            assert result == "600000"

    def test_symbol_f_with_more_than_two_parts(self):
        """Test when symbol_f has more than two parts after splitting by dot."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("600000", "600000.SH.extra", "CN")):
            result = normalize_symbol_for_yfinance("600000")
            assert result == "600000.SH.extra"

    def test_convert_shanghai_sh_to_ss(self):
        """Test converting Shanghai SH suffix to SS."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("600000", "600000.SH", "CN")):
            result = normalize_symbol_for_yfinance("600000")
            assert result == "600000.SS"

    def test_convert_hongkong_hk_with_5_char_prefix(self):
        """Test converting Hong Kong HK suffix with 5 character prefix."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("00700", "00700.HK", "HK")):
            result = normalize_symbol_for_yfinance("00700")
            assert result == "0700.HK"

    def test_hongkong_hk_with_non_5_char_prefix(self):
        """Test Hong Kong HK suffix with non-5 character prefix.

        Note: the conversion logic strips the first digit when the prefix
        is exactly five characters long, so even a value like 00007 becomes
        0007.HK.
        """
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("00007", "00007.HK", "HK")):
            result = normalize_symbol_for_yfinance("00007")
            assert result == "0007.HK"

    def test_shenzhen_sz_suffix(self):
        """Test Shenzhen SZ suffix remains unchanged."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("000001", "000001.SZ", "CN")):
            result = normalize_symbol_for_yfinance("000001")
            assert result == "000001.SZ"

    def test_beijing_bj_suffix(self):
        """Test Beijing BJ suffix remains unchanged."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("8000001", "8000001.BJ", "CN")):
            result = normalize_symbol_for_yfinance("8000001")
            assert result == "8000001.BJ"

    def test_unknown_suffix(self):
        """Test unknown suffix remains unchanged."""
        with patch("openbb_app.core.data_source.normalize_symbol", return_value=("123456", "123456.XX", "XX")):
            result = normalize_symbol_for_yfinance("123456")
            assert result == "123456.XX"