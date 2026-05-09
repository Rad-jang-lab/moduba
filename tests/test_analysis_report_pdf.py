from __future__ import annotations

import copy

from analysis_report_pdf import (
    build_analysis_report_pdf_lines,
    export_analysis_report_to_pdf,
    render_analysis_report_pdf_bytes,
)


def _report_model_fixture() -> dict:
    return {
        "report_schema_version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "metadata": {"app": "moduba", "report_source": "viewer"},
        "summary": {
            "analysis_count": 4,
            "valid_count": 3,
            "invalid_count": 1,
            "warning_count": 1,
            "analysis_types": ["snr", "cnr", "uniformity", "mtf"],
        },
        "sections": [
            {"analysis_type": "snr", "title": "SNR", "status": "success", "validity": "valid", "metrics": [{"name": "snr", "value": 2.5, "formatted_value": "2.5"}], "curve_summaries": [], "warnings": [], "reason_codes": [], "roi_info": {"signal_roi_id": "s"}, "source_payload_keys": ["result"]},
            {"analysis_type": "cnr", "title": "CNR", "status": "success", "validity": "valid", "metrics": [{"name": "cnr", "value": 1.2, "formatted_value": "1.2"}], "curve_summaries": [], "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
            {"analysis_type": "uniformity", "title": "Uniformity", "status": "success", "validity": "valid", "metrics": [{"name": "uniformity", "value": 88.8, "formatted_value": "88.8"}], "curve_summaries": [], "warnings": [], "reason_codes": [], "roi_info": {}, "source_payload_keys": ["result"]},
            {"analysis_type": "mtf", "title": "MTF", "status": "reject", "validity": "invalid", "metrics": [{"name": "mtf50", "value": 0.25, "formatted_value": "0.25"}], "curve_summaries": [{"name": "mtf", "point_count": 2, "x_label": "x", "y_label": "y"}], "warnings": ["w"], "reason_codes": ["r"], "roi_info": {}, "source_payload_keys": ["key_mtf_metrics", "mtf_curve"]},
        ],
    }


def test_build_report_pdf_lines_includes_summary_and_sections():
    lines = build_analysis_report_pdf_lines(_report_model_fixture())
    text = "\n".join(lines)
    assert "Summary:" in text
    assert "[SNR]" in text and "[CNR]" in text and "[Uniformity]" in text and "[MTF]" in text


def test_build_report_pdf_lines_includes_invalid_reasons():
    lines = build_analysis_report_pdf_lines(_report_model_fixture())
    text = "\n".join(lines)
    assert "validity: invalid" in text
    assert "reason_codes: ['r']" in text


def test_build_report_pdf_lines_summarizes_mtf_curve_without_expanding_points():
    lines = build_analysis_report_pdf_lines(_report_model_fixture())
    text = "\n".join(lines)
    assert "point_count=2" in text
    assert "[0.0, 0.1]" not in text


def test_render_analysis_report_pdf_bytes_returns_pdf_binary():
    data = render_analysis_report_pdf_bytes(_report_model_fixture())
    assert data.startswith(b"%PDF")


def test_export_analysis_report_to_pdf_writes_file(tmp_path):
    out = tmp_path / "report.pdf"
    data = export_analysis_report_to_pdf(_report_model_fixture(), path=out)
    assert out.read_bytes() == data
    assert data.startswith(b"%PDF")


def test_pdf_export_rejects_none_report_model():
    try:
        render_analysis_report_pdf_bytes(None)
    except ValueError:
        return
    raise AssertionError("ValueError expected")


def test_pdf_export_preserves_report_model_schema_without_mutation():
    model = _report_model_fixture()
    before = copy.deepcopy(model)
    _ = render_analysis_report_pdf_bytes(model)
    assert model == before


def test_pdf_output_order_is_deterministic():
    model = _report_model_fixture()
    a = render_analysis_report_pdf_bytes(model)
    b = render_analysis_report_pdf_bytes(model)
    assert a == b
