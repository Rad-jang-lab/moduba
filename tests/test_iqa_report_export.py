import csv
import io
import json

from iqa_history import IQAHistoryEntry
from iqa_report import build_iqa_history_summary_report, build_iqa_report
from iqa_report_export import (
    build_iqa_history_entries_csv_rows,
    build_iqa_history_export_bundle,
    build_iqa_history_summary_export_bundle,
    build_iqa_report_csv_rows,
    build_iqa_report_export_bundle,
    build_iqa_report_json_payload,
    build_iqa_report_txt_payload,
)


def _entry(status="success", idx="1"):
    return IQAHistoryEntry(
        history_id=f"iqa_{idx}",
        created_at="2026-01-01T00:00:00+00:00",
        status=status,
        invalid_reason="missing_target" if status != "success" else None,
        reference_label="Ref",
        target_label="Tar",
        input_mode="raw_dicom_pixel",
        scope="roi",
        roi_label="ROI-1",
        data_range_policy="bits",
        data_range_used=1023.0,
        metrics={} if status != "success" else {"mse": 1.0, "rmse": 1.0, "psnr": float("inf"), "ssim": 0.9, "hist_corr": 0.8},
        histogram={"histogram_corr": 0.8, "histogram_distribution_hint": "similar"},
        warnings=["missing_bits_stored"],
        export_record={"analysis_type": "iqa", "context_roi_bbox": (1, 2, 3, 4)},
    )


def test_single_report_txt_json_csv_payloads():
    report = build_iqa_report(_entry())
    txt = build_iqa_report_txt_payload(report)
    assert "IQA Report" in txt and "Reference:" in txt and "Metrics:" in txt and "Interpretation:" in txt

    payload = build_iqa_report_json_payload(report)
    json.dumps(payload, ensure_ascii=False)
    assert "metrics" in payload and "histogram" in payload and "warnings" in payload and "export_record" in payload

    rows = build_iqa_report_csv_rows(report)
    assert len(rows) == 1
    row = rows[0]
    assert "metric_psnr" in row and "metric_ssim" in row and "metric_hist_corr" in row and "roi_label" in row and "interpretation" in row
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(row.keys()))
    writer.writeheader()
    writer.writerows(rows)
    assert "report_type" in stream.getvalue()


def test_invalid_report_export_has_invalid_markers_and_no_stale_metrics():
    report = build_iqa_report(_entry(status="invalid", idx="2"))
    txt = build_iqa_report_txt_payload(report)
    assert "Status: Invalid" in txt and "missing_target" in txt
    payload = build_iqa_report_json_payload(report)
    assert payload["status"] == "invalid"
    rows = build_iqa_report_csv_rows(report)
    assert rows[0]["status"] == "invalid"
    assert rows[0]["metric_psnr"] in {None, ""}


def test_history_summary_bundle_and_entries_rows():
    entries = [_entry(idx="1"), _entry(idx="2"), _entry(status="invalid", idx="3")]
    summary = build_iqa_history_summary_report(entries)
    bundle = build_iqa_history_summary_export_bundle(summary)
    assert {"txt", "json", "csv_rows"}.issubset(bundle)
    assert bundle["json"]["total_count"] == 3 and bundle["json"]["success_count"] == 2 and bundle["json"]["invalid_count"] == 1

    hist_bundle = build_iqa_history_export_bundle(entries)
    assert {"summary", "txt", "json", "csv_rows"}.issubset(hist_bundle)
    assert len(hist_bundle["csv_rows"]) == 3
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(hist_bundle["csv_rows"][0].keys()))
    writer.writeheader()
    writer.writerows(hist_bundle["csv_rows"])


def test_export_bundle_structure_and_dict_dataclass_compatibility():
    dataclass_report = build_iqa_report(_entry(idx="9"))
    dict_report = build_iqa_report(_entry(idx="10").__dict__)
    b1 = build_iqa_report_export_bundle(dataclass_report)
    b2 = build_iqa_report_export_bundle(dict_report)
    assert {"txt", "json", "csv_rows"}.issubset(b1) and {"txt", "json", "csv_rows"}.issubset(b2)
    json.dumps(b1["json"], ensure_ascii=False)
    json.dumps(b2["json"], ensure_ascii=False)

    rows = build_iqa_history_entries_csv_rows([_entry(idx="1"), _entry(status="invalid", idx="2")])
    assert len(rows) == 2
