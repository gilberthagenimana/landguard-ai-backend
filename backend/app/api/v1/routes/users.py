from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.case_review import CaseReview
from app.models.role import Role
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN")),
):
    return db.query(User).all()


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    clean_email = payload.email.strip().lower()
    username = (payload.username or "").strip() or clean_email.split("@")[0]

    existing_email = db.query(User).filter(User.email.ilike(clean_email)).first()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered")

    existing_user = db.query(User).filter(User.username.ilike(username)).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Username '{username}' is already taken")

    role_name = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User role is not configured")

    user = User(
        username=username,
        full_name=payload.full_name.strip(),
        email=clean_email,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
    )
    user.roles.append(role)
    db.add(user)
    db.flush()
    record_audit(db, action="USER_CREATED", entity="User", entity_id=str(user.id), user_id=current_user.id, metadata={"role": role_name})
    db.commit()
    db.refresh(user)

    # Notify administrators about the new user registration.
    from app.services.notification.service import notify_admins

    notify_admins(
        db,
        event_type="USER_REGISTERED",
        title="New User Registered",
        description="A new user account was registered in the system.",
        priority="low",
        auto_commit=False,
    )

    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _current_user: User = Depends(require_roles("ADMIN"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    new_role = data.pop("role", None)
    new_password = data.pop("password", None)

    if "email" in data and data["email"]:
        clean_email = data["email"].strip().lower()
        data["email"] = clean_email
        conflict = db.query(User).filter(User.email.ilike(clean_email), User.id != user.id).first()
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered")

    if "username" in data and data["username"]:
        clean_username = data["username"].strip()
        data["username"] = clean_username
        conflict = db.query(User).filter(User.username.ilike(clean_username), User.id != user.id).first()
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken")

    if new_password:
        user.password_hash = hash_password(new_password)

    for field, value in data.items():
        if value is not None:
            if isinstance(value, str):
                value = value.strip()
            setattr(user, field, value)

    if new_role:
        role_name = new_role.value if hasattr(new_role, "value") else str(new_role)
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role")
        user.roles = [role]

    record_audit(db, action="USER_UPDATED", entity="User", entity_id=str(user.id), user_id=current_user.id)
    db.commit()
    db.refresh(user)
    return user



@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_access(
    user_id: int,
    permanent: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove your own admin access")

    if permanent:
        has_tx = db.query(Transaction).filter(Transaction.created_by == user.id).first()
        has_cases = db.query(CaseReview).filter(CaseReview.assigned_to == user.id).first()
        if has_tx or has_cases:
            user.is_active = False
            record_audit(
                db,
                action="USER_DISABLED",
                entity="User",
                entity_id=str(user.id),
                user_id=current_user.id,
                metadata={"reason": "User no longer with organization; access revoked. Retained in historical audits."},
            )
        else:
            user.roles = []
            record_audit(
                db,
                action="USER_DELETED",
                entity="User",
                entity_id=str(user.id),
                user_id=current_user.id,
                metadata={"reason": "User deleted as they no longer work with the organization."},
            )
            db.delete(user)
    else:
        user.is_active = False
        record_audit(
            db,
            action="USER_DISABLED",
            entity="User",
            entity_id=str(user.id),
            user_id=current_user.id,
            metadata={"reason": "Access revoked by admin."},
        )
    db.commit()


@router.post("/{user_id}/reactivate", response_model=UserOut)
def reactivate_user_access(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = True
    record_audit(db, action="USER_REACTIVATED", entity="User", entity_id=str(user.id), user_id=current_user.id)
    db.commit()
    db.refresh(user)
    return user
