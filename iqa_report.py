from __future__ import annotations

from typing import Any, Mapping

from iqa_history import IQAHistoryEntry, restore_iqa_history_entry
from iqa_result_schema import to_jsonable


def _entry_obj(entry: IQAHistoryEntry | Mapping[str, Any]) -> IQAHistoryEntry:
    return entry if isinstance(entry, IQAHistoryEntry) else restore_iqa_history_entry(entry)


def _interpretation(entry: IQAHistoryEntry) -> str:
    if entry.status != "success":
        return f"IQA 실행 불가: {entry.invalid_reason or 'invalid'}. 진단 정확도 판정이 아닌 영상 품질 비교 지표입니다."
    m = entry.metrics or {}
    parts: list[str] = []
    ssim = m.get("ssim")
    hist_corr = m.get("hist_corr")
    if isinstance(ssim, (int, float)):
        if ssim >= 0.95:
            parts.append("구조 유사도는 매우 높습니다.")
        elif ssim >= 0.85:
            parts.append("구조 유사도는 비교적 높습니다.")
        else:
            parts.append("구조 차이 가능성이 있습니다.")
    if isinstance(hist_corr, (int, float)) and hist_corr < 0.5:
        parts.append("밝기 분포 차이가 있어 window/level 또는 처리 조건 확인이 필요합니다.")
    if entry.scope in {"full_image", "full"}:
        parts.append("Full Image 결과는 배경 포함 가능성이 있습니다.")
    if entry.scope == "roi":
        parts.append("ROI 기준 결과입니다.")
    parts.append("진단 정확도 판정이 아닌 영상 품질 비교 지표입니다.")
    return " ".join(parts)


def build_iqa_report(entry: IQAHistoryEntry | Mapping[str, Any]) -> dict[str, Any]:
    e = _entry_obj(entry)
    report = {
        "report_type": "iqa_single",
        "history_id": e.history_id,
        "created_at": e.created_at,
        "status": e.status,
        "invalid_reason": e.invalid_reason,
        "reference_label": e.reference_label,
        "target_label": e.target_label,
        "input_mode": e.input_mode,
        "scope": e.scope,
        "data_range_policy": e.data_range_policy,
        "data_range_used": e.data_range_used,
        "photometric_invert": e.photometric_invert,
        "roi_id": e.roi_id,
        "roi_label": e.roi_label,
        "roi_bbox": e.roi_bbox,
        "roi_policy": e.roi_policy,
        "metrics": dict(e.metrics or {}),
        "histogram": dict(e.histogram or {}),
        "warnings": list(e.warnings or []),
        "interpretation": _interpretation(e),
        "export_record": dict(e.export_record or {}),
        "source": e.source,
    }
    return report


def format_iqa_report_text(report: Mapping[str, Any]) -> str:
    m = report.get("metrics", {}) or {}
    h = report.get("histogram", {}) or {}
    status = str(report.get("status", "unknown")).capitalize()
    lines = [
        "IQA Report",
        f"Status: {status}",
        f"Reference: {report.get('reference_label')}",
        f"Target: {report.get('target_label')}",
        f"Scope: {report.get('scope')}",
        f"ROI: {report.get('roi_label')} / {report.get('roi_id')}",
        f"Input Mode: {report.get('input_mode')}",
        f"Data Range: {report.get('data_range_policy')} / {report.get('data_range_used')}",
        "",
        "Metrics:",
        f"- MSE: {m.get('mse', '계산 불가')}",
        f"- RMSE: {m.get('rmse', '계산 불가')}",
        f"- PSNR: {m.get('psnr', '계산 불가')}",
        f"- SSIM: {m.get('ssim', '계산 불가')}",
        f"- HIST Corr: {m.get('hist_corr', '계산 불가')}",
        "",
        "Histogram:",
        f"- Range: {h.get('histogram_range')}",
        f"- Bins: {h.get('histogram_bins')}",
        f"- Distribution: {h.get('histogram_distribution_hint')} / {h.get('histogram_summary')}",
        "",
        "Warnings:",
    ]
    warnings = report.get("warnings", []) or []
    if warnings:
        lines.extend([f"- {w}" for w in warnings])
    else:
        lines.append("- None")
    lines += ["", "Interpretation:", f"- {report.get('interpretation', '')}"]
    return "\n".join(lines)


def iqa_report_to_jsonable(report: Mapping[str, Any]) -> dict[str, Any]:
    return to_jsonable(dict(report))


def build_iqa_history_summary_report(entries: list[IQAHistoryEntry | Mapping[str, Any]]) -> dict[str, Any]:
    objs = [_entry_obj(item) for item in entries]
    success = [e for e in objs if e.status == "success" and e.metrics]
    invalid = [e for e in objs if e.status != "success"]
    ssim_values = [float(e.metrics.get("ssim")) for e in success if isinstance(e.metrics.get("ssim"), (int, float))]
    psnr_values = [float(e.metrics.get("psnr")) for e in success if isinstance(e.metrics.get("psnr"), (int, float))]
    low_hist = [e for e in success if isinstance(e.metrics.get("hist_corr"), (int, float)) and float(e.metrics.get("hist_corr")) < 0.5]
    entries_summary = [
        {
            "history_id": e.history_id,
            "status": e.status,
            "reference_label": e.reference_label,
            "target_label": e.target_label,
            "scope": e.scope,
            "roi_label": e.roi_label,
            "psnr": (e.metrics or {}).get("psnr"),
            "ssim": (e.metrics or {}).get("ssim"),
            "hist_corr": (e.metrics or {}).get("hist_corr"),
            "summary": e.display_summary,
        }
        for e in objs
    ]
    return {
        "report_type": "iqa_history_summary",
        "total_count": len(objs),
        "success_count": len(success),
        "invalid_count": len(invalid),
        "latest_history_id": objs[-1].history_id if objs else None,
        "latest_created_at": objs[-1].created_at if objs else None,
        "average_ssim": (sum(ssim_values) / len(ssim_values)) if ssim_values else None,
        "average_psnr": (sum(psnr_values) / len(psnr_values)) if psnr_values else None,
        "low_hist_corr_count": len(low_hist),
        "roi_count": sum(1 for e in objs if e.scope == "roi"),
        "full_image_count": sum(1 for e in objs if e.scope in {"full_image", "full"}),
        "warning_count": sum(len(e.warnings or []) for e in objs),
        "entries_summary": entries_summary,
    }


def format_iqa_history_summary_text(report: Mapping[str, Any]) -> str:
    return (
        f"IQA History Summary | total={report.get('total_count')} success={report.get('success_count')} "
        f"invalid={report.get('invalid_count')} avg_ssim={report.get('average_ssim')} avg_psnr={report.get('average_psnr')}"
    )


def flatten_iqa_report_for_export(report: Mapping[str, Any]) -> dict[str, Any]:
    m = report.get("metrics", {}) or {}
    h = report.get("histogram", {}) or {}
    return {
        "report_type": report.get("report_type"),
        "status": report.get("status"),
        "reference_label": report.get("reference_label"),
        "target_label": report.get("target_label"),
        "scope": report.get("scope"),
        "roi_label": report.get("roi_label"),
        "metric_psnr": m.get("psnr"),
        "metric_ssim": m.get("ssim"),
        "metric_hist_corr": m.get("hist_corr"),
        "histogram_distribution_hint": h.get("histogram_distribution_hint"),
        "warning_count": len(report.get("warnings", []) or []),
        "interpretation": report.get("interpretation"),
    }


def flatten_iqa_history_summary_for_export(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_type": report.get("report_type"),
        "total_count": report.get("total_count"),
        "success_count": report.get("success_count"),
        "invalid_count": report.get("invalid_count"),
        "latest_history_id": report.get("latest_history_id"),
        "average_ssim": report.get("average_ssim"),
        "average_psnr": report.get("average_psnr"),
        "low_hist_corr_count": report.get("low_hist_corr_count"),
        "warning_count": report.get("warning_count"),
    }
