from __future__ import annotations

from typing import Any, Callable

from dicom_batch_execution import build_dicom_batch_execution_result, validate_dicom_batch_execution_result
from dicom_batch_execution_plan import validate_dicom_batch_execution_plan


ViewerExecutor = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]


def run_dicom_batch_execution_plan_with_executor(execution_plan: dict[str, Any], roi_preset: dict[str, Any], analysis_executor: ViewerExecutor | None = None, metadata: dict[str, Any] | None = None, generated_at: str | None = None) -> dict[str, Any]:
    plan = validate_dicom_batch_execution_plan(execution_plan)

    def _adapter(dicom_path: str, analysis_type: str, roi_definitions: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
        if analysis_executor is None:
            raise RuntimeError("analysis_executor is None")
        item = {"dicom_path": dicom_path}
        context = {"analysis_type": analysis_type, "roi_definitions": list(roi_definitions)}
        out = analysis_executor(dict(task), item, context)
        if not isinstance(out, dict):
            raise ValueError("analysis_executor must return dict payload")
        return out

    exec_fn = None if analysis_executor is None else _adapter
    return validate_dicom_batch_execution_result(
        build_dicom_batch_execution_result(plan, roi_preset, analysis_executor=exec_fn, metadata=metadata, generated_at=generated_at)
    )


def build_dicom_batch_run_orchestration_summary(execution_plan: dict[str, Any] | None = None, execution_result: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = validate_dicom_batch_execution_plan(execution_plan) if execution_plan else None
    result = validate_dicom_batch_execution_result(execution_result) if execution_result else None
    return {
        "has_execution_plan": plan is not None,
        "has_execution_result": result is not None,
        "plan_id": str((plan or {}).get("execution_plan_id", "")),
        "run_id": str((result or {}).get("run_id", "")),
        "item_count": int((result or {}).get("item_count", (plan or {}).get("item_count", 0))),
        "task_count": int((result or {}).get("task_count", (plan or {}).get("task_count", 0))),
        "completed_task_count": int((result or {}).get("completed_task_count", 0)),
        "blocked_task_count": int((result or {}).get("blocked_task_count", (plan or {}).get("blocked_task_count", 0))),
        "not_executed_task_count": int((result or {}).get("not_executed_task_count", 0)),
        "error_task_count": int((result or {}).get("error_task_count", 0)),
    }


def render_dicom_batch_run_orchestration_summary_text(summary_or_plan: dict[str, Any] | None = None, execution_result: dict[str, Any] | None = None) -> str:
    summary = summary_or_plan if summary_or_plan and "has_execution_plan" in summary_or_plan else build_dicom_batch_run_orchestration_summary(summary_or_plan, execution_result)
    lines = [
        "DICOM Batch Run Orchestration Summary",
        f"Has Execution Plan: {summary.get('has_execution_plan')}",
        f"Has Execution Result: {summary.get('has_execution_result')}",
        f"Plan ID: {summary.get('plan_id')}",
        f"Run ID: {summary.get('run_id')}",
        f"Items: {summary.get('item_count')} Tasks: {summary.get('task_count')}",
        f"Status Counts: completed={summary.get('completed_task_count')} blocked={summary.get('blocked_task_count')} not_executed={summary.get('not_executed_task_count')} error={summary.get('error_task_count')}",
        "Next Action: Run Batch Execution -> Bridge -> History -> Batch QC -> Report/Export",
    ]
    return "\n".join(lines) + "\n"
