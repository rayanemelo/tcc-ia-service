import os

MODEL_PATH = os.getenv("MODEL_PATH", "models/flood_classifier.pt")
THRESHOLD = float(os.getenv("THRESHOLD", 0.7))
