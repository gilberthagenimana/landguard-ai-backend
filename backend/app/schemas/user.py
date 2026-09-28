from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import UserRole


class UserBase(BaseModel):
    full_name: str
    email: str = Field(..., min_length=3, max_length=255)
    username: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    role: UserRole


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    created_at: datetime
    updated_at: datetime
    roles: list[RoleOut] = []
