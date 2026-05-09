from __future__ import annotations

from types import SimpleNamespace

import pytest

from dicom_viewer import DicomViewer
from tests.test_dicom_batch_execution import _plan, _preset


def test_viewer_build_execution_plan_requires_manifest_or_current_state():
    with pytest.raises(ValueError): DicomViewer.build_current_dicom_batch_execution_plan_for_viewer(SimpleNamespace(current_dicom_batch_manifest=None, current_roi_preset=None))

def test_viewer_build_execution_plan_sets_current_plan(monkeypatch):
    v = SimpleNamespace(current_dicom_batch_manifest={}, current_roi_preset=_preset(), current_roi_bounds_validation={"x":1})
    monkeypatch.setattr("dicom_viewer.DicomViewer.build_dicom_batch_analysis_plan_for_viewer", lambda self, **k: {"dicom_batch_analysis_plan_schema_version":1,"batch_plan_id":"bp","generated_at":"x","metadata":{},"manifest_id":"m","roi_preset_name":"p","analyses":["snr"],"item_count":1,"ready_item_count":1,"blocked_item_count":0,"items":[{"analysis_item_schema_version":1,"item_id":"i1","dicom_path":"/tmp/a.dcm","dicom_status":"valid","analyses":[{"analysis_type":"snr","required_roles":["signal"],"is_ready":True,"ready_reason":"ok","blocked_reasons":[],"missing_roles":[],"matched_roi_ids":["r1"]}],"is_ready_for_any_analysis":True,"blocked_reasons":[]}]} )
    monkeypatch.setattr("dicom_viewer.build_dicom_batch_execution_plan", lambda *a, **k: _plan())
    monkeypatch.setattr("dicom_viewer.DicomViewer._refresh_window_b_batch_workspace", lambda self: None)
    out = DicomViewer.build_current_dicom_batch_execution_plan_for_viewer(v)
    assert out["dicom_batch_execution_plan_schema_version"] == 1

def test_viewer_run_execution_plan_requires_current_plan():
    with pytest.raises(ValueError): DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=None))

def test_viewer_run_execution_plan_sets_current_result(monkeypatch):
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset())
    monkeypatch.setattr("dicom_viewer.DicomViewer._refresh_window_b_batch_workspace", lambda self: None)
    out = DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(v, analysis_executor=lambda *_: {"ok": True})
    assert out["dicom_batch_execution_result_schema_version"] == 1

def test_viewer_run_execution_plan_refreshes_batch_workspace(monkeypatch):
    calls={"c":0}
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset())
    monkeypatch.setattr("dicom_viewer.DicomViewer._refresh_window_b_batch_workspace", lambda self: calls.__setitem__("c", calls["c"]+1))
    _ = DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(v)
    assert calls["c"] == 1

def test_viewer_preview_execution_result_empty_state():
    assert "empty" in DicomViewer.preview_current_dicom_batch_execution_result_for_viewer(SimpleNamespace(current_dicom_batch_execution_result=None))

def test_viewer_preview_execution_result_contains_status_counts():
    v = SimpleNamespace(current_dicom_batch_execution_result=DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset()), analysis_executor=None))
    t = DicomViewer.preview_current_dicom_batch_execution_result_for_viewer(v)
    assert "Tasks:" in t
