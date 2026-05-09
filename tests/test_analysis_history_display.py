from __future__ import annotations

import json

import pytest

from analysis_history_display import (
    build_history_record_display_model,
    build_history_records_display_model,
    render_history_record_detail_text,
)
from analysis_history_store import append_analysis_history_record, build_analysis_history_record
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _normalized_export_fixture, _viewer_for_export


def _records() -> list[dict]:
    r1 = build_analysis_history_record(_normalized_export_fixture(), generated_at="2026-01-01T00:00:00+00:00", record_id="r1")
    return [r1]


def test_build_history_records_display_model_lists_records():
    model = build_history_records_display_model(_records())
    assert model["record_count"] == 1


def test_build_history_records_display_model_handles_empty_records():
    model = build_history_records_display_model([])
    assert model["rows"] == []


def test_build_history_records_display_model_filters_by_analysis_type():
    assert build_history_records_display_model(_records(), analysis_type="mtf")["record_count"] == 1


def test_build_history_records_display_model_filters_by_validity():
    assert build_history_records_display_model(_records(), validity="invalid")["record_count"] == 1


def test_build_history_record_display_model_preserves_invalid_result():
    d = build_history_record_display_model(_records()[0])
    mtf = next(r for r in d["analysis_rows"] if r["analysis_type"] == "mtf")
    assert mtf["validity"] == "invalid"


def test_render_history_record_detail_text_contains_summary_and_sections():
    text = render_history_record_detail_text(_records()[0])
    assert "Summary:" in text and "[SNR]" in text and "[MTF]" in text


def test_render_history_record_detail_text_includes_invalid_reasons():
    text = render_history_record_detail_text(_records()[0])
    assert "reason_codes: ['r']" in text


def test_render_history_record_detail_text_does_not_expand_mtf_curve_raw_points():
    text = render_history_record_detail_text(_records()[0])
    assert "[0.0, 0.1]" not in text


def test_history_display_rejects_none_record():
    with pytest.raises(ValueError):
        build_history_record_display_model(None)


def test_history_display_rejects_wrong_schema_version():
    bad = _records()[0]
    bad["history_schema_version"] = 9
    with pytest.raises(ValueError):
        build_history_record_display_model(bad)


def test_history_display_does_not_mutate_input_records():
    rec = _records()[0]
    before = json.loads(json.dumps(rec))
    _ = build_history_record_display_model(rec)
    assert rec == before


def test_viewer_load_analysis_history_for_viewer_reads_jsonl(tmp_path):
    p = tmp_path / "h.jsonl"
    append_analysis_history_record(p, _records()[0])
    viewer = _viewer_for_export()
    out = DicomViewer.load_analysis_history_for_viewer(viewer, p)
    assert len(out) == 1


def test_viewer_history_display_model_uses_history_helpers(tmp_path):
    p = tmp_path / "h.jsonl"
    append_analysis_history_record(p, _records()[0])
    viewer = _viewer_for_export()
    model = DicomViewer.build_analysis_history_display_model(viewer, p)
    assert model["record_count"] == 1


def test_viewer_history_dialog_cancel_returns_none_without_mutation(monkeypatch):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    before = json.loads(json.dumps(viewer.analysis_last_run_normalized))
    monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_kwargs: "")
    assert DicomViewer.build_analysis_history_display_model(viewer, None) is None
    assert viewer.analysis_last_run_normalized == before
