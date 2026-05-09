from __future__ import annotations

from types import SimpleNamespace

import pytest

from dicom_viewer import DicomViewer
from tests.test_dicom_batch_execution import _preset
from tests.test_dicom_batch_execution_plan import _bp, _bp_item, _bv, _bv_item
from dicom_batch_execution_plan import build_dicom_batch_execution_plan


def _plan():
    return build_dicom_batch_execution_plan(_bp([_bp_item("i1")]), _bv([_bv_item("i1")]))


def test_viewer_validate_render_preview_and_strict_modes():
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset())
    r = DicomViewer.validate_current_dicom_batch_roi_roles_for_viewer(v)
    assert v.current_dicom_batch_roi_role_validation_report == r
    assert "DICOM Batch ROI Role Validation" in DicomViewer.render_current_dicom_batch_roi_role_validation_text_for_viewer(v)
    assert "DICOM Batch ROI Role Validation" in DicomViewer.preview_current_dicom_batch_roi_role_validation_for_viewer(v)

    v2 = SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset(), current_dicom_batch_execution_result={"old": True})
    with pytest.raises(ValueError):
        DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v2, strict_roi_role_validation=True)
    assert v2.current_dicom_batch_execution_result == {"old": True}


def test_viewer_validate_requires_inputs_and_empty_render_text():
    with pytest.raises(ValueError):
        DicomViewer.validate_current_dicom_batch_roi_roles_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=None, current_roi_preset=_preset()))
    with pytest.raises(ValueError):
        DicomViewer.validate_current_dicom_batch_roi_roles_for_viewer(SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=None))
    assert "No ROI role validation report" in DicomViewer.render_current_dicom_batch_roi_role_validation_text_for_viewer(SimpleNamespace())
