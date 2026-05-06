import json

import numpy as np
import pytest

from iqa_dicom_adapter import (
    apply_modality_transform_for_iqa,
    calculate_dicom_iqa,
    get_dicom_pixel_array_for_iqa,
    prepare_dicom_iqa_input,
)


class FakeDicom:
    def __init__(self, pixel_array, **kwargs):
        self.pixel_array = np.asarray(pixel_array)
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_raw_dicom_pixel_mode_uses_bits_range_and_keeps_values() -> None:
    ds = FakeDicom(np.array([[0, 100], [200, 300]], dtype=np.uint16), BitsStored=14, PhotometricInterpretation="MONOCHROME2")
    arr, info = get_dicom_pixel_array_for_iqa(ds, input_mode="raw_dicom_pixel")
    assert info["data_range_policy"] == "bits"
    assert np.array_equal(arr, ds.pixel_array.astype(np.float64))

    prepared = prepare_dicom_iqa_input(ds, input_mode="raw_dicom_pixel")
    assert prepared["context"]["bits_stored"] == 14


def test_modality_lut_mode_applies_slope_intercept() -> None:
    ds = FakeDicom(np.array([[0, 1], [2, 3]], dtype=np.int16), RescaleSlope=2, RescaleIntercept=-1000, PhotometricInterpretation="MONOCHROME2")
    arr, info = get_dicom_pixel_array_for_iqa(ds, input_mode="modality_lut")
    assert np.array_equal(arr, apply_modality_transform_for_iqa(ds.pixel_array, 2, -1000))
    assert info["data_range_policy"] == "actual_union"


def test_windowed_display_mode_outputs_255_range() -> None:
    ds = FakeDicom(
        np.array([[0, 50], [100, 150]], dtype=np.uint16),
        WindowCenter=75,
        WindowWidth=150,
        PhotometricInterpretation="MONOCHROME2",
    )
    arr, info = get_dicom_pixel_array_for_iqa(ds, input_mode="windowed_display")
    assert float(np.min(arr)) >= 0.0
    assert float(np.max(arr)) <= 255.0
    assert info["data_range_policy"] == "explicit"
    assert info["data_range_used"] == 255.0


def test_monochrome1_warning_and_inversion_flag() -> None:
    ds = FakeDicom(np.array([[0, 10], [20, 30]], dtype=np.uint16), PhotometricInterpretation="MONOCHROME1")
    _arr, info = get_dicom_pixel_array_for_iqa(ds, input_mode="raw_dicom_pixel", options={"photometric_invert": False})
    assert "MONOCHROME1 without inversion option" in info["warnings"]

    _arr2, info2 = get_dicom_pixel_array_for_iqa(ds, input_mode="raw_dicom_pixel", options={"photometric_invert": True})
    assert info2["photometric_inversion_applied"] is True


def test_missing_bitsstored_fallback_warning() -> None:
    ds = FakeDicom(np.array([[0, 1]], dtype=np.uint16), PhotometricInterpretation="MONOCHROME2")
    _arr, info = get_dicom_pixel_array_for_iqa(ds, input_mode="raw_dicom_pixel")
    assert any("BitsStored missing" in item for item in info["warnings"])
    assert info["data_range_policy"] == "actual_union"


def test_shape_mismatch_raises() -> None:
    ref = FakeDicom(np.zeros((4, 4), dtype=np.uint16), BitsStored=12, PhotometricInterpretation="MONOCHROME2")
    tar = FakeDicom(np.zeros((5, 4), dtype=np.uint16), BitsStored=12, PhotometricInterpretation="MONOCHROME2")
    with pytest.raises(ValueError, match="shape mismatch"):
        calculate_dicom_iqa(ref, tar)


def test_roi_bbox_crop() -> None:
    ds = FakeDicom(np.arange(100, dtype=np.uint16).reshape(10, 10), BitsStored=12, PhotometricInterpretation="MONOCHROME2")
    prepared = prepare_dicom_iqa_input(ds, scope="roi", options={"bbox": (2, 3, 6, 8)})
    assert prepared["array"].shape == (5, 4)

    with pytest.raises(ValueError):
        prepare_dicom_iqa_input(ds, scope="roi", options={"bbox": (6, 8, 2, 3)})


def test_calculate_dicom_iqa_integration_and_jsonable() -> None:
    ref = FakeDicom(np.arange(16, dtype=np.uint16).reshape(4, 4), BitsStored=14, PhotometricInterpretation="MONOCHROME2")
    tar = FakeDicom(np.arange(16, dtype=np.uint16).reshape(4, 4), BitsStored=14, PhotometricInterpretation="MONOCHROME2")
    result = calculate_dicom_iqa(ref, tar, input_mode="raw_dicom_pixel", scope="full_image")

    payload = result.to_dict()
    assert set(payload.keys()) == {"metrics", "context", "warnings"}
    json.dumps(payload)
