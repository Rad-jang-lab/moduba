from __future__ import annotations

import math
from typing import Any

from iqa_result_schema import IQAResult
LABEL_MAP = {
    "raw_dicom_pixel": "Raw DICOM Pixel",
    "modality_lut": "Modality LUT",
    "windowed_display": "Windowed Display",
    "full_image": "Full Image",
    "full": "Full Image",
    "roi": "Selected ROI",
    "actual_union": "Actual Union",
    "bits": "Bits Stored",
    "auto": "Auto",
}
WARNING_MESSAGE_MAP = {
    "roi_bbox_clipped_to_image_bounds": "ROI가 영상 범위를 벗어나 공통 가능한 영역으로 보정되었습니다.",
    "invalid_roi_bbox_after_clip": "ROI 보정 후 유효한 비교 영역이 남지 않았습니다.",
    "missing_scope_roi": "ROI 범위가 선택되었지만 사용할 ROI가 없습니다.",
    "missing_bits_stored": "Bits Stored 정보가 없어 data range 기준을 자동으로 대체했습니다.",
    "monochrome1_without_inversion": "MONOCHROME1 영상이지만 반전 옵션이 적용되지 않았습니다.",
    "full_image_background": "Full Image 분석에는 배경 영역이 포함될 수 있습니다.",
    "same_image": "Reference와 Target이 동일합니다. 검증용 비교로 사용할 수 있습니다.",
    "stale_roi_id": "세션에 저장된 ROI를 현재 영상에서 찾을 수 없습니다.",
}


def _hist_value(result: IQAResult, key: str) -> Any:
    hist = getattr(result.context, "histogram", None)
    if isinstance(hist, dict) and key in hist:
        return hist.get(key)
    if isinstance(result.context.ssim_params, dict):
        return result.context.ssim_params.get(key)
    return None


def _num(value: Any, digits: int = 4) -> str:
    if value is None:
        return "계산 불가"
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return f"{float(value):.{digits}f}"
    return str(value)


def _warning_severity(warning: str) -> str:
    w = warning.lower()
    if any(k in w for k in ["shape mismatch", "missing_reference", "missing_target", "data_range <= 0", "failed_to_load"]):
        return "error"
    if any(k in w for k in ["fallback", "monochrome1", "full image", "constant histogram", "bitsstored", "windowcenter/width"]):
        return "caution"
    return "info"
def _friendly(value: Any) -> str:
    text = str(value)
    return LABEL_MAP.get(text, text)


def build_iqa_metric_rows(result: IQAResult) -> list[dict[str, Any]]:
    m = result.metrics
    return [
        {"label": "MSE", "value": _num(m.mse), "unit": "", "note": ""},
        {"label": "RMSE", "value": _num(m.rmse), "unit": "", "note": ""},
        {"label": "PSNR", "value": _num(m.psnr), "unit": "dB", "note": "data range 기준"},
        {"label": "SSIM", "value": _num(m.ssim), "unit": "", "note": "0~1"},
        {"label": "HIST corr", "value": _num(m.hist_corr), "unit": "", "note": "분포 유사도"},
    ]


def build_iqa_context_rows(result: IQAResult) -> list[dict[str, Any]]:
    c = result.context
    return [
        {"label": "Input Mode", "value": _friendly(c.input_mode)},
        {"label": "Scope", "value": _friendly(c.scope)},
        {"label": "Data Range Policy", "value": _friendly(c.data_range_policy)},
        {"label": "Data Range Used", "value": _num(c.data_range_used)},
        {"label": "Bits Stored", "value": c.bits_stored},
        {"label": "Photometric", "value": c.ssim_params.get("photometric_interpretation") if isinstance(c.ssim_params, dict) else None},
        {"label": "Window Center", "value": c.ssim_params.get("window_center") if isinstance(c.ssim_params, dict) else None},
        {"label": "Window Width", "value": c.ssim_params.get("window_width") if isinstance(c.ssim_params, dict) else None},
        {"label": "Image Shape", "value": list(c.image_shape)},
        {"label": "Original Ref Shape", "value": c.ssim_params.get("original_reference_shape") if isinstance(c.ssim_params, dict) else None},
        {"label": "Original Tar Shape", "value": c.ssim_params.get("original_target_shape") if isinstance(c.ssim_params, dict) else None},
        {"label": "Compared Shape", "value": c.ssim_params.get("compared_shape") if isinstance(c.ssim_params, dict) else None},
        {"label": "Shape Alignment Policy", "value": c.ssim_params.get("shape_alignment_policy") if isinstance(c.ssim_params, dict) else "none"},
        {"label": "ROI ID", "value": c.ssim_params.get("roi_id") if isinstance(c.ssim_params, dict) else None},
        {"label": "ROI Label", "value": c.ssim_params.get("roi_label") if isinstance(c.ssim_params, dict) else None},
        {"label": "ROI Policy", "value": c.ssim_params.get("roi_policy") if isinstance(c.ssim_params, dict) else None},
        {"label": "ROI BBox", "value": c.ssim_params.get("roi_bbox") if isinstance(c.ssim_params, dict) else None},
        {"label": "Histogram Bins", "value": _hist_value(result, "histogram_bins") or c.histogram_bins},
        {"label": "Histogram Range", "value": _hist_value(result, "histogram_range") or c.histogram_range},
        {"label": "Histogram Normalized", "value": _hist_value(result, "histogram_normalized")},
        {"label": "Histogram Corr", "value": _num(_hist_value(result, "histogram_corr"))},
        {"label": "Histogram Distribution Hint", "value": _hist_value(result, "histogram_distribution_hint")},
        {"label": "Reference Peak Bin", "value": _hist_value(result, "histogram_reference_peak_bin")},
        {"label": "Target Peak Bin", "value": _hist_value(result, "histogram_target_peak_bin")},
    ]


def build_iqa_warning_rows(result: IQAResult) -> list[dict[str, Any]]:
    if not result.warnings:
        return [{"severity": "info", "message": "주의 사항 없음"}]
    rows = []
    for item in sorted(set(result.warnings)):
        message = WARNING_MESSAGE_MAP.get(str(item), str(item))
        lower = message.lower()
        if "shape mismatch" in lower:
            message = "영상 크기가 달라 공통 영역 기준으로 비교했습니다."
        elif "bitsstored missing" in lower:
            message = "Data range 기준을 자동으로 대체했습니다. PSNR 해석에 주의하세요."
        elif "monochrome1 without inversion option" in lower:
            message = "MONOCHROME1 영상이지만 반전 옵션이 적용되지 않았습니다."
        elif "windowcenter/width missing" in lower:
            message = "Window Center/Width 정보가 없어 min-max fallback을 사용했습니다."
        elif "identical image" in lower:
            message = "Reference와 Target이 동일합니다. 검증용 비교로 사용할 수 있습니다."
        rows.append({"severity": _warning_severity(item), "message": message})
    severity_rank = {"error": 0, "caution": 1, "info": 2}
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda r: (severity_rank.get(r.get("severity", "info"), 9), r.get("message", ""))):
        msg = str(row.get("message", ""))
        if msg in seen:
            continue
        seen.add(msg)
        deduped.append(row)
    return deduped


def build_iqa_summary(result: IQAResult) -> str:
    parts = []
    if result.metrics.ssim >= 0.95:
        parts.append("구조 유사도는 매우 높습니다")
    elif result.metrics.ssim >= 0.85:
        parts.append("구조 유사도는 비교적 높습니다")
    else:
        parts.append("구조 차이 가능성이 있습니다")
    if not math.isnan(result.metrics.hist_corr) and result.metrics.hist_corr < 0.5:
        parts.append("밝기/분포 차이가 있습니다")
    hist_hint = str(_hist_value(result, "histogram_distribution_hint") or "")
    if hist_hint == "target_shifted_brighter":
        parts.append("Target 영상이 Reference보다 높은 밝기 구간에 더 많이 분포합니다")
    elif hist_hint == "target_shifted_darker":
        parts.append("Target 영상이 Reference보다 낮은 밝기 구간에 더 많이 분포합니다")
    if result.context.scope in {"full", "full_image", "Full Image"}:
        parts.append("Full Image 비교에는 background가 포함될 수 있습니다")
    if any("fallback" in item.lower() for item in result.warnings):
        parts.append("fallback 조건이 있어 결과 해석에 주의가 필요합니다")
    parts.append("진단 정확도 판정이 아닌 영상 품질 비교 지표입니다")
    return ". ".join(parts) + "."


def build_iqa_display_model(result: IQAResult, reference_label: str | None = None, target_label: str | None = None) -> dict[str, Any]:
    return {
        "title": "IQA Comparison",
        "reference_label": reference_label,
        "target_label": target_label,
        "summary": build_iqa_summary(result),
        "metric_rows": build_iqa_metric_rows(result),
        "context_rows": build_iqa_context_rows(result),
        "warning_rows": build_iqa_warning_rows(result),
    }


def format_iqa_display_text(display_model: dict[str, Any]) -> tuple[str, str]:
    metrics = display_model.get("metric_rows", [])
    metric_map = {row["label"]: row for row in metrics}
    pair_text = ''
    if display_model.get('reference_label') or display_model.get('target_label'):
        pair_text = f"Reference={display_model.get('reference_label')} | Target={display_model.get('target_label')} | "
    context_lookup = {row["label"]: row.get("value") for row in display_model.get("context_rows", [])}
    result_text = "\n".join([
        "[IQA Summary]",
        f"- 종합 해석: {display_model.get('summary')}",
        "- Status: success",
        f"- Reference: {display_model.get('reference_label') or 'None'}",
        f"- Target: {display_model.get('target_label') or 'None'}",
        "",
        "[Metrics]",
        f"- MSE: {metric_map.get('MSE', {}).get('value')}",
        f"- RMSE: {metric_map.get('RMSE', {}).get('value')}",
        f"- PSNR: {metric_map.get('PSNR', {}).get('value')}",
        f"- SSIM: {metric_map.get('SSIM', {}).get('value')}",
        f"- HIST Corr: {metric_map.get('HIST corr', {}).get('value')}",
        "",
        "[Histogram]",
        f"- Range: {context_lookup.get('Histogram Range')}",
        f"- Bins: {context_lookup.get('Histogram Bins')}",
        f"- Corr: {context_lookup.get('Histogram Corr')}",
        f"- Distribution: {context_lookup.get('Histogram Distribution Hint')}",
    ])
    warnings = ",".join(row.get("message", "") for row in display_model.get("warning_rows", []))
    context_text = "\n".join([
        "[Context]",
        f"- Input Mode: {context_lookup.get('Input Mode')}",
        f"- Scope: {context_lookup.get('Scope')}",
        f"- ROI: {context_lookup.get('ROI Label') or context_lookup.get('ROI ID') or 'None'}",
        f"- Data Range: {context_lookup.get('Data Range Policy')} / {context_lookup.get('Data Range Used')}",
        f"- Bits Stored: {context_lookup.get('Bits Stored')}",
        f"- Photometric: {context_lookup.get('Photometric')}",
        f"- Window Center/Width: {context_lookup.get('Window Center')} / {context_lookup.get('Window Width')}",
        f"- Compared Shape: {context_lookup.get('Compared Shape')}",
        "",
        "[Warnings]",
        f"- {warnings or 'Warnings: None'}",
    ])
    return result_text, context_text
