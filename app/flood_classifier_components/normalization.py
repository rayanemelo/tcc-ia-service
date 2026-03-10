"""Utilitários de coerção, clamp e parsing de JSON retornado pelo modelo."""

import json
import re
from typing import Optional

from app.config import THRESHOLD


def clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    """Limita um valor ao intervalo fechado [min_value, max_value]."""
    return max(min_value, min(max_value, value))


def coerce_bool(value) -> bool:
    """Normaliza entradas heterogeneas para booleano."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "sim"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def coerce_float(value, default: float = 0.0, *, clamp_output: bool = True) -> float:
    """Converte entrada para float com fallback seguro."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default

    if clamp_output:
        return clamp(number)
    return number


def normalize_choice(value, allowed: set[str], default: str) -> str:
    """Normaliza um texto para uma lista fechada de opcoes permitidas."""
    text = str(value).strip().lower() if value is not None else ""
    return text if text in allowed else default


def safe_text(value) -> Optional[str]:
    """Converte bytes/objeto para string limpa; retorna None para vazio."""
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore").strip()
    else:
        text = str(value).strip()
    return text or None


def extract_json_object(text: str) -> dict:
    """Extrai um objeto JSON da resposta textual do modelo."""
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


def normalize_model_output(parsed: dict) -> dict:
    """Normaliza e corrige campos da resposta do modelo."""
    image_valid = coerce_bool(parsed.get("image_valid", True))
    flood_detected = coerce_bool(parsed.get("flood_detected", False))
    fraud_suspected = coerce_bool(parsed.get("fraud_suspected", False))
    confidence = coerce_float(parsed.get("confidence", 0.0), 0.0)

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
        "confidence": round(clamp(confidence), 4),
        "evidence_quality": normalize_choice(
            parsed.get("evidence_quality"), {"high", "medium", "low"}, "medium"
        ),
        "scene_consistency": round(coerce_float(parsed.get("scene_consistency", 0.5), 0.5), 4),
        "manipulation_probability": round(
            coerce_float(parsed.get("manipulation_probability", 0.0), 0.0), 4
        ),
        "ai_generated_probability": round(
            coerce_float(parsed.get("ai_generated_probability", 0.0), 0.0), 4
        ),
        "reason": reason,
    }
