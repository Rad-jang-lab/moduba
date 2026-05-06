from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from iqa_metrics import build_iqa_context, calculate_iqa_metrics
from iqa_result_schema import IQAResult


def _as_scalar(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def extract_dicom_iqa_metadata(ds: Any) -> dict[str, Any]:
    return {
        "bits_allocated": getattr(ds, "BitsAllocated", None),
        "bits_stored": getattr(ds, "BitsStored", None),
        "high_bit": getattr(ds, "HighBit", None),
        "pixel_representation": getattr(ds, "PixelRepresentation", None),
        "photometric_interpretation": getattr(ds, "PhotometricInterpretation", None),
        "rescale_slope": _as_scalar(getattr(ds, "RescaleSlope", None)),
        "rescale_intercept": _as_scalar(getattr(ds, "RescaleIntercept", None)),
        "window_center": _as_scalar(getattr(ds, "WindowCenter", None)),
        "window_width": _as_scalar(getattr(ds, "WindowWidth", None)),
        "source_identifier": str(getattr(ds, "SOPInstanceUID", None) or getattr(ds, "filename", None) or "unknown"),
    }


def apply_modality_transform_for_iqa(array: np.ndarray, slope: float | None = None, intercept: float | None = None) -> np.ndarray:
    slope_value = 1.0 if slope is None else float(slope)
    intercept_value = 0.0 if intercept is None else float(intercept)
    arr = np.asarray(array, dtype=np.float64)
    return arr * slope_value + intercept_value


def apply_window_for_iqa(array: np.ndarray, window_center: float, window_width: float, output_range: float = 255.0) -> np.ndarray:
    arr = np.asarray(array, dtype=np.float64)
    width = max(float(window_width), 1e-6)
    center = float(window_center)
    lower = center - (width / 2.0)
    upper = center + (width / 2.0)
    clipped = np.clip(arr, lower, upper)
    scaled = (clipped - lower) / (upper - lower)
    return scaled * float(output_range)


def normalize_photometric_for_iqa(array: np.ndarray, photometric_interpretation: str | None, enabled: bool = False) -> tuple[np.ndarray, bool]:
    arr = np.asarray(array, dtype=np.float64)
    photo = str(photometric_interpretation or "").upper()
    if photo == "MONOCHROME1" and enabled:
        return float(np.max(arr)) - arr, True
    return arr, False


def _crop_with_bbox(array: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = [int(v) for v in bbox]
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"invalid ROI bbox: {bbox}")
    if x0 < 0 or y0 < 0 or x1 > array.shape[1] or y1 > array.shape[0]:
        raise ValueError(f"ROI bbox out of range: {bbox} for shape={array.shape}")
    return array[y0:y1, x0:x1]


def _apply_roi_scope(array: np.ndarray, scope: str, options: Mapping[str, Any] | None = None) -> np.ndarray:
    opts = dict(options or {})
    if scope != "roi":
        return array
    bbox = opts.get("bbox")
    mask = opts.get("mask")
    if bbox is not None:
        return _crop_with_bbox(array, bbox)
    if mask is not None:
        mask_arr = np.asarray(mask)
        if mask_arr.shape != array.shape:
            raise ValueError(f"ROI mask shape mismatch: mask={mask_arr.shape}, image={array.shape}")
        return np.asarray(array, dtype=np.float64)[mask_arr.astype(bool)]
    raise ValueError("scope='roi' requires 'bbox' or 'mask' option")


def get_dicom_pixel_array_for_iqa(ds: Any, input_mode: str = "raw_dicom_pixel", options: Mapping[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    opts = dict(options or {})
    if not hasattr(ds, "pixel_array"):
        raise ValueError("DICOM-like object does not provide pixel_array")
    raw = np.asarray(ds.pixel_array)
    metadata = extract_dicom_iqa_metadata(ds)
    warnings: list[str] = []

    if input_mode == "raw_dicom_pixel":
        transformed = raw.astype(np.float64)
        policy = str(opts.get("data_range_policy", "bits"))
        data_range_used = opts.get("data_range_used")
        if policy == "bits" and metadata.get("bits_stored") is None:
            warnings.append("BitsStored missing: fallback data_range_policy=actual_union")
            policy = "actual_union"
    elif input_mode == "modality_lut":
        slope = metadata.get("rescale_slope")
        intercept = metadata.get("rescale_intercept")
        if slope is None:
            warnings.append("RescaleSlope missing: using slope=1")
        if intercept is None:
            warnings.append("RescaleIntercept missing: using intercept=0")
        transformed = apply_modality_transform_for_iqa(raw, slope=slope, intercept=intercept)
        policy = str(opts.get("data_range_policy", "actual_union"))
        data_range_used = opts.get("data_range_used")
    elif input_mode == "windowed_display":
        wc = metadata.get("window_center")
        ww = metadata.get("window_width")
        arr = raw.astype(np.float64)
        if wc is None or ww is None:
            warnings.append("WindowCenter/Width missing: using minmax fallback window")
            vmin = float(np.min(arr))
            vmax = float(np.max(arr))
            wc = (vmin + vmax) / 2.0
            ww = max(vmax - vmin, 1.0)
        output_range = float(opts.get("output_range", 255.0))
        transformed = apply_window_for_iqa(arr, float(wc), float(ww), output_range=output_range)
        policy = str(opts.get("data_range_policy", "explicit"))
        data_range_used = float(opts.get("data_range_used", output_range))
    else:
        raise ValueError(f"unsupported IQA input_mode: {input_mode}")

    invert_opt = bool(opts.get("photometric_invert", False))
    transformed, inversion_applied = normalize_photometric_for_iqa(
        transformed,
        metadata.get("photometric_interpretation"),
        enabled=invert_opt,
    )
    if str(metadata.get("photometric_interpretation") or "").upper() == "MONOCHROME1" and not inversion_applied:
        warnings.append("MONOCHROME1 without inversion option")

    scope = str(opts.get("scope", "full_image"))
    scoped_array = _apply_roi_scope(transformed, scope, opts)
    info = {
        **metadata,
        "input_mode": input_mode,
        "scope": scope,
        "data_range_policy": policy,
        "data_range_used": data_range_used,
        "dtype_before": str(raw.dtype),
        "dtype_after": str(np.asarray(scoped_array).dtype),
        "pixel_min": float(np.min(scoped_array)),
        "pixel_max": float(np.max(scoped_array)),
        "image_shape": tuple(int(v) for v in np.asarray(scoped_array).shape),
        "photometric_inversion_applied": inversion_applied,
        "warnings": warnings,
    }
    return np.asarray(scoped_array, dtype=np.float64), info


def build_dicom_iqa_context(
    ds: Any,
    input_mode: str,
    scope: str,
    data_range_policy: str,
    data_range_used: float,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    meta = extract_dicom_iqa_metadata(ds)
    opts = dict(options or {})
    return {
        "input_mode": input_mode,
        "scope": scope,
        "data_range_policy": data_range_policy,
        "data_range_used": float(data_range_used),
        "bits_stored": meta.get("bits_stored"),
        "histogram_bins": int(opts.get("histogram_bins", 256)),
        "histogram_range": opts.get("histogram_range"),
        "ssim_params": dict(opts.get("ssim_params") or {}),
        "dicom": meta,
    }


def prepare_dicom_iqa_input(ds: Any, input_mode: str = "raw_dicom_pixel", scope: str = "full_image", options: Mapping[str, Any] | None = None) -> dict[str, Any]:
    opts = dict(options or {})
    opts["scope"] = scope
    array, info = get_dicom_pixel_array_for_iqa(ds, input_mode=input_mode, options=opts)
    context = build_dicom_iqa_context(
        ds,
        input_mode=input_mode,
        scope=scope,
        data_range_policy=str(info["data_range_policy"]),
        data_range_used=float(info["data_range_used"] if info.get("data_range_used") is not None else np.nan),
        options=opts,
    )
    context.update(
        {
            "image_shape": info["image_shape"],
            "dtype_before": info["dtype_before"],
            "dtype_after": info["dtype_after"],
            "pixel_min": info["pixel_min"],
            "pixel_max": info["pixel_max"],
            "photometric_interpretation": info["photometric_interpretation"],
            "rescale_slope": info["rescale_slope"],
            "rescale_intercept": info["rescale_intercept"],
            "window_center": info["window_center"],
            "window_width": info["window_width"],
            "source_identifier": info["source_identifier"],
            "photometric_inversion_applied": info["photometric_inversion_applied"],
        }
    )
    return {"array": array, "context": context, "warnings": list(info["warnings"]) }


def calculate_dicom_iqa(
    reference_ds: Any,
    target_ds: Any,
    input_mode: str = "raw_dicom_pixel",
    scope: str = "full_image",
    options: Mapping[str, Any] | None = None,
) -> IQAResult:
    opts = dict(options or {})
    prepared_ref = prepare_dicom_iqa_input(reference_ds, input_mode=input_mode, scope=scope, options=opts)
    prepared_tar = prepare_dicom_iqa_input(target_ds, input_mode=input_mode, scope=scope, options=opts)

    ref_array = np.asarray(prepared_ref["array"], dtype=np.float64)
    tar_array = np.asarray(prepared_tar["array"], dtype=np.float64)
    if ref_array.shape != tar_array.shape:
        raise ValueError(f"reference/target shape mismatch after DICOM adapter: reference={ref_array.shape}, target={tar_array.shape}")

    iqa_options = {
        "input_mode": "dicom",
        "scope": scope,
        "data_range_policy": prepared_ref["context"]["data_range_policy"],
        "data_range_used": prepared_ref["context"].get("data_range_used"),
        "bits_stored": prepared_ref["context"].get("bits_stored"),
        "histogram_bins": int(opts.get("histogram_bins", 256)),
        "histogram_range": opts.get("histogram_range"),
        "ssim_params": dict(opts.get("ssim_params") or {}),
    }
    result = calculate_iqa_metrics(ref_array, tar_array, options=iqa_options)

    merged_context = result.context
    context_dict = build_iqa_context(
        ref_array,
        tar_array,
        input_mode="dicom",
        scope=scope,
        data_range_policy=result.context.data_range_policy,
        data_range_used=result.context.data_range_used,
        bits_stored=result.context.bits_stored,
        histogram_bins=result.context.histogram_bins,
        histogram_range=result.context.histogram_range,
        ssim_params=result.context.ssim_params,
    )
    warning_list = sorted(set(result.warnings + prepared_ref["warnings"] + prepared_tar["warnings"]))
    payload = result.to_dict()
    payload["context"]["dicom"] = {
        "reference": prepared_ref["context"],
        "target": prepared_tar["context"],
    }
    return IQAResult(metrics=result.metrics, context=merged_context, warnings=warning_list)
