import os

THRESHOLD = float(os.getenv("THRESHOLD", 0.7))
AI_PROVIDER = os.getenv("AI_PROVIDER", "transformers").lower()
VLM_MODEL_ID = os.getenv("VLM_MODEL_ID", "Qwen/Qwen3-VL-8B-Thinking")
VLM_MAX_NEW_TOKENS = int(os.getenv("VLM_MAX_NEW_TOKENS", "256"))
VLM_TEMPERATURE = float(os.getenv("VLM_TEMPERATURE", "0.2"))
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")
LMSTUDIO_CHAT_PATH = os.getenv("LMSTUDIO_CHAT_PATH", "/v1/chat/completions")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "qwen/qwen3-vl-8b")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
