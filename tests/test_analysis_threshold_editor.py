from __future__ import annotations

import json

import pytest

from analysis_threshold_editor import (
    add_threshold_rule,
    duplicate_threshold_rule,
    get_threshold_rule,
    list_threshold_rules,
    remove_threshold_rule,
    reorder_threshold_rules,
    update_threshold_rule,
)
from analysis_thresholds import evaluate_analysis_thresholds
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _normalized_export_fixture, _viewer_for_export


def _cfg():
    return {
        "threshold_schema_version": 1,
        "name": "editor",
        "description": "d",
        "rules": [{"rule_id": "r1", "analysis_type": "snr", "metric": "snr", "operator": ">=", "threshold": 2.0, "severity": "fail", "label": "SNR"}],
    }


def _rule(rule_id: str = "r2"):
    return {"rule_id": rule_id, "analysis_type": "cnr", "metric": "cnr", "operator": ">=", "threshold": 1.0, "severity": "warn", "label": "CNR"}


def test_add_threshold_rule_returns_new_config_without_mutating_input():
    config = _cfg()
    before = json.loads(json.dumps(config))
    out = add_threshold_rule(config, _rule())
    assert config == before
    assert len(out["rules"]) == 2


def test_add_threshold_rule_rejects_duplicate_rule_id():
    with pytest.raises(ValueError):
        add_threshold_rule(_cfg(), _rule("r1"))


def test_add_threshold_rule_rejects_invalid_rule():
    bad = _rule()
    bad["operator"] = "in"
    with pytest.raises(ValueError):
        add_threshold_rule(_cfg(), bad)


def test_update_threshold_rule_changes_selected_fields():
    out = update_threshold_rule(_cfg(), "r1", {"threshold": 3.5, "label": "updated"})
    got = get_threshold_rule(out, "r1")
    assert got["threshold"] == 3.5 and got["label"] == "updated"


def test_update_threshold_rule_rejects_missing_rule():
    with pytest.raises(ValueError):
        update_threshold_rule(_cfg(), "x", {"threshold": 9})


def test_update_threshold_rule_rejects_invalid_operator():
    with pytest.raises(ValueError):
        update_threshold_rule(_cfg(), "r1", {"operator": "??"})


def test_remove_threshold_rule_removes_rule():
    out = remove_threshold_rule(_cfg(), "r1")
    assert out["rules"] == []


def test_remove_threshold_rule_rejects_missing_rule():
    with pytest.raises(ValueError):
        remove_threshold_rule(_cfg(), "x")


def test_reorder_threshold_rules_changes_order():
    c = add_threshold_rule(_cfg(), _rule("r2"))
    out = reorder_threshold_rules(c, ["r2", "r1"])
    assert [r["rule_id"] for r in out["rules"]] == ["r2", "r1"]


def test_reorder_threshold_rules_rejects_missing_or_extra_ids():
    c = add_threshold_rule(_cfg(), _rule("r2"))
    with pytest.raises(ValueError):
        reorder_threshold_rules(c, ["r1"])


def test_duplicate_threshold_rule_copies_rule_with_new_id():
    out = duplicate_threshold_rule(_cfg(), "r1", "r1_copy")
    assert [r["rule_id"] for r in out["rules"]] == ["r1", "r1_copy"]


def test_duplicate_threshold_rule_rejects_duplicate_new_id():
    with pytest.raises(ValueError):
        duplicate_threshold_rule(_cfg(), "r1", "r1")


def test_get_threshold_rule_returns_copy():
    c = _cfg()
    rule = get_threshold_rule(c, "r1")
    rule["threshold"] = 99
    assert c["rules"][0]["threshold"] == 2.0


def test_list_threshold_rules_returns_copies():
    c = _cfg()
    rules = list_threshold_rules(c)
    rules[0]["threshold"] = 99
    assert c["rules"][0]["threshold"] == 2.0


def test_editor_helpers_preserve_config_metadata():
    c = _cfg()
    c["description"] = "kept"
    out = add_threshold_rule(c, _rule())
    assert out["name"] == "editor" and out["description"] == "kept"


def test_viewer_add_rule_to_current_threshold_config_updates_selected_config():
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    DicomViewer.add_rule_to_current_threshold_config(v, _rule())
    assert len(v.current_threshold_config["rules"]) == 2 and v.current_threshold_config_display["rule_count"] == 2


def test_viewer_update_rule_in_current_threshold_config_updates_display_text():
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    DicomViewer.update_rule_in_current_threshold_config(v, "r1", {"threshold": 4.5})
    assert "4.5" in DicomViewer.render_current_threshold_config_text(v)


def test_viewer_remove_rule_from_current_threshold_config():
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    DicomViewer.remove_rule_from_current_threshold_config(v, "r1")
    assert "No rules configured" in DicomViewer.render_current_threshold_config_text(v)


def test_viewer_editor_methods_require_current_config():
    v = _viewer_for_export()
    v.current_threshold_config = None
    with pytest.raises(ValueError):
        DicomViewer.list_current_threshold_rules(v)


def test_editor_does_not_add_default_clinical_thresholds():
    cfg = {"threshold_schema_version": 1, "name": "empty", "description": "", "rules": []}
    out = add_threshold_rule(cfg, _rule("only"))
    assert [r["rule_id"] for r in out["rules"]] == ["only"]
    ev = evaluate_analysis_thresholds(_normalized_export_fixture(), out)
    assert ev["config_name"] == "empty"
