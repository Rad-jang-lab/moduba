from __future__ import annotations

from typing import Any

from analysis_thresholds import validate_threshold_config


def build_threshold_editor_display_model(config: dict[str, Any], selected_rule_id: str | None = None) -> dict[str, Any]:
    c = validate_threshold_config({**dict(config), "rules": [dict(r) for r in (config.get("rules") or [])]})
    rules = []
    ids = {str(r.get("rule_id")) for r in c.get("rules", [])}
    if selected_rule_id is not None and str(selected_rule_id) not in ids:
        raise ValueError("selected_rule_id not found")
    for r in c.get("rules", []):
        rules.append(
            {
                "rule_id": str(r.get("rule_id", "")),
                "analysis_type": str(r.get("analysis_type", "")),
                "metric": str(r.get("metric", "")),
                "operator": str(r.get("operator", "")),
                "threshold": r.get("threshold"),
                "severity": str(r.get("severity", "")),
                "label": str(r.get("label", "")),
                "is_selected": selected_rule_id is not None and str(r.get("rule_id")) == str(selected_rule_id),
            }
        )
    return {
        "threshold_editor_display_schema_version": 1,
        "name": str(c.get("name", "")),
        "description": str(c.get("description", "")),
        "rule_count": len(rules),
        "selected_rule_id": None if selected_rule_id is None else str(selected_rule_id),
        "rules": rules,
    }


def render_threshold_rule_detail_text(rule: dict[str, Any]) -> str:
    r = dict(rule)
    lines = [
        f"Rule ID: {r.get('rule_id','')}",
        f"Analysis Type: {r.get('analysis_type','')}",
        f"Metric: {r.get('metric','')}",
        f"Operator: {r.get('operator','')}",
        f"Threshold: {r.get('threshold','')}",
        f"Severity: {r.get('severity','')}",
        f"Label: {r.get('label','')}",
    ]
    return "\n".join(lines) + "\n"


def render_threshold_editor_text(config: dict[str, Any], selected_rule_id: str | None = None) -> str:
    m = build_threshold_editor_display_model(config, selected_rule_id=selected_rule_id)
    lines = [f"Name: {m['name']}", f"Description: {m['description']}", f"Rule Count: {m['rule_count']}", f"Selected Rule ID: {m['selected_rule_id']}"]
    if not m["rules"]:
        lines.append("No rules configured")
    for r in m["rules"]:
        mark = "*" if r["is_selected"] else "-"
        lines.append(f"{mark} {r['rule_id']}: {r['analysis_type']}.{r['metric']} {r['operator']} {r['threshold']} [{r['severity']}] {r['label']}")
    return "\n".join(lines) + "\n"
