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
    viewer.persistent_measurements = []
    viewer.analysis_results_table = None
    viewer.analysis_last_run = {
        "snr": {
            "inputs": {"signal_roi_id": "sig1", "noise_roi_id": "noi1"},
            "factors": {"signal": {"roi_role": "signal"}, "noise": {"roi_role": "noise"}},
            "formula": "mean(Signal ROI) / std(Noise ROI)",
            "preview": "10.0 / 2.0",
            "result": 5.0,
        },
        "cnr": {
            "inputs": {"formula": "standard_noise", "region_a_roi_id": "a1", "region_b_roi_id": "b1", "noise_roi_id": "n1"},
            "factors": {"region_a": {"roi_role": "target"}, "region_b": {"roi_role": "reference"}, "noise": {"roi_role": "noise"}},
            "result": 3.2,
        },
        "uniformity": {
            "inputs": {"source": "selected_rois", "roi_count": 2, "roi_ids": ["u1", "u2"], "formula": "max_min", "formula_label": "U_max_min"},
            "stats": {"max": 20.0, "min": 5.0, "mean": 12.5, "std": 2.0, "pixel_count": 16},
            "result": {"value": 60.0, "formula": "max_min", "formula_label": "U_max_min"},
        },
        "line_profile": {
            "inputs": {"line_id": "line1"},
            "result": {"length_px": 24.0, "sample_count": 24},
        },
    }
    viewer.analysis_inputs = {
        "cnr_formula": DummyVar("standard_noise"),
    }
    viewer.analysis_results = {}
    return viewer


def test_analysis_export_payload_separates_user_schema_and_developer_meta():
    viewer = _build_viewer()
    roi = viewer._append_persistent_measurement(
        "roi",
        (1, 1),
        (3, 3),
        extra_meta={"roi_type": "free", "role": "signal"},
        roi_bounds_exclusive=True,
    )
    assert roi is not None
    roi.id = "roi_stats_1"

    payload = viewer._build_analysis_export_payload()

    assert "user_schema" in payload
    assert "developer_meta" in payload
    assert "rows" in payload["user_schema"]
    assert "analysis_last_run" in payload["developer_meta"]

    metric_names = {row["metric_name"] for row in payload["user_schema"]["rows"]}
    assert {"SNR", "CNR", "UNIFORMITY", "LINE_PROFILE_SUMMARY", "ROI_STATS"}.issubset(metric_names)

    for row in payload["user_schema"]["rows"]:
        assert "metric_name" in row
        assert "formula_mode" in row
        assert "roi_ids" in row
        assert "roles" in row
        assert "stats" in row
        assert "result_value" in row
