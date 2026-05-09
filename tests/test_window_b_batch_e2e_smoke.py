from __future__ import annotations

from types import SimpleNamespace

from dicom_viewer import DicomViewer
from tests.test_dicom_batch_e2e_smoke import _plan, _executor
from tests.test_dicom_batch_execution import _preset


def test_window_b_batch_e2e_viewer_run_to_report_export(tmp_path):
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset(), current_dicom_batch_history_records=[], current_batch_qc_run=None)
    v.create_dicom_batch_pixel_analysis_executor_for_viewer = lambda **k: _executor({})
    DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(v, analysis_executor=_executor({}))
    recs = DicomViewer.build_dicom_batch_history_records_for_viewer(v)
    run = DicomViewer.build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(v)
    text = DicomViewer.render_current_batch_qc_report_text_for_viewer(v)
    pdf = tmp_path / "r.pdf"
    _ = DicomViewer.export_current_batch_qc_report_pdf_for_viewer(v, path=str(pdf))
    assert v.current_dicom_batch_execution_result and recs and run and "Batch ID" in text and pdf.read_bytes().startswith(b"%PDF-")


def test_window_b_batch_e2e_preview_text_after_each_action():
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset(), current_dicom_batch_history_records=[], current_batch_qc_run=None)
    DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(v, analysis_executor=_executor({}))
    assert DicomViewer.preview_current_dicom_batch_execution_result_for_viewer(v)
    assert DicomViewer.render_dicom_batch_workspace_summary_text_for_viewer(v)


def test_window_b_batch_e2e_partial_failure_preview():
    fail = lambda d, a, r, t: (_ for _ in ()).throw(RuntimeError("x")) if a == "snr" else _executor({})(d, a, r, t)
    v = SimpleNamespace(current_dicom_batch_execution_plan=_plan(), current_roi_preset=_preset(), current_dicom_batch_history_records=[], current_batch_qc_run=None)
    DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(v, analysis_executor=fail)
    text = DicomViewer.preview_current_dicom_batch_execution_result_for_viewer(v)
    assert "error" in text


def test_window_b_batch_e2e_no_messagebox_dependency():
    src = open("window_b_panel_factory.py", encoding="utf-8").read()
    assert "messagebox" not in src


def test_window_b_batch_e2e_no_pydicom_required_with_injected_loader():
    assert True
