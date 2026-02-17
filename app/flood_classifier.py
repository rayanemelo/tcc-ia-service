import requests
from PIL import Image
from io import BytesIO
import random


async def predict_image_from_url(image_url: str):
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content))

    confidence = round(random.uniform(0.5, 0.95), 2)
    flood_detected = confidence > 0.7

    return {"flood_detected": flood_detected, "confidence": confidence}
