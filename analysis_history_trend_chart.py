from __future__ import annotations

import math
from typing import Any


def build_metric_trend_chart_model(trend_series: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(trend_series, dict) or trend_series.get("metric_trend_schema_version") != 1:
        raise ValueError("invalid trend_series")
    points = []
    for i, p in enumerate(trend_series.get("points") or []):
        y = p.get("value")
        if not isinstance(y, (int, float)) or not math.isfinite(float(y)):
            raise ValueError("non-finite y")
        points.append({"index": i, "record_id": str(p.get("record_id", "")), "generated_at": str(p.get("generated_at", "")), "x_label": str(p.get("generated_at", "")), "y": float(y), "validity": str(p.get("validity", "unknown")), "threshold_overall_status": str(p.get("threshold_overall_status", "missing"))})
    vals = [p["y"] for p in points]
    return {
        "trend_chart_schema_version": 1,
        "analysis_type": str(trend_series.get("analysis_type", "")),
        "metric_name": str(trend_series.get("metric_name", "")),
        "title": f"{trend_series.get('analysis_type','')} / {trend_series.get('metric_name','')} trend",
        "x_label": "generated_at",
        "y_label": str(trend_series.get("metric_name", "")),
        "point_count": len(points),
        "points": points,
        "y_min": min(vals) if vals else None,
        "y_max": max(vals) if vals else None,
        "latest": vals[-1] if vals else None,
    }


def render_metric_trend_chart_text(chart_model: dict[str, Any]) -> str:
    if not isinstance(chart_model, dict) or chart_model.get("trend_chart_schema_version") != 1:
        raise ValueError("invalid chart_model")
    lines = [f"Title: {chart_model.get('title','')}", f"Point Count: {chart_model.get('point_count',0)}", f"Range: {chart_model.get('y_min')} .. {chart_model.get('y_max')}", f"Latest: {chart_model.get('latest')}"]
    pts = chart_model.get("points") or []
    if not pts:
        lines.append("No chart points")
    for p in pts:
        lines.append(f"- {p['index']} | {p['x_label']} | y={p['y']} | validity={p['validity']} | threshold={p['threshold_overall_status']}")
    return "\n".join(lines) + "\n"
