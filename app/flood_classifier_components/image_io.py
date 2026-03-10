"""Validação de URL, download e preparo de imagem para inferência visual."""

import ipaddress
import socket
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError

from app.flood_classifier_components.constants import (
    IMAGE_DOWNLOAD_TIMEOUT_SECONDS,
    MAX_IMAGE_BYTES,
    MAX_VLM_IMAGE_SIDE,
    VLM_JPEG_QUALITY,
)


def validate_public_url(image_url: str) -> None:
    """Valida URL de imagem para evitar SSRF e hosts internos."""
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


def download_image_bytes(image_url: str) -> bytes:
    """Baixa bytes da imagem, validando URL, tipo MIME e tamanho maximo."""
    validate_public_url(image_url)

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


def prepare_image_for_vlm(raw_bytes: bytes) -> bytes:
    """Converte a imagem para JPEG RGB e reduz dimensao para inferencia no VLM."""
    try:
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Arquivo retornado nao e uma imagem valida") from exc

    image.thumbnail((MAX_VLM_IMAGE_SIDE, MAX_VLM_IMAGE_SIDE), Image.Resampling.LANCZOS)

    output = BytesIO()
    image.save(output, format="JPEG", quality=VLM_JPEG_QUALITY, optimize=True)
    return output.getvalue()
