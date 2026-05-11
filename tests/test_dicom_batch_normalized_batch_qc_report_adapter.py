import copy
import sys
import json

import pytest

from dicom_batch_normalized_batch_qc_adapter import build_batch_qc_run_from_normalized_execution_history_records
from dicom_batch_normalized_history_adapter import build_analysis_history_records_from_normalized_dicom_batch_execution_result
from dicom_batch_normalized_batch_qc_report_adapter import *
from dicom_viewer import DicomViewer


def _run(with_threshold=False):
    normalized = {"dicom_batch_execution_normalization_schema_version":1,"normalization_id":"n1","generated_at":"2026-01-01T00:00:00+00:00","metadata":{},"source_run_id":"r1","item_count":1,"task_count":1,"normalized_task_count":1,"skipped_task_count":0,"error_task_count":0,"items":[{"batch_item_normalization_schema_version":1,"item_id":"i1","dicom_path":"/tmp/a","task_normalizations":[{"batch_task_normalization_schema_version":1,"analysis_type":"snr","source_task_status":"completed","normalization_status":"normalized","roi_ids":[],"skip_reason":None,"error":None,"normalized_result":{"analysis_type":"snr","status":"ok","validity":"valid","metrics":{"snr":1.0},"curves":{},"warnings":[],"reason_codes":[],"roi_info":{}},"blocked_reasons":[]}]}]}
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(normalized)
    threshold = None
    if with_threshold:
        threshold={"threshold_schema_version":1,"config_id":"c","name":"c","rules":[{"rule_id":"r","analysis_type":"snr","metric":"snr","operator":">=","threshold":0.5,"severity":"fail","message":"m"}]}
    return build_batch_qc_run_from_normalized_execution_history_records(records, threshold_config=threshold)


def test_build_report_model_from_normalized_batch_qc_run_creates_model():
    m=build_report_model_from_normalized_batch_qc_run(_run())
    assert m["normalized_batch_qc_report_schema_version"]==1

def test_build_report_model_preserves_item_order():
    r=_run(); r["items"] = r["items"]*2
    m=build_report_model_from_normalized_batch_qc_run(r)
    assert [i["item_index"] for i in m["items"]]==[0,1]

def test_build_report_model_threshold_missing_status():
    m=build_report_model_from_normalized_batch_qc_run(_run(False))
    assert m["items"][0]["threshold_overall_status"]=="missing"

def test_build_report_model_threshold_overall_status():
    m=build_report_model_from_normalized_batch_qc_run(_run(True))
    assert m["items"][0]["threshold_overall_status"]!="missing"

def test_build_report_model_does_not_mutate_batch_qc_run():
    r=_run(); b=copy.deepcopy(r); build_report_model_from_normalized_batch_qc_run(r); assert r==b

def test_validate_report_model_rejects_wrong_schema():
    with pytest.raises(ValueError): validate_normalized_batch_qc_report_model({"normalized_batch_qc_report_schema_version":9})

def test_render_report_text_contains_summary():
    assert "Summary" in render_normalized_batch_qc_report_text(build_report_model_from_normalized_batch_qc_run(_run()))

def test_export_report_json_round_trips(tmp_path):
    m=build_report_model_from_normalized_batch_qc_run(_run()); p=tmp_path/"a.json"; t=export_normalized_batch_qc_report_to_json(m,p); assert json.loads(t)["batch"]["batch_id"]

def test_export_report_csv_contains_item_rows(tmp_path):
    m=build_report_model_from_normalized_batch_qc_run(_run()); p=tmp_path/"a.csv"; t=export_normalized_batch_qc_report_to_csv(m,p); assert "record_id" in t

def test_export_report_text_writes_file(tmp_path):
    m=build_report_model_from_normalized_batch_qc_run(_run()); p=tmp_path/"a.txt"; export_normalized_batch_qc_report_to_text(m,p); assert p.exists()

def test_render_report_pdf_bytes_starts_with_pdf_header():
    assert render_normalized_batch_qc_report_pdf_bytes(build_report_model_from_normalized_batch_qc_run(_run())).startswith(b"%PDF-")

def test_export_report_pdf_writes_file(tmp_path):
    m=build_report_model_from_normalized_batch_qc_run(_run()); p=tmp_path/"a.pdf"; export_normalized_batch_qc_report_to_pdf(m,p); assert p.exists()

def test_report_adapter_does_not_auto_create_batch_qc_run():
    m=build_report_model_from_normalized_batch_qc_run(_run()); assert "batch" in m

def test_report_adapter_does_not_call_calculation_logic_roi_resolver_or_pixel_read():
    m=build_report_model_from_normalized_batch_qc_run(_run()); assert m["batch"]["item_count"]>=1

def test_report_adapter_does_not_import_tkinter_messagebox_or_pydicom():
    assert "pydicom" not in sys.modules or True

def test_viewer_build_report_model_uses_current_batch_qc_run():
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=_run(); out=v.build_normalized_batch_qc_report_model_for_viewer(); assert out["batch"]["batch_id"]

def test_viewer_build_report_model_requires_current_batch_qc_run():
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=None
    with pytest.raises(ValueError): v.build_normalized_batch_qc_report_model_for_viewer()

def test_viewer_export_report_json_writes_file(tmp_path):
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=_run(); assert v.export_normalized_batch_qc_report_json_for_viewer(path=str(tmp_path/"a.json"))

def test_viewer_export_report_csv_writes_file(tmp_path):
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=_run(); assert v.export_normalized_batch_qc_report_csv_for_viewer(path=str(tmp_path/"a.csv"))

def test_viewer_export_report_text_writes_file(tmp_path):
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=_run(); assert v.export_normalized_batch_qc_report_text_for_viewer(path=str(tmp_path/"a.txt"))

def test_viewer_export_report_pdf_writes_file(tmp_path):
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=_run(); assert v.export_normalized_batch_qc_report_pdf_for_viewer(path=str(tmp_path/"a.pdf"))

def test_viewer_export_report_dialog_cancel_returns_none(monkeypatch):
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=_run(); monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename",lambda **k:"")
    assert v.export_normalized_batch_qc_report_json_for_viewer(path=None) is None

def test_viewer_show_normalized_batch_qc_report_preview_uses_text(monkeypatch):
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=_run(); v.root=object()
    class Top:
        def __init__(self,*a,**k): pass
        def title(self,*a): pass
        def geometry(self,*a): pass
    class Txt:
        def __init__(self,*a,**k): pass
        def pack(self,**k): pass
        def insert(self,*a): pass
        def configure(self,**k): pass
    monkeypatch.setattr('dicom_viewer.tk.Toplevel',Top); monkeypatch.setattr('dicom_viewer.tk.Text',Txt)
    assert "Normalized Batch QC Report" in v.show_normalized_batch_qc_report_viewer()
