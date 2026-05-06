import json
import math

import numpy as np

from iqa_export import iqa_result_to_analysis_record
from iqa_history import (
    append_iqa_history,
    build_iqa_history_entry,
    get_latest_iqa_history,
    iqa_history_entry_to_jsonable,
)
from iqa_metrics import calculate_iqa_metrics


class _SelectionState:
    reference_id = "ref_1"
    reference_label = "Ref 1"
    target_id = "tar_1"
    target_label = "Tar 1"
    input_mode = "raw_dicom_pixel"
    scope = "roi"
    data_range_mode = "auto"
    photometric_invert = False


def _result():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    res = calculate_iqa_metrics(arr, arr.copy(), options={"scope": "roi", "data_range_policy": "explicit", "data_range_used": 255.0})
    res.context.ssim_params.update({"roi_id": "roi_1", "roi_label": "Lung ROI", "roi_bbox": (0, 0, 3, 3), "roi_policy": "bbox"})
    res.context.histogram.update({"histogram_bins": 64, "histogram_range": (0, 255), "histogram_corr": 1.0})
    return res


def test_successful_history_entry_preserves_payloads() -> None:
    res = _result()
    export = iqa_result_to_analysis_record(res, source="test")
    entry = build_iqa_history_entry(res, selection_state=_SelectionState(), export_record=export, display_model={"summary": "ok"}, status="success")
    assert entry.status == "success"
    assert entry.metrics["mse"] == 0.0
    assert entry.context["scope"] == "roi"
    assert entry.histogram["histogram_bins"] == 64
    assert entry.roi_id == "roi_1"
    assert entry.export_record["analysis_type"] == "iqa"


def test_invalid_history_entry_has_no_stale_metrics() -> None:
    entry = build_iqa_history_entry(
        None,
        selection_state=_SelectionState(),
        export_record={"analysis_type": "iqa", "status": "invalid"},
        status="invalid",
        invalid_reason="missing_target",
    )
    assert entry.status == "invalid"
    assert entry.invalid_reason == "missing_target"
    assert entry.metrics == {}


def test_history_json_serializable_and_collection_helpers() -> None:
    res = _result()
    entry = build_iqa_history_entry(res, selection_state=_SelectionState(), status="success")
    payload = iqa_history_entry_to_jsonable(entry)
    json.dumps(payload)
    hist = []
    append_iqa_history(hist, payload, max_items=2)
    append_iqa_history(hist, payload, max_items=2)
    append_iqa_history(hist, payload, max_items=2)
    assert len(hist) == 2
    assert get_latest_iqa_history(hist) is not None


def test_history_json_handles_inf_nan() -> None:
    arr = np.zeros((4, 4), dtype=np.float64)
    res = calculate_iqa_metrics(arr, arr, options={"data_range_policy": "explicit", "data_range_used": 255.0})
    res.context.histogram["histogram_corr"] = np.float64(math.nan)
    payload = iqa_history_entry_to_jsonable(build_iqa_history_entry(res, selection_state=_SelectionState(), status="success"))
    json.dumps(payload)
