from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EvidenceUploadRequest(BaseModel):
    document_type: Literal["SALE_AGREEMENT", "PAYMENT_RECEIPT", "IDENTITY_DOCUMENT", "OWNERSHIP_PROOF", "SUPPORTING_DOCUMENT"]
    stated_payment_amount: Optional[str] = None
    stated_payment_date: Optional[datetime] = None
    payment_reference: Optional[str] = None
    notes: Optional[str] = None


class EvidenceReviewRequest(BaseModel):
    status: Literal["UPLOADED", "UNDER_REVIEW", "VERIFIED_FOR_REVIEW", "NEEDS_CLARIFICATION", "INCONSISTENT"]
    review_notes: Optional[str] = None


class EvidenceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    transaction_id: int
    document_type: str
    original_filename: str
    file_size: int
    mime_type: str
    status: str
    stated_payment_amount: Optional[str] = None
    stated_payment_date: Optional[datetime] = None
    payment_reference: Optional[str] = None
    notes: Optional[str] = None
    uploaded_by: int
    uploaded_by_name: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EvidenceReviewHistoryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    evidence_id: int
    previous_status: Optional[str]
    new_status: str
    changed_by: Optional[int]
    reason: Optional[str]
    created_at: datetime
