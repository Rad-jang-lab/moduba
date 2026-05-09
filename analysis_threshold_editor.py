from __future__ import annotations

import math
from typing import Any

from analysis_thresholds import validate_threshold_config

_REQUIRED_RULE_FIELDS = ("rule_id", "analysis_type", "metric", "operator", "threshold", "severity", "label")


def _validated_config_copy(config: dict[str, Any]) -> dict[str, Any]:
    c = {**dict(config)}
    c["rules"] = [dict(r) for r in (config.get("rules") or [])]
    return validate_threshold_config(c)


def _rule_index_by_id(rules: list[dict[str, Any]], rule_id: str) -> int:
    for idx, rule in enumerate(rules):
        if str(rule.get("rule_id")) == str(rule_id):
            return idx
    raise ValueError("rule_id not found")


def validate_threshold_rule(rule: dict[str, Any]) -> dict[str, Any]:
    if rule is None:
        raise ValueError("rule is None")
    normalized = dict(rule)
    for key in _REQUIRED_RULE_FIELDS:
        if key not in normalized:
            raise ValueError(f"missing {key}")
    if str(normalized.get("operator")) not in {">", ">=", "<", "<=", "==", "!="}:
        raise ValueError("unsupported operator")
    if str(normalized.get("severity")) not in {"fail", "warn"}:
        raise ValueError("unsupported severity")
    if not math.isfinite(float(normalized.get("threshold"))):
        raise ValueError("threshold must be finite")
    return normalized


def add_threshold_rule(config: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    c = _validated_config_copy(config)
    r = validate_threshold_rule(rule)
    if any(str(x.get("rule_id")) == str(r["rule_id"]) for x in c["rules"]):
        raise ValueError("duplicate rule_id")
    c["rules"].append(r)
    return validate_threshold_config(c)


def update_threshold_rule(config: dict[str, Any], rule_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    c = _validated_config_copy(config)
    idx = _rule_index_by_id(c["rules"], rule_id)
    merged = {**c["rules"][idx], **dict(updates or {})}
    if str(merged.get("rule_id")) != str(rule_id):
        if any(str(x.get("rule_id")) == str(merged.get("rule_id")) for i, x in enumerate(c["rules"]) if i != idx):
            raise ValueError("duplicate rule_id")
    c["rules"][idx] = validate_threshold_rule(merged)
    return validate_threshold_config(c)


def remove_threshold_rule(config: dict[str, Any], rule_id: str) -> dict[str, Any]:
    c = _validated_config_copy(config)
    idx = _rule_index_by_id(c["rules"], rule_id)
    c["rules"].pop(idx)
    return validate_threshold_config(c)


def reorder_threshold_rules(config: dict[str, Any], rule_ids: list[str]) -> dict[str, Any]:
    c = _validated_config_copy(config)
    existing_ids = [str(r.get("rule_id")) for r in c["rules"]]
    requested_ids = [str(x) for x in list(rule_ids)]
    if len(existing_ids) != len(requested_ids) or set(existing_ids) != set(requested_ids):
        raise ValueError("rule_ids must exactly match existing rules")
    by_id = {str(r.get("rule_id")): dict(r) for r in c["rules"]}
    c["rules"] = [by_id[rid] for rid in requested_ids]
    return validate_threshold_config(c)


def duplicate_threshold_rule(config: dict[str, Any], source_rule_id: str, new_rule_id: str) -> dict[str, Any]:
    c = _validated_config_copy(config)
    if any(str(r.get("rule_id")) == str(new_rule_id) for r in c["rules"]):
        raise ValueError("duplicate rule_id")
    idx = _rule_index_by_id(c["rules"], source_rule_id)
    duplicated = dict(c["rules"][idx])
    duplicated["rule_id"] = str(new_rule_id)
    c["rules"].append(validate_threshold_rule(duplicated))
    return validate_threshold_config(c)


def get_threshold_rule(config: dict[str, Any], rule_id: str) -> dict[str, Any]:
    c = _validated_config_copy(config)
    idx = _rule_index_by_id(c["rules"], rule_id)
    return dict(c["rules"][idx])


def list_threshold_rules(config: dict[str, Any]) -> list[dict[str, Any]]:
    c = _validated_config_copy(config)
    return [dict(r) for r in c["rules"]]
