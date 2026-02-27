from fastapi import APIRouter, HTTPException

from app.flood_classifier import predict_image_from_url
from app.schemas import AnalyzeRequest, PredictionResponse

router = APIRouter()


@router.get("/")
async def health_check():
    return {"status": "ok"}


@router.post("/analyze", response_model=PredictionResponse)
async def analyze_image(data: AnalyzeRequest):
    try:
        return await predict_image_from_url(str(data.imageUrl))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
