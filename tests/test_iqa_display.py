import math

import numpy as np

from iqa_display import (
    LABEL_MAP,
    WARNING_MESSAGE_MAP,
    build_iqa_context_rows,
    build_iqa_display_model,
    build_iqa_metric_rows,
    build_iqa_summary,
    build_iqa_warning_rows,
    format_iqa_display_text,
)
from iqa_metrics import calculate_iqa_metrics


def _result(ref, tar, **opts):
    return calculate_iqa_metrics(ref, tar, options=opts)


def test_display_model_structure():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    model = build_iqa_display_model(_result(arr, arr, data_range_policy="explicit", data_range_used=255.0))
    assert {"title", "summary", "metric_rows", "context_rows", "warning_rows"}.issubset(model)


def test_metric_formatting_psnr_ssim_hist_and_inf_nan():
    ref = np.zeros((4, 4), dtype=np.float64)
    tar = np.zeros((4, 4), dtype=np.float64)
    rows = build_iqa_metric_rows(_result(ref, tar, data_range_policy="explicit", data_range_used=255.0))
    psnr = next(item for item in rows if item["label"] == "PSNR")
    assert psnr["unit"] == "dB"
    assert psnr["value"] == "inf"

    tar2 = np.ones((4, 4), dtype=np.float64)
    res2 = _result(ref, tar2, data_range_policy="explicit", data_range_used=255.0, histogram_bins=1, histogram_range=(0.0, 1.0))
    hist_row = next(item for item in build_iqa_metric_rows(res2) if item["label"] == "HIST corr")
    assert hist_row["value"] == "nan"


def test_context_rows_include_required_fields():
    arr = np.arange(9, dtype=np.float64).reshape(3, 3)
    rows = build_iqa_context_rows(_result(arr, arr, data_range_policy="actual_union"))
    labels = {r["label"] for r in rows}
    assert {"Input Mode", "Scope", "Data Range Policy", "Data Range Used", "Bits Stored", "Photometric", "Image Shape"}.issubset(labels)


def test_warning_severity_caution_mapping():
    arr = np.arange(9, dtype=np.float64).reshape(3, 3)
    res = _result(arr, arr, data_range_policy="bits")
    # bits_stored missing triggers warning in resolver path
    warning_rows = build_iqa_warning_rows(res)
    assert all(row["severity"] in {"info", "caution", "error"} for row in warning_rows)


def test_summary_interpretation_high_ssim_low_hist():
    ref = np.zeros((4, 4), dtype=np.float64)
    tar = np.zeros((4, 4), dtype=np.float64)
    tar[::2, ::2] = 1
    res = _result(ref, tar, data_range_policy="explicit", data_range_used=255.0, histogram_bins=2, histogram_range=(0, 1))
    summary = build_iqa_summary(res)
    assert "구조" in summary


def test_no_warning_state_message():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    res = _result(arr, arr, data_range_policy="explicit", data_range_used=255.0, scope="roi")
    warning_rows = build_iqa_warning_rows(res)
    if not res.warnings:
        assert warning_rows[0]["message"] in {"주의 사항 없음", "Warnings: None"}


def test_format_display_text_contains_metrics_context_warning():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    model = build_iqa_display_model(_result(arr, arr, data_range_policy="explicit", data_range_used=255.0, scope="roi"))
    result_text, context_text = format_iqa_display_text(model)
    assert "[IQA Summary]" in result_text and "[Metrics]" in result_text and "[Histogram]" in result_text
    assert "[Context]" in context_text and "[Warnings]" in context_text


def test_label_and_warning_mapping_user_friendly():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    res = _result(arr, arr, input_mode="raw_dicom_pixel", scope="roi", data_range_policy="actual_union")
    from iqa_result_schema import IQAResult
    rows = build_iqa_context_rows(res)
    res2 = IQAResult(metrics=res.metrics, context=res.context, warnings=["roi_bbox_clipped_to_image_bounds", "missing_scope_roi"])
    lookup = {r["label"]: r["value"] for r in rows}
    assert lookup["Input Mode"] == "Raw DICOM Pixel"
    assert lookup["Scope"] == "Selected ROI"
    assert lookup["Data Range Policy"] == "Actual Union"
    warnings = [r["message"] for r in build_iqa_warning_rows(res2)]
    assert WARNING_MESSAGE_MAP["missing_scope_roi"] in warnings
    assert any("공통 가능한 영역" in m for m in warnings)
    assert any("ROI 범위가 선택되었지만 사용할 ROI가 없습니다." in m for m in warnings)


def test_label_mapping_covers_all_usability_labels():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    for input_mode, expected_mode in [
        ("raw_dicom_pixel", "Raw DICOM Pixel"),
        ("modality_lut", "Modality LUT"),
        ("windowed_display", "Windowed Display"),
    ]:
        res = _result(arr, arr, input_mode=input_mode, scope="full_image", data_range_policy="bits")
        rows = {r["label"]: r["value"] for r in build_iqa_context_rows(res)}
        assert rows["Input Mode"] == expected_mode
    for scope, expected_scope in [("full_image", "Full Image"), ("roi", "Selected ROI")]:
        res = _result(arr, arr, input_mode="raw_dicom_pixel", scope=scope, data_range_policy="bits")
        rows = {r["label"]: r["value"] for r in build_iqa_context_rows(res)}
        assert rows["Scope"] == expected_scope
    for policy, expected_policy in [("actual_union", "Actual Union"), ("bits", "Bits Stored")]:
        res = _result(arr, arr, input_mode="raw_dicom_pixel", scope="full_image", data_range_policy=policy)
        rows = {r["label"]: r["value"] for r in build_iqa_context_rows(res)}
        assert rows["Data Range Policy"] == expected_policy
    assert LABEL_MAP["auto"] == "Auto"


def test_warning_mapping_for_requested_codes():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    res = _result(arr, arr)
    from iqa_result_schema import IQAResult
    warning_codes = [
        "roi_bbox_clipped_to_image_bounds",
        "invalid_roi_bbox_after_clip",
        "missing_scope_roi",
        "missing_bits_stored",
        "monochrome1_without_inversion",
        "full_image_background",
    ]
    rows = build_iqa_warning_rows(IQAResult(metrics=res.metrics, context=res.context, warnings=warning_codes))
    messages = [r["message"] for r in rows]
    for code in warning_codes:
        assert WARNING_MESSAGE_MAP[code] in messages


def test_warning_rows_are_deduped_and_sorted_by_severity():
    arr = np.arange(16, dtype=np.float64).reshape(4, 4)
    res = _result(arr, arr)
    from iqa_result_schema import IQAResult
    res2 = IQAResult(metrics=res.metrics, context=res.context, warnings=["missing_target", "missing_target", "full_image_background"])
    rows = build_iqa_warning_rows(res2)
    assert rows[0]["severity"] == "error"
    assert len(rows) == 2
