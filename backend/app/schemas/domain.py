from datetime import datetime
from decimal import Decimal
import math
from typing import Any, Literal, Optional
from app.core.transaction_status import TransactionStatus
from pydantic import BaseModel, ConfigDict, Field


class ParcelCreate(BaseModel):
    upi: str
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
    has_pending_transaction: bool = False
    created_at: datetime
    updated_at: datetime
    current_owner_name: Optional[str] = None
    current_owner_id: Optional[int] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    boundary_geometry: Optional[dict[str, Any]] = None
    location_data_source: Optional[str] = None
    location_verification_status: str = "NOT_SUBMITTED"
    location_verification_metadata: Optional[dict[str, Any]] = None


def _valid_coordinate_pair(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(isinstance(item, (int, float)) and math.isfinite(item) for item in value[:2])
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def _validate_geojson_coordinates(value: Any) -> bool:
    if _valid_coordinate_pair(value):
        return True
    return isinstance(value, list) and bool(value) and all(_validate_geojson_coordinates(item) for item in value)


def validate_geojson(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("type") not in {
        "Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon",
    }:
        raise ValueError("boundary_geometry must be a valid GeoJSON geometry object")
    coordinates = value.get("coordinates")
    if not _validate_geojson_coordinates(coordinates):
        raise ValueError("boundary_geometry contains invalid coordinate values")
    return value


class ParcelLocationSubmissionCreate(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    boundary_geometry: Optional[dict[str, Any]] = None
    source: str = Field(min_length=3, max_length=255)
    metadata: Optional[dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if (self.latitude is None) != (self.longitude is None) or (self.latitude is None and self.boundary_geometry is None):
            raise ValueError("Provide both coordinates or a boundary geometry")
        if self.boundary_geometry is not None:
            self.boundary_geometry = validate_geojson(self.boundary_geometry)


class ParcelLocationSubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parcel_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    boundary_geometry: Optional[dict[str, Any]] = None
    source: str
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias="submission_metadata", serialization_alias="metadata")
    status: str
    submitted_by: int
    submitted_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None


class ParcelLocationReview(BaseModel):
    decision: Literal["VERIFIED", "REJECTED"]
    review_notes: Optional[str] = Field(default=None, max_length=1000)


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


class CaseCreate(BaseModel):
    transaction_id: int
    priority: Optional[str] = "MEDIUM"
    assigned_to: Optional[int] = None
    notes: Optional[str] = None


class CaseUpdate(BaseModel):
    status: Optional[Literal["OPEN", "UNDER_REVIEW", "NEEDS_INFORMATION", "RESOLVED", "CLOSED"]] = None
    review_notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    assigned_to: Optional[int] = None
    priority: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = None
    due_date: Optional[datetime] = None


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
    priority: str = "MEDIUM"
    review_notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    due_date: Optional[datetime] = None
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



class PublicParcelOut(BaseModel):
    """Safe public parcel information; never implies official verification."""

    upi: str
    parcel_code: str
    location: str
    district: str
    status: str
    has_pending_transaction: bool = False
    warning_message: Optional[str] = None

    record_classification: str = "UNVERIFIED_LOCAL_RECORD"
    official_verification: str = "NOT_INDEPENDENTLY_VERIFIED"

    public_notice: str = (
        "LandGuard AI is a decision-support prototype using available "
        "system records. This result is not an official land registry "
        "record or legal confirmation of ownership. Verify with the "
        "authorized land authority before making a transaction."
    )
