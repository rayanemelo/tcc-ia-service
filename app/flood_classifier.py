import asyncio
import base64
import ipaddress
import json
import math
import re
import socket
from datetime import datetime
from io import BytesIO
from typing import Optional
from urllib.parse import urlparse

import requests
from PIL import ExifTags, Image, UnidentifiedImageError

from app.config import (
    GEO_PHOTO_MAP_MAX_DISTANCE_KM,
    GEO_PHOTO_USER_MAX_DISTANCE_KM,
    GEO_USER_MAP_MAX_DISTANCE_KM,
    LMSTUDIO_API_KEY,
    LMSTUDIO_BASE_URL,
    LMSTUDIO_CHAT_PATH,
    LMSTUDIO_MODEL,
    MAX_IMAGE_AGE_HOURS,
    THRESHOLD,
    VLM_MAX_NEW_TOKENS,
    VLM_TEMPERATURE,
)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_DOWNLOAD_TIMEOUT_SECONDS = 10
APPROVE_THRESHOLD = 0.85
MANUAL_REVIEW_THRESHOLD = 0.60
MAX_VLM_IMAGE_SIDE = 1024
VLM_JPEG_QUALITY = 85

NEUTRAL_SCORE = 0.5
VERACITY_VISUAL_WEIGHT = 0.50
VERACITY_TEMPORAL_WEIGHT = 0.20
VERACITY_GEO_WEIGHT = 0.30
FINAL_SCORE_FLOOD_WEIGHT = 0.55
FINAL_SCORE_VERACITY_WEIGHT = 0.45

EVIDENCE_QUALITY_SCORE = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
}

SYSTEM_PROMPT = (
    "Você é um especialista em análise forense visual e monitoramento de alagamentos urbanos. "
    "Sua tarefa é analisar imagens enviadas por usuários para verificar autenticidade da imagem, presença de alagamento e possíveis tentativas de fraude ou manipulação."
    "Analise cuidadosamente a imagem considerando as seguintes dimensões: "
    "1. AUTENTICIDADE DA IMAGEM "
    "Verifique se a imagem parece ser uma fotografia real de um ambiente físico. "
    "Sinais de imagem inválida incluem: "
    "- screenshot de aplicativo ou rede social "
    "- foto exibida em tela de celular, computador ou televisão "
    "- foto de outra foto impressa "
    "- imagem claramente gerada por computador, ilustração ou renderização 3D "
    "- presença de interface de aplicativo, barras de status ou menus."
    "2. MANIPULAÇÃO DIGITAL OU MONTAGEM "
    "Procure sinais de edição ou manipulação visual, como: "
    "- iluminação inconsistente entre objetos "
    "- sombras incompatíveis com a direção da luz "
    "- brilho diferente em partes da imagem "
    "- bordas recortadas indicando possível colagem "
    "- halos ou contornos artificiais em objetos "
    "- sinais de que um objeto foi retirado de outra foto e inserido na imagem "
    "- distorções no fundo da imagem "
    "- inconsistências de perspectiva "
    "- texturas desalinhadas (exemplo: azulejos ou grades desencontrados) "
    "- padrões repetidos artificialmente "
    "- áreas pixeladas ou com resolução diferente do restante da imagem "
    "- artefatos de compressão inconsistentes."
    "3. SINAIS DE IMAGEM GERADA POR IA "
    "Observe possíveis artefatos típicos de imagens geradas por IA, como: "
    "- objetos deformados ou incompletos "
    "- padrões repetitivos ou artificiais "
    "- texto ilegível em placas ou sinais "
    "- reflexos impossíveis ou inconsistentes "
    "- estruturas urbanas fisicamente impossíveis "
    "- incoerência entre objetos e cenário."
    "4. QUALIDADE DA EVIDÊNCIA "
    "Avalie se a imagem possui qualidade suficiente para análise confiável. "
    "Considere fatores como: "
    "- baixa resolução "
    "- imagem borrada "
    "- iluminação insuficiente ou muito escura "
    "- câmera obstruída por chuva, vidro ou sujeira "
    "- enquadramento que não mostra claramente o local."
    "Classifique a qualidade da evidência como: "
    "- high: imagem clara, com boa visibilidade do local "
    "- medium: imagem parcialmente clara mas com algumas limitações "
    "- low: imagem difícil de analisar."
    "5. DETECÇÃO DE ALAGAMENTO "
    "Avalie a presença de água acumulada no ambiente urbano."
    "Classifique mentalmente o nível de alagamento com base nos seguintes critérios: "
    "LEVE: "
    "- água cobrindo apenas a rua "
    "- lâmina de água rasa "
    "- trânsito ainda possível."
    "MODERADO: "
    "- água invadindo calçadas "
    "- água próxima ou entrando em imóveis "
    "- água cobrindo parte significativa das rodas dos veículos "
    "- trânsito difícil ou arriscado."
    "INTERDITADO: "
    "- rua ou área completamente submersa "
    "- veículos parcialmente submersos "
    "- grande volume de água "
    "- impossível transitar com segurança."
    "NÃO CONSIDERAR COMO ALAGAMENTO: "
    "- pequenas poças isoladas "
    "- chão apenas molhado "
    "- água acumulada apenas na sarjeta."
    "6. COBERTURA DE ÁGUA "
    "Avalie aproximadamente quanto da área visível está coberta por água: "
    "- none: nenhuma água visível "
    "- small: pequenas áreas com água "
    "- medium: parte significativa da rua coberta "
    "- large: grande parte da área visível coberta."
    "7. CONSISTÊNCIA FÍSICA DA CENA "
    "Avalie se a cena parece fisicamente plausível considerando: "
    "- continuidade da lâmina d'água "
    "- reflexos naturais "
    "- interação da água com objetos "
    "- coerência com inclinação da rua."
    "8. PROBABILIDADE DE MANIPULAÇÃO "
    "Estime a probabilidade de manipulação digital com base nos sinais observados."
    "9. PROBABILIDADE DE IMAGEM GERADA POR IA "
    "Estime a probabilidade de que a imagem tenha sido gerada por inteligência artificial."
    "Evite marcar fraude apenas por baixa qualidade da imagem. "
    "Fraude deve ser marcada apenas se houver sinais claros de manipulação ou tentativa de engano."
    "Se algum campo não puder ser determinado com confiança, forneça a melhor estimativa baseada nas evidências visuais."
    "Responda SOMENTE com JSON válido neste formato exato: "
    "{"
    '"image_valid": true|false, '
    '"flood_detected": true|false, '
    '"flood_level": "none|leve|moderado|interditado", '
    '"fraud_suspected": true|false, '
    '"confidence": 0.0-1.0, '
    '"evidence_quality": "high|medium|low", '
    '"water_coverage": "none|small|medium|large", '
    '"scene_consistency": 0.0-1.0, '
    '"manipulation_probability": 0.0-1.0, '
    '"ai_generated_probability": 0.0-1.0, '
    '"reason": "explicação curta e objetiva"'
    "}"
)

USER_PROMPT = (
    "Analise cuidadosamente a imagem enviada. "
    "Avalie autenticidade, presença de alagamento, possíveis manipulações e qualidade da evidência. "
    "Responda apenas com JSON válido no formato definido. "
    "Não use markdown e não inclua explicações adicionais."
)


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "sim"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _coerce_float(value, default: float = 0.0, *, clamp_output: bool = True) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default

    if clamp_output:
        return _clamp(number)
    return number


def _normalize_choice(value, allowed: set[str], default: str) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return text if text in allowed else default


def _safe_text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore").strip()
    else:
        text = str(value).strip()
    return text or None


def _rational_to_float(value) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    if isinstance(value, tuple) and len(value) == 2:
        numerator = _rational_to_float(value[0])
        denominator = _rational_to_float(value[1])
        if numerator is None or denominator in (None, 0):
            return None
        return numerator / denominator

    return None


def _gps_to_decimal(coordinate, reference) -> Optional[float]:
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
        degrees = _rational_to_float(coordinate[0])
        minutes = _rational_to_float(coordinate[1])
        seconds = _rational_to_float(coordinate[2])
        if None in (degrees, minutes, seconds):
            return None
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    else:
        return None

    ref_text = (_safe_text(reference) or "").upper()
    if ref_text in {"S", "W"}:
        decimal = -abs(decimal)

    return round(decimal, 6)


def _parse_exif_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    for date_format in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue

    return None


def _validate_public_url(image_url: str) -> None:
    parsed = urlparse(image_url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("imageUrl precisa usar http ou https")

    if not parsed.hostname:
        raise ValueError("imageUrl invalida")

    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Host local nao e permitido")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError("Nao foi possivel resolver o host da imagem") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError("Hosts internos/privados nao sao permitidos")


def _download_image_bytes(image_url: str) -> bytes:
    _validate_public_url(image_url)

    try:
        response = requests.get(image_url, timeout=IMAGE_DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError("Falha ao baixar a imagem da URL informada") from exc

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "image/" not in content_type:
        raise ValueError("A URL nao retornou um conteudo de imagem")

    data = response.content
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Imagem acima do limite de tamanho permitido")

    return data


def _prepare_image_for_vlm(raw_bytes: bytes) -> bytes:
    try:
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Arquivo retornado nao e uma imagem valida") from exc

    # Reduce very large images to lower vision decode memory usage in LM Studio.
    image.thumbnail((MAX_VLM_IMAGE_SIDE, MAX_VLM_IMAGE_SIDE), Image.Resampling.LANCZOS)

    output = BytesIO()
    image.save(output, format="JPEG", quality=VLM_JPEG_QUALITY, optimize=True)
    return output.getvalue()


def _extract_exif_metadata(raw_bytes: bytes) -> dict:
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

    metadata["datetime_original"] = _safe_text(exif_named.get("DateTimeOriginal"))
    metadata["gps_latitude"] = _gps_to_decimal(
        gps_named.get("GPSLatitude"), gps_named.get("GPSLatitudeRef")
    )
    metadata["gps_longitude"] = _gps_to_decimal(
        gps_named.get("GPSLongitude"), gps_named.get("GPSLongitudeRef")
    )
    metadata["make"] = _safe_text(exif_named.get("Make"))
    metadata["model"] = _safe_text(exif_named.get("Model"))
    metadata["software"] = _safe_text(exif_named.get("Software"))

    metadata_found = any(value is not None for value in metadata.values())
    return {
        "metadata_found": metadata_found,
        "metadata": metadata,
    }


def _score_from_age_hours(age_hours: float) -> float:
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.85
    if age_hours <= MAX_IMAGE_AGE_HOURS:
        return 0.7
    if age_hours <= 24 * 30:
        return 0.35
    return 0.15


def _analyze_image_age(exif_payload: dict) -> tuple[dict, float]:
    metadata = exif_payload["metadata"]
    datetime_original = metadata.get("datetime_original")
    capture_datetime = _parse_exif_datetime(datetime_original)

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
    temporal_score = _score_from_age_hours(age_hours)

    if is_old_image:
        reason = (
            f"Foto considerada antiga: {age_hours:.1f}h (limite {MAX_IMAGE_AGE_HOURS}h)"
        )
    else:
        reason = f"Foto recente: {age_hours:.1f}h"

    result["is_old_image"] = is_old_image
    result["age_hours"] = round(age_hours, 2)
    result["reason"] = reason
    return result, temporal_score


def _normalize_point(point: Optional[dict]) -> Optional[tuple[float, float]]:
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


def _haversine_km(
    point_a: Optional[tuple[float, float]], point_b: Optional[tuple[float, float]]
) -> Optional[float]:
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


def _distance_consistency_score(distance_km: float, max_distance_km: float) -> float:
    limit = max(max_distance_km, 0.1)

    if distance_km <= limit:
        return 1.0
    if distance_km <= limit * 2:
        return 0.65
    if distance_km <= limit * 4:
        return 0.35
    return 0.0


def _round_or_none(value: Optional[float], decimals: int = 3) -> Optional[float]:
    if value is None:
        return None
    return round(value, decimals)


def _evaluate_geo_consistency(
    user_location: Optional[dict],
    map_location: Optional[dict],
    photo_location: Optional[dict],
) -> dict:
    user_point = _normalize_point(user_location)
    map_point = _normalize_point(map_location)
    photo_point = _normalize_point(photo_location)

    distance_user_to_map = _haversine_km(user_point, map_point)
    distance_photo_to_map = _haversine_km(photo_point, map_point)
    distance_photo_to_user = _haversine_km(photo_point, user_point)

    has_photo_reference = (
        distance_photo_to_map is not None or distance_photo_to_user is not None
    )

    if not has_photo_reference and distance_user_to_map is not None:
        user_map_score = _distance_consistency_score(
            distance_user_to_map,
            GEO_USER_MAP_MAX_DISTANCE_KM,
        )
        partial_score = _clamp((user_map_score * 0.4) + (NEUTRAL_SCORE * 0.6))
        return {
            "checked": True,
            "score": round(partial_score, 4),
            "status": "partial",
            "reason": "GPS EXIF ausente; consistencia apenas entre usuario e ponto no mapa",
            "distance_user_to_map_km": _round_or_none(distance_user_to_map),
            "distance_photo_to_map_km": _round_or_none(distance_photo_to_map),
            "distance_photo_to_user_km": _round_or_none(distance_photo_to_user),
        }

    components = []
    if distance_user_to_map is not None:
        components.append(
            _distance_consistency_score(
                distance_user_to_map,
                GEO_USER_MAP_MAX_DISTANCE_KM,
            )
        )

    if distance_photo_to_map is not None:
        components.append(
            _distance_consistency_score(
                distance_photo_to_map,
                GEO_PHOTO_MAP_MAX_DISTANCE_KM,
            )
        )

    if distance_photo_to_user is not None:
        components.append(
            _distance_consistency_score(
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
            "distance_user_to_map_km": _round_or_none(distance_user_to_map),
            "distance_photo_to_map_km": _round_or_none(distance_photo_to_map),
            "distance_photo_to_user_km": _round_or_none(distance_photo_to_user),
        }

    score = _clamp(sum(components) / len(components))
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
        "distance_user_to_map_km": _round_or_none(distance_user_to_map),
        "distance_photo_to_map_km": _round_or_none(distance_photo_to_map),
        "distance_photo_to_user_km": _round_or_none(distance_photo_to_user),
    }


def _photo_location_from_exif(exif_analysis: dict) -> Optional[dict]:
    metadata = exif_analysis.get("metadata", {})
    latitude = metadata.get("gps_latitude")
    longitude = metadata.get("gps_longitude")

    if latitude is None or longitude is None:
        return None

    return {
        "latitude": latitude,
        "longitude": longitude,
    }


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Resposta do modelo nao contem JSON valido")

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError("Resposta JSON do modelo invalida") from exc

    if not isinstance(parsed, dict):
        raise ValueError("JSON retornado pelo modelo nao e um objeto")

    return parsed


def _normalize_output(parsed: dict) -> dict:
    image_valid = _coerce_bool(parsed.get("image_valid", True))
    flood_detected = _coerce_bool(parsed.get("flood_detected", False))
    fraud_suspected = _coerce_bool(parsed.get("fraud_suspected", False))
    confidence = _coerce_float(parsed.get("confidence", 0.0), 0.0)

    if not image_valid:
        flood_detected = False
        confidence = min(confidence, 0.2)

    if flood_detected and confidence < THRESHOLD:
        confidence = THRESHOLD
    if not flood_detected and confidence >= THRESHOLD:
        confidence = THRESHOLD - 0.01

    reason = str(parsed.get("reason", "Sem justificativa retornada pelo modelo")).strip()
    if not reason:
        reason = "Sem justificativa retornada pelo modelo"

    return {
        "image_valid": image_valid,
        "flood_detected": flood_detected,
        "fraud_suspected": fraud_suspected,
        "confidence": round(_clamp(confidence), 4),
        "evidence_quality": _normalize_choice(
            parsed.get("evidence_quality"), {"high", "medium", "low"}, "medium"
        ),
        "scene_consistency": round(
            _coerce_float(parsed.get("scene_consistency", 0.5), 0.5), 4
        ),
        "manipulation_probability": round(
            _coerce_float(parsed.get("manipulation_probability", 0.0), 0.0), 4
        ),
        "ai_generated_probability": round(
            _coerce_float(parsed.get("ai_generated_probability", 0.0), 0.0), 4
        ),
        "reason": reason,
    }


def _compute_visual_veracity_score(model_output: dict) -> float:
    quality_score = EVIDENCE_QUALITY_SCORE.get(
        model_output["evidence_quality"],
        NEUTRAL_SCORE,
    )

    score = (
        0.30 * (1.0 if model_output["image_valid"] else 0.0)
        + 0.20 * (0.0 if model_output["fraud_suspected"] else 1.0)
        + 0.20 * (1.0 - model_output["manipulation_probability"])
        + 0.10 * (1.0 - model_output["ai_generated_probability"])
        + 0.10 * model_output["scene_consistency"]
        + 0.10 * quality_score
    )

    return _clamp(score)


def _compute_veracity_score(
    visual_score: float,
    temporal_score: float,
    geo_score: float,
) -> float:
    return _clamp(
        (visual_score * VERACITY_VISUAL_WEIGHT)
        + (temporal_score * VERACITY_TEMPORAL_WEIGHT)
        + (geo_score * VERACITY_GEO_WEIGHT)
    )


def _decision_from_score(
    image_valid: bool,
    flood_detected: bool,
    final_score: float,
    veracity_score: float,
) -> tuple[str, str]:
    if not image_valid:
        return "reject", "Imagem invalida para comprovacao (ex.: screenshot/foto de tela)"

    if not flood_detected:
        return "reject", "Alagamento nao detectado"

    if veracity_score < 0.35:
        return "reject", "Baixa veracidade da evidencia"

    if final_score >= APPROVE_THRESHOLD:
        return "approve", "Alta confianca para aprovacao"

    if final_score >= MANUAL_REVIEW_THRESHOLD:
        return "manual_review", "Pontuacao intermediaria, revisar manualmente"

    return "reject", "Baixa confianca geral para aprovacao"


def _predict_with_lmstudio(raw_bytes: bytes) -> dict:
    image_b64 = base64.b64encode(raw_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{image_b64}"

    payload = {
        "model": LMSTUDIO_MODEL,
        "temperature": VLM_TEMPERATURE,
        "max_tokens": VLM_MAX_NEW_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    }

    headers = {"Content-Type": "application/json"}
    if LMSTUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"

    endpoint = f"{LMSTUDIO_BASE_URL.rstrip('/')}/{LMSTUDIO_CHAT_PATH.lstrip('/')}"

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Falha ao consultar LM Studio em '{endpoint}': {exc}"
        ) from exc

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError("Resposta do LM Studio em formato inesperado") from exc

    parsed = _extract_json(content if isinstance(content, str) else json.dumps(content))
    return _normalize_output(parsed)


async def predict_image_from_url(
    image_url: str,
    user_location: Optional[dict] = None,
    map_location: Optional[dict] = None,
):
    raw_bytes = await asyncio.to_thread(_download_image_bytes, image_url)

    exif_payload = await asyncio.to_thread(_extract_exif_metadata, raw_bytes)
    exif_analysis, temporal_score = await asyncio.to_thread(
        _analyze_image_age,
        exif_payload,
    )

    photo_location = _photo_location_from_exif(exif_analysis)
    geo_consistency = await asyncio.to_thread(
        _evaluate_geo_consistency,
        user_location,
        map_location,
        photo_location,
    )

    prepared_bytes = await asyncio.to_thread(_prepare_image_for_vlm, raw_bytes)
    model_output = await asyncio.to_thread(_predict_with_lmstudio, prepared_bytes)

    visual_score = _compute_visual_veracity_score(model_output)
    geo_score = float(geo_consistency["score"])

    veracity_score = _compute_veracity_score(
        visual_score,
        temporal_score,
        geo_score,
    )

    final_score = _clamp(
        (model_output["confidence"] * FINAL_SCORE_FLOOD_WEIGHT)
        + (veracity_score * FINAL_SCORE_VERACITY_WEIGHT)
    )

    decision, decision_reason = _decision_from_score(
        model_output["image_valid"],
        model_output["flood_detected"],
        final_score,
        veracity_score,
    )

    reason = model_output["reason"].strip().rstrip(".")
    if decision != "approve":
        reason = f"{reason}. {decision_reason}"

    return {
        "flood_detected": model_output["flood_detected"],
        "confidence": model_output["confidence"],
        "veracity_score": round(veracity_score, 4),
        "final_score": round(final_score, 4),
        "decision": decision,
        "reason": reason,
        "exif_analysis": exif_analysis,
        "geo_consistency": geo_consistency,
        "veracity_signals": {
            "visual_score": round(visual_score, 4),
            "temporal_score": round(temporal_score, 4),
            "geo_score": round(geo_score, 4),
        },
    }
