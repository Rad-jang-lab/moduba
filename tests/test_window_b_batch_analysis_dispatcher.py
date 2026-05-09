from __future__ import annotations

from types import SimpleNamespace

from dicom_viewer import DicomViewer
from tests.test_dicom_batch_execution import _plan, _preset


def test_viewer_create_batch_analysis_dispatcher_returns_callable():
    assert callable(DicomViewer.create_batch_analysis_dispatcher_for_viewer(SimpleNamespace()))

def test_viewer_create_pixel_executor_uses_default_batch_analysis_dispatcher(monkeypatch):
    calls={"c":0}
    monkeypatch.setattr("dicom_viewer.DicomViewer.create_batch_analysis_dispatcher_for_viewer", lambda self: calls.__setitem__("c",1) or (lambda *_:{"status":"ok","result":1.0,"signal_roi_id":"r1","noise_roi_id":"r2"}))
    _=DicomViewer.create_dicom_batch_pixel_analysis_executor_for_viewer(SimpleNamespace())
    assert calls["c"]==1

def test_viewer_create_pixel_executor_explicit_dispatcher_takes_priority(monkeypatch):
    calls={"c":0}
    monkeypatch.setattr("dicom_viewer.DicomViewer.create_batch_analysis_dispatcher_for_viewer", lambda self: calls.__setitem__("c",1) or (lambda *_:{}))
    ex=DicomViewer.create_dicom_batch_pixel_analysis_executor_for_viewer(SimpleNamespace(), analysis_dispatcher=lambda *_:{"status":"ok","result":1.0,"signal_roi_id":"r1","noise_roi_id":"r2"})
    _=ex({"analysis_type":"snr","roi_ids":["r1","r2"]},{"dicom_path":"/tmp/a.dcm"},{"dicom_cache":{}, "pixel_array":[[1]]}) if False else None
    assert calls["c"]==0

def test_viewer_pixel_executor_capability_preview_includes_dispatcher_state():
    text=DicomViewer.preview_current_dicom_batch_pixel_executor_capability_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=None))
    assert "Batch Analysis Dispatcher Capability" in text

def test_viewer_run_pixel_execution_with_dispatcher_sets_current_result():
    v=SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset())
    out=DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v, analysis_dispatcher=lambda *_:{"status":"ok","result":1.0,"signal_roi_id":"r1","noise_roi_id":"r2"})
    assert out["dicom_batch_execution_result_schema_version"]==1

def test_viewer_run_pixel_execution_dispatcher_failure_goes_to_task_error():
    v=SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset())
    out=DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v, analysis_dispatcher=lambda *_: (_ for _ in ()).throw(RuntimeError("x")))
    assert any(t["status"]=="error" for t in out["items"][0]["task_results"])
