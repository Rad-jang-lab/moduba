from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ORDER = ["snr", "cnr", "uniformity", "mtf"]


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


def build_analysis_export_snapshot(normalized_results: dict[str, dict[str, Any]], metadata: dict[str, Any] | None = None, generated_at: str | None = None) -> dict[str, Any]:
    if normalized_results is None:
        raise ValueError("normalized_results is None")
    ordered: dict[str, dict[str, Any]] = {}
    for key in _ordered_keys(normalized_results):
        payload = normalized_results.get(key)
        if payload is None:
            raise ValueError(f"normalized_results[{key!r}] is None")
        _ensure_finite(payload)
        ordered[key] = payload
    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "export_schema_version": 1,
        "generated_at": stamp,
        "metadata": dict(metadata or {}),
        "results": ordered,
    }


def export_analysis_results_to_json(normalized_results: dict[str, dict[str, Any]], path: str | Path | None = None, metadata: dict[str, Any] | None = None, generated_at: str | None = None) -> str:
    snapshot = build_analysis_export_snapshot(normalized_results, metadata=metadata, generated_at=generated_at)
    text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def export_analysis_results_to_csv(normalized_results: dict[str, dict[str, Any]], path: str | Path | None = None, metadata: dict[str, Any] | None = None, generated_at: str | None = None) -> str:
    snapshot = build_analysis_export_snapshot(normalized_results, metadata=metadata, generated_at=generated_at)
    output = io.StringIO()
    fieldnames = [
        "export_schema_version", "generated_at", "analysis_type", "status", "validity", "item_type", "item_name", "item_index", "value", "x", "y", "point_count", "warnings_json", "reason_codes_json", "roi_info_json", "source_payload_keys_json",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    for analysis_type in _ordered_keys(snapshot["results"]):
        item = snapshot["results"][analysis_type]
        common = {
            "export_schema_version": snapshot["export_schema_version"],
            "generated_at": snapshot["generated_at"],
            "analysis_type": analysis_type,
            "status": item.get("status", ""),
            "validity": item.get("validity", ""),
            "warnings_json": json.dumps(item.get("warnings") or [], ensure_ascii=False),
            "reason_codes_json": json.dumps(item.get("reason_codes") or [], ensure_ascii=False),
            "roi_info_json": json.dumps(item.get("roi_info") or {}, ensure_ascii=False),
            "source_payload_keys_json": json.dumps(item.get("source_payload_keys") or [], ensure_ascii=False),
        }
        writer.writerow({**common, "item_type": "result_summary", "item_name": "summary", "item_index": "", "value": "", "x": "", "y": "", "point_count": ""})
        for metric_name in sorted((item.get("metrics") or {}).keys()):
            writer.writerow({**common, "item_type": "metric", "item_name": metric_name, "item_index": "", "value": (item["metrics"][metric_name]), "x": "", "y": "", "point_count": ""})
        for curve_name in sorted((item.get("curves") or {}).keys()):
            curve = item["curves"][curve_name] or {}
            xs = list(curve.get("x") or [])
            ys = list(curve.get("y") or [])
            for idx, (x, y) in enumerate(zip(xs, ys)):
                writer.writerow({**common, "item_type": "curve_point", "item_name": curve_name, "item_index": idx, "value": "", "x": x, "y": y, "point_count": len(xs)})

    text = output.getvalue()
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text
