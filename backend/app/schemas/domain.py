from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ParcelCreate(BaseModel):
    parcel_code: str
    location: str
    province: str
    district: str
    sector: str
    cell: str
    village: str
    area_ha: float = Field(gt=0)
    status: str = "ACTIVE"
    registration_reference: Optional[str] = None


class ParcelUpdate(BaseModel):
    location: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    sector: Optional[str] = None
    cell: Optional[str] = None
    village: Optional[str] = None
    area_ha: Optional[float] = Field(default=None, gt=0)
    status: Optional[str] = None
    registration_reference: Optional[str] = None


class ParcelOut(ParcelCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    current_owner_name: Optional[str] = None
    current_owner_id: Optional[int] = None


class OwnerCreate(BaseModel):
    owner_code: str
    full_name: str
    identification_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: str = "ACTIVE"


class OwnerUpdate(BaseModel):
    full_name: Optional[str] = None
    identification_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None


class OwnerOut(OwnerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    parcels_owned: int = 0


class OwnershipHistoryCreate(BaseModel):
    previous_owner_id: Optional[int] = None
    new_owner_id: int
    transfer_date: datetime
    reason_type: str = "TRANSFER"
    supporting_reference: Optional[str] = None


class OwnershipHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parcel_id: int
    previous_owner_id: Optional[int] = None
    previous_owner_name: Optional[str] = None
    new_owner_id: Optional[int] = None
    new_owner_name: Optional[str] = None
    transfer_date: datetime
    reason_type: str
    supporting_reference: Optional[str] = None
    created_at: datetime


class TransactionCreate(BaseModel):
    parcel_id: int
    seller_owner_id: Optional[int] = None
    buyer_owner_id: Optional[int] = None
    transaction_type: str
    transaction_date: datetime
    declared_value: Optional[Decimal] = None
    status: str = "PENDING"


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    transaction_code: str
    parcel_id: int
    parcel_code: Optional[str] = None
    seller_owner_id: Optional[int] = None
    seller_name: Optional[str] = None
    buyer_owner_id: Optional[int] = None
    buyer_name: Optional[str] = None
    transaction_type: str
    transaction_date: datetime
    declared_value: Optional[Decimal] = None
    status: str
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    latest_risk_level: Optional[str] = None
    latest_risk_score: Optional[int] = None


class CaseUpdate(BaseModel):
    status: Optional[Literal["OPEN", "UNDER_REVIEW", "NEEDS_INFORMATION", "RESOLVED", "CLOSED"]] = None
    review_notes: Optional[str] = None
    assigned_to: Optional[int] = None


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_code: str
    transaction_id: int
    transaction_code: Optional[str] = None
    parcel_id: int
    parcel_code: Optional[str] = None
    assigned_to: Optional[int] = None
    assigned_name: Optional[str] = None
    status: str
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    risk_level: Optional[str] = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    audit_metadata: Optional[dict] = None
    details: Optional[str] = None
    created_at: datetime


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
