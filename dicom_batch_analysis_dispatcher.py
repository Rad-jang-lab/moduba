from __future__ import annotations

from typing import Any, Callable

from analysis_result_model import normalize_analysis_result

SUPPORTED_BATCH_ANALYSIS_TYPES = {"snr", "cnr", "uniformity", "mtf"}


def get_batch_analysis_type(task: dict[str, Any]) -> str:
    t = str((task or {}).get("analysis_type", "")).strip().lower()
    if not t:
        raise ValueError("missing analysis_type")
    return t


def get_task_roi_ids(task: dict[str, Any]) -> list[str]:
    roi_ids = [str(x) for x in ((task or {}).get("roi_ids") or [])]
    if not roi_ids:
        raise ValueError("missing roi_ids")
    return roi_ids


def get_pixel_array_from_context(context: dict[str, Any]):
    if "pixel_array" in (context or {}):
        return context["pixel_array"]
    pd = dict((context or {}).get("pixel_data") or {})
    if "pixel_array" in pd:
        return pd["pixel_array"]
    raise ValueError("missing pixel_array")


def get_resolved_rois_from_context_or_task(task: dict[str, Any], item: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if isinstance((context or {}).get("resolved_rois"), dict):
        return dict(context["resolved_rois"])
    return {"roi_ids": get_task_roi_ids(task)}


def validate_batch_analysis_payload(analysis_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        normalize_analysis_result(analysis_type, dict(payload))
    except Exception as exc:
        raise ValueError(f"invalid analysis payload for {analysis_type}") from exc
    return payload


def create_existing_analysis_dispatcher(*, snr_analyzer=None, cnr_analyzer=None, uniformity_analyzer=None, mtf_analyzer=None, payload_validator: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None):
    analyzers = {"snr": snr_analyzer, "cnr": cnr_analyzer, "uniformity": uniformity_analyzer, "mtf": mtf_analyzer}
    validator = payload_validator or validate_batch_analysis_payload

    def _dispatch(task: dict[str, Any], item: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        analysis_type = get_batch_analysis_type(task)
        if analysis_type not in SUPPORTED_BATCH_ANALYSIS_TYPES:
            raise ValueError(f"unsupported analysis_type: {analysis_type}")
        analyzer = analyzers.get(analysis_type)
        if not callable(analyzer):
            raise ValueError(f"missing analyzer for analysis_type: {analysis_type}")
        _ = get_task_roi_ids(task)
        _ = get_pixel_array_from_context(context)
        rois = get_resolved_rois_from_context_or_task(task, item, context)
        payload = analyzer(dict(task), dict(item), {**dict(context), **rois})
        if not isinstance(payload, dict):
            raise ValueError("analysis payload must be a dict")
        return validator(analysis_type, payload)

    return _dispatch


def render_batch_analysis_dispatcher_capability_text(dispatcher_info: dict[str, Any]) -> str:
    sup = sorted(list(dispatcher_info.get("supported_analysis_types") or []))
    conn = sorted(list(dispatcher_info.get("connected_analyzer_types") or []))
    miss = sorted(list(dispatcher_info.get("missing_analyzer_types") or []))
    lines = [
        "Batch Analysis Dispatcher Capability",
        f"supported_analysis_types: {sup}",
        f"connected_analyzer_types: {conn}",
        f"missing_analyzer_types: {miss}",
        f"payload_validation_enabled: {bool(dispatcher_info.get('payload_validation_enabled', True))}",
        "next_action: Run Pixel Batch Execution",
    ]
    return "\n".join(lines) + "\n"
