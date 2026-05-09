from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis_history_store import append_analysis_history_record
from analysis_history_summary import (
    build_history_summary,
    build_metric_trend_series,
    build_threshold_status_summary,
    render_history_summary_text,
    render_metric_trend_text,
)
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export


def _records():
    a = {
        "history_schema_version": 1,
        "record_id": "a",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {},
        "export_snapshot": {
            "results": {
                "snr": {"validity": "valid", "warnings": [], "metrics": {"snr": 10.0}},
                "mtf": {"validity": "invalid", "warnings": ["w"], "metrics": {"mtf50": 0.2, "curve": [1, 2]}},
            }
        },
    }
    b = json.loads(json.dumps(a))
    b["record_id"] = "b"
    b["generated_at"] = "2026-01-02T00:00:00+00:00"
    b["export_snapshot"]["results"]["snr"]["metrics"]["snr"] = 12.0
    b["threshold_evaluation"] = {
        "threshold_evaluation_schema_version": 1,
        "overall_status": "pass",
        "config_name": "cfg",
        "results": [{"rule_id": "r1", "status": "warn"}],
    }
    c = json.loads(json.dumps(a))
    c["record_id"] = "c"
    c["generated_at"] = "2026-01-03T00:00:00+00:00"
    c["export_snapshot"]["results"]["snr"]["metrics"]["snr"] = float("inf")
    return [a, b, c]


def test_build_history_summary_handles_empty_records():
    assert build_history_summary([])["record_count"] == 0


def test_build_history_summary_counts_analysis_and_validity():
    s = build_history_summary(_records())
    assert s["analysis_counts"]["snr"] == 3
    assert s["validity_counts"]["invalid"] >= 1


def test_build_history_summary_filters_by_analysis_type():
    s = build_history_summary(_records(), analysis_type="snr")
    assert "snr.snr" in s["metric_summaries"]


def test_build_history_summary_filters_by_validity():
    s = build_history_summary(_records(), validity="valid")
    assert s["validity_counts"]["invalid"] == 0


def test_build_history_summary_builds_metric_summaries():
    assert build_history_summary(_records())["metric_summaries"]["snr.snr"]["count"] >= 2


def test_build_history_summary_skips_non_finite_metrics():
    assert build_history_summary(_records())["metric_non_finite_counts"]["snr.snr"] >= 1


def test_build_metric_trend_series_orders_points_by_generated_at():
    t = build_metric_trend_series(_records(), "snr", "snr")
    assert [p["generated_at"] for p in t["points"]] == sorted([p["generated_at"] for p in t["points"]])


def test_build_metric_trend_series_tracks_missing_metrics():
    r = _records()
    del r[0]["export_snapshot"]["results"]["snr"]["metrics"]["snr"]
    assert build_metric_trend_series(r, "snr", "snr")["missing_count"] >= 1


def test_build_metric_trend_series_includes_invalid_validity():
    assert any(p["validity"] == "invalid" for p in build_metric_trend_series(_records(), "mtf", "mtf50")["points"])


def test_build_metric_trend_series_omits_mtf_curve_raw_points():
    assert "curve" not in render_metric_trend_text(build_metric_trend_series(_records(), "mtf", "mtf50"))


def test_build_threshold_status_summary_counts_optional_evaluations():
    assert build_threshold_status_summary(_records())["threshold_status_counts"]["missing"] >= 1


def test_render_history_summary_text_contains_counts_and_metrics():
    assert "Metric Summaries" in render_history_summary_text(build_history_summary(_records()))


def test_render_metric_trend_text_contains_points_without_curve_dump():
    assert "curve" not in render_metric_trend_text(build_metric_trend_series(_records(), "snr", "snr"))


def test_history_summary_helpers_do_not_mutate_records():
    r = _records()
    b = json.loads(json.dumps(r, default=str))
    _ = build_history_summary(r)
    assert r[0]["record_id"] == b[0]["record_id"]


def test_history_summary_rejects_wrong_schema_version():
    r = _records()
    r[0]["history_schema_version"] = 9
    with pytest.raises(ValueError):
        build_history_summary(r)


def test_viewer_history_summary_loads_jsonl_and_renders_text(tmp_path: Path):
    p = tmp_path / "h.jsonl"
    for rec in _records():
        append_analysis_history_record(p, rec)
    v = _viewer_for_export()
    assert "Record Count" in (DicomViewer.render_analysis_history_summary_text_for_viewer(v, p) or "")


def test_viewer_metric_trend_loads_jsonl_and_renders_text(tmp_path: Path):
    p = tmp_path / "h.jsonl"
    for rec in _records():
        append_analysis_history_record(p, rec)
    v = _viewer_for_export()
    assert "Point Count" in (DicomViewer.render_metric_trend_text_for_viewer(v, p, "snr", "snr") or "")


def test_viewer_history_summary_dialog_cancel_returns_none_without_mutation(monkeypatch):
    v = _viewer_for_export()
    monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_: "")
    assert DicomViewer.render_analysis_history_summary_text_for_viewer(v) is None


def test_show_history_summary_viewer_uses_summary_text_without_mutation(monkeypatch, tmp_path: Path):
    class D:
        def title(self, *_): pass
        def geometry(self, *_): pass
    class W:
        def pack(self, *_, **__): pass
        def insert(self, *_, **__): pass
        def configure(self, *_, **__): pass
    monkeypatch.setattr("dicom_viewer.tk.Toplevel", lambda *_, **__: D())
    monkeypatch.setattr("dicom_viewer.tk.Text", lambda *_, **__: W())
    p = tmp_path / "h.jsonl"
    recs = _records()
    before = json.loads(json.dumps(recs, default=str))
    for rec in recs:
        append_analysis_history_record(p, rec)
    v = _viewer_for_export()
    _ = DicomViewer.show_analysis_history_summary_viewer(v, p)
    assert recs[0]["record_id"] == before[0]["record_id"]
