from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from analysis_batch_qc import build_batch_qc_run
from dicom_batch_execution_normalization import validate_normalized_dicom_batch_execution_result
from dicom_batch_normalized_history_adapter import build_analysis_history_records_from_normalized_dicom_batch_execution_result


def build_batch_qc_run_from_normalized_execution_history_records(
    records: list[dict[str, Any]],
    threshold_config: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    batch_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    record_list = [dict(r) for r in (records or [])]
    if not record_list:
        raise ValueError("history records are empty")
    merged_metadata = {"batch_qc_source": "normalized_execution_history_records", "history_record_count": len(record_list)}
    if metadata:
        merged_metadata.update(dict(metadata))
    run = build_batch_qc_run(
        record_list,
        threshold_config=None if threshold_config is None else dict(threshold_config),
        metadata=merged_metadata,
        batch_id=batch_id,
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
    )
    return validate_normalized_batch_qc_adapter_run(run)


def build_batch_qc_run_from_normalized_dicom_batch_execution_result(
    normalized_execution_result: dict[str, Any],
    threshold_config: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    batch_id: str | None = None,
    record_id_prefix: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = validate_normalized_dicom_batch_execution_result(normalized_execution_result)
    records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(
        payload,
        metadata=None,
        record_id_prefix=record_id_prefix,
        generated_at=generated_at,
    )
    if not records:
        raise ValueError("history records are empty")
    merged_metadata = {
        "normalization_id": payload.get("normalization_id"),
        "source_run_id": payload.get("source_run_id"),
    }
    if metadata:
        merged_metadata.update(dict(metadata))
    return build_batch_qc_run_from_normalized_execution_history_records(
        records,
        threshold_config=threshold_config,
        metadata=merged_metadata,
        batch_id=batch_id,
        generated_at=generated_at,
    )


def validate_normalized_batch_qc_adapter_run(batch_qc_run: dict[str, Any]) -> dict[str, Any]:
    payload = dict(batch_qc_run)
    if payload.get("batch_qc_schema_version") != 1:
        raise ValueError("invalid batch_qc schema")
    if not isinstance(payload.get("items"), list):
        raise ValueError("batch_qc items must be list")
    return payload


def render_normalized_batch_qc_adapter_text(batch_qc_run: dict[str, Any], records: list[dict[str, Any]] | None = None, normalized_execution_result: dict[str, Any] | None = None) -> str:
    run = validate_normalized_batch_qc_adapter_run(batch_qc_run)
    lines = [
        "Normalized Execution Batch QC Adapter",
        f"batch_id: {run.get('batch_id')}",
        f"item_count: {run.get('item_count')}",
        f"history_record_count: {len(records) if records is not None else 'N/A'}",
    ]
    has_threshold = any(isinstance(item.get("threshold_evaluation"), dict) for item in (run.get("items") or []))
    lines.append(f"threshold_config_applied: {has_threshold}")
    lines.append(f"threshold_evaluation_present: {has_threshold}")
    if normalized_execution_result is not None:
        payload = validate_normalized_dicom_batch_execution_result(normalized_execution_result)
        lines.append(f"normalization_id: {payload.get('normalization_id')}")
        lines.append(f"source_run_id: {payload.get('source_run_id')}")
    for idx, item in enumerate(run.get("items") or []):
        te = item.get("threshold_evaluation") or {}
        lines.append(f"- [{idx}] record_id={item.get('record_id')} analysis_types={item.get('analysis_types')} threshold={te.get('overall_status','missing') if te else 'missing'}")
    lines.append("Next Action: Batch QC report/export는 별도 helper 또는 다음 회차에서 수행")
    return "\n".join(lines) + "\n"
