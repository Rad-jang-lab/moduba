from __future__ import annotations

import copy
import json

import pytest

from analysis_batch_qc import build_batch_qc_run
from analysis_batch_qc_report import *
from tests.test_analysis_history_summary import _records


def _run():
    return build_batch_qc_run(_records())


def test_build_batch_qc_report_model_from_run():
    m = build_batch_qc_report_model(_run())
    assert m["batch_qc_report_schema_version"] == 1 and m["batch"]["item_count"] >= 1

def test_batch_qc_report_model_preserves_item_order():
    run = _run(); m = build_batch_qc_report_model(run)
    assert [i["record_id"] for i in m["items"]] == [i.get("record_id") for i in run["items"]]

def test_batch_qc_report_model_threshold_missing_status():
    assert build_batch_qc_report_model(_run())["items"][0]["threshold_overall_status"] == "missing"

def test_batch_qc_report_model_threshold_overall_status():
    run = _run(); run["items"][0]["threshold_evaluation"] = {"overall_status": "pass"}
    assert build_batch_qc_report_model(run)["items"][0]["threshold_overall_status"] == "pass"

def test_render_batch_qc_report_text_contains_summary():
    t = render_batch_qc_report_text(build_batch_qc_report_model(_run()))
    assert "Batch ID" in t and "Item Count" in t and "Threshold Status Counts" in t

def test_export_batch_qc_report_to_json_disallows_nan():
    m = build_batch_qc_report_model(_run()); m["summary"]["x"] = float("nan")
    with pytest.raises(ValueError): export_batch_qc_report_to_json(m)

def test_export_batch_qc_report_to_text_roundtrip(tmp_path):
    p = tmp_path / "r.txt"; m = build_batch_qc_report_model(_run())
    t = export_batch_qc_report_to_text(m, p)
    assert p.read_text() == t

def test_export_batch_qc_report_to_pdf_returns_pdf_bytes(tmp_path):
    p = tmp_path / "r.pdf"
    b = export_batch_qc_report_to_pdf(build_batch_qc_report_model(_run()), p)
    assert b.startswith(b"%PDF-") and p.read_bytes().startswith(b"%PDF-")

def test_batch_qc_report_module_does_not_import_tkinter_or_pydicom():
    src = open("analysis_batch_qc_report.py", encoding="utf-8").read()
    assert "import tkinter" not in src and "import pydicom" not in src

def test_batch_qc_report_model_does_not_mutate_input():
    run = _run(); b = copy.deepcopy(run)
    _ = build_batch_qc_report_model(run)
    assert run == b
