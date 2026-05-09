from __future__ import annotations

from typing import Any


def _status_rank(s: str) -> int:
    return {"ready": 0, "warning": 1, "blocked": 2}.get(s, 1)


def build_dicom_batch_workflow_readiness_report(*, execution_plan=None, roi_role_validation_report=None, pixel_capability_text=None, execution_result=None, history_records=None, batch_qc_run=None, batch_qc_report_model=None, strict_roi_role_validation=False, metadata=None) -> dict[str, Any]:
    checks = []
    actions = []
    has_plan = execution_plan is not None
    if has_plan:
        checks.append({"name": "execution_plan", "status": "ready", "message": "execution plan loaded", "reason_codes": []})
    else:
        checks.append({"name": "execution_plan", "status": "blocked", "message": "execution plan is missing", "reason_codes": ["MISSING_EXECUTION_PLAN"]})
        actions.append("Build Execution Plan")

    has_roi = roi_role_validation_report is not None
    roi_valid = None if not has_roi else bool((roi_role_validation_report or {}).get("valid"))
    if not has_roi:
        checks.append({"name": "roi_role_validation", "status": "warning", "message": "ROI role validation report is missing", "reason_codes": ["MISSING_ROI_ROLE_VALIDATION"]})
        actions.append("Validate ROI Roles")
    elif roi_valid:
        checks.append({"name": "roi_role_validation", "status": "ready", "message": "ROI role validation passed", "reason_codes": []})
    else:
        status = "blocked" if strict_roi_role_validation else "warning"
        reasons = ["ROI_ROLE_VALIDATION_INVALID"] + (["STRICT_ROI_VALIDATION_BLOCK"] if strict_roi_role_validation else [])
        checks.append({"name": "roi_role_validation", "status": status, "message": "ROI role validation is invalid", "reason_codes": reasons})
        actions.append("Fix ROI preset/task mapping")

    px = str(pixel_capability_text or "")
    if not px:
        checks.append({"name": "pixel_executor", "status": "warning", "message": "pixel executor capability not checked", "reason_codes": ["PIXEL_EXECUTOR_NOT_CHECKED"]})
        actions.append("Check Pixel Executor")
    elif "missing_analyzer_types: []" in px:
        checks.append({"name": "pixel_executor", "status": "ready", "message": "pixel executor/dispatcher capability looks ready", "reason_codes": []})
    else:
        checks.append({"name": "pixel_executor", "status": "warning", "message": "pixel executor/dispatcher may be incomplete", "reason_codes": ["DISPATCHER_NOT_READY"]})

    has_result = execution_result is not None
    has_hist = bool(history_records)
    has_qc = batch_qc_run is not None
    has_report = batch_qc_report_model is not None
    reasons=[]
    if not has_result: reasons.append("EXECUTION_RESULT_EMPTY")
    if not has_hist: reasons.append("HISTORY_RECORDS_EMPTY")
    if not has_qc: reasons.append("BATCH_QC_RUN_EMPTY")
    if not has_report: reasons.append("REPORT_NOT_BUILT")
    checks.append({"name": "downstream", "status": "ready" if not reasons else "warning", "message": "downstream artifacts ready" if not reasons else "downstream artifacts are partial", "reason_codes": reasons})

    overall = "ready"
    for c in checks:
        if _status_rank(c["status"]) > _status_rank(overall): overall = c["status"]
    return {"batch_workflow_readiness_schema_version": 1, "overall_status": overall, "summary": {"has_execution_plan": has_plan, "has_roi_role_validation": has_roi, "roi_role_validation_valid": roi_valid, "has_execution_result": has_result, "has_history_records": has_hist, "has_batch_qc_run": has_qc, "strict_roi_role_validation": bool(strict_roi_role_validation)}, "checks": checks, "next_actions": actions, "metadata": dict(metadata or {})}


def render_dicom_batch_workflow_readiness_text(report) -> str:
    r=report or {}
    s=r.get('summary') or {}
    lines=["DICOM Batch Workflow Readiness",f"overall_status: {r.get('overall_status','warning')}",f"strict_roi_role_validation: {bool(s.get('strict_roi_role_validation'))}"]
    for c in list(r.get('checks') or []):
        lines.append(f"- {c.get('name')}: {c.get('status')} | {c.get('message')} | reasons={c.get('reason_codes')}")
    lines.append("next_actions:")
    for a in list(r.get('next_actions') or []): lines.append(f"- {a}")
    return "\n".join(lines)+"\n"


def assert_dicom_batch_workflow_ready_for_pixel_run(report):
    if str((report or {}).get("overall_status")) == "blocked":
        raise ValueError("Batch workflow readiness is blocked")
