from __future__ import annotations

import json

import pytest

from analysis_threshold_editor_display import *
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export
from tests.test_analysis_threshold_integration import _normalized_export_fixture
from analysis_threshold_catalog import add_threshold_config_to_catalog, build_empty_threshold_catalog


def _cfg():
    return {"threshold_schema_version": 1, "name": "cfg", "description": "d", "rules": [{"rule_id": "r1", "analysis_type": "snr", "metric": "snr", "operator": ">=", "threshold": 2.0, "severity": "fail", "label": "SNR"}]}


def test_build_threshold_editor_display_model_lists_rules():
    m = build_threshold_editor_display_model(_cfg())
    assert m["rule_count"] == 1 and m["rules"][0]["rule_id"] == "r1"


def test_build_threshold_editor_display_model_marks_selected_rule():
    m = build_threshold_editor_display_model(_cfg(), selected_rule_id="r1")
    assert m["rules"][0]["is_selected"] is True


def test_build_threshold_editor_display_model_rejects_missing_selected_rule():
    with pytest.raises(ValueError):
        build_threshold_editor_display_model(_cfg(), selected_rule_id="x")


def test_build_threshold_editor_display_model_handles_empty_config():
    c = {"threshold_schema_version": 1, "name": "e", "description": "", "rules": []}
    assert build_threshold_editor_display_model(c)["rule_count"] == 0


def test_render_threshold_rule_detail_text_contains_rule_fields():
    t = render_threshold_rule_detail_text(_cfg()["rules"][0])
    assert "Rule ID:" in t and "Severity:" in t


def test_render_threshold_editor_text_handles_empty_rules():
    c = {"threshold_schema_version": 1, "name": "e", "description": "", "rules": []}
    assert "No rules configured" in render_threshold_editor_text(c)


def test_editor_display_helpers_do_not_mutate_config():
    c = _cfg(); b = json.loads(json.dumps(c)); _ = build_threshold_editor_display_model(c); assert c == b


def test_viewer_build_current_threshold_editor_display_model_requires_current_config():
    v = _viewer_for_export(); v.current_threshold_config = None
    with pytest.raises(ValueError): DicomViewer.build_current_threshold_editor_display_model(v)


def test_viewer_build_current_threshold_editor_display_model_lists_current_rules():
    v = _viewer_for_export(); DicomViewer.set_current_threshold_config(v, _cfg())
    assert DicomViewer.build_current_threshold_editor_display_model(v)["rule_count"] == 1


def test_viewer_editor_add_rule_updates_display_model():
    v = _viewer_for_export(); DicomViewer.set_current_threshold_config(v, _cfg())
    DicomViewer.add_rule_to_current_threshold_config(v, {"rule_id":"r2","analysis_type":"cnr","metric":"cnr","operator":">=","threshold":1.0,"severity":"warn","label":"CNR"})
    assert DicomViewer.build_current_threshold_editor_display_model(v)["rule_count"] == 2


def test_viewer_editor_update_rule_updates_display_model():
    v = _viewer_for_export(); DicomViewer.set_current_threshold_config(v, _cfg()); DicomViewer.update_rule_in_current_threshold_config(v,"r1",{"label":"u"})
    assert DicomViewer.get_current_threshold_rule(v,"r1")["label"] == "u"


def test_viewer_editor_remove_rule_updates_display_model():
    v = _viewer_for_export(); DicomViewer.set_current_threshold_config(v, _cfg()); DicomViewer.remove_rule_from_current_threshold_config(v,"r1")
    assert DicomViewer.build_current_threshold_editor_display_model(v)["rule_count"] == 0


def test_viewer_editor_duplicate_rule_updates_display_model():
    v = _viewer_for_export(); DicomViewer.set_current_threshold_config(v, _cfg()); DicomViewer.duplicate_rule_in_current_threshold_config(v,"r1","r2")
    assert DicomViewer.build_current_threshold_editor_display_model(v)["rule_count"] == 2


def test_viewer_editor_reorder_rule_updates_display_model():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.add_rule_to_current_threshold_config(v,{"rule_id":"r2","analysis_type":"cnr","metric":"cnr","operator":">=","threshold":1.0,"severity":"warn","label":"CNR"})
    DicomViewer.reorder_rules_in_current_threshold_config(v,["r2","r1"])
    assert DicomViewer.list_current_threshold_rules(v)[0]["rule_id"] == "r2"


def test_viewer_editor_does_not_mutate_catalog_automatically():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v, add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a"))
    before=json.loads(json.dumps(v.current_threshold_catalog)); DicomViewer.update_rule_in_current_threshold_config(v,"r1",{"label":"x"})
    assert v.current_threshold_catalog == before


def test_viewer_editor_does_not_auto_insert_threshold_into_report_or_history():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.update_rule_in_current_threshold_config(v,"r1",{"label":"x"})
    assert "QC Threshold Evaluation" not in DicomViewer.render_current_analysis_report_markdown(v)
    assert "threshold_evaluation" not in DicomViewer.build_current_analysis_history_record(v)


def test_show_threshold_config_editor_uses_existing_editor_methods(monkeypatch):
    class D: 
        def title(self,*_): pass
        def geometry(self,*_): pass
        def destroy(self): pass
    class W:
        def pack(self,*_,**__): pass
        def bind(self,*_,**__): pass
        def delete(self,*_,**__): pass
        def insert(self,*_,**__): pass
        def curselection(self): return ()
        def configure(self,*_,**__): pass
        def grid(self,*_,**__): pass
    monkeypatch.setattr("dicom_viewer.tk.Toplevel", lambda *_,**__: D())
    monkeypatch.setattr("dicom_viewer.ttk.Frame", lambda *_,**__: W())
    monkeypatch.setattr("dicom_viewer.tk.Listbox", lambda *_,**__: W())
    monkeypatch.setattr("dicom_viewer.tk.Text", lambda *_,**__: W())
    monkeypatch.setattr("dicom_viewer.ttk.Button", lambda *_,**__: W())
    monkeypatch.setattr("dicom_viewer.ttk.Label", lambda *_,**__: W())
    monkeypatch.setattr("dicom_viewer.ttk.Entry", lambda *_,**__: W())
    monkeypatch.setattr("dicom_viewer.tk.StringVar", lambda *_, value='', **__: type("SV",(),{"get":lambda self:value,"set":lambda self,v:None})())
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg())
    assert DicomViewer.show_threshold_config_editor(v)["rule_count"] == 1


def test_editor_ux_does_not_add_default_clinical_thresholds():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,{"threshold_schema_version":1,"name":"e","description":"","rules":[]})
    assert DicomViewer.build_current_threshold_editor_display_model(v)["rule_count"] == 0
