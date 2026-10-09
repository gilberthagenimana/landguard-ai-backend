from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token, verify_password
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


def authenticate_user(db: Session, identifier: str, password: str) -> Optional[User]:
    user = (
        db.query(User)
        .filter(or_(User.email == identifier, User.username == identifier))
        .first()
    )
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def is_account_locked(user: User) -> bool:
    """Check if user account is temporarily locked due to failed attempts."""
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        if user.last_failed_login:
            lockout_end = user.last_failed_login + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            if datetime.utcnow() < lockout_end:
                return True
    return False


def record_failed_login(db: Session, user: User) -> None:
    """Record a failed login attempt."""
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    user.last_failed_login = datetime.utcnow()



def reset_failed_logins(db: Session, user: User) -> None:
    """Reset failed login counter on successful login."""
    user.failed_login_attempts = 0
    user.last_failed_login = None


def create_auth_token(user: User, role: str | None = None) -> str:
    expires_delta = timedelta(minutes=60)
    if role is None:
        # Preserve compatibility for internal callers and existing tests.
        role = sorted(user_role.name for user_role in user.roles)[0] if user.roles else None
    elif role not in {user_role.name for user_role in user.roles}:
        raise ValueError("Selected role is not assigned to this account")
    return create_access_token(subject=str(user.id), expires_delta=expires_delta, claims={"role": role})


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is disabled")
    return user


def require_roles(*allowed_roles: str):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = {role.name for role in current_user.roles}
        if not set(allowed_roles).intersection(user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return role_checker
