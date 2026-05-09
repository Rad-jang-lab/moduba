from __future__ import annotations

from pathlib import Path, PureWindowsPath


def _normalize_path_parts(path_text: str) -> tuple[str, str]:
    normalized = str(path_text or "").strip()
    if not normalized:
        return "", ""
    if "\\" in normalized and "/" not in normalized:
        p = PureWindowsPath(normalized)
        return (p.parent.name if p.parent and str(p.parent) not in {"", "."} else "", p.name or normalized)
    p = Path(normalized)
    return (p.parent.name if p.parent and str(p.parent) not in {"", "."} else "", p.name or normalized)


def format_compact_path_label(path_text: str, max_chars: int = 54, empty_placeholder: str = "No file") -> str:
    """UI 표시용 compact path 라벨 생성. 내부 path 식별자 대체용이 아니다."""
    parent, base = _normalize_path_parts(path_text)
    if not base:
        return empty_placeholder
    compact = f"{parent}/{base}" if parent else base
    if len(compact) <= max_chars:
        return compact
    if max_chars <= 3:
        return "." * max_chars
    tail_len = max(max_chars - 3, 1)
    return f"...{compact[-tail_len:]}"


def build_viewer_a_status_label(path_text: str, current_frame_index: int, frame_count: int, prefix: str = "A") -> str:
    compact = format_compact_path_label(path_text, max_chars=42)
    frame_text = "-"
    if frame_count > 0:
        frame_text = f"{max(current_frame_index, 0) + 1}/{frame_count}"
    return f"{prefix} | {compact} | Frame {frame_text}"


def build_pair_status_label(reference_label: str, target_label: str, ready_text: str, roi_label: str = "", scope: str = "full_image") -> str:
    ref = format_compact_path_label(reference_label) if reference_label else "None"
    tar = format_compact_path_label(target_label) if target_label else "None"
    roi_text = f" | ROI={roi_label or 'None'}" if scope == "roi" else ""
    return f"Pair: Reference={ref} | Target={tar}{roi_text} | {ready_text}"


def build_analysis_display_model(normalized_result: dict) -> dict:
    analysis_type = str(normalized_result.get("analysis_type", "")).lower()
    title_map = {"snr": "SNR", "cnr": "CNR", "uniformity": "Uniformity", "mtf": "MTF"}
    metrics = dict(normalized_result.get("metrics") or {})
    metric_rows = [
        {"name": key, "value": f"{float(val):.6g}", "raw_value": float(val)}
        for key, val in metrics.items()
        if isinstance(val, (int, float))
    ]
    curve_summaries = []
    for name, curve in (normalized_result.get("curves") or {}).items():
        xs = list((curve or {}).get("x") or [])
        ys = list((curve or {}).get("y") or [])
        curve_summaries.append({"name": str(name), "point_count": min(len(xs), len(ys)), "x_label": "x", "y_label": "y"})
    roi_lines = [f"{k}: {v}" for k, v in (normalized_result.get("roi_info") or {}).items()]
    return {
        "analysis_type": analysis_type,
        "title": title_map.get(analysis_type, analysis_type.upper() or "Analysis"),
        "status_text": f"Status: {normalized_result.get('status', '-')}",
        "validity_text": f"Validity: {normalized_result.get('validity', '-')}",
        "metric_rows": metric_rows,
        "curve_summaries": curve_summaries,
        "warning_lines": list(normalized_result.get("warnings") or []),
        "reason_lines": list(normalized_result.get("reason_codes") or []),
        "roi_lines": roi_lines,
    }
