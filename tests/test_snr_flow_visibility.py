import sys
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "matplotlib" not in sys.modules:
    matplotlib_stub = types.ModuleType("matplotlib")
    pyplot_stub = types.ModuleType("matplotlib.pyplot")

    def _noop(*_args, **_kwargs):
        return None

    pyplot_stub.figure = _noop
    pyplot_stub.plot = _noop
    pyplot_stub.xlabel = _noop
    pyplot_stub.ylabel = _noop
    pyplot_stub.title = _noop
    pyplot_stub.tight_layout = _noop
    pyplot_stub.show = _noop
    matplotlib_stub.pyplot = pyplot_stub
    sys.modules["matplotlib"] = matplotlib_stub
    sys.modules["matplotlib.pyplot"] = pyplot_stub

import dicom_viewer
from dicom_viewer import DicomViewer


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _build_viewer() -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.frames = [np.ones((10, 10), dtype=np.float32) * 5.0]
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
        "uniformity_formula": DummyVar("max_min"),
        "uniformity_input_mode": DummyVar("selected_rois"),
        "uniformity_role_filter": DummyVar("signal"),
        "uniformity_roi_ids": DummyVar(""),
    }
    viewer.image_analysis_inputs = {}
    viewer.analysis_results = {
        "snr_preview": DummyVar(""),
        "snr_result": DummyVar(""),
        "cnr_preview": DummyVar(""),
        "cnr_result": DummyVar(""),
        "uniformity_preview": DummyVar(""),
        "uniformity_result": DummyVar(""),
    }
    viewer.analysis_last_run = {}
    viewer._analysis_action_buttons = {}
    viewer._uniformity_roi_listbox = None
    return viewer


def test_snr_invalid_path_is_saved_in_analysis_last_run(monkeypatch):
    monkeypatch.setattr(dicom_viewer, "messagebox", SimpleNamespace(showinfo=lambda *_a, **_k: None, showwarning=lambda *_a, **_k: None))
    viewer = _build_viewer()
    signal = viewer._append_persistent_measurement("roi", (1, 1), (5, 5), extra_meta={"roi_type": "free"}, roi_bounds_exclusive=True)
    noise = viewer._append_persistent_measurement("roi", (5, 1), (9, 5), extra_meta={"roi_type": "free"}, roi_bounds_exclusive=True)
    assert signal is not None and noise is not None
    viewer.analysis_inputs["snr_signal_roi_id"].set(signal.id)
    viewer.analysis_inputs["snr_background_roi_id"].set(noise.id)

    viewer.calculate_snr_from_inputs()

    snr = viewer.analysis_last_run["snr"]
    assert snr["status"] == "invalid"
    assert snr["reason"] == "noise std <= 0"
    assert snr["result"] is None
    assert "Invalid" in viewer.analysis_results["snr_result"].get()
    rows = viewer._build_analysis_last_run_rows()
    snr_rows = [row for row in rows if row["metric_name"] == "SNR"]
    assert len(snr_rows) == 1
    assert "[invalid]" in snr_rows[0]["formula_mode"]


def test_snr_missing_path_is_saved_in_analysis_last_run(monkeypatch):
    monkeypatch.setattr(dicom_viewer, "messagebox", SimpleNamespace(showinfo=lambda *_a, **_k: None, showwarning=lambda *_a, **_k: None))
    viewer = _build_viewer()

    viewer.calculate_snr_from_inputs()

    snr = viewer.analysis_last_run["snr"]
    assert snr["status"] == "missing"
    assert snr["result"] is None
    assert "Missing inputs" in viewer.analysis_results["snr_result"].get()


def test_cnr_invalid_and_missing_paths_are_saved_in_analysis_last_run(monkeypatch):
    monkeypatch.setattr(dicom_viewer, "messagebox", SimpleNamespace(showinfo=lambda *_a, **_k: None, showwarning=lambda *_a, **_k: None))
    viewer = _build_viewer()
    viewer.analysis_inputs["cnr_formula"].set("standard_noise")

    viewer.calculate_cnr_from_inputs()
    missing_cnr = viewer.analysis_last_run["cnr"]
    assert missing_cnr["status"] == "missing"
    assert "Missing inputs" in viewer.analysis_results["cnr_result"].get()

    target = viewer._append_persistent_measurement("roi", (1, 1), (5, 5), extra_meta={"roi_type": "free"}, roi_bounds_exclusive=True)
    reference = viewer._append_persistent_measurement("roi", (5, 1), (9, 5), extra_meta={"roi_type": "free"}, roi_bounds_exclusive=True)
    noise = viewer._append_persistent_measurement("roi", (1, 5), (5, 9), extra_meta={"roi_type": "free"}, roi_bounds_exclusive=True)
    assert target is not None and reference is not None and noise is not None
    viewer.analysis_inputs["cnr_target_roi_id"].set(target.id)
    viewer.analysis_inputs["cnr_reference_roi_id"].set(reference.id)
    viewer.analysis_inputs["cnr_noise_roi_id"].set(noise.id)

    viewer.calculate_cnr_from_inputs()
    invalid_cnr = viewer.analysis_last_run["cnr"]
    assert invalid_cnr["status"] == "invalid"
    assert invalid_cnr["result"] is None
    cnr_rows = [row for row in viewer._build_analysis_last_run_rows() if row["metric_name"] == "CNR"]
    assert len(cnr_rows) == 1
    assert "[invalid]" in cnr_rows[0]["formula_mode"]


def test_uniformity_missing_and_invalid_paths_are_saved_in_analysis_last_run(monkeypatch):
    monkeypatch.setattr(dicom_viewer, "messagebox", SimpleNamespace(showinfo=lambda *_a, **_k: None, showwarning=lambda *_a, **_k: None))
    viewer = _build_viewer()

    viewer.calculate_uniformity_from_inputs()
    missing_uniformity = viewer.analysis_last_run["uniformity"]
    assert missing_uniformity["status"] == "missing"
    assert "Missing ROI set" in viewer.analysis_results["uniformity_result"].get()

    zero_viewer = _build_viewer()
    zero_viewer.frames = [np.zeros((10, 10), dtype=np.float32)]
    zero_viewer.analysis_inputs["uniformity_formula"] = DummyVar("std_mean")
    roi = zero_viewer._append_persistent_measurement("roi", (1, 1), (5, 5), extra_meta={"roi_type": "free"}, roi_bounds_exclusive=True)
    assert roi is not None
    zero_viewer.analysis_inputs["uniformity_roi_ids"] = DummyVar(roi.id)
    zero_viewer.analysis_inputs["uniformity_input_mode"] = DummyVar("selected_rois")
    zero_viewer.analysis_inputs["uniformity_role_filter"] = DummyVar("signal")

    zero_viewer.calculate_uniformity_from_inputs()
    invalid_uniformity = zero_viewer.analysis_last_run["uniformity"]
    assert invalid_uniformity["status"] == "invalid"
    assert invalid_uniformity["result"]["value"] is None
    uniformity_rows = [row for row in zero_viewer._build_analysis_last_run_rows() if row["metric_name"] == "UNIFORMITY"]
    assert len(uniformity_rows) == 1
    assert "[invalid]" in uniformity_rows[0]["formula_mode"]
