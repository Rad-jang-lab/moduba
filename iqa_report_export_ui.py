from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from iqa_history import get_latest_iqa_history
from iqa_report import build_iqa_report
from iqa_report_export import build_iqa_report_export_bundle
from iqa_report_file_export import (
    sanitize_export_base_name,
    write_iqa_report_csv,
    write_iqa_report_export_bundle,
    write_iqa_report_json,
    write_iqa_report_txt,
)

FORMAT_LABELS = {"txt": "TXT", "json": "JSON", "csv": "CSV", "all": "All"}


def normalize_iqa_report_export_format(value: str | None) -> str:
    fmt = str(value or "txt").lower().strip()
    return fmt if fmt in FORMAT_LABELS else "txt"


def get_iqa_report_export_format_options() -> list[tuple[str, str]]:
    return [(k, v) for k, v in FORMAT_LABELS.items()]


def get_iqa_report_export_format_label(value: str | None) -> str:
    return FORMAT_LABELS[normalize_iqa_report_export_format(value)]


def resolve_latest_iqa_report_for_export(analysis_last_run: Mapping[str, Any] | None, iqa_history: list[Any] | None) -> dict[str, Any] | None:
    last = (analysis_last_run or {}).get("iqa_report")
    if isinstance(last, dict) and last:
        return dict(last)
    latest = get_latest_iqa_history(iqa_history or [])
    if latest:
        return build_iqa_report(latest)
    return None


def build_iqa_report_default_base_name(report: Mapping[str, Any]) -> str:
    history_id = str(report.get("history_id") or "latest")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return sanitize_export_base_name(f"iqa_report_{history_id}_{stamp}")


def get_iqa_report_save_suffix(fmt: str | None) -> str:
    f = normalize_iqa_report_export_format(fmt)
    return "" if f == "all" else f".{f}"


def requires_directory_for_format(fmt: str | None) -> bool:
    return normalize_iqa_report_export_format(fmt) == "all"


def build_iqa_report_export_no_report_status() -> str:
    return "IQA report 저장 불가: 저장할 IQA report가 없습니다."


def build_iqa_report_export_cancel_status() -> str:
    return "IQA report 저장 취소"


def format_iqa_report_export_status(result: Mapping[str, Any]) -> str:
    status = str(result.get("status", "")).lower()
    if status == "success":
        if result.get("files"):
            return f"IQA report 저장 완료: {len(result.get('files', []))} files"
        return f"IQA report 저장 완료: {result.get('path')}"
    if status == "cancel":
        return build_iqa_report_export_cancel_status()
    if status == "no_report":
        return build_iqa_report_export_no_report_status()
    return f"IQA report 저장 실패: {result.get('error') or 'unknown'}"


def save_iqa_report_bundle(bundle: Mapping[str, Any], fmt: str, path_or_dir: str, base_name: str | None = None) -> dict[str, Any]:
    fmt = normalize_iqa_report_export_format(fmt)
    if not path_or_dir:
        return {"status": "cancel", "format": fmt}
    if fmt == "all":
        result = write_iqa_report_export_bundle(bundle, output_dir=path_or_dir, base_name=base_name or "iqa_report", formats=("txt", "json", "csv"))
        return {"status": "success", "format": fmt, "files": result.get("files", [])}
    if fmt == "txt":
        res = write_iqa_report_txt(path_or_dir, str(bundle.get("txt", "")))
    elif fmt == "json":
        res = write_iqa_report_json(path_or_dir, bundle.get("json", {}))
    else:
        res = write_iqa_report_csv(path_or_dir, bundle.get("csv_rows", []))
    return {"status": "success", "format": fmt, "path": res.get("path")}


def save_iqa_report_by_format(
    report: Mapping[str, Any] | None,
    fmt: str,
    ask_save_path: Callable[[str, str], str],
    ask_save_dir: Callable[[str], str],
) -> tuple[str, dict[str, Any] | None]:
    if not report:
        return build_iqa_report_export_no_report_status(), None
    bundle = build_iqa_report_export_bundle(report)
    base_name = build_iqa_report_default_base_name(report)
    fmt = normalize_iqa_report_export_format(fmt)
    try:
        target = ask_save_dir(base_name) if requires_directory_for_format(fmt) else ask_save_path(fmt, base_name)
        result = save_iqa_report_bundle(bundle, fmt=fmt, path_or_dir=str(target or ""), base_name=base_name)
        return format_iqa_report_export_status(result), bundle
    except Exception as exc:
        return format_iqa_report_export_status({"status": "error", "format": fmt, "error": str(exc)}), bundle
