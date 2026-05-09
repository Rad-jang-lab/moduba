from __future__ import annotations

import json

import pytest

from analysis_history_display import render_history_record_detail_text
from analysis_history_store import build_analysis_history_record
from analysis_report_model import build_analysis_report_model, render_analysis_report_markdown
from analysis_report_pdf import build_analysis_report_pdf_lines
from analysis_thresholds import evaluate_analysis_thresholds
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _normalized_export_fixture, _viewer_for_export


def _cfg():
    return {"threshold_schema_version":1,"name":"cfg","description":"d","rules":[{"rule_id":"snr_min","analysis_type":"snr","metric":"snr","operator":">=","threshold":2.0,"severity":"fail","label":"l"}]}


def _eval():
    return evaluate_analysis_thresholds(_normalized_export_fixture(), _cfg(), generated_at="2026-01-01T00:00:00+00:00")


def test_report_model_can_include_threshold_evaluation():
    m = build_analysis_report_model(_normalized_export_fixture(), threshold_evaluation=_eval())
    assert "threshold_evaluation" in m

def test_report_model_without_threshold_evaluation_is_backward_compatible():
    m = build_analysis_report_model(_normalized_export_fixture())
    assert "threshold_evaluation" not in m

def test_markdown_report_renders_threshold_section_when_present():
    t = render_analysis_report_markdown(build_analysis_report_model(_normalized_export_fixture(), threshold_evaluation=_eval()))
    assert "QC Threshold Evaluation" in t

def test_markdown_report_omits_threshold_section_when_absent():
    t = render_analysis_report_markdown(build_analysis_report_model(_normalized_export_fixture()))
    assert "QC Threshold Evaluation" not in t

def test_pdf_lines_render_threshold_section_when_present():
    lines = build_analysis_report_pdf_lines(build_analysis_report_model(_normalized_export_fixture(), threshold_evaluation=_eval()))
    assert any("QC Threshold Evaluation" in l for l in lines)

def test_history_record_can_include_threshold_evaluation():
    r = build_analysis_history_record(_normalized_export_fixture(), threshold_evaluation=_eval())
    assert "threshold_evaluation" in r

def test_history_record_without_threshold_evaluation_is_backward_compatible():
    r = build_analysis_history_record(_normalized_export_fixture())
    assert "threshold_evaluation" not in r

def test_history_display_detail_renders_threshold_evaluation_when_present():
    r = build_analysis_history_record(_normalized_export_fixture(), threshold_evaluation=_eval())
    assert "[THRESHOLD]" in render_history_record_detail_text(r)

def test_viewer_report_can_include_threshold_evaluation_from_config():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture()
    t = DicomViewer.render_current_analysis_report_markdown(v, threshold_config=_cfg())
    assert "QC Threshold Evaluation" in t

def test_viewer_history_record_can_include_threshold_evaluation_from_config():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture()
    r = DicomViewer.build_current_analysis_history_record(v, threshold_config=_cfg())
    assert "threshold_evaluation" in r

def test_threshold_integration_does_not_mutate_normalized_results():
    fixture=_normalized_export_fixture(); before=json.loads(json.dumps(fixture))
    _ = build_analysis_report_model(fixture, threshold_evaluation=_eval())
    assert fixture==before

def test_invalid_threshold_evaluation_schema_is_rejected():
    with pytest.raises(ValueError):
        build_analysis_report_model(_normalized_export_fixture(), threshold_evaluation={"threshold_evaluation_schema_version":9})


def test_viewer_report_omits_threshold_when_not_requested_even_if_selected_config_exists():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    t=DicomViewer.render_current_analysis_report_markdown(v)
    assert "QC Threshold Evaluation" not in t


def test_viewer_report_includes_selected_threshold_when_requested():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    t=DicomViewer.render_current_analysis_report_markdown(v,use_selected_threshold_config=True)
    assert "QC Threshold Evaluation" in t


def test_viewer_report_uses_explicit_threshold_config_over_selected_config():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture()
    selected={"threshold_schema_version":1,"name":"selected","description":"d","rules":[{"rule_id":"s","analysis_type":"snr","metric":"snr","operator":">=","threshold":9.0,"severity":"fail","label":"l"}]}
    explicit=_cfg()
    DicomViewer.set_current_threshold_config(v, selected)
    t=DicomViewer.render_current_analysis_report_markdown(v,threshold_config=explicit,use_selected_threshold_config=True)
    assert "Config Name: cfg" in t


def test_viewer_report_selected_threshold_requires_current_config():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture()
    with pytest.raises(ValueError): DicomViewer.render_current_analysis_report_markdown(v,use_selected_threshold_config=True)


def test_viewer_markdown_export_with_selected_threshold_includes_threshold_section(tmp_path):
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    out=tmp_path/"r.md"; t=DicomViewer.export_analysis_report_markdown_with_selected_threshold(v,path=str(out))
    assert "QC Threshold Evaluation" in (t or "")


def test_viewer_pdf_export_with_selected_threshold_includes_threshold_lines(tmp_path):
    from analysis_report_pdf import build_analysis_report_pdf_lines
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    _=DicomViewer.export_analysis_report_pdf_with_selected_threshold(v,path=str(tmp_path/"r.pdf"))
    model=DicomViewer.build_current_analysis_report_model(v,use_selected_threshold_config=True)
    assert any("QC Threshold Evaluation" in l for l in build_analysis_report_pdf_lines(model))


def test_viewer_history_record_omits_threshold_when_not_requested_even_if_selected_config_exists():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    r=DicomViewer.build_current_analysis_history_record(v)
    assert "threshold_evaluation" not in r


def test_viewer_history_record_includes_selected_threshold_when_requested():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    r=DicomViewer.build_current_analysis_history_record(v,use_selected_threshold_config=True)
    assert "threshold_evaluation" in r


def test_viewer_history_append_with_selected_threshold_writes_threshold_evaluation(tmp_path):
    from analysis_history_store import load_analysis_history_records
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    p=tmp_path/"h.jsonl"; DicomViewer.append_current_analysis_history_with_selected_threshold(v,p,record_id="x")
    assert "threshold_evaluation" in load_analysis_history_records(p)[0]


def test_viewer_report_preview_with_selected_threshold_contains_overall_status():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    t=DicomViewer.build_current_analysis_report_preview_text_with_selected_threshold(v)
    assert "Overall Status:" in t


def test_selected_threshold_integration_does_not_mutate_config_or_normalized_results():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture(); DicomViewer.set_current_threshold_config(v,_cfg())
    br=json.loads(json.dumps(v.analysis_last_run_normalized)); bc=json.loads(json.dumps(v.current_threshold_config))
    _=DicomViewer.build_current_analysis_report_model(v,use_selected_threshold_config=True)
    assert v.analysis_last_run_normalized==br and v.current_threshold_config==bc


def test_selected_threshold_wrappers_are_backward_compatible():
    v=_viewer_for_export(); v.analysis_last_run_normalized=_normalized_export_fixture()
    with pytest.raises(ValueError): DicomViewer.export_analysis_report_markdown_with_selected_threshold(v,path="/tmp/a.md")
