from __future__ import annotations

import json

import pytest

from analysis_threshold_config import (
    build_empty_threshold_config,
    build_threshold_config_display_model,
    load_threshold_config,
    render_threshold_config_text,
    save_threshold_config,
)
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _normalized_export_fixture, _viewer_for_export


def _cfg():
    return {"threshold_schema_version":1,"name":"cfg","description":"d","rules":[{"rule_id":"snr_min","analysis_type":"snr","metric":"snr","operator":">=","threshold":2.0,"severity":"fail","label":"SNR min"}]}


def test_build_empty_threshold_config_has_no_default_clinical_rules():
    c=build_empty_threshold_config(); assert c["rules"]==[]

def test_load_threshold_config_validates_json_config(tmp_path):
    p=tmp_path/"c.json"; p.write_text(json.dumps(_cfg()),encoding="utf-8")
    assert load_threshold_config(p)["name"]=="cfg"

def test_load_threshold_config_rejects_invalid_json(tmp_path):
    p=tmp_path/"c.json"; p.write_text("{bad}",encoding="utf-8")
    with pytest.raises(ValueError): load_threshold_config(p)

def test_load_threshold_config_rejects_invalid_schema(tmp_path):
    p=tmp_path/"c.json"; p.write_text(json.dumps({"threshold_schema_version":9}),encoding="utf-8")
    with pytest.raises(ValueError): load_threshold_config(p)

def test_save_threshold_config_writes_deterministic_json(tmp_path):
    p=tmp_path/"c.json"; t=save_threshold_config(_cfg(),p)
    assert p.read_text(encoding="utf-8")==t

def test_threshold_config_display_model_summarizes_rules():
    m=build_threshold_config_display_model(_cfg()); assert m["rule_count"]==1

def test_render_threshold_config_text_handles_empty_rules():
    assert "No rules configured" in render_threshold_config_text(build_empty_threshold_config())

def test_render_threshold_config_text_lists_rules():
    assert "snr_min" in render_threshold_config_text(_cfg())

def test_threshold_config_helpers_do_not_mutate_input():
    c=_cfg(); before=json.loads(json.dumps(c)); _=build_threshold_config_display_model(c); assert c==before

def test_viewer_set_current_threshold_config_validates_config():
    v=_viewer_for_export(); out=DicomViewer.set_current_threshold_config(v,_cfg()); assert out["name"]=="cfg"

def test_viewer_load_threshold_config_for_viewer_reads_json(tmp_path):
    p=tmp_path/"c.json"; p.write_text(json.dumps(_cfg()),encoding="utf-8"); v=_viewer_for_export(); assert DicomViewer.load_threshold_config_for_viewer(v,p)["name"]=="cfg"

def test_viewer_load_threshold_config_cancel_returns_none(monkeypatch):
    v=_viewer_for_export(); monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_k: ""); assert DicomViewer.load_threshold_config_for_viewer(v,None) is None

def test_viewer_save_current_threshold_config_writes_json(tmp_path):
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); p=tmp_path/"c.json"; DicomViewer.save_current_threshold_config(v,p); assert "snr_min" in p.read_text(encoding="utf-8")

def test_viewer_evaluate_current_analysis_with_selected_threshold_config():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg()); out=DicomViewer.evaluate_current_analysis_with_selected_threshold_config(v,generated_at="2026-01-01T00:00:00+00:00"); assert out["summary"]["rule_count"]==1

def test_viewer_selected_threshold_evaluation_rejects_missing_config():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture();
    with pytest.raises(ValueError): DicomViewer.evaluate_current_analysis_with_selected_threshold_config(v)

def test_viewer_threshold_preview_does_not_mutate_results_or_config(monkeypatch):
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    before_res=json.loads(json.dumps(v.analysis_last_run_normalized)); before_cfg=json.loads(json.dumps(v.current_threshold_config))
    class F:
        def __init__(self,*a,**k): pass
        def title(self,*a,**k): pass
        def geometry(self,*a,**k): pass
        def pack(self,*a,**k): pass
        def insert(self,*a,**k): pass
        def configure(self,*a,**k): pass
    monkeypatch.setattr("dicom_viewer.tk.Toplevel", F); monkeypatch.setattr("dicom_viewer.ttk.Frame", F); monkeypatch.setattr("dicom_viewer.tk.Text", F)
    _=DicomViewer.show_current_threshold_evaluation_preview(v)
    assert v.analysis_last_run_normalized==before_res and v.current_threshold_config==before_cfg
