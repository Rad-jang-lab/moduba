from __future__ import annotations

import json
from typing import Any

from analysis_threshold_catalog import validate_threshold_catalog
from analysis_thresholds import validate_threshold_config


def configs_are_equivalent_for_catalog_sync(config_a: dict[str, Any], config_b: dict[str, Any]) -> bool:
    a = validate_threshold_config({**dict(config_a), "rules": [dict(r) for r in (config_a.get("rules") or [])]})
    b = validate_threshold_config({**dict(config_b), "rules": [dict(r) for r in (config_b.get("rules") or [])]})
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def build_threshold_catalog_sync_status(current_config: dict[str, Any] | None, catalog: dict[str, Any] | None, selected_config_id: str | None = None) -> dict[str, Any]:
    has_current = current_config is not None
    if current_config is not None:
        current_config = validate_threshold_config({**dict(current_config), "rules": [dict(r) for r in (current_config.get("rules") or [])]})
    if catalog is None:
        return {"threshold_catalog_sync_schema_version": 1, "has_current_config": has_current, "has_catalog": False, "selected_config_id": None, "is_dirty": has_current, "status": "no_catalog", "current_config_name": str((current_config or {}).get("name", "")), "selected_config_name": "", "message": "catalog is empty"}
    c = validate_threshold_catalog(catalog)
    sid = selected_config_id if selected_config_id is not None else c.get("selected_config_id")
    if sid is None:
        status = "no_selected_config" if not has_current else "unsynced_current_config"
        return {"threshold_catalog_sync_schema_version": 1, "has_current_config": has_current, "has_catalog": True, "selected_config_id": None, "is_dirty": has_current, "status": status, "current_config_name": str((current_config or {}).get("name", "")), "selected_config_name": "", "message": "no selected config"}
    sid = str(sid)
    if sid not in c["configs"]:
        raise ValueError("selected_config_id not found")
    sel = c["configs"][sid]
    if not has_current:
        return {"threshold_catalog_sync_schema_version": 1, "has_current_config": False, "has_catalog": True, "selected_config_id": sid, "is_dirty": False, "status": "synced", "current_config_name": "", "selected_config_name": str(sel.get("name", "")), "message": "no current config"}
    dirty = not configs_are_equivalent_for_catalog_sync(current_config, sel)
    return {"threshold_catalog_sync_schema_version": 1, "has_current_config": True, "has_catalog": True, "selected_config_id": sid, "is_dirty": dirty, "status": "dirty" if dirty else "synced", "current_config_name": str(current_config.get("name", "")), "selected_config_name": str(sel.get("name", "")), "message": "current differs from selected" if dirty else "current is synced"}
