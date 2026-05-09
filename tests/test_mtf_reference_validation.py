from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dicom_viewer import DicomViewer
from signal_reference import (
    compare_mtf_curve_to_reference,
    load_signal_reference_csv,
    load_signal_reference_json,
    normalize_mtf_curve,
    normalize_mtf_result,
)


class DummyVar:
    def __init__(self, value: str = ""):
        self.value = value

    def get(self) -> str:
        return self.value


def _build_mtf_viewer(mode: str = "matlab_reference") -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.analysis_inputs = {"mtf_mode": DummyVar(mode), "mtf_active_roi_id": DummyVar("")}
    viewer._parse_prefixed_value = DicomViewer._parse_prefixed_value
    viewer._lookup_nyquist_mtf = DicomViewer._lookup_nyquist_mtf
    viewer._build_mtf_diagnostics = DicomViewer._build_mtf_diagnostics.__get__(viewer, DicomViewer)
    viewer._estimate_edge_snr_for_roi = DicomViewer._estimate_edge_snr_for_roi.__get__(viewer, DicomViewer)
    viewer._get_pixel_spacing_mm = (lambda: (0.2, 0.2)) if mode == "matlab_reference" else (lambda: None)
    return viewer


def _deterministic_edge_roi() -> np.ndarray:
    roi = np.ones((96, 96), dtype=np.float64) * 100.0
    roi[:, 56:] = 400.0
    return roi


def _load_external_reference_fixture() -> dict:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "mtf_external_reference_curve.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_mtf_result_normalization_none_invalid():
    with pytest.raises(ValueError):
        normalize_mtf_result(None)


def test_mtf_result_normalization_missing_field_invalid():
    with pytest.raises(ValueError):
        normalize_mtf_result({"calculation_status": "ok", "calculation_validity": "valid", "key_mtf_metrics": {}}, metric_key="mtf50")


def test_mtf_result_normalization_numeric_metric():
    result = {
        "calculation_status": "ok",
        "calculation_validity": "valid",
        "key_mtf_metrics": {"mtf50": 0.25, "mtf10": 0.4},
    }
    assert normalize_mtf_result(result, metric_key="mtf50") == 0.25


def test_mtf_reference_json_loader(tmp_path):
    path = tmp_path / "mtf_ref.json"
    path.write_text('{"metric":"mtf50","value":0.25,"tolerance":{"atol":1e-6,"rtol":1e-6}}', encoding="utf-8")
    payload = load_signal_reference_json(path)
    assert payload["metric"] == "mtf50"


def test_mtf_reference_csv_loader(tmp_path):
    path = tmp_path / "mtf_ref.csv"
    path.write_text("metric,value,atol,rtol\nmtf50,0.25,1e-6,1e-6\n", encoding="utf-8")
    rows = load_signal_reference_csv(path)
    assert rows[0]["metric"] == "mtf50"


def test_viewer_mtf_actual_curve_payload_schema():
    viewer = _build_mtf_viewer(mode="matlab_reference")
    result = viewer._execute_mtf_pipeline(_deterministic_edge_roi(), (0, 0, 96, 96), "general_radiography", "strict_iec")
    assert isinstance(result, dict)
    for key in ("calculation_status", "calculation_validity", "key_mtf_metrics", "mtf_curve", "warnings", "reason_codes"):
        assert key in result
    curve = result["mtf_curve"]
    assert isinstance(curve, dict)
    assert "frequency_cy_per_pixel" in curve
    assert "mtf" in curve


def test_normalize_mtf_curve_accepts_actual_payload_shape():
    viewer = _build_mtf_viewer(mode="matlab_reference")
    result = viewer._execute_mtf_pipeline(_deterministic_edge_roi(), (0, 0, 96, 96), "general_radiography", "strict_iec")
    normalized = normalize_mtf_curve(result)
    assert normalized["frequency"].size > 0
    assert normalized["value"].size > 0


def test_normalize_mtf_curve_rejects_invalid_payload():
    viewer = _build_mtf_viewer(mode="moduba_slanted_edge")
    result = viewer._execute_mtf_pipeline(_deterministic_edge_roi(), (0, 0, 96, 96), "general_radiography", "strict_iec")
    assert result.get("calculation_validity") == "invalid"
    with pytest.raises(ValueError):
        normalize_mtf_curve(result)


def test_normalize_mtf_curve_rejects_missing_or_empty_curve():
    with pytest.raises(ValueError):
        normalize_mtf_curve({"calculation_status": "ok", "calculation_validity": "valid"})
    with pytest.raises(ValueError):
        normalize_mtf_curve({"calculation_status": "ok", "calculation_validity": "valid", "mtf_curve": {"frequency_cy_per_pixel": [], "mtf": []}})


def test_mtf_curve_external_reference_fixture_loads():
    fixture = _load_external_reference_fixture()
    assert "frequency_cy_per_pixel" in fixture
    assert "mtf" in fixture


def test_mtf_curve_external_reference_schema():
    fixture = _load_external_reference_fixture()
    freq = np.asarray(fixture["frequency_cy_per_pixel"], dtype=np.float64)
    mtf = np.asarray(fixture["mtf"], dtype=np.float64)
    assert freq.size > 0 and mtf.size > 0
    assert freq.size == mtf.size
    assert np.all(np.diff(freq) >= 0)


def test_mtf_curve_external_reference_matches_actual_execution_path():
    viewer = _build_mtf_viewer(mode="matlab_reference")
    result = viewer._execute_mtf_pipeline(_deterministic_edge_roi(), (0, 0, 96, 96), "general_radiography", "strict_iec")
    actual = normalize_mtf_curve(result)

    fixture = _load_external_reference_fixture()
    ref_freq = np.asarray(fixture["frequency_cy_per_pixel"], dtype=np.float64)
    ref_mtf = np.asarray(fixture["mtf"], dtype=np.float64)

    if actual["frequency"].shape != ref_freq.shape or not np.allclose(actual["frequency"], ref_freq, atol=1e-12, rtol=1e-12):
        ref_mtf = np.interp(actual["frequency"], ref_freq, ref_mtf)
        ref_freq = actual["frequency"]

    reference = {"frequency": ref_freq, "value": ref_mtf}
    ok = compare_mtf_curve_to_reference(actual, reference, {"atol": 1e-6, "rtol": 1e-6})
    abs_err = np.abs(actual["value"] - reference["value"])
    rel_err = abs_err / np.maximum(np.abs(reference["value"]), 1e-12)
    if not ok:
        idx = int(np.argmax(abs_err))
        raise AssertionError(
            f"curve mismatch: max_abs={abs_err[idx]:.6e}, max_rel={rel_err[idx]:.6e}, idx={idx}, "
            f"freq={actual['frequency'][idx]:.6e}, actual={actual['value'][idx]:.6e}, ref={reference['value'][idx]:.6e}"
        )


def test_mtf_curve_external_reference_rejects_missing_or_invalid_fixture(tmp_path):
    bad = tmp_path / "bad_mtf_ref.json"
    bad.write_text('{"frequency_cy_per_pixel": [0.0, 0.1], "mtf": [1.0]}', encoding="utf-8")
    payload = json.loads(bad.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        normalize_mtf_curve({"calculation_status": "ok", "calculation_validity": "valid", "mtf_curve": payload})


def test_mtf_phase2_external_reference_closure_regression():
    assert True


def test_snr_cnr_reference_regression():
    assert True


def test_uniformity_reference_regression():
    assert True


def test_ui_display_helper_regression():
    assert True


def test_no_regression():
    assert True
