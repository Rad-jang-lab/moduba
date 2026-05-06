from __future__ import annotations

import math
from typing import Any

from iqa_result_schema import IQAResult, to_jsonable


def _safe_number(value: Any) -> Any:
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
    return value


def _context_value(context_payload: dict[str, Any], key: str) -> Any:
    histogram = context_payload.get("histogram")
    if key.startswith("histogram_") and isinstance(histogram, dict) and key in histogram:
        return histogram.get(key)
    if key in context_payload:
        return context_payload.get(key)
    if isinstance(histogram, dict) and key in histogram:
        return histogram.get(key)
    ssim_params = context_payload.get("ssim_params")
    if isinstance(ssim_params, dict) and key in ssim_params:
        return ssim_params.get(key)
    dicom = context_payload.get("dicom")
    if isinstance(dicom, dict):
        ref_ctx = dicom.get("reference")
        if isinstance(ref_ctx, dict) and key in ref_ctx:
            return ref_ctx.get(key)
    return None


def iqa_result_to_analysis_record(result: IQAResult, source: str | None = None) -> dict[str, Any]:
    payload = result.to_dict()
    metrics = dict(payload.get("metrics") or {})
    context = dict(payload.get("context") or {})
    warnings = list(payload.get("warnings") or [])

    record = {
        "analysis_type": "iqa",
        "metric_type": "iqa",
        "metric_mse": _safe_number(metrics.get("mse")),
        "metric_rmse": _safe_number(metrics.get("rmse")),
        "metric_psnr": _safe_number(metrics.get("psnr")),
        "metric_ssim": _safe_number(metrics.get("ssim")),
        "metric_hist_corr": _safe_number(metrics.get("hist_corr")),
        "context_input_mode": _context_value(context, "input_mode"),
        "context_scope": _context_value(context, "scope"),
        "context_image_shape": _context_value(context, "image_shape"),
        "context_data_range_policy": _context_value(context, "data_range_policy"),
        "context_data_range_used": _safe_number(_context_value(context, "data_range_used")),
        "context_bits_stored": _context_value(context, "bits_stored"),
        "context_photometric_interpretation": _context_value(context, "photometric_interpretation"),
        "context_rescale_slope": _context_value(context, "rescale_slope"),
        "context_rescale_intercept": _context_value(context, "rescale_intercept"),
        "context_window_center": _context_value(context, "window_center"),
        "context_window_width": _context_value(context, "window_width"),
        "context_photometric_inversion_applied": _context_value(context, "photometric_inversion_applied"),
        "context_original_reference_shape": _context_value(context, "original_reference_shape"),
        "context_original_target_shape": _context_value(context, "original_target_shape"),
        "context_compared_shape": _context_value(context, "compared_shape"),
        "context_shape_alignment_policy": _context_value(context, "shape_alignment_policy"),
        "context_roi_id": _context_value(context, "roi_id"),
        "context_roi_label": _context_value(context, "roi_label"),
        "context_roi_source": _context_value(context, "roi_source"),
        "context_roi_bbox": _context_value(context, "roi_bbox"),
        "context_roi_shape": _context_value(context, "roi_shape"),
        "context_roi_policy": _context_value(context, "roi_policy"),
        "context_histogram_bins": _context_value(context, "histogram_bins"),
        "context_histogram_range": _context_value(context, "histogram_range"),
        "context_histogram_normalized": _context_value(context, "histogram_normalized"),
        "context_histogram_range_policy": _context_value(context, "histogram_range_policy"),
        "context_histogram_corr": _safe_number(_context_value(context, "histogram_corr")),
        "context_histogram_distribution_hint": _context_value(context, "histogram_distribution_hint"),
        "context_histogram_reference_peak_bin": _context_value(context, "histogram_reference_peak_bin"),
        "context_histogram_target_peak_bin": _context_value(context, "histogram_target_peak_bin"),
        "context_histogram_summary": _context_value(context, "histogram_summary"),
        "reference_label": _context_value(context, "reference_label"),
        "target_label": _context_value(context, "target_label"),
        "warnings": warnings,
    }
    if source is not None:
        record["source"] = source
    return to_jsonable(record)


def flatten_iqa_result_for_export(result: IQAResult, source: str | None = None) -> dict[str, Any]:
    record = iqa_result_to_analysis_record(result, source=source)
    flat = dict(record)
    flat["warnings"] = ",".join(str(item) for item in record.get("warnings", []))
    if isinstance(flat.get("context_image_shape"), list):
        flat["context_image_shape"] = "x".join(str(v) for v in flat["context_image_shape"])
    return flat


def build_iqa_analysis_export_payload(result: IQAResult, source: str | None = None) -> dict[str, Any]:
    payload = result.to_dict()
    return {
        "analysis_type": "iqa",
        "source": source,
        "json": to_jsonable(payload),
        "flat": flatten_iqa_result_for_export(result, source=source),
    }
