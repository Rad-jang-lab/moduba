from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from iqa_metrics import calculate_histogram_correlation


def resolve_histogram_range(reference: np.ndarray, target: np.ndarray, policy: str = "data_range", data_range: float | None = None, explicit_range: tuple[float, float] | None = None) -> tuple[tuple[float, float], list[str]]:
    warnings: list[str] = []
    ref = np.asarray(reference, dtype=np.float64)
    tar = np.asarray(target, dtype=np.float64)
    mode = str(policy or "auto")
    if mode == "explicit":
        if explicit_range is None:
            raise ValueError("explicit histogram policy requires explicit_range")
        return (float(explicit_range[0]), float(explicit_range[1])), warnings
    if mode in {"data_range", "auto"} and data_range is not None and float(data_range) > 0:
        return (0.0, float(data_range)), warnings
    if mode in {"data_range", "auto"}:
        warnings.append("histogram_range_fallback_actual_union")
        mode = "actual_union"
    if mode == "actual_union":
        mn = float(np.nanmin([np.nanmin(ref), np.nanmin(tar)]))
        mx = float(np.nanmax([np.nanmax(ref), np.nanmax(tar)]))
        if mx <= mn:
            mx = mn + 1.0
            warnings.append("constant_histogram_range_adjusted")
        return (mn, mx), warnings
    raise ValueError(f"unsupported histogram range policy: {policy}")


def calculate_histogram_data(reference: np.ndarray, target: np.ndarray, bins: int = 256, hist_range: tuple[float, float] | None = None, normalize: bool = True) -> dict[str, Any]:
    ref = np.asarray(reference, dtype=np.float64)
    tar = np.asarray(target, dtype=np.float64)
    ref = ref[np.isfinite(ref)]
    tar = tar[np.isfinite(tar)]
    warnings: list[str] = []
    if ref.size == 0 or tar.size == 0:
        raise ValueError("reference/target histogram data is empty after finite filtering")
    if hist_range is None:
        hist_range = (float(min(ref.min(), tar.min())), float(max(ref.max(), tar.max())))
    if hist_range[1] <= hist_range[0]:
        hist_range = (hist_range[0], hist_range[0] + 1.0)
        warnings.append("constant_histogram_range_adjusted")
    ref_hist, bin_edges = np.histogram(ref, bins=bins, range=hist_range)
    tar_hist, _ = np.histogram(tar, bins=bins, range=hist_range)
    ref_count = int(ref_hist.sum())
    tar_count = int(tar_hist.sum())
    ref_values = ref_hist.astype(np.float64)
    tar_values = tar_hist.astype(np.float64)
    if normalize:
        ref_values = ref_values / (ref_count if ref_count else 1.0)
        tar_values = tar_values / (tar_count if tar_count else 1.0)
    corr = calculate_histogram_correlation(ref, tar, bins=bins, hist_range=hist_range)
    if float(np.std(ref)) == 0.0 or float(np.std(tar)) == 0.0:
        warnings.append("constant_histogram_input")
    if np.isnan(corr):
        warnings.append("constant_histogram_correlation_nan")
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    peak_ref = int(np.argmax(ref_values))
    peak_tar = int(np.argmax(tar_values))
    shift_hint = "aligned_distribution"
    if peak_tar > peak_ref:
        shift_hint = "target_shifted_brighter"
    elif peak_tar < peak_ref:
        shift_hint = "target_shifted_darker"
    return {
        "bins": int(bins),
        "hist_range": (float(hist_range[0]), float(hist_range[1])),
        "bin_edges": bin_edges.tolist(),
        "bin_centers": bin_centers.tolist(),
        "reference_hist": ref_values.tolist(),
        "target_hist": tar_values.tolist(),
        "normalized": bool(normalize),
        "reference_count": ref_count,
        "target_count": tar_count,
        "hist_corr": float(corr),
        "peak_bin_reference": peak_ref,
        "peak_bin_target": peak_tar,
        "distribution_shift_hint": shift_hint,
        "warnings": warnings,
    }


def calculate_histogram_overlay_series(reference: np.ndarray, target: np.ndarray, bins: int = 256, hist_range: tuple[float, float] | None = None, normalize: bool = True) -> dict[str, Any]:
    return calculate_histogram_data(reference, target, bins=bins, hist_range=hist_range, normalize=normalize)


def summarize_histogram_difference(histogram_result: Mapping[str, Any]) -> str:
    corr = histogram_result.get("hist_corr")
    hint = str(histogram_result.get("distribution_shift_hint", ""))
    if isinstance(corr, (int, float)) and corr < 0.5:
        base = "두 영상의 밝기 분포 차이가 큽니다."
    else:
        base = "두 영상의 밝기 분포는 전반적으로 유사합니다."
    if hint == "target_shifted_brighter":
        return f"{base} Target 영상이 더 높은 밝기 구간에 분포합니다."
    if hint == "target_shifted_darker":
        return f"{base} Target 영상이 더 낮은 밝기 구간에 분포합니다."
    return base


def build_histogram_context(**kwargs: Any) -> dict[str, Any]:
    return dict(kwargs)


def histogram_result_to_jsonable(result: Mapping[str, Any]) -> dict[str, Any]:
    return dict(result)


def build_histogram_preview_model(histogram_result: Mapping[str, Any], reference_label: str | None = None, target_label: str | None = None) -> dict[str, Any]:
    return {
        "title": "Histogram",
        "reference_label": reference_label,
        "target_label": target_label,
        "bins": histogram_result.get("bins"),
        "hist_range": histogram_result.get("hist_range"),
        "normalized": histogram_result.get("normalized"),
        "reference_peak_bin": histogram_result.get("peak_bin_reference"),
        "target_peak_bin": histogram_result.get("peak_bin_target"),
        "distribution_hint": histogram_result.get("distribution_shift_hint"),
        "hist_corr": histogram_result.get("hist_corr"),
        "summary": summarize_histogram_difference(histogram_result),
        "series": {
            "reference": histogram_result.get("reference_hist"),
            "target": histogram_result.get("target_hist"),
            "bin_centers": histogram_result.get("bin_centers"),
        },
        "warning_rows": [{"message": str(w)} for w in histogram_result.get("warnings", [])],
    }


def format_histogram_preview_text(preview_model: Mapping[str, Any]) -> str:
    rng = preview_model.get("hist_range")
    rng_text = f"{rng[0]} ~ {rng[1]}" if isinstance(rng, (list, tuple)) and len(rng) == 2 else "n/a"
    return (
        f"Histogram | Range: {rng_text} | Bins: {preview_model.get('bins')} | "
        f"Corr: {preview_model.get('hist_corr')} | 분포 차이: {preview_model.get('summary')}"
    )
