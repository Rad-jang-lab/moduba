from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_report_model_from_normalized_batch_qc_run(batch_qc_run: dict[str, Any], metadata: dict[str, Any] | None = None, generated_at: str | None = None) -> dict[str, Any]:
    if batch_qc_run is None:
        raise ValueError("batch_qc_run is empty")
    run = dict(batch_qc_run)
    if run.get("batch_qc_schema_version") != 1:
        raise ValueError("invalid batch_qc schema")
    items_out = []
    for idx, item in enumerate(run.get("items") or []):
        te = item.get("threshold_evaluation") or {}
        items_out.append({
            "item_index": idx,
            "record_id": item.get("record_id"),
            "analysis_types": list(item.get("analysis_types") or []),
            "validity_counts": dict(item.get("validity_counts") or {}),
            "warning_count": int(item.get("warning_count", 0)),
            "threshold_overall_status": te.get("overall_status", "missing") if isinstance(te, dict) and te else "missing",
            "metadata": dict(item.get("metadata") or {}),
        })
    model = {
        "normalized_batch_qc_report_schema_version": 1,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "metadata": dict(metadata or {}),
        "batch": {
            "batch_id": run.get("batch_id"),
            "batch_generated_at": run.get("generated_at"),
            "item_count": int(run.get("item_count", len(items_out))),
        },
        "summary": dict(run.get("summary") or {}),
        "items": items_out,
    }
    return validate_normalized_batch_qc_report_model(model)


def validate_normalized_batch_qc_report_model(report_model: dict[str, Any]) -> dict[str, Any]:
    payload = dict(report_model)
    if payload.get("normalized_batch_qc_report_schema_version") != 1:
        raise ValueError("invalid report schema")
    if not isinstance(payload.get("items"), list):
        raise ValueError("items must be list")
    return payload


def render_normalized_batch_qc_report_text(report_model: dict[str, Any]) -> str:
    m = validate_normalized_batch_qc_report_model(report_model)
    lines = [
        "Normalized Batch QC Report",
        f"Batch ID: {m['batch'].get('batch_id')}",
        f"Generated At: {m.get('generated_at')}",
        f"Item Count: {m['batch'].get('item_count')}",
        f"Summary: {m.get('summary')}",
    ]
    for item in m.get("items", []):
        lines.append(f"- [{item['item_index']}] {item['record_id']} analyses={item['analysis_types']} threshold={item['threshold_overall_status']} warnings={item['warning_count']}")
    return "\n".join(lines) + "\n"


def export_normalized_batch_qc_report_to_json(report_model: dict[str, Any], path: str | Path | None = None) -> str:
    text = json.dumps(validate_normalized_batch_qc_report_model(report_model), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def export_normalized_batch_qc_report_to_csv(report_model: dict[str, Any], path: str | Path | None = None) -> str:
    m = validate_normalized_batch_qc_report_model(report_model)
    fields = ["normalized_batch_qc_report_schema_version","generated_at","batch_id","item_index","record_id","analysis_types_json","threshold_overall_status","validity_counts_json","warning_count","metadata_json"]
    buf=io.StringIO(); w=csv.DictWriter(buf, fieldnames=fields, lineterminator="\n"); w.writeheader()
    for item in m.get("items", []):
        w.writerow({"normalized_batch_qc_report_schema_version":1,"generated_at":m.get("generated_at"),"batch_id":m["batch"].get("batch_id"),"item_index":item.get("item_index"),"record_id":item.get("record_id"),"analysis_types_json":json.dumps(item.get("analysis_types") or [],ensure_ascii=False,sort_keys=True),"threshold_overall_status":item.get("threshold_overall_status"),"validity_counts_json":json.dumps(item.get("validity_counts") or {},ensure_ascii=False,sort_keys=True),"warning_count":item.get("warning_count",0),"metadata_json":json.dumps(item.get("metadata") or {},ensure_ascii=False,sort_keys=True)})
    text=buf.getvalue()
    if path is not None: Path(path).write_text(text,encoding='utf-8')
    return text


def export_normalized_batch_qc_report_to_text(report_model: dict[str, Any], path: str | Path | None = None) -> str:
    text = render_normalized_batch_qc_report_text(report_model)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def render_normalized_batch_qc_report_pdf_bytes(report_model: dict[str, Any]) -> bytes:
    text = render_normalized_batch_qc_report_text(report_model)
    safe = text.encode("ascii", errors="replace")
    pdf = b"%PDF-1.1\n1 0 obj<<>>endobj\n2 0 obj<< /Length " + str(len(safe)+32).encode() + b" >>stream\nBT /F1 10 Tf 40 760 Td (Normalized Batch QC Report) Tj ET\nendstream\nendobj\ntrailer<<>>\n%%EOF"
    return pdf


def export_normalized_batch_qc_report_to_pdf(report_model: dict[str, Any], path: str | Path | None = None) -> bytes:
    data = render_normalized_batch_qc_report_pdf_bytes(report_model)
    if path is not None:
        Path(path).write_bytes(data)
    return data
