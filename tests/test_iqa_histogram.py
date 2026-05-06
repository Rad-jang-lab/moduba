import numpy as np

from iqa_histogram import (
    build_histogram_preview_model,
    calculate_histogram_data,
    format_histogram_preview_text,
    resolve_histogram_range,
)
from iqa_metrics import calculate_iqa_metrics
from iqa_export import flatten_iqa_result_for_export
from iqa_display import build_iqa_context_rows


def test_histogram_preview_model_structure() -> None:
    ref = np.arange(16, dtype=np.float64).reshape(4, 4)
    tar = ref.copy()
    hist = calculate_histogram_data(ref, tar, bins=8, hist_range=(0, 15))
    model = build_histogram_preview_model(hist, reference_label="Ref", target_label="Tar")
    assert {"title", "bins", "hist_range", "normalized", "hist_corr", "distribution_hint", "series"}.issubset(model.keys())


def test_histogram_preview_text_contains_corr_range_bins() -> None:
    ref = np.array([0, 1, 2, 3], dtype=np.float64)
    tar = np.array([1, 2, 3, 4], dtype=np.float64)
    hist = calculate_histogram_data(ref, tar, bins=4, hist_range=(0, 4))
    text = format_histogram_preview_text(build_histogram_preview_model(hist))
    assert "Corr:" in text and "Range:" in text and "Bins:" in text and "분포 차이" in text


def test_root_histogram_context_preferred_and_ssim_fallback_preserved() -> None:
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    res = calculate_iqa_metrics(arr, arr.copy(), options={"data_range_policy": "explicit", "data_range_used": 255.0})
    res.context.ssim_params["histogram_bins"] = 32
    res.context.histogram["histogram_bins"] = 64
    rows = build_iqa_context_rows(res)
    val = next(row["value"] for row in rows if row["label"] == "Histogram Bins")
    assert val == 64
    res.context.histogram.clear()
    rows2 = build_iqa_context_rows(res)
    val2 = next(row["value"] for row in rows2 if row["label"] == "Histogram Bins")
    assert val2 == 32


def test_export_histogram_fields_include_summary() -> None:
    arr = np.arange(25, dtype=np.float64).reshape(5, 5)
    res = calculate_iqa_metrics(arr, arr.copy(), options={"scope": "roi", "data_range_policy": "explicit", "data_range_used": 255.0})
    res.context.histogram.update(
        {
            "histogram_bins": 64,
            "histogram_range": (0, 255),
            "histogram_normalized": True,
            "histogram_range_policy": "auto",
            "histogram_corr": 0.8,
            "histogram_distribution_hint": "aligned_distribution",
            "histogram_reference_peak_bin": 4,
            "histogram_target_peak_bin": 4,
            "histogram_summary": "두 영상의 밝기 분포는 전반적으로 유사합니다.",
        }
    )
    flat = flatten_iqa_result_for_export(res)
    assert flat["context_histogram_bins"] == 64
    assert flat["context_histogram_summary"]


def test_range_policy_data_range() -> None:
    ref = np.array([1, 2], dtype=np.float64)
    tar = np.array([3, 4], dtype=np.float64)
    hist_range, _warnings = resolve_histogram_range(ref, tar, policy="data_range", data_range=255)
    assert hist_range == (0.0, 255.0)
