"""JWT authentication and password hashing utilities."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_password_hash(password: str) -> str:
    """Return password hash for *password*."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True when *plain_password* matches *hashed_password*."""
    return pwd_context.verify(plain_password, hashed_password)


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #

def create_access_token(
    subject: str | UUID,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        subject: Usually the user's UUID as a string.
        expires_delta: Override the default expiry window.
        extra_claims: Additional claims to embed (e.g. role, org_id).

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Returns:
        The decoded payload dict.

    Raises:
        HTTPException 401 when the token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub: str | None = payload.get("sub")
        if sub is None:
            raise credentials_exception
        return payload
    except JWTError as exc:
        logger.warning("JWT verification failed", error=str(exc))
        raise credentials_exception from exc


# --------------------------------------------------------------------------- #
# FastAPI dependency
# --------------------------------------------------------------------------- #

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """FastAPI dependency that returns the authenticated User model.

    Raises:
        HTTPException 401 – invalid/expired token.
        HTTPException 403 – inactive account.
    """
    from app.models.user import User  # local import to avoid circular deps
    from sqlalchemy import select

    payload = verify_token(token)
    user_id: str = payload["sub"]

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account",
        )
    return user


async def require_role(*roles: str):
    """Dependency factory that restricts access to specific roles.

    Usage::

        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """

    async def _check(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {roles}",
            )
        return current_user

    return _check
