from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dicom_batch_execution_plan import validate_dicom_batch_execution_plan
from roi_preset import validate_roi_preset


Executor = Callable[[str, str, list[dict[str, Any]], dict[str, Any]], Any]


def build_execution_roi_lookup(roi_preset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    preset = validate_roi_preset(roi_preset)
    lookup: dict[str, dict[str, Any]] = {}
    for roi in preset.get("roi_definitions", []):
        lookup[str(roi["roi_id"])] = json.loads(json.dumps(roi))
    return lookup


def resolve_task_roi_definitions(task: dict[str, Any], roi_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    roi_defs = []
    for roi_id in task.get("roi_ids", []):
        if roi_id not in roi_lookup:
            raise ValueError(f"roi_id not found: {roi_id}")
        roi_defs.append(json.loads(json.dumps(roi_lookup[roi_id])))
    return roi_defs


def execute_dicom_batch_task(dicom_path: str, task: dict[str, Any], roi_lookup: dict[str, dict[str, Any]], analysis_executor: Executor | None = None) -> dict[str, Any]:
    result = {
        "batch_task_execution_result_schema_version": 1,
        "analysis_type": task.get("analysis_type"),
        "status": "not_executed",
        "dicom_path": dicom_path,
        "roi_ids": list(task.get("roi_ids", [])),
        "blocked_reasons": list(task.get("blocked_reasons", [])),
        "raw_result_payload": None,
        "error": None,
    }

    if not task.get("is_executable", False):
        result["status"] = "blocked"
        return result

    try:
        roi_definitions = resolve_task_roi_definitions(task, roi_lookup)
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result

    if analysis_executor is None:
        result["status"] = "not_executed"
        return result

    try:
        payload = analysis_executor(dicom_path, str(task.get("analysis_type", "")), roi_definitions, dict(task))
        result["status"] = "completed"
        result["raw_result_payload"] = payload
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result


def validate_dicom_batch_execution_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(result)
    if payload.get("dicom_batch_execution_result_schema_version") != 1:
        raise ValueError("unsupported schema")
    if not isinstance(payload.get("items"), list):
        raise ValueError("items must be list")
    for item in payload["items"]:
        if item.get("batch_item_execution_result_schema_version") != 1:
            raise ValueError("bad item schema")
        if not isinstance(item.get("task_results"), list):
            raise ValueError("task_results must be list")
        for task_result in item["task_results"]:
            if task_result.get("batch_task_execution_result_schema_version") != 1:
                raise ValueError("bad task result schema")
    return payload


def build_dicom_batch_execution_result(execution_plan: dict[str, Any], roi_preset: dict[str, Any], analysis_executor: Executor | None = None, metadata: dict[str, Any] | None = None, generated_at: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    plan = validate_dicom_batch_execution_plan(execution_plan)
    roi_lookup = build_execution_roi_lookup(roi_preset)

    items = []
    completed = blocked = not_executed = errored = 0
    for item in plan.get("items", []):
        task_results = []
        for task in item.get("tasks", []):
            tr = execute_dicom_batch_task(item.get("dicom_path"), task, roi_lookup, analysis_executor=analysis_executor)
            task_results.append(tr)
            status = tr["status"]
            if status == "completed":
                completed += 1
            elif status == "blocked":
                blocked += 1
            elif status == "error":
                errored += 1
            else:
                not_executed += 1

        items.append({
            "batch_item_execution_result_schema_version": 1,
            "item_id": item.get("item_id"),
            "dicom_path": item.get("dicom_path"),
            "dicom_status": item.get("dicom_status"),
            "bounds_status": item.get("bounds_status"),
            "is_executable_for_any_analysis": item.get("is_executable_for_any_analysis"),
            "task_results": task_results,
        })

    result = {
        "dicom_batch_execution_result_schema_version": 1,
        "run_id": run_id or f"run_{uuid.uuid4().hex}",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "metadata": dict(metadata or {}),
        "execution_plan_id": plan.get("execution_plan_id"),
        "item_count": len(items),
        "task_count": sum(len(i["task_results"]) for i in items),
        "completed_task_count": completed,
        "blocked_task_count": blocked,
        "not_executed_task_count": not_executed,
        "error_task_count": errored,
        "items": items,
    }
    return validate_dicom_batch_execution_result(result)


def render_dicom_batch_execution_result_text(result: dict[str, Any]) -> str:
    payload = validate_dicom_batch_execution_result(result)
    lines = [
        f"Run ID: {payload['run_id']}",
        f"Execution Plan ID: {payload['execution_plan_id']}",
        f"Tasks: {payload['task_count']} (completed={payload['completed_task_count']}, blocked={payload['blocked_task_count']}, not_executed={payload['not_executed_task_count']}, error={payload['error_task_count']})",
    ]
    for idx, item in enumerate(payload["items"]):
        lines.append(f"- [{idx}] {item['item_id']} {item['dicom_status']} {item['bounds_status']}")
        for t_idx, task in enumerate(item["task_results"]):
            lines.append(f"  - ({t_idx}) {task['analysis_type']} status={task['status']}")
    return "\n".join(lines) + "\n"


def export_dicom_batch_execution_result_to_json(result: dict[str, Any], path: str | Path | None = None) -> str:
    text = json.dumps(validate_dicom_batch_execution_result(result), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def export_dicom_batch_execution_result_to_csv(result: dict[str, Any], path: str | Path | None = None) -> str:
    payload = validate_dicom_batch_execution_result(result)
    fields = ["dicom_batch_execution_result_schema_version", "run_id", "generated_at", "item_index", "item_id", "dicom_path", "dicom_status", "bounds_status", "task_index", "analysis_type", "task_status", "roi_ids_json", "blocked_reasons_json", "error", "has_raw_result_payload"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for i, item in enumerate(payload["items"]):
        for j, task in enumerate(item["task_results"]):
            w.writerow({
                "dicom_batch_execution_result_schema_version": 1,
                "run_id": payload["run_id"],
                "generated_at": payload["generated_at"],
                "item_index": i,
                "item_id": item["item_id"],
                "dicom_path": item["dicom_path"],
                "dicom_status": item["dicom_status"],
                "bounds_status": item["bounds_status"],
                "task_index": j,
                "analysis_type": task["analysis_type"],
                "task_status": task["status"],
                "roi_ids_json": json.dumps(task.get("roi_ids", []), ensure_ascii=False, sort_keys=True),
                "blocked_reasons_json": json.dumps(task.get("blocked_reasons", []), ensure_ascii=False, sort_keys=True),
                "error": task.get("error"),
                "has_raw_result_payload": task.get("raw_result_payload") is not None,
            })
    text = buf.getvalue()
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def load_dicom_batch_execution_result(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("failed to load") from exc
    return validate_dicom_batch_execution_result(payload)
