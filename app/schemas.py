from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class LocationPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AnalyzeRequest(BaseModel):
    imageUrl: HttpUrl
    userLocation: Optional[LocationPoint] = None
    mapLocation: Optional[LocationPoint] = None


class ExifMetadata(BaseModel):
    datetime_original: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    make: Optional[str] = None
    model: Optional[str] = None
    software: Optional[str] = None


class ExifAnalysis(BaseModel):
    metadata_found: bool
    is_old_image: Optional[bool] = None
    age_hours: Optional[float] = None
    threshold_hours: Optional[int] = None
    reason: str
    metadata: ExifMetadata


class GeoConsistency(BaseModel):
    checked: bool
    score: float
    status: Literal["consistent", "partial", "inconsistent", "not_available"]
    reason: str
    distance_user_to_map_km: Optional[float] = None
    distance_photo_to_map_km: Optional[float] = None
    distance_photo_to_user_km: Optional[float] = None


class VeracitySignals(BaseModel):
    visual_score: float
    temporal_score: float
    geo_score: float


class PredictionResponse(BaseModel):
    flood_detected: bool
    confidence: float
    veracity_score: float
    final_score: float
    decision: Literal["approve", "manual_review", "reject"]
    reason: str
    exif_analysis: ExifAnalysis
    geo_consistency: GeoConsistency
    veracity_signals: VeracitySignals
