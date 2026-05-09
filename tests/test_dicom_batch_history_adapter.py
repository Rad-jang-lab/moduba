from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from analysis_history_store import load_analysis_history_records
from dicom_batch_history_adapter import *
from dicom_viewer import DicomViewer
from tests.test_analysis_threshold_integration import _cfg


def _result(task_results=None):
    return {
        "dicom_batch_execution_result_schema_version": 1,
        "run_id": "run1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "metadata": {},
        "execution_plan_id": "ep1",
        "item_count": 1,
        "task_count": len(task_results or []),
        "completed_task_count": 0,
        "blocked_task_count": 0,
        "not_executed_task_count": 0,
        "error_task_count": 0,
        "items": [{"batch_item_execution_result_schema_version": 1, "item_id": "i1", "dicom_path": "/tmp/a.dcm", "dicom_status": "valid", "bounds_status": "pass", "is_executable_for_any_analysis": True, "task_results": task_results or []}],
    }


def _task(status="completed", analysis_type="snr", payload=None):
    return {"batch_task_execution_result_schema_version": 1, "analysis_type": analysis_type, "status": status, "dicom_path": "/tmp/a.dcm", "roi_ids": ["r1"], "blocked_reasons": [], "raw_result_payload": payload, "error": None}


def test_completed_batch_task_normalizes_to_history_record():
    r = _result([_task(payload={"result": 5.0, "status": "ok"})])
    rec = build_analysis_history_records_from_dicom_batch_execution_result(r)[0]
    assert rec["export_snapshot"]["results"]["snr"]["metrics"]["snr"] == 5.0

def test_batch_execution_item_groups_multiple_tasks_into_one_history_record():
    r = _result([_task("completed", "snr", {"result": 5.0, "status": "ok"}), _task("completed", "cnr", {"result": 3.0, "status": "ok", "inputs": {}})])
    rec = build_analysis_history_records_from_dicom_batch_execution_result(r)
    assert len(rec) == 1 and {"snr", "cnr"}.issubset(set(rec[0]["export_snapshot"]["results"].keys()))

def test_error_task_becomes_invalid_normalized_result():
    t = _task("error", "snr", None); t["error"] = "boom"
    out = normalize_dicom_batch_task_execution_result(t)
    assert out["validity"] == "invalid" and "BATCH_TASK_ERROR" in out["reason_codes"] and out["metrics"] == {}

def test_blocked_task_becomes_invalid_normalized_result():
    t = _task("blocked", "snr", None); t["blocked_reasons"]=["roi_out_of_bounds"]
    out = normalize_dicom_batch_task_execution_result(t)
    assert out["validity"] == "invalid" and any("roi_out_of_bounds" in w for w in out["warnings"])

def test_not_executed_task_becomes_invalid_normalized_result():
    assert normalize_dicom_batch_task_execution_result(_task("not_executed", "snr", None))["validity"] == "invalid"

def test_completed_task_without_payload_becomes_invalid():
    assert "BATCH_TASK_MISSING_RAW_RESULT_PAYLOAD" in normalize_dicom_batch_task_execution_result(_task("completed", "snr", None))["reason_codes"]

def test_normalization_error_does_not_drop_entire_item():
    r = _result([_task("completed", "snr", {"result": "bad", "status": "ok"}), _task("completed", "cnr", {"result": 1.0, "status": "ok", "inputs": {}})])
    rec = build_analysis_history_records_from_dicom_batch_execution_result(r)[0]
    assert "snr" in rec["export_snapshot"]["results"] and "cnr" in rec["export_snapshot"]["results"]

def test_adapter_preserves_batch_metadata_in_history_record():
    rec = build_analysis_history_records_from_dicom_batch_execution_result(_result([_task(payload={"result": 1.0, "status": "ok"})]))[0]
    md = rec["metadata"]
    assert md["batch_run_id"] == "run1" and md["execution_plan_id"] == "ep1" and md["item_id"] == "i1" and md["dicom_path"] == "/tmp/a.dcm"

def test_adapter_does_not_mutate_execution_result_input():
    r = _result([_task(payload={"result": 1.0, "status": "ok"})]); b=copy.deepcopy(r)
    _ = build_analysis_history_records_from_dicom_batch_execution_result(r)
    assert r == b

def test_append_dicom_batch_execution_history_records_round_trips_jsonl(tmp_path):
    recs = build_analysis_history_records_from_dicom_batch_execution_result(_result([_task(payload={"result": 1.0, "status": "ok"})]))
    p = tmp_path/"h.jsonl"; append_dicom_batch_execution_history_records(str(p), recs)
    assert load_analysis_history_records(p)[0]["record_id"] == recs[0]["record_id"]

def test_build_batch_qc_run_from_dicom_batch_execution_result_uses_existing_batch_qc():
    run = build_batch_qc_run_from_dicom_batch_execution_result(_result([_task(payload={"result": 1.0, "status": "ok"})]))
    assert run["item_count"] == 1

def test_threshold_config_is_not_used_unless_explicit():
    run = build_batch_qc_run_from_dicom_batch_execution_result(_result([_task(payload={"result": 1.0, "status": "ok"})]), threshold_config=None)
    assert run["items"][0]["threshold_evaluation"] is None

def test_threshold_config_is_applied_when_explicit():
    run = build_batch_qc_run_from_dicom_batch_execution_result(_result([_task(payload={"result": 1.0, "status": "ok"})]), threshold_config=_cfg())
    assert run["items"][0]["threshold_evaluation"] is not None

def test_adapter_does_not_import_tkinter_or_pydicom():
    src = open("dicom_batch_history_adapter.py", encoding="utf-8").read()
    assert "import tkinter" not in src and "import pydicom" not in src

def _viewer():
    return SimpleNamespace(current_dicom_batch_execution_result=None, current_threshold_config=None)

def test_viewer_build_dicom_batch_history_records_uses_current_execution_result():
    v=_viewer(); v.current_dicom_batch_execution_result=_result([_task(payload={"result":1.0,"status":"ok"})])
    assert len(DicomViewer.build_dicom_batch_history_records_for_viewer(v)) == 1

def test_viewer_build_dicom_batch_history_records_requires_current_result():
    with pytest.raises(ValueError): DicomViewer.build_dicom_batch_history_records_for_viewer(_viewer())

def test_viewer_append_history_cancelled_dialog_does_not_mutate_state(monkeypatch):
    v=_viewer(); v.current_dicom_batch_execution_result=_result([_task(payload={"result":1.0,"status":"ok"})]); b=copy.deepcopy(v.current_dicom_batch_execution_result)
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: "")
    assert DicomViewer.append_dicom_batch_history_records_for_viewer(v, history_path=None) is None and v.current_dicom_batch_execution_result == b

def test_viewer_batch_qc_from_execution_result_selected_threshold_policy():
    v=_viewer(); v.current_dicom_batch_execution_result=_result([_task(payload={"result":1.0,"status":"ok"})]); v.current_threshold_config=_cfg()
    r1=DicomViewer.build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(v, use_selected_threshold_config=False)
    r2=DicomViewer.build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(v, use_selected_threshold_config=True)
    exp=_cfg(); exp["rules"][0]["severity"]="fail"
    r3=DicomViewer.build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(v, threshold_config=exp, use_selected_threshold_config=True)
    assert r1["items"][0]["threshold_evaluation"] is None and r2["items"][0]["threshold_evaluation"] is not None and r3["items"][0]["threshold_evaluation"]["results"][0]["severity"]=="fail"
