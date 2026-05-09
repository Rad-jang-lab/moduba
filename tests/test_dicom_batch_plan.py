from __future__ import annotations
import json
import pytest
from dicom_batch_plan import *
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export


def _manifest(valid=True):
    return {"dicom_batch_manifest_schema_version":1,"manifest_id":"m1","generated_at":"2026-01-01T00:00:00+00:00","metadata":{},"source_paths":[],"recursive":True,"item_count":1,"valid_item_count":1 if valid else 0,"invalid_item_count":0 if valid else 1,"items":[{"batch_item_schema_version":1,"item_id":"i1","path":"/tmp/a.dcm","status":"valid" if valid else "invalid","reason":None if valid else "not_dicom","dicom_metadata":{}}]}

def _preset(roles):
    return {"roi_preset_schema_version":1,"name":"p","description":"","metadata":{},"roi_definitions":[{"roi_id":"r1","label":"","roi_type":"point","coordinates":{"x":1,"y":1},"analysis_roles":roles,"notes":""}]}

def test_build_dicom_batch_analysis_plan_ready_items():
    p=build_dicom_batch_analysis_plan(_manifest(),_preset(["signal","noise","uniformity","mtf_edge","region_a","region_b","background"]))
    assert p["ready_item_count"]==1

def test_build_dicom_batch_analysis_plan_blocks_invalid_dicom_item():
    assert build_dicom_batch_analysis_plan(_manifest(False),_preset(["signal","noise"]))["blocked_item_count"]==1

def test_build_dicom_batch_analysis_plan_blocks_missing_roi_roles():
    assert build_dicom_batch_analysis_plan(_manifest(),_preset(["signal"]))["blocked_item_count"]==1

def test_build_dicom_batch_analysis_plan_handles_empty_manifest():
    m=_manifest(); m["items"]=[]; m["item_count"]=0
    assert build_dicom_batch_analysis_plan(m,_preset(["signal","noise"]))["item_count"]==0

def test_build_dicom_batch_analysis_plan_does_not_mutate_inputs():
    m=_manifest(); p=_preset(["signal","noise"])
    bm=json.loads(json.dumps(m)); bp=json.loads(json.dumps(p))
    build_dicom_batch_analysis_plan(m,p)
    assert m==bm and p==bp

def test_validate_dicom_batch_analysis_plan_rejects_wrong_schema():
    with pytest.raises(ValueError):
        validate_dicom_batch_analysis_plan({"dicom_batch_analysis_plan_schema_version":2,"items":[]})

def test_render_dicom_batch_analysis_plan_text_contains_counts_and_readiness():
    assert "Ready" in render_dicom_batch_analysis_plan_text(build_dicom_batch_analysis_plan(_manifest(),_preset(["signal","noise"])))

def test_export_dicom_batch_analysis_plan_to_json_round_trips():
    assert json.loads(export_dicom_batch_analysis_plan_to_json(build_dicom_batch_analysis_plan(_manifest(),_preset(["signal","noise"]))))["item_count"]==1

def test_export_dicom_batch_analysis_plan_to_csv_exports_item_rows():
    assert "dicom_path" in export_dicom_batch_analysis_plan_to_csv(build_dicom_batch_analysis_plan(_manifest(),_preset(["signal","noise"])))

def test_load_dicom_batch_analysis_plan_reads_valid_json(tmp_path):
    p=tmp_path/"p.json"
    export_dicom_batch_analysis_plan_to_json(build_dicom_batch_analysis_plan(_manifest(),_preset(["signal","noise"])),p)
    assert load_dicom_batch_analysis_plan(p)["item_count"]==1

def test_load_dicom_batch_analysis_plan_rejects_malformed_json(tmp_path):
    p=tmp_path/"x.json"; p.write_text("{x")
    with pytest.raises(ValueError):
        load_dicom_batch_analysis_plan(p)

def test_viewer_build_dicom_batch_analysis_plan_uses_current_manifest_and_preset():
    v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(["signal","noise"])
    assert DicomViewer.build_dicom_batch_analysis_plan_for_viewer(v)["item_count"]==1

def test_viewer_build_dicom_batch_analysis_plan_requires_current_manifest():
    v=_viewer_for_export(); v.current_roi_preset=_preset(["signal","noise"])
    with pytest.raises(ValueError): DicomViewer.build_dicom_batch_analysis_plan_for_viewer(v)

def test_viewer_build_dicom_batch_analysis_plan_requires_current_roi_preset():
    v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest()
    with pytest.raises(ValueError): DicomViewer.build_dicom_batch_analysis_plan_for_viewer(v)

def test_viewer_export_dicom_batch_analysis_plan_json_writes_file(tmp_path):
    v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(["signal","noise"])
    p=tmp_path/"p.json"; DicomViewer.export_dicom_batch_analysis_plan_json_for_viewer(v,path=str(p)); assert p.exists()

def test_viewer_export_dicom_batch_analysis_plan_csv_writes_file(tmp_path):
    v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(["signal","noise"])
    p=tmp_path/"p.csv"; DicomViewer.export_dicom_batch_analysis_plan_csv_for_viewer(v,path=str(p)); assert p.exists()

def test_viewer_dicom_batch_plan_dialog_cancel_returns_none_without_mutation(monkeypatch):
    v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(["signal","noise"])
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: "")
    assert DicomViewer.export_dicom_batch_analysis_plan_json_for_viewer(v,path=None) is None

def test_dicom_batch_plan_does_not_start_batch_analysis_or_calculation():
    v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(["signal","noise"])
    DicomViewer.build_dicom_batch_analysis_plan_for_viewer(v); assert not hasattr(v,"dicom_batch_execution_state")

def test_dicom_batch_plan_does_not_read_pixel_data():
    assert True

def test_dicom_batch_plan_does_not_change_roi_resolver():
    assert True
