from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np


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


def calculate_slanted_edge_mtf(
    roi: np.ndarray,
    manual_edge_geometry: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    oversampling: int = 4,
) -> Dict[str, Any]:
    """Phase-1 slanted-edge MTF calculation engine.

    Returns structured pass/reject result. On reject, MTF fields are omitted.
    """

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

    esf_x, esf_y = _build_esf(roi_arr, edge, oversampling=max(2, int(oversampling)))
    if esf_x.size < 16:
        return _reject(REJECTION_NO_EDGE, edge_angle_deg=edge.angle_deg)

    lsf = np.gradient(esf_y, esf_x)
    if not np.all(np.isfinite(lsf)):
        return _reject(REJECTION_NO_EDGE, edge_angle_deg=edge.angle_deg)

    freqs, mtf = _compute_mtf(esf_x, lsf)
    if freqs.size == 0 or mtf.size == 0:
        return _reject(REJECTION_NO_EDGE, edge_angle_deg=edge.angle_deg)

    mtf50 = _interpolate_crossing(freqs, mtf, 0.5)
    mtf10 = _interpolate_crossing(freqs, mtf, 0.1)

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
        "basic_notes": [
            "Phase 1 engine result.",
            f"Oversampling={max(2, int(oversampling))}x",
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


def _compute_mtf(esf_x: np.ndarray, lsf: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    dx = float(np.mean(np.diff(esf_x)))
    if not np.isfinite(dx) or dx <= 0:
        return np.array([]), np.array([])

    window = np.hanning(lsf.size)
    lsf_w = lsf * window
    spec = np.fft.rfft(lsf_w)
    mag = np.abs(spec)
    if mag.size == 0 or mag[0] == 0:
        return np.array([]), np.array([])

    mtf = mag / mag[0]
    freq = np.fft.rfftfreq(lsf.size, d=dx)
    return freq.astype(np.float64), mtf.astype(np.float64)


def _interpolate_crossing(freq: np.ndarray, mtf: np.ndarray, target: float) -> Optional[float]:
    if freq.size < 2:
        return None
    for i in range(1, mtf.size):
        y1 = mtf[i - 1]
        y2 = mtf[i]
        if y1 >= target >= y2:
            x1 = freq[i - 1]
            x2 = freq[i]
            if y1 == y2:
                return float(x1)
            t = (target - y1) / (y2 - y1)
            return float(x1 + t * (x2 - x1))
    return None


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
