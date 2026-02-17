from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    imageUrl: str


# fixme
class PredictionResponse(BaseModel):
    flood_detected: bool
    confidence: float
