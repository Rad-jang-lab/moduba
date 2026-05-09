from __future__ import annotations

import json

import pytest

from analysis_history_store import (
    append_analysis_history_record,
    build_analysis_history_record,
    export_analysis_history_to_json,
    filter_analysis_history_records,
    load_analysis_history_records,
)
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _normalized_export_fixture, _viewer_for_export


def test_build_history_record_contains_snapshot_and_summary():
    rec = build_analysis_history_record(_normalized_export_fixture(), generated_at="2026-01-01T00:00:00+00:00", record_id="r1")
    assert rec["record_id"] == "r1"
    assert "export_snapshot" in rec
    assert "summary" in rec


def test_build_history_record_preserves_invalid_result():
    rec = build_analysis_history_record(_normalized_export_fixture(), generated_at="2026-01-01T00:00:00+00:00")
    assert rec["summary"]["invalid_count"] == 1


def test_build_history_record_rejects_none_result():
    with pytest.raises(ValueError):
        build_analysis_history_record({"snr": None})


def test_build_history_record_rejects_non_finite_numeric_values():
    fixture = _normalized_export_fixture()
    fixture["snr"]["metrics"]["snr"] = float("nan")
    with pytest.raises(ValueError):
        build_analysis_history_record(fixture)


def test_build_history_record_uses_timezone_aware_generated_at():
    rec = build_analysis_history_record(_normalized_export_fixture())
    assert "+" in rec["generated_at"] or rec["generated_at"].endswith("Z")


def test_append_and_load_history_records_jsonl(tmp_path):
    p = tmp_path / "h.jsonl"
    r1 = build_analysis_history_record(_normalized_export_fixture(), generated_at="2026-01-01T00:00:00+00:00", record_id="r1")
    append_analysis_history_record(p, r1)
    out = load_analysis_history_records(p)
    assert out[0]["record_id"] == "r1"


def test_load_history_records_empty_file_returns_empty_list(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text("", encoding="utf-8")
    assert load_analysis_history_records(p) == []


def test_load_history_records_rejects_malformed_json_line(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text("{bad}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_analysis_history_records(p)


def test_load_history_records_rejects_wrong_schema_version(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text(json.dumps({"history_schema_version": 9}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_analysis_history_records(p)


def test_filter_history_records_by_analysis_type():
    recs = [build_analysis_history_record(_normalized_export_fixture(), generated_at="2026-01-01T00:00:00+00:00")]
    assert len(filter_analysis_history_records(recs, analysis_type="mtf")) == 1
    assert len(filter_analysis_history_records(recs, analysis_type="unknown")) == 0


def test_filter_history_records_by_validity():
    recs = [build_analysis_history_record(_normalized_export_fixture(), generated_at="2026-01-01T00:00:00+00:00")]
    assert len(filter_analysis_history_records(recs, validity="invalid")) == 1
    assert len(filter_analysis_history_records(recs, validity="nope")) == 0


def test_export_analysis_history_to_json_returns_deterministic_json(tmp_path):
    recs = [build_analysis_history_record(_normalized_export_fixture(), generated_at="2026-01-01T00:00:00+00:00", record_id="r1")]
    text = export_analysis_history_to_json(recs)
    assert json.loads(text)[0]["record_id"] == "r1"
    p = tmp_path / "h.json"
    text2 = export_analysis_history_to_json(recs, path=p)
    assert p.read_text(encoding="utf-8") == text2


def test_viewer_build_current_analysis_history_record_uses_normalized_cache():
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    rec = DicomViewer.build_current_analysis_history_record(viewer, record_id="rv")
    assert rec["record_id"] == "rv"
    assert rec["summary"]["analysis_count"] == 4


def test_viewer_append_current_analysis_history_writes_jsonl(tmp_path):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    p = tmp_path / "h.jsonl"
    rec = DicomViewer.append_current_analysis_history(viewer, p, record_id="rv2")
    loaded = load_analysis_history_records(p)
    assert rec["record_id"] == "rv2"
    assert loaded[0]["record_id"] == "rv2"
