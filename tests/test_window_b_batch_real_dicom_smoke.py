from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from dicom_viewer import DicomViewer
from tests.test_dicom_batch_execution import _preset
from tests.test_dicom_batch_real_dicom_smoke import _create_minimal_test_dicom, _plan_for_path


def _dispatcher(task, item, context):
    return {"status": "ok", "result": 1.0, "signal_roi_id": "r1", "noise_roi_id": "r1"}


def test_window_b_viewer_real_dicom_run_to_execution_result(tmp_path):
    path = _create_minimal_test_dicom(tmp_path / "v.dcm", np.array([[1, 2], [3, 4]], dtype=np.uint16))
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan_for_path(str(path)), current_roi_preset=_preset(), current_dicom_batch_history_records=[], current_batch_qc_run=None)
    DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v, analysis_dispatcher=_dispatcher)
    text = DicomViewer.preview_current_dicom_batch_execution_result_for_viewer(v)
    assert v.current_dicom_batch_execution_result and ("completed" in text or "blocked" in text)


def test_window_b_viewer_real_dicom_run_to_report_text(tmp_path):
    path = _create_minimal_test_dicom(tmp_path / "v2.dcm", np.array([[1, 2], [3, 4]], dtype=np.uint16))
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan_for_path(str(path)), current_roi_preset=_preset(), current_dicom_batch_history_records=[], current_batch_qc_run=None)
    DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v, analysis_dispatcher=_dispatcher)
    DicomViewer.build_dicom_batch_history_records_for_viewer(v)
    DicomViewer.build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(v)
    text = DicomViewer.render_current_batch_qc_report_text_for_viewer(v)
    assert "Batch QC Report" in text


def test_window_b_real_dicom_error_preview_for_unreadable_path():
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan_for_path("/no/such/path.dcm"), current_roi_preset=_preset(), current_dicom_batch_history_records=[], current_batch_qc_run=None)
    DicomViewer.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(v, analysis_dispatcher=_dispatcher)
    text = DicomViewer.preview_current_dicom_batch_execution_result_for_viewer(v)
    assert "error" in text or "blocked" in text


def test_window_b_real_dicom_smoke_no_messagebox():
    src = open("window_b_panel_factory.py", encoding="utf-8").read()
    assert "messagebox" not in src
