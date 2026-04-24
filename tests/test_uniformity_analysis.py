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

from dicom_viewer import DicomViewer
from domain_store import DomainStore


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _build_viewer() -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.frames = [np.arange(100, dtype=np.float32).reshape(10, 10)]
    viewer.current_frame = 0
    viewer.dataset = SimpleNamespace()
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer._uniformity_roi_listbox = None
    viewer._ensure_domain_store = lambda: None
    viewer._get_current_geometry_key = lambda: "g1"
    viewer._geometry_matches = lambda left, right: DicomViewer._geometry_matches(left, right)
    viewer._get_measurement_roi_role = DicomViewer._get_measurement_roi_role.__get__(viewer, DicomViewer)
    viewer._selector_measurements_for_current_frame = DicomViewer._selector_measurements_for_current_frame.__get__(viewer, DicomViewer)
    viewer._selector_measurements_for_image = DicomViewer._selector_measurements_for_image.__get__(viewer, DicomViewer)
    viewer._action_add_measurement_to_store = DicomViewer._action_add_measurement_to_store.__get__(viewer, DicomViewer)

    viewer.analysis_inputs = {
        "uniformity_formula": DummyVar("max_min"),
        "uniformity_input_mode": DummyVar("selected_rois"),
        "uniformity_role_filter": DummyVar("signal"),
        "uniformity_roi_ids": DummyVar(""),
    }
    viewer.analysis_results = {
        "uniformity_preview": DummyVar(""),
        "uniformity_result": DummyVar(""),
    }
    viewer.analysis_last_run = {}
    viewer._analysis_option_maps = {"roi": {}}
    return viewer


def _add_roi(viewer: DicomViewer, roi_id: str, start, end, role=None):
    from dicom_viewer import Measurement
    measurement = Measurement(
        id=roi_id,
        kind="roi",
        start=(float(start[0]), float(start[1])),
        end=(float(end[0]), float(end[1])),
        frame_index=0,
        geometry_key="g1",
        summary_text="",
        meta={"roi_type": "free", "role": role} if role else {"roi_type": "free"},
    )
    metrics = viewer.compute_measurement(measurement, viewer.frames[0])
    measurement.summary_text = metrics["summary"]
    measurement.meta = viewer._canonicalize_measurement_meta(measurement, metrics)
    viewer._action_add_measurement_to_store(measurement)
    return measurement


def test_uniformity_selected_roi_set_supports_two_formulas():
    viewer = _build_viewer()
    roi1 = _add_roi(viewer, "roi1", (0, 0), (2, 2))
    roi2 = _add_roi(viewer, "roi2", (2, 0), (4, 2))
    viewer.analysis_inputs["uniformity_roi_ids"].set(f"{roi1.id},{roi2.id}")

    values = np.concatenate([
        viewer.frames[0][0:2, 0:2].reshape(-1),
        viewer.frames[0][0:2, 2:4].reshape(-1),
    ])
    max_val = float(np.max(values))
    min_val = float(np.min(values))
    mean_val = float(np.mean(values))
    std_val = float(np.std(values))

    viewer.analysis_inputs["uniformity_formula"].set("max_min")
    viewer.calculate_uniformity_from_inputs()
    result_max_min = viewer.analysis_last_run["uniformity"]
    expected_max_min = (1.0 - ((max_val - min_val) / (max_val + min_val))) * 100.0
    assert np.isclose(result_max_min["result"]["value"], expected_max_min)
    assert result_max_min["inputs"]["roi_count"] == 2

    viewer.analysis_inputs["uniformity_formula"].set("std_mean")
    viewer.calculate_uniformity_from_inputs()
    result_std_mean = viewer.analysis_last_run["uniformity"]
    expected_std_mean = (1.0 - (std_val / mean_val)) * 100.0
    assert np.isclose(result_std_mean["result"]["value"], expected_std_mean)
    assert result_std_mean["stats"]["max"] == max_val
    assert result_std_mean["stats"]["min"] == min_val
    assert np.isclose(result_std_mean["stats"]["mean"], mean_val)
    assert np.isclose(result_std_mean["stats"]["std"], std_val)


def test_uniformity_role_group_input_mode():
    viewer = _build_viewer()
    _add_roi(viewer, "signal1", (0, 0), (2, 2), role="signal")
    _add_roi(viewer, "signal2", (2, 0), (4, 2), role="signal")
    _add_roi(viewer, "noise1", (0, 2), (2, 4), role="noise")

    viewer.analysis_inputs["uniformity_input_mode"].set("role_group")
    viewer.analysis_inputs["uniformity_role_filter"].set("signal")
    viewer.analysis_inputs["uniformity_formula"].set("max_min")
    viewer.calculate_uniformity_from_inputs()

    result = viewer.analysis_last_run["uniformity"]
    assert result["inputs"]["source"].startswith("role_group")
    assert result["inputs"]["roi_count"] == 2
    assert set(result["inputs"]["roi_ids"]) == {"signal1", "signal2"}
