from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_batch_qc_report_model(batch_run: dict[str, Any], metadata: dict[str, Any] | None = None, generated_at: str | None = None) -> dict[str, Any]:
    payload = dict(batch_run or {})
    if payload.get("batch_qc_schema_version") != 1:
        raise ValueError("unsupported batch_qc schema")
    items_out = []
    for idx, item in enumerate(list(payload.get("items") or [])):
        i = dict(item)
        threshold_eval = i.get("threshold_evaluation")
        threshold_status = "missing"
        if isinstance(threshold_eval, dict):
            threshold_status = str(threshold_eval.get("overall_status", "missing"))
        items_out.append(
            {
                "item_index": idx,
                "record_id": str(i.get("record_id", "")),
                "record_generated_at": str(i.get("generated_at", "")),
                "analysis_types": list(i.get("analysis_types") or []),
                "validity_counts": dict(i.get("validity_counts") or {}),
                "warning_count": int(i.get("warning_count", 0)),
                "threshold_overall_status": threshold_status,
                "metadata": dict(i.get("metadata") or {}),
                "summary": dict(i.get("summary") or {}),
            }
        )
    out = {
        "batch_qc_report_schema_version": 1,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "metadata": dict(metadata or {}),
        "batch": {
            "batch_id": str(payload.get("batch_id", "")),
            "batch_generated_at": str(payload.get("generated_at", "")),
            "item_count": int(payload.get("item_count", len(items_out))),
        },
        "summary": dict(payload.get("summary") or {}),
        "items": items_out,
    }
    return out


def render_batch_qc_report_text(report_model: dict[str, Any]) -> str:
    m = dict(report_model or {})
    b = dict(m.get("batch") or {})
    s = dict(m.get("summary") or {})
    lines = [
        "Batch QC Report",
        f"Report Generated At: {m.get('generated_at', '')}",
        f"Batch ID: {b.get('batch_id', '')}",
        f"Batch Generated At: {b.get('batch_generated_at', '')}",
        f"Item Count: {b.get('item_count', 0)}",
        f"Valid/Invalid Items: {s.get('valid_item_count', 0)} / {s.get('invalid_item_count', 0)}",
        f"Warning Count: {s.get('warning_count', 0)}",
        f"Threshold Status Counts: {s.get('threshold_status_counts', {})}",
        f"Analysis Counts: {s.get('analysis_counts', {})}",
    ]
    for item in list(m.get("items") or []):
        md = dict(item.get("metadata") or {})
        loc = md.get("dicom_path") or md.get("item_id") or ""
        lines.append(
            f"- [{item.get('item_index')}] record_id={item.get('record_id')} analyses={item.get('analysis_types')} validity={item.get('validity_counts')} warnings={item.get('warning_count')} threshold={item.get('threshold_overall_status')} location={loc}"
        )
    return "\n".join(lines) + "\n"


def export_batch_qc_report_to_json(report_model: dict[str, Any], path: str | Path | None = None) -> str:
    text = json.dumps(report_model, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def export_batch_qc_report_to_text(report_model: dict[str, Any], path: str | Path | None = None) -> str:
    text = render_batch_qc_report_text(report_model)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_batch_qc_report_pdf_bytes(report_model: dict[str, Any]) -> bytes:
    lines = render_batch_qc_report_text(report_model).splitlines()
    cmds = [f"({_escape_pdf_text(line)}) Tj" for line in lines]
    content = "BT /F1 10 Tf 50 790 Td 14 TL " + " T* ".join(cmds) + " ET"
    c = content.encode("latin-1", errors="replace")
    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(c)} >> stream\n".encode("ascii") + c + b"\nendstream endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offs = [0]
    for o in objs:
        offs.append(len(pdf)); pdf.extend(o)
    xoff = len(pdf)
    pdf.extend(f"xref\n0 {len(objs)+1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offs[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xoff}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)


def export_batch_qc_report_to_pdf(report_model: dict[str, Any], path: str | Path | None = None) -> bytes:
    b = render_batch_qc_report_pdf_bytes(report_model)
    if path is not None:
        Path(path).write_bytes(b)
    return b
