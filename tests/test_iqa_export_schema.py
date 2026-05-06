import json
import math

import numpy as np

from iqa_dicom_adapter import calculate_dicom_iqa
from iqa_export import build_iqa_analysis_export_payload, flatten_iqa_result_for_export, iqa_result_to_analysis_record
from iqa_metrics import calculate_iqa_metrics


class FakeDicom:
    def __init__(self, pixel_array, **kwargs):
        self.pixel_array = np.asarray(pixel_array)
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_iqa_result_json_export_structure_preserved() -> None:
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    result = calculate_iqa_metrics(arr, arr.copy(), options={"data_range_policy": "explicit", "data_range_used": 255.0})
    payload = build_iqa_analysis_export_payload(result, source="unit")

    assert set(payload["json"].keys()) == {"metrics", "context", "warnings"}
    json.dumps(payload)


def test_iqa_result_flat_export_fields_present() -> None:
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    result = calculate_iqa_metrics(arr, arr.copy(), options={"data_range_policy": "explicit", "data_range_used": 255.0})
    flat = flatten_iqa_result_for_export(result, source="unit")

    assert flat["analysis_type"] == "iqa"
    assert "metric_mse" in flat
    assert "metric_rmse" in flat
    assert "metric_psnr" in flat
    assert "metric_ssim" in flat
    assert "metric_hist_corr" in flat
    assert "context_data_range_policy" in flat
    assert "context_data_range_used" in flat
    assert "warnings" in flat


def test_iqa_export_handles_nan_inf_policy() -> None:
    ref = np.zeros((4, 4), dtype=np.float64)
    tar = np.ones((4, 4), dtype=np.float64)
    result = calculate_iqa_metrics(
        ref,
        tar,
        options={"data_range_policy": "explicit", "data_range_used": 255.0, "histogram_bins": 1, "histogram_range": (0.0, 1.0)},
    )
    record = iqa_result_to_analysis_record(result)

    assert record["metric_psnr"] != "-inf"
    assert record["metric_hist_corr"] == "nan"

    identical = calculate_iqa_metrics(ref, ref.copy(), options={"data_range_policy": "explicit", "data_range_used": 255.0})
    record2 = iqa_result_to_analysis_record(identical)
    assert record2["metric_psnr"] == "inf"


def test_dicom_adapter_integration_export_contains_iqa_context() -> None:
    ref = FakeDicom(np.arange(16, dtype=np.uint16).reshape(4, 4), BitsStored=14, PhotometricInterpretation="MONOCHROME2")
    tar = FakeDicom(np.arange(16, dtype=np.uint16).reshape(4, 4), BitsStored=14, PhotometricInterpretation="MONOCHROME2")
    result = calculate_dicom_iqa(ref, tar, input_mode="raw_dicom_pixel")
    record = iqa_result_to_analysis_record(result, source="dicom")

    assert record["analysis_type"] == "iqa"
    assert record["context_input_mode"] == "dicom"
    json.dumps(record)


def test_flat_export_includes_roi_and_shape_fields() -> None:
    arr = np.arange(25, dtype=np.uint16).reshape(5, 5)
    result = calculate_iqa_metrics(arr, arr.copy(), options={"scope": "roi", "data_range_policy": "explicit", "data_range_used": 255.0})
    result.context.ssim_params.update(
        {
            "roi_id": "roi_1",
            "roi_label": "Lung ROI",
            "roi_source": "analysis_selector",
            "roi_bbox": (1, 1, 4, 4),
            "roi_policy": "bbox",
            "shape_alignment_policy": "none",
            "original_reference_shape": (5, 5),
            "original_target_shape": (5, 5),
            "compared_shape": (3, 3),
            "reference_label": "Ref",
            "target_label": "Tar",
        }
    )
    flat = flatten_iqa_result_for_export(result, source="unit")
    assert flat["context_scope"] == "roi"
    assert flat["context_roi_id"] == "roi_1"
    assert flat["context_roi_label"] == "Lung ROI"
    assert flat["context_roi_source"] == "analysis_selector"
    assert flat["context_roi_policy"] == "bbox"
    assert flat["context_shape_alignment_policy"] == "none"
    assert flat["reference_label"] == "Ref"
    assert flat["target_label"] == "Tar"
