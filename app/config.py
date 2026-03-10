"""Centraliza leitura de variáveis de ambiente e parâmetros globais da aplicação."""

import os
from dotenv import load_dotenv

load_dotenv()

THRESHOLD = float(os.getenv("THRESHOLD", 0.7))
VLM_MAX_NEW_TOKENS = int(os.getenv("VLM_MAX_NEW_TOKENS", "256"))
VLM_TEMPERATURE = float(os.getenv("VLM_TEMPERATURE", "0.2"))
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")
LMSTUDIO_CHAT_PATH = os.getenv("LMSTUDIO_CHAT_PATH", "/v1/chat/completions")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "mistralai/ministral-3-3b")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")

# Anti-fraud tuning
MAX_IMAGE_AGE_HOURS = int(os.getenv("MAX_IMAGE_AGE_HOURS", "168"))
GEO_USER_MAP_MAX_DISTANCE_KM = float(os.getenv("GEO_USER_MAP_MAX_DISTANCE_KM", "5"))
GEO_PHOTO_MAP_MAX_DISTANCE_KM = float(os.getenv("GEO_PHOTO_MAP_MAX_DISTANCE_KM", "1.5"))
GEO_PHOTO_USER_MAX_DISTANCE_KM = float(os.getenv("GEO_PHOTO_USER_MAX_DISTANCE_KM", "5"))
