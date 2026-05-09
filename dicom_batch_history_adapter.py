from __future__ import annotations

from collections import Counter
from typing import Any

from analysis_batch_qc import build_batch_qc_run
from analysis_history_store import append_analysis_history_record, build_analysis_history_record
from analysis_result_model import normalize_analysis_result
from dicom_batch_execution import validate_dicom_batch_execution_result


_REASON_BY_STATUS = {
    "blocked": "BATCH_TASK_BLOCKED",
    "error": "BATCH_TASK_ERROR",
    "not_executed": "BATCH_TASK_NOT_EXECUTED",
}


def build_invalid_batch_task_normalized_result(
    analysis_type: str,
    status: str,
    *,
    roi_ids: list[Any] | None = None,
    warnings: list[str] | None = None,
    reason_codes: list[str] | None = None,
    source_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload_keys = sorted((source_payload or {}).keys())
    return {
        "analysis_type": str(analysis_type).strip().lower(),
        "status": str(status),
        "validity": "invalid",
        "metrics": {},
        "curves": {},
        "warnings": list(warnings or []),
        "reason_codes": list(reason_codes or []),
        "roi_info": {"roi_ids": list(roi_ids or [])},
        "source_payload_keys": payload_keys,
    }


def normalize_dicom_batch_task_execution_result(task_result: dict[str, Any]) -> dict[str, Any]:
    task = dict(task_result or {})
    analysis_type = str(task.get("analysis_type", ""))
    status = str(task.get("status", "not_executed"))
    roi_ids = list(task.get("roi_ids") or [])
    blocked_reasons = [str(x) for x in (task.get("blocked_reasons") or [])]
    error = task.get("error")
    raw = task.get("raw_result_payload")

    base_warnings = []
    if blocked_reasons:
        base_warnings.extend([f"blocked_reason:{x}" for x in blocked_reasons])
    if error:
        base_warnings.append(f"task_error:{error}")

    if status == "completed":
        if not isinstance(raw, dict):
            return build_invalid_batch_task_normalized_result(
                analysis_type,
                status,
                roi_ids=roi_ids,
                warnings=base_warnings + ["missing_raw_result_payload"],
                reason_codes=["BATCH_TASK_MISSING_RAW_RESULT_PAYLOAD"],
                source_payload=task,
            )
        try:
            normalized = normalize_analysis_result(analysis_type, raw)
        except ValueError as exc:
            reason = "BATCH_TASK_UNSUPPORTED_ANALYSIS_TYPE" if "unsupported analysis_type" in str(exc) else "BATCH_TASK_NORMALIZATION_ERROR"
            return build_invalid_batch_task_normalized_result(
                analysis_type,
                "normalization_error",
                roi_ids=roi_ids,
                warnings=base_warnings + [f"normalization_error:{exc}"],
                reason_codes=[reason],
                source_payload=task,
            )
        except Exception as exc:
            return build_invalid_batch_task_normalized_result(
                analysis_type,
                "normalization_error",
                roi_ids=roi_ids,
                warnings=base_warnings + [f"normalization_error:{exc}"],
                reason_codes=["BATCH_TASK_NORMALIZATION_ERROR"],
                source_payload=task,
            )
        out = dict(normalized)
        out["roi_info"] = dict(out.get("roi_info") or {})
        out["roi_info"].setdefault("roi_ids", roi_ids)
        if base_warnings:
            out["warnings"] = list(out.get("warnings") or []) + base_warnings
        return out

    reason = _REASON_BY_STATUS.get(status, "BATCH_TASK_NOT_EXECUTED")
    return build_invalid_batch_task_normalized_result(
        analysis_type,
        status,
        roi_ids=roi_ids,
        warnings=base_warnings,
        reason_codes=[reason],
        source_payload=task,
    )


def build_analysis_history_records_from_dicom_batch_execution_result(result: dict[str, Any], metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]]:
    payload = validate_dicom_batch_execution_result(result)
    records: list[dict[str, Any]] = []
    prefix = record_id_prefix or "batch"
    run_id = str(payload.get("run_id", ""))
    for item in payload.get("items", []):
        task_results = list(item.get("task_results") or [])
        if not task_results:
            continue
        normalized_results: dict[str, dict[str, Any]] = {}
        roi_ids_by_analysis: dict[str, list[Any]] = {}
        status_counts = Counter()
        for tr in task_results:
            at = str(tr.get("analysis_type", "")).strip().lower()
            status_counts[str(tr.get("status", "not_executed"))] += 1
            normalized_results[at] = normalize_dicom_batch_task_execution_result(tr)
            roi_ids_by_analysis[at] = list(tr.get("roi_ids") or [])

        base_metadata = {
            "history_source": "dicom_batch_execution_result",
            "batch_run_id": payload.get("run_id"),
            "execution_plan_id": payload.get("execution_plan_id"),
            "batch_generated_at": payload.get("generated_at"),
            "item_id": item.get("item_id"),
            "dicom_path": item.get("dicom_path"),
            "dicom_status": item.get("dicom_status"),
            "bounds_status": item.get("bounds_status"),
            "task_status_counts": dict(status_counts),
            "roi_ids_by_analysis": roi_ids_by_analysis,
        }
        if metadata:
            base_metadata.update(dict(metadata))
        records.append(
            build_analysis_history_record(
                normalized_results,
                metadata=base_metadata,
                record_id=f"{prefix}_{run_id}_{item.get('item_id')}",
            )
        )
    return records


def append_dicom_batch_execution_history_records(history_path: str, records: list[dict[str, Any]]) -> None:
    for record in records:
        append_analysis_history_record(history_path, record)


def build_batch_qc_run_from_dicom_batch_execution_result(result: dict[str, Any], threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None) -> dict[str, Any]:
    records = build_analysis_history_records_from_dicom_batch_execution_result(result)
    return build_batch_qc_run(records, threshold_config=threshold_config, metadata=metadata, batch_id=batch_id)


def render_dicom_batch_history_bridge_summary_text(records: list[dict[str, Any]], batch_qc_run: dict[str, Any] | None = None) -> str:
    lines = [f"History Record Count: {len(records)}"]
    if records:
        m = records[0].get("metadata") or {}
        lines.extend([
            f"Batch Run ID: {m.get('batch_run_id')}",
            f"Execution Plan ID: {m.get('execution_plan_id')}",
            f"Generated At: {m.get('batch_generated_at')}",
            f"Item Count: {len(records)}",
        ])
    for idx, r in enumerate(records):
        results = ((r.get("export_snapshot") or {}).get("results") or {})
        valid = sum(1 for v in results.values() if isinstance(v, dict) and v.get("validity") == "valid")
        invalid = sum(1 for v in results.values() if isinstance(v, dict) and v.get("validity") == "invalid")
        warn_count = sum(len((v.get("warnings") or [])) for v in results.values() if isinstance(v, dict))
        md = r.get("metadata") or {}
        lines.append(f"- [{idx}] item_id={md.get('item_id')} path={md.get('dicom_path')} analyses={sorted(results.keys())} valid={valid} invalid={invalid} warnings={warn_count}")
    if batch_qc_run is not None:
        lines.append(f"Batch QC: item_count={batch_qc_run.get('item_count')} summary={batch_qc_run.get('summary')}")
    return "\n".join(lines) + "\n"
