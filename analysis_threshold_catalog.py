from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis_threshold_config import load_threshold_config, save_threshold_config
from analysis_thresholds import validate_threshold_config


def build_empty_threshold_catalog(name: str = "Threshold catalog", description: str = "") -> dict[str, Any]:
    return {"threshold_catalog_schema_version": 1, "name": str(name), "description": str(description), "selected_config_id": None, "configs": {}}


def validate_threshold_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    c = dict(catalog or {})
    if c.get("threshold_catalog_schema_version") != 1:
        raise ValueError("unsupported threshold catalog schema version")
    configs = c.get("configs")
    if not isinstance(configs, dict):
        raise ValueError("configs must be dict")
    normalized_configs: dict[str, dict[str, Any]] = {}
    for config_id, config in configs.items():
        cid = str(config_id)
        normalized_configs[cid] = validate_threshold_config({**dict(config), "rules": [dict(r) for r in (config.get("rules") or [])]})
    selected = c.get("selected_config_id")
    if selected is not None and str(selected) not in normalized_configs:
        raise ValueError("selected_config_id not found")
    return {
        "threshold_catalog_schema_version": 1,
        "name": str(c.get("name", "")),
        "description": str(c.get("description", "")),
        "selected_config_id": None if selected is None else str(selected),
        "configs": {k: dict(v) for k, v in normalized_configs.items()},
    }


def _catalog_copy(catalog: dict[str, Any]) -> dict[str, Any]:
    return validate_threshold_catalog(catalog)


def add_threshold_config_to_catalog(catalog: dict[str, Any], config: dict[str, Any], config_id: str | None = None) -> dict[str, Any]:
    c = _catalog_copy(catalog)
    cid = str(config_id or config.get("name") or "").strip()
    if not cid:
        raise ValueError("config_id is empty")
    if cid in c["configs"]:
        raise ValueError("duplicate config_id")
    c["configs"][cid] = validate_threshold_config({**dict(config), "rules": [dict(r) for r in (config.get("rules") or [])]})
    return validate_threshold_catalog(c)


def update_threshold_config_in_catalog(catalog: dict[str, Any], config_id: str, config: dict[str, Any]) -> dict[str, Any]:
    c = _catalog_copy(catalog)
    cid = str(config_id)
    if cid not in c["configs"]:
        raise ValueError("config_id not found")
    c["configs"][cid] = validate_threshold_config({**dict(config), "rules": [dict(r) for r in (config.get("rules") or [])]})
    return validate_threshold_catalog(c)


def remove_threshold_config_from_catalog(catalog: dict[str, Any], config_id: str) -> dict[str, Any]:
    c = _catalog_copy(catalog)
    cid = str(config_id)
    if cid not in c["configs"]:
        raise ValueError("config_id not found")
    c["configs"].pop(cid)
    if c.get("selected_config_id") == cid:
        c["selected_config_id"] = None
    return validate_threshold_catalog(c)


def get_threshold_config_from_catalog(catalog: dict[str, Any], config_id: str) -> dict[str, Any]:
    c = _catalog_copy(catalog)
    cid = str(config_id)
    if cid not in c["configs"]:
        raise ValueError("config_id not found")
    return dict(c["configs"][cid])


def list_threshold_catalog_entries(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    c = _catalog_copy(catalog)
    out = []
    for cid in sorted(c["configs"].keys()):
        cfg = c["configs"][cid]
        out.append({"config_id": cid, "name": str(cfg.get("name", "")), "description": str(cfg.get("description", "")), "rule_count": len(cfg.get("rules", []))})
    return out


def set_selected_threshold_config_id(catalog: dict[str, Any], config_id: str) -> dict[str, Any]:
    c = _catalog_copy(catalog)
    cid = str(config_id)
    if cid not in c["configs"]:
        raise ValueError("config_id not found")
    c["selected_config_id"] = cid
    return validate_threshold_catalog(c)


def clear_selected_threshold_config_id(catalog: dict[str, Any]) -> dict[str, Any]:
    c = _catalog_copy(catalog)
    c["selected_config_id"] = None
    return validate_threshold_catalog(c)


def get_selected_threshold_config(catalog: dict[str, Any]) -> dict[str, Any]:
    c = _catalog_copy(catalog)
    sid = c.get("selected_config_id")
    if sid is None:
        raise ValueError("selected_config_id is empty")
    return get_threshold_config_from_catalog(c, sid)


def load_threshold_catalog(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid threshold catalog json") from exc
    return validate_threshold_catalog(payload)


def save_threshold_catalog(catalog: dict[str, Any], path: str | Path) -> str:
    validated = validate_threshold_catalog(catalog)
    text = json.dumps(validated, ensure_ascii=False, indent=2, sort_keys=True)
    Path(path).write_text(text, encoding="utf-8")
    return text


def import_threshold_config_file_to_catalog(catalog: dict[str, Any], path: str | Path, config_id: str | None = None) -> dict[str, Any]:
    config = load_threshold_config(path)
    return add_threshold_config_to_catalog(catalog, config, config_id=config_id)


def export_threshold_config_from_catalog(catalog: dict[str, Any], config_id: str, path: str | Path) -> str:
    config = get_threshold_config_from_catalog(catalog, config_id)
    return save_threshold_config(config, path)


def build_threshold_catalog_display_model(catalog: dict[str, Any]) -> dict[str, Any]:
    c = validate_threshold_catalog(catalog)
    entries = []
    selected = c.get("selected_config_id")
    for row in list_threshold_catalog_entries(c):
        entries.append({**row, "is_selected": row["config_id"] == selected})
    return {
        "threshold_catalog_display_schema_version": 1,
        "name": c.get("name", ""),
        "description": c.get("description", ""),
        "config_count": len(entries),
        "selected_config_id": selected,
        "entries": entries,
    }


def render_threshold_catalog_text(catalog: dict[str, Any]) -> str:
    m = build_threshold_catalog_display_model(catalog)
    lines = [f"Name: {m['name']}", f"Description: {m['description']}", f"Config Count: {m['config_count']}", f"Selected Config ID: {m['selected_config_id']}"]
    if not m["entries"]:
        lines.append("No configs in catalog")
    for e in m["entries"]:
        mark = "*" if e["is_selected"] else "-"
        lines.append(f"{mark} {e['config_id']}: {e['name']} (rules={e['rule_count']})")
    return "\n".join(lines) + "\n"
