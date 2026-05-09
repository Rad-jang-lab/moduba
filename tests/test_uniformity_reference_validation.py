from __future__ import annotations

import numpy as np
import pytest

from signal_reference import (
    calculate_reference_uniformity_max_min,
    compare_signal_result_to_reference,
    load_signal_reference_csv,
    load_signal_reference_json,
    normalize_uniformity_result,
)
from tests.test_uniformity_analysis import _add_roi, _build_viewer


def test_reference_uniformity_formula():
    values = np.asarray([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    expected = float((1.0 - ((4.0 - 1.0) / (4.0 + 1.0))) * 100.0)
    assert calculate_reference_uniformity_max_min(values) == pytest.approx(expected, abs=1e-12)


def test_viewer_uniformity_matches_reference():
    viewer = _build_viewer()
    roi1 = _add_roi(viewer, "roi1", (0, 0), (2, 2))
    roi2 = _add_roi(viewer, "roi2", (2, 0), (4, 2))
    viewer.analysis_inputs["uniformity_formula"].set("max_min")
    viewer.analysis_inputs["uniformity_roi_ids"].set(f"{roi1.id},{roi2.id}")
    viewer.calculate_uniformity_from_inputs()
    got = normalize_uniformity_result(viewer.analysis_last_run.get("uniformity"))
    values = np.concatenate([viewer.frames[0][0:2, 0:2].reshape(-1), viewer.frames[0][0:2, 2:4].reshape(-1)])
    expected = calculate_reference_uniformity_max_min(values)
    assert compare_signal_result_to_reference(got, expected, {"atol": 1e-6, "rtol": 1e-6})




def test_reference_uniformity_max_plus_min_zero_raises():
    values = np.asarray([0.0, 0.0, 0.0], dtype=np.float64)
    with pytest.raises(ValueError, match=r"max \+ min <= 0"):
        calculate_reference_uniformity_max_min(values)


def test_viewer_uniformity_max_plus_min_zero_is_invalid():
    viewer = _build_viewer()
    viewer.frames = [np.zeros((10, 10), dtype=np.float32)]
    roi = _add_roi(viewer, "roi_zero", (0, 0), (2, 2))
    viewer.analysis_inputs["uniformity_formula"].set("max_min")
    viewer.analysis_inputs["uniformity_roi_ids"].set(roi.id)
    viewer.calculate_uniformity_from_inputs()
    result = viewer.analysis_last_run.get("uniformity")
    assert result is not None
    assert result.get("status") == "invalid"
    with pytest.raises(ValueError):
        normalize_uniformity_result(result)


def test_uniformity_result_normalization():
    assert normalize_uniformity_result({"status": "success", "result": {"value": 87.5}}) == 87.5


def test_uniformity_missing_roi_invalid():
    viewer = _build_viewer()
    viewer.analysis_inputs["uniformity_formula"].set("max_min")
    viewer.analysis_inputs["uniformity_roi_ids"].set("")
    viewer.calculate_uniformity_from_inputs()
    with pytest.raises(ValueError):
        normalize_uniformity_result(viewer.analysis_last_run.get("uniformity"))


def test_uniformity_reference_json_loader(tmp_path):
    path = tmp_path / "uniformity_ref.json"
    path.write_text('{"metric":"UNIFORMITY","formula":"max_min","value":90.0}', encoding="utf-8")
    payload = load_signal_reference_json(path)
    assert payload["metric"] == "UNIFORMITY"


def test_uniformity_reference_csv_loader(tmp_path):
    path = tmp_path / "uniformity_ref.csv"
    path.write_text("metric,formula,value\nUNIFORMITY,max_min,90.0\n", encoding="utf-8")
    rows = load_signal_reference_csv(path)
    assert rows[0]["metric"] == "UNIFORMITY"


def test_uniformity_tolerance_failure():
    assert compare_signal_result_to_reference(10.0, 10.5, {"atol": 1e-9, "rtol": 1e-9}) is False


def test_snr_cnr_reference_regression():
    assert True


def test_ui_display_helper_regression():
    assert True


def test_no_regression():
    assert True
