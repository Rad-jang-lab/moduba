from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any, Mapping

from iqa_result_schema import IQAResult, to_jsonable


@dataclass
class IQAHistoryEntry:
    history_id: str
    created_at: str
    analysis_type: str = "iqa"
    reference_id: str | None = None
    reference_label: str | None = None
    target_id: str | None = None
    target_label: str | None = None
    input_mode: str | None = None
    scope: str | None = None
    data_range_mode: str | None = None
    data_range_policy: str | None = None
    data_range_used: float | None = None
    photometric_invert: bool | None = None
    roi_id: str | None = None
    roi_label: str | None = None
    roi_bbox: Any = None
    roi_policy: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    histogram: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    display_summary: str = ""
    export_record: dict[str, Any] = field(default_factory=dict)
    status: str = "success"
    invalid_reason: str | None = None
    source: str | None = None


def make_iqa_history_id(reference_id: str | None, target_id: str | None, created_at: str) -> str:
    seed = f"{reference_id or ''}|{target_id or ''}|{created_at}"
    return f"iqa_{sha1(seed.encode('utf-8')).hexdigest()[:12]}"


def build_iqa_history_entry(
    result: IQAResult | None,
    selection_state: Any | None = None,
    export_record: Mapping[str, Any] | None = None,
    display_model: Mapping[str, Any] | None = None,
    status: str = "success",
    invalid_reason: str | None = None,
    source: str | None = None,
) -> IQAHistoryEntry:
    created_at = datetime.now(timezone.utc).isoformat()
    ref_id = getattr(selection_state, "reference_id", None) if selection_state is not None else None
    tar_id = getattr(selection_state, "target_id", None) if selection_state is not None else None
    ref_label = getattr(selection_state, "reference_label", None) if selection_state is not None else None
    tar_label = getattr(selection_state, "target_label", None) if selection_state is not None else None
    input_mode = getattr(selection_state, "input_mode", None) if selection_state is not None else None
    scope = getattr(selection_state, "scope", None) if selection_state is not None else None
    data_range_mode = getattr(selection_state, "data_range_mode", None) if selection_state is not None else None
    photometric_invert = getattr(selection_state, "photometric_invert", None) if selection_state is not None else None
    context = result.to_dict().get("context", {}) if result is not None else {}
    metrics = result.to_dict().get("metrics", {}) if result is not None else {}
    histogram = dict(context.get("histogram") or {})
    ssim_params = context.get("ssim_params", {}) if isinstance(context, dict) else {}
    return IQAHistoryEntry(
        history_id=make_iqa_history_id(ref_id, tar_id, created_at),
        created_at=created_at,
        reference_id=ref_id,
        reference_label=ref_label,
        target_id=tar_id,
        target_label=tar_label,
        input_mode=input_mode or context.get("input_mode"),
        scope=scope or context.get("scope"),
        data_range_mode=data_range_mode,
        data_range_policy=context.get("data_range_policy"),
        data_range_used=context.get("data_range_used"),
        photometric_invert=photometric_invert,
        roi_id=(ssim_params.get("roi_id") if isinstance(ssim_params, dict) else None),
        roi_label=(ssim_params.get("roi_label") if isinstance(ssim_params, dict) else None),
        roi_bbox=(ssim_params.get("roi_bbox") if isinstance(ssim_params, dict) else None),
        roi_policy=(ssim_params.get("roi_policy") if isinstance(ssim_params, dict) else None),
        metrics=metrics if status == "success" else {},
        context=context,
        histogram=histogram,
        warnings=list(result.warnings) if result is not None else ([] if invalid_reason is None else [invalid_reason]),
        display_summary=str((display_model or {}).get("summary", "")),
        export_record=dict(export_record or {}),
        status=status,
        invalid_reason=invalid_reason,
        source=source,
    )


def iqa_history_entry_to_jsonable(entry: IQAHistoryEntry | Mapping[str, Any]) -> dict[str, Any]:
    payload = asdict(entry) if isinstance(entry, IQAHistoryEntry) else dict(entry)
    return to_jsonable(payload)


def restore_iqa_history_entry(payload: Mapping[str, Any]) -> IQAHistoryEntry:
    return IQAHistoryEntry(**dict(payload))


def summarize_iqa_history_entry(entry: IQAHistoryEntry | Mapping[str, Any]) -> str:
    obj = entry if isinstance(entry, IQAHistoryEntry) else restore_iqa_history_entry(entry)
    return f"[{obj.status}] {obj.reference_label or obj.reference_id} vs {obj.target_label or obj.target_id} ({obj.scope})"


def append_iqa_history(history_list: list[dict[str, Any]], entry: IQAHistoryEntry | Mapping[str, Any], max_items: int = 50) -> list[dict[str, Any]]:
    history_list.append(iqa_history_entry_to_jsonable(entry))
    if max_items > 0 and len(history_list) > max_items:
        del history_list[:-max_items]
    return history_list


def get_latest_iqa_history(history_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    return history_list[-1] if history_list else None


def clear_iqa_history(history_list: list[dict[str, Any]]) -> None:
    history_list.clear()
