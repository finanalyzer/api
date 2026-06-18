import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from openbb_app.core.utils import (
    save_api_key_to_credentials,
    get_api_key_with_priority,
    _store_api_key_in_credentials,
)


def create_mock_credentials(akshare_key=None, tushare_key=None):
    """Create a mock credentials object with optional API keys."""
    mock_credentials = MagicMock()
    if akshare_key:
        mock_credentials.akshare_api_key.get_secret_value.return_value = akshare_key
    if tushare_key:
        mock_credentials.tushare_api_key.get_secret_value.return_value = tushare_key
    return mock_credentials


class TestSaveApiKeyToCredentials:
    """Tests for save_api_key_to_credentials function."""

    def test_save_akshare_api_key_success(self):
        """Test saving AkShare API key successfully."""
        mock_user_service = MagicMock()
        mock_user = MagicMock()
        mock_user_service.read_from_file.return_value = mock_user
        mock_obb = MagicMock()

        with patch(
            "openbb_core.app.service.user_service.UserService", mock_user_service
        ):
            with patch("openbb.obb", mock_obb):
                with patch("builtins.print") as mock_print:
                    result = save_api_key_to_credentials(
                        "akshare", "test_akshare_key"
                    )

                    assert result == "test_akshare_key"
                    mock_user_service.read_from_file.assert_called_once()
                    assert (
                        mock_user.credentials.akshare_api_key
                        == "test_akshare_key"
                    )
                    assert (
                        mock_obb.user.credentials.akshare_api_key
                        == "test_akshare_key"
                    )
                    mock_user_service.write_to_file.assert_called_once_with(mock_user)
                    mock_print.assert_called_once_with(
                        "✅ Akshare API key saved to OpenBB credentials."
                    )

    def test_save_tushare_api_key_success(self):
        """Test saving Tushare API key successfully."""
        mock_user_service = MagicMock()
        mock_user = MagicMock()
        mock_user_service.read_from_file.return_value = mock_user
        mock_obb = MagicMock()

        with patch(
            "openbb_core.app.service.user_service.UserService", mock_user_service
        ):
            with patch("openbb.obb", mock_obb):
                with patch("builtins.print") as mock_print:
                    result = save_api_key_to_credentials(
                        "tushare", "test_tushare_key"
                    )

                    assert result == "test_tushare_key"
                    mock_user_service.read_from_file.assert_called_once()
                    assert (
                        mock_user.credentials.tushare_api_key
                        == "test_tushare_key"
                    )
                    assert (
                        mock_obb.user.credentials.tushare_api_key
                        == "test_tushare_key"
                    )
                    mock_user_service.write_to_file.assert_called_once_with(mock_user)
                    mock_print.assert_called_once_with(
                        "✅ Tushare API key saved to OpenBB credentials."
                    )

    def test_save_api_key_failure(self):
        """Test when saving API key fails due to exception."""
        mock_user_service = MagicMock()
        mock_user_service.read_from_file.side_effect = Exception("Read error")

        with patch(
            "openbb_core.app.service.user_service.UserService", mock_user_service
        ):
            with patch("openbb_app.core.utils.logger") as mock_logger:
                with patch("builtins.print") as mock_print:
                    result = save_api_key_to_credentials("akshare", "test_key")

                    assert result is None
                    mock_logger.error.assert_called_once_with(
                        "Failed to save akshare API key: Read error"
                    )
                    mock_print.assert_called_once_with(
                        "❌ Failed to save akshare API key: Read error"
                    )

    def test_save_api_key_with_unknown_provider(self):
        """Test saving API key with unknown provider."""
        mock_user_service = MagicMock()
        mock_user = MagicMock()
        mock_user_service.read_from_file.return_value = mock_user
        mock_obb = MagicMock()

        with patch(
            "openbb_core.app.service.user_service.UserService", mock_user_service
        ):
            with patch("openbb.obb", mock_obb):
                with patch("builtins.print") as mock_print:
                    result = save_api_key_to_credentials("unknown", "test_key")

                    assert result == "test_key"
                    mock_user_service.read_from_file.assert_called_once()
                    mock_user_service.write_to_file.assert_called_once_with(mock_user)
                    mock_print.assert_called_once_with(
                        "✅ Unknown API key saved to OpenBB credentials."
                    )


class TestGetApiKeyWithPriority:
    """Tests for get_api_key_with_priority function."""

    def test_env_var_valid_stores_in_credentials(self):
        """Test: Environment variable present and valid."""
        mock_credentials = create_mock_credentials()

        with patch.dict(
            "os.environ", {"AKSHARE_API_KEY": "valid_akshare_key_123"}
        ):
            with patch(
                "openbb_app.core.utils._store_api_key_in_credentials"
            ) as mock_store:
                mock_store.return_value = True
                with patch("openbb_app.core.utils.logger") as mock_logger:
                    api_key, source = get_api_key_with_priority(
                        "akshare", mock_credentials
                    )

                    assert api_key == "valid_akshare_key_123"
                    assert source == "env"
                    # Verify storage was called
                    mock_store.assert_called_once_with(
                        "akshare", "valid_akshare_key_123"
                    )
                    mock_logger.info.assert_called()

    def test_env_var_invalid_falls_back_to_credentials(self):
        """Test: Environment variable invalid, credentials has valid key."""
        mock_credentials = create_mock_credentials(
            akshare_key="cred_akshare_key_456"
        )

        with patch.dict("os.environ", {"AKSHARE_API_KEY": "short"}):
            with patch("openbb_app.core.utils.logger") as mock_logger:
                api_key, source = get_api_key_with_priority(
                    "akshare", mock_credentials
                )

                assert api_key == "cred_akshare_key_456"
                assert source == "credentials"
                mock_logger.warning.assert_called()

    def test_env_var_missing_falls_back_to_credentials(self):
        """Test: Environment variable missing, credentials has valid key."""
        mock_credentials = create_mock_credentials(
            akshare_key="cred_akshare_key_789"
        )

        with patch.dict("os.environ", {}, clear=True):
            with patch("openbb_app.core.utils.logger") as mock_logger:
                api_key, source = get_api_key_with_priority(
                    "akshare", mock_credentials
                )

                assert api_key == "cred_akshare_key_789"
                assert source == "credentials"

    def test_both_missing_returns_not_found(self):
        """Test: Both environment variable and credentials missing."""
        mock_credentials = create_mock_credentials()

        with patch.dict("os.environ", {}, clear=True):
            with patch("openbb_app.core.utils.logger") as mock_logger:
                api_key, source = get_api_key_with_priority(
                    "akshare", mock_credentials
                )

                assert api_key is None
                assert source == "not_found"
                mock_logger.error.assert_called_once()
                error_msg = mock_logger.error.call_args[0][0]
                assert "not found" in error_msg.lower()

    def test_env_var_empty_falls_back_to_credentials(self):
        """Test: Environment variable empty, credentials has valid key."""
        mock_credentials = create_mock_credentials(
            akshare_key="cred_akshare_key_abc"
        )

        with patch.dict("os.environ", {"AKSHARE_API_KEY": "   "}):
            with patch("openbb_app.core.utils.logger"):
                api_key, source = get_api_key_with_priority(
                    "akshare", mock_credentials
                )

                assert api_key == "cred_akshare_key_abc"
                assert source == "credentials"

    def test_partial_key_presence_env_only(self):
        """Test: Only AkShare in env, Tushare in credentials."""
        # Test AkShare from env
        mock_credentials_akshare = create_mock_credentials()

        with patch.dict("os.environ", {"AKSHARE_API_KEY": "akshare_env_key_123"}):
            with patch(
                "openbb_app.core.utils._store_api_key_in_credentials"
            ) as mock_store:
                mock_store.return_value = True
                with patch("openbb_app.core.utils.logger"):
                    akshare_key, akshare_source = get_api_key_with_priority(
                        "akshare", mock_credentials_akshare
                    )
                    assert akshare_key == "akshare_env_key_123"
                    assert akshare_source == "env"

        # Test Tushare from credentials (separate test context)
        # Tushare key must be alphanumeric only (no underscores)
        mock_credentials_tushare = create_mock_credentials(
            tushare_key="tusharecredkeyxyz123"
        )

        with patch.dict("os.environ", {}, clear=True):
            with patch("openbb_app.core.utils.logger"):
                tushare_key, tushare_source = get_api_key_with_priority(
                    "tushare", mock_credentials_tushare
                )
                assert tushare_key == "tusharecredkeyxyz123"
                assert tushare_source == "credentials"

    def test_credentials_key_invalid_env_missing(self):
        """Test: Credentials key invalid, env missing - returns not found."""
        mock_credentials = create_mock_credentials(akshare_key="123")  # Too short

        with patch.dict("os.environ", {}, clear=True):
            with patch("openbb_app.core.utils.logger") as mock_logger:
                api_key, source = get_api_key_with_priority(
                    "akshare", mock_credentials
                )

                assert api_key is None
                assert source == "not_found"

    def test_tushare_env_valid(self):
        """Test: Tushare API key from environment variable."""
        mock_credentials = create_mock_credentials()
        # Tushare key must be alphanumeric only (no underscores)
        test_key = "tushareapikeyvalid12345"

        def mock_store_keys(*args, **kwargs):
            return True

        with patch.dict("os.environ", {"TUSHARE_API_KEY": test_key}):
            with patch(
                "openbb_app.core.utils._store_api_key_in_credentials",
                side_effect=mock_store_keys
            ):
                with patch("openbb_app.core.utils.logger"):
                    api_key, source = get_api_key_with_priority(
                        "tushare", mock_credentials
                    )

                    assert api_key == test_key, f"Expected {test_key}, got {api_key}"
                    assert source == "env", f"Expected 'env', got {source}"


class TestStoreApiKeyInCredentials:
    """Tests for _store_api_key_in_credentials function."""

    def test_store_success(self):
        """Test successful storage of API key."""
        mock_user_service = MagicMock()
        mock_user = MagicMock()
        mock_user_service.read_from_file.return_value = mock_user
        mock_obb = MagicMock()

        with patch(
            "openbb_core.app.service.user_service.UserService", mock_user_service
        ):
            with patch("openbb.obb", mock_obb):
                result = _store_api_key_in_credentials("akshare", "test_key")

                assert result is True
                mock_user_service.read_from_file.assert_called_once()
                mock_user_service.write_to_file.assert_called_once_with(mock_user)
                assert mock_obb.user.credentials.akshare_api_key == "test_key"

    def test_store_failure(self):
        """Test failure during storage."""
        mock_user_service = MagicMock()
        mock_user_service.read_from_file.side_effect = Exception("Storage error")

        with patch(
            "openbb_core.app.service.user_service.UserService", mock_user_service
        ):
            with patch("openbb_app.core.utils.logger") as mock_logger:
                result = _store_api_key_in_credentials("akshare", "test_key")

                assert result is False
                mock_logger.error.assert_called()
