from datetime import datetime
from typing import Literal

from pydantic import BaseModel


RuleStatus = Literal["PASS", "FAIL", "WARNING"]
RuleSeverity = Literal["LOW", "MEDIUM", "HIGH"]


class VerificationResult(BaseModel):
    rule_name: str
    status: RuleStatus
    severity: RuleSeverity
    explanation: str


class VerificationResponse(BaseModel):
    transaction_id: int
    overall_status: Literal["PASS", "REVIEW_REQUIRED"]
    verified_at: datetime
    results: list[VerificationResult]
