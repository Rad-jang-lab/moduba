from __future__ import annotations

import math
from typing import Any

from analysis_history_store import filter_analysis_history_records


def _validated_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in records:
        if r.get("history_schema_version") != 1:
            raise ValueError("unsupported history schema version")
        out.append(dict(r))
    return out


def build_threshold_status_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _validated_records(records)
    counts = {"pass": 0, "warn": 0, "fail": 0, "not_evaluated": 0, "missing": 0}
    config_name_counts: dict[str, int] = {}
    rule_status_counts: dict[str, dict[str, int]] = {}
    for r in rows:
        te = r.get("threshold_evaluation")
        if not isinstance(te, dict):
            counts["missing"] += 1
            continue
        status = str(te.get("overall_status", "not_evaluated"))
        counts[status if status in counts else "not_evaluated"] += 1
        name = str(te.get("config_name", ""))
        config_name_counts[name] = config_name_counts.get(name, 0) + 1
        for rr in te.get("results", []) or []:
            rid = str(rr.get("rule_id", ""))
            rs = str(rr.get("status", "not_evaluated"))
            slot = rule_status_counts.setdefault(rid, {"fail": 0, "warn": 0})
            if rs in slot:
                slot[rs] += 1
    return {"threshold_status_counts": counts, "config_name_counts": dict(sorted(config_name_counts.items())), "rule_status_counts": dict(sorted(rule_status_counts.items()))}


def build_history_summary(records: list[dict[str, Any]], analysis_type: str | None = None, validity: str | None = None) -> dict[str, Any]:
    rows = filter_analysis_history_records(_validated_records(records), analysis_type=None, validity=None)
    analysis_counts: dict[str, int] = {}
    validity_counts = {"valid": 0, "invalid": 0, "unknown": 0}
    warning_count = 0
    metric_values: dict[str, list[tuple[str, float]]] = {}
    metric_non_finite_counts: dict[str, int] = {}
    for r in rows:
        results = ((r.get("export_snapshot") or {}).get("results") or {})
        for atype, item in results.items():
            if analysis_type and atype != analysis_type:
                continue
            if not isinstance(item, dict):
                continue
            val = str(item.get("validity", "unknown")) or "unknown"
            if validity and val != validity:
                continue
            analysis_counts[atype] = analysis_counts.get(atype, 0) + 1
            validity_counts[val if val in validity_counts else "unknown"] += 1
            warning_count += len(item.get("warnings") or [])
            for mname, mval in (item.get("metrics") or {}).items():
                if isinstance(mval, (int, float)):
                    if math.isfinite(float(mval)):
                        key = f"{atype}.{mname}"
                        metric_values.setdefault(key, []).append((str(r.get("generated_at", "")), float(mval)))
                    else:
                        key = f"{atype}.{mname}"
                        metric_non_finite_counts[key] = metric_non_finite_counts.get(key, 0) + 1
    metric_summaries = {}
    for k, pairs in sorted(metric_values.items()):
        vals = [v for _, v in pairs]
        latest = vals[max(range(len(pairs)), key=lambda i: pairs[i][0])] if vals else None
        metric_summaries[k] = {"count": len(vals), "min": min(vals) if vals else None, "max": max(vals) if vals else None, "mean": (sum(vals) / len(vals)) if vals else None, "latest": latest}
    t = build_threshold_status_summary(rows)
    return {"history_summary_schema_version": 1, "record_count": len(rows), "filters": {"analysis_type": analysis_type, "validity": validity}, "analysis_counts": dict(sorted(analysis_counts.items())), "validity_counts": validity_counts, "warning_count": warning_count, "threshold_status_counts": t["threshold_status_counts"], "metric_summaries": metric_summaries, "metric_non_finite_counts": dict(sorted(metric_non_finite_counts.items()))}


def build_metric_trend_series(records: list[dict[str, Any]], analysis_type: str, metric_name: str) -> dict[str, Any]:
    rows = _validated_records(records)
    points = []
    missing_count = 0
    non_finite_count = 0
    for r in rows:
        item = (((r.get("export_snapshot") or {}).get("results") or {}).get(analysis_type) or {})
        metrics = item.get("metrics") or {}
        if metric_name not in metrics:
            missing_count += 1
            continue
        value = metrics[metric_name]
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            non_finite_count += 1
            continue
        te = r.get("threshold_evaluation") or {}
        points.append({"record_id": str(r.get("record_id", "")), "generated_at": str(r.get("generated_at", "")), "value": float(value), "validity": str(item.get("validity", "unknown")), "threshold_overall_status": str(te.get("overall_status", "missing")) if te else "missing"})
    points = sorted(points, key=lambda p: (p["generated_at"], p["record_id"]))
    return {"metric_trend_schema_version": 1, "analysis_type": analysis_type, "metric_name": metric_name, "point_count": len(points), "missing_count": missing_count, "non_finite_count": non_finite_count, "points": points}


def render_history_summary_text(summary: dict[str, Any]) -> str:
    lines = [f"Record Count: {summary.get('record_count',0)}", f"Filters: {summary.get('filters',{})}", f"Analysis Counts: {summary.get('analysis_counts',{})}", f"Validity Counts: {summary.get('validity_counts',{})}", f"Warning Count: {summary.get('warning_count',0)}", f"Threshold Status Counts: {summary.get('threshold_status_counts',{})}", f"Metric Non-finite Counts: {summary.get('metric_non_finite_counts',{})}", "Metric Summaries:"]
    for k, v in sorted((summary.get("metric_summaries") or {}).items()):
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"


def render_metric_trend_text(trend_series: dict[str, Any]) -> str:
    points = trend_series.get("points") or []
    vals = [p["value"] for p in points]
    lines = [f"Analysis: {trend_series.get('analysis_type')}", f"Metric: {trend_series.get('metric_name')}", f"Point Count: {trend_series.get('point_count',0)}", f"Missing Count: {trend_series.get('missing_count',0)}", f"Non-finite Count: {trend_series.get('non_finite_count',0)}", f"Summary: latest={vals[-1] if vals else None}, min={min(vals) if vals else None}, max={max(vals) if vals else None}, mean={(sum(vals)/len(vals)) if vals else None}"]
    if not points:
        lines.append("No trend points")
    for p in points:
        lines.append(f"- {p['generated_at']} | {p['record_id']} | value={p['value']} | validity={p['validity']} | threshold={p['threshold_overall_status']}")
    return "\n".join(lines) + "\n"
