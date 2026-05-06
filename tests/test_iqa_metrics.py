import math

import numpy as np
import pytest

from iqa_metrics import (
    calculate_histogram_correlation,
    calculate_iqa_metrics,
    calculate_mse,
    calculate_psnr,
    calculate_rmse,
    calculate_ssim,
    resolve_iqa_data_range,
)


def test_identical_arrays_return_zero_error_inf_psnr_and_max_similarity() -> None:
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    result = calculate_iqa_metrics(
        arr,
        arr.copy(),
        options={"data_range_policy": "explicit", "data_range_used": 255.0, "scope": "roi"},
    )

    assert result.metrics.mse == 0.0
    assert result.metrics.rmse == 0.0
    assert math.isinf(result.metrics.psnr)
    assert result.metrics.ssim == pytest.approx(1.0)
    assert result.metrics.hist_corr == pytest.approx(1.0)


def test_known_mse_and_psnr_case() -> None:
    reference = np.zeros((4, 4), dtype=np.float64)
    target = np.zeros((4, 4), dtype=np.float64)
    target[0, 0] = 10.0

    mse = calculate_mse(reference, target)
    assert mse == pytest.approx(6.25)
    assert calculate_rmse(reference, target) == pytest.approx(2.5)
    assert calculate_psnr(mse, 255.0) == pytest.approx(40.1720, abs=1e-4)


def test_constant_offset_case() -> None:
    reference = np.zeros((4, 4), dtype=np.float64)
    target = np.ones((4, 4), dtype=np.float64) * 10.0

    mse = calculate_mse(reference, target)
    assert mse == pytest.approx(100.0)
    assert calculate_rmse(reference, target) == pytest.approx(10.0)
    assert calculate_psnr(mse, 255.0) == pytest.approx(28.1308, abs=1e-4)


def test_data_range_policies() -> None:
    reference = np.array([[0, 5], [10, 15]], dtype=np.float64)
    target = np.array([[2, 20], [-5, 8]], dtype=np.float64)

    assert resolve_iqa_data_range(reference, target, "bits", bits_stored=14)["data_range"] == 16383.0
    assert resolve_iqa_data_range(reference, target, "actual_peak")["data_range"] == 20.0
    assert resolve_iqa_data_range(reference, target, "actual_union")["data_range"] == 25.0
    assert resolve_iqa_data_range(reference, target, "explicit", explicit_data_range=123.0)["data_range"] == 123.0


def test_shape_mismatch_raises_value_error() -> None:
    with pytest.raises(ValueError, match="shape mismatch"):
        calculate_iqa_metrics(np.zeros((4, 4)), np.zeros((4, 5)))


def test_uint16_subtraction_is_float64_and_does_not_overflow() -> None:
    reference = np.array([[0]], dtype=np.uint16)
    target = np.array([[65535]], dtype=np.uint16)

    assert calculate_mse(reference, target) == pytest.approx(65535.0**2)


def test_constant_histogram_returns_nan_and_structured_warning() -> None:
    reference = np.zeros((4, 4), dtype=np.float64)
    target = np.ones((4, 4), dtype=np.float64)

    assert math.isnan(calculate_histogram_correlation(reference, target, bins=1, hist_range=(0.0, 1.0)))
    result = calculate_iqa_metrics(
        reference,
        target,
        options={
            "data_range_policy": "explicit",
            "data_range_used": 255.0,
            "histogram_bins": 1,
            "histogram_range": (0.0, 1.0),
            "scope": "roi",
        },
    )
    assert math.isnan(result.metrics.hist_corr)
    assert "constant histogram: correlation unavailable" in result.warnings


def test_calculate_ssim_identical_arrays_is_one() -> None:
    arr = np.arange(9, dtype=np.float64).reshape(3, 3)
    assert calculate_ssim(arr, arr.copy(), 255.0) == pytest.approx(1.0)
