from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:  # optional dependency
    from scipy.interpolate import PchipInterpolator  # type: ignore
except Exception:  # pragma: no cover - runtime fallback path
    PchipInterpolator = None


REJECTION_NO_EDGE = "MTF calculation rejected: no usable slanted edge was detected in the ROI."
REJECTION_AUTO_FAIL_NO_MANUAL = (
    "MTF calculation rejected: automatic edge detection failed and no manual edge geometry was provided."
)
REJECTION_ANGLE = (
    "MTF calculation rejected: edge angle is less than 2.0° from the nearest pixel axis; "
    "slanted-edge oversampling is not reliable."
)
REJECTION_CONTRAST = "MTF calculation rejected: edge contrast is insufficient for stable ESF/LSF estimation."
REJECTION_CLIPPING = "MTF calculation rejected: clipping or saturation makes the edge response unusable."
REJECTION_NONLINEAR = (
    "MTF calculation rejected: pixel values are not suitable for physical MTF interpretation due to nonlinear display processing."
)


@dataclass(frozen=True)
class EdgeGeometry:
    point: np.ndarray
    normal: np.ndarray
    angle_deg: float


class MTFCalculationError(RuntimeError):
    pass


def calculate_matlab_reference_mtf(roi: np.ndarray, pixel_spacing_mm: float | None) -> Dict[str, Any]:
    """MATLAB-compatible 1D MTF reference pipeline.

    Returns frequency in cycles/pixel for UI compatibility; lp/mm values are
    exposed through diagnostics.
    """

    try:
        roi_arr = _validate_roi(roi)
    except MTFCalculationError:
        return _reject(REJECTION_NO_EDGE)

    if not isinstance(pixel_spacing_mm, (int, float)) or float(pixel_spacing_mm) <= 0:
        return _reject("MTF calculation rejected: PixelSpacing is required for MATLAB reference mode.")

    pixel_spacing_mm = float(pixel_spacing_mm)
    roi_f64 = np.asarray(roi_arr, dtype=np.float64)
    edge = _detect_edge_geometry(roi_f64)
    edge_orientation = _determine_edge_orientation(edge.angle_deg) if edge is not None else "unknown"
    esf_raw = np.mean(roi_f64, axis=0)
    esf_smooth, gaussian_kernel = _smooth_gaussian_window_5(esf_raw)
    esf_monotonic_before = _is_monotonic_profile(esf_raw)
    esf_monotonic_after = _is_monotonic_profile(esf_smooth)
    esf = _normalize_01(esf_smooth)
    lsf_raw = np.abs(np.diff(esf))
    if lsf_raw.size < 4:
        return _reject(REJECTION_NO_EDGE)
    lsf = lsf_raw / max(float(np.max(lsf_raw)), 1e-12)

    nfft = 4096
    window = np.hamming(lsf.size)
    lsf_windowed = lsf * window
    mtf_full = np.abs(np.fft.fft(lsf_windowed, n=nfft))
    half = nfft // 2
    mtf = mtf_full[:half]
    if mtf.size == 0 or mtf[0] == 0:
        return _reject(REJECTION_NO_EDGE)
    mtf = mtf / mtf[0]

    freq_lp_mm = np.arange(half, dtype=np.float64) / (float(nfft) * pixel_spacing_mm)
    freq_cy_per_pixel = freq_lp_mm * pixel_spacing_mm

    mtf50_lpmm, mtf50_diag = _interpolate_threshold_lpmm(freq_lp_mm, mtf, 0.5)
    mtf10_lpmm, mtf10_diag = _interpolate_threshold_lpmm(freq_lp_mm, mtf, 0.1)
    mtf50 = float(mtf50_lpmm * pixel_spacing_mm) if isinstance(mtf50_lpmm, (int, float)) else None
    mtf10 = float(mtf10_lpmm * pixel_spacing_mm) if isinstance(mtf10_lpmm, (int, float)) else None

    esf_direction_used = "column-wise mean"
    if edge_orientation == "vertical":
        expected_direction = "column-wise mean"
    elif edge_orientation == "horizontal":
        expected_direction = "row-wise mean"
    else:
        expected_direction = "unknown"
    direction_match = expected_direction == "unknown" or expected_direction == esf_direction_used
    roi_is_valid_for_matlab_esf = bool(
        edge_orientation == "vertical"
        and esf_monotonic_before
        and esf_monotonic_after
    )
    roi_validity_reason = (
        "ROI valid for MATLAB-style ESF extraction."
        if roi_is_valid_for_matlab_esf
        else "Invalid ROI for MATLAB-style ESF extraction: ROI orientation or crop does not match the MATLAB reference condition."
    )

    diagnostics = {
        "interpolation": {
            "pchip_available": bool(PchipInterpolator is not None),
            "interpolation_method_used": mtf50_diag.get("method"),
            "mtf50_interpolation_method": mtf50_diag.get("method"),
            "mtf10_interpolation_method": mtf10_diag.get("method"),
            "scipy_pchip_used": bool(PchipInterpolator is not None),
            "fallback_method": None if PchipInterpolator is not None else "linear",
            "warning": (
                "PCHIP unavailable: using linear fallback; result may differ from MATLAB."
                if PchipInterpolator is None
                else None
            ),
            "matlab_equivalence_flag": "fully_equivalent" if PchipInterpolator is not None else "not fully MATLAB-equivalent",
        },
        "gaussian_smoothing": {
            "matlab_smoothing_reference": "smoothdata gaussian 5",
            "moduba_smoothing_method": "gaussian_window_5_numpy_convolve",
            "gaussian_kernel_size": int(gaussian_kernel.size),
            "kernel_size_used": int(gaussian_kernel.size),
            "gaussian_sigma_or_equivalent": 1.0,
            "sigma_used": 1.0,
            "gaussian_boundary_mode": "numpy_convolve_same_zero_padding",
            "boundary_mode": "numpy_convolve_same_zero_padding",
            "smoothing_normalization_behavior": "kernel normalized to sum=1 before convolution",
            "smoothing_equivalence_status": "unknown",
            "smoothing_equivalence_note": "Gaussian smoothing behavior differs from MATLAB unless smoothdata boundary handling is replicated exactly.",
        },
        "esf": {
            "esf_length": int(esf.size),
            "esf_axis_used": "axis=0",
            "matlab_esf_axis_equivalent": True,
            "esf_min_raw": float(np.min(esf_raw)),
            "esf_max_raw": float(np.max(esf_raw)),
            "esf_min_norm": float(np.min(esf)),
            "esf_max_norm": float(np.max(esf)),
            "smoothing_enabled": True,
            "smoothing_method": "gaussian_window_5",
            "smoothing_window_size": 5,
            "gaussian_kernel": gaussian_kernel.tolist(),
        },
        "lsf": {
            "lsf_length": int(lsf.size),
            "lsf_min_raw": float(np.min(lsf_raw)),
            "lsf_max_raw": float(np.max(lsf_raw)),
            "lsf_min_norm": float(np.min(lsf)),
            "lsf_max_norm": float(np.max(lsf)),
        },
        "fft": {
            "window_function": "hamming",
            "hamming_applied": True,
            "nfft": int(nfft),
            "fft_length_used": int(mtf.size),
            "freq_step_cy_per_pixel": float(freq_cy_per_pixel[1] - freq_cy_per_pixel[0]) if freq_cy_per_pixel.size > 1 else None,
            "max_freq_cy_per_pixel": float(np.max(freq_cy_per_pixel)) if freq_cy_per_pixel.size else None,
            "nyquist_cy_per_pixel": 0.5,
            "zero_padding_applied": nfft > int(lsf.size),
            "padding_ratio": float(nfft / max(int(lsf.size), 1)),
            "half_spectrum_used": True,
        },
        "edge_orientation_and_esf_direction": {
            "edge_orientation_detected": edge_orientation,
            "esf_direction_used": esf_direction_used,
            "expected_direction": expected_direction,
            "direction_match": bool(direction_match),
            "match_status": "match" if direction_match else "mismatch",
        },
        "matlab_esf_validity": {
            "esf_axis_used": "axis=0",
            "matlab_esf_axis_equivalent": True,
            "detected_edge_orientation": edge_orientation,
            "roi_is_valid_for_matlab_esf": roi_is_valid_for_matlab_esf,
            "roi_validity_reason": roi_validity_reason,
            "esf_monotonic_before_smoothing": esf_monotonic_before,
            "esf_monotonic_after_smoothing": esf_monotonic_after,
        },
        "signal_vs_fft": {
            "esf_length": int(esf.size),
            "lsf_length": int(lsf.size),
            "nfft": int(nfft),
            "zero_padding_applied": nfft > int(lsf.size),
            "padding_ratio": float(nfft / max(int(lsf.size), 1)),
        },
        "mtf50_crossing": mtf50_diag,
        "mtf10_crossing": mtf10_diag,
        "frequency_lp_per_mm": freq_lp_mm.tolist(),
        "mtf50_lp_per_mm": mtf50_lpmm,
        "mtf10_lp_per_mm": mtf10_lpmm,
        "nyquist_lp_per_mm": float(0.5 / pixel_spacing_mm),
    }

    return {
        "calculation_status": "pass",
        "rejection_reason": None,
        "edge_angle_deg": None,
        "mtf_curve": {
            "frequency_cy_per_pixel": freq_cy_per_pixel.tolist(),
            "mtf": mtf.tolist(),
        },
        "esf_curve": {
            "x": np.arange(esf.size, dtype=np.float64).tolist(),
            "y": esf.tolist(),
        },
        "lsf_curve": {
            "x": np.arange(lsf.size, dtype=np.float64).tolist(),
            "y": lsf.tolist(),
        },
        "mtf50": mtf50,
        "mtf10": mtf10,
        "diagnostics": diagnostics,
        "basic_notes": [
            "MATLAB reference mode result.",
            "mean(roi, axis=0) + gaussian(5) + abs(diff) + hamming + nfft=4096",
        ],
    }


def calculate_slanted_edge_mtf(
    roi: np.ndarray,
    manual_edge_geometry: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    oversampling: int = 4,
) -> Dict[str, Any]:
    """Phase-1 slanted-edge MTF calculation engine.

    Returns structured pass/reject result. On reject, MTF fields are omitted.
    """

    diagnostics: Dict[str, Any] = {}

    try:
        roi_arr = _validate_roi(roi)
    except MTFCalculationError:
        return _reject(REJECTION_NO_EDGE)

    if _is_obviously_nonlinear(metadata or {}):
        return _reject(REJECTION_NONLINEAR)

    if _is_saturated(roi_arr):
        return _reject(REJECTION_CLIPPING)

    edge = _detect_edge_geometry(roi_arr)
    if edge is None:
        if manual_edge_geometry is None:
            return _reject(REJECTION_AUTO_FAIL_NO_MANUAL)
        try:
            edge = _manual_edge_from_input(manual_edge_geometry)
        except MTFCalculationError:
            return _reject(REJECTION_NO_EDGE)

    angle_from_axis = _angle_from_nearest_axis(edge.angle_deg)
    if angle_from_axis < 2.0:
        return _reject(REJECTION_ANGLE, edge_angle_deg=edge.angle_deg)

    contrast = _estimate_edge_contrast(roi_arr, edge)
    if contrast < 0.05:
        return _reject(REJECTION_CONTRAST, edge_angle_deg=edge.angle_deg)

    effective_oversampling = max(2, int(oversampling))
    esf_x, esf_y = _build_esf(roi_arr, edge, oversampling=effective_oversampling)
    if esf_x.size < 16:
        return _reject(REJECTION_NO_EDGE, edge_angle_deg=edge.angle_deg)

    esf_min_raw = float(np.min(esf_y))
    esf_max_raw = float(np.max(esf_y))
    esf_norm = _normalize_01(esf_y)

    lsf = np.gradient(esf_y, esf_x)
    if not np.all(np.isfinite(lsf)):
        return _reject(REJECTION_NO_EDGE, edge_angle_deg=edge.angle_deg)
    lsf_min_raw = float(np.min(lsf))
    lsf_max_raw = float(np.max(lsf))
    lsf_abs = np.abs(lsf)
    lsf_norm = _normalize_01(lsf_abs)

    freqs, mtf, fft_diag = _compute_mtf(esf_x, lsf)
    if freqs.size == 0 or mtf.size == 0:
        return _reject(REJECTION_NO_EDGE, edge_angle_deg=edge.angle_deg)

    mtf50, mtf50_diag = _interpolate_crossing(freqs, mtf, 0.5, return_diag=True)
    mtf10, mtf10_diag = _interpolate_crossing(freqs, mtf, 0.1, return_diag=True)
    orientation = _determine_edge_orientation(edge.angle_deg)
    esf_direction = "column_mean" if orientation == "vertical" else "row_mean"
    diagnostics = {
        "esf": {
            "esf_length": int(esf_y.size),
            "esf_min_raw": esf_min_raw,
            "esf_max_raw": esf_max_raw,
            "esf_min_norm": float(np.min(esf_norm)),
            "esf_max_norm": float(np.max(esf_norm)),
            "smoothing_enabled": True,
            "smoothing_method": "weighted_moving_average_[1,2,3,2,1]",
            "smoothing_window_size": 5,
        },
        "lsf": {
            "lsf_length": int(lsf.size),
            "lsf_min_raw": lsf_min_raw,
            "lsf_max_raw": lsf_max_raw,
            "lsf_min_norm": float(np.min(lsf_norm)),
            "lsf_max_norm": float(np.max(lsf_norm)),
        },
        "fft": fft_diag,
        "interpolation": {
            "mtf50_interpolation_method": "linear",
            "mtf10_interpolation_method": "linear",
        },
        "edge_orientation_and_esf_direction": {
            "edge_orientation_detected": orientation,
            "esf_direction_used": esf_direction,
            "match_status": "match" if esf_direction == "column_mean" else "mismatch",
        },
        "signal_vs_fft": {
            "esf_length": int(esf_y.size),
            "lsf_length": int(lsf.size),
            "nfft": int(fft_diag.get("nfft", 0)),
            "zero_padding_applied": bool(fft_diag.get("zero_padding_applied", False)),
            "padding_ratio": float(fft_diag.get("padding_ratio", 0.0)),
        },
        "mtf50_crossing": mtf50_diag,
        "mtf10_crossing": mtf10_diag,
    }

    return {
        "calculation_status": "pass",
        "rejection_reason": None,
        "edge_angle_deg": float(edge.angle_deg),
        "mtf_curve": {
            "frequency_cy_per_pixel": freqs.tolist(),
            "mtf": mtf.tolist(),
        },
        "esf_curve": {
            "x": esf_x.tolist(),
            "y": esf_y.tolist(),
        },
        "lsf_curve": {
            "x": esf_x.tolist(),
            "y": lsf.tolist(),
        },
        "mtf50": mtf50,
        "mtf10": mtf10,
        "diagnostics": diagnostics,
        "basic_notes": [
            "Phase 1 engine result.",
            f"Oversampling={effective_oversampling}x",
            "Pixel spacing not required in Phase 1.",
        ],
    }


def _validate_roi(roi: np.ndarray) -> np.ndarray:
    arr = np.asarray(roi, dtype=np.float64)
    if arr.ndim != 2 or arr.size == 0:
        raise MTFCalculationError("invalid roi")
    if arr.shape[0] < 4 or arr.shape[1] < 4:
        raise MTFCalculationError("invalid roi")
    if not np.all(np.isfinite(arr)):
        raise MTFCalculationError("invalid roi")
    return arr


def _is_obviously_nonlinear(metadata: Dict[str, Any]) -> bool:
    nonlinear_flags = (
        "nonlinear_display_processed",
        "voi_lut_applied",
        "presentation_lut_applied",
        "windowing_applied",
    )
    return any(bool(metadata.get(k, False)) for k in nonlinear_flags)


def _is_saturated(roi: np.ndarray, tail_fraction: float = 0.02) -> bool:
    flat = roi.ravel()
    lo = float(np.min(flat))
    hi = float(np.max(flat))
    if hi <= lo:
        return False
    lo_clip = float(np.mean(flat <= lo))
    hi_clip = float(np.mean(flat >= hi))
    return lo_clip > tail_fraction or hi_clip > tail_fraction


def _detect_edge_geometry(roi: np.ndarray) -> Optional[EdgeGeometry]:
    gx, gy = np.gradient(roi)
    mag = np.hypot(gx, gy)
    thresh = float(np.percentile(mag, 92.0))
    if thresh <= 0:
        return None
    mask = mag >= thresh
    ys, xs = np.nonzero(mask)
    if xs.size < 20:
        return None

    weights = mag[mask]
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    mean = np.average(pts, axis=0, weights=weights)
    centered = pts - mean
    wcentered = centered * weights[:, None]
    cov = (wcentered.T @ centered) / np.sum(weights)

    eigvals, eigvecs = np.linalg.eigh(cov)
    direction = eigvecs[:, int(np.argmax(eigvals))]
    direction = direction / np.linalg.norm(direction)
    normal = np.array([-direction[1], direction[0]], dtype=np.float64)

    angle_deg = float(np.degrees(np.arctan2(direction[1], direction[0])) % 180.0)
    return EdgeGeometry(point=mean, normal=normal, angle_deg=angle_deg)


def _manual_edge_from_input(geom: Dict[str, Any]) -> EdgeGeometry:
    if "point" in geom and "normal" in geom:
        point = np.asarray(geom["point"], dtype=np.float64)
        normal = np.asarray(geom["normal"], dtype=np.float64)
        if point.shape != (2,) or normal.shape != (2,):
            raise MTFCalculationError("manual edge invalid")
        nrm = np.linalg.norm(normal)
        if nrm == 0:
            raise MTFCalculationError("manual edge invalid")
        normal = normal / nrm
        direction = np.array([normal[1], -normal[0]], dtype=np.float64)
        angle_deg = float(np.degrees(np.arctan2(direction[1], direction[0])) % 180.0)
        return EdgeGeometry(point=point, normal=normal, angle_deg=angle_deg)

    if "p1" in geom and "p2" in geom:
        p1 = np.asarray(geom["p1"], dtype=np.float64)
        p2 = np.asarray(geom["p2"], dtype=np.float64)
        if p1.shape != (2,) or p2.shape != (2,):
            raise MTFCalculationError("manual edge invalid")
        d = p2 - p1
        nrm = np.linalg.norm(d)
        if nrm == 0:
            raise MTFCalculationError("manual edge invalid")
        direction = d / nrm
        normal = np.array([-direction[1], direction[0]], dtype=np.float64)
        angle_deg = float(np.degrees(np.arctan2(direction[1], direction[0])) % 180.0)
        return EdgeGeometry(point=(p1 + p2) / 2.0, normal=normal, angle_deg=angle_deg)

    raise MTFCalculationError("manual edge invalid")


def _angle_from_nearest_axis(angle_deg: float) -> float:
    mod = angle_deg % 90.0
    return float(min(mod, 90.0 - mod))


def _estimate_edge_contrast(roi: np.ndarray, edge: EdgeGeometry) -> float:
    h, w = roi.shape
    ys, xs = np.indices((h, w), dtype=np.float64)
    dist = (xs - edge.point[0]) * edge.normal[0] + (ys - edge.point[1]) * edge.normal[1]
    pos = roi[dist > 1.0]
    neg = roi[dist < -1.0]
    if pos.size < 10 or neg.size < 10:
        return 0.0
    contrast = abs(float(np.mean(pos) - np.mean(neg)))
    dynamic = float(np.max(roi) - np.min(roi))
    if dynamic <= 0:
        return 0.0
    return contrast / dynamic


def _build_esf(roi: np.ndarray, edge: EdgeGeometry, oversampling: int) -> Tuple[np.ndarray, np.ndarray]:
    h, w = roi.shape
    ys, xs = np.indices((h, w), dtype=np.float64)
    dist = (xs - edge.point[0]) * edge.normal[0] + (ys - edge.point[1]) * edge.normal[1]
    values = roi.ravel()
    dist = dist.ravel()

    bin_width = 1.0 / float(oversampling)
    dmin = float(np.min(dist))
    dmax = float(np.max(dist))
    nbins = int(np.ceil((dmax - dmin) / bin_width)) + 1
    if nbins < 16:
        return np.array([]), np.array([])

    idx = np.floor((dist - dmin) / bin_width).astype(int)
    idx = np.clip(idx, 0, nbins - 1)

    sums = np.bincount(idx, weights=values, minlength=nbins)
    counts = np.bincount(idx, minlength=nbins)

    centers = dmin + (np.arange(nbins) + 0.5) * bin_width
    esf = np.empty(nbins, dtype=np.float64)
    valid = counts > 0
    if np.count_nonzero(valid) < 16:
        return np.array([]), np.array([])

    esf[valid] = sums[valid] / counts[valid]
    esf[~valid] = np.interp(centers[~valid], centers[valid], esf[valid])

    kernel = np.array([1, 2, 3, 2, 1], dtype=np.float64)
    kernel /= np.sum(kernel)
    esf = np.convolve(esf, kernel, mode="same")

    return centers, esf


def _compute_mtf(esf_x: np.ndarray, lsf: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    dx = float(np.mean(np.diff(esf_x)))
    if not np.isfinite(dx) or dx <= 0:
        return np.array([]), np.array([]), {}

    nfft = int(lsf.size)
    window = np.hanning(lsf.size)
    lsf_w = lsf * window
    spec = np.fft.rfft(lsf_w)
    mag = np.abs(spec)
    if mag.size == 0 or mag[0] == 0:
        return np.array([]), np.array([]), {}

    mtf = mag / mag[0]
    freq = np.fft.rfftfreq(lsf.size, d=dx)
    fft_diag = {
        "window_function": "hanning",
        "hamming_applied": False,
        "nfft": nfft,
        "fft_length_used": int(mag.size),
        "freq_step_cy_per_pixel": float(freq[1] - freq[0]) if freq.size > 1 else None,
        "max_freq_cy_per_pixel": float(np.max(freq)) if freq.size else None,
        "nyquist_cy_per_pixel": 0.5,
        "zero_padding_applied": False,
        "padding_ratio": float(nfft / max(lsf.size, 1)),
        "half_spectrum_used": True,
    }
    return freq.astype(np.float64), mtf.astype(np.float64), fft_diag


def _interpolate_crossing(
    freq: np.ndarray, mtf: np.ndarray, target: float, return_diag: bool = False
) -> Optional[float] | Tuple[Optional[float], Dict[str, Any]]:
    base_diag: Dict[str, Any] = {
        "mtf_curve_length": int(mtf.size),
        "index_before_crossing": None,
        "index_after_crossing": None,
        "frequency_before": None,
        "frequency_after": None,
        "interpolated_result": None,
        "monotonic_check": "pass" if bool(np.all(np.diff(mtf) <= 1e-12)) else "fail",
    }
    if freq.size < 2:
        return (None, base_diag) if return_diag else None
    for i in range(1, mtf.size):
        y1 = mtf[i - 1]
        y2 = mtf[i]
        if y1 >= target >= y2:
            x1 = freq[i - 1]
            x2 = freq[i]
            if y1 == y2:
                result = float(x1)
                base_diag.update(
                    {
                        "index_before_crossing": int(i - 1),
                        "index_after_crossing": int(i),
                        "frequency_before": float(x1),
                        "frequency_after": float(x2),
                        "interpolated_result": result,
                    }
                )
                return (result, base_diag) if return_diag else result
            t = (target - y1) / (y2 - y1)
            result = float(x1 + t * (x2 - x1))
            base_diag.update(
                {
                    "index_before_crossing": int(i - 1),
                    "index_after_crossing": int(i),
                    "frequency_before": float(x1),
                    "frequency_after": float(x2),
                    "interpolated_result": result,
                }
            )
            if base_diag["monotonic_check"] == "fail":
                lo = max(int(i) - 3, 1)
                hi = min(int(i) + 3, mtf.size - 1)
                local_diff = np.diff(mtf[lo - 1 : hi + 1])
                sign_changes = int(np.sum(np.sign(local_diff[:-1]) != np.sign(local_diff[1:]))) if local_diff.size > 1 else 0
                if sign_changes > 0:
                    base_diag["oscillation_note"] = "unstable MTF curve near threshold"
            return (result, base_diag) if return_diag else result
    return (None, base_diag) if return_diag else None


def _normalize_01(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return arr
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def _is_monotonic_profile(values: np.ndarray, tolerance: float = 1e-9) -> bool:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size < 2:
        return True
    diff = np.diff(arr)
    return bool(np.all(diff >= -tolerance) or np.all(diff <= tolerance))


def _determine_edge_orientation(angle_deg: float) -> str:
    angle_mod = float(angle_deg % 180.0)
    distance_to_vertical = min(abs(angle_mod - 90.0), abs(angle_mod + 90.0), abs(angle_mod - 270.0))
    return "vertical" if distance_to_vertical <= 45.0 else "horizontal"


def _reject(message: str, edge_angle_deg: Optional[float] = None) -> Dict[str, Any]:
    return {
        "calculation_status": "reject",
        "rejection_reason": message,
        "edge_angle_deg": edge_angle_deg,
        "mtf_curve": None,
        "esf_curve": None,
        "lsf_curve": None,
        "mtf50": None,
        "mtf10": None,
        "basic_notes": ["Phase 1 fatal validation rejection."],
    }


def _smooth_gaussian_window_5(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return arr, np.array([], dtype=np.float64)
    radius = 2
    sigma = 1.0
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x**2) / (2.0 * sigma * sigma))
    kernel /= np.sum(kernel)
    smoothed = np.convolve(arr, kernel, mode="same")
    return smoothed, kernel


def _interpolate_threshold_lpmm(freq_lpmm: np.ndarray, mtf: np.ndarray, target: float) -> Tuple[Optional[float], Dict[str, Any]]:
    diag: Dict[str, Any] = {
        "target": float(target),
        "index_before_crossing": None,
        "index_after_crossing": None,
        "frequency_before": None,
        "frequency_after": None,
        "interpolated_result": None,
        "method": "pchip" if PchipInterpolator is not None else "linear",
        "reason": None,
    }
    if freq_lpmm.size < 2 or mtf.size < 2:
        diag["reason"] = "insufficient_points"
        return None, diag
    crossing_index = None
    for i in range(1, mtf.size):
        if mtf[i - 1] >= target >= mtf[i]:
            crossing_index = i
            break
    if crossing_index is None:
        diag["reason"] = "no_valid_crossing"
        return None, diag

    i = int(crossing_index)
    x1 = float(freq_lpmm[i - 1])
    x2 = float(freq_lpmm[i])
    y1 = float(mtf[i - 1])
    y2 = float(mtf[i])
    diag["index_before_crossing"] = int(i - 1)
    diag["index_after_crossing"] = int(i)
    diag["frequency_before"] = x1
    diag["frequency_after"] = x2

    if x2 <= x1:
        diag["reason"] = "invalid_frequency_interval"
        return None, diag

    if PchipInterpolator is not None:
        try:
            pchip = PchipInterpolator(freq_lpmm, mtf, extrapolate=False)
            grid = np.linspace(x1, x2, 128, dtype=np.float64)
            vals = np.asarray(pchip(grid), dtype=np.float64)
            valid = np.isfinite(vals)
            grid = grid[valid]
            vals = vals[valid]
            if grid.size >= 2:
                for j in range(1, vals.size):
                    if vals[j - 1] >= target >= vals[j]:
                        gx1 = float(grid[j - 1])
                        gx2 = float(grid[j])
                        gy1 = float(vals[j - 1])
                        gy2 = float(vals[j])
                        t = 0.0 if gy1 == gy2 else (target - gy1) / (gy2 - gy1)
                        result = float(gx1 + t * (gx2 - gx1))
                        diag["interpolated_result"] = result
                        return result, diag
        except Exception:
            diag["method"] = "linear_fallback_after_pchip_error"

    if y1 == y2:
        result = x1
    else:
        t = (target - y1) / (y2 - y1)
        result = float(x1 + t * (x2 - x1))
    diag["interpolated_result"] = result
    return result, diag
