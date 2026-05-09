from __future__ import annotations
import json
import pytest
from analysis_history_trend_chart import *
from analysis_history_store import append_analysis_history_record
from analysis_history_summary import build_metric_trend_series
from dicom_viewer import DicomViewer
from tests.test_analysis_history_summary import _records
from tests.test_analysis_result_model import _viewer_for_export


def _trend():
    return build_metric_trend_series(_records(), "snr", "snr")

def test_build_metric_trend_chart_model_handles_empty_trend():
    m=build_metric_trend_chart_model({"metric_trend_schema_version":1,"analysis_type":"snr","metric_name":"snr","points":[]}); assert m["point_count"]==0

def test_build_metric_trend_chart_model_maps_points(): assert build_metric_trend_chart_model(_trend())["point_count"]>=1

def test_build_metric_trend_chart_model_preserves_validity_and_threshold_status():
    p=build_metric_trend_chart_model(_trend())["points"][0]; assert "validity" in p and "threshold_overall_status" in p

def test_build_metric_trend_chart_model_computes_y_min_y_max_latest():
    m=build_metric_trend_chart_model(_trend()); assert m["y_min"] is not None and m["latest"] is not None

def test_build_metric_trend_chart_model_rejects_wrong_schema_version():
    with pytest.raises(ValueError): build_metric_trend_chart_model({"metric_trend_schema_version":9})

def test_build_metric_trend_chart_model_rejects_non_finite_y():
    with pytest.raises(ValueError): build_metric_trend_chart_model({"metric_trend_schema_version":1,"analysis_type":"a","metric_name":"m","points":[{"value":float('inf')}]})

def test_render_metric_trend_chart_text_contains_summary_and_points(): assert "Point Count" in render_metric_trend_chart_text(build_metric_trend_chart_model(_trend()))
def test_render_metric_trend_chart_text_handles_empty_chart(): assert "No chart points" in render_metric_trend_chart_text(build_metric_trend_chart_model({"metric_trend_schema_version":1,"analysis_type":"a","metric_name":"m","points":[]}))
def test_trend_chart_helpers_do_not_mutate_trend_series(): t=_trend(); b=json.loads(json.dumps(t)); _=build_metric_trend_chart_model(t); assert t==b
def test_trend_chart_does_not_dump_mtf_curve_raw_points(): assert "curve" not in render_metric_trend_chart_text(build_metric_trend_chart_model(build_metric_trend_series(_records(),"mtf","mtf50")))

def test_viewer_build_metric_trend_chart_model_loads_jsonl(tmp_path):
    p=tmp_path/"h.jsonl"; [append_analysis_history_record(p,r) for r in _records()]; v=_viewer_for_export(); assert DicomViewer.build_metric_trend_chart_model_for_viewer(v,p,"snr","snr")["point_count"]>=1

def test_viewer_render_metric_trend_chart_text_loads_jsonl(tmp_path):
    p=tmp_path/"h.jsonl"; [append_analysis_history_record(p,r) for r in _records()]; v=_viewer_for_export(); assert "Point Count" in (DicomViewer.render_metric_trend_chart_text_for_viewer(v,p,"snr","snr") or "")

def test_viewer_trend_chart_dialog_cancel_returns_none_without_mutation(monkeypatch):
    v=_viewer_for_export(); monkeypatch.setattr("dicom_viewer.filedialog.askopenfilename", lambda **_: ""); assert DicomViewer.render_metric_trend_chart_text_for_viewer(v,analysis_type="snr",metric_name="snr") is None

def test_show_metric_trend_chart_viewer_uses_chart_model_without_mutation(monkeypatch,tmp_path):
    class D:
        def title(self,*_): pass
        def geometry(self,*_): pass
    class W:
        def pack(self,*_,**__): pass
        def insert(self,*_,**__): pass
        def configure(self,*_,**__): pass
        def create_oval(self,*_,**__): pass
        def create_line(self,*_,**__): pass
    monkeypatch.setattr("dicom_viewer.tk.Toplevel", lambda *_,**__: D())
    monkeypatch.setattr("dicom_viewer.tk.Text", lambda *_,**__: W())
    monkeypatch.setattr("dicom_viewer.tk.Canvas", lambda *_,**__: W())
    p=tmp_path/"h.jsonl"; recs=_records(); b=json.loads(json.dumps(recs, default=str)); [append_analysis_history_record(p,r) for r in recs]; v=_viewer_for_export(); _=DicomViewer.show_metric_trend_chart_viewer(v,p,"snr","snr"); assert recs[0]["record_id"]==b[0]["record_id"]
