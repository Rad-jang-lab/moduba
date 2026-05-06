import json

from iqa_history import IQAHistoryEntry
from iqa_report import (
    build_iqa_history_summary_report,
    build_iqa_report,
    flatten_iqa_history_summary_for_export,
    flatten_iqa_report_for_export,
    format_iqa_history_summary_text,
    format_iqa_report_text,
    iqa_report_to_jsonable,
)


def _success_entry() -> IQAHistoryEntry:
    return IQAHistoryEntry(
        history_id="iqa_1",
        created_at="2026-01-01T00:00:00+00:00",
        status="success",
        reference_label="Ref",
        target_label="Tar",
        input_mode="raw_dicom_pixel",
        scope="roi",
        data_range_policy="bits",
        data_range_used=16383.0,
        roi_id="roi_1",
        roi_label="Lung ROI",
        roi_bbox=(1, 1, 4, 4),
        roi_policy="bbox",
        metrics={"mse": 1.0, "rmse": 1.0, "psnr": 40.0, "ssim": 0.9, "hist_corr": 0.4},
        histogram={"histogram_bins": 64, "histogram_range": (0, 16383), "histogram_distribution_hint": "target_shifted_brighter", "histogram_summary": "분포 차이"},
        warnings=["warn_a"],
        export_record={"analysis_type": "iqa"},
        source="test",
    )


def test_single_success_report_contains_required_fields():
    report = build_iqa_report(_success_entry())
    assert report["report_type"] == "iqa_single"
    assert report["reference_label"] == "Ref"
    assert report["metrics"]["ssim"] == 0.9
    assert report["histogram"]["histogram_bins"] == 64


def test_report_text_formatting_contains_sections():
    text = format_iqa_report_text(build_iqa_report(_success_entry()))
    assert "IQA Report" in text and "Metrics:" in text and "Histogram:" in text and "Interpretation:" in text


def test_invalid_report_has_reason_and_no_stale_metrics():
    entry = IQAHistoryEntry(history_id="iqa_2", created_at="2026", status="invalid", invalid_reason="missing_target", metrics={})
    report = build_iqa_report(entry)
    assert report["status"] == "invalid"
    assert report["invalid_reason"] == "missing_target"
    assert report["metrics"] == {}
    assert "IQA 실행 불가" in report["interpretation"]


def test_json_serialization_and_dict_compatibility():
    report = build_iqa_report(_success_entry().__dict__)
    payload = iqa_report_to_jsonable(report)
    json.dumps(payload)


def test_multi_history_summary_and_flatten_helpers():
    s1 = _success_entry()
    s2 = _success_entry()
    s2.history_id = "iqa_2"
    s2.metrics = {"mse": 2.0, "rmse": 1.414, "psnr": 35.0, "ssim": 0.8, "hist_corr": 0.6}
    inv = IQAHistoryEntry(history_id="iqa_3", created_at="2026", status="invalid", invalid_reason="missing_target", metrics={})
    summary = build_iqa_history_summary_report([s1, s2, inv])
    assert summary["total_count"] == 3
    assert summary["success_count"] == 2
    assert summary["invalid_count"] == 1
    assert summary["average_ssim"] == (0.9 + 0.8) / 2
    assert "IQA History Summary" in format_iqa_history_summary_text(summary)
    flat = flatten_iqa_report_for_export(build_iqa_report(s1))
    assert "metric_psnr" in flat and "roi_label" in flat and "interpretation" in flat
    summary_flat = flatten_iqa_history_summary_for_export(summary)
    assert summary_flat["success_count"] == 2
