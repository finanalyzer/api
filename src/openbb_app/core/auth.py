from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from openbb_app.core.config import config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def validate_api_key(token: str, api_key: str) -> bool:
    """Validate API key in header against pre-defined list of keys."""
    if not token:
        return False
    if token.replace("Bearer ", "").strip() == api_key:
        return True
    return False

async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not validate_api_key(token=token, api_key=config.app_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token
