import csv
import json
from pathlib import Path

from iqa_report import build_iqa_report
from iqa_report_export import build_iqa_report_export_bundle
from iqa_report_file_export import (
    write_iqa_report_txt,
    write_iqa_report_json,
    write_iqa_report_csv,
    write_iqa_report_export_bundle,
)
from tests.test_iqa_report_export import _entry


def test_write_txt_file(tmp_path):
    report = build_iqa_report(_entry())
    bundle = build_iqa_report_export_bundle(report)
    out = write_iqa_report_txt(tmp_path / "r.txt", bundle["txt"])
    assert out["status"] == "success"
    text = (tmp_path / "r.txt").read_text(encoding="utf-8")
    assert "IQA Report" in text and "Reference:" in text and "Target:" in text


def test_write_json_file(tmp_path):
    report = build_iqa_report(_entry())
    bundle = build_iqa_report_export_bundle(report)
    write_iqa_report_json(tmp_path / "r.json", bundle["json"])
    payload = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert payload["report_type"] == "iqa_single"
    assert "interpretation" in payload


def test_write_csv_file(tmp_path):
    report = build_iqa_report(_entry())
    bundle = build_iqa_report_export_bundle(report)
    write_iqa_report_csv(tmp_path / "r.csv", bundle["csv_rows"])
    with (tmp_path / "r.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and "metric_psnr" in rows[0] and "metric_ssim" in rows[0] and "status" in rows[0]


def test_write_bundle_all_formats(tmp_path):
    report = build_iqa_report(_entry())
    bundle = build_iqa_report_export_bundle(report)
    res = write_iqa_report_export_bundle(bundle, output_dir=tmp_path, base_name="bundle")
    assert len(res["files"]) == 3
    assert (tmp_path / "bundle.txt").exists() and (tmp_path / "bundle.json").exists() and (tmp_path / "bundle.csv").exists()


def test_write_bundle_selected_formats(tmp_path):
    report = build_iqa_report(_entry())
    bundle = build_iqa_report_export_bundle(report)
    write_iqa_report_export_bundle(bundle, output_dir=tmp_path, base_name="only_json", formats=("json",))
    assert (tmp_path / "only_json.json").exists()
    assert not (tmp_path / "only_json.txt").exists()


def test_invalid_format_and_empty_csv_rows_policy(tmp_path):
    report = build_iqa_report(_entry())
    bundle = build_iqa_report_export_bundle(report)
    try:
        write_iqa_report_export_bundle(bundle, output_dir=tmp_path, base_name="bad", formats=("xml",))
        assert False
    except ValueError:
        pass
    try:
        write_iqa_report_csv(tmp_path / "e.csv", [])
        assert False
    except ValueError:
        pass


def test_csv_safe_conversion_and_no_ui_dependency(tmp_path):
    rows = [{"a": {"k": 1}, "b": [1, 2], "c": (3, 4), "d": None}]
    write_iqa_report_csv(tmp_path / "safe.csv", rows)
    assert (tmp_path / "safe.csv").exists()
    src = Path("iqa_report_file_export.py").read_text(encoding="utf-8")
    assert "tkinter" not in src and "filedialog" not in src
