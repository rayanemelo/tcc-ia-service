"""Cálculo de scores de veracidade/final e regra de decisão operacional."""

from app.flood_classifier_components.constants import (
    APPROVE_THRESHOLD,
    EVIDENCE_QUALITY_SCORE,
    FINAL_SCORE_FLOOD_WEIGHT,
    FINAL_SCORE_VERACITY_WEIGHT,
    MANUAL_REVIEW_THRESHOLD,
    NEUTRAL_SCORE,
    VERACITY_GEO_WEIGHT,
    VERACITY_TEMPORAL_WEIGHT,
    VERACITY_VISUAL_WEIGHT,
)
from app.flood_classifier_components.normalization import clamp


def compute_visual_veracity_score(model_output: dict) -> float:
    """Calcula score visual de veracidade a partir da saida do modelo."""
    quality_score = EVIDENCE_QUALITY_SCORE.get(
        model_output["evidence_quality"],
        NEUTRAL_SCORE,
    )

    score = (
        0.30 * (1.0 if model_output["image_valid"] else 0.0)
        + 0.20 * (0.0 if model_output["fraud_suspected"] else 1.0)
        + 0.20 * (1.0 - model_output["manipulation_probability"])
        + 0.10 * (1.0 - model_output["ai_generated_probability"])
        + 0.10 * model_output["scene_consistency"]
        + 0.10 * quality_score
    )

    return clamp(score)


def compute_veracity_score(
    visual_score: float,
    temporal_score: float,
    geo_score: float,
) -> float:
    """Combina sinais visual/temporal/geografico no score de veracidade."""
    return clamp(
        (visual_score * VERACITY_VISUAL_WEIGHT)
        + (temporal_score * VERACITY_TEMPORAL_WEIGHT)
        + (geo_score * VERACITY_GEO_WEIGHT)
    )


def compute_final_score(confidence: float, veracity_score: float) -> float:
    """Calcula score final ponderando confianca visual e veracidade global."""
    return clamp(
        (confidence * FINAL_SCORE_FLOOD_WEIGHT)
        + (veracity_score * FINAL_SCORE_VERACITY_WEIGHT)
    )


def decision_from_score(
    image_valid: bool,
    flood_detected: bool,
    final_score: float,
    veracity_score: float,
) -> tuple[str, str]:
    """Converte scores em decisao operacional."""
    if not image_valid:
        return "reject", "Imagem invalida para comprovacao (ex.: screenshot/foto de tela)"

    if not flood_detected:
        return "reject", "Alagamento nao detectado"

    if veracity_score < 0.35:
        return "reject", "Baixa veracidade da evidencia"

    if final_score >= APPROVE_THRESHOLD:
        return "approve", "Alta confianca para aprovacao"

    if final_score >= MANUAL_REVIEW_THRESHOLD:
        return "manual_review", "Pontuacao intermediaria, revisar manualmente"

    return "reject", "Baixa confianca geral para aprovacao"
