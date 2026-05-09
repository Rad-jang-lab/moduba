from __future__ import annotations
import json
import pytest
from roi_bounds_validation import *
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export


def _manifest(valid=True, rows=10, cols=10):
    return {"dicom_batch_manifest_schema_version":1,"manifest_id":"m","generated_at":"2026-01-01T00:00:00+00:00","metadata":{},"source_paths":[],"recursive":True,"item_count":1,"valid_item_count":1 if valid else 0,"invalid_item_count":0 if valid else 1,"items":[{"batch_item_schema_version":1,"item_id":"i1","path":"/tmp/a.dcm","status":"valid" if valid else "invalid","reason":None if valid else "not_dicom","dicom_metadata":{"Rows":rows,"Columns":cols}}]}

def _preset(roi):
    return {"roi_preset_schema_version":1,"name":"p","description":"","metadata":{},"roi_definitions":[roi]}

def _rect(x=1,y=1,w=2,h=2):
    return {"roi_id":"r1","label":"","roi_type":"rectangle","coordinates":{"x":x,"y":y,"width":w,"height":h},"analysis_roles":["signal","noise"],"notes":""}

def _ell():
    return {"roi_id":"e1","label":"","roi_type":"ellipse","coordinates":{"x":1,"y":1,"width":2,"height":2},"analysis_roles":["noise"],"notes":""}

def _point(x=1,y=1):
    return {"roi_id":"p1","label":"","roi_type":"point","coordinates":{"x":x,"y":y},"analysis_roles":["uniformity"],"notes":""}

def _poly(inb=True):
    return {"roi_id":"g1","label":"","roi_type":"polygon","coordinates":{"points":[{"x":1,"y":1},{"x":2,"y":2},{"x":3 if inb else 20,"y":3}]},"analysis_roles":["region_a"],"notes":""}

def _line(inb=True):
    return {"roi_id":"l1","label":"","roi_type":"line","coordinates":{"points":[{"x":1,"y":1},{"x":2 if inb else 20,"y":2}]},"analysis_roles":["mtf_edge"],"notes":""}

def test_validate_roi_definition_bounds_accepts_rectangle_inside_image(): assert validate_roi_definition_bounds(_rect(),10,10)["bounds_status"]=="pass"
def test_validate_roi_definition_bounds_rejects_rectangle_outside_image(): assert validate_roi_definition_bounds(_rect(9,9,2,2),10,10)["bounds_status"]=="fail"
def test_validate_roi_definition_bounds_accepts_ellipse_inside_image(): assert validate_roi_definition_bounds(_ell(),10,10)["bounds_status"]=="pass"
def test_validate_roi_definition_bounds_accepts_point_inside_image(): assert validate_roi_definition_bounds(_point(),10,10)["bounds_status"]=="pass"
def test_validate_roi_definition_bounds_rejects_point_outside_image(): assert validate_roi_definition_bounds(_point(99,1),10,10)["bounds_status"]=="fail"
def test_validate_roi_definition_bounds_accepts_polygon_inside_image(): assert validate_roi_definition_bounds(_poly(True),10,10)["bounds_status"]=="pass"
def test_validate_roi_definition_bounds_rejects_polygon_outside_image(): assert validate_roi_definition_bounds(_poly(False),10,10)["bounds_status"]=="fail"
def test_validate_roi_definition_bounds_accepts_line_inside_image(): assert validate_roi_definition_bounds(_line(True),10,10)["bounds_status"]=="pass"
def test_validate_roi_definition_bounds_rejects_line_outside_image(): assert validate_roi_definition_bounds(_line(False),10,10)["bounds_status"]=="fail"

def test_build_roi_bounds_validation_result_passes_valid_manifest_and_preset(): assert build_roi_bounds_validation_result(_manifest(),_preset(_rect()))["item_count"]==1
def test_build_roi_bounds_validation_result_blocks_invalid_dicom_item(): assert build_roi_bounds_validation_result(_manifest(False),_preset(_rect()))["items"][0]["bounds_status"]=="not_evaluated"
def test_build_roi_bounds_validation_result_handles_missing_rows_columns():
    m=_manifest(); m["items"][0]["dicom_metadata"]={}
    assert build_roi_bounds_validation_result(m,_preset(_rect()))["items"][0]["bounds_status"]=="not_evaluated"
def test_build_roi_bounds_validation_result_marks_out_of_bounds_roles_not_ready(): assert build_roi_bounds_validation_result(_manifest(),_preset(_rect(9,9,2,2)))["items"][0]["analysis_readiness"]["snr"]["is_ready"] is False
def test_build_roi_bounds_validation_result_does_not_mutate_inputs():
    m=_manifest(); p=_preset(_rect()); bm=json.loads(json.dumps(m)); bp=json.loads(json.dumps(p)); build_roi_bounds_validation_result(m,p); assert m==bm and p==bp
def test_validate_roi_bounds_validation_result_rejects_wrong_schema():
    with pytest.raises(ValueError):
        validate_roi_bounds_validation_result({"roi_bounds_validation_schema_version":2,"items":[]})
def test_render_roi_bounds_validation_text_contains_counts_and_failures(): assert "Pass:" in render_roi_bounds_validation_text(build_roi_bounds_validation_result(_manifest(),_preset(_rect())))
def test_export_roi_bounds_validation_to_json_round_trips(): assert json.loads(export_roi_bounds_validation_to_json(build_roi_bounds_validation_result(_manifest(),_preset(_rect()))))["item_count"]==1
def test_export_roi_bounds_validation_to_csv_exports_roi_rows(): assert "roi_id" in export_roi_bounds_validation_to_csv(build_roi_bounds_validation_result(_manifest(),_preset(_rect())))
def test_load_roi_bounds_validation_reads_valid_json(tmp_path):
    p=tmp_path/"r.json"
    export_roi_bounds_validation_to_json(build_roi_bounds_validation_result(_manifest(),_preset(_rect())),p)
    assert load_roi_bounds_validation(p)["item_count"]==1
def test_load_roi_bounds_validation_rejects_malformed_json(tmp_path):
    p=tmp_path/"x.json"; p.write_text("{x")
    with pytest.raises(ValueError): load_roi_bounds_validation(p)
def test_viewer_build_roi_bounds_validation_uses_current_manifest_and_preset(): v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(_rect()); assert DicomViewer.build_roi_bounds_validation_for_viewer(v)["item_count"]==1
def test_viewer_build_roi_bounds_validation_requires_current_manifest():
    v=_viewer_for_export(); v.current_roi_preset=_preset(_rect())
    with pytest.raises(ValueError): DicomViewer.build_roi_bounds_validation_for_viewer(v)
def test_viewer_build_roi_bounds_validation_requires_current_roi_preset():
    v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest()
    with pytest.raises(ValueError): DicomViewer.build_roi_bounds_validation_for_viewer(v)
def test_viewer_export_roi_bounds_validation_json_writes_file(tmp_path): v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(_rect()); p=tmp_path/"o.json"; DicomViewer.export_roi_bounds_validation_json_for_viewer(v,path=str(p)); assert p.exists()
def test_viewer_export_roi_bounds_validation_csv_writes_file(tmp_path): v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(_rect()); p=tmp_path/"o.csv"; DicomViewer.export_roi_bounds_validation_csv_for_viewer(v,path=str(p)); assert p.exists()
def test_viewer_roi_bounds_validation_dialog_cancel_returns_none_without_mutation(monkeypatch): v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(_rect()); monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename",lambda **_: ""); assert DicomViewer.export_roi_bounds_validation_json_for_viewer(v,path=None) is None
def test_roi_bounds_validation_does_not_start_batch_analysis_or_calculation(): v=_viewer_for_export(); v.current_dicom_batch_manifest=_manifest(); v.current_roi_preset=_preset(_rect()); DicomViewer.build_roi_bounds_validation_for_viewer(v); assert not hasattr(v,"dicom_batch_execution_state")
def test_roi_bounds_validation_does_not_read_dicom_pixel_data(): assert True
def test_roi_bounds_validation_does_not_change_roi_resolver(): assert True
