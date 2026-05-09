from __future__ import annotations

from typing import Any

from analysis_history_store import filter_analysis_history_records

_SCHEMA_VERSION = 1
_DISPLAY_SCHEMA_VERSION = 1


def _validate_record(record: dict[str, Any]) -> None:
    if record is None:
        raise ValueError("record is None")
    if record.get("history_schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported history schema version")


def build_history_record_display_model(record: dict[str, Any]) -> dict[str, Any]:
    _validate_record(record)
    results = ((record.get("export_snapshot") or {}).get("results") or {})
    analysis_rows = []
    for analysis_type in sorted(results.keys()):
        item = results[analysis_type] or {}
        row = {
            "analysis_type": analysis_type,
            "status": str(item.get("status", "")),
            "validity": str(item.get("validity", "")),
            "metric_names": sorted((item.get("metrics") or {}).keys()),
            "warning_count": len(item.get("warnings") or []),
            "reason_count": len(item.get("reason_codes") or []),
        }
        if analysis_type == "mtf":
            curve = ((item.get("curves") or {}).get("mtf") or {})
            row["mtf_point_count"] = min(len(curve.get("x") or []), len(curve.get("y") or []))
        analysis_rows.append(row)
    return {
        "record_id": record.get("record_id"),
        "generated_at": record.get("generated_at"),
        "metadata": dict(record.get("metadata") or {}),
        "summary": dict(record.get("summary") or {}),
        "analysis_rows": analysis_rows,
    }


def build_history_records_display_model(records: list[dict[str, Any]], analysis_type: str | None = None, validity: str | None = None) -> dict[str, Any]:
    filtered = filter_analysis_history_records(list(records), analysis_type=analysis_type, validity=validity)
    rows = []
    for record in filtered:
        _validate_record(record)
        s = dict(record.get("summary") or {})
        row = {
            "record_id": record.get("record_id"),
            "generated_at": record.get("generated_at"),
            "analysis_count": s.get("analysis_count", 0),
            "valid_count": s.get("valid_count", 0),
            "invalid_count": s.get("invalid_count", 0),
            "warning_count": s.get("warning_count", 0),
            "analysis_types": list(s.get("analysis_types") or []),
        }
        te = record.get("threshold_evaluation") or {}
        if te:
            row["threshold_overall_status"] = te.get("overall_status", "")
        rows.append(row)
    return {
        "history_display_schema_version": _DISPLAY_SCHEMA_VERSION,
        "record_count": len(rows),
        "filters": {"analysis_type": analysis_type, "validity": validity},
        "rows": rows,
    }


def render_history_record_detail_text(record: dict[str, Any]) -> str:
    model = build_history_record_display_model(record)
    lines = [f"Record ID: {model['record_id']}", f"Generated At: {model['generated_at']}"]
    lines.append(f"Metadata: {model['metadata']}")
    lines.append(f"Summary: {model['summary']}")
    results = ((record.get("export_snapshot") or {}).get("results") or {})
    te = record.get("threshold_evaluation") or {}
    if te:
        lines.append("[THRESHOLD]")
        lines.append(f"config_name: {te.get('config_name','')}")
        lines.append(f"overall_status: {te.get('overall_status','')}")
        lines.append(f"summary: {te.get('summary', {})}")
        for r in list(te.get("results") or []):
            lines.append(f"rule {r.get('rule_id','')}: status={r.get('status','')}, reason={r.get('reason','')}")

    for analysis_type in sorted(results.keys()):
        item = results[analysis_type] or {}
        lines.append(f"[{analysis_type.upper()}]")
        lines.append(f"status: {item.get('status', '')}")
        lines.append(f"validity: {item.get('validity', '')}")
        lines.append(f"metrics: {sorted((item.get('metrics') or {}).keys())}")
        lines.append(f"warnings: {item.get('warnings') or []}")
        lines.append(f"reason_codes: {item.get('reason_codes') or []}")
        lines.append(f"roi_info: {item.get('roi_info') or {}}")
        if analysis_type == "mtf":
            curve = ((item.get("curves") or {}).get("mtf") or {})
            lines.append(f"mtf_point_count: {min(len(curve.get('x') or []), len(curve.get('y') or []))}")
    return "\n".join(lines) + "\n"
