"""Expõe a interface pública do pacote modular do classificador de alagamento."""

from app.flood_classifier_components.service import predict_image_from_url

__all__ = ["predict_image_from_url"]
