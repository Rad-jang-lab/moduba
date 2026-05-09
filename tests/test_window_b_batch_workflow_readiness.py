from __future__ import annotations

from types import SimpleNamespace

import pytest

from dicom_viewer import DicomViewer


def test_viewer_workflow_readiness_helpers_and_state():
    v=SimpleNamespace(current_dicom_batch_execution_plan={"items": []}, current_dicom_batch_roi_role_validation_report={"valid": True}, current_dicom_batch_execution_result=None, current_dicom_batch_history_records=[], current_batch_qc_run=None)
    DicomViewer.set_current_dicom_batch_strict_roi_validation_for_viewer(v, True)
    assert v.current_dicom_batch_strict_roi_validation is True
    r=DicomViewer.build_current_dicom_batch_workflow_readiness_for_viewer(v)
    assert v.current_dicom_batch_workflow_readiness_report == r
    assert "DICOM Batch Workflow Readiness" in DicomViewer.preview_current_dicom_batch_workflow_readiness_for_viewer(v)


def test_viewer_run_strict_true_blocks_invalid_and_false_preserves():
    v=SimpleNamespace(current_dicom_batch_execution_plan={"items": []}, current_roi_preset={"rois": []}, current_dicom_batch_execution_result={"old": True})
    with pytest.raises(ValueError):
        DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v, strict_roi_role_validation=True)
    assert v.current_dicom_batch_execution_result == {"old": True}
