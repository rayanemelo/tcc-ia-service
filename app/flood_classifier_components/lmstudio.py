"""Integração com LM Studio para inferência multimodal e normalização da resposta."""

import base64
import json

import requests

from app.config import (
    LMSTUDIO_API_KEY,
    LMSTUDIO_BASE_URL,
    LMSTUDIO_CHAT_PATH,
    LMSTUDIO_MODEL,
    VLM_MAX_NEW_TOKENS,
    VLM_TEMPERATURE,
)
from app.flood_classifier_components.constants import SYSTEM_PROMPT, USER_PROMPT
from app.flood_classifier_components.normalization import (
    extract_json_object,
    normalize_model_output,
)


def predict_with_lmstudio(raw_bytes: bytes) -> dict:
    """Executa inferencia no LM Studio e devolve saida normalizada."""
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

    parsed = extract_json_object(content if isinstance(content, str) else json.dumps(content))
    return normalize_model_output(parsed)
