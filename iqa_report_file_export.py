from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from iqa_result_schema import to_jsonable


def ensure_file_suffix(path: str | Path, suffix: str) -> Path:
    p = Path(path)
    if not p.suffix:
        return p.with_suffix(suffix)
    return p


def sanitize_export_base_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in (name or "iqa_export"))
    return cleaned.strip("._") or "iqa_export"


def _ensure_parent_exists(path: Path) -> None:
    if not path.parent.exists():
        raise ValueError(f"parent directory does not exist: {path.parent}")


def _result(path: Path, fmt: str, bytes_written: int) -> dict[str, Any]:
    return {"status": "success", "path": str(path), "format": fmt, "bytes_written": int(bytes_written)}


def write_text_payload(path: str | Path, text: str) -> dict[str, Any]:
    out = ensure_file_suffix(path, ".txt")
    _ensure_parent_exists(out)
    data = str(text)
    out.write_text(data, encoding="utf-8")
    return _result(out, "txt", len(data.encode("utf-8")))


def write_iqa_report_txt(path: str | Path, txt_payload: str) -> dict[str, Any]:
    return write_text_payload(path, txt_payload)


def write_iqa_report_json(path: str | Path, json_payload: Mapping[str, Any], indent: int = 2) -> dict[str, Any]:
    out = ensure_file_suffix(path, ".json")
    _ensure_parent_exists(out)
    safe_payload = to_jsonable(dict(json_payload))
    data = json.dumps(safe_payload, ensure_ascii=False, indent=indent)
    out.write_text(data, encoding="utf-8")
    return _result(out, "json", len(data.encode("utf-8")))


def _csv_safe_value(value: Any) -> Any:
    safe = to_jsonable(value)
    if isinstance(safe, (dict, list, tuple)):
        return json.dumps(safe, ensure_ascii=False, sort_keys=True)
    return safe


def write_iqa_report_csv(path: str | Path, csv_rows: list[Mapping[str, Any]], fieldnames: Iterable[str] | None = None) -> dict[str, Any]:
    if not csv_rows:
        raise ValueError("csv_rows must not be empty")
    out = ensure_file_suffix(path, ".csv")
    _ensure_parent_exists(out)
    if fieldnames is None:
        ordered: list[str] = []
        seen = set()
        for row in csv_rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    ordered.append(str(key))
        fieldnames = ordered
    fieldnames = [str(f) for f in fieldnames]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow({k: _csv_safe_value(v) for k, v in row.items()})
    return _result(out, "csv", out.stat().st_size)


def write_iqa_report_export_bundle(bundle: Mapping[str, Any], output_dir: str | Path, base_name: str = "iqa_report", formats: tuple[str, ...] = ("txt", "json", "csv")) -> dict[str, Any]:
    out_dir = Path(output_dir)
    if not out_dir.exists():
        raise ValueError(f"output_dir does not exist: {out_dir}")
    name = sanitize_export_base_name(base_name)
    results = []
    for fmt in formats:
        if fmt == "txt":
            results.append(write_iqa_report_txt(out_dir / f"{name}.txt", str(bundle.get("txt", ""))))
        elif fmt == "json":
            payload = bundle.get("json", {})
            if not isinstance(payload, Mapping):
                raise ValueError("bundle['json'] must be a mapping")
            results.append(write_iqa_report_json(out_dir / f"{name}.json", payload))
        elif fmt == "csv":
            rows = bundle.get("csv_rows", [])
            if not isinstance(rows, list):
                raise ValueError("bundle['csv_rows'] must be a list")
            results.append(write_iqa_report_csv(out_dir / f"{name}.csv", rows))
        else:
            raise ValueError(f"unsupported export format: {fmt}")
    return {"status": "success", "output_dir": str(out_dir), "files": results}


def write_iqa_history_export_bundle(bundle: Mapping[str, Any], output_dir: str | Path, base_name: str = "iqa_history", formats: tuple[str, ...] = ("txt", "json", "csv")) -> dict[str, Any]:
    return write_iqa_report_export_bundle(bundle, output_dir=output_dir, base_name=base_name, formats=formats)
