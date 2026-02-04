"""
Security utilities: JWT skeleton, input sanitization, safe DB patterns.
Production: integrate with real identity provider and parameterized queries.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import get_settings

# Password hashing for future auth (e.g. admin users)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """
    JWT access token skeleton. Use 'sub' for user id; add scopes/roles as needed.
    Token is signed; verify with verify_token in dependencies.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES))
    payload = {"sub": str(subject), "exp": expire, "iat": now}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify JWT and return payload or None. Use in FastAPI dependency."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def hash_password(plain: str) -> str:
    """Hash password for storage. Use with verify_password on login."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plain password against stored hash."""
    return pwd_context.verify(plain, hashed)


# Patterns for input sanitization (reduce XSS / injection surface)
_UNSAFE_PATTERN = re.compile(r"[<>\"';&]|(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC)\b)", re.I)


def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    Sanitize user input: strip, limit length, remove obviously dangerous chars.
    Not a replacement for parameterized queries; use both.
    """
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()[:max_length]
    return _UNSAFE_PATTERN.sub("", cleaned)


def is_safe_for_log(value: str, max_length: int = 200) -> str:
    """Redact or truncate sensitive data before logging."""
    if not value or len(value) > max_length:
        return "(redacted)" if value else ""
    return value[:max_length]
