"""Ponto de entrada da API FastAPI e registro das rotas HTTP."""

from fastapi import FastAPI
from app.routes import router

app = FastAPI(
    title="Flood AI Service",
    description="Serviço de análise de imagens para detecção de alagamentos",
    version="1.0.0",
)

app.include_router(router)
