from __future__ import annotations

import json
from typing import Any, Mapping

from iqa_history import IQAHistoryEntry
from iqa_report import (
    build_iqa_history_summary_report,
    build_iqa_report,
    flatten_iqa_history_summary_for_export,
    flatten_iqa_report_for_export,
    format_iqa_history_summary_text,
    format_iqa_report_text,
    iqa_report_to_jsonable,
)
from iqa_result_schema import to_jsonable


def _to_csv_safe(value: Any) -> Any:
    safe = to_jsonable(value)
    if isinstance(safe, (dict, list, tuple)):
        return json.dumps(safe, ensure_ascii=False, sort_keys=True)
    return safe


def build_iqa_report_txt_payload(report: Mapping[str, Any]) -> str:
    return format_iqa_report_text(report)


def build_iqa_history_summary_txt_payload(summary_report: Mapping[str, Any]) -> str:
    head = format_iqa_history_summary_text(summary_report)
    lines = [head, "", "Entries:"]
    for row in list(summary_report.get("entries_summary") or []):
        lines.append(
            f"- {row.get('history_id')} | status={row.get('status')} | ref={row.get('reference_label')} | "
            f"tar={row.get('target_label')} | scope={row.get('scope')} | ssim={row.get('ssim')} | psnr={row.get('psnr')}"
        )
    lines.append("\n진단 정확도 판정이 아닌 영상 품질 비교 지표입니다.")
    return "\n".join(lines)


def build_iqa_report_json_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    return iqa_report_to_jsonable(report)


def build_iqa_history_summary_json_payload(summary_report: Mapping[str, Any]) -> dict[str, Any]:
    return to_jsonable(dict(summary_report))


def build_iqa_report_csv_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    flat = flatten_iqa_report_for_export(report)
    m = report.get("metrics", {}) or {}
    h = report.get("histogram", {}) or {}
    row = {
        "report_type": report.get("report_type"),
        "history_id": report.get("history_id"),
        "created_at": report.get("created_at"),
        "status": report.get("status"),
        "reference_label": report.get("reference_label"),
        "target_label": report.get("target_label"),
        "input_mode": report.get("input_mode"),
        "scope": report.get("scope"),
        "roi_label": report.get("roi_label"),
        "data_range_policy": report.get("data_range_policy"),
        "data_range_used": report.get("data_range_used"),
        "metric_mse": m.get("mse"),
        "metric_rmse": m.get("rmse"),
        "metric_psnr": m.get("psnr"),
        "metric_ssim": m.get("ssim"),
        "metric_hist_corr": m.get("hist_corr"),
        "histogram_corr": h.get("histogram_corr"),
        "histogram_distribution_hint": h.get("histogram_distribution_hint"),
        "warning_count": len(report.get("warnings", []) or []),
        "invalid_reason": report.get("invalid_reason"),
        "interpretation": report.get("interpretation"),
        "warnings": report.get("warnings", []),
        "export_record": report.get("export_record", {}),
    }
    row.update(flat)
    return [{k: _to_csv_safe(v) for k, v in row.items()}]


def build_iqa_history_summary_csv_rows(summary_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    flat = flatten_iqa_history_summary_for_export(summary_report)
    return [{k: _to_csv_safe(v) for k, v in flat.items()}]


def build_iqa_history_entries_csv_rows(entries: list[Mapping[str, Any] | IQAHistoryEntry]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in entries:
        report = build_iqa_report(item.__dict__ if isinstance(item, IQAHistoryEntry) else item)
        rows.extend(build_iqa_report_csv_rows(report))
    return rows


def build_iqa_report_export_bundle(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "txt": build_iqa_report_txt_payload(report),
        "json": build_iqa_report_json_payload(report),
        "csv_rows": build_iqa_report_csv_rows(report),
    }


def build_iqa_history_summary_export_bundle(summary_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "txt": build_iqa_history_summary_txt_payload(summary_report),
        "json": build_iqa_history_summary_json_payload(summary_report),
        "csv_rows": build_iqa_history_summary_csv_rows(summary_report),
    }


def build_iqa_history_export_bundle(entries: list[Mapping[str, Any] | IQAHistoryEntry]) -> dict[str, Any]:
    summary = build_iqa_history_summary_report(entries)
    return {
        "summary": summary,
        "txt": build_iqa_history_summary_txt_payload(summary),
        "json": build_iqa_history_summary_json_payload(summary),
        "csv_rows": build_iqa_history_entries_csv_rows(entries),
    }
