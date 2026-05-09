from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis_report_model import build_analysis_report_model
from analysis_result_export import build_analysis_export_snapshot

_SCHEMA_VERSION = 1


def build_analysis_history_record(normalized_results: dict[str, dict[str, Any]], metadata: dict[str, Any] | None = None, generated_at: str | None = None, record_id: str | None = None, threshold_evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    if normalized_results is None:
        raise ValueError("normalized_results is None")
    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    rid = record_id or f"hist_{uuid.uuid4().hex}"
    export_snapshot = build_analysis_export_snapshot(normalized_results, metadata=metadata, generated_at=stamp)
    report_model = build_analysis_report_model(normalized_results, metadata=metadata, generated_at=stamp, threshold_evaluation=threshold_evaluation)
    record = {
        "history_schema_version": _SCHEMA_VERSION,
        "record_id": rid,
        "generated_at": stamp,
        "metadata": dict(metadata or {}),
        "summary": dict(report_model.get("summary") or {}),
        "export_snapshot": export_snapshot,
    }
    if threshold_evaluation is not None:
        if threshold_evaluation.get("threshold_evaluation_schema_version") != 1:
            raise ValueError("invalid threshold_evaluation schema")
        record["threshold_evaluation"] = dict(threshold_evaluation)
    return record


def append_analysis_history_record(history_path: str | Path, record: dict[str, Any]) -> None:
    path = Path(history_path)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_analysis_history_records(history_path: str | Path) -> list[dict[str, Any]]:
    path = Path(history_path)
    if not path.exists() or path.read_text(encoding="utf-8") == "":
        return []
    out: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSON line at {idx}") from exc
        if item.get("history_schema_version") != _SCHEMA_VERSION:
            raise ValueError(f"unsupported history schema version at line {idx}")
        out.append(item)
    return out


def filter_analysis_history_records(records: list[dict[str, Any]], analysis_type: str | None = None, validity: str | None = None) -> list[dict[str, Any]]:
    out = []
    for r in records:
        summary = dict(r.get("summary") or {})
        if analysis_type and analysis_type not in list(summary.get("analysis_types") or []):
            continue
        if validity:
            results = ((r.get("export_snapshot") or {}).get("results") or {})
            if not any(str(v.get("validity", "")) == validity for v in results.values() if isinstance(v, dict)):
                continue
        out.append(r)
    return out


def export_analysis_history_to_json(records: list[dict[str, Any]], path: str | Path | None = None) -> str:
    text = json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text
