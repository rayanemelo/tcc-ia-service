"""Schemas Pydantic de entrada e saída usados pela API de análise."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class LocationPoint(BaseModel):
    """Representa um ponto geográfico com latitude e longitude válidas."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AnalyzeRequest(BaseModel):
    """Payload de requisição para análise de uma imagem de alagamento."""

    imageUrl: HttpUrl
    userLocation: Optional[LocationPoint] = None
    mapLocation: Optional[LocationPoint] = None


class ExifMetadata(BaseModel):
    """Metadados EXIF extraídos da imagem utilizada na análise."""

    datetime_original: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    make: Optional[str] = None
    model: Optional[str] = None
    software: Optional[str] = None


class ExifAnalysis(BaseModel):
    """Resultado da avaliação temporal e de disponibilidade de metadados EXIF."""

    metadata_found: bool
    is_old_image: Optional[bool] = None
    age_hours: Optional[float] = None
    threshold_hours: Optional[int] = None
    reason: str
    metadata: ExifMetadata


class GeoConsistency(BaseModel):
    """Resultado da checagem de consistência entre usuário, mapa e EXIF."""

    checked: bool
    score: float
    status: Literal["consistent", "partial", "inconsistent", "not_available"]
    reason: str
    distance_user_to_map_km: Optional[float] = None
    distance_photo_to_map_km: Optional[float] = None
    distance_photo_to_user_km: Optional[float] = None


class VeracitySignals(BaseModel):
    """Decomposição dos sinais que formam o score de veracidade final."""

    visual_score: float
    temporal_score: float
    geo_score: float


class PredictionResponse(BaseModel):
    """Resposta final da API com decisão e evidências da classificação."""

    flood_detected: bool
    confidence: float
    veracity_score: float
    final_score: float
    decision: Literal["approve", "manual_review", "reject"]
    reason: str
    exif_analysis: ExifAnalysis
    geo_consistency: GeoConsistency
    veracity_signals: VeracitySignals
