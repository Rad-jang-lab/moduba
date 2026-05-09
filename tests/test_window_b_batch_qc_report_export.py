from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from analysis_batch_qc import build_batch_qc_run
from dicom_viewer import DicomViewer
from tests.test_analysis_history_summary import _records


def _run():
    return build_batch_qc_run(_records())


def test_viewer_build_current_batch_qc_report_requires_run():
    with pytest.raises(ValueError): DicomViewer.build_current_batch_qc_report_model_for_viewer(SimpleNamespace(current_batch_qc_run=None))

def test_viewer_build_current_batch_qc_report_uses_current_run():
    v = SimpleNamespace(current_batch_qc_run=_run(), current_batch_qc_report_model=None)
    assert DicomViewer.build_current_batch_qc_report_model_for_viewer(v)["batch"]["item_count"] >= 1

def test_viewer_render_current_batch_qc_report_text():
    v = SimpleNamespace(current_batch_qc_run=_run(), current_batch_qc_report_model=None)
    assert "Batch ID" in DicomViewer.render_current_batch_qc_report_text_for_viewer(v)

def test_viewer_export_batch_qc_json_cancel_returns_none(monkeypatch):
    v = SimpleNamespace(current_batch_qc_run=_run())
    b = copy.deepcopy(v.current_batch_qc_run)
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: "")
    assert DicomViewer.export_current_batch_qc_run_json_for_viewer(v, None) is None and v.current_batch_qc_run == b

def test_viewer_export_batch_qc_csv_cancel_returns_none(monkeypatch):
    v = SimpleNamespace(current_batch_qc_run=_run())
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: "")
    assert DicomViewer.export_current_batch_qc_run_csv_for_viewer(v, None) is None

def test_viewer_export_batch_qc_report_text_writes_file(tmp_path):
    v = SimpleNamespace(current_batch_qc_run=_run(), current_batch_qc_report_model=None)
    p = tmp_path / "r.txt"
    assert "Batch QC Report" in (DicomViewer.export_current_batch_qc_report_text_for_viewer(v, path=str(p)) or "") and p.exists()

def test_viewer_export_batch_qc_report_pdf_writes_file(tmp_path):
    v = SimpleNamespace(current_batch_qc_run=_run(), current_batch_qc_report_model=None)
    p = tmp_path / "r.pdf"
    out = DicomViewer.export_current_batch_qc_report_pdf_for_viewer(v, path=str(p))
    assert p.exists() and (out or b"").startswith(b"%PDF-")
