from __future__ import annotations

import json

import pytest

from analysis_thresholds import (
    evaluate_analysis_thresholds,
    render_threshold_evaluation_text,
    validate_threshold_config,
)
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _normalized_export_fixture, _viewer_for_export


def _config(severity: str = "fail") -> dict:
    return {
        "threshold_schema_version": 1,
        "name": "cfg",
        "description": "d",
        "rules": [
            {"rule_id": "snr_min", "analysis_type": "snr", "metric": "snr", "operator": ">=", "threshold": 2.0, "severity": severity, "label": "SNR min"},
            {"rule_id": "mtf50_min", "analysis_type": "mtf", "metric": "mtf50", "operator": ">=", "threshold": 0.2, "severity": "fail", "label": "MTF50 min"},
        ],
    }


def test_validate_threshold_config_accepts_valid_config():
    assert validate_threshold_config(_config())["name"] == "cfg"


def test_validate_threshold_config_rejects_missing_schema_version():
    c = _config(); c.pop("threshold_schema_version")
    with pytest.raises(ValueError):
        validate_threshold_config(c)


def test_validate_threshold_config_rejects_duplicate_rule_ids():
    c = _config(); c["rules"].append(dict(c["rules"][0]))
    with pytest.raises(ValueError):
        validate_threshold_config(c)


def test_validate_threshold_config_rejects_unsupported_operator():
    c = _config(); c["rules"][0]["operator"] = "~="
    with pytest.raises(ValueError):
        validate_threshold_config(c)


def test_validate_threshold_config_rejects_non_finite_threshold():
    c = _config(); c["rules"][0]["threshold"] = float("nan")
    with pytest.raises(ValueError):
        validate_threshold_config(c)


def test_evaluate_thresholds_passes_when_metrics_meet_rules():
    c = _config()
    c["rules"] = [c["rules"][0]]
    out = evaluate_analysis_thresholds(_normalized_export_fixture(), c, generated_at="2026-01-01T00:00:00+00:00")
    assert out["overall_status"] == "pass"


def test_evaluate_thresholds_fails_when_fail_rule_misses_threshold():
    c = _config(); c["rules"][0]["threshold"] = 9.0
    out = evaluate_analysis_thresholds(_normalized_export_fixture(), c, generated_at="2026-01-01T00:00:00+00:00")
    assert out["overall_status"] == "fail"


def test_evaluate_thresholds_warns_when_warn_rule_misses_threshold():
    c = _config(severity="warn"); c["rules"] = [c["rules"][0]]; c["rules"][0]["threshold"] = 9.0
    out = evaluate_analysis_thresholds(_normalized_export_fixture(), c, generated_at="2026-01-01T00:00:00+00:00")
    assert out["overall_status"] == "warn"


def test_evaluate_thresholds_not_evaluated_for_missing_analysis():
    c = _config(); c["rules"] = [{"rule_id":"x","analysis_type":"abc","metric":"m","operator":">=","threshold":1.0,"severity":"fail","label":"l"}]
    out = evaluate_analysis_thresholds(_normalized_export_fixture(), c)
    assert out["results"][0]["status"] == "not_evaluated"


def test_evaluate_thresholds_not_evaluated_for_missing_metric():
    c = _config(); c["rules"] = [{"rule_id":"x","analysis_type":"snr","metric":"unknown","operator":">=","threshold":1.0,"severity":"fail","label":"l"}]
    out = evaluate_analysis_thresholds(_normalized_export_fixture(), c)
    assert out["results"][0]["status"] == "not_evaluated"


def test_evaluate_thresholds_not_evaluated_for_invalid_analysis_result():
    out = evaluate_analysis_thresholds(_normalized_export_fixture(), {"threshold_schema_version":1,"name":"n","description":"d","rules":[{"rule_id":"m","analysis_type":"mtf","metric":"mtf50","operator":">=","threshold":0.1,"severity":"fail","label":"l"}]})
    assert out["results"][0]["status"] == "not_evaluated"


def test_evaluate_thresholds_rejects_none_normalized_results():
    with pytest.raises(ValueError):
        evaluate_analysis_thresholds(None, _config())


def test_evaluate_thresholds_does_not_mutate_normalized_results():
    fixture = _normalized_export_fixture(); before = json.loads(json.dumps(fixture))
    _ = evaluate_analysis_thresholds(fixture, _config())
    assert fixture == before


def test_evaluate_thresholds_uses_timezone_aware_generated_at():
    out = evaluate_analysis_thresholds(_normalized_export_fixture(), _config())
    assert "+" in out["generated_at"] or out["generated_at"].endswith("Z")


def test_render_threshold_evaluation_text_contains_summary_and_rules():
    text = render_threshold_evaluation_text(evaluate_analysis_thresholds(_normalized_export_fixture(), _config(), generated_at="2026-01-01T00:00:00+00:00"))
    assert "Overall:" in text and "snr_min" in text


def test_viewer_evaluate_current_analysis_thresholds_uses_normalized_cache():
    viewer = _viewer_for_export(); viewer.analysis_last_run_normalized = _normalized_export_fixture()
    out = DicomViewer.evaluate_current_analysis_thresholds(viewer, _config(), generated_at="2026-01-01T00:00:00+00:00")
    assert out["summary"]["rule_count"] == 2


def test_viewer_evaluate_current_analysis_thresholds_builds_cache_from_raw_when_needed():
    viewer = _viewer_for_export(); viewer.analysis_last_run = {"snr": {"status": "success", "result": 3.1, "signal_roi_id": "s", "noise_roi_id": "n"}}
    cfg = {"threshold_schema_version":1,"name":"n","description":"d","rules":[{"rule_id":"s","analysis_type":"snr","metric":"snr","operator":">=","threshold":1.0,"severity":"fail","label":"l"}]}
    out = DicomViewer.evaluate_current_analysis_thresholds(viewer, cfg, generated_at="2026-01-01T00:00:00+00:00")
    assert out["overall_status"] == "pass"
