"""Funções para extrair EXIF, converter GPS e avaliar idade temporal da imagem."""

from datetime import datetime
from io import BytesIO
from typing import Optional

from PIL import ExifTags, Image, UnidentifiedImageError

from app.config import MAX_IMAGE_AGE_HOURS
from app.flood_classifier_components.constants import NEUTRAL_SCORE
from app.flood_classifier_components.normalization import safe_text


def rational_to_float(value) -> Optional[float]:
    """Converte representacoes EXIF racionais para float."""
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    if isinstance(value, tuple) and len(value) == 2:
        numerator = rational_to_float(value[0])
        denominator = rational_to_float(value[1])
        if numerator is None or denominator in (None, 0):
            return None
        return numerator / denominator

    return None


def gps_to_decimal(coordinate, reference) -> Optional[float]:
    """Converte coordenada GPS EXIF para graus decimais."""
    if coordinate is None:
        return None

    if isinstance(coordinate, (int, float)):
        decimal = float(coordinate)
    elif isinstance(coordinate, str):
        try:
            decimal = float(coordinate)
        except ValueError:
            return None
    elif isinstance(coordinate, (tuple, list)) and len(coordinate) >= 3:
        degrees = rational_to_float(coordinate[0])
        minutes = rational_to_float(coordinate[1])
        seconds = rational_to_float(coordinate[2])
        if None in (degrees, minutes, seconds):
            return None
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    else:
        return None

    ref_text = (safe_text(reference) or "").upper()
    if ref_text in {"S", "W"}:
        decimal = -abs(decimal)

    return round(decimal, 6)


def parse_exif_datetime(value: Optional[str]) -> Optional[datetime]:
    """Interpreta datas EXIF nos formatos mais comuns."""
    if not value:
        return None

    for date_format in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue

    return None


def extract_exif_metadata(raw_bytes: bytes) -> dict:
    """Extrai metadados EXIF usados na verificacao temporal e geografica."""
    metadata = {
        "datetime_original": None,
        "gps_latitude": None,
        "gps_longitude": None,
        "make": None,
        "model": None,
        "software": None,
    }

    try:
        with Image.open(BytesIO(raw_bytes)) as image:
            exif_raw = image.getexif()
    except (UnidentifiedImageError, OSError):
        return {
            "metadata_found": False,
            "metadata": metadata,
        }

    if not exif_raw:
        return {
            "metadata_found": False,
            "metadata": metadata,
        }

    exif_named = {
        ExifTags.TAGS.get(tag_id, tag_id): value for tag_id, value in exif_raw.items()
    }
    gps_info = exif_named.get("GPSInfo")
    gps_named = {}
    if isinstance(gps_info, dict):
        gps_named = {
            ExifTags.GPSTAGS.get(tag_id, tag_id): value
            for tag_id, value in gps_info.items()
        }

    metadata["datetime_original"] = safe_text(exif_named.get("DateTimeOriginal"))
    metadata["gps_latitude"] = gps_to_decimal(
        gps_named.get("GPSLatitude"), gps_named.get("GPSLatitudeRef")
    )
    metadata["gps_longitude"] = gps_to_decimal(
        gps_named.get("GPSLongitude"), gps_named.get("GPSLongitudeRef")
    )
    metadata["make"] = safe_text(exif_named.get("Make"))
    metadata["model"] = safe_text(exif_named.get("Model"))
    metadata["software"] = safe_text(exif_named.get("Software"))

    metadata_found = any(value is not None for value in metadata.values())
    return {
        "metadata_found": metadata_found,
        "metadata": metadata,
    }


def score_from_age_hours(age_hours: float) -> float:
    """Mapeia idade da foto (em horas) para score temporal [0,1]."""
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.85
    if age_hours <= MAX_IMAGE_AGE_HOURS:
        return 0.7
    if age_hours <= 24 * 30:
        return 0.35
    return 0.15


def analyze_image_age(exif_payload: dict) -> tuple[dict, float]:
    """Analisa idade da imagem com base no EXIF DateTimeOriginal."""
    metadata = exif_payload["metadata"]
    datetime_original = metadata.get("datetime_original")
    capture_datetime = parse_exif_datetime(datetime_original)

    result = {
        "metadata_found": exif_payload.get("metadata_found", False),
        "is_old_image": None,
        "age_hours": None,
        "threshold_hours": MAX_IMAGE_AGE_HOURS,
        "reason": "DateTimeOriginal ausente ou invalido no EXIF",
        "metadata": metadata,
    }

    if capture_datetime is None:
        return result, NEUTRAL_SCORE

    now = datetime.now(capture_datetime.tzinfo) if capture_datetime.tzinfo else datetime.now()
    age_hours = (now - capture_datetime).total_seconds() / 3600.0

    if age_hours < -1:
        result["is_old_image"] = True
        result["age_hours"] = round(age_hours, 2)
        result["reason"] = "Data da foto no futuro em relacao ao servidor"
        return result, 0.1

    age_hours = max(0.0, age_hours)
    is_old_image = age_hours > MAX_IMAGE_AGE_HOURS
    temporal_score = score_from_age_hours(age_hours)

    if is_old_image:
        reason = f"Foto considerada antiga: {age_hours:.1f}h (limite {MAX_IMAGE_AGE_HOURS}h)"
    else:
        reason = f"Foto recente: {age_hours:.1f}h"

    result["is_old_image"] = is_old_image
    result["age_hours"] = round(age_hours, 2)
    result["reason"] = reason
    return result, temporal_score


def photo_location_from_exif(exif_analysis: dict) -> Optional[dict]:
    """Extrai latitude/longitude da analise EXIF no formato esperado."""
    metadata = exif_analysis.get("metadata", {})
    latitude = metadata.get("gps_latitude")
    longitude = metadata.get("gps_longitude")

    if latitude is None or longitude is None:
        return None

    return {
        "latitude": latitude,
        "longitude": longitude,
    }
