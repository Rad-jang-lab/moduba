from __future__ import annotations

import csv
import io
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis_thresholds import evaluate_analysis_thresholds, validate_threshold_config


def _validate_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("history_schema_version") != 1:
        raise ValueError("unsupported history schema version")
    return dict(record)


def build_batch_qc_item_from_history_record(record: dict[str, Any], threshold_config: dict[str, Any] | None = None) -> dict[str, Any]:
    r = _validate_record(record)
    results = ((r.get("export_snapshot") or {}).get("results") or {})
    validity_counts = {"valid": 0, "invalid": 0, "unknown": 0}
    warning_count = 0
    for item in results.values():
        if not isinstance(item, dict):
            continue
        v = str(item.get("validity", "unknown"))
        validity_counts[v if v in validity_counts else "unknown"] += 1
        warning_count += len(item.get("warnings") or [])
    threshold_eval = None
    if threshold_config is not None:
        cfg = validate_threshold_config({**dict(threshold_config), "rules": [dict(x) for x in (threshold_config.get("rules") or [])]})
        threshold_eval = _sanitize_non_finite(evaluate_analysis_thresholds(results, cfg, generated_at=str(r.get("generated_at", ""))))
    return {
        "batch_item_schema_version": 1,
        "record_id": str(r.get("record_id", "")),
        "generated_at": str(r.get("generated_at", "")),
        "metadata": dict(r.get("metadata") or {}),
        "summary": dict(r.get("summary") or {}),
        "analysis_types": sorted(list(results.keys())),
        "validity_counts": validity_counts,
        "warning_count": warning_count,
        "threshold_evaluation": threshold_eval,
    }


def summarize_batch_qc_run(batch_run: dict[str, Any]) -> dict[str, Any]:
    items = batch_run.get("items") or []
    t = {"pass": 0, "warn": 0, "fail": 0, "not_evaluated": 0, "missing": 0}
    analysis_counts: dict[str, int] = {}
    valid_item_count = 0
    invalid_item_count = 0
    warning_count = 0
    for i in items:
        vc = i.get("validity_counts") or {}
        warning_count += int(i.get("warning_count", 0))
        if int(vc.get("invalid", 0)) > 0:
            invalid_item_count += 1
        else:
            valid_item_count += 1
        for a in i.get("analysis_types") or []:
            analysis_counts[a] = analysis_counts.get(a, 0) + 1
        te = i.get("threshold_evaluation")
        if isinstance(te, dict):
            s = str(te.get("overall_status", "not_evaluated"))
            t[s if s in t else "not_evaluated"] += 1
        else:
            t["missing"] += 1
    return {"valid_item_count": valid_item_count, "invalid_item_count": invalid_item_count, "warning_count": warning_count, "threshold_status_counts": t, "analysis_counts": dict(sorted(analysis_counts.items()))}


def build_batch_qc_run(records: list[dict[str, Any]], threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, generated_at: str | None = None, batch_id: str | None = None) -> dict[str, Any]:
    items = [build_batch_qc_item_from_history_record(r, threshold_config=threshold_config) for r in records]
    run = {"batch_qc_schema_version": 1, "batch_id": batch_id or f"batch_{uuid.uuid4().hex}", "generated_at": generated_at or datetime.now(timezone.utc).isoformat(), "metadata": dict(metadata or {}), "item_count": len(items), "summary": {}, "items": items}
    run["summary"] = summarize_batch_qc_run(run)
    return run


def render_batch_qc_summary_text(batch_run: dict[str, Any]) -> str:
    s = batch_run.get("summary") or {}
    lines = [f"Batch ID: {batch_run.get('batch_id')}", f"Generated At: {batch_run.get('generated_at')}", f"Item Count: {batch_run.get('item_count')}", f"Summary: {s}"]
    for i, it in enumerate(batch_run.get("items") or []):
        te = it.get("threshold_evaluation") or {}
        lines.append(f"- [{i}] {it.get('record_id')} | {it.get('generated_at')} | analyses={it.get('analysis_types')} | validity={it.get('validity_counts')} | warnings={it.get('warning_count')} | threshold={te.get('overall_status','missing') if te else 'missing'}")
    return "\n".join(lines) + "\n"


def export_batch_qc_run_to_json(batch_run: dict[str, Any], path: str | Path | None = None) -> str:
    text = json.dumps(batch_run, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def export_batch_qc_run_to_csv(batch_run: dict[str, Any], path: str | Path | None = None) -> str:
    fields = ["batch_qc_schema_version", "batch_id", "batch_generated_at", "item_index", "record_id", "record_generated_at", "analysis_types_json", "valid_count", "invalid_count", "unknown_count", "warning_count", "threshold_overall_status", "metadata_json", "summary_json"]
    io_buf = io.StringIO()
    w = csv.DictWriter(io_buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for idx, it in enumerate(batch_run.get("items") or []):
        vc = it.get("validity_counts") or {}
        te = it.get("threshold_evaluation") or {}
        w.writerow({"batch_qc_schema_version": 1, "batch_id": batch_run.get("batch_id", ""), "batch_generated_at": batch_run.get("generated_at", ""), "item_index": idx, "record_id": it.get("record_id", ""), "record_generated_at": it.get("generated_at", ""), "analysis_types_json": json.dumps(it.get("analysis_types") or [], ensure_ascii=False, sort_keys=True), "valid_count": vc.get("valid", 0), "invalid_count": vc.get("invalid", 0), "unknown_count": vc.get("unknown", 0), "warning_count": it.get("warning_count", 0), "threshold_overall_status": te.get("overall_status", "missing") if te else "missing", "metadata_json": json.dumps(it.get("metadata") or {}, ensure_ascii=False, sort_keys=True), "summary_json": json.dumps(it.get("summary") or {}, ensure_ascii=False, sort_keys=True)})
    text = io_buf.getvalue()
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text
def _sanitize_non_finite(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        return [_sanitize_non_finite(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_non_finite(v) for k, v in value.items()}
    return value
