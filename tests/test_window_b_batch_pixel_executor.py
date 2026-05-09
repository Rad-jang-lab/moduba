from __future__ import annotations

from types import SimpleNamespace

import pytest

from dicom_viewer import DicomViewer


def test_viewer_create_pixel_executor_returns_callable():
    assert callable(DicomViewer.create_dicom_batch_pixel_analysis_executor_for_viewer(SimpleNamespace()))

def test_viewer_run_pixel_execution_requires_current_plan():
    with pytest.raises(ValueError): DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=None))

def test_viewer_run_pixel_execution_sets_current_result(monkeypatch):
    v=SimpleNamespace(current_dicom_batch_execution_plan={"x":1},current_roi_preset={"x":1})
    monkeypatch.setattr("dicom_viewer.DicomViewer.create_dicom_batch_pixel_analysis_executor_for_viewer", lambda self, **k: object())
    monkeypatch.setattr("dicom_viewer.DicomViewer.run_current_dicom_batch_execution_plan_for_viewer", lambda self, **k: {"ok":1})
    assert DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v)=={"ok":1}

def test_viewer_run_pixel_execution_refreshes_batch_workspace(monkeypatch):
    v=SimpleNamespace(current_dicom_batch_execution_plan={"x":1},current_roi_preset={"x":1})
    monkeypatch.setattr("dicom_viewer.DicomViewer.create_dicom_batch_pixel_analysis_executor_for_viewer", lambda self, **k: object())
    monkeypatch.setattr("dicom_viewer.DicomViewer.run_current_dicom_batch_execution_plan_for_viewer", lambda self, **k: {"ok":1})
    _=DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v)

def test_viewer_pixel_executor_capability_preview_empty_state():
    t=DicomViewer.preview_current_dicom_batch_pixel_executor_capability_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=None))
    assert "has_execution_plan" in t

def test_viewer_pixel_executor_capability_preview_lists_supported_types():
    t=DicomViewer.preview_current_dicom_batch_pixel_executor_capability_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=None))
    assert "snr" in t and "mtf" in t
