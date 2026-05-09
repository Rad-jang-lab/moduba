from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

_ORDER = ["snr", "cnr", "uniformity", "mtf"]
_TITLE = {"snr": "SNR", "cnr": "CNR", "uniformity": "Uniformity", "mtf": "MTF"}


def _ordered_keys(results: dict[str, Any]) -> list[str]:
    lead = [k for k in _ORDER if k in results]
    tail = sorted(k for k in results if k not in _ORDER)
    return [*lead, *tail]


def _ensure_finite(obj: Any) -> None:
    if isinstance(obj, (int, float)):
        if not math.isfinite(float(obj)):
            raise ValueError(f"non-finite numeric value detected: {obj!r}")
    elif isinstance(obj, dict):
        for v in obj.values():
            _ensure_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _ensure_finite(v)


def _format_metric_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def build_analysis_report_model(normalized_results: dict[str, dict[str, Any]], metadata: dict[str, Any] | None = None, generated_at: str | None = None, threshold_evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    if normalized_results is None:
        raise ValueError("normalized_results is None")

    sections: list[dict[str, Any]] = []
    analysis_types: list[str] = []
    valid_count = 0
    invalid_count = 0
    warning_count = 0

    for analysis_type in _ordered_keys(normalized_results):
        item = normalized_results.get(analysis_type)
        if item is None:
            raise ValueError(f"normalized_results[{analysis_type!r}] is None")
        _ensure_finite(item)

        validity = str(item.get("validity", ""))
        warnings = list(item.get("warnings") or [])
        metrics = []
        for name in sorted((item.get("metrics") or {}).keys()):
            value = item["metrics"][name]
            metrics.append({"name": name, "value": value, "formatted_value": _format_metric_value(value)})

        curve_summaries = []
        for curve_name in sorted((item.get("curves") or {}).keys()):
            curve = item["curves"][curve_name] or {}
            xs = list(curve.get("x") or [])
            ys = list(curve.get("y") or [])
            curve_summaries.append({
                "name": curve_name,
                "point_count": min(len(xs), len(ys)),
                "x_label": str(curve.get("x_label") or "x"),
                "y_label": str(curve.get("y_label") or "y"),
            })

        section = {
            "analysis_type": analysis_type,
            "title": _TITLE.get(analysis_type, analysis_type.upper()),
            "status": str(item.get("status", "")),
            "validity": validity,
            "metrics": metrics,
            "curve_summaries": curve_summaries,
            "warnings": warnings,
            "reason_codes": list(item.get("reason_codes") or []),
            "roi_info": dict(item.get("roi_info") or {}),
            "source_payload_keys": list(item.get("source_payload_keys") or []),
        }
        sections.append(section)
        analysis_types.append(analysis_type)
        warning_count += len(warnings)
        if validity == "valid":
            valid_count += 1
        else:
            invalid_count += 1

    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    model = {
        "report_schema_version": 1,
        "generated_at": stamp,
        "metadata": dict(metadata or {}),
        "summary": {
            "analysis_count": len(sections),
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "warning_count": warning_count,
            "analysis_types": analysis_types,
        },
        "sections": sections,
    }
    if threshold_evaluation is not None:
        if threshold_evaluation.get("threshold_evaluation_schema_version") != 1:
            raise ValueError("invalid threshold_evaluation schema")
        model["threshold_evaluation"] = dict(threshold_evaluation)
    return model


def render_analysis_report_markdown(report_model: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# QC Analysis Report")
    lines.append("")
    lines.append(f"- Generated At: {report_model.get('generated_at', '')}")
    metadata = dict(report_model.get("metadata") or {})
    if metadata:
        lines.append("- Metadata:")
        for key in sorted(metadata.keys()):
            lines.append(f"  - {key}: {metadata[key]}")
    summary = dict(report_model.get("summary") or {})
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Analysis Count: {summary.get('analysis_count', 0)}")
    lines.append(f"- Valid Count: {summary.get('valid_count', 0)}")
    lines.append(f"- Invalid Count: {summary.get('invalid_count', 0)}")
    lines.append(f"- Warning Count: {summary.get('warning_count', 0)}")
    lines.append(f"- Analysis Types: {', '.join(summary.get('analysis_types', []))}")

    threshold_eval = report_model.get("threshold_evaluation")
    if threshold_eval is not None:
        lines.append("")
        lines.append("## QC Threshold Evaluation")
        lines.append(f"- Config Name: {threshold_eval.get('config_name', '')}")
        lines.append(f"- Overall Status: {threshold_eval.get('overall_status', '')}")
        lines.append(f"- Summary: {threshold_eval.get('summary', {})}")
        for rule in list(threshold_eval.get("results") or []):
            lines.append(f"- Rule {rule.get('rule_id','')}: status={rule.get('status','')}, reason={rule.get('reason','')}")

    for section in list(report_model.get("sections") or []):
        lines.append("")
        lines.append(f"## {section.get('title', section.get('analysis_type', 'Analysis'))}")
        lines.append(f"- Analysis Type: {section.get('analysis_type', '')}")
        lines.append(f"- Status: {section.get('status', '')}")
        lines.append(f"- Validity: {section.get('validity', '')}")

        lines.append("- Metrics:")
        for metric in list(section.get("metrics") or []):
            lines.append(f"  - {metric.get('name', '')}: {metric.get('formatted_value', '')}")

        curve_summaries = list(section.get("curve_summaries") or [])
        if curve_summaries:
            lines.append("- Curve Summaries:")
            for curve in curve_summaries:
                lines.append(
                    f"  - {curve.get('name', '')}: point_count={curve.get('point_count', 0)}, x_label={curve.get('x_label', '')}, y_label={curve.get('y_label', '')}"
                )

        warnings = list(section.get("warnings") or [])
        reason_codes = list(section.get("reason_codes") or [])
        lines.append(f"- Warnings: {warnings}")
        lines.append(f"- Reason Codes: {reason_codes}")
        lines.append(f"- ROI Info: {dict(section.get('roi_info') or {})}")
        lines.append(f"- Source Payload Keys: {list(section.get('source_payload_keys') or [])}")

    return "\n".join(lines) + "\n"
