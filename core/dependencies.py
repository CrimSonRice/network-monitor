"""
FastAPI dependency injection: settings, auth, DB sessions.
Centralizes dependencies for testability and clean routes.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import Settings, get_settings
from core.security import verify_token

SettingsDep = Annotated[Settings, Depends(get_settings)]

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> dict | None:
    """
    Optional JWT auth: returns payload if valid token present, else None.
    Use for routes that behave differently for authenticated users.
    """
    if not credentials:
        return None
    payload = verify_token(credentials.credentials)
    return payload


async def get_current_user_required(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> dict:
    """Required JWT auth: 401 if missing or invalid."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


CurrentUserOptional = Annotated[dict | None, Depends(get_current_user_optional)]
CurrentUserRequired = Annotated[dict, Depends(get_current_user_required)]
