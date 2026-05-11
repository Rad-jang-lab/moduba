from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis_result_model import normalize_analysis_result
from dicom_batch_execution import validate_dicom_batch_execution_result


NORMALIZATION_SCHEMA_VERSION = 1


def normalize_batch_task_execution_result(task_result: dict[str, Any]) -> dict[str, Any]:
    task = dict(task_result)
    analysis_type = str(task.get("analysis_type", "")).strip().lower()
    status = str(task.get("status", "")).strip().lower()
    normalized: dict[str, Any] = {
        "batch_task_normalization_schema_version": 1,
        "analysis_type": analysis_type,
        "source_task_status": status,
        "normalization_status": "skipped",
        "roi_ids": list(task.get("roi_ids") or []),
        "skip_reason": None,
        "error": None,
        "normalized_result": None,
        "blocked_reasons": list(task.get("blocked_reasons") or []),
    }

    if status == "completed":
        payload = task.get("raw_result_payload")
        if payload is None:
            normalized["normalization_status"] = "error"
            normalized["error"] = "raw_result_payload is None"
            return normalized
        try:
            normalized_result = normalize_analysis_result(analysis_type, payload)
        except ValueError as exc:
            normalized["normalization_status"] = "error"
            normalized["error"] = str(exc)
            return normalized
        normalized["normalization_status"] = "normalized"
        normalized["normalized_result"] = normalized_result
        return normalized

    if status == "blocked":
        normalized["normalization_status"] = "skipped"
        normalized["skip_reason"] = "blocked"
        return normalized

    if status == "not_executed":
        normalized["normalization_status"] = "skipped"
        normalized["skip_reason"] = "not_executed"
        return normalized

    if status == "error":
        normalized["normalization_status"] = "error"
        normalized["error"] = str(task.get("error") or "task execution error")
        return normalized

    raise ValueError(f"unsupported task status: {status}")


def build_normalized_dicom_batch_execution_result(
    execution_result: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    generated_at: str | None = None,
    normalization_id: str | None = None,
) -> dict[str, Any]:
    source = validate_dicom_batch_execution_result(execution_result)
    items: list[dict[str, Any]] = []
    normalized_count = skipped_count = error_count = 0
    task_count = 0

    for item in source.get("items", []):
        task_normalizations = []
        for task in item.get("task_results", []):
            norm = normalize_batch_task_execution_result(task)
            task_normalizations.append(norm)
            task_count += 1
            if norm["normalization_status"] == "normalized":
                normalized_count += 1
            elif norm["normalization_status"] == "skipped":
                skipped_count += 1
            else:
                error_count += 1
        items.append(
            {
                "batch_item_normalization_schema_version": 1,
                "item_id": item.get("item_id"),
                "dicom_path": item.get("dicom_path"),
                "task_normalizations": task_normalizations,
            }
        )

    result = {
        "dicom_batch_execution_normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
        "normalization_id": normalization_id or f"norm_{uuid.uuid4().hex}",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "metadata": dict(metadata or {}),
        "source_run_id": source.get("run_id"),
        "item_count": len(items),
        "task_count": task_count,
        "normalized_task_count": normalized_count,
        "skipped_task_count": skipped_count,
        "error_task_count": error_count,
        "items": items,
    }
    return validate_normalized_dicom_batch_execution_result(result)


def validate_normalized_dicom_batch_execution_result(normalized_execution_result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(normalized_execution_result)
    if payload.get("dicom_batch_execution_normalization_schema_version") != NORMALIZATION_SCHEMA_VERSION:
        raise ValueError("unsupported normalization schema")
    if not isinstance(payload.get("items"), list):
        raise ValueError("items must be list")
    for item in payload["items"]:
        if item.get("batch_item_normalization_schema_version") != 1:
            raise ValueError("bad item normalization schema")
        if not isinstance(item.get("task_normalizations"), list):
            raise ValueError("task_normalizations must be list")
        for task in item["task_normalizations"]:
            if task.get("batch_task_normalization_schema_version") != 1:
                raise ValueError("bad task normalization schema")
    return payload


def render_normalized_dicom_batch_execution_result_text(normalized_execution_result: dict[str, Any]) -> str:
    payload = validate_normalized_dicom_batch_execution_result(normalized_execution_result)
    lines = [
        f"Normalization ID: {payload['normalization_id']}",
        f"Source Run ID: {payload['source_run_id']}",
        f"Tasks: {payload['task_count']} (normalized={payload['normalized_task_count']}, skipped={payload['skipped_task_count']}, error={payload['error_task_count']})",
    ]
    for idx, item in enumerate(payload["items"]):
        lines.append(f"- [{idx}] {item['item_id']} {item['dicom_path']}")
        for t_idx, task in enumerate(item["task_normalizations"]):
            lines.append(
                f"  - ({t_idx}) {task['analysis_type']} src={task['source_task_status']} norm={task['normalization_status']}"
            )
    return "\n".join(lines) + "\n"


def export_normalized_dicom_batch_execution_result_to_json(normalized_execution_result: dict[str, Any], path: str | Path | None = None) -> str:
    text = json.dumps(
        validate_normalized_dicom_batch_execution_result(normalized_execution_result),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def export_normalized_dicom_batch_execution_result_to_csv(normalized_execution_result: dict[str, Any], path: str | Path | None = None) -> str:
    payload = validate_normalized_dicom_batch_execution_result(normalized_execution_result)
    fields = [
        "dicom_batch_execution_normalization_schema_version",
        "normalization_id",
        "generated_at",
        "source_run_id",
        "item_index",
        "item_id",
        "dicom_path",
        "task_index",
        "analysis_type",
        "source_task_status",
        "normalization_status",
        "roi_ids_json",
        "skip_reason",
        "error",
        "metric_names_json",
        "curve_names_json",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for i, item in enumerate(payload["items"]):
        for j, task in enumerate(item["task_normalizations"]):
            normalized_result = dict(task.get("normalized_result") or {})
            writer.writerow(
                {
                    "dicom_batch_execution_normalization_schema_version": payload["dicom_batch_execution_normalization_schema_version"],
                    "normalization_id": payload["normalization_id"],
                    "generated_at": payload["generated_at"],
                    "source_run_id": payload["source_run_id"],
                    "item_index": i,
                    "item_id": item.get("item_id"),
                    "dicom_path": item.get("dicom_path"),
                    "task_index": j,
                    "analysis_type": task.get("analysis_type"),
                    "source_task_status": task.get("source_task_status"),
                    "normalization_status": task.get("normalization_status"),
                    "roi_ids_json": json.dumps(task.get("roi_ids") or [], ensure_ascii=False, sort_keys=True),
                    "skip_reason": task.get("skip_reason"),
                    "error": task.get("error"),
                    "metric_names_json": json.dumps(sorted((normalized_result.get("metrics") or {}).keys()), ensure_ascii=False),
                    "curve_names_json": json.dumps(sorted((normalized_result.get("curves") or {}).keys()), ensure_ascii=False),
                }
            )
    text = buf.getvalue()
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def load_normalized_dicom_batch_execution_result(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("failed to load") from exc
    return validate_normalized_dicom_batch_execution_result(payload)
