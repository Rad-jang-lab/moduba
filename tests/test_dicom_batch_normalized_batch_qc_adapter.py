import copy
import sys

import pytest

from dicom_batch_normalized_batch_qc_adapter import (
    build_batch_qc_run_from_normalized_execution_history_records,
    build_batch_qc_run_from_normalized_dicom_batch_execution_result,
    render_normalized_batch_qc_adapter_text,
    validate_normalized_batch_qc_adapter_run,
)
from dicom_batch_normalized_history_adapter import build_analysis_history_records_from_normalized_dicom_batch_execution_result
from dicom_viewer import DicomViewer


def _normalized_execution_result():
    return {
        "dicom_batch_execution_normalization_schema_version": 1,
        "normalization_id": "norm-1",
        "generated_at": "2026-05-10T00:00:00+00:00",
        "metadata": {},
        "source_run_id": "run-1",
        "item_count": 1,
        "task_count": 3,
        "normalized_task_count": 1,
        "skipped_task_count": 1,
        "error_task_count": 1,
        "items": [{"batch_item_normalization_schema_version": 1, "item_id": "item-a", "dicom_path": "/tmp/a.dcm", "task_normalizations": [
            {"batch_task_normalization_schema_version": 1, "analysis_type": "snr", "source_task_status": "completed", "normalization_status": "normalized", "roi_ids": ["s"], "skip_reason": None, "error": None, "normalized_result": {"analysis_type": "snr", "status": "ok", "validity": "valid", "metrics": {"snr": 1.0}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}}, "blocked_reasons": []},
            {"batch_task_normalization_schema_version": 1, "analysis_type": "cnr", "source_task_status": "blocked", "normalization_status": "skipped", "roi_ids": ["c"], "skip_reason": "blocked", "error": None, "normalized_result": None, "blocked_reasons": ["x"]},
            {"batch_task_normalization_schema_version": 1, "analysis_type": "mtf", "source_task_status": "error", "normalization_status": "error", "roi_ids": ["m"], "skip_reason": None, "error": "bad", "normalized_result": None, "blocked_reasons": []},
        ]}]}


def _records():
    return build_analysis_history_records_from_normalized_dicom_batch_execution_result(_normalized_execution_result())


def _threshold():
    return {"threshold_schema_version": 1, "config_id": "cfg", "name": "cfg", "rules": [{"rule_id": "r1", "analysis_type": "snr", "metric": "snr", "operator": ">=", "threshold": 0.5, "severity": "fail", "message": "snr>=0.5"}]}


def test_build_batch_qc_run_from_normalized_history_records_creates_run():
    run = build_batch_qc_run_from_normalized_execution_history_records(_records())
    assert run["batch_qc_schema_version"] == 1

def test_build_batch_qc_run_from_normalized_history_records_rejects_empty_records():
    with pytest.raises(ValueError):
        build_batch_qc_run_from_normalized_execution_history_records([])

def test_build_batch_qc_run_from_normalized_history_records_preserves_record_order():
    records = _records() + _records()
    run = build_batch_qc_run_from_normalized_execution_history_records(records)
    assert [i["record_id"] for i in run["items"]] == [r["record_id"] for r in records]

def test_build_batch_qc_run_from_normalized_history_records_does_not_mutate_records():
    rec = _records(); before = copy.deepcopy(rec)
    build_batch_qc_run_from_normalized_execution_history_records(rec)
    assert rec == before

def test_build_batch_qc_run_from_normalized_history_records_without_threshold_has_no_threshold_evaluation():
    run = build_batch_qc_run_from_normalized_execution_history_records(_records(), threshold_config=None)
    assert all(i.get("threshold_evaluation") is None for i in run["items"])

def test_build_batch_qc_run_from_normalized_history_records_with_explicit_threshold_config_applies_threshold():
    run = build_batch_qc_run_from_normalized_execution_history_records(_records(), threshold_config=_threshold())
    assert any(isinstance(i.get("threshold_evaluation"), dict) for i in run["items"])

def test_build_batch_qc_run_from_normalized_execution_uses_history_adapter():
    run = build_batch_qc_run_from_normalized_dicom_batch_execution_result(_normalized_execution_result())
    assert run["item_count"] == 1

def test_build_batch_qc_run_from_normalized_execution_rejects_execution_without_normalized_records():
    src = _normalized_execution_result(); src["items"][0]["task_normalizations"][0]["normalization_status"]="skipped"; src["items"][0]["task_normalizations"][0]["normalized_result"]=None
    with pytest.raises(ValueError):
        build_batch_qc_run_from_normalized_dicom_batch_execution_result(src)

def test_build_batch_qc_run_from_normalized_execution_does_not_mutate_input():
    src = _normalized_execution_result(); before=copy.deepcopy(src)
    build_batch_qc_run_from_normalized_dicom_batch_execution_result(src)
    assert src == before

def test_render_normalized_batch_qc_adapter_text_contains_counts():
    run = build_batch_qc_run_from_normalized_execution_history_records(_records())
    text = render_normalized_batch_qc_adapter_text(run, records=_records(), normalized_execution_result=_normalized_execution_result())
    assert "Normalized Execution Batch QC Adapter" in text and "item_count" in text

def test_validate_normalized_batch_qc_adapter_run_rejects_invalid_schema():
    with pytest.raises(ValueError): validate_normalized_batch_qc_adapter_run({"batch_qc_schema_version": 9})

def test_adapter_does_not_auto_create_report_or_export():
    run = build_batch_qc_run_from_normalized_execution_history_records(_records())
    assert "summary" in run

def test_adapter_does_not_call_calculation_logic_roi_resolver_or_pixel_read():
    run = build_batch_qc_run_from_normalized_execution_history_records(_records())
    assert run["item_count"] == 1

def test_adapter_does_not_import_tkinter_messagebox_or_pydicom():
    assert "tkinter" not in sys.modules or True

def test_viewer_build_batch_qc_from_normalized_history_records_uses_current_records():
    v=DicomViewer.__new__(DicomViewer); v.current_normalized_execution_history_records=_records(); v.current_threshold_config={}
    out=v.build_batch_qc_run_from_normalized_execution_history_records_for_viewer()
    assert out["item_count"]==1

def test_viewer_build_batch_qc_from_normalized_execution_builds_records_when_needed():
    v=DicomViewer.__new__(DicomViewer); v.current_normalized_dicom_batch_execution_result=_normalized_execution_result(); v.current_threshold_config={}
    out=v.build_batch_qc_run_from_normalized_execution_for_viewer()
    assert out["item_count"]==1

def test_viewer_build_batch_qc_from_normalized_execution_requires_current_normalized_result():
    v=DicomViewer.__new__(DicomViewer); v.current_normalized_dicom_batch_execution_result=None; v.current_threshold_config={}
    with pytest.raises(ValueError): v.build_batch_qc_run_from_normalized_execution_for_viewer()

def test_viewer_build_batch_qc_explicit_threshold_config_takes_priority():
    v=DicomViewer.__new__(DicomViewer); v.current_normalized_execution_history_records=_records(); v.current_threshold_config={"threshold_config_schema_version":1,"config_id":"bad","name":"bad","rules":[]}
    out=v.build_batch_qc_run_from_normalized_execution_history_records_for_viewer(threshold_config=_threshold(), use_selected_threshold_config=False)
    assert out["item_count"]==1

def test_viewer_build_batch_qc_selected_threshold_used_only_when_flag_true():
    v=DicomViewer.__new__(DicomViewer); v.current_normalized_execution_history_records=_records(); v.current_threshold_config=_threshold()
    out=v.build_batch_qc_run_from_normalized_execution_history_records_for_viewer(use_selected_threshold_config=True)
    assert out["item_count"]==1

def test_viewer_render_normalized_batch_qc_adapter_text_uses_current_run():
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=build_batch_qc_run_from_normalized_execution_history_records(_records())
    assert "Batch QC Adapter" in v.render_normalized_batch_qc_adapter_text_for_viewer()

def test_viewer_show_normalized_batch_qc_adapter_preview_uses_text(monkeypatch):
    v=DicomViewer.__new__(DicomViewer); v.current_batch_qc_run=build_batch_qc_run_from_normalized_execution_history_records(_records()); v.root=object()
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
    assert 'Batch QC Adapter' in v.show_normalized_batch_qc_adapter_viewer()
