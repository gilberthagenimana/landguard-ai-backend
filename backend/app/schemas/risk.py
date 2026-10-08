from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FeatureImportance(BaseModel):
    feature: str
    description: str
    impact: Literal["LOW", "MEDIUM", "HIGH"]


class RiskAnalysisResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    transaction_id: int
    risk_score: int
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    model_version: str
    reasons: list[str]
    analyzed_at: datetime
    confidence: int | None = None
    feature_importance: list[FeatureImportance] | None = None
