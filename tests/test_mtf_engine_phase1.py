import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from mtf_engine import (
    REJECTION_ANGLE,
    REJECTION_AUTO_FAIL_NO_MANUAL,
    REJECTION_CLIPPING,
    REJECTION_CONTRAST,
    REJECTION_NONLINEAR,
    calculate_matlab_reference_mtf,
    calculate_slanted_edge_mtf,
)


def _make_slanted_edge(size=96, angle_deg=6.0, low=100.0, high=500.0, noise_std=2.0, seed=7):
    rng = np.random.default_rng(seed)
    ys, xs = np.indices((size, size), dtype=np.float64)
    theta = np.deg2rad(angle_deg)
    normal = np.array([np.cos(theta), np.sin(theta)], dtype=np.float64)
    dist = (xs - size / 2.0) * normal[0] + (ys - size / 2.0) * normal[1]
    img = np.where(dist >= 0.0, high, low)
    if noise_std > 0:
        img = img + rng.normal(0.0, noise_std, size=img.shape)
    return img.astype(np.float64)


def test_phase1_mtf_pass_with_detected_edge():
    roi = _make_slanted_edge(angle_deg=5.0)
    result = calculate_slanted_edge_mtf(roi)

    assert result["calculation_status"] == "pass"
    assert result["rejection_reason"] is None
    assert result["mtf_curve"] is not None
    assert result["mtf50"] is not None
    assert result["mtf10"] is not None
    assert result["edge_angle_deg"] is not None
    assert 2.0 <= min(result["edge_angle_deg"] % 90, 90 - (result["edge_angle_deg"] % 90))


def test_rejects_when_auto_detection_fails_without_manual_geometry():
    roi = np.ones((64, 64), dtype=np.float64) * 123.0
    result = calculate_slanted_edge_mtf(roi)
    assert result["calculation_status"] == "reject"
    assert result["rejection_reason"] == REJECTION_AUTO_FAIL_NO_MANUAL
    assert result["mtf_curve"] is None


def test_rejects_for_too_small_edge_angle():
    roi = _make_slanted_edge(angle_deg=0.5)
    result = calculate_slanted_edge_mtf(roi)
    assert result["calculation_status"] == "reject"
    assert result["rejection_reason"] == REJECTION_ANGLE


def test_rejects_for_low_edge_contrast():
    roi = _make_slanted_edge(angle_deg=5.0, low=100.0, high=103.0, noise_std=4.0)
    result = calculate_slanted_edge_mtf(roi)
    assert result["calculation_status"] == "reject"
    assert result["rejection_reason"] == REJECTION_CONTRAST


def test_rejects_for_clipping_saturation():
    roi = _make_slanted_edge(angle_deg=5.0)
    roi[:, :20] = roi.min()
    roi[:, -20:] = roi.max()
    result = calculate_slanted_edge_mtf(roi)
    assert result["calculation_status"] == "reject"
    assert result["rejection_reason"] == REJECTION_CLIPPING


def test_rejects_for_obviously_nonlinear_metadata():
    roi = _make_slanted_edge(angle_deg=5.0)
    result = calculate_slanted_edge_mtf(roi, metadata={"voi_lut_applied": True})
    assert result["calculation_status"] == "reject"
    assert result["rejection_reason"] == REJECTION_NONLINEAR


def test_matlab_reference_mode_returns_curves_and_metrics():
    roi = _make_slanted_edge(size=96, angle_deg=8.0)
    result = calculate_matlab_reference_mtf(roi, pixel_spacing_mm=0.1988)

    assert result["calculation_status"] == "pass"
    assert isinstance(result["mtf50"], float)
    assert isinstance(result["mtf10"], float)
    assert result["mtf_curve"] is not None
    diag = result.get("diagnostics") or {}
    assert diag.get("fft", {}).get("window_function") == "hamming"
    assert diag.get("fft", {}).get("nfft") == 4096
    interpolation = diag.get("interpolation", {})
    assert interpolation.get("interpolation_method_used") in {"pchip", "linear", "linear_fallback_after_pchip_error"}
    assert isinstance(interpolation.get("pchip_available"), bool)
    if not interpolation.get("pchip_available"):
        assert interpolation.get("warning") == "PCHIP unavailable: using linear fallback; result may differ from MATLAB."
        assert interpolation.get("matlab_equivalence_flag") == "not fully MATLAB-equivalent"
    assert diag.get("gaussian_smoothing", {}).get("gaussian_kernel_size") == 5
    assert diag.get("gaussian_smoothing", {}).get("gaussian_boundary_mode") == "numpy_convolve_same_zero_padding"


def test_matlab_reference_mode_rejects_without_pixel_spacing():
    roi = _make_slanted_edge(size=96, angle_deg=8.0)
    result = calculate_matlab_reference_mtf(roi, pixel_spacing_mm=None)
    assert result["calculation_status"] == "reject"
