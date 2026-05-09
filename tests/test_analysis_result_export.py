from __future__ import annotations

import csv
import io
import json

import pytest

from analysis_result_export import (
    build_analysis_export_snapshot,
    export_analysis_results_to_csv,
    export_analysis_results_to_json,
)


def _normalized_fixture() -> dict:
    return {
        "snr": {"analysis_type": "snr", "status": "success", "validity": "valid", "metrics": {"snr": 2.5}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {"signal_roi_id": "s"}, "source_payload_keys": ["result"]},
        "cnr": {"analysis_type": "cnr", "status": "success", "validity": "valid", "metrics": {"cnr": 1.2}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
        "uniformity": {"analysis_type": "uniformity", "status": "success", "validity": "valid", "metrics": {"uniformity": 88.8}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
        "mtf": {"analysis_type": "mtf", "status": "ok", "validity": "valid", "metrics": {"mtf50": 0.25}, "curves": {"mtf": {"x": [0.0, 0.1], "y": [1.0, 0.8]}}, "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["key_mtf_metrics", "mtf_curve"]},
    }


def test_build_analysis_export_snapshot_preserves_normalized_results():
    snap = build_analysis_export_snapshot(_normalized_fixture(), metadata={"a": 1}, generated_at="2026-01-01T00:00:00+00:00")
    assert snap["results"]["snr"]["metrics"]["snr"] == 2.5


def test_export_analysis_results_to_json_preserves_metrics_and_curves():
    text = export_analysis_results_to_json(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    payload = json.loads(text)
    assert payload["results"]["mtf"]["curves"]["mtf"]["x"] == [0.0, 0.1]


def test_export_analysis_results_to_csv_exports_summary_metric_and_curve_rows():
    text = export_analysis_results_to_csv(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert any(r["item_type"] == "result_summary" and r["analysis_type"] == "mtf" for r in rows)
    assert any(r["item_type"] == "metric" and r["item_name"] == "mtf50" for r in rows)
    assert any(r["item_type"] == "curve_point" and r["item_name"] == "mtf" for r in rows)


def test_export_invalid_result_keeps_warnings_and_reason_codes():
    fixture = _normalized_fixture()
    fixture["mtf"]["status"] = "reject"
    fixture["mtf"]["validity"] = "invalid"
    fixture["mtf"]["warnings"] = ["w"]
    fixture["mtf"]["reason_codes"] = ["r"]
    rows = list(csv.DictReader(io.StringIO(export_analysis_results_to_csv(fixture, generated_at="2026-01-01T00:00:00+00:00"))))
    row = next(r for r in rows if r["analysis_type"] == "mtf" and r["item_type"] == "result_summary")
    assert '"w"' in row["warnings_json"]
    assert '"r"' in row["reason_codes_json"]


def test_export_rejects_none_normalized_result():
    with pytest.raises(ValueError):
        build_analysis_export_snapshot({"snr": None})


def test_export_rejects_non_finite_numeric_values():
    fixture = _normalized_fixture()
    fixture["snr"]["metrics"]["snr"] = float("nan")
    with pytest.raises(ValueError):
        build_analysis_export_snapshot(fixture)


def test_export_uses_timezone_aware_generated_at():
    snap = build_analysis_export_snapshot(_normalized_fixture())
    assert "+" in snap["generated_at"] or snap["generated_at"].endswith("Z")


def test_export_json_can_write_to_path(tmp_path):
    out = tmp_path / "a.json"
    text = export_analysis_results_to_json(_normalized_fixture(), path=out, generated_at="2026-01-01T00:00:00+00:00")
    assert out.read_text(encoding="utf-8") == text


def test_export_csv_can_write_to_path(tmp_path):
    out = tmp_path / "a.csv"
    text = export_analysis_results_to_csv(_normalized_fixture(), path=out, generated_at="2026-01-01T00:00:00+00:00")
    assert out.read_text(encoding="utf-8") == text


def test_export_order_is_deterministic():
    text1 = export_analysis_results_to_csv(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    text2 = export_analysis_results_to_csv(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    assert text1 == text2
