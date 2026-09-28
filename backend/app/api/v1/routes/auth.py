from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.domain import ProfileUpdate
from app.schemas.user import UserCreate, UserOut
from app.services.audit.service import record_audit
from app.services.auth.service import authenticate_user, create_auth_token, get_current_user, require_roles

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        identifier = payload.identifier()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    user = authenticate_user(db, identifier, payload.password)
    if not user:
        record_audit(db, action="LOGIN_FAILED", entity="User", entity_id=identifier, details="Invalid credentials")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    assigned_roles = {role.name for role in user.roles}
    if payload.role.value not in assigned_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected role is not assigned to this account")

    token = create_auth_token(user)
    record_audit(db, action="LOGIN", entity="User", entity_id=str(user.id), user_id=user.id)
    db.commit()
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record_audit(db, action="LOGOUT", entity="User", entity_id=str(current_user.id), user_id=current_user.id)
    db.commit()
    return {"message": "Signed out"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "roles": [role.name for role in current_user.roles],
    }


@router.put("/me")
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.full_name:
        current_user.full_name = payload.full_name
    if payload.password:
        current_user.password_hash = hash_password(payload.password)
    record_audit(db, action="PROFILE_UPDATE", entity="User", entity_id=str(current_user.id), user_id=current_user.id)
    db.commit()
    return {"message": "Profile updated"}


@router.post("/register", response_model=UserOut)
def register_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    existing = db.query(User).filter((User.email == payload.email) | (User.username == (payload.username or payload.email))).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    new_user = User(
        username=payload.username or payload.email.split("@")[0],
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
    )
    role = db.query(Role).filter(Role.name == payload.role.value).first()
    if role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User role is not configured")
    new_user.roles.append(role)
    db.add(new_user)
    db.flush()
    record_audit(db, action="USER_CREATED", entity="User", entity_id=str(new_user.id), user_id=current_user.id)
    db.commit()
    db.refresh(new_user)
    return new_user
