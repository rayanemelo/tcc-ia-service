import asyncio
import base64
import ipaddress
import json
import re
import socket
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError

from app.config import (
    LMSTUDIO_API_KEY,
    LMSTUDIO_BASE_URL,
    LMSTUDIO_CHAT_PATH,
    LMSTUDIO_MODEL,
    THRESHOLD,
    VLM_MAX_NEW_TOKENS,
    VLM_TEMPERATURE,
)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_DOWNLOAD_TIMEOUT_SECONDS = 10
APPROVE_THRESHOLD = 0.85
MANUAL_REVIEW_THRESHOLD = 0.60

SYSTEM_PROMPT = (
    "Voce analisa imagens para identificar alagamentos urbanos. "
    "Responda SOMENTE com JSON valido neste formato: "
    '{"flood_detected": true|false, "confidence": 0.0-1.0, "reason": "texto curto"}'
)

USER_PROMPT = (
    "Analise esta imagem e indique se ha alagamento real no local. "
    "Nao use markdown, nao use texto extra, responda apenas JSON."
)


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
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
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


def _decision_from_confidence(confidence: float) -> tuple[str, str]:
    if confidence >= APPROVE_THRESHOLD:
        return "approve", "Alta confianca para alagamento"
    if confidence >= MANUAL_REVIEW_THRESHOLD:
        return "manual_review", "Confianca intermediaria, requer validacao humana"
    return "reject", "Baixa confianca para alagamento"


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "sim"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _normalize_output(parsed: dict) -> dict:
    flood_detected = _coerce_bool(parsed.get("flood_detected", False))
    confidence_raw = parsed.get("confidence", 0.0)

    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(1.0, confidence))

    reason = str(parsed.get("reason", "Sem justificativa retornada pelo modelo"))
    if flood_detected and confidence < THRESHOLD:
        confidence = THRESHOLD
    if not flood_detected and confidence >= THRESHOLD:
        confidence = THRESHOLD - 0.01

    decision, decision_reason = _decision_from_confidence(confidence)
    return {
        "flood_detected": flood_detected,
        "confidence": round(confidence, 4),
        "decision": decision,
        "reason": reason if reason else decision_reason,
    }


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
        raise RuntimeError(f"Falha ao consultar LM Studio em '{endpoint}': {exc}") from exc

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError("Resposta do LM Studio em formato inesperado") from exc

    parsed = _extract_json(content if isinstance(content, str) else json.dumps(content))
    return _normalize_output(parsed)


async def predict_image_from_url(image_url: str):
    raw_bytes = await asyncio.to_thread(_download_image_bytes, image_url)

    try:
        Image.open(BytesIO(raw_bytes)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Arquivo retornado nao e uma imagem valida") from exc

    return await asyncio.to_thread(_predict_with_lmstudio, raw_bytes)
