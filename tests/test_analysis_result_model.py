from __future__ import annotations

import csv
import io
import json
import numpy as np
import pytest

from analysis_result_model import normalize_analysis_last_run, normalize_analysis_result
from tests.test_mtf_reference_validation import _build_mtf_viewer, _deterministic_edge_roi
from dicom_viewer import DicomViewer


def test_normalize_snr_result_to_common_model():
    payload = {"status": "success", "result": 2.5, "signal_roi_id": "s1", "noise_roi_id": "n1"}
    out = normalize_analysis_result("snr", payload)
    assert out["metrics"]["snr"] == 2.5


def test_normalize_cnr_result_to_common_model():
    payload = {"status": "success", "result": 1.2, "inputs": {"region_a_roi_id": "a", "region_b_roi_id": "b", "noise_roi_id": "n"}}
    out = normalize_analysis_result("cnr", payload)
    assert out["metrics"]["cnr"] == 1.2


def test_normalize_uniformity_result_to_common_model():
    payload = {"status": "success", "result": {"value": 88.8}, "inputs": {"roi_ids": ["r1"], "roi_count": 1}}
    out = normalize_analysis_result("uniformity", payload)
    assert out["metrics"]["uniformity"] == 88.8


def test_normalize_mtf_result_to_common_model_with_curve():
    viewer = _build_mtf_viewer(mode="matlab_reference")
    payload = viewer._execute_mtf_pipeline(_deterministic_edge_roi(), (0, 0, 96, 96), "general_radiography", "strict_iec")
    out = normalize_analysis_result("mtf", payload)
    assert "mtf50" in out["metrics"]
    assert "mtf" in out["curves"]
    assert len(out["curves"]["mtf"]["x"]) == len(out["curves"]["mtf"]["y"])


def test_normalize_mtf_invalid_result_preserves_reason_codes():
    payload = {"calculation_status": "reject", "calculation_validity": "invalid", "reason_codes": ["EDGE_SNR_LOW"], "warnings": ["w"]}
    out = normalize_analysis_result("mtf", payload)
    assert out["reason_codes"] == ["EDGE_SNR_LOW"]
    assert out["warnings"] == ["w"]


def test_normalize_analysis_result_rejects_none_payload():
    with pytest.raises(ValueError):
        normalize_analysis_result("snr", None)


def test_normalize_analysis_last_run_skips_missing_keys():
    out = normalize_analysis_last_run({"snr": {"status": "success", "result": 1.0}})
    assert set(out.keys()) == {"snr"}


def test_normalize_analysis_last_run_rejects_existing_none_payload():
    with pytest.raises(ValueError):
        normalize_analysis_last_run({"snr": None})


def test_common_model_preserves_source_payload_keys():
    payload = {"status": "success", "result": 1.0, "extra": 1}
    out = normalize_analysis_result("snr", payload)
    assert "extra" in out["source_payload_keys"]


def test_common_model_rejects_or_flags_non_finite_metrics():
    payload = {"status": "success", "result": float("nan")}
    out = normalize_analysis_result("snr", payload)
    assert "snr" not in out["metrics"]
    assert "NON_FINITE_METRIC" in out["reason_codes"]


def test_viewer_result_display_uses_common_analysis_model_when_available():
    viewer = object.__new__(DicomViewer)
    viewer.analysis_last_run = {}
    viewer.analysis_last_run_normalized = {}
    viewer.analysis_last_run_display = {}
    viewer.window_b_manager = None
    viewer._ensure_domain_store = lambda: None
    viewer.domain_store = type("Store", (), {"set_analysis_last_run": lambda *_a, **_k: None})()
    DicomViewer._action_set_analysis_last_run(viewer, "snr", {"status": "success", "result": 3.0, "signal_roi_id": "s", "noise_roi_id": "n"})
    assert "snr" in viewer.analysis_last_run_normalized
    assert "snr" in viewer.analysis_last_run_display


def _normalized_export_fixture() -> dict[str, dict]:
    return {
        "snr": {"analysis_type": "snr", "status": "success", "validity": "valid", "metrics": {"snr": 2.5}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {"signal_roi_id": "s"}, "source_payload_keys": ["result"]},
        "cnr": {"analysis_type": "cnr", "status": "success", "validity": "valid", "metrics": {"cnr": 1.2}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
        "uniformity": {"analysis_type": "uniformity", "status": "success", "validity": "valid", "metrics": {"uniformity": 88.8}, "curves": {}, "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
        "mtf": {"analysis_type": "mtf", "status": "reject", "validity": "invalid", "metrics": {"mtf50": 0.25}, "curves": {"mtf": {"x": [0.0, 0.1], "y": [1.0, 0.8]}}, "warnings": ["w"], "reason_codes": ["r"], "roi_info": {}, "source_payload_keys": ["key_mtf_metrics", "mtf_curve"]},
    }


def _viewer_for_export() -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.analysis_last_run = {}
    viewer.analysis_last_run_normalized = {}
    return viewer


def test_viewer_export_uses_analysis_last_run_normalized_for_json(tmp_path):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    out = tmp_path / "a.json"
    text = DicomViewer.export_analysis_results_json(viewer, str(out))
    payload = json.loads(text or "{}")
    assert payload["export_schema_version"] == 1
    assert payload["results"]["snr"]["metrics"]["snr"] == 2.5
    assert out.exists()


def test_viewer_export_uses_analysis_last_run_normalized_for_csv(tmp_path):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    out = tmp_path / "a.csv"
    text = DicomViewer.export_analysis_results_csv(viewer, str(out))
    rows = list(csv.DictReader(io.StringIO(text or "")))
    assert any(r["analysis_type"] == "mtf" and r["item_type"] == "curve_point" for r in rows)
    assert out.exists()


def test_viewer_export_builds_normalized_cache_from_raw_last_run_when_needed():
    viewer = _viewer_for_export()
    viewer.analysis_last_run = {"snr": {"status": "success", "result": 3.1, "signal_roi_id": "s", "noise_roi_id": "n"}}
    out = DicomViewer._get_exportable_analysis_results(viewer)
    assert out["snr"]["metrics"]["snr"] == 3.1
    assert "snr" in viewer.analysis_last_run_normalized


def test_viewer_export_rejects_empty_results():
    viewer = _viewer_for_export()
    with pytest.raises(ValueError):
        DicomViewer._get_exportable_analysis_results(viewer)


def test_viewer_export_cancelled_dialog_does_not_write_file(monkeypatch, tmp_path):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_kwargs: "")
    res = DicomViewer.export_analysis_results_json(viewer)
    assert res is None
    assert list(tmp_path.iterdir()) == []


def test_viewer_report_uses_analysis_last_run_normalized(tmp_path):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    out = tmp_path / "report.md"
    text = DicomViewer.export_analysis_report_markdown(viewer, str(out))
    assert "## Summary" in (text or "")
    assert "## MTF" in (text or "")
    assert out.read_text(encoding="utf-8") == text


def test_viewer_report_builds_normalized_cache_from_raw_last_run_when_needed():
    viewer = _viewer_for_export()
    viewer.analysis_last_run = {"snr": {"status": "success", "result": 3.1, "signal_roi_id": "s", "noise_roi_id": "n"}}
    text = DicomViewer.render_current_analysis_report_markdown(viewer)
    assert "## SNR" in text
    assert "snr" in viewer.analysis_last_run_normalized


def test_viewer_report_rejects_empty_results():
    viewer = _viewer_for_export()
    with pytest.raises(ValueError):
        DicomViewer.render_current_analysis_report_markdown(viewer)


def test_viewer_report_preserves_invalid_warnings_and_reasons():
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    text = DicomViewer.render_current_analysis_report_markdown(viewer)
    assert "Validity: invalid" in text
    assert "Reason Codes: ['r']" in text


def test_viewer_report_cancelled_dialog_does_not_write_file(monkeypatch):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_kwargs: "")
    assert DicomViewer.export_analysis_report_markdown(viewer) is None


def test_viewer_report_does_not_expand_mtf_curve_raw_points():
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    text = DicomViewer.render_current_analysis_report_markdown(viewer)
    assert "[0.0, 0.1]" not in text


def test_viewer_pdf_report_uses_analysis_last_run_normalized(tmp_path):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    out = tmp_path / "report.pdf"
    data = DicomViewer.export_analysis_report_pdf(viewer, str(out))
    assert (data or b"").startswith(b"%PDF")
    assert out.read_bytes() == data


def test_viewer_pdf_report_builds_normalized_cache_from_raw_last_run_when_needed(tmp_path):
    viewer = _viewer_for_export()
    viewer.analysis_last_run = {"snr": {"status": "success", "result": 3.1, "signal_roi_id": "s", "noise_roi_id": "n"}}
    out = tmp_path / "report.pdf"
    data = DicomViewer.export_analysis_report_pdf(viewer, str(out))
    assert (data or b"").startswith(b"%PDF")
    assert "snr" in viewer.analysis_last_run_normalized


def test_viewer_pdf_report_rejects_empty_results(tmp_path):
    viewer = _viewer_for_export()
    with pytest.raises(ValueError):
        DicomViewer.export_analysis_report_pdf(viewer, str(tmp_path / "report.pdf"))


def test_viewer_pdf_report_cancelled_dialog_does_not_write_file(monkeypatch):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_kwargs: "")
    assert DicomViewer.export_analysis_report_pdf(viewer) is None


def test_viewer_pdf_report_preserves_invalid_warnings_and_reasons(tmp_path):
    from analysis_report_pdf import build_analysis_report_pdf_lines

    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    data = DicomViewer.export_analysis_report_pdf(viewer, str(tmp_path / "report.pdf"))
    assert (data or b"").startswith(b"%PDF")
    model = DicomViewer.build_current_analysis_report_model(viewer, metadata={"report_format": "pdf"})
    lines = "\n".join(build_analysis_report_pdf_lines(model))
    assert "validity: invalid" in lines
    assert "reason_codes: ['r']" in lines
    assert "[0.0, 0.1]" not in lines


def test_viewer_report_preview_uses_analysis_last_run_normalized():
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    text = DicomViewer.build_current_analysis_report_preview_text(viewer)
    assert "## Summary" in text
    assert "## SNR" in text and "## CNR" in text and "## Uniformity" in text and "## MTF" in text


def test_viewer_report_preview_builds_normalized_cache_from_raw_last_run_when_needed():
    viewer = _viewer_for_export()
    viewer.analysis_last_run = {"snr": {"status": "success", "result": 3.1, "signal_roi_id": "s", "noise_roi_id": "n"}}
    text = DicomViewer.build_current_analysis_report_preview_text(viewer)
    assert "## SNR" in text
    assert "snr" in viewer.analysis_last_run_normalized


def test_viewer_report_preview_rejects_empty_results():
    viewer = _viewer_for_export()
    with pytest.raises(ValueError):
        DicomViewer.build_current_analysis_report_preview_text(viewer)


def test_viewer_report_preview_preserves_invalid_warnings_and_reasons():
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    text = DicomViewer.build_current_analysis_report_preview_text(viewer)
    assert "Validity: invalid" in text
    assert "Reason Codes: ['r']" in text


def test_viewer_report_preview_does_not_expand_mtf_curve_raw_points():
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    text = DicomViewer.build_current_analysis_report_preview_text(viewer)
    assert "[0.0, 0.1]" not in text


def test_show_report_preview_uses_preview_text_without_mutating_results(monkeypatch):
    viewer = _viewer_for_export()
    viewer.analysis_last_run_normalized = _normalized_export_fixture()
    before = json.loads(json.dumps(viewer.analysis_last_run_normalized))
    created = {"text": ""}

    class _FakeWidget:
        def __init__(self, *_args, **_kwargs):
            pass

        def pack(self, *args, **kwargs):
            return None

        def configure(self, **kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class _FakeText(_FakeWidget):
        def insert(self, _index, value):
            created["text"] = value

        def yview(self, *_args, **_kwargs):
            return None

    class _FakeTop(_FakeWidget):
        def title(self, *_args, **_kwargs):
            return None

        def geometry(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("dicom_viewer.tk.Toplevel", _FakeTop)
    monkeypatch.setattr("dicom_viewer.tk.Text", _FakeText)
    monkeypatch.setattr("dicom_viewer.ttk.Frame", _FakeWidget)
    monkeypatch.setattr("dicom_viewer.ttk.Scrollbar", _FakeWidget)
    text = DicomViewer.show_analysis_report_preview(viewer)
    assert "## Summary" in text
    assert created["text"] == text
    assert viewer.analysis_last_run_normalized == before
