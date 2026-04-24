from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
import numpy as np


@dataclass
class AnalysisUniformityResult:
    payload: dict[str, Any]
    preview_text: str
    result_text: str
    message_level: str | None = None
    message_text: str = ""
    history_row: dict[str, Any] | None = None


class AnalysisResultController:
    def evaluate_uniformity(
        self,
        roi_set: list[Any],
        source: str,
        formula_key: str,
        formulas: dict[str, dict[str, Any]],
        collect_factors: Callable[[Any], dict[str, Any]],
        get_frame_array: Callable[[int], np.ndarray],
        extract_roi_pixels: Callable[[np.ndarray, tuple[float, float], tuple[float, float], bool], tuple[np.ndarray, tuple[int, int, int, int]]],
    ) -> AnalysisUniformityResult:
        selected_formula = formulas.get(formula_key, formulas["max_min"])
        roi_ids = [measurement.id for measurement in roi_set]
        payload: dict[str, Any] = {
            "metric": "uniformity",
            "status": "missing",
            "reason": "",
            "preview_text": "",
            "result_text": "",
            "inputs": {
                "source": source,
                "roi_count": int(len(roi_set)),
                "roi_ids": roi_ids,
                "formula": formula_key,
                "formula_label": selected_formula["label"],
            },
            "factors": [collect_factors(measurement) for measurement in roi_set],
            "stats": {},
            "result": {
                "value": None,
                "formula": formula_key,
                "formula_label": selected_formula["label"],
            },
        }
        if not roi_set:
            payload["reason"] = "no ROI set"
            payload["preview_text"] = "Preview: ROI set not selected"
            payload["result_text"] = "Uniformity unavailable"
            return AnalysisUniformityResult(
                payload=payload,
                preview_text="ROI selection required",
                result_text="Uniformity unavailable",
                message_level="info",
                message_text="Uniformity 계산에 사용할 ROI 집합이 비어 있습니다.",
            )

        samples: list[np.ndarray] = []
        for measurement in roi_set:
            frame = get_frame_array(measurement.frame_index)
            roi_pixels, _ = extract_roi_pixels(frame, measurement.start, measurement.end, False)
            if roi_pixels.size > 0:
                samples.append(roi_pixels.reshape(-1))
        if not samples:
            payload["reason"] = "ROI pixels unavailable"
            payload["preview_text"] = "Preview: Selected ROIs are empty"
            payload["result_text"] = "Uniformity unavailable"
            return AnalysisUniformityResult(
                payload=payload,
                preview_text="Selected ROIs are empty",
                result_text="Uniformity unavailable",
                message_level="info",
                message_text="선택된 ROI에서 유효한 픽셀을 찾지 못했습니다.",
            )

        values = np.concatenate(samples)
        aggregate_stats = {
            "max": float(np.max(values)),
            "min": float(np.min(values)),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "pixel_count": int(values.size),
        }
        payload["stats"] = aggregate_stats
        uniformity_value = selected_formula["calculator"](aggregate_stats)
        preview_text = f"{len(roi_set)} ROIs selected"
        if uniformity_value is None:
            payload["status"] = "invalid"
            payload["reason"] = "invalid denominator"
            payload["preview_text"] = f"Preview: {preview_text}"
            payload["result_text"] = "Uniformity unavailable"
            return AnalysisUniformityResult(
                payload=payload,
                preview_text=preview_text,
                result_text="Uniformity unavailable",
                message_level="warning",
                message_text="선택한 공식에서 분모가 0 또는 음수입니다.",
            )

        payload["status"] = "success"
        payload["preview_text"] = f"Preview: {preview_text}"
        payload["result_text"] = f"Uniformity: {uniformity_value:.2f}"
        payload["result"] = {
            "value": float(uniformity_value),
            "formula": formula_key,
            "formula_label": selected_formula["label"],
        }
        return AnalysisUniformityResult(
            payload=payload,
            preview_text=preview_text,
            result_text=f"Uniformity: {uniformity_value:.2f}",
            history_row={
                "metric_name": "UNIFORMITY",
                "item_name": "Uniformity",
                "stats": aggregate_stats,
                "result_value": float(uniformity_value),
                "unit": "%",
                "note": selected_formula["label"],
                "extra": {"formula": formula_key, "roi_ids": roi_ids, "source": source},
            },
        )


class HistoryController:
    def build_flat_history_view(self, grouped_rows: list[dict[str, Any]], search_text: str = "") -> list[dict[str, Any]]:
        query = search_text.strip().lower()
        filtered_rows: list[dict[str, Any]] = []
        for row in grouped_rows:
            haystack = " ".join(
                [
                    str(row.get("image_name", "")),
                    str(row.get("target_name", "")),
                    str(row.get("measurement_type", "")),
                    str(row.get("metric", "")),
                    str(row.get("note", "")),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            enriched = dict(row)
            enriched["row_type"] = "result"
            primary_entry = enriched.get("primary_entry")
            if primary_entry is not None:
                enriched["study_id"] = str(getattr(primary_entry, "study_id", "") or "")
                enriched["group_id"] = str(getattr(primary_entry, "group_id", "") or "")
            filtered_rows.append(enriched)
        return filtered_rows


class SessionController:
    def build_serialize_payload(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": context["schema_version"],
            "created_at": datetime.utcnow().isoformat(),
            "app": "moduba",
            "source_image_path": context["source_image_path"],
            "frame_index": int(context["frame_index"]),
            "display": dict(context["display"]),
            "roi_list": list(context["roi_list"]),
            "line_list": list(context["line_list"]),
            "analysis_options": dict(context["analysis_options"]),
            "results_history": list(context["results_history"]),
            "analysis_groups": list(context["analysis_groups"]),
            "study_sessions": list(context["study_sessions"]),
            "active_study_id": str(context["active_study_id"]),
            "active_group_id": str(context["active_group_id"]),
            "compare_state": dict(context["compare_state"]),
            "store_snapshot_timestamp": context["store_snapshot"].get("snapshot_timestamp"),
            "store_snapshot": context["store_snapshot"],
        }


class ReportExportController:
    def filter_selected_rows(self, history_rows: list[dict[str, Any]], selected_indices: set[int]) -> list[dict[str, Any]]:
        if not selected_indices:
            return history_rows
        return [
            row for row in history_rows
            if selected_indices.intersection(set(row.get("store_indices", [])))
        ]
