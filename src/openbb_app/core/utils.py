import logging
import random
import re
import string
import time
from typing import List, Optional, Tuple

import pandas as pd
from mysharelib.tools import setup_logger
from openbb import obb
from openbb_ai.models import LlmMessage  # type: ignore[import-untyped]

from .config import config

setup_logger(__name__)
logger = logging.getLogger(__name__)


def validate_api_key(token: str, api_key: str) -> bool:
    """Validate API key in header against pre-defined list of keys."""
    if not token:
        return False
    if token.replace("Bearer ", "").strip() == api_key:
        return True
    return False


async def sanitize_message(message: str) -> str:
    """Sanitize a message by escaping forbidden characters."""
    cleaned_message = re.sub(r"(?<!\{)\{(?!{)", "{{", message)
    cleaned_message = re.sub(r"(?<!\})\}(?!})", "}}", cleaned_message)
    return cleaned_message


async def is_last_message(message: LlmMessage, messages: list[LlmMessage]) -> bool:
    """Check if the message is the last human message in the conversation."""
    human_messages = [msg for msg in messages if msg.role == "human"]
    return message == human_messages[-1] if human_messages else False


async def generate_id(length: int = 2) -> str:
    """Generate a unique ID with a total length of 4 characters."""
    timestamp = int(time.time() * 1000) % 1000

    base36_chars = string.digits + string.ascii_lowercase

    def to_base36(num):
        result = ""
        while num > 0:
            result = base36_chars[num % 36] + result
            num //= 36
        return result.zfill(2)

    random_suffix = "".join(random.choices(base36_chars, k=length))
    return to_base36(timestamp) + random_suffix


def validate_api_key(api_key: str, provider: str) -> Tuple[bool, str]:
    """
    Validate the format of an API key.

    Args:
        api_key: The API key string to validate
        provider: The provider name ('akshare' or 'tushare')

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key or not api_key.strip():
        return False, "API key cannot be empty"

    api_key = api_key.strip()

    if provider == "akshare":
        if len(api_key) < 8:
            return False, "AkShare API key must be at least 8 characters"
        if not re.match(r"^[a-zA-Z0-9\-_]+$", api_key):
            return False, "AkShare API key contains invalid characters"
    elif provider == "tushare":
        if len(api_key) < 10:
            return False, "Tushare API key must be at least 10 characters"
        if not re.match(r"^[a-zA-Z0-9]+$", api_key):
            return False, "Tushare API key contains invalid characters"
    else:
        return False, f"Unknown provider: {provider}"

    return True, ""


def prompt_for_api_key(provider: str) -> Optional[str]:
    """
    Prompt the user to input an API key interactively.

    Args:
        provider: The provider name ('akshare' or 'tushare')

    Returns:
        The API key string if provided, None if user chose to skip
    """
    provider_name = provider.capitalize()

    print(f"\n{'='*60}")
    print(f"⚠️  {provider_name} API Key Not Found")
    print(f"{'='*60}")
    print(
        f"\nThe {provider_name} API key is required for accessing {provider_name} data."
    )

    if provider == "akshare":
        print("\n📖 How to obtain AkShare API key:")
        print("   - Visit: https://akshare.akfamily.xyz/")
    elif provider == "tushare":
        print("\n📖 How to obtain Tushare API key:")
        print("   - Visit: https://tushare.pro/")
        print("   - Register for an account")
        print("   - Navigate to 个人中心 -> 接口TOKEN")
        print("   - Copy your API token")

    print(f"\n{'='*60}")

    while True:
        api_key = input(
            f"\nEnter {provider_name} API key (or press Enter to skip): "
        ).strip()

        if not api_key:
            print(f"\n⚠️  Skipping {provider_name} API key configuration.")
            print(f"   {provider_name} service will be unavailable.")
            return None

        is_valid, error_msg = validate_api_key(api_key, provider)
        if is_valid:
            print(f"\n✅ {provider_name} API key validated successfully.")
            return api_key
        else:
            print(f"\n❌ Invalid API key: {error_msg}")
            retry = input("Would you like to try again? (y/n): ").strip().lower()
            if retry != "y":
                print(f"\n⚠️  Skipping {provider_name} API key configuration.")
                print(f"   {provider_name} service will be unavailable.")
                return None


def save_api_key_to_credentials(provider: str, api_key: str) -> Optional[str]:
    """
    Save API key to OpenBB credentials.

    Args:
        provider: The provider name ('akshare' or 'tushare')
        api_key: The API key to save

    Returns:
        The API key if saved successfully, None otherwise
    """
    from openbb import obb
    from openbb_core.app.service.user_service import UserService

    try:
        u = UserService.read_from_file()
        if provider == "akshare":
            u.credentials.akshare_api_key = api_key
            obb.user.credentials.akshare_api_key = api_key
        elif provider == "tushare":
            u.credentials.tushare_api_key = api_key
            obb.user.credentials.tushare_api_key = api_key
        UserService.write_to_file(u)
        print(f"✅ {provider.capitalize()} API key saved to OpenBB credentials.")
        return api_key
    except Exception as e:
        logger.error(f"Failed to save {provider} API key: {e}")
        print(f"❌ Failed to save {provider} API key: {e}")
        return None


def _get_credential_attr_name(provider: str) -> str:
    """Get the attribute name for a provider's API key in credentials."""
    return f"{provider}_api_key"


def _get_env_var_name(provider: str) -> str:
    """Get the environment variable name for a provider's API key."""
    return f"{provider.upper()}_API_KEY"


def get_api_key_with_priority(
    provider: str, obb_user_credentials
) -> Tuple[Optional[str], str]:
    """
    Retrieve API key using priority-based mechanism.

    Priority order:
    1. Environment variables (if valid, store in obb.user.credentials)
    2. obb.user.credentials storage
    3. None (if not found in either location)

    Args:
        provider: The provider name ('akshare' or 'tushare')
        obb_user_credentials: Mock or real obb.user.credentials object

    Returns:
        Tuple of (api_key, source) where source is one of:
        - 'env': Key was retrieved from environment variable
        - 'credentials': Key was retrieved from obb.user.credentials
        - 'not_found': Key was not found in either location
    """
    import os

    env_var_name = _get_env_var_name(provider)
    cred_attr_name = _get_credential_attr_name(provider)

    logger.debug(f"Retrieving API key for '{provider}' using priority-based mechanism.")

    # Step 1: Try environment variables first
    env_key = None
    try:
        env_key = os.environ.get(env_var_name, "").strip()
        if env_key:
            is_valid, error_msg = validate_api_key(env_key, provider)
            if is_valid:
                logger.info(
                    f"Valid {provider.capitalize()} API key found in environment variable '{env_var_name}'."
                )
                # Store in obb.user.credentials for persistence
                _store_api_key_in_credentials(provider, env_key)
                return env_key, "env"
            else:
                logger.warning(
                    f"Invalid {provider.capitalize()} API key in environment variable '{env_var_name}': {error_msg}"
                )
        else:
            logger.debug(
                f"Environment variable '{env_var_name}' is not set or empty."
            )
    except Exception as e:
        logger.error(f"Error reading {env_var_name} from environment: {e}")

    # Step 2: Try obb.user.credentials storage
    try:
        cred_key = getattr(obb_user_credentials, cred_attr_name, None)
        if cred_key:
            key_value = cred_key.get_secret_value()
            if key_value and key_value.strip():
                is_valid, error_msg = validate_api_key(key_value, provider)
                if is_valid:
                    logger.info(
                        f"Valid {provider.capitalize()} API key found in obb.user.credentials."
                    )
                    return key_value, "credentials"
                else:
                    logger.warning(
                        f"Invalid {provider.capitalize()} API key in obb.user.credentials: {error_msg}"
                    )
    except Exception as e:
        logger.debug(f"Error reading {cred_attr_name} from obb.user.credentials: {e}")

    # Step 3: Key not found - generate detailed error log
    logger.error(
        f"{provider.capitalize()} API key not found. "
        f"Checked locations: (1) Environment variable '{env_var_name}', "
        f"(2) obb.user.credentials['{cred_attr_name}']"
    )

    return None, "not_found"


def _store_api_key_in_credentials(provider: str, api_key: str) -> bool:
    """
    Atomically store API key in obb.user.credentials.

    Args:
        provider: The provider name ('akshare' or 'tushare')
        api_key: The API key to store

    Returns:
        True if stored successfully, False otherwise
    """
    from openbb import obb
    from openbb_core.app.service.user_service import UserService

    cred_attr_name = _get_credential_attr_name(provider)

    try:
        # Read current state
        u = UserService.read_from_file()

        # Update credentials
        setattr(u.credentials, cred_attr_name, api_key)

        # Atomic write: write to file first, then update in-memory
        UserService.write_to_file(u)
        setattr(obb.user.credentials, cred_attr_name, api_key)

        logger.info(f"API key stored in obb.user.credentials['{cred_attr_name}'].")
        return True
    except Exception as e:
        logger.error(f"Failed to store API key in credentials: {e}")
        return False


def configure_api_keys() -> Tuple[Optional[str], Optional[str]]:
    """
    Check and configure API keys for akshare and tushare.

    Priority-based retrieval mechanism:
    1. Environment variables (if valid, automatically store in obb.user.credentials)
    2. obb.user.credentials storage
    3. Prompt user for missing keys and store them in OpenBB credentials

    Each retrieval step includes:
    - Validation checks for API key format
    - Detailed logging at each stage
    - Proper error handling

    Returns:
        Tuple of (akshare_api_key, tushare_api_key) - None if not configured
    """
    from openbb import obb

    print("\n🔍 Checking API key configuration using priority-based mechanism...")

    # Use priority-based retrieval for each provider
    akshare_key, akshare_source = get_api_key_with_priority(
        "akshare", obb.user.credentials
    )
    tushare_key, tushare_source = get_api_key_with_priority(
        "tushare", obb.user.credentials
    )

    # Collect missing keys
    missing_keys = []
    if not akshare_key:
        missing_keys.append("akshare")
    if not tushare_key:
        missing_keys.append("tushare")

    if not missing_keys:
        print("✅ All API keys are configured.")
        return akshare_key, tushare_key

    print(f"\n⚠️  Missing API keys: {', '.join(missing_keys)}")

    for provider in missing_keys:
        api_key = prompt_for_api_key(provider)

        if api_key:
            saved_key = save_api_key_to_credentials(provider, api_key)
            if provider == "akshare":
                akshare_key = saved_key
            elif provider == "tushare":
                tushare_key = saved_key
        else:
            if provider == "akshare":
                logger.warning(
                    "AkShare API key not provided. "
                    "AkShare service will be unavailable."
                )
                print("\n⚠️  AkShare service will be unavailable.")
            elif provider == "tushare":
                logger.warning(
                    "Tushare API key not provided. "
                    "Tushare service will be unavailable."
                )
                print("\n⚠️  Tushare service will be unavailable.")

    print(f"\n{'='*60}")
    print("API Key Configuration Summary:")
    print(f"{'='*60}")
    print(f"AkShare: {'✅ Configured' if akshare_key else '❌ Not configured'}")
    print(f"Tushare: {'✅ Configured' if tushare_key else '❌ Not configured'}")
    print(f"{'='*60}\n")

    return akshare_key, tushare_key


def check_api_keys():
    """
    Check if API keys for akshare and tushare are configured.
    """
    import os

    from openbb import obb

    if "info" in obb.reference:
        obj = obb.reference["info"]["extensions"]["openbb_provider_extension"]
        print([item for item in obj if "akshare" in item])
        print([item for item in obj if "tushare" in item])

    akshare_api_key, tushare_api_key = configure_api_keys()

    if akshare_api_key:
        os.environ["AKSHARE_API_KEY"] = akshare_api_key
    else:
        logger.warning(
            "AKSHARE_API_KEY not configured. AkShare data source will be unavailable."
        )

    if tushare_api_key:
        os.environ["TUSHARE_API_KEY"] = tushare_api_key
    else:
        logger.warning(
            "TUSHARE_API_KEY not configured. Tushare data source will be unavailable."
        )


BUY = "买入"
SELL = "卖出"
HOLD = "持有"


def get_strategies(w52low: float, w52high: float, price: float, rate: float) -> str:
    """
    52周价格策略
        - 买入: 当前价格 <= 52周最低价 * (1 + rate)
        - 卖出: 当前价格 >= 52周最高价 * (1 - rate)
        - 持有: 其他情况
    """
    adjusted_low = w52low * (1 + rate)
    adjusted_high = w52high * (1 - rate)
    if price <= adjusted_low:
        return BUY
    elif price >= adjusted_high:
        return SELL
    else:
        return HOLD


def get_tvlink(symbol: str) -> str:
    """
    Generate TradingView link for the stock.

    Args:
        symbol: Stock symbol in format like 000001.SZ, 600000.SH, 00700.HK

    Returns:
        TradingView link as string
    """
    from mysharelib.tools import get_exchange, normalize_symbol

    symbol_b, _, _ = normalize_symbol(symbol)
    return f"https://cn.tradingview.com/chart/?symbol={get_exchange(str(symbol_b))}:{int(symbol_b)}"


def get_quote(symbols: str) -> List[dict]:
    all_data = []
    list = symbols.split(",")
    for symbol in list:
        try:
            data = get_stock_quote(symbol)
            data["symbol"] = symbol
            all_data.append(data)
        except Exception as e:
            print(f"Error fetching data for symbol {symbol}: {e}")
            continue
    return all_data


def get_stock_quote(symbol: str) -> dict:
    """
    Get stock quote data from OpenBB API.

    Args:
        symbol: Stock symbol

    Returns:
        Dictionary with financial metrics
    """
    from openbb import obb

    try:
        logger.info(f"Fetching quote data for {symbol}")

        # Call OpenBB API
        quote = obb.equity.price.quote(symbol=symbol, provider="akshare")

        quote_dict = quote.to_dict()

        def extract_value(val):
            if isinstance(val, list) and len(val) > 0:
                return float(val[0]) if val[0] is not None else 0.0
            return float(val) if val is not None else 0.0

        result = {
            "current_price": extract_value(quote_dict.get("last_price", 0)),
            "fifty_two_week_low": extract_value(quote_dict.get("year_low", 0)),
            "fifty_two_week_high": extract_value(quote_dict.get("year_high", 0)),
            "dividend_yield": extract_value(quote_dict.get("dividend_yield_ttm", 0)),
            "latest_dividend": extract_value(quote_dict.get("dividend_ttm", 0)),
        }

        logger.info(f"Successfully fetched quote data for {symbol}")
        return result
    except Exception as e:
        logger.error(f"Error fetching quote data for {symbol}: {e}")
        # Return fallback values
        return {
            "current_price": 0,
            "fifty_two_week_low": 0,
            "fifty_two_week_high": 0,
            "dividend_yield": 0,
            "latest_dividend": 0,
        }


def get_symbols(exchange: str = "") -> List[dict]:
    """Get available tickers for OpenBB Workspace widget."""
    result_df = obb.equity.search(provider=config.default_provider).to_dataframe()
    if exchange == "HKEX":
        result_df = result_df[result_df["exchange"] == "HKEX"]
    else:
        result_df = result_df[result_df["exchange"] != "HKEX"]
    if not result_df.empty:
        equity_list = [
            {
                "label": (
                    row["name"] if "name" in result_df.columns else "Unknown Company"
                ),
                "value": (
                    row["symbol"] if "symbol" in result_df.columns else "invalid ticker"
                ),
                "extraInfo": {
                    "description": (
                        row["symbol"]
                        if "symbol" in result_df.columns
                        else "invalid ticker"
                    ),
                    "rightOfDescription": (
                        row["exchange"]
                        if "exchange" in result_df.columns
                        else "invalid"
                    ),
                },
            }
            for index, row in result_df.iterrows()
        ]
        return equity_list
    return []


def get_news(symbol: str, limit: int = 10) -> pd.DataFrame:
    """Get latest news for a stock"""
    from mysharelib.tools import normalize_symbol

    symbol_b, _, _ = normalize_symbol(symbol)
    return obb.news.company(symbol_b, provider="akshare").to_dataframe().head(limit)


def get_info(symbol: str) -> pd.DataFrame:
    """
    获取股票基本信息
    """
    from mysharelib.tools import normalize_symbol

    _, symbol_f, _ = normalize_symbol(symbol)

    df_base = (
        obb.equity.fundamental.metrics(symbol=symbol_f, provider="akshare")
        .to_dataframe()
        .T
    )
    return df_base[0]
