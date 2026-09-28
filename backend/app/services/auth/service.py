from datetime import timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token, verify_password
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


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


def create_auth_token(user: User) -> str:
    expires_delta = timedelta(minutes=60)
    role = next(iter({role.name for role in user.roles}), None)
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
