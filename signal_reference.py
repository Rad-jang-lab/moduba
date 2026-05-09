from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


def _to_1d_float_array(values: Any, *, field_name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        raise ValueError(f"{field_name} must not be empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{field_name} must contain only finite numeric values")
    return arr


def calculate_reference_snr(signal_values: Any, noise_values: Any) -> float:
    signal = _to_1d_float_array(signal_values, field_name="signal_values")
    noise = _to_1d_float_array(noise_values, field_name="noise_values")
    denominator = float(np.std(noise, ddof=0))
    if denominator <= 0.0:
        raise ValueError("noise std <= 0")
    return float(np.mean(signal) / denominator)


def calculate_reference_cnr(signal_values: Any, background_values: Any, noise_values: Any) -> float:
    signal = _to_1d_float_array(signal_values, field_name="signal_values")
    background = _to_1d_float_array(background_values, field_name="background_values")
    noise = _to_1d_float_array(noise_values, field_name="noise_values")
    denominator = float(np.std(noise, ddof=0))
    if denominator <= 0.0:
        raise ValueError("noise std <= 0")
    numerator = float(abs(np.mean(signal) - np.mean(background)))
    return float(numerator / denominator)


def normalize_snr_result(result: dict[str, Any] | None) -> float:
    if result is None:
        raise ValueError("SNR result is None")
    value = result.get("result")
    if value is None:
        raise ValueError(f"SNR result missing numeric value: status={result.get('status')!r}")
    if not isinstance(value, (int, float)):
        raise ValueError("SNR result value is not numeric")
    return float(value)


def normalize_cnr_result(result: dict[str, Any] | None) -> float:
    if result is None:
        raise ValueError("CNR result is None")
    value = result.get("result")
    if value is None:
        raise ValueError(f"CNR result missing numeric value: status={result.get('status')!r}")
    if not isinstance(value, (int, float)):
        raise ValueError("CNR result value is not numeric")
    return float(value)


def compare_signal_result_to_reference(result_value: float, reference_value: float, tolerance: dict[str, float]) -> bool:
    atol = float(tolerance.get("atol", 1e-6))
    rtol = float(tolerance.get("rtol", 1e-6))
    return bool(np.isclose(float(result_value), float(reference_value), atol=atol, rtol=rtol))


def load_signal_reference_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict):
        raise ValueError("reference json payload must be an object")
    return payload


def load_signal_reference_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def calculate_reference_uniformity_max_min(values: Any) -> float:
    arr = _to_1d_float_array(values, field_name="uniformity_values")
    max_val = float(np.max(arr))
    min_val = float(np.min(arr))
    denominator = max_val + min_val
    if denominator <= 0.0:
        raise ValueError("max + min <= 0")
    return float((1.0 - ((max_val - min_val) / denominator)) * 100.0)


def normalize_uniformity_result(result: dict[str, Any] | None) -> float:
    if result is None:
        raise ValueError("Uniformity result is None")
    payload = result.get("result")
    if not isinstance(payload, dict):
        raise ValueError("Uniformity result missing 'result' payload")
    value = payload.get("value")
    if value is None:
        raise ValueError(f"Uniformity result missing numeric value: status={result.get('status')!r}")
    if not isinstance(value, (int, float)):
        raise ValueError("Uniformity result value is not numeric")
    return float(value)



def normalize_mtf_result(result: dict[str, Any] | None, metric_key: str = "mtf50") -> float:
    if result is None:
        raise ValueError("MTF result is None")
    validity = str(result.get("calculation_validity", "")).strip().lower()
    status = str(result.get("calculation_status", "")).strip().lower()
    if validity == "invalid" or status in {"reject", "invalid", "error"}:
        raise ValueError(f"MTF result is invalid: status={status!r}, validity={validity!r}")
    candidates = []
    key_metrics = result.get("key_mtf_metrics")
    if isinstance(key_metrics, dict):
        candidates.append(key_metrics.get(metric_key))
    candidates.append(result.get(metric_key))
    value = next((item for item in candidates if isinstance(item, (int, float))), None)
    if value is None:
        raise ValueError(f"MTF result missing numeric metric: {metric_key}")
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError(f"MTF result metric is non-finite: {metric_key}={value!r}")
    return numeric



def normalize_mtf_curve(result: dict[str, Any] | None) -> dict[str, np.ndarray]:
    if result is None:
        raise ValueError("MTF result is None")
    validity = str(result.get("calculation_validity", "")).strip().lower()
    status = str(result.get("calculation_status", "")).strip().lower()
    if validity == "invalid" or status in {"reject", "invalid", "error"}:
        raise ValueError(f"MTF result is invalid: status={status!r}, validity={validity!r}")
    curve = result.get("mtf_curve")
    if not isinstance(curve, dict):
        raise ValueError("MTF result missing mtf_curve payload")
    freq = curve.get("frequency_cy_per_pixel", curve.get("x", []))
    values = curve.get("mtf", curve.get("y", []))
    freq_arr = np.asarray(freq, dtype=np.float64).reshape(-1)
    value_arr = np.asarray(values, dtype=np.float64).reshape(-1)
    if freq_arr.size == 0 or value_arr.size == 0:
        raise ValueError("MTF curve payload is empty")
    if freq_arr.size != value_arr.size:
        raise ValueError("MTF curve frequency/value size mismatch")
    if not np.all(np.isfinite(freq_arr)) or not np.all(np.isfinite(value_arr)):
        raise ValueError("MTF curve contains non-finite values")
    if np.any(np.diff(freq_arr) < 0):
        raise ValueError("MTF curve frequency is not sorted ascending")
    return {"frequency": freq_arr, "value": value_arr}


def compare_mtf_curve_to_reference(
    actual_curve: dict[str, np.ndarray],
    reference_curve: dict[str, np.ndarray],
    tolerance: dict[str, float],
) -> bool:
    atol = float(tolerance.get("atol", 1e-6))
    rtol = float(tolerance.get("rtol", 1e-6))
    af = np.asarray(actual_curve.get("frequency", []), dtype=np.float64)
    av = np.asarray(actual_curve.get("value", []), dtype=np.float64)
    rf = np.asarray(reference_curve.get("frequency", []), dtype=np.float64)
    rv = np.asarray(reference_curve.get("value", []), dtype=np.float64)
    if af.shape != rf.shape or av.shape != rv.shape:
        return False
    return bool(np.allclose(af, rf, atol=atol, rtol=rtol) and np.allclose(av, rv, atol=atol, rtol=rtol))
