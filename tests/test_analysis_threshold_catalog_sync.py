from __future__ import annotations
import json, pytest
from analysis_threshold_catalog_sync import *
from analysis_threshold_catalog import build_empty_threshold_catalog, add_threshold_config_to_catalog, set_selected_threshold_config_id
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export
from tests.test_analysis_threshold_integration import _normalized_export_fixture

def _cfg(name="cfg",rid="r1"):
    return {"threshold_schema_version":1,"name":name,"description":"d","rules":[{"rule_id":rid,"analysis_type":"snr","metric":"snr","operator":">=","threshold":2.0,"severity":"fail","label":"SNR"}]}

def _cat():
    return set_selected_threshold_config_id(add_threshold_config_to_catalog(build_empty_threshold_catalog(),_cfg(),"a"),"a")

def test_build_threshold_catalog_sync_status_synced(): assert build_threshold_catalog_sync_status(_cfg(),_cat())["status"]=="synced"
def test_build_threshold_catalog_sync_status_dirty(): assert build_threshold_catalog_sync_status(_cfg("x"),_cat())["status"]=="dirty"
def test_build_threshold_catalog_sync_status_no_catalog(): assert build_threshold_catalog_sync_status(_cfg(),None)["status"]=="no_catalog"
def test_build_threshold_catalog_sync_status_no_selected_config(): assert build_threshold_catalog_sync_status(_cfg(), add_threshold_config_to_catalog(build_empty_threshold_catalog(),_cfg(),"a"))["status"] in {"no_selected_config","unsynced_current_config"}
def test_build_threshold_catalog_sync_status_rejects_missing_selected_config():
    with pytest.raises(ValueError): build_threshold_catalog_sync_status(_cfg(), _cat(), selected_config_id="x")
def test_catalog_sync_helpers_do_not_mutate_inputs():
    c=_cfg(); cat=_cat(); bc=json.loads(json.dumps(c)); bt=json.loads(json.dumps(cat)); _=build_threshold_catalog_sync_status(c,cat); assert c==bc and cat==bt
def test_viewer_build_current_threshold_catalog_sync_status_synced():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v,_cat()); assert DicomViewer.build_current_threshold_catalog_sync_status(v)["status"]=="synced"
def test_viewer_build_current_threshold_catalog_sync_status_dirty_after_editor_change():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v,_cat()); DicomViewer.update_rule_in_current_threshold_config(v,"r1",{"label":"x"}); assert DicomViewer.build_current_threshold_catalog_sync_status(v)["status"]=="dirty"
def test_viewer_save_current_threshold_config_to_selected_catalog_entry_updates_catalog():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg("n")); DicomViewer.set_current_threshold_catalog(v,_cat()); DicomViewer.save_current_threshold_config_to_selected_catalog_entry(v); assert v.current_threshold_catalog["configs"]["a"]["name"]=="n"
def test_viewer_save_current_threshold_config_to_selected_catalog_entry_requires_current_config():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_catalog(v,_cat()); v.current_threshold_config=None
    with pytest.raises(ValueError): DicomViewer.save_current_threshold_config_to_selected_catalog_entry(v)
def test_viewer_save_current_threshold_config_to_selected_catalog_entry_requires_selected_config():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v,add_threshold_config_to_catalog(build_empty_threshold_catalog(),_cfg(),"a"))
    with pytest.raises(ValueError): DicomViewer.save_current_threshold_config_to_selected_catalog_entry(v)
def test_viewer_save_current_threshold_config_as_catalog_entry_adds_new_entry():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v,_cat()); DicomViewer.save_current_threshold_config_as_catalog_entry(v,"b"); assert "b" in v.current_threshold_catalog["configs"]
def test_viewer_save_current_threshold_config_as_catalog_entry_rejects_duplicate_id():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v,_cat())
    with pytest.raises(ValueError): DicomViewer.save_current_threshold_config_as_catalog_entry(v,"a")
def test_viewer_refresh_current_threshold_config_from_selected_catalog_entry_discards_unsaved_changes():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg("x")); DicomViewer.set_current_threshold_catalog(v,_cat()); DicomViewer.refresh_current_threshold_config_from_selected_catalog_entry(v); assert v.current_threshold_config["name"]=="cfg"
def test_viewer_editor_changes_do_not_auto_mutate_catalog():
    v=_viewer_for_export(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v,_cat()); b=json.loads(json.dumps(v.current_threshold_catalog)); DicomViewer.update_rule_in_current_threshold_config(v,"r1",{"label":"x"}); assert v.current_threshold_catalog==b
def test_viewer_catalog_sync_does_not_auto_insert_threshold_into_report_or_history():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg()); DicomViewer.set_current_threshold_catalog(v,_cat()); DicomViewer.save_current_threshold_config_to_selected_catalog_entry(v); assert "QC Threshold Evaluation" not in DicomViewer.render_current_analysis_report_markdown(v)
def test_catalog_sync_does_not_add_default_clinical_thresholds(): assert build_empty_threshold_catalog()["configs"]=={}
def test_catalog_sync_does_not_add_builtin_clinical_presets(): assert build_empty_threshold_catalog()["configs"]=={}
