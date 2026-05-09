from __future__ import annotations

import json

import pytest

from analysis_report_model import build_analysis_report_model, render_analysis_report_markdown


def _normalized_fixture() -> dict:
    return {
        "snr": {"analysis_type": "snr", "status": "success", "validity": "valid", "metrics": {"snr": 2.5}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {"signal_roi_id": "s"}, "source_payload_keys": ["result"]},
        "cnr": {"analysis_type": "cnr", "status": "success", "validity": "valid", "metrics": {"cnr": 1.2}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
        "uniformity": {"analysis_type": "uniformity", "status": "success", "validity": "valid", "metrics": {"uniformity": 88.8}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
        "mtf": {"analysis_type": "mtf", "status": "reject", "validity": "invalid", "metrics": {"mtf50": 0.25}, "curves": {"mtf": {"x": [0.0, 0.1], "y": [1.0, 0.8]}}, "warnings": ["w"], "reason_codes": ["r"], "roi_info": {}, "source_payload_keys": ["key_mtf_metrics", "mtf_curve"]},
    }


def test_build_report_model_includes_all_analysis_sections():
    report = build_analysis_report_model(_normalized_fixture(), metadata={"app": "moduba"}, generated_at="2026-01-01T00:00:00+00:00")
    assert [s["analysis_type"] for s in report["sections"]] == ["snr", "cnr", "uniformity", "mtf"]


def test_build_report_model_counts_valid_invalid_and_warnings():
    report = build_analysis_report_model(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    assert report["summary"]["valid_count"] == 3
    assert report["summary"]["invalid_count"] == 1
    assert report["summary"]["warning_count"] == 1


def test_build_report_model_preserves_invalid_result_reasons():
    report = build_analysis_report_model(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    mtf = next(s for s in report["sections"] if s["analysis_type"] == "mtf")
    assert mtf["warnings"] == ["w"]
    assert mtf["reason_codes"] == ["r"]


def test_build_report_model_summarizes_mtf_curve_without_expanding_points():
    report = build_analysis_report_model(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    mtf = next(s for s in report["sections"] if s["analysis_type"] == "mtf")
    assert mtf["curve_summaries"][0]["point_count"] == 2
    assert "x" not in mtf["curve_summaries"][0]
    assert "y" not in mtf["curve_summaries"][0]


def test_build_report_model_rejects_none_result():
    with pytest.raises(ValueError):
        build_analysis_report_model({"snr": None})


def test_build_report_model_rejects_non_finite_numeric_values():
    fixture = _normalized_fixture()
    fixture["snr"]["metrics"]["snr"] = float("nan")
    with pytest.raises(ValueError):
        build_analysis_report_model(fixture)


def test_build_report_model_uses_timezone_aware_generated_at():
    report = build_analysis_report_model(_normalized_fixture())
    assert "+" in report["generated_at"] or report["generated_at"].endswith("Z")


def test_render_report_markdown_contains_summary_and_sections():
    report = build_analysis_report_model(_normalized_fixture(), metadata={"app": "moduba"}, generated_at="2026-01-01T00:00:00+00:00")
    text = render_analysis_report_markdown(report)
    assert "## Summary" in text
    assert "## SNR" in text
    assert "## CNR" in text
    assert "## Uniformity" in text
    assert "## MTF" in text


def test_render_report_markdown_includes_invalid_reasons():
    report = build_analysis_report_model(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    text = render_analysis_report_markdown(report)
    assert "Validity: invalid" in text
    assert "Reason Codes: ['r']" in text


def test_report_output_order_is_deterministic():
    report = build_analysis_report_model(_normalized_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    text1 = render_analysis_report_markdown(report)
    text2 = render_analysis_report_markdown(json.loads(json.dumps(report)))
    assert text1 == text2
    assert "[0.0, 0.1]" not in text1
