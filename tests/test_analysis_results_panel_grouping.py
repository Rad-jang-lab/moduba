import sys
import types
from pathlib import Path

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


def test_group_analysis_rows_for_panel_separates_metric_and_snapshot_sections():
    rows = [
        {
            "metric_name": "SNR",
            "formula_mode": "mean/std [success]",
            "roi_ids": ["r1", "r2"],
            "roles": ["signal", "noise"],
            "stats": {"status": "success"},
            "result_value": 3.5,
            "result_text": "Result: SNR=3.5",
        },
        {
            "metric_name": "ROI_STATS",
            "formula_mode": "ROI_STATS | single_roi_summary",
            "roi_ids": ["roi_a"],
            "roles": ["signal"],
            "stats": {"mean": 10.0},
            "result_value": 10.0,
            "result_text": "mean=10.0",
        },
    ]

    grouped = DicomViewer._group_analysis_rows_for_panel(rows)

    assert grouped[0]["category"] == "SECTION"
    assert grouped[0]["metric_name"] == "Results"
    assert grouped[1]["category"] == "METRIC"
    assert grouped[1]["metric_name"] == "SNR"
    assert grouped[2]["category"] == "SECTION"
    assert grouped[2]["metric_name"] == "ROI Stats"
    assert grouped[3]["category"] == "ROI_SNAPSHOT"
    assert grouped[3]["metric_name"] == "ROI_STATS"
