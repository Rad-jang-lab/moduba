import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip("matplotlib")

from dicom_viewer import DicomViewer
from mtf_engine import calculate_matlab_reference_mtf


def test_matlab_imcrop_semantics_include_boundary_pixels():
    viewer = DicomViewer.__new__(DicomViewer)
    image = np.arange(100 * 100, dtype=np.float32).reshape(100, 100)
    roi, bounds = viewer._extract_roi_pixels(
        image,
        start=(10, 20),
        end=(20, 30),
        ensure_non_empty=True,
        semantics="matlab_imcrop",
    )
    assert bounds == (10, 20, 20, 30)
    assert roi.shape == (11, 11)


def test_default_crop_semantics_remain_end_exclusive():
    viewer = DicomViewer.__new__(DicomViewer)
    image = np.arange(100 * 100, dtype=np.float32).reshape(100, 100)
    roi, bounds = viewer._extract_roi_pixels(
        image,
        start=(10, 20),
        end=(20, 30),
        ensure_non_empty=True,
        semantics="default",
    )
    assert bounds == (10, 20, 20, 30)
    assert roi.shape == (10, 10)


def _make_vertical_edge_roi(size: int = 96) -> np.ndarray:
    roi = np.ones((size, size), dtype=np.float64) * 100.0
    roi[:, size // 2 :] = 400.0
    return roi


def _make_horizontal_edge_roi(size: int = 96) -> np.ndarray:
    roi = np.ones((size, size), dtype=np.float64) * 100.0
    roi[size // 2 :, :] = 400.0
    return roi


def test_matlab_reference_diagnostics_valid_for_columnwise_esf():
    roi = _make_vertical_edge_roi()
    result = calculate_matlab_reference_mtf(roi, pixel_spacing_mm=0.1988)
    diag = result.get("diagnostics", {}).get("matlab_esf_validity", {})
    assert result["calculation_status"] == "pass"
    assert diag.get("esf_axis_used") == "axis=0"
    assert diag.get("matlab_esf_axis_equivalent") is True
    assert diag.get("roi_is_valid_for_matlab_esf") is True
    assert diag.get("roi_validity_reason") == "ROI valid for MATLAB-style ESF extraction."


def test_matlab_reference_diagnostics_invalid_for_horizontal_edge():
    roi = _make_horizontal_edge_roi()
    result = calculate_matlab_reference_mtf(roi, pixel_spacing_mm=0.1988)
    diag = result.get("diagnostics", {}).get("matlab_esf_validity", {})
    assert result["calculation_status"] == "pass"
    assert diag.get("detected_edge_orientation") == "horizontal"
    assert diag.get("roi_is_valid_for_matlab_esf") is False
    assert (
        diag.get("roi_validity_reason")
        == "Invalid ROI for MATLAB-style ESF extraction: ROI orientation or crop does not match the MATLAB reference condition."
    )


def test_build_mtf_diagnostics_includes_roi_equivalence_comparison_block():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.path_var = type("PathVar", (), {"get": lambda self: "MTF LOW_70kVp_20mAs_001.DCM"})()
    phase1 = {
        "diagnostics": {
            "interpolation": {"pchip_available": False, "interpolation_method_used": "linear"},
            "gaussian_smoothing": {},
            "edge_orientation_and_esf_direction": {"edge_orientation_detected": "vertical"},
            "matlab_esf_validity": {"roi_is_valid_for_matlab_esf": True},
            "fft": {"nfft": 4096},
            "lsf": {"lsf_length": 32},
        },
        "mtf_curve": {"frequency_cy_per_pixel": [0.0, 0.1], "mtf": [1.0, 0.5]},
    }
    roi_pixels = np.ones((11, 11), dtype=np.float32)
    diagnostics = viewer._build_mtf_diagnostics(
        mtf_mode_id="matlab_reference",
        mtf_mode_label="MATLAB Reference",
        selected_roi_id="roi-1",
        bounds=(10, 20, 20, 30),
        spacing=(0.1988, 0.1988),
        roi_pixels=roi_pixels,
        dtype_before="float32",
        phase1=phase1,
        key_metrics={"mtf50": 0.1, "mtf10": 0.2},
        roi_start=(10.0, 20.0),
        roi_end=(20.0, 30.0),
        crop_semantics="matlab_imcrop",
    )
    block = diagnostics.get("roi_equivalence_comparison_block") or {}
    assert block.get("roi_definition_source") == "two_corner_points:start_end"
    assert block.get("roi_crop_bounds_used") == [10, 20, 20, 30]
    assert block.get("roi_shape_used") == [11, 11]
    assert block.get("matlab_imcrop_equivalence_status") == "equivalent"
    assert block.get("roi_summary_line") == "x0=10, y0=20, x1=20, y1=30, width=11, height=11"
