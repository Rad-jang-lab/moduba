import numpy as np
from dicom_viewer import DicomViewer


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _build_viewer(reference, target, scope="full"):
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.image_analysis_inputs = {
        "reference_image_id": DummyVar("ref"),
        "target_image_id": DummyVar("tar"),
        "scope_type": DummyVar(scope),
        "scope_roi_id": DummyVar(""),
    }
    viewer.image_analysis_results = {
        "image_formula": DummyVar(""),
        "image_result": DummyVar(""),
    }
    viewer._image_analysis_comboboxes = {}
    viewer._image_analysis_option_maps = {"image": {}, "roi": {}}
    viewer._resolve_image_analysis_selection = DicomViewer._resolve_image_analysis_selection.__get__(viewer, DicomViewer)
    viewer._load_analysis_image_array = lambda image_id: reference if image_id == "ref" else target
    viewer.current_file_index = 0
    viewer.dicom_datasets = []
    return viewer


def test_identical_image_has_zero_mse_and_inf_psnr():
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    viewer = _build_viewer(arr, arr.copy())
    viewer.calculate_image_comparison_metrics()
    result = viewer.image_analysis_results["image_result"].get()
    assert "MSE=0.0000" in result
    assert "PSNR=inf" in result


def test_shape_mismatch_reports_warning():
    ref = np.ones((5, 6), dtype=np.uint16)
    tar = np.ones((4, 6), dtype=np.uint16)
    viewer = _build_viewer(ref, tar)
    viewer.calculate_image_comparison_metrics()
    assert "shape_mismatch" in viewer.image_analysis_results["image_result"].get()


def test_data_range_ambiguous_reports_warning():
    ref = np.zeros((4, 4), dtype=np.float64)
    tar = np.zeros((4, 4), dtype=np.float64)
    viewer = _build_viewer(ref, tar)
    viewer.calculate_image_comparison_metrics()
    assert "data_range_ambiguous" in viewer.image_analysis_results["image_result"].get()


def test_formula_contains_conditions_text():
    ref = np.arange(9, dtype=np.uint16).reshape(3, 3)
    tar = (ref + 1).astype(np.uint16)
    viewer = _build_viewer(ref, tar)
    viewer.calculate_image_comparison_metrics()
    formula = viewer.image_analysis_results["image_formula"].get()
    assert "data_range_policy=" in formula
    assert "hist=(bins=64" in formula
    assert "scope=Full Image" in formula
