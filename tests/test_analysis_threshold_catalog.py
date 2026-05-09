from __future__ import annotations

import json

import pytest

from analysis_threshold_catalog import *
from analysis_threshold_config import save_threshold_config
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export
from tests.test_analysis_threshold_integration import _normalized_export_fixture


def _cfg(name="cfg", rid="r1"):
    return {"threshold_schema_version": 1, "name": name, "description": "d", "rules": [{"rule_id": rid, "analysis_type": "snr", "metric": "snr", "operator": ">=", "threshold": 2.0, "severity": "fail", "label": "SNR"}]}


def test_build_empty_threshold_catalog_has_no_builtin_presets():
    c = build_empty_threshold_catalog()
    assert c["configs"] == {} and c["selected_config_id"] is None


def test_validate_threshold_catalog_accepts_valid_catalog():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    assert validate_threshold_catalog(c)["configs"]["a"]["name"] == "cfg"


def test_validate_threshold_catalog_rejects_wrong_schema_version():
    with pytest.raises(ValueError):
        validate_threshold_catalog({"threshold_catalog_schema_version": 9, "configs": {}})


def test_validate_threshold_catalog_rejects_invalid_nested_config():
    with pytest.raises(ValueError):
        validate_threshold_catalog({"threshold_catalog_schema_version": 1, "name": "", "description": "", "selected_config_id": None, "configs": {"a": {"threshold_schema_version": 1, "rules": [{}]}}})


def test_add_threshold_config_to_catalog_adds_config_without_mutating_input():
    base = build_empty_threshold_catalog()
    before = json.loads(json.dumps(base))
    out = add_threshold_config_to_catalog(base, _cfg(), "a")
    assert base == before and "a" in out["configs"]


def test_add_threshold_config_to_catalog_rejects_duplicate_config_id():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    with pytest.raises(ValueError):
        add_threshold_config_to_catalog(c, _cfg("other"), "a")


def test_update_threshold_config_in_catalog_replaces_config():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    out = update_threshold_config_in_catalog(c, "a", _cfg("updated", "r2"))
    assert out["configs"]["a"]["name"] == "updated"


def test_remove_threshold_config_from_catalog_removes_config():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    out = remove_threshold_config_from_catalog(c, "a")
    assert out["configs"] == {}


def test_get_threshold_config_from_catalog_returns_copy():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    got = get_threshold_config_from_catalog(c, "a")
    got["name"] = "x"
    assert c["configs"]["a"]["name"] == "cfg"


def test_list_threshold_catalog_entries_is_deterministic():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg("b"), "b")
    c = add_threshold_config_to_catalog(c, _cfg("a", "r2"), "a")
    assert [e["config_id"] for e in list_threshold_catalog_entries(c)] == ["a", "b"]


def test_set_selected_threshold_config_id_selects_existing_config():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    assert set_selected_threshold_config_id(c, "a")["selected_config_id"] == "a"


def test_set_selected_threshold_config_id_rejects_missing_config():
    with pytest.raises(ValueError):
        set_selected_threshold_config_id(build_empty_threshold_catalog(), "x")


def test_get_selected_threshold_config_returns_selected_copy():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    c = set_selected_threshold_config_id(c, "a")
    got = get_selected_threshold_config(c)
    got["name"] = "x"
    assert c["configs"]["a"]["name"] == "cfg"


def test_load_threshold_catalog_reads_valid_json(tmp_path):
    p = tmp_path / "c.json"
    save_threshold_catalog(add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a"), p)
    assert "a" in load_threshold_catalog(p)["configs"]


def test_load_threshold_catalog_rejects_malformed_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError):
        load_threshold_catalog(p)


def test_save_threshold_catalog_writes_deterministic_json(tmp_path):
    p = tmp_path / "c.json"
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    t = save_threshold_catalog(c, p)
    assert t == p.read_text(encoding="utf-8")


def test_import_threshold_config_file_to_catalog_validates_config(tmp_path):
    cfgp = tmp_path / "cfg.json"
    save_threshold_config(_cfg(), cfgp)
    c = import_threshold_config_file_to_catalog(build_empty_threshold_catalog(), cfgp, config_id="a")
    assert "a" in c["configs"]


def test_export_threshold_config_from_catalog_writes_config_json(tmp_path):
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    p = tmp_path / "o.json"
    export_threshold_config_from_catalog(c, "a", p)
    assert json.loads(p.read_text(encoding="utf-8"))["name"] == "cfg"


def test_build_threshold_catalog_display_model_summarizes_configs():
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    m = build_threshold_catalog_display_model(c)
    assert m["config_count"] == 1 and m["entries"][0]["rule_count"] == 1


def test_render_threshold_catalog_text_handles_empty_catalog():
    assert "No configs in catalog" in render_threshold_catalog_text(build_empty_threshold_catalog())


def test_viewer_load_threshold_catalog_for_viewer_reads_json(tmp_path):
    v = _viewer_for_export()
    p = tmp_path / "c.json"
    save_threshold_catalog(add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a"), p)
    DicomViewer.load_threshold_catalog_for_viewer(v, str(p))
    assert "a" in v.current_threshold_catalog["configs"]


def test_viewer_save_current_threshold_catalog_writes_json(tmp_path):
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_catalog(v, add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a"))
    p = tmp_path / "c.json"
    DicomViewer.save_current_threshold_catalog(v, str(p))
    assert p.exists()


def test_viewer_add_current_threshold_config_to_catalog():
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_catalog(v, build_empty_threshold_catalog())
    DicomViewer.set_current_threshold_config(v, _cfg())
    DicomViewer.add_current_threshold_config_to_catalog(v, "a")
    assert "a" in v.current_threshold_catalog["configs"]


def test_viewer_apply_selected_catalog_threshold_config_to_viewer():
    v = _viewer_for_export()
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg("sel"), "a")
    c = set_selected_threshold_config_id(c, "a")
    DicomViewer.set_current_threshold_catalog(v, c)
    DicomViewer.apply_selected_catalog_threshold_config_to_viewer(v)
    assert v.current_threshold_config["name"] == "sel"


def test_viewer_catalog_methods_require_catalog_or_config():
    v = _viewer_for_export()
    with pytest.raises(ValueError):
        DicomViewer.render_current_threshold_catalog_text(v)
    DicomViewer.set_current_threshold_catalog(v, build_empty_threshold_catalog())
    with pytest.raises(ValueError):
        DicomViewer.add_current_threshold_config_to_catalog(v)


def test_catalog_does_not_add_default_clinical_thresholds():
    c = build_empty_threshold_catalog()
    assert c["configs"] == {}


def test_viewer_build_current_threshold_catalog_display_model_creates_empty_catalog_when_missing():
    v = _viewer_for_export()
    if hasattr(v, "current_threshold_catalog"):
        v.current_threshold_catalog = None
    m = DicomViewer.build_current_threshold_catalog_display_model(v)
    assert m["config_count"] == 0 and v.current_threshold_catalog["configs"] == {}


def test_viewer_catalog_display_model_lists_configs():
    v = _viewer_for_export()
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg("a"), "a")
    c = add_threshold_config_to_catalog(c, _cfg("b", "r2"), "b")
    DicomViewer.set_current_threshold_catalog(v, c)
    m = DicomViewer.build_current_threshold_catalog_display_model(v)
    assert [e["config_id"] for e in m["entries"]] == ["a", "b"]


def test_viewer_catalog_manager_load_save_actions_use_existing_helpers(monkeypatch, tmp_path):
    v = _viewer_for_export()
    p = tmp_path / "c.json"
    save_threshold_catalog(add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a"), p)
    monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_: str(p))
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: str(tmp_path / "o.json"))
    assert DicomViewer.load_threshold_catalog_for_viewer(v)["configs"]["a"]["name"] == "cfg"
    assert DicomViewer.save_current_threshold_catalog(v) is not None


def test_viewer_catalog_manager_import_config_adds_entry(monkeypatch, tmp_path):
    v = _viewer_for_export(); DicomViewer.set_current_threshold_catalog(v, build_empty_threshold_catalog())
    p = tmp_path / "cfg.json"; save_threshold_config(_cfg(), p)
    monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_: str(p))
    DicomViewer.import_threshold_config_file_to_current_catalog(v)
    assert len(v.current_threshold_catalog["configs"]) == 1


def test_viewer_catalog_manager_export_selected_config_writes_json(monkeypatch, tmp_path):
    v = _viewer_for_export()
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    DicomViewer.set_current_threshold_catalog(v, c)
    p = tmp_path / "out.json"
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: str(p))
    DicomViewer.export_threshold_config_from_current_catalog(v, "a")
    assert json.loads(p.read_text(encoding="utf-8"))["name"] == "cfg"


def test_viewer_catalog_manager_select_config_updates_selected_id_only():
    v = _viewer_for_export()
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    DicomViewer.set_current_threshold_catalog(v, c); v.current_threshold_config = None
    DicomViewer.select_threshold_config_from_catalog(v, "a")
    assert v.current_threshold_catalog["selected_config_id"] == "a" and v.current_threshold_config is None


def test_viewer_catalog_manager_apply_selected_updates_current_threshold_config():
    v = _viewer_for_export()
    c = set_selected_threshold_config_id(add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg("sel"), "a"), "a")
    DicomViewer.set_current_threshold_catalog(v, c)
    DicomViewer.apply_selected_catalog_threshold_config_to_viewer(v)
    assert v.current_threshold_config["name"] == "sel"


def test_viewer_catalog_manager_remove_selected_config():
    v = _viewer_for_export()
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    DicomViewer.set_current_threshold_catalog(v, c)
    DicomViewer.remove_threshold_config_from_current_catalog(v, "a")
    assert v.current_threshold_catalog["configs"] == {}


def test_viewer_catalog_manager_cancelled_dialogs_do_not_mutate_catalog(monkeypatch):
    v = _viewer_for_export()
    c = add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a")
    DicomViewer.set_current_threshold_catalog(v, c)
    before = json.loads(json.dumps(v.current_threshold_catalog))
    monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_: "")
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: "")
    assert DicomViewer.load_threshold_catalog_for_viewer(v) is None
    assert DicomViewer.save_current_threshold_catalog(v) is None
    assert DicomViewer.import_threshold_config_file_to_current_catalog(v) is None
    assert DicomViewer.export_threshold_config_from_current_catalog(v, "a") is None
    assert v.current_threshold_catalog == before


def test_viewer_catalog_manager_does_not_auto_insert_threshold_into_report_or_history():
    v = _viewer_for_export(); v.analysis_last_run_normalized = _normalized_export_fixture()
    c = set_selected_threshold_config_id(add_threshold_config_to_catalog(build_empty_threshold_catalog(), _cfg(), "a"), "a")
    DicomViewer.set_current_threshold_catalog(v, c)
    DicomViewer.apply_selected_catalog_threshold_config_to_viewer(v)
    assert "QC Threshold Evaluation" not in DicomViewer.render_current_analysis_report_markdown(v)
    assert "threshold_evaluation" not in DicomViewer.build_current_analysis_history_record(v)


def test_viewer_catalog_manager_does_not_add_builtin_clinical_presets():
    v = _viewer_for_export()
    DicomViewer.build_current_threshold_catalog_display_model(v)
    assert v.current_threshold_catalog["configs"] == {}


def test_show_threshold_catalog_manager_does_not_mutate_analysis_results(monkeypatch):
    class Dummy:
        def title(self, *_): pass
        def geometry(self, *_): pass
        def destroy(self): pass
    class W:
        def pack(self, *_, **__): pass
        def bind(self, *_, **__): pass
        def delete(self, *_, **__): pass
        def insert(self, *_, **__): pass
        def curselection(self): return ()
        def configure(self, *_, **__): pass
    monkeypatch.setattr("dicom_viewer.tk.Toplevel", lambda *_, **__: Dummy())
    monkeypatch.setattr("dicom_viewer.ttk.Frame", lambda *_, **__: W())
    monkeypatch.setattr("dicom_viewer.tk.Listbox", lambda *_, **__: W())
    monkeypatch.setattr("dicom_viewer.tk.Text", lambda *_, **__: W())
    monkeypatch.setattr("dicom_viewer.ttk.Button", lambda *_, **__: W())
    monkeypatch.setattr("dicom_viewer.ttk.Entry", lambda *_, **__: W())
    monkeypatch.setattr("dicom_viewer.tk.StringVar", lambda *_, value='', **__: type("SV",(),{"get":lambda self:value,"set":lambda self,v:None})())
    v = _viewer_for_export(); v.analysis_last_run_normalized = _normalized_export_fixture()
    before = json.loads(json.dumps(v.analysis_last_run_normalized))
    DicomViewer.show_threshold_catalog_manager(v)
    assert v.analysis_last_run_normalized == before
