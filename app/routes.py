from fastapi import APIRouter, UploadFile, File
from app.flood_classifier import predict_image_from_url
from app.schemas import AnalyzeRequest, PredictionResponse

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/analyze", response_model=PredictionResponse)
async def analyze_image(data: AnalyzeRequest):
    result = await predict_image_from_url(data.imageUrl)
    return result
