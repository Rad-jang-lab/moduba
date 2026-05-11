import copy
import json
import types

import pytest

from dicom_batch_execution_normalization import (
    normalize_batch_task_execution_result,
    build_normalized_dicom_batch_execution_result,
    validate_normalized_dicom_batch_execution_result,
    render_normalized_dicom_batch_execution_result_text,
    export_normalized_dicom_batch_execution_result_to_json,
    export_normalized_dicom_batch_execution_result_to_csv,
    load_normalized_dicom_batch_execution_result,
)
from dicom_viewer import DicomViewer


def _task(analysis_type, status, payload=None, roi_ids=None, blocked_reasons=None, error=None):
    return {
        "batch_task_execution_result_schema_version": 1,
        "analysis_type": analysis_type,
        "status": status,
        "dicom_path": "/tmp/a.dcm",
        "roi_ids": roi_ids or [],
        "blocked_reasons": blocked_reasons or [],
        "raw_result_payload": payload,
        "error": error,
    }


def _execution_result():
    return {
        "dicom_batch_execution_result_schema_version": 1,
        "run_id": "run-1",
        "generated_at": "2026-05-10T00:00:00+00:00",
        "metadata": {},
        "execution_plan_id": "plan-1",
        "item_count": 1,
        "task_count": 7,
        "completed_task_count": 4,
        "blocked_task_count": 1,
        "not_executed_task_count": 1,
        "error_task_count": 1,
        "items": [
            {
                "batch_item_execution_result_schema_version": 1,
                "item_id": "item-1",
                "dicom_path": "/tmp/a.dcm",
                "dicom_status": "ok",
                "bounds_status": "valid",
                "is_executable_for_any_analysis": True,
                "task_results": [
                    _task("snr", "completed", {"result": 10.0, "signal_roi_id": "s", "noise_roi_id": "n"}, ["s", "n"]),
                    _task("cnr", "completed", {"result": 4.0, "inputs": {"region_a_roi_id": "a", "region_b_roi_id": "b", "noise_roi_id": "n"}}, ["a", "b", "n"]),
                    _task("uniformity", "completed", {"result": {"value": 0.88}, "inputs": {"roi_ids": ["u1", "u2"], "roi_count": 2}}, ["u1", "u2"]),
                    _task("mtf", "completed", {"key_mtf_metrics": {"MTF50": 1.2}, "mtf_curve": {"frequency_cy_per_pixel": [0.0, 0.5], "mtf": [1.0, 0.2]}, "roi_size_mm": [10, 10]}, ["m1"]),
                    _task("snr", "blocked", None, ["x"], ["missing_role"]),
                    _task("snr", "not_executed", None, ["x"]),
                    _task("snr", "error", None, ["x"], error="boom"),
                ],
            }
        ],
    }


def test_normalize_batch_task_execution_result_completed_snr():
    out = normalize_batch_task_execution_result(_task("snr", "completed", {"result": 10.0, "signal_roi_id": "s", "noise_roi_id": "n"}))
    assert out["normalization_status"] == "normalized"
    assert out["normalized_result"]["metrics"]["snr"] == 10.0


def test_normalize_batch_task_execution_result_completed_cnr():
    out = normalize_batch_task_execution_result(_task("cnr", "completed", {"result": 2.0, "inputs": {}}))
    assert out["normalization_status"] == "normalized"
    assert out["normalized_result"]["metrics"]["cnr"] == 2.0


def test_normalize_batch_task_execution_result_completed_uniformity():
    out = normalize_batch_task_execution_result(_task("uniformity", "completed", {"result": {"value": 0.7}, "inputs": {"roi_ids": ["a"]}}))
    assert out["normalization_status"] == "normalized"


def test_normalize_batch_task_execution_result_completed_mtf_with_curve():
    out = normalize_batch_task_execution_result(_task("mtf", "completed", {"key_mtf_metrics": {"MTF50": 1.0}, "mtf_curve": {"frequency_cy_per_pixel": [0], "mtf": [1]}}))
    assert out["normalization_status"] == "normalized"
    assert "mtf" in out["normalized_result"]["curves"]


def test_normalize_batch_task_execution_result_skips_blocked_task():
    out = normalize_batch_task_execution_result(_task("snr", "blocked", blocked_reasons=["a"]))
    assert out["normalization_status"] == "skipped"
    assert out["skip_reason"] == "blocked"


def test_normalize_batch_task_execution_result_skips_not_executed_task():
    out = normalize_batch_task_execution_result(_task("snr", "not_executed"))
    assert out["normalization_status"] == "skipped"


def test_normalize_batch_task_execution_result_handles_error_task():
    out = normalize_batch_task_execution_result(_task("snr", "error", error="bad"))
    assert out["normalization_status"] == "error"


def test_normalize_batch_task_execution_result_errors_on_completed_missing_payload():
    out = normalize_batch_task_execution_result(_task("snr", "completed", None))
    assert out["normalization_status"] == "error"


def test_normalize_batch_task_execution_result_errors_on_invalid_payload():
    out = normalize_batch_task_execution_result(_task("snr", "completed", "invalid"))
    assert out["normalization_status"] == "error"


def test_build_normalized_dicom_batch_execution_result_counts_statuses():
    out = build_normalized_dicom_batch_execution_result(_execution_result(), normalization_id="nid")
    assert out["normalized_task_count"] == 4
    assert out["skipped_task_count"] == 2
    assert out["error_task_count"] == 1


def test_build_normalized_dicom_batch_execution_result_does_not_mutate_input():
    src = _execution_result()
    before = copy.deepcopy(src)
    build_normalized_dicom_batch_execution_result(src)
    assert src == before


def test_validate_normalized_dicom_batch_execution_result_rejects_wrong_schema():
    with pytest.raises(ValueError):
        validate_normalized_dicom_batch_execution_result({"dicom_batch_execution_normalization_schema_version": 9, "items": []})


def test_render_normalized_dicom_batch_execution_result_text_contains_counts_and_tasks():
    text = render_normalized_dicom_batch_execution_result_text(build_normalized_dicom_batch_execution_result(_execution_result(), normalization_id="nid"))
    assert "normalized=" in text and "snr" in text


def test_export_normalized_dicom_batch_execution_result_to_json_round_trips(tmp_path):
    payload = build_normalized_dicom_batch_execution_result(_execution_result(), normalization_id="nid")
    path = tmp_path / "n.json"
    text = export_normalized_dicom_batch_execution_result_to_json(payload, path)
    assert json.loads(text)["normalization_id"] == "nid"
    assert load_normalized_dicom_batch_execution_result(path)["normalization_id"] == "nid"


def test_export_normalized_dicom_batch_execution_result_to_csv_exports_task_rows(tmp_path):
    payload = build_normalized_dicom_batch_execution_result(_execution_result(), normalization_id="nid")
    path = tmp_path / "n.csv"
    text = export_normalized_dicom_batch_execution_result_to_csv(payload, path)
    assert "analysis_type" in text
    assert text.count("\n") >= 8


def test_load_normalized_dicom_batch_execution_result_reads_valid_json(tmp_path):
    payload = build_normalized_dicom_batch_execution_result(_execution_result(), normalization_id="nid")
    path = tmp_path / "in.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_normalized_dicom_batch_execution_result(path)["normalization_id"] == "nid"


def test_load_normalized_dicom_batch_execution_result_rejects_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_normalized_dicom_batch_execution_result(path)


def test_viewer_build_normalized_dicom_batch_execution_result_uses_current_execution_result():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_dicom_batch_execution_result = _execution_result()
    out = viewer.build_normalized_dicom_batch_execution_result_for_viewer(normalization_id="nid")
    assert out["normalization_id"] == "nid"
    assert viewer.current_normalized_dicom_batch_execution_result["normalization_id"] == "nid"


def test_viewer_build_normalized_dicom_batch_execution_result_requires_current_execution_result():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_dicom_batch_execution_result = None
    with pytest.raises(ValueError):
        viewer.build_normalized_dicom_batch_execution_result_for_viewer()


def test_viewer_export_normalized_dicom_batch_execution_result_json_writes_file(tmp_path):
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_dicom_batch_execution_result = _execution_result()
    path = tmp_path / "out.json"
    text = viewer.export_normalized_dicom_batch_execution_result_json_for_viewer(path=str(path), normalization_id="nid")
    assert text is not None and path.exists()


def test_viewer_export_normalized_dicom_batch_execution_result_csv_writes_file(tmp_path):
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_dicom_batch_execution_result = _execution_result()
    path = tmp_path / "out.csv"
    text = viewer.export_normalized_dicom_batch_execution_result_csv_for_viewer(path=str(path), normalization_id="nid")
    assert text is not None and path.exists()


def test_viewer_normalized_execution_dialog_cancel_returns_none_without_mutation(monkeypatch):
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_dicom_batch_execution_result = _execution_result()
    baseline = copy.deepcopy(viewer.current_dicom_batch_execution_result)
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_kwargs: "")
    out = viewer.export_normalized_dicom_batch_execution_result_json_for_viewer(path=None)
    assert out is None
    assert viewer.current_dicom_batch_execution_result == baseline


def test_normalized_execution_result_does_not_auto_create_history_or_batch_qc():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.current_dicom_batch_execution_result = _execution_result()
    viewer.history_controller = types.SimpleNamespace(append=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("history should not be called")))
    viewer.build_normalized_dicom_batch_execution_result_for_viewer()


def test_normalized_execution_result_does_not_call_calculation_logic_or_roi_resolver(monkeypatch):
    monkeypatch.setattr("analysis_result_model.normalize_analysis_result", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("patched wrong target")))
    out = build_normalized_dicom_batch_execution_result(_execution_result())
    assert out["task_count"] == 7
