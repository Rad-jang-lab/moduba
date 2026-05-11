import copy

import pytest

from analysis_history_store import load_analysis_history_records
from dicom_batch_normalized_history_adapter import (
    append_normalized_dicom_batch_execution_history_records,
    build_analysis_history_records_from_normalized_dicom_batch_execution_result,
    render_normalized_execution_history_adapter_text,
    validate_normalized_execution_history_adapter_records,
)
from dicom_viewer import DicomViewer


def _normalized_execution_result():
    return {
        "dicom_batch_execution_normalization_schema_version": 1,
        "normalization_id": "norm-1",
        "generated_at": "2026-05-10T00:00:00+00:00",
        "metadata": {},
        "source_run_id": "run-1",
        "item_count": 2,
        "task_count": 6,
        "normalized_task_count": 4,
        "skipped_task_count": 1,
        "error_task_count": 1,
        "items": [
            {
                "batch_item_normalization_schema_version": 1,
                "item_id": "item-a",
                "dicom_path": "/tmp/a.dcm",
                "task_normalizations": [
                    {"batch_task_normalization_schema_version": 1, "analysis_type": "snr", "source_task_status": "completed", "normalization_status": "normalized", "roi_ids": ["s", "n"], "skip_reason": None, "error": None, "normalized_result": {"analysis_type": "snr", "status": "ok", "validity": "valid", "metrics": {"snr": 10.0}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}}, "blocked_reasons": []},
                    {"batch_task_normalization_schema_version": 1, "analysis_type": "cnr", "source_task_status": "completed", "normalization_status": "normalized", "roi_ids": ["a", "b", "n"], "skip_reason": None, "error": None, "normalized_result": {"analysis_type": "cnr", "status": "ok", "validity": "valid", "metrics": {"cnr": 3.0}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}}, "blocked_reasons": []},
                    {"batch_task_normalization_schema_version": 1, "analysis_type": "uniformity", "source_task_status": "blocked", "normalization_status": "skipped", "roi_ids": ["u1"], "skip_reason": "blocked", "error": None, "normalized_result": None, "blocked_reasons": ["missing"]},
                    {"batch_task_normalization_schema_version": 1, "analysis_type": "mtf", "source_task_status": "error", "normalization_status": "error", "roi_ids": ["m1"], "skip_reason": None, "error": "calc fail", "normalized_result": None, "blocked_reasons": []},
                ],
            },
            {
                "batch_item_normalization_schema_version": 1,
                "item_id": "item-b",
                "dicom_path": "/tmp/b.dcm",
                "task_normalizations": [
                    {"batch_task_normalization_schema_version": 1, "analysis_type": "snr", "source_task_status": "blocked", "normalization_status": "skipped", "roi_ids": ["x"], "skip_reason": "blocked", "error": None, "normalized_result": None, "blocked_reasons": ["x"]},
                    {"batch_task_normalization_schema_version": 1, "analysis_type": "mtf", "source_task_status": "error", "normalization_status": "error", "roi_ids": ["y"], "skip_reason": None, "error": "bad", "normalized_result": None, "blocked_reasons": []},
                ],
            },
        ],
    }


def test_build_history_records_from_normalized_execution_creates_record_per_item():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert len(records) == 1


def test_build_history_records_from_normalized_execution_groups_multiple_analysis_results():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    results = records[0]["export_snapshot"]["results"]
    assert set(results.keys()) == {"snr", "cnr"}


def test_build_history_records_skips_items_without_normalized_tasks():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert all(r["metadata"]["item_id"] != "item-b" for r in records)


def test_build_history_records_preserves_metadata():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result(), metadata={"site": "A"})
    assert records[0]["metadata"]["history_source"] == "normalized_dicom_batch_execution_result"
    assert records[0]["metadata"]["site"] == "A"


def test_build_history_records_preserves_roi_ids_by_analysis():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert records[0]["metadata"]["roi_ids_by_analysis"]["snr"] == ["s", "n"]


def test_build_history_records_preserves_skipped_tasks_metadata():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert records[0]["metadata"]["skipped_task_count"] == 1


def test_build_history_records_preserves_error_tasks_metadata():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert records[0]["metadata"]["error_task_count"] == 1


def test_build_history_records_does_not_mutate_input():
    src = _normalized_execution_result()
    before = copy.deepcopy(src)
    build_analysis_history_records_from_normalized_dicom_batch_execution_result(src)
    assert src == before


def test_build_history_records_rejects_invalid_normalized_execution_schema():
    with pytest.raises(ValueError):
        build_analysis_history_records_from_normalized_dicom_batch_execution_result({"dicom_batch_execution_normalization_schema_version": 2, "items": []})


def test_build_history_records_rejects_unknown_normalization_status():
    src = _normalized_execution_result()
    src["items"][0]["task_normalizations"][0]["normalization_status"] = "mystery"
    with pytest.raises(ValueError):
        build_analysis_history_records_from_normalized_dicom_batch_execution_result(src)


def test_append_normalized_execution_history_records_round_trips_jsonl(tmp_path):
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    path = tmp_path / "history.jsonl"
    append_normalized_dicom_batch_execution_history_records(path, records)
    loaded = load_analysis_history_records(path)
    assert len(loaded) == len(records)


def test_render_normalized_execution_history_adapter_text_contains_counts():
    src = _normalized_execution_result()
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(src)
    text = render_normalized_execution_history_adapter_text(records, normalized_execution_result=src)
    assert "History Record Count" in text and "Skipped Items" in text


def test_validate_normalized_execution_history_adapter_records_rejects_invalid_records():
    with pytest.raises(ValueError):
        validate_normalized_execution_history_adapter_records([{"history_schema_version": 0}])


def test_adapter_does_not_auto_create_batch_qc_or_report():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert isinstance(records, list)


def test_adapter_does_not_call_calculation_logic_roi_resolver_or_pixel_read():
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert len(records) == 1


def test_viewer_build_history_records_from_normalized_execution_uses_current_normalized_result():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_normalized_dicom_batch_execution_result = _normalized_execution_result()
    out = viewer.build_analysis_history_records_from_normalized_execution_for_viewer()
    assert len(out) == 1


def test_viewer_build_history_records_from_normalized_execution_requires_current_result():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_normalized_dicom_batch_execution_result = None
    viewer.current_dicom_batch_execution_result = None
    with pytest.raises(ValueError):
        viewer.build_analysis_history_records_from_normalized_execution_for_viewer()


def test_viewer_append_normalized_execution_history_records_writes_file(tmp_path):
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_normalized_dicom_batch_execution_result = _normalized_execution_result()
    viewer._refresh_result_history_table = lambda: None
    out = viewer.append_normalized_execution_history_records_for_viewer(history_path=tmp_path / "h.jsonl")
    assert out is not None


def test_viewer_append_normalized_execution_history_records_dialog_cancel_returns_none(monkeypatch):
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_normalized_dicom_batch_execution_result = _normalized_execution_result()
    viewer._refresh_result_history_table = lambda: None
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_kwargs: "")
    assert viewer.append_normalized_execution_history_records_for_viewer(history_path=None) is None


def test_viewer_show_normalized_execution_history_adapter_preview_uses_text(monkeypatch):
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_normalized_dicom_batch_execution_result = _normalized_execution_result()
    viewer.root = object()

    class FakeTop:
        def __init__(self, *_args, **_kwargs):
            pass

        def title(self, *_args):
            pass

        def geometry(self, *_args):
            pass

    class FakeText:
        def __init__(self, *_args, **_kwargs):
            self.buf = ""

        def pack(self, **_kwargs):
            return None

        def insert(self, *_args):
            return None

        def configure(self, **_kwargs):
            return None

    monkeypatch.setattr("dicom_viewer.tk.Toplevel", FakeTop)
    monkeypatch.setattr("dicom_viewer.tk.Text", FakeText)
    text = viewer.show_normalized_execution_history_adapter_viewer()
    assert "History Record Count" in text
