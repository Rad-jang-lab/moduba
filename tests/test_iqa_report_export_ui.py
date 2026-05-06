from pathlib import Path

from iqa_report import build_iqa_report
from iqa_report_export_ui import (
    build_iqa_report_export_cancel_status,
    build_iqa_report_export_no_report_status,
    format_iqa_report_export_status,
    get_iqa_report_export_format_label,
    get_iqa_report_export_format_options,
    normalize_iqa_report_export_format,
    resolve_latest_iqa_report_for_export,
    save_iqa_report_bundle,
)
from iqa_report_export import build_iqa_report_export_bundle
from tests.test_iqa_report_export import _entry


def test_format_normalization_and_labels():
    assert normalize_iqa_report_export_format("txt") == "txt"
    assert normalize_iqa_report_export_format("JSON") == "json"
    assert normalize_iqa_report_export_format("bad") == "txt"
    assert get_iqa_report_export_format_label("csv") == "CSV"
    assert ("all", "All") in get_iqa_report_export_format_options()


def test_latest_report_resolve_policy():
    r = build_iqa_report(_entry())
    assert resolve_latest_iqa_report_for_export({"iqa_report": r}, []) == r
    assert resolve_latest_iqa_report_for_export({}, [_entry().__dict__])["reference_label"] == "Ref"
    assert resolve_latest_iqa_report_for_export({}, []) is None


def test_save_execution_helper_and_status_messages(tmp_path):
    report = build_iqa_report(_entry())
    bundle = build_iqa_report_export_bundle(report)
    txt = save_iqa_report_bundle(bundle, "txt", str(tmp_path / "a.txt"))
    js = save_iqa_report_bundle(bundle, "json", str(tmp_path / "a.json"))
    cs = save_iqa_report_bundle(bundle, "csv", str(tmp_path / "a.csv"))
    al = save_iqa_report_bundle(bundle, "all", str(tmp_path), base_name="allx")
    assert txt["status"] == js["status"] == cs["status"] == al["status"] == "success"
    assert "저장 완료" in format_iqa_report_export_status(txt)
    assert build_iqa_report_export_cancel_status() == "IQA report 저장 취소"
    assert "저장할 IQA report가 없습니다" in build_iqa_report_export_no_report_status()


def test_no_ui_dependency():
    src = Path("iqa_report_export_ui.py").read_text(encoding="utf-8")
    assert "tkinter" not in src and "filedialog" not in src and "messagebox" not in src
