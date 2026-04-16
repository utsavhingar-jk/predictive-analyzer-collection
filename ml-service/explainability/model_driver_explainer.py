"""
Model-driver explainability helpers for tree-based models.

Returns top feature contributions for the prediction that was actually used.
For XGBoost models we prefer native ``pred_contribs`` because it reflects the
exact fitted model. SHAP is kept as a compatibility fallback.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np
import shap
import xgboost as xgb


def friendly_feature_name(feature_name: str, display_names: Mapping[str, str] | None = None) -> str:
    if display_names and feature_name in display_names:
        return display_names[feature_name]
    return feature_name.replace("_", " ").strip().title()


def summarize_drivers(drivers: list[dict], target_label: str) -> str:
    if not drivers:
        return f"ML prediction for {target_label} was generated from the trained model inputs."
    def _direction_text(driver: dict) -> str:
        return (
            "pushed the model output higher"
            if driver.get("direction") == "increases_prediction"
            else "pushed the model output lower"
        )
    lead = drivers[0]
    parts = [
        f"{lead['display_name']} ({lead['feature_value']:.3g}) {_direction_text(lead)}",
    ]
    if len(drivers) > 1:
        second = drivers[1]
        parts.append(
            f"{second['display_name']} ({second['feature_value']:.3g}) {_direction_text(second)}"
        )
    return f"Top model drivers for {target_label}: " + "; ".join(parts) + "."


def top_feature_drivers(
    model,
    scaler,
    features: np.ndarray,
    feature_names: list[str],
    *,
    top_n: int = 5,
    class_index: int | None = None,
    display_names: Mapping[str, str] | None = None,
) -> list[dict]:
    """
    Return top-N feature contributions for one prediction.

    ``contribution`` is in model-score space (for example, log-odds for
    classifiers and raw score for regressors), which makes it a faithful
    directional explanation of why the model moved the prediction.
    """
    scaled = scaler.transform(features)
    contrib = _extract_contributions(model, scaled, class_index=class_index)
    raw_features = features[0]
    n = min(len(feature_names), len(raw_features), len(contrib))

    drivers: list[dict] = []
    for idx in range(n):
        contribution = float(contrib[idx])
        drivers.append(
            {
                "feature_name": feature_names[idx],
                "display_name": friendly_feature_name(feature_names[idx], display_names),
                "feature_value": float(raw_features[idx]),
                "contribution": round(contribution, 6),
                "direction": "increases_prediction" if contribution >= 0 else "decreases_prediction",
                "direction_text": "pushed the model output higher"
                if contribution >= 0
                else "pushed the model output lower",
            }
        )

    ordered = sorted(drivers, key=lambda item: abs(item["contribution"]), reverse=True)[:top_n]
    for driver in ordered:
        driver.pop("direction_text", None)
    return ordered


def _extract_contributions(model, scaled: np.ndarray, class_index: int | None) -> np.ndarray:
    native = _xgboost_contributions(model, scaled, class_index=class_index)
    if native is not None:
        return native
    return _shap_contributions(model, scaled, class_index=class_index)


def _xgboost_contributions(model, scaled: np.ndarray, class_index: int | None) -> np.ndarray | None:
    if not hasattr(model, "get_booster"):
        return None
    try:
        booster = model.get_booster()
        contrib = booster.predict(
            xgb.DMatrix(scaled),
            pred_contribs=True,
            strict_shape=True,
        )
        arr = np.asarray(contrib)
        if arr.ndim == 3:
            chosen = class_index if class_index is not None else 0
            return arr[0, chosen, :-1]
        if arr.ndim == 2:
            return arr[0, :-1]
        if arr.ndim == 1:
            return arr[:-1]
    except Exception:
        return None
    return None


def _shap_contributions(model, scaled: np.ndarray, class_index: int | None) -> np.ndarray:
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(scaled)

    if isinstance(shap_values, list):
        chosen = class_index if class_index is not None else 0
        return np.asarray(shap_values[chosen])[0]

    arr = np.asarray(shap_values)
    if arr.ndim == 3:
        # Common shapes:
        #   (rows, features, classes)
        #   (classes, rows, features)
        if arr.shape[0] == scaled.shape[0]:
            chosen = class_index if class_index is not None else 0
            return arr[0, :, chosen]
        chosen = class_index if class_index is not None else 0
        return arr[chosen, 0, :]
    if arr.ndim == 2:
        return arr[0]
    return arr
