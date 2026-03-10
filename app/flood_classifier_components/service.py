"""Orquestra o pipeline completo de classificação de imagens de alagamento."""

import asyncio
from typing import Optional

from app.flood_classifier_components.exif_utils import (
    analyze_image_age,
    extract_exif_metadata,
    photo_location_from_exif,
)
from app.flood_classifier_components.geo import evaluate_geo_consistency
from app.flood_classifier_components.image_io import (
    download_image_bytes,
    prepare_image_for_vlm,
)
from app.flood_classifier_components.lmstudio import predict_with_lmstudio
from app.flood_classifier_components.scoring import (
    compute_final_score,
    compute_veracity_score,
    compute_visual_veracity_score,
    decision_from_score,
)


async def predict_image_from_url(
    image_url: str,
    user_location: Optional[dict] = None,
    map_location: Optional[dict] = None,
):
    """Orquestra o pipeline completo de classificacao da imagem."""
    raw_bytes = await asyncio.to_thread(download_image_bytes, image_url)

    exif_payload = await asyncio.to_thread(extract_exif_metadata, raw_bytes)
    exif_analysis, temporal_score = await asyncio.to_thread(
        analyze_image_age,
        exif_payload,
    )

    photo_location = photo_location_from_exif(exif_analysis)
    geo_consistency = await asyncio.to_thread(
        evaluate_geo_consistency,
        user_location,
        map_location,
        photo_location,
    )

    prepared_bytes = await asyncio.to_thread(prepare_image_for_vlm, raw_bytes)
    model_output = await asyncio.to_thread(predict_with_lmstudio, prepared_bytes)

    visual_score = compute_visual_veracity_score(model_output)
    geo_score = float(geo_consistency["score"])

    veracity_score = compute_veracity_score(
        visual_score,
        temporal_score,
        geo_score,
    )

    final_score = compute_final_score(model_output["confidence"], veracity_score)

    decision, decision_reason = decision_from_score(
        model_output["image_valid"],
        model_output["flood_detected"],
        final_score,
        veracity_score,
    )

    reason = model_output["reason"].strip().rstrip(".")
    if decision != "approve":
        reason = f"{reason}. {decision_reason}"

    return {
        "flood_detected": model_output["flood_detected"],
        "confidence": model_output["confidence"],
        "veracity_score": round(veracity_score, 4),
        "final_score": round(final_score, 4),
        "decision": decision,
        "reason": reason,
        "exif_analysis": exif_analysis,
        "geo_consistency": geo_consistency,
        "veracity_signals": {
            "visual_score": round(visual_score, 4),
            "temporal_score": round(temporal_score, 4),
            "geo_score": round(geo_score, 4),
        },
    }
