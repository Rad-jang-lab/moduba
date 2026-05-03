from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

WARNING_MTF_PEAK = "MTF peak exceeds 1.0: possible sharpening or edge-enhancement detected."
WARNING_NONMONOTONIC_TAIL = (
    "Non-monotonic high-frequency tail detected: possible aliasing, sharpening, or noise-floor bias."
)
WARNING_LOW_SNR = "Low edge SNR: high-frequency MTF tail may be biased by noise floor."
WARNING_CLIPPING = "Edge plateau clipping detected: MTF interpretation may be biased by signal saturation."


def evaluate_mtf_integrity(
    phase1_result: Dict[str, Any],
    edge_snr: Optional[float] = None,
    clipping_detected: Optional[bool] = None,
) -> Dict[str, Any]:
    """Phase-2 integrity analysis for a precomputed slanted-edge MTF result.

    This function does not recompute MTF. It inspects provided outputs and emits
    warning findings for downstream QA grading.
    """

    warnings: List[str] = []
    reason_codes: List[str] = []
    notes: List[str] = [
        "Phase 2 integrity layer only; MTF not recomputed.",
        "No QA grade assignment in this phase.",
        "No IEC compliance decision in this phase.",
    ]

    peak_mtf_value: Optional[float] = None
    tail_behavior_status = "not_assessed"

    freq, mtf = _extract_curve(phase1_result.get("mtf_curve"))
    if freq.size and mtf.size:
        peak_mtf_value = float(np.max(mtf))

        if peak_mtf_value > 1.05:
            warnings.append(WARNING_MTF_PEAK)
            reason_codes.extend(["MTF_PEAK_GT_ONE", "POSSIBLE_SHARPENING"])

        tail_behavior_status, tail_codes = _assess_tail_behavior(freq, mtf)
        if tail_codes:
            warnings.append(WARNING_NONMONOTONIC_TAIL)
            reason_codes.extend(tail_codes)
    else:
        notes.append("MTF curve unavailable for integrity checks.")

    edge_snr_status, snr_codes, snr_warning = _assess_edge_snr(edge_snr)
    reason_codes.extend(snr_codes)
    if snr_warning:
        warnings.append(snr_warning)

    if clipping_detected is None:
        clipping_detected = bool(phase1_result.get("clipping_detected", False))
    clipping_interpretation_status, clipping_codes, clipping_warning = _assess_clipping(clipping_detected)
    reason_codes.extend(clipping_codes)
    if clipping_warning:
        warnings.append(clipping_warning)

    anomaly_count = _count_anomaly_categories(reason_codes)
    questionable_result = anomaly_count >= 2
    if questionable_result:
        reason_codes.append("RESULT_QUESTIONABLE")

    reason_codes = _ordered_unique(reason_codes)
    warnings = _ordered_unique(warnings)

    integrity_status = "warning" if warnings else "pass"

    anomaly_summary = {
        "warning_count": len(warnings),
        "reason_code_count": len(reason_codes),
        "anomaly_category_count": anomaly_count,
        "tail_points_evaluated": int(_tail_point_count(freq)),
    }

    return {
        "integrity_status": integrity_status,
        "warnings": warnings,
        "reason_codes": reason_codes,
        "peak_mtf_value": peak_mtf_value,
        "tail_behavior_status": tail_behavior_status,
        "edge_snr_status": edge_snr_status,
        "clipping_interpretation_status": clipping_interpretation_status,
        "questionable_result": questionable_result,
        "anomaly_summary": anomaly_summary,
        "integrity_notes": notes,
    }


def _extract_curve(curve: Any) -> Tuple[np.ndarray, np.ndarray]:
    if not isinstance(curve, dict):
        return np.array([]), np.array([])
    f = np.asarray(curve.get("frequency_cy_per_pixel", []), dtype=np.float64)
    m = np.asarray(curve.get("mtf", []), dtype=np.float64)
    if f.size == 0 or m.size == 0 or f.size != m.size:
        return np.array([]), np.array([])
    if not np.all(np.isfinite(f)) or not np.all(np.isfinite(m)):
        return np.array([]), np.array([])
    order = np.argsort(f)
    return f[order], m[order]


def _assess_tail_behavior(freq: np.ndarray, mtf: np.ndarray) -> Tuple[str, List[str]]:
    tail_idx = _tail_indices(freq)
    if tail_idx.size < 3:
        return "not_assessed", []

    tail = mtf[tail_idx]
    diffs = np.diff(tail)
    tail_span = float(np.max(tail) - np.min(tail)) if tail.size else 0.0

    positive_jumps = int(np.count_nonzero(diffs > 0.05))
    sign_changes = int(np.count_nonzero(np.signbit(diffs[1:]) != np.signbit(diffs[:-1]))) if diffs.size >= 2 else 0

    if tail_span > 0.05 and (positive_jumps >= 1 or sign_changes >= 3):
        return "nonmonotonic", ["NONMONOTONIC_TAIL", "POSSIBLE_ALIASING", "HIGH_FREQUENCY_NOISE_BIAS_RISK"]

    return "stable", []


def _tail_indices(freq: np.ndarray) -> np.ndarray:
    if freq.size < 8:
        return np.array([], dtype=int)
    max_freq = float(np.max(freq))
    if not np.isfinite(max_freq) or max_freq <= 0:
        return np.array([], dtype=int)
    nyquist_band = np.flatnonzero(freq >= (0.8 * max_freq))
    if nyquist_band.size >= 3:
        return nyquist_band.astype(int)
    n = freq.size
    start = int(np.floor(0.8 * n))
    return np.arange(start, n, dtype=int)


def _tail_point_count(freq: np.ndarray) -> int:
    return int(_tail_indices(freq).size)


def _assess_edge_snr(edge_snr: Optional[float]) -> Tuple[str, List[str], Optional[str]]:
    if edge_snr is None:
        return "not_assessed", ["EDGE_SNR_NOT_ASSESSED"], None
    if edge_snr < 20:
        return "low", ["EDGE_SNR_LOW", "HIGH_FREQUENCY_NOISE_BIAS_RISK"], WARNING_LOW_SNR
    if edge_snr < 30:
        return "borderline", ["EDGE_SNR_BORDERLINE", "HIGH_FREQUENCY_NOISE_BIAS_RISK"], WARNING_LOW_SNR
    return "ok", [], None


def _assess_clipping(clipping_detected: bool) -> Tuple[str, List[str], Optional[str]]:
    if clipping_detected:
        return "risk_detected", ["EDGE_CLIPPING_DETECTED"], WARNING_CLIPPING
    return "not_detected", [], None


def _ordered_unique(items: Sequence[Any]) -> List[Any]:
    seen = set()
    ordered = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _count_anomaly_categories(reason_codes: Sequence[str]) -> int:
    categories = set()
    rc = set(reason_codes)
    if {"MTF_PEAK_GT_ONE", "POSSIBLE_SHARPENING"} & rc:
        categories.add("peak")
    if {"NONMONOTONIC_TAIL", "POSSIBLE_ALIASING", "HIGH_FREQUENCY_NOISE_BIAS_RISK"} & rc:
        categories.add("tail_or_noise")
    if {"EDGE_SNR_LOW", "EDGE_SNR_BORDERLINE"} & rc:
        categories.add("snr")
    if "EDGE_CLIPPING_DETECTED" in rc:
        categories.add("clipping")
    return len(categories)
