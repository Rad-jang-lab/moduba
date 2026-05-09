from __future__ import annotations

from pathlib import Path
from typing import Any


def build_analysis_report_pdf_lines(report_model: dict[str, Any]) -> list[str]:
    if report_model is None:
        raise ValueError("report_model is None")
    lines: list[str] = [
        "QC Analysis Report",
        f"Generated At: {report_model.get('generated_at', '')}",
    ]
    metadata = dict(report_model.get("metadata") or {})
    if metadata:
        lines.append("Metadata:")
        for key in sorted(metadata.keys()):
            lines.append(f"- {key}: {metadata[key]}")
    summary = dict(report_model.get("summary") or {})
    lines.extend(
        [
            "Summary:",
            f"- analysis_count: {summary.get('analysis_count', 0)}",
            f"- valid_count: {summary.get('valid_count', 0)}",
            f"- invalid_count: {summary.get('invalid_count', 0)}",
            f"- warning_count: {summary.get('warning_count', 0)}",
            f"- analysis_types: {', '.join(summary.get('analysis_types', []))}",
        ]
    )
    threshold_eval = report_model.get("threshold_evaluation")
    if threshold_eval:
        lines.append("")
        lines.append("QC Threshold Evaluation:")
        lines.append(f"- overall_status: {threshold_eval.get('overall_status', '')}")
        lines.append(f"- summary: {threshold_eval.get('summary', {})}")
        for r in list(threshold_eval.get("results") or []):
            lines.append(f"- rule {r.get('rule_id','')}: status={r.get('status','')}, reason={r.get('reason','')}")

    for section in list(report_model.get("sections") or []):
        lines.append("")
        lines.append(f"[{section.get('title', section.get('analysis_type', 'Analysis'))}]")
        lines.append(f"analysis_type: {section.get('analysis_type', '')}")
        lines.append(f"status: {section.get('status', '')}")
        lines.append(f"validity: {section.get('validity', '')}")
        lines.append("metrics:")
        for metric in list(section.get("metrics") or []):
            lines.append(f"- {metric.get('name', '')}: {metric.get('formatted_value', metric.get('value', ''))}")
        if section.get("curve_summaries"):
            lines.append("curve_summaries:")
            for curve in list(section.get("curve_summaries") or []):
                lines.append(
                    f"- {curve.get('name', '')}: point_count={curve.get('point_count', 0)}, x_label={curve.get('x_label', '')}, y_label={curve.get('y_label', '')}"
                )
        lines.append(f"warnings: {list(section.get('warnings') or [])}")
        lines.append(f"reason_codes: {list(section.get('reason_codes') or [])}")
        lines.append(f"roi_info: {dict(section.get('roi_info') or {})}")
        lines.append(f"source_payload_keys: {list(section.get('source_payload_keys') or [])}")
    return lines


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_analysis_report_pdf_bytes(report_model: dict[str, Any]) -> bytes:
    lines = build_analysis_report_pdf_lines(report_model)
    text_lines = [f"({_escape_pdf_text(line)}) Tj" for line in lines]
    content = "BT /F1 10 Tf 50 790 Td 14 TL " + " T* ".join(text_lines) + " ET"
    content_bytes = content.encode("latin-1", errors="replace")

    objs = []
    objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objs.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n")
    objs.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objs.append(f"5 0 obj << /Length {len(content_bytes)} >> stream\n".encode("ascii") + content_bytes + b"\nendstream endobj\n")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objs)+1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)


def export_analysis_report_to_pdf(report_model: dict[str, Any], path: str | Path | None = None) -> bytes:
    pdf_bytes = render_analysis_report_pdf_bytes(report_model)
    if path is not None:
        Path(path).write_bytes(pdf_bytes)
    return pdf_bytes
