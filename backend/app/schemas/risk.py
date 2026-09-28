from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RiskAnalysisResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    transaction_id: int
    risk_score: int
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    model_version: str
    reasons: list[str]
    analyzed_at: datetime
