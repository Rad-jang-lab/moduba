import json
import math

import numpy as np
import pytest

from iqa_metrics import build_iqa_context, calculate_iqa_metrics
from iqa_result_schema import IQAContext, IQAMetrics, IQAResult, to_jsonable


def test_iqa_result_contains_metrics_context_and_warnings() -> None:
    reference = np.zeros((4, 4), dtype=np.float64)
    target = np.zeros((4, 4), dtype=np.float64)

    result = calculate_iqa_metrics(
        reference,
        target,
        options={"data_range_policy": "actual_union", "scope": "full_image"},
    )
    payload = result.to_dict()

    assert set(payload) == {"metrics", "context", "warnings"}
    assert set(payload["metrics"]) == {"mse", "rmse", "psnr", "ssim", "hist_corr"}
    assert payload["context"]["input_mode"] == "array"
    assert payload["context"]["scope"] == "full_image"
    assert payload["context"]["image_shape"] == [4, 4]
    assert "full image scope may include background" in payload["warnings"]
    assert "data_range <= 0" in payload["warnings"]


def test_iqa_result_schema_is_json_serializable() -> None:
    context = build_iqa_context(
        np.zeros((2, 2)),
        np.zeros((2, 2)),
        input_mode="raw_dicom",
        scope="roi",
        data_range_policy="bits",
        data_range_used=16383.0,
        bits_stored=14,
        histogram_bins=64,
        histogram_range=(0.0, 16383.0),
        ssim_params={"k1": 0.01, "k2": 0.03},
    )
    result = IQAResult(
        metrics=IQAMetrics(mse=np.float64(0.0), rmse=np.float64(0.0), psnr=math.inf, ssim=1.0, hist_corr=1.0),
        context=context,
        warnings=["example"],
    )

    payload = result.to_dict()
    json.dumps(payload)
    assert payload["context"]["histogram_range"] == [0.0, 16383.0]
    assert payload["metrics"]["psnr"] == math.inf


def test_to_jsonable_converts_numpy_types() -> None:
    payload = to_jsonable({"value": np.float64(1.25), "shape": (np.int64(2), np.int64(3))})

    assert payload == {"value": 1.25, "shape": [2, 3]}
    json.dumps(payload)


def test_iqa_context_histogram_is_jsonable_and_preserved() -> None:
    result = IQAResult(
        metrics=IQAMetrics(mse=0.0, rmse=0.0, psnr=math.inf, ssim=1.0, hist_corr=1.0),
        context=IQAContext(
            input_mode="dicom",
            scope="roi",
            image_shape=(4, 4),
            data_range_policy="explicit",
            data_range_used=255.0,
            histogram={
                "histogram_bins": np.int64(64),
                "histogram_range": (0, 255),
                "histogram_corr": np.float64(0.9),
            },
            ssim_params={"histogram_bins": 32},
        ),
        warnings=[],
    )
    payload = result.to_dict()
    assert payload["context"]["histogram"]["histogram_bins"] == 64
    assert payload["context"]["histogram"]["histogram_range"] == [0, 255]
