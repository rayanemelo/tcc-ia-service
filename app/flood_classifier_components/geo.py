"""Cálculos geográficos e validação de consistência entre pontos de localização."""

import math
from typing import Optional

from app.config import (
    GEO_PHOTO_MAP_MAX_DISTANCE_KM,
    GEO_PHOTO_USER_MAX_DISTANCE_KM,
    GEO_USER_MAP_MAX_DISTANCE_KM,
)
from app.flood_classifier_components.constants import NEUTRAL_SCORE
from app.flood_classifier_components.normalization import clamp


def normalize_point(point: Optional[dict]) -> Optional[tuple[float, float]]:
    """Normaliza um dicionario {'latitude','longitude'} para tupla (lat, lon)."""
    if not point:
        return None

    try:
        latitude = float(point["latitude"])
        longitude = float(point["longitude"])
    except (TypeError, ValueError, KeyError):
        return None

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    return latitude, longitude


def haversine_km(
    point_a: Optional[tuple[float, float]], point_b: Optional[tuple[float, float]]
) -> Optional[float]:
    """Calcula distancia entre dois pontos geograficos em km (formula de Haversine)."""
    if point_a is None or point_b is None:
        return None

    lat1, lon1 = point_a
    lat2, lon2 = point_b

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    earth_radius_km = 6371.0
    return earth_radius_km * c


def distance_consistency_score(distance_km: float, max_distance_km: float) -> float:
    """Converte distancia em score de consistencia geografica."""
    limit = max(max_distance_km, 0.1)

    if distance_km <= limit:
        return 1.0
    if distance_km <= limit * 2:
        return 0.65
    if distance_km <= limit * 4:
        return 0.35
    return 0.0


def round_or_none(value: Optional[float], decimals: int = 3) -> Optional[float]:
    """Arredonda valores numericos para exibicao; preserva None."""
    if value is None:
        return None
    return round(value, decimals)


def evaluate_geo_consistency(
    user_location: Optional[dict],
    map_location: Optional[dict],
    photo_location: Optional[dict],
) -> dict:
    """Avalia consistencia geografica entre usuario, mapa e EXIF da foto."""
    user_point = normalize_point(user_location)
    map_point = normalize_point(map_location)
    photo_point = normalize_point(photo_location)

    distance_user_to_map = haversine_km(user_point, map_point)
    distance_photo_to_map = haversine_km(photo_point, map_point)
    distance_photo_to_user = haversine_km(photo_point, user_point)

    has_photo_reference = (
        distance_photo_to_map is not None or distance_photo_to_user is not None
    )

    if not has_photo_reference and distance_user_to_map is not None:
        user_map_score = distance_consistency_score(
            distance_user_to_map,
            GEO_USER_MAP_MAX_DISTANCE_KM,
        )
        partial_score = clamp((user_map_score * 0.4) + (NEUTRAL_SCORE * 0.6))
        return {
            "checked": True,
            "score": round(partial_score, 4),
            "status": "partial",
            "reason": "GPS EXIF ausente; consistencia apenas entre usuario e ponto no mapa",
            "distance_user_to_map_km": round_or_none(distance_user_to_map),
            "distance_photo_to_map_km": round_or_none(distance_photo_to_map),
            "distance_photo_to_user_km": round_or_none(distance_photo_to_user),
        }

    components = []
    if distance_user_to_map is not None:
        components.append(
            distance_consistency_score(
                distance_user_to_map,
                GEO_USER_MAP_MAX_DISTANCE_KM,
            )
        )

    if distance_photo_to_map is not None:
        components.append(
            distance_consistency_score(
                distance_photo_to_map,
                GEO_PHOTO_MAP_MAX_DISTANCE_KM,
            )
        )

    if distance_photo_to_user is not None:
        components.append(
            distance_consistency_score(
                distance_photo_to_user,
                GEO_PHOTO_USER_MAX_DISTANCE_KM,
            )
        )

    if not components:
        return {
            "checked": False,
            "score": NEUTRAL_SCORE,
            "status": "not_available",
            "reason": "Dados insuficientes para validar consistencia geografica",
            "distance_user_to_map_km": round_or_none(distance_user_to_map),
            "distance_photo_to_map_km": round_or_none(distance_photo_to_map),
            "distance_photo_to_user_km": round_or_none(distance_photo_to_user),
        }

    score = clamp(sum(components) / len(components))
    if score >= 0.75:
        status = "consistent"
        reason = "Coordenadas entre usuario, mapa e foto estao consistentes"
    elif score >= 0.5:
        status = "partial"
        reason = "Consistencia geografica parcial; recomenda revisao manual"
    else:
        status = "inconsistent"
        reason = "Inconsistencia geografica relevante detectada"

    return {
        "checked": True,
        "score": round(score, 4),
        "status": status,
        "reason": reason,
        "distance_user_to_map_km": round_or_none(distance_user_to_map),
        "distance_photo_to_map_km": round_or_none(distance_photo_to_map),
        "distance_photo_to_user_km": round_or_none(distance_photo_to_user),
    }
