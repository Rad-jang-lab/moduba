from __future__ import annotations

from collections import Counter
from typing import Any

SUPPORTED_ANALYSIS_TYPES_FOR_ROLE_VALIDATION = {"snr", "cnr", "uniformity", "mtf"}
MIN_ROI_COUNT_BY_ANALYSIS_TYPE = {"snr": 2, "cnr": 2, "uniformity": 1, "mtf": 1}


def get_roi_preset_index(roi_preset) -> dict[str, Any]:
    rois = list((roi_preset or {}).get("rois") or [])
    by_id: dict[str, Any] = {}
    duplicate_ids: list[str] = []
    missing_id_count = 0
    for roi in rois:
        rid = str((roi or {}).get("id", "")).strip()
        if not rid:
            missing_id_count += 1
            continue
        if rid in by_id:
            duplicate_ids.append(rid)
            continue
        by_id[rid] = dict(roi or {})
    return {"roi_by_id": by_id, "duplicate_ids": duplicate_ids, "missing_id_count": missing_id_count}


def get_task_analysis_type_for_role_validation(task) -> str:
    return str((task or {}).get("analysis_type", "")).strip().lower()


def get_task_roi_ids_for_role_validation(task) -> list[str]:
    roi_ids = (task or {}).get("roi_ids")
    if roi_ids is None:
        return []
    if not isinstance(roi_ids, list):
        return []
    return [str(x).strip() for x in roi_ids if str(x).strip()]


def validate_task_roi_role_mapping(task, roi_preset, *, bounds_result=None, role_policy=None) -> dict[str, Any]:
    errors = []
    warnings = []
    reason_codes = []
    analysis_type = get_task_analysis_type_for_role_validation(task)
    roi_ids = get_task_roi_ids_for_role_validation(task)
    idx = get_roi_preset_index(roi_preset)
    known = set(idx["roi_by_id"].keys())

    if not analysis_type:
        errors.append("analysis_type is missing"); reason_codes.append("MISSING_ANALYSIS_TYPE")
    elif analysis_type not in SUPPORTED_ANALYSIS_TYPES_FOR_ROLE_VALIDATION:
        errors.append(f"unsupported analysis_type: {analysis_type}"); reason_codes.append("UNSUPPORTED_ANALYSIS_TYPE")

    if (task or {}).get("roi_ids") is not None and not isinstance((task or {}).get("roi_ids"), list):
        errors.append("task roi_ids must be a list"); reason_codes.append("INVALID_ROI_IDS")
    if not roi_ids:
        errors.append("task roi_ids is empty"); reason_codes.append("MISSING_ROI_IDS")

    dup = [k for k, v in Counter(roi_ids).items() if v > 1]
    if dup:
        warnings.append(f"duplicate roi_ids: {dup}"); reason_codes.append("DUPLICATE_ROI_ID")
    unknown = [rid for rid in roi_ids if rid not in known]
    if unknown:
        errors.append(f"unknown roi_ids: {unknown}"); reason_codes.append("UNKNOWN_ROI_ID")

    if analysis_type in MIN_ROI_COUNT_BY_ANALYSIS_TYPE and len(roi_ids) < MIN_ROI_COUNT_BY_ANALYSIS_TYPE[analysis_type]:
        errors.append(f"analysis_type {analysis_type} requires at least {MIN_ROI_COUNT_BY_ANALYSIS_TYPE[analysis_type]} roi_ids")
        reason_codes.append("MISSING_REQUIRED_ROLE")

    if bounds_result is not None:
        bitems = {str(i.get('item_id')): i for i in list((bounds_result or {}).get('items') or [])}
        item = bitems.get(str((task or {}).get('item_id', '')))
        if item and str(item.get('bounds_status', '')) not in ('pass', ''):
            warnings.append(f"bounds_status={item.get('bounds_status')}")
            reason_codes.append("ROI_BOUNDS_WARNING")

    role_status = "invalid" if errors else ("warning" if warnings else "valid")
    return {
        "valid": not errors,
        "analysis_type": analysis_type,
        "task_id": str((task or {}).get("task_id", "")),
        "roi_ids": list(roi_ids),
        "resolved_roi_ids": [rid for rid in roi_ids if rid in known],
        "missing_roi_ids": [rid for rid in roi_ids if rid not in known],
        "duplicate_roi_ids": dup,
        "role_status": role_status,
        "role_bindings": {},
        "warnings": warnings,
        "errors": errors,
        "reason_codes": sorted(set(reason_codes)),
    }


def validate_dicom_batch_roi_roles(execution_plan, roi_preset, *, bounds_result=None, role_policy=None) -> dict[str, Any]:
    items_out = []
    task_count = valid = warn = invalid = unknown = missing_role = 0
    for item in list((execution_plan or {}).get("items") or []):
        tv = []
        for task in list((item or {}).get("tasks") or []):
            merged_task = dict(task); merged_task.setdefault("item_id", item.get("item_id"))
            out = validate_task_roi_role_mapping(merged_task, roi_preset, bounds_result=bounds_result, role_policy=role_policy)
            tv.append(out); task_count += 1
            if out["role_status"] == "valid": valid += 1
            elif out["role_status"] == "warning": warn += 1
            else: invalid += 1
            if "UNKNOWN_ROI_ID" in out["reason_codes"]: unknown += 1
            if "MISSING_REQUIRED_ROLE" in out["reason_codes"]: missing_role += 1
        items_out.append({"item_id": item.get("item_id"), "dicom_path": item.get("dicom_path"), "task_validations": tv})
    report = {"roi_role_validation_schema_version": 1, "valid": invalid == 0, "summary": {"task_count": task_count, "valid_task_count": valid, "warning_task_count": warn, "invalid_task_count": invalid, "unknown_roi_count": unknown, "missing_role_count": missing_role}, "items": items_out, "warnings": [], "errors": [], "metadata": {"execution_plan_id": (execution_plan or {}).get("execution_plan_id", "")}}
    return report


def render_dicom_batch_roi_role_validation_text(validation_report) -> str:
    r = validation_report or {}
    s = r.get("summary") or {}
    lines = ["DICOM Batch ROI Role Validation", f"valid: {bool(r.get('valid'))}", f"tasks: {s.get('task_count', 0)} (valid={s.get('valid_task_count', 0)}, warning={s.get('warning_task_count', 0)}, invalid={s.get('invalid_task_count', 0)})"]
    for item in list(r.get("items") or []):
        lines.append(f"- item {item.get('item_id')} path={item.get('dicom_path')}")
        for t in list(item.get("task_validations") or []):
            lines.append(f"  * {t.get('analysis_type')} roi_ids={t.get('roi_ids')} status={t.get('role_status')} reasons={t.get('reason_codes')}")
    lines.append("next_action: Run Pixel Batch Execution" if r.get("valid") else "next_action: fix ROI preset/task mapping before strict run")
    return "\n".join(lines) + "\n"


def assert_dicom_batch_roi_roles_valid(validation_report):
    if not bool((validation_report or {}).get("valid")):
        raise ValueError("ROI role validation failed")
