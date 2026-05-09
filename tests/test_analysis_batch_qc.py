from __future__ import annotations

import json
import pytest

from analysis_batch_qc import (
    build_batch_qc_item_from_history_record,
    build_batch_qc_run,
    summarize_batch_qc_run,
    render_batch_qc_summary_text,
    export_batch_qc_run_to_json,
    export_batch_qc_run_to_csv,
)
from analysis_history_store import append_analysis_history_record
from dicom_viewer import DicomViewer
from tests.test_analysis_history_summary import _records
from tests.test_analysis_threshold_integration import _cfg
from tests.test_analysis_result_model import _viewer_for_export


def test_build_batch_qc_item_from_history_record_preserves_summary():
    assert "summary" in build_batch_qc_item_from_history_record(_records()[0])


def test_build_batch_qc_item_from_history_record_includes_threshold_when_config_provided():
    assert build_batch_qc_item_from_history_record(_records()[0], _cfg())["threshold_evaluation"] is not None


def test_build_batch_qc_item_from_history_record_omits_threshold_without_config():
    assert build_batch_qc_item_from_history_record(_records()[0])["threshold_evaluation"] is None


def test_build_batch_qc_run_handles_empty_records():
    assert build_batch_qc_run([])["item_count"] == 0


def test_build_batch_qc_run_summarizes_items():
    assert build_batch_qc_run(_records())["summary"]["warning_count"] >= 0


def test_build_batch_qc_run_rejects_wrong_history_schema():
    r = _records()
    r[0]["history_schema_version"] = 9
    with pytest.raises(ValueError):
        build_batch_qc_run(r)


def test_build_batch_qc_run_does_not_mutate_records_or_config():
    r = _records()
    c = _cfg()
    br = json.loads(json.dumps(r, default=str))
    bc = json.loads(json.dumps(c))
    _ = build_batch_qc_run(r, c)
    assert r[0]["record_id"] == br[0]["record_id"] and c == bc


def test_summarize_batch_qc_run_counts_threshold_statuses():
    assert "missing" in summarize_batch_qc_run(build_batch_qc_run(_records()))["threshold_status_counts"]


def test_render_batch_qc_summary_text_contains_items_and_status():
    assert "Item Count" in render_batch_qc_summary_text(build_batch_qc_run(_records()))


def test_render_batch_qc_summary_text_does_not_dump_mtf_curve_raw_points():
    assert "curve" not in render_batch_qc_summary_text(build_batch_qc_run(_records()))


def test_export_batch_qc_run_to_json_round_trips():
    payload = json.loads(export_batch_qc_run_to_json(build_batch_qc_run(_records())))
    assert payload["batch_qc_schema_version"] == 1


def test_export_batch_qc_run_to_csv_exports_item_rows():
    assert "record_id" in export_batch_qc_run_to_csv(build_batch_qc_run(_records()))


def test_export_batch_qc_run_to_json_writes_file(tmp_path):
    p = tmp_path / "b.json"
    _ = export_batch_qc_run_to_json(build_batch_qc_run(_records()), p)
    assert p.exists()


def test_export_batch_qc_run_to_csv_writes_file(tmp_path):
    p = tmp_path / "b.csv"
    _ = export_batch_qc_run_to_csv(build_batch_qc_run(_records()), p)
    assert p.exists()


def test_viewer_build_batch_qc_run_loads_history_jsonl(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    assert DicomViewer.build_batch_qc_run_for_viewer(v, p)["item_count"] >= 1


def test_viewer_render_batch_qc_summary_text_loads_history_jsonl(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    assert "Batch ID" in (DicomViewer.render_batch_qc_summary_text_for_viewer(v, p) or "")


def test_viewer_batch_qc_dialog_cancel_returns_none_without_mutation(monkeypatch):
    v = _viewer_for_export()
    monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_: "")
    assert DicomViewer.render_batch_qc_summary_text_for_viewer(v) is None


def test_viewer_batch_qc_does_not_auto_use_current_threshold_config(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    run = DicomViewer.build_batch_qc_run_for_viewer(v, p)
    assert all(i.get("threshold_evaluation") is None for i in run["items"])


def test_viewer_batch_qc_omits_threshold_when_not_requested_even_if_current_config_exists(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    run = DicomViewer.build_batch_qc_run_for_viewer(v, p, use_selected_threshold_config=False)
    assert all(i.get("threshold_evaluation") is None for i in run["items"])


def test_viewer_batch_qc_includes_selected_threshold_when_requested(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    run = DicomViewer.build_batch_qc_run_for_viewer(v, p, use_selected_threshold_config=True)
    assert all(i.get("threshold_evaluation") is not None for i in run["items"])


def test_viewer_batch_qc_uses_explicit_threshold_config_over_selected_config(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    selected = _cfg()
    selected["rules"][0]["severity"] = "warn"
    DicomViewer.set_current_threshold_config(v, selected)
    explicit = _cfg()
    explicit["rules"][0]["severity"] = "fail"
    run = DicomViewer.build_batch_qc_run_for_viewer(v, p, threshold_config=explicit, use_selected_threshold_config=True)
    assert run["items"][0]["threshold_evaluation"]["results"][0]["severity"] == "fail"


def test_viewer_batch_qc_selected_threshold_requires_current_config(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    with pytest.raises(ValueError):
        DicomViewer.build_batch_qc_run_for_viewer(v, p, use_selected_threshold_config=True)


def test_viewer_batch_qc_summary_with_selected_threshold_contains_threshold_status(tmp_path):
    p = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(p, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    text = DicomViewer.render_batch_qc_summary_text_with_selected_threshold_for_viewer(v, p) or ""
    assert "threshold=" in text and "threshold=missing" not in text


def test_viewer_batch_qc_json_export_with_selected_threshold_includes_threshold_evaluation(tmp_path):
    hp = tmp_path / "h.jsonl"
    out = tmp_path / "b.json"
    for r in _records():
        append_analysis_history_record(hp, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    payload = json.loads(DicomViewer.export_batch_qc_run_json_with_selected_threshold_for_viewer(v, path=str(out), history_path=hp) or "{}")
    assert payload["items"][0]["threshold_evaluation"] is not None


def test_viewer_batch_qc_csv_export_with_selected_threshold_includes_threshold_status(tmp_path):
    hp = tmp_path / "h.jsonl"
    out = tmp_path / "b.csv"
    for r in _records():
        append_analysis_history_record(hp, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    csv_text = DicomViewer.export_batch_qc_run_csv_with_selected_threshold_for_viewer(v, path=str(out), history_path=hp) or ""
    assert "threshold_overall_status" in csv_text and ",missing" not in csv_text


def test_viewer_batch_qc_selected_threshold_wrapper_does_not_mutate_config_or_records(tmp_path):
    hp = tmp_path / "h.jsonl"
    records = _records()
    for r in records:
        append_analysis_history_record(hp, r)
    v = _viewer_for_export()
    cfg = _cfg()
    baseline_cfg = json.loads(json.dumps(cfg))
    baseline_records = json.loads(json.dumps(records, default=str))
    DicomViewer.set_current_threshold_config(v, cfg)
    _ = DicomViewer.build_batch_qc_run_with_selected_threshold_for_viewer(v, hp)
    assert cfg == baseline_cfg and records[0]["record_id"] == baseline_records[0]["record_id"]


def test_viewer_batch_qc_does_not_auto_use_catalog_selected_config(tmp_path):
    hp = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(hp, r)
    v = _viewer_for_export()
    catalog = {"threshold_catalog_schema_version": 1, "selected_config_id": "sel", "configs": {"sel": _cfg()}}
    DicomViewer.set_current_threshold_catalog(v, catalog)
    run = DicomViewer.build_batch_qc_run_for_viewer(v, hp)
    assert all(i.get("threshold_evaluation") is None for i in run["items"])


def test_viewer_batch_qc_selected_threshold_cancelled_dialog_does_not_mutate_state(monkeypatch):
    v = _viewer_for_export()
    cfg = _cfg()
    DicomViewer.set_current_threshold_config(v, cfg)
    baseline = json.loads(json.dumps(v.current_threshold_config))
    monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_: "")
    assert DicomViewer.build_batch_qc_run_with_selected_threshold_for_viewer(v) is None
    assert v.current_threshold_config == baseline


def test_batch_qc_selected_threshold_does_not_add_default_clinical_thresholds(tmp_path):
    hp = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(hp, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    run = DicomViewer.build_batch_qc_run_with_selected_threshold_for_viewer(v, hp)
    rule_ids = [rr.get("rule_id") for rr in run["items"][0]["threshold_evaluation"]["results"]]
    assert rule_ids == ["snr_min"]


def test_batch_qc_selected_threshold_does_not_start_dicom_batch_execution(tmp_path):
    hp = tmp_path / "h.jsonl"
    for r in _records():
        append_analysis_history_record(hp, r)
    v = _viewer_for_export()
    DicomViewer.set_current_threshold_config(v, _cfg())
    _ = DicomViewer.build_batch_qc_run_with_selected_threshold_for_viewer(v, hp)
    assert not hasattr(v, "batch_dicom_execution_state")
