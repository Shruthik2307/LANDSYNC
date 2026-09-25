"""
engine/ml_schema.py
===================
Versioned ML feature contract shared by training and serving.

The production model must consume EXACTLY this feature vector. Any change
to the order or meaning of features requires bumping FEATURE_SCHEMA_VERSION
and retraining — a served model trained against a different schema is
rejected at load time (spec §22/§23).

Labels are NOT defined here deliberately: the target must come from
human-verified reconciliation outcomes on real data (spec §10), never from
the rule-based score and never from synthetic fixtures.
"""

from __future__ import annotations

FEATURE_SCHEMA_VERSION = "1.0.0"

# Ordered feature vector consumed by the model. All values are deterministic
# outputs of engine.metrics.compute_pair_metrics (None → feature absent).
FEATURE_ORDER: tuple[str, ...] = (
    "iou",                      # intersection / union area ratio
    "area_ratio",               # min(area) / max(area)
    "area_difference_m2",       # |area_a - area_b| (metres²)
    "centroid_distance_m",      # projected metric distance
    "hausdorff_distance_m",     # max boundary distance
    "boundary_displacement_m",  # mean sampled boundary offset
    "shape_similarity",         # convex-hull IoU
    "overlap_pct_of_cadastral", # intersection / area_a * 100
    "compactness_difference",   # |compactness_a - compactness_b|
    "perimeter_difference_m",   # |perimeter_a - perimeter_b|
    "vertex_count_diff",        # |vertices_a - vertices_b|
    "survey_number_match",      # bool / unknown
    "land_use_match",           # bool / unknown
    "classification_match",     # bool / unknown
)

# Attributes fields that feed the *_match features (kept in sync with
# engine.metrics._attribute_agreement).
ATTRIBUTE_FEATURE_FIELDS = ("survey_number", "land_use", "classification")


def features_from_pair_metrics(pair_metrics: dict) -> dict[str, float | None]:
    """Build the versioned feature dict from engine.metrics output.

    Unknown values (missing attribute fields, failed metric) map to None —
    the caller decides the imputation policy; nothing is silently guessed.
    """
    sm = pair_metrics.get("spatial_metrics", {})
    am = pair_metrics.get("attribute_metrics", {})
    vca = sm.get("vertex_count_cadastral")
    vcm = sm.get("vertex_count_municipal")
    return {
        "iou": sm.get("iou"),
        "area_ratio": sm.get("area_ratio"),
        "area_difference_m2": sm.get("area_difference_m2"),
        "centroid_distance_m": sm.get("centroid_distance_m"),
        "hausdorff_distance_m": sm.get("hausdorff_distance_m"),
        "boundary_displacement_m": sm.get("boundary_displacement_m"),
        "shape_similarity": sm.get("shape_similarity"),
        "overlap_pct_of_cadastral": sm.get("overlap_pct_of_cadastral"),
        "compactness_difference": sm.get("compactness_difference"),
        "perimeter_difference_m": sm.get("perimeter_difference_m"),
        "vertex_count_diff": (
            abs(vca - vcm) if vca is not None and vcm is not None else None
        ),
        "survey_number_match": am.get("survey_number_match"),
        "land_use_match": am.get("land_use_match"),
        "classification_match": am.get("classification_match"),
    }
