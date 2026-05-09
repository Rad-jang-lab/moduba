from __future__ import annotations

from typing import Any
import math


def _finite_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    return None


def _base_model(analysis_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("calculation_status", payload.get("status", "unknown")))
    validity = str(payload.get("calculation_validity", "valid" if status in {"success", "ok", "pass"} else "invalid"))
    return {
        "analysis_type": analysis_type,
        "status": status,
        "validity": validity,
        "metrics": {},
        "curves": {},
        "warnings": list(payload.get("warnings") or []),
        "reason_codes": list(payload.get("reason_codes") or []),
        "roi_info": {},
        "source_payload_keys": sorted(payload.keys()),
    }


def _add_metric(model: dict[str, Any], key: str, value: Any) -> None:
    numeric = _finite_number(value)
    if numeric is None:
        if value is not None:
            model["warnings"].append(f"non_finite_metric:{key}")
            model["reason_codes"].append("NON_FINITE_METRIC")
        return
    model["metrics"][key] = numeric


def normalize_analysis_result(analysis_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        raise ValueError(f"{analysis_type} payload is None")
    if not isinstance(payload, dict):
        raise ValueError("analysis payload must be a dict")
    t = str(analysis_type).strip().lower()
    model = _base_model(t, payload)

    if t == "snr":
        _add_metric(model, "snr", payload.get("result"))
        model["roi_info"] = {"signal_roi_id": payload.get("signal_roi_id"), "noise_roi_id": payload.get("noise_roi_id")}
    elif t == "cnr":
        _add_metric(model, "cnr", payload.get("result"))
        inputs = dict(payload.get("inputs") or {})
        model["roi_info"] = {
            "region_a_roi_id": inputs.get("region_a_roi_id"),
            "region_b_roi_id": inputs.get("region_b_roi_id"),
            "noise_roi_id": inputs.get("noise_roi_id"),
        }
    elif t == "uniformity":
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        _add_metric(model, "uniformity", result.get("value"))
        inputs = dict(payload.get("inputs") or {})
        model["roi_info"] = {"roi_ids": list(inputs.get("roi_ids") or []), "roi_count": inputs.get("roi_count")}
    elif t == "mtf":
        metrics = dict(payload.get("key_mtf_metrics") or {})
        for key, value in metrics.items():
            _add_metric(model, key, value)
        curve = payload.get("mtf_curve") if isinstance(payload.get("mtf_curve"), dict) else {}
        x = curve.get("frequency_cy_per_pixel")
        y = curve.get("mtf")
        if isinstance(x, list) and isinstance(y, list):
            model["curves"]["mtf"] = {"x": x, "y": y}
        model["roi_info"] = {"roi_size_mm": payload.get("roi_size_mm")}
    else:
        raise ValueError(f"unsupported analysis_type: {analysis_type}")

    return model


def normalize_analysis_last_run(analysis_last_run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in ("snr", "cnr", "uniformity", "mtf"):
        if key not in analysis_last_run:
            continue
        payload = analysis_last_run[key]
        if payload is None:
            raise ValueError(f"analysis_last_run[{key!r}] is None")
        result[key] = normalize_analysis_result(key, payload)
    return result
