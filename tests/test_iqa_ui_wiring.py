from types import SimpleNamespace

import numpy as np

from dicom_viewer import DicomViewer


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeDicom:
    def __init__(self, arr, **kwargs):
        self.pixel_array = np.asarray(arr)
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeLoader:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_decoded_file(self, key):
        return self.mapping[key], [self.mapping[key].pixel_array]


def _build_viewer():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.image_analysis_inputs = {
        "reference_image_id": DummyVar("ref"),
        "target_image_id": DummyVar("tar"),
        "scope_type": DummyVar("full_image"),
        "scope_roi_id": DummyVar(""),
    }
    viewer.image_analysis_results = {"image_formula": DummyVar(""), "image_result": DummyVar("")}
    viewer._image_analysis_comboboxes = {}
    viewer._image_analysis_option_maps = {"image": {}, "roi": {}}
    viewer._analysis_comboboxes = {}
    viewer._analysis_option_maps = {"roi": {}}
    viewer.analysis_last_run = {}
    viewer._resolve_image_analysis_selection = DicomViewer._resolve_image_analysis_selection.__get__(viewer, DicomViewer)
    viewer._get_selected_measurement_from_analysis = lambda *args, **kwargs: None
    return viewer


def test_scope_default_full_image():
    viewer = _build_viewer()
    assert viewer.image_analysis_inputs["scope_type"].get() == "full_image"


def test_metric_callback_uses_iqa_pipeline_and_populates_result_fields():
    viewer = _build_viewer()
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader(
        {
            "ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "tar": FakeDicom(arr.copy(), BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
        }
    )

    viewer.calculate_image_comparison_metrics()
    text = viewer.image_analysis_results["image_result"].get()
    formula = viewer.image_analysis_results["image_formula"].get()
    assert "[IQA Summary]" in text and "[Metrics]" in text and "SSIM:" in text and "HIST Corr:" in text
    assert "[Context]" in formula and "Input Mode:" in formula and "Data Range:" in formula


def test_warning_display_includes_bitsstored_missing():
    viewer = _build_viewer()
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader(
        {
            "ref": FakeDicom(arr, PhotometricInterpretation="MONOCHROME2"),
            "tar": FakeDicom(arr.copy(), PhotometricInterpretation="MONOCHROME2"),
        }
    )
    viewer.calculate_image_comparison_metrics()
    assert "Data range 기준을 자동으로 대체했습니다" in viewer.image_analysis_results["image_result"].get()


def test_missing_input_returns_explicit_invalid_state():
    viewer = _build_viewer()
    viewer.image_analysis_inputs["reference_image_id"].set("")
    viewer._load_analysis_image_array = lambda image_id: None
    viewer.calculate_image_comparison_metrics()
    assert "IQA 실행 불가 상태" in viewer.image_analysis_results["image_result"].get()
    assert "Status: invalid" in viewer.image_analysis_results["image_result"].get()
    assert "MSE: 계산 불가" in viewer.image_analysis_results["image_result"].get()


def test_export_record_is_attached_after_iqa_action():
    viewer = _build_viewer()
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader(
        {
            "ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "tar": FakeDicom(arr.copy(), BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
        }
    )
    viewer.calculate_image_comparison_metrics()
    assert "iqa" in viewer.analysis_last_run
    assert viewer.analysis_last_run["iqa"]["analysis_type"] == "iqa"
    assert viewer.analysis_last_run["iqa"]["context_input_mode"] == "dicom"
    assert viewer.analysis_last_run["iqa"]["context_scope"] == "full_image"
    assert getattr(viewer, "iqa_history", [])


def test_manual_reference_target_preserved_and_display_labels():
    viewer = _build_viewer()
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader(
        {
            "manual_ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "manual_tar": FakeDicom(arr.copy(), BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "tar": FakeDicom(arr.copy(), BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
        }
    )
    viewer.iqa_ui_state = SimpleNamespace(
        reference_id="manual_ref",
        target_id="manual_tar",
        reference_label="Reference A",
        target_label="Target B",
        input_mode="raw_dicom_pixel",
        scope="full_image",
        data_range_mode="auto",
        photometric_invert=False,
    )
    viewer.calculate_image_comparison_metrics()
    result_text = viewer.image_analysis_results["image_result"].get()
    assert "Reference: Reference A" in result_text
    assert "Target: Target B" in result_text


def test_same_image_warning_is_reported():
    viewer = _build_viewer()
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer.image_analysis_inputs["target_image_id"].set("ref")
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader({"ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2")})
    viewer.calculate_image_comparison_metrics()
    assert "Reference와 Target이 동일합니다. 검증용 비교로 사용할 수 있습니다." in viewer.image_analysis_results["image_formula"].get()


def test_clear_then_run_returns_missing_reason_and_no_stale_result():
    viewer = _build_viewer()
    viewer.image_analysis_inputs["reference_image_id"].set("")
    viewer.image_analysis_inputs["target_image_id"].set("")
    viewer.image_analysis_results["image_result"].set("old")
    viewer._load_analysis_image_array = lambda image_id: None
    viewer.calculate_image_comparison_metrics()
    assert "Status: invalid" in viewer.image_analysis_results["image_result"].get()
    assert "missing" in viewer.image_analysis_results["image_formula"].get()
    assert getattr(viewer, "iqa_history", [])[-1]["status"] == "invalid"


def test_selected_roi_without_roi_reports_missing_scope_roi():
    viewer = _build_viewer()
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer.image_analysis_inputs["scope_type"].set("roi")
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader(
        {
            "ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "tar": FakeDicom(arr.copy(), BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
        }
    )
    viewer.calculate_image_comparison_metrics()
    assert "ROI 범위가 선택되었지만 사용할 ROI가 없습니다." in viewer.image_analysis_results["image_formula"].get()


def test_roi_scope_runs_with_bbox_and_exports_roi_context():
    viewer = _build_viewer()
    arr = np.arange(64, dtype=np.uint16).reshape(8, 8)
    viewer.image_analysis_inputs["scope_type"].set("roi")
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader(
        {
            "ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "tar": FakeDicom(arr.copy(), BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
        }
    )
    roi = SimpleNamespace(id="roi_1", start=(1, 2), end=(5, 6), summary_text="Lung ROI")
    viewer._get_selected_measurement_from_analysis = lambda *args, **kwargs: roi
    viewer._find_measurement_by_id = lambda *args, **kwargs: roi
    viewer.image_analysis_inputs["scope_roi_id"].set("roi_1")
    viewer.calculate_image_comparison_metrics()
    assert "ROI: Lung ROI" in viewer.image_analysis_results["image_formula"].get()
    assert viewer.analysis_last_run["iqa"]["context_roi_id"] == "roi_1"


def test_roi_bbox_clipped_warning_and_invalid_stale_policy():
    viewer = _build_viewer()
    arr = np.arange(64, dtype=np.uint16).reshape(8, 8)
    viewer.image_analysis_inputs["scope_type"].set("roi")
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader(
        {
            "ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
            "tar": FakeDicom(arr.copy(), BitsStored=14, PhotometricInterpretation="MONOCHROME2"),
        }
    )
    roi = SimpleNamespace(id="roi_1", start=(-2, -2), end=(20, 20), summary_text="Wide ROI")
    viewer._get_selected_measurement_from_analysis = lambda *args, **kwargs: roi
    viewer._find_measurement_by_id = lambda *args, **kwargs: roi
    viewer.image_analysis_inputs["scope_roi_id"].set("roi_1")
    viewer.calculate_image_comparison_metrics()
    assert "공통 가능한 영역으로 보정되었습니다" in viewer.image_analysis_results["image_formula"].get()
    viewer._get_selected_measurement_from_analysis = lambda *args, **kwargs: None
    viewer._find_measurement_by_id = lambda *args, **kwargs: None
    viewer.calculate_image_comparison_metrics()
    assert viewer.analysis_last_run["iqa"]["status"] == "invalid"


def test_roi_resolver_priority_state_id_over_combobox():
    viewer = _build_viewer()
    arr = np.arange(64, dtype=np.uint16).reshape(8, 8)
    viewer.image_analysis_inputs["scope_type"].set("roi")
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader({"ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"), "tar": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2")})
    roi_a = SimpleNamespace(id="roi_a", start=(0, 0), end=(4, 4), summary_text="A")
    roi_b = SimpleNamespace(id="roi_b", start=(1, 1), end=(5, 5), summary_text="B")
    viewer.iqa_ui_state = SimpleNamespace(reference_id="", target_id="", reference_label="", target_label="", input_mode="raw_dicom_pixel", scope="roi", data_range_mode="auto", photometric_invert=False, selected_roi_id="roi_a", selected_roi_label="", selected_roi_source="", roi_bbox=None, roi_policy="none", roi_resolution_warnings=[])
    viewer.image_analysis_inputs["scope_roi_id"].set("roi_b")
    viewer._get_selected_measurement_from_analysis = lambda *args, **kwargs: roi_a
    viewer._find_measurement_by_id = lambda roi_id, **kwargs: roi_a if roi_id == "roi_a" else roi_b
    viewer.calculate_image_comparison_metrics()
    assert viewer.analysis_last_run["iqa"]["context_roi_id"] == "roi_a"


def test_unsupported_roi_shape_invalid_without_full_fallback():
    viewer = _build_viewer()
    arr = np.arange(64, dtype=np.uint16).reshape(8, 8)
    viewer.image_analysis_inputs["scope_type"].set("roi")
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader({"ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"), "tar": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2")})
    bad_roi = SimpleNamespace(id="roi_bad", start=None, end=None, summary_text="Bad")
    viewer._get_selected_measurement_from_analysis = lambda *args, **kwargs: bad_roi
    viewer._find_measurement_by_id = lambda *args, **kwargs: bad_roi
    viewer.image_analysis_inputs["scope_roi_id"].set("roi_bad")
    viewer.calculate_image_comparison_metrics()
    assert "unsupported_roi_shape" in viewer.image_analysis_results["image_formula"].get()
    assert viewer.analysis_last_run["iqa"]["status"] == "invalid"


def test_report_preview_is_compact_and_full_report_payload_is_preserved():
    viewer = _build_viewer()
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer._load_analysis_image_array = lambda image_id: arr
    viewer.dicom_loader = FakeLoader({"ref": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2"), "tar": FakeDicom(arr, BitsStored=14, PhotometricInterpretation="MONOCHROME2")})
    viewer.calculate_image_comparison_metrics()
    preview = viewer.analysis_last_run.get("iqa_report_text", "")
    report = viewer.analysis_last_run.get("iqa_report", {})
    assert "Reference:" in preview and "Target:" in preview and "Metrics:" in preview and "Interpretation:" in preview
    assert len([line for line in preview.splitlines() if line.strip()]) <= 10
    assert report.get("report_type") == "iqa_single"
    assert isinstance(report.get("metrics"), dict)
