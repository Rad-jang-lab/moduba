from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dicom_batch_plan import validate_dicom_batch_analysis_plan
from roi_bounds_validation import validate_roi_bounds_validation_result

DEFAULT_ANALYSES = ["snr", "cnr", "uniformity", "mtf"]
ROLE_MAP = {
    "snr": ["signal", "noise"],
    "cnr": ["region_a", "region_b", "noise", "background"],
    "uniformity": ["uniformity"],
    "mtf": ["mtf_edge"],
}


def validate_dicom_batch_execution_plan(execution_plan: dict[str, Any]) -> dict[str, Any]:
    plan = dict(execution_plan)
    if plan.get("dicom_batch_execution_plan_schema_version") != 1:
        raise ValueError("unsupported schema")
    if not isinstance(plan.get("items"), list):
        raise ValueError("items must be list")

    for item in plan["items"]:
        if item.get("execution_item_schema_version") != 1:
            raise ValueError("bad item schema")
        if not isinstance(item.get("tasks"), list):
            raise ValueError("tasks must be list")
        for task in item["tasks"]:
            if task.get("execution_task_schema_version") != 1:
                raise ValueError("bad task schema")
    return plan


def _roi_ids_for_analysis(roi_results: list[dict[str, Any]], analysis_type: str) -> list[str]:
    expected_roles = ROLE_MAP.get(analysis_type, [])
    roi_ids = []
    for roi_result in roi_results:
        roles = roi_result.get("analysis_roles", [])
        if any(role in expected_roles for role in roles):
            roi_ids.append(roi_result.get("roi_id"))
    return sorted(roi_id for roi_id in roi_ids if roi_id)


def build_dicom_batch_execution_plan(
    batch_plan: dict[str, Any],
    bounds_validation: dict[str, Any],
    analyses: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    generated_at: str | None = None,
    execution_plan_id: str | None = None,
) -> dict[str, Any]:
    validated_batch_plan = validate_dicom_batch_analysis_plan(batch_plan)
    validated_bounds = validate_roi_bounds_validation_result(bounds_validation)

    if validated_batch_plan.get("item_count") != validated_bounds.get("item_count"):
        raise ValueError("item_count mismatch")

    if (
        validated_batch_plan.get("manifest_id")
        and validated_bounds.get("manifest_id")
        and validated_batch_plan.get("manifest_id") != validated_bounds.get("manifest_id")
    ):
        raise ValueError("manifest_id mismatch")

    selected_analyses = list(analyses or validated_batch_plan.get("analyses") or DEFAULT_ANALYSES)
    batch_items = {item.get("item_id"): item for item in validated_batch_plan.get("items") or []}
    bound_items = {item.get("item_id"): item for item in validated_bounds.get("items") or []}

    if set(batch_items.keys()) != set(bound_items.keys()):
        raise ValueError("item_id mismatch")

    items: list[dict[str, Any]] = []
    executable_item_count = 0
    blocked_item_count = 0
    task_count = 0
    executable_task_count = 0
    blocked_task_count = 0

    for item_id in sorted(batch_items.keys()):
        plan_item = batch_items[item_id]
        bounds_item = bound_items[item_id]

        tasks = []
        item_blocked_reasons = []

        for analysis in selected_analyses:
            task_count += 1
            blocked_reasons = []

            if plan_item.get("dicom_status") != "valid":
                blocked_reasons.append("dicom_invalid")
            if bounds_item.get("bounds_status") == "not_evaluated":
                blocked_reasons.append("bounds_not_evaluated")
            if bounds_item.get("bounds_status") == "fail":
                blocked_reasons.append("roi_out_of_bounds")

            batch_readiness = (plan_item.get("analysis_readiness") or {}).get(analysis) or {}
            bounds_readiness = (bounds_item.get("analysis_readiness") or {}).get(analysis) or {}

            if not batch_readiness.get("is_ready", False) or not bounds_readiness.get("is_ready", False):
                blocked_reasons.append("readiness_mismatch")
            if bounds_readiness.get("missing_roles"):
                blocked_reasons.append("missing_required_roles")

            is_executable = len(blocked_reasons) == 0
            if is_executable:
                executable_task_count += 1
            else:
                blocked_task_count += 1

            tasks.append(
                {
                    "execution_task_schema_version": 1,
                    "analysis_type": analysis,
                    "is_executable": is_executable,
                    "required_roles": batch_readiness.get("required_roles")
                    or bounds_readiness.get("required_roles")
                    or [],
                    "roi_ids": _roi_ids_for_analysis(bounds_item.get("roi_results") or [], analysis),
                    "blocked_reasons": sorted(set(blocked_reasons)),
                }
            )
            item_blocked_reasons.extend(blocked_reasons)

        is_executable_for_any_analysis = any(task["is_executable"] for task in tasks)
        if is_executable_for_any_analysis:
            executable_item_count += 1
        else:
            blocked_item_count += 1

        items.append(
            {
                "execution_item_schema_version": 1,
                "item_id": item_id,
                "dicom_path": plan_item.get("dicom_path"),
                "dicom_status": plan_item.get("dicom_status"),
                "bounds_status": bounds_item.get("bounds_status"),
                "is_executable_for_any_analysis": is_executable_for_any_analysis,
                "tasks": tasks,
                "blocked_reasons": sorted(set(item_blocked_reasons)),
            }
        )

    execution_plan = {
        "dicom_batch_execution_plan_schema_version": 1,
        "execution_plan_id": execution_plan_id or f"exec_{uuid.uuid4().hex}",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "metadata": dict(metadata or {}),
        "batch_plan_id": validated_batch_plan.get("plan_id"),
        "bounds_validation_id": validated_bounds.get("validation_id"),
        "analyses": selected_analyses,
        "item_count": len(items),
        "executable_item_count": executable_item_count,
        "blocked_item_count": blocked_item_count,
        "task_count": task_count,
        "executable_task_count": executable_task_count,
        "blocked_task_count": blocked_task_count,
        "items": items,
    }
    return validate_dicom_batch_execution_plan(execution_plan)


def render_dicom_batch_execution_plan_text(execution_plan: dict[str, Any]) -> str:
    plan = validate_dicom_batch_execution_plan(execution_plan)
    lines = [
        f"Execution Plan ID: {plan['execution_plan_id']}",
        f"Items: {plan['item_count']} (executable={plan['executable_item_count']}, blocked={plan['blocked_item_count']})",
        f"Tasks: {plan['task_count']} (executable={plan['executable_task_count']}, blocked={plan['blocked_task_count']})",
    ]
    for index, item in enumerate(plan["items"]):
        lines.append(
            f"- [{index}] {item['item_id']} {item['dicom_status']} {item['bounds_status']} any={item['is_executable_for_any_analysis']}"
        )
    return "\n".join(lines) + "\n"


def export_dicom_batch_execution_plan_to_json(execution_plan: dict[str, Any], path: str | Path | None = None) -> str:
    text = json.dumps(
        validate_dicom_batch_execution_plan(execution_plan),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def export_dicom_batch_execution_plan_to_csv(execution_plan: dict[str, Any], path: str | Path | None = None) -> str:
    plan = validate_dicom_batch_execution_plan(execution_plan)
    fields = [
        "dicom_batch_execution_plan_schema_version",
        "execution_plan_id",
        "generated_at",
        "item_index",
        "item_id",
        "dicom_path",
        "dicom_status",
        "bounds_status",
        "is_executable_for_any_analysis",
        "task_index",
        "analysis_type",
        "is_executable",
        "required_roles_json",
        "roi_ids_json",
        "task_blocked_reasons_json",
        "item_blocked_reasons_json",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()

    for item_index, item in enumerate(plan["items"]):
        for task_index, task in enumerate(item["tasks"]):
            writer.writerow(
                {
                    "dicom_batch_execution_plan_schema_version": 1,
                    "execution_plan_id": plan["execution_plan_id"],
                    "generated_at": plan["generated_at"],
                    "item_index": item_index,
                    "item_id": item["item_id"],
                    "dicom_path": item["dicom_path"],
                    "dicom_status": item["dicom_status"],
                    "bounds_status": item["bounds_status"],
                    "is_executable_for_any_analysis": item["is_executable_for_any_analysis"],
                    "task_index": task_index,
                    "analysis_type": task["analysis_type"],
                    "is_executable": task["is_executable"],
                    "required_roles_json": json.dumps(task["required_roles"], ensure_ascii=False, sort_keys=True),
                    "roi_ids_json": json.dumps(task["roi_ids"], ensure_ascii=False, sort_keys=True),
                    "task_blocked_reasons_json": json.dumps(task["blocked_reasons"], ensure_ascii=False, sort_keys=True),
                    "item_blocked_reasons_json": json.dumps(item["blocked_reasons"], ensure_ascii=False, sort_keys=True),
                }
            )

    text = buffer.getvalue()
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def load_dicom_batch_execution_plan(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("failed to load") from exc
    return validate_dicom_batch_execution_plan(payload)
