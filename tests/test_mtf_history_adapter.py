import sys
import types
from pathlib import Path

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

from dicom_viewer import (
    DicomViewer,
    MTF_METRIC_EDGE_ANGLE_DEG,
    MTF_METRIC_EDGE_SNR,
    MTF_METRIC_INVALID,
    MTF_METRIC_MTF10,
    MTF_METRIC_MTF50,
    MTF_METRIC_NYQUIST_MTF,
    MTF_METRIC_ROI_HEIGHT_MM,
    MTF_METRIC_ROI_WIDTH_MM,
    ResultHistoryStore,
)


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value


def _build_viewer() -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.dataset = None
    viewer.frames = [np.arange(100, dtype=np.float32).reshape(10, 10)]
    viewer.current_frame = 0
    viewer.file_paths = []
    viewer.current_file_index = -1
    viewer.path_var = DummyVar("")
    viewer.measurement_mode = DummyVar("analysis")
    viewer.analysis_last_run = {}
    viewer.analysis_groups = {}
    viewer.study_sessions = {}
    viewer.active_study_id = ""
    viewer.active_group_id = ""
    viewer.result_history_store = ResultHistoryStore()
    viewer._refresh_result_history_table = lambda: None
    viewer._refresh_analysis_results_panel = lambda: None
    return viewer


def test_append_mtf_result_to_history_valid_appends_numeric_rows():
    viewer = _build_viewer()
    result = {
        "calculation_status": "ok",
        "calculation_validity": "valid",
        "iec_compliance": "noncompliant",
        "qa_grade": "B",
        "reason_codes": ["EDGE_SNR_BORDERLINE"],
        "warnings": ["EDGE_SNR_BORDERLINE"],
        "key_mtf_metrics": {
            "mtf50": 1.2,
            "mtf10": 2.1,
            "nyquist_mtf": 0.37,
            "frequency_unit": "cycles/mm",
        },
        "edge_angle_deg": 4.5,
        "edge_snr": 9.8,
        "roi_size_mm": {"width": 60.0, "height": 110.0},
    }
    context = {"image_id": "img-1", "frame_index": 0, "roi_id": "roi-1", "group_id": "g-1", "study_id": "s-1"}

    viewer.append_mtf_result_to_history(result, context)

    entries = viewer.result_history_store.entries()
    assert [entry.metric for entry in entries] == [
        MTF_METRIC_MTF50,
        MTF_METRIC_MTF10,
        MTF_METRIC_NYQUIST_MTF,
        MTF_METRIC_EDGE_ANGLE_DEG,
        MTF_METRIC_EDGE_SNR,
        MTF_METRIC_ROI_WIDTH_MM,
        MTF_METRIC_ROI_HEIGHT_MM,
    ]
    assert all(entry.measurement_type == "MTF" for entry in entries)
    assert entries[0].unit == "cycles/mm"
    assert entries[3].unit == "deg"
    assert entries[5].unit == "mm"
    assert entries[0].group_id == "g-1"
    assert entries[0].study_id == "s-1"
    assert "IEC=noncompliant" in entries[0].note
    assert entries[0].extra_payload is not None


def test_append_mtf_result_to_history_invalid_appends_single_failure_row():
    viewer = _build_viewer()
    result = {
        "calculation_status": "reject",
        "calculation_validity": "invalid",
        "reason_codes": ["EDGE_ANGLE_TOO_SMALL", "NONLINEAR_PIPELINE_DETECTED"],
    }
    context = {"image_id": "img-2", "frame_index": 0, "roi_id": "roi-x", "group_id": "g-2", "study_id": "s-2"}

    viewer.append_mtf_result_to_history(result, context)

    entries = viewer.result_history_store.entries()
    assert len(entries) == 1
    assert entries[0].metric == MTF_METRIC_INVALID
    assert entries[0].value is None
    assert "MTF rejected" in entries[0].note
    assert "EDGE_ANGLE_TOO_SMALL" in entries[0].note
