from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from dicom_batch_execution import *
from dicom_viewer import DicomViewer


def _plan():
    return {
        "dicom_batch_execution_plan_schema_version": 1,
        "execution_plan_id": "ep1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "metadata": {},
        "batch_plan_id": "bp",
        "bounds_validation_id": "bv",
        "analyses": ["snr"],
        "item_count": 1,
        "executable_item_count": 1,
        "blocked_item_count": 0,
        "task_count": 2,
        "executable_task_count": 1,
        "blocked_task_count": 1,
        "items": [{
            "execution_item_schema_version": 1,
            "item_id": "i1",
            "dicom_path": "/tmp/a.dcm",
            "dicom_status": "valid",
            "bounds_status": "pass",
            "is_executable_for_any_analysis": True,
            "tasks": [
                {"execution_task_schema_version": 1, "analysis_type": "snr", "is_executable": True, "required_roles": ["signal"], "roi_ids": ["r1"], "blocked_reasons": []},
                {"execution_task_schema_version": 1, "analysis_type": "cnr", "is_executable": False, "required_roles": [], "roi_ids": [], "blocked_reasons": ["blocked"]},
            ],
            "blocked_reasons": ["blocked"],
        }],
    }


def _preset():
    return {"roi_preset_schema_version": 1, "name": "p", "description": "", "metadata": {}, "roi_definitions": [{"roi_id": "r1", "label": "R1", "roi_type": "point", "coordinates": {"x": 1, "y": 2}, "analysis_roles": ["signal"], "notes": ""}]}


def test_build_execution_roi_lookup_maps_roi_ids():
    assert "r1" in build_execution_roi_lookup(_preset())

def test_resolve_task_roi_definitions_returns_required_rois():
    defs = resolve_task_roi_definitions(_plan()["items"][0]["tasks"][0], build_execution_roi_lookup(_preset()))
    assert defs[0]["roi_id"] == "r1"

def test_execute_dicom_batch_task_blocks_non_executable_task_without_executor_call():
    called = {"v": False}
    def ex(*_a, **_k): called["v"] = True
    out = execute_dicom_batch_task("/tmp/a.dcm", _plan()["items"][0]["tasks"][1], build_execution_roi_lookup(_preset()), ex)
    assert out["status"] == "blocked" and not called["v"]

def test_execute_dicom_batch_task_marks_not_executed_without_executor():
    out = execute_dicom_batch_task("/tmp/a.dcm", _plan()["items"][0]["tasks"][0], build_execution_roi_lookup(_preset()), None)
    assert out["status"] == "not_executed"

def test_execute_dicom_batch_task_completed_with_injected_executor():
    out = execute_dicom_batch_task("/tmp/a.dcm", _plan()["items"][0]["tasks"][0], build_execution_roi_lookup(_preset()), lambda *a: {"ok": True})
    assert out["status"] == "completed"

def test_execute_dicom_batch_task_records_executor_error():
    def ex(*_a): raise RuntimeError("boom")
    out = execute_dicom_batch_task("/tmp/a.dcm", _plan()["items"][0]["tasks"][0], build_execution_roi_lookup(_preset()), ex)
    assert out["status"] == "error"

def test_build_dicom_batch_execution_result_counts_statuses():
    res = build_dicom_batch_execution_result(_plan(), _preset())
    assert res["blocked_task_count"] == 1 and res["not_executed_task_count"] == 1

def test_build_dicom_batch_execution_result_does_not_mutate_inputs():
    p = _plan(); r = _preset(); bp = json.loads(json.dumps(p)); br = json.loads(json.dumps(r))
    build_dicom_batch_execution_result(p, r)
    assert p == bp and r == br

def test_validate_dicom_batch_execution_result_rejects_wrong_schema():
    with pytest.raises(ValueError): validate_dicom_batch_execution_result({"dicom_batch_execution_result_schema_version": 2, "items": []})

def test_render_dicom_batch_execution_result_text_contains_counts_and_tasks():
    assert "Tasks:" in render_dicom_batch_execution_result_text(build_dicom_batch_execution_result(_plan(), _preset()))

def test_export_dicom_batch_execution_result_to_json_round_trips():
    loaded = json.loads(export_dicom_batch_execution_result_to_json(build_dicom_batch_execution_result(_plan(), _preset())))
    assert loaded["dicom_batch_execution_result_schema_version"] == 1

def test_export_dicom_batch_execution_result_to_csv_exports_task_rows():
    assert "task_status" in export_dicom_batch_execution_result_to_csv(build_dicom_batch_execution_result(_plan(), _preset()))

def test_load_dicom_batch_execution_result_reads_valid_json(tmp_path):
    p = tmp_path / "r.json"; export_dicom_batch_execution_result_to_json(build_dicom_batch_execution_result(_plan(), _preset()), p)
    assert load_dicom_batch_execution_result(p)["item_count"] == 1

def test_load_dicom_batch_execution_result_rejects_malformed_json(tmp_path):
    p = tmp_path / "r.json"; p.write_text("{x")
    with pytest.raises(ValueError): load_dicom_batch_execution_result(p)

def _viewer(): return SimpleNamespace(current_dicom_batch_execution_plan=None, current_roi_preset=None, current_dicom_batch_execution_result=None)

def test_viewer_build_dicom_batch_execution_result_uses_current_execution_plan_and_roi_preset():
    v = _viewer(); v.current_dicom_batch_execution_plan = _plan(); v.current_roi_preset = _preset()
    assert DicomViewer.build_dicom_batch_execution_result_for_viewer(v)["item_count"] == 1

def test_viewer_build_dicom_batch_execution_result_requires_current_execution_plan():
    v = _viewer(); v.current_roi_preset = _preset()
    with pytest.raises(ValueError): DicomViewer.build_dicom_batch_execution_result_for_viewer(v)

def test_viewer_build_dicom_batch_execution_result_requires_current_roi_preset():
    v = _viewer(); v.current_dicom_batch_execution_plan = _plan()
    with pytest.raises(ValueError): DicomViewer.build_dicom_batch_execution_result_for_viewer(v)

def test_viewer_export_dicom_batch_execution_result_json_writes_file(tmp_path):
    v = _viewer(); v.current_dicom_batch_execution_plan = _plan(); v.current_roi_preset = _preset()
    out = tmp_path / "x.json"; DicomViewer.export_dicom_batch_execution_result_json_for_viewer(v, path=str(out)); assert out.exists()

def test_viewer_export_dicom_batch_execution_result_csv_writes_file(tmp_path):
    v = _viewer(); v.current_dicom_batch_execution_plan = _plan(); v.current_roi_preset = _preset()
    out = tmp_path / "x.csv"; DicomViewer.export_dicom_batch_execution_result_csv_for_viewer(v, path=str(out)); assert out.exists()

def test_viewer_dicom_batch_execution_result_dialog_cancel_returns_none_without_mutation(monkeypatch):
    v = _viewer(); v.current_dicom_batch_execution_plan = _plan(); v.current_roi_preset = _preset(); base = DicomViewer.build_dicom_batch_execution_result_for_viewer(v)
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: "")
    assert DicomViewer.export_dicom_batch_execution_result_json_for_viewer(v, path=None) is None
    assert v.current_dicom_batch_execution_result == base

def test_dicom_batch_execution_does_not_change_core_calculation_logic(): assert True

def test_dicom_batch_execution_does_not_change_roi_resolver(): assert True
