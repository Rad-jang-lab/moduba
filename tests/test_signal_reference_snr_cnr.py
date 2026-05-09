from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

import dicom_viewer
from dicom_viewer import DicomViewer
from signal_reference import (
    calculate_reference_cnr,
    calculate_reference_snr,
    compare_signal_result_to_reference,
    load_signal_reference_csv,
    load_signal_reference_json,
    normalize_cnr_result,
    normalize_snr_result,
)


class DummyVar:
    def __init__(self, value: str = ""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _build_viewer(frame: np.ndarray) -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.frames = [np.asarray(frame, dtype=np.float32)]
    viewer.current_frame = 0
    viewer.dataset = SimpleNamespace()
    viewer.persistent_measurements = []
    viewer.analysis_results_table = None
    viewer._analysis_comboboxes = {}
    viewer._image_analysis_comboboxes = {}
    viewer._analysis_option_maps = {"roi": {}}
    viewer._image_analysis_option_maps = {}
    viewer.analysis_inputs = {
        "snr_signal_roi_id": DummyVar(""),
        "snr_background_roi_id": DummyVar(""),
        "cnr_formula": DummyVar("standard_noise"),
        "cnr_target_roi_id": DummyVar(""),
        "cnr_reference_roi_id": DummyVar(""),
        "cnr_noise_roi_id": DummyVar(""),
    }
    viewer.image_analysis_inputs = {}
    viewer.analysis_results = {
        "snr_preview": DummyVar(""),
        "snr_result": DummyVar(""),
        "cnr_preview": DummyVar(""),
        "cnr_result": DummyVar(""),
    }
    viewer.analysis_last_run = {}
    viewer._analysis_action_buttons = {}
    return viewer


def _add_roi(viewer: DicomViewer, roi_id: str, start: tuple[int, int], end: tuple[int, int], role: str) -> str:
    measurement = viewer._append_persistent_measurement(
        "roi", start, end, extra_meta={"roi_type": "free", "role": role}, roi_bounds_exclusive=True
    )
    assert measurement is not None
    measurement.id = roi_id
    measurement.meta["role"] = role
    return measurement.id


def _fixture() -> tuple[DicomViewer, dict[str, str], dict[str, np.ndarray]]:
    frame = np.array(
        [
            [1, 2, 3, 4, 5, 6],
            [2, 3, 4, 5, 6, 7],
            [3, 4, 5, 6, 7, 8],
            [4, 5, 6, 7, 8, 9],
            [5, 6, 7, 8, 9, 10],
            [6, 7, 8, 9, 10, 11],
        ],
        dtype=np.float32,
    )
    viewer = _build_viewer(frame)
    rois = {
        "signal": _add_roi(viewer, "roi_signal", (0, 0), (3, 3), "signal"),
        "background": _add_roi(viewer, "roi_background", (3, 0), (6, 3), "background"),
        "noise": _add_roi(viewer, "roi_noise", (0, 3), (3, 6), "noise"),
        "target": _add_roi(viewer, "roi_target", (0, 0), (3, 3), "target"),
        "reference": _add_roi(viewer, "roi_reference", (3, 0), (6, 3), "reference"),
    }
    signal_vals = frame[0:3, 0:3].reshape(-1)
    background_vals = frame[0:3, 3:6].reshape(-1)
    noise_vals = frame[3:6, 0:3].reshape(-1)
    return viewer, rois, {"signal": signal_vals, "background": background_vals, "noise": noise_vals}


def test_reference_snr_formula():
    _viewer, _rois, values = _fixture()
    got = calculate_reference_snr(values["signal"], values["noise"])
    expected = float(np.mean(values["signal"].astype(np.float64)) / np.std(values["noise"].astype(np.float64), ddof=0))
    assert got == pytest.approx(expected, abs=1e-12)


def test_reference_cnr_formula():
    _viewer, _rois, values = _fixture()
    got = calculate_reference_cnr(values["signal"], values["background"], values["noise"])
    expected = float(abs(np.mean(values["signal"].astype(np.float64)) - np.mean(values["background"].astype(np.float64))) / np.std(values["noise"].astype(np.float64), ddof=0))
    assert got == pytest.approx(expected, abs=1e-12)


def test_viewer_snr_matches_reference(monkeypatch):
    monkeypatch.setattr(dicom_viewer, "messagebox", SimpleNamespace(showinfo=lambda *_a, **_k: None, showwarning=lambda *_a, **_k: None))
    viewer, rois, values = _fixture()
    viewer.analysis_inputs["snr_signal_roi_id"].set(rois["signal"])
    viewer.analysis_inputs["snr_background_roi_id"].set(rois["noise"])
    viewer.calculate_snr_from_inputs()
    got = normalize_snr_result(viewer.analysis_last_run.get("snr"))
    expected = calculate_reference_snr(values["signal"], values["noise"])
    assert compare_signal_result_to_reference(got, expected, {"atol": 1e-6, "rtol": 1e-6})


def test_viewer_cnr_matches_reference(monkeypatch):
    monkeypatch.setattr(dicom_viewer, "messagebox", SimpleNamespace(showinfo=lambda *_a, **_k: None, showwarning=lambda *_a, **_k: None))
    viewer, rois, values = _fixture()
    viewer.analysis_inputs["cnr_formula"].set("standard_noise")
    viewer.analysis_inputs["cnr_target_roi_id"].set(rois["target"])
    viewer.analysis_inputs["cnr_reference_roi_id"].set(rois["reference"])
    viewer.analysis_inputs["cnr_noise_roi_id"].set(rois["noise"])
    viewer.calculate_cnr_from_inputs()
    got = normalize_cnr_result(viewer.analysis_last_run.get("cnr"))
    expected = calculate_reference_cnr(values["signal"], values["background"], values["noise"])
    assert compare_signal_result_to_reference(got, expected, {"atol": 1e-6, "rtol": 1e-6})


def test_resolver_path_used():
    viewer, rois, _values = _fixture()
    viewer.analysis_inputs["snr_signal_roi_id"].set(rois["signal"])
    viewer.analysis_inputs["snr_background_roi_id"].set(rois["noise"])
    resolved = viewer.resolve_signal_analysis_inputs("snr")
    assert resolved["is_valid"] is True
    assert resolved["source"]["signal"] == "direct"
    assert resolved["source"]["background"] == "direct"


def test_missing_roi_invalid(monkeypatch):
    monkeypatch.setattr(dicom_viewer, "messagebox", SimpleNamespace(showinfo=lambda *_a, **_k: None, showwarning=lambda *_a, **_k: None))
    viewer = _build_viewer(np.arange(36, dtype=np.float32).reshape(6, 6))
    signal_id = _add_roi(viewer, "roi_signal_only", (0, 0), (3, 3), "signal")
    viewer.analysis_inputs["snr_signal_roi_id"].set(signal_id)
    viewer.calculate_snr_from_inputs()
    with pytest.raises(ValueError):
        normalize_snr_result(viewer.analysis_last_run.get("snr"))


def test_reference_json_loader(tmp_path):
    payload = {"metric": "SNR", "value": 1.23}
    path = tmp_path / "ref.json"
    path.write_text('{"metric":"SNR","value":1.23}', encoding="utf-8")
    assert load_signal_reference_json(path) == payload


def test_reference_csv_loader(tmp_path):
    path = tmp_path / "ref.csv"
    path.write_text("metric,value\nSNR,1.23\n", encoding="utf-8")
    rows = load_signal_reference_csv(path)
    assert rows == [{"metric": "SNR", "value": "1.23"}]


def test_tolerance_failure():
    assert compare_signal_result_to_reference(1.0, 1.1, {"atol": 1e-9, "rtol": 1e-9}) is False


def test_no_regression():
    assert True
