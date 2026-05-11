from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis_history_store import append_analysis_history_record, build_analysis_history_record, load_analysis_history_records
from dicom_batch_execution_normalization import validate_normalized_dicom_batch_execution_result


def build_analysis_history_records_from_normalized_dicom_batch_execution_result(
    normalized_execution_result: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    record_id_prefix: str | None = None,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    payload = validate_normalized_dicom_batch_execution_result(normalized_execution_result)
    prefix = record_id_prefix or "normalized_batch"
    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []

    for item in payload.get("items", []):
        task_normalizations = list(item.get("task_normalizations") or [])
        normalized_results: dict[str, dict[str, Any]] = {}
        roi_ids_by_analysis: dict[str, list[Any]] = {}
        normalization_status_by_analysis: dict[str, str] = {}
        skipped_tasks: list[dict[str, Any]] = []
        error_tasks: list[dict[str, Any]] = []

        for task in task_normalizations:
            analysis_type = str(task.get("analysis_type", "")).strip().lower()
            status = str(task.get("normalization_status", "")).strip().lower()
            roi_ids_by_analysis[analysis_type] = list(task.get("roi_ids") or [])
            normalization_status_by_analysis[analysis_type] = status

            if status == "normalized":
                normalized_result = task.get("normalized_result")
                if not isinstance(normalized_result, dict):
                    raise ValueError("normalized task missing normalized_result")
                normalized_results[analysis_type] = dict(normalized_result)
                continue
            if status == "skipped":
                skipped_tasks.append(
                    {
                        "analysis_type": analysis_type,
                        "skip_reason": task.get("skip_reason"),
                        "roi_ids": list(task.get("roi_ids") or []),
                    }
                )
                continue
            if status == "error":
                error_tasks.append(
                    {
                        "analysis_type": analysis_type,
                        "error": task.get("error"),
                        "roi_ids": list(task.get("roi_ids") or []),
                    }
                )
                continue
            raise ValueError(f"unknown normalization_status: {status}")

        if not normalized_results:
            continue

        item_metadata = {
            "history_source": "normalized_dicom_batch_execution_result",
            "normalization_id": payload.get("normalization_id"),
            "source_run_id": payload.get("source_run_id"),
            "normalized_generated_at": payload.get("generated_at"),
            "item_id": item.get("item_id"),
            "dicom_path": item.get("dicom_path"),
            "task_count": len(task_normalizations),
            "normalized_task_count": len(normalized_results),
            "skipped_task_count": len(skipped_tasks),
            "error_task_count": len(error_tasks),
            "skipped_tasks": skipped_tasks,
            "error_tasks": error_tasks,
            "roi_ids_by_analysis": roi_ids_by_analysis,
            "normalization_status_by_analysis": normalization_status_by_analysis,
        }
        if metadata:
            item_metadata.update(dict(metadata))

        records.append(
            build_analysis_history_record(
                normalized_results,
                metadata=item_metadata,
                generated_at=stamp,
                record_id=f"{prefix}_{payload.get('normalization_id')}_{item.get('item_id')}",
            )
        )
    return records


def validate_normalized_execution_history_adapter_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError("records must be list")
    out = []
    for record in records:
        if not isinstance(record, dict) or record.get("history_schema_version") != 1:
            raise ValueError("invalid history record")
        out.append(dict(record))
    return out


def append_normalized_dicom_batch_execution_history_records(history_path: str | Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if history_path is None or str(history_path).strip() == "":
        raise ValueError("history_path is required")
    validated = validate_normalized_execution_history_adapter_records(records)
    for record in validated:
        append_analysis_history_record(history_path, record)
    return validated


def render_normalized_execution_history_adapter_text(records: list[dict[str, Any]], normalized_execution_result: dict[str, Any] | None = None) -> str:
    validated_records = validate_normalized_execution_history_adapter_records(records)
    lines = [f"History Record Count: {len(validated_records)}"]
    if normalized_execution_result is not None:
        payload = validate_normalized_dicom_batch_execution_result(normalized_execution_result)
        lines.append(f"Normalization ID: {payload.get('normalization_id')}")
        lines.append(f"Source Run ID: {payload.get('source_run_id')}")
        lines.append(
            f"Items: {payload.get('item_count')} Tasks: {payload.get('task_count')} (normalized={payload.get('normalized_task_count')}, skipped={payload.get('skipped_task_count')}, error={payload.get('error_task_count')})"
        )
        lines.append(f"Skipped Items (no normalized tasks): {max(int(payload.get('item_count', 0)) - len(validated_records), 0)}")
    for idx, record in enumerate(validated_records):
        meta = dict(record.get("metadata") or {})
        results = ((record.get("export_snapshot") or {}).get("results") or {})
        lines.append(f"- [{idx}] item_id={meta.get('item_id')} analyses={sorted(results.keys())} skipped={meta.get('skipped_task_count')} error={meta.get('error_task_count')}")
    return "\n".join(lines) + "\n"
