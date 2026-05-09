from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

_OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
_SEVERITIES = {"fail", "warn"}


def validate_threshold_config(config: dict[str, Any]) -> dict[str, Any]:
    if config is None:
        raise ValueError("config is None")
    if config.get("threshold_schema_version") != 1:
        raise ValueError("unsupported threshold schema version")
    rules = config.get("rules")
    if not isinstance(rules, list):
        raise ValueError("rules must be list")
    ids: set[str] = set()
    for rule in rules:
        for key in ("rule_id", "analysis_type", "metric", "operator", "threshold", "severity"):
            if key not in rule:
                raise ValueError(f"missing {key}")
        if rule["rule_id"] in ids:
            raise ValueError("duplicate rule_id")
        ids.add(rule["rule_id"])
        if rule["operator"] not in _OPS:
            raise ValueError("unsupported operator")
        if rule["severity"] not in _SEVERITIES:
            raise ValueError("unsupported severity")
        if not math.isfinite(float(rule["threshold"])):
            raise ValueError("threshold must be finite")
    return config


def evaluate_analysis_thresholds(normalized_results: dict[str, dict[str, Any]], threshold_config: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    if normalized_results is None:
        raise ValueError("normalized_results is None")
    config = validate_threshold_config(threshold_config)
    results = []
    for rule in config.get("rules", []):
        item = normalized_results.get(rule["analysis_type"])
        status = "pass"
        reason = ""
        actual: Any = None
        if item is None:
            status, reason = "not_evaluated", "analysis_missing"
        elif str(item.get("validity", "")) != "valid":
            status, reason = "not_evaluated", "analysis_invalid"
        else:
            metrics = item.get("metrics") or {}
            if rule["metric"] not in metrics:
                status, reason = "not_evaluated", "metric_missing"
            else:
                actual = metrics[rule["metric"]]
                if not math.isfinite(float(actual)):
                    status, reason = "not_evaluated", "metric_non_finite"
                else:
                    ok = _OPS[rule["operator"]](float(actual), float(rule["threshold"]))
                    if not ok:
                        status = "fail" if rule["severity"] == "fail" else "warn"
                        reason = "threshold_not_met"
        results.append({**rule, "actual_value": actual, "status": status, "reason": reason})

    evaluation = {
        "threshold_evaluation_schema_version": 1,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "config_name": str(config.get("name", "")),
        "overall_status": "not_evaluated",
        "summary": {},
        "results": results,
    }
    evaluation["summary"] = summarize_threshold_evaluation(evaluation)
    statuses = [r["status"] for r in results]
    if any(s == "fail" for s in statuses):
        evaluation["overall_status"] = "fail"
    elif any(s == "warn" for s in statuses):
        evaluation["overall_status"] = "warn"
    elif statuses and all(s == "pass" for s in statuses):
        evaluation["overall_status"] = "pass"
    else:
        evaluation["overall_status"] = "not_evaluated"
    return evaluation


def summarize_threshold_evaluation(evaluation: dict[str, Any]) -> dict[str, int]:
    statuses = [r.get("status") for r in evaluation.get("results", [])]
    return {
        "rule_count": len(statuses),
        "passed_count": sum(1 for s in statuses if s == "pass"),
        "warning_count": sum(1 for s in statuses if s == "warn"),
        "failed_count": sum(1 for s in statuses if s == "fail"),
        "not_evaluated_count": sum(1 for s in statuses if s == "not_evaluated"),
    }


def render_threshold_evaluation_text(evaluation: dict[str, Any]) -> str:
    lines = [f"Config: {evaluation.get('config_name','')}", f"Generated At: {evaluation.get('generated_at','')}", f"Overall: {evaluation.get('overall_status','')}", f"Summary: {evaluation.get('summary',{})}"]
    for r in evaluation.get("results", []):
        lines.append(f"- {r.get('rule_id')}: {r.get('status')} | actual={r.get('actual_value')} | {r.get('metric')} {r.get('operator')} {r.get('threshold')} | reason={r.get('reason','')}")
    return "\n".join(lines) + "\n"
