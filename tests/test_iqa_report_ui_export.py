import csv
import json
from pathlib import Path

from dicom_viewer import DicomViewer, IQA_BUTTON_LABELS
from tests.test_iqa_report_export import _entry
from tests.test_iqa_ui_wiring import DummyVar, _build_viewer
from iqa_report import build_iqa_report


def _prep_viewer_with_export_state():
    v = _build_viewer()
    v.image_analysis_inputs["iqa_report_export_format"] = DummyVar("txt")
    v.image_analysis_results["iqa_export_status"] = DummyVar("")
    v.iqa_history = []
    return v


def test_default_export_format_state_and_internal_value():
    v = _prep_viewer_with_export_state()
    assert v._get_iqa_report_export_format() == "txt"
    assert IQA_BUTTON_LABELS["set_ref"] == "Set Ref"
    assert IQA_BUTTON_LABELS["set_target"] == "Set Target"
    assert IQA_BUTTON_LABELS["save_report"] == "Save Report"


def test_resolve_latest_report_from_analysis_last_run():
    v = _prep_viewer_with_export_state()
    report = build_iqa_report(_entry())
    v.analysis_last_run["iqa_report"] = report
    resolved = v._resolve_latest_iqa_report_for_export()
    assert resolved["report_type"] == "iqa_single"


def test_resolve_latest_report_from_history_fallback():
    v = _prep_viewer_with_export_state()
    v.iqa_history = [_entry().__dict__]
    resolved = v._resolve_latest_iqa_report_for_export()
    assert resolved and resolved["reference_label"] == "Ref"


def test_no_report_state_does_not_write(monkeypatch):
    v = _prep_viewer_with_export_state()
    called = {"n": 0}
    monkeypatch.setattr("iqa_report_ui_export.write_iqa_report_txt", lambda *a, **k: called.__setitem__("n", 1))
    v._save_latest_iqa_report()
    assert called["n"] == 0
    assert "저장할 IQA report가 없습니다" in v.image_analysis_results["iqa_export_status"].get()


def test_save_txt_json_csv_and_all(tmp_path):
    v = _prep_viewer_with_export_state()
    v.analysis_last_run["iqa_report"] = build_iqa_report(_entry())

    # txt
    txt = tmp_path / "a.txt"
    v._ask_iqa_report_save_path = lambda fmt, default_name: str(txt)
    v.image_analysis_inputs["iqa_report_export_format"].set("txt")
    v._save_latest_iqa_report()
    assert txt.exists()

    # json
    js = tmp_path / "a.json"
    v._ask_iqa_report_save_path = lambda fmt, default_name: str(js)
    v.image_analysis_inputs["iqa_report_export_format"].set("json")
    v._save_latest_iqa_report()
    json.loads(js.read_text(encoding="utf-8"))

    # csv
    cs = tmp_path / "a.csv"
    v._ask_iqa_report_save_path = lambda fmt, default_name: str(cs)
    v.image_analysis_inputs["iqa_report_export_format"].set("csv")
    v._save_latest_iqa_report()
    with cs.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows

    # all
    v._ask_iqa_report_save_directory = lambda default_name: str(tmp_path)
    v.image_analysis_inputs["iqa_report_export_format"].set("all")
    v._save_latest_iqa_report()
    assert len(list(Path(tmp_path).glob("iqa_report_*.txt"))) >= 1


def test_cancel_and_invalid_and_error_handling(monkeypatch, tmp_path):
    v = _prep_viewer_with_export_state()
    invalid = build_iqa_report(_entry(status="invalid", idx="2"))
    v.analysis_last_run["iqa_report"] = invalid
    v._ask_iqa_report_save_path = lambda fmt, default_name: ""
    v._save_latest_iqa_report()
    assert "취소" in v.image_analysis_results["iqa_export_status"].get()

    v._ask_iqa_report_save_path = lambda fmt, default_name: str(tmp_path / "inv.json")
    v.image_analysis_inputs["iqa_report_export_format"].set("json")
    v._save_latest_iqa_report()
    payload = json.loads((tmp_path / "inv.json").read_text(encoding="utf-8"))
    assert payload["status"] == "invalid"

    monkeypatch.setattr("iqa_report_export_ui.write_iqa_report_json", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    v._save_latest_iqa_report()
    assert "저장 실패" in v.image_analysis_results["iqa_export_status"].get()
