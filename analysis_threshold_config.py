from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis_thresholds import validate_threshold_config


def build_empty_threshold_config(name: str = "Untitled threshold config", description: str = "") -> dict[str, Any]:
    return {"threshold_schema_version": 1, "name": str(name), "description": str(description), "rules": []}


def load_threshold_config(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid threshold config json") from exc
    return validate_threshold_config(payload)


def save_threshold_config(config: dict[str, Any], path: str | Path) -> str:
    validated = validate_threshold_config(dict(config))
    text = json.dumps(validated, ensure_ascii=False, indent=2, sort_keys=True)
    Path(path).write_text(text, encoding="utf-8")
    return text


def build_threshold_config_display_model(config: dict[str, Any]) -> dict[str, Any]:
    c = validate_threshold_config(dict(config))
    return {
        "threshold_config_display_schema_version": 1,
        "name": c.get("name", ""),
        "description": c.get("description", ""),
        "rule_count": len(c.get("rules", [])),
        "rules": [dict(r) for r in c.get("rules", [])],
    }


def render_threshold_config_text(config: dict[str, Any]) -> str:
    m = build_threshold_config_display_model(config)
    lines = [f"Name: {m['name']}", f"Description: {m['description']}", f"Rule Count: {m['rule_count']}"]
    if not m["rules"]:
        lines.append("No rules configured")
    for r in m["rules"]:
        lines.append(f"- {r.get('rule_id','')}: {r.get('analysis_type','')}.{r.get('metric','')} {r.get('operator','')} {r.get('threshold','')} [{r.get('severity','')}] {r.get('label','')}")
    return "\n".join(lines) + "\n"
