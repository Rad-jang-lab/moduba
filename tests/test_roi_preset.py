from __future__ import annotations
import json, pytest
from roi_preset import *
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export

def _rect():
    return {"roi_id":"r1","label":"L","roi_type":"rectangle","coordinates":{"x":1,"y":2,"width":3,"height":4},"analysis_roles":["signal","noise"],"notes":""}

def test_build_empty_roi_preset_has_no_rois(): assert build_empty_roi_preset()["roi_definitions"]==[]
def test_validate_roi_preset_accepts_valid_rectangle(): assert validate_roi_preset(build_roi_preset_from_roi_definitions([_rect()]))["roi_definitions"][0]["roi_id"]=="r1"
def test_validate_roi_preset_rejects_wrong_schema_version():
    with pytest.raises(ValueError): validate_roi_preset({"roi_preset_schema_version":2,"roi_definitions":[]})
def test_validate_roi_preset_rejects_duplicate_roi_ids():
    with pytest.raises(ValueError): validate_roi_preset(build_roi_preset_from_roi_definitions([_rect(),_rect()]))
def test_validate_roi_preset_rejects_unsupported_roi_type():
    r=_rect(); r['roi_type']='x'
    with pytest.raises(ValueError): build_roi_preset_from_roi_definitions([r])
def test_validate_roi_preset_rejects_unsupported_role():
    r=_rect(); r['analysis_roles']=['x']
    with pytest.raises(ValueError): build_roi_preset_from_roi_definitions([r])
def test_validate_roi_preset_rejects_non_finite_coordinates():
    r=_rect(); r['coordinates']['x']=float('inf')
    with pytest.raises(ValueError): build_roi_preset_from_roi_definitions([r])
def test_validate_roi_preset_rejects_short_polygon():
    r={"roi_id":"p","label":"","roi_type":"polygon","coordinates":{"points":[{"x":1,"y":1},{"x":2,"y":2}]},"analysis_roles":["uniformity"],"notes":""}
    with pytest.raises(ValueError): build_roi_preset_from_roi_definitions([r])
def test_validate_roi_preset_rejects_short_line():
    r={"roi_id":"l","label":"","roi_type":"line","coordinates":{"points":[{"x":1,"y":1}]},"analysis_roles":["mtf_edge"],"notes":""}
    with pytest.raises(ValueError): build_roi_preset_from_roi_definitions([r])
def test_export_roi_preset_to_json_round_trips(): assert json.loads(export_roi_preset_to_json(build_roi_preset_from_roi_definitions([_rect()])))['roi_preset_schema_version']==1
def test_load_roi_preset_reads_valid_json(tmp_path):
    p=tmp_path/'r.json'; export_roi_preset_to_json(build_roi_preset_from_roi_definitions([_rect()]),p); assert load_roi_preset(p)['name']
def test_load_roi_preset_rejects_malformed_json(tmp_path):
    p=tmp_path/'x.json'; p.write_text('{x');
    with pytest.raises(ValueError): load_roi_preset(p)
def test_render_roi_preset_text_contains_roles_and_counts():
    t=render_roi_preset_text(build_roi_preset_from_roi_definitions([_rect()])); assert 'ROI Count' in t and 'signal' in t
def test_roi_preset_helpers_do_not_mutate_inputs():
    r=[_rect()]; b=json.loads(json.dumps(r)); build_roi_preset_from_roi_definitions(r); assert r==b
def test_check_roi_preset_analysis_readiness_snr(): assert check_roi_preset_analysis_readiness(build_roi_preset_from_roi_definitions([_rect()]),'snr')['is_ready']
def test_check_roi_preset_analysis_readiness_cnr():
    rs=[{"roi_id":"a","label":"","roi_type":"point","coordinates":{"x":1,"y":1},"analysis_roles":["region_a"],"notes":""},{"roi_id":"b","label":"","roi_type":"point","coordinates":{"x":2,"y":2},"analysis_roles":["region_b","background"],"notes":""}]
    assert check_roi_preset_analysis_readiness(build_roi_preset_from_roi_definitions(rs),'cnr')['is_ready']
def test_check_roi_preset_analysis_readiness_uniformity():
    r={"roi_id":"u","label":"","roi_type":"ellipse","coordinates":{"x":1,"y":1,"width":2,"height":2},"analysis_roles":["uniformity"],"notes":""}
    assert check_roi_preset_analysis_readiness(build_roi_preset_from_roi_definitions([r]),'uniformity')['is_ready']
def test_check_roi_preset_analysis_readiness_mtf():
    r={"roi_id":"m","label":"","roi_type":"line","coordinates":{"points":[{"x":1,"y":1},{"x":2,"y":2}]},"analysis_roles":["mtf_edge"],"notes":""}
    assert check_roi_preset_analysis_readiness(build_roi_preset_from_roi_definitions([r]),'mtf')['is_ready']
def test_viewer_load_roi_preset_for_viewer_reads_json(tmp_path):
    p=tmp_path/'r.json'; export_roi_preset_to_json(build_roi_preset_from_roi_definitions([_rect()]),p); v=_viewer_for_export(); assert DicomViewer.load_roi_preset_for_viewer(v,str(p))['roi_preset_schema_version']==1
def test_viewer_save_current_roi_preset_writes_json(tmp_path):
    p=tmp_path/'r.json'; v=_viewer_for_export(); v.current_roi_preset=build_roi_preset_from_roi_definitions([_rect()]); DicomViewer.save_current_roi_preset(v,str(p)); assert p.exists()
def test_viewer_roi_preset_dialog_cancel_returns_none_without_mutation(monkeypatch):
    v=_viewer_for_export(); base=getattr(v,'current_threshold_config',None); monkeypatch.setattr('dicom_viewer.filedialog.askopenfilename', lambda **_: ''); assert DicomViewer.load_roi_preset_for_viewer(v) is None; assert getattr(v,'current_threshold_config',None)==base
def test_roi_preset_does_not_start_batch_analysis_or_calculation():
    v=_viewer_for_export(); v.current_roi_preset=build_roi_preset_from_roi_definitions([_rect()]); DicomViewer.render_current_roi_preset_text(v); assert not hasattr(v,'dicom_batch_execution_state')
