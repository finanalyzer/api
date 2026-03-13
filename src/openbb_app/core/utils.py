import random
import re
from typing import Optional, Tuple
import string
import time
from openbb_ai.models import LlmMessage  # type: ignore[import-untyped]
import logging
from mysharelib.tools import setup_logger

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
    
    if provider == 'akshare':
        if len(api_key) < 8:
            return False, "AkShare API key must be at least 8 characters"
        if not re.match(r'^[a-zA-Z0-9\-_]+$', api_key):
            return False, "AkShare API key contains invalid characters"
    elif provider == 'tushare':
        if len(api_key) < 10:
            return False, "Tushare API key must be at least 10 characters"
        if not re.match(r'^[a-zA-Z0-9]+$', api_key):
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
    print(f"\nThe {provider_name} API key is required for accessing {provider_name} data.")
    
    if provider == 'akshare':
        print("\n📖 How to obtain AkShare API key:")
        print("   - Visit: https://akshare.akfamily.xyz/")
    elif provider == 'tushare':
        print("\n📖 How to obtain Tushare API key:")
        print("   - Visit: https://tushare.pro/")
        print("   - Register for an account")
        print("   - Navigate to 个人中心 -> 接口TOKEN")
        print("   - Copy your API token")
    
    print(f"\n{'='*60}")
    
    while True:
        api_key = input(f"\nEnter {provider_name} API key (or press Enter to skip): ").strip()
        
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
            if retry != 'y':
                print(f"\n⚠️  Skipping {provider_name} API key configuration.")
                print(f"   {provider_name} service will be unavailable.")
                return None

def configure_api_keys() -> Tuple[Optional[str], Optional[str]]:
    """
    Check and configure API keys for akshare and tushare.
    Prompts user for missing keys and stores them in OpenBB credentials.
    
    Returns:
        Tuple of (akshare_api_key, tushare_api_key) - None if not configured
    """
    from openbb import obb
    from openbb_core.app.service.user_service import UserService
    
    akshare_key = None
    tushare_key = None
    
    print("\n🔍 Checking API key configuration...")
    
    try:
        akshare_key = obb.user.credentials.akshare_api_key.get_secret_value()
    except Exception:
        akshare_key = None
    
    try:
        tushare_key = obb.user.credentials.tushare_api_key.get_secret_value()
    except Exception:
        tushare_key = None
    
    missing_keys = []
    if not akshare_key:
        missing_keys.append('akshare')
    if not tushare_key:
        missing_keys.append('tushare')
    
    if not missing_keys:
        print("✅ All API keys are configured.")
        return akshare_key, tushare_key
    
    print(f"\n⚠️  Missing API keys: {', '.join(missing_keys)}")
    
    for provider in missing_keys:
        api_key = prompt_for_api_key(provider)
        
        if api_key:
            try:
                if provider == 'akshare':
                    u = UserService.read_from_file()
                    u.credentials.akshare_api_key = api_key
                    UserService.write_to_file(u)
                    obb.user.credentials.akshare_api_key = api_key
                    akshare_key = api_key
                    print(f"✅ AkShare API key saved to OpenBB credentials.")
                elif provider == 'tushare':
                    u = UserService.read_from_file()
                    u.credentials.tushare_api_key = api_key
                    UserService.write_to_file(u)
                    obb.user.credentials.tushare_api_key = api_key
                    tushare_key = api_key
                    print(f"✅ Tushare API key saved to OpenBB credentials.")
            except Exception as e:
                logger.error(f"Failed to save {provider} API key: {e}")
                print(f"❌ Failed to save {provider} API key: {e}")
        else:
            if provider == 'akshare':
                logger.warning("AkShare API key not provided. AkShare service will be unavailable.")
                print(f"\n⚠️  AkShare service will be unavailable.")
            elif provider == 'tushare':
                logger.warning("Tushare API key not provided. Tushare service will be unavailable.")
                print(f"\n⚠️  Tushare service will be unavailable.")
    
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

    if 'info' in obb.reference:
        obj = obb.reference["info"]["extensions"]["openbb_provider_extension"]
        print([item for item in obj if "akshare" in item])
        print([item for item in obj if "tushare" in item])

    akshare_api_key, tushare_api_key = configure_api_keys()

    if akshare_api_key:
        os.environ["AKSHARE_API_KEY"] = akshare_api_key
    else:
        logger.warning("AKSHARE_API_KEY not configured. AkShare data source will be unavailable.")

    if tushare_api_key:
        os.environ["TUSHARE_API_KEY"] = tushare_api_key
    else:
        logger.warning("TUSHARE_API_KEY not configured. Tushare data source will be unavailable.")
        