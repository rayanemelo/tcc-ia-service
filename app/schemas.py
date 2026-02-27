from typing import Literal

from pydantic import BaseModel, HttpUrl


class AnalyzeRequest(BaseModel):
    imageUrl: HttpUrl


class PredictionResponse(BaseModel):
    flood_detected: bool
    confidence: float
    decision: Literal["approve", "manual_review", "reject"]
    reason: str
