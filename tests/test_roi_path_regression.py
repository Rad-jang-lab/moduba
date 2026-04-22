import sys
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure tests run even when matplotlib is not installed.
if "matplotlib" not in sys.modules:
    matplotlib_stub = types.ModuleType("matplotlib")
    pyplot_stub = types.ModuleType("matplotlib.pyplot")

    def _noop(*_args, **_kwargs):
        return None

    pyplot_stub.figure = _noop
    pyplot_stub.plot = _noop
    pyplot_stub.xlabel = _noop
    pyplot_stub.ylabel = _noop
    pyplot_stub.title = _noop
    pyplot_stub.tight_layout = _noop
    pyplot_stub.show = _noop
    matplotlib_stub.pyplot = pyplot_stub
    sys.modules["matplotlib"] = matplotlib_stub
    sys.modules["matplotlib.pyplot"] = pyplot_stub

from dicom_viewer import DicomViewer, Measurement


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


CASE_GRID_POSITIONS = {
    "center": (1, 1),
    "right_edge": (1, 2),
    "bottom_edge": (2, 1),
    "bottom_right_corner": (2, 2),
}

CASE_BOUNDS = {
    "center": (4, 4, 8, 8),
    "right_edge": (8, 4, 10, 8),
    "bottom_edge": (4, 8, 8, 10),
    "bottom_right_corner": (8, 8, 10, 10),
}


def _build_headless_viewer() -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.frames = [np.arange(100, dtype=np.float32).reshape(10, 10)]
    viewer.current_frame = 0
    viewer.dataset = SimpleNamespace()
    viewer.persistent_measurements = []

    viewer.grid_spacing_px = DummyVar(4)
    viewer.grid_roi_width_cells = DummyVar(1)
    viewer.grid_roi_height_cells = DummyVar(1)

    viewer.analysis_inputs = {
        "snr_signal_roi_id": DummyVar(""),
        "snr_background_roi_id": DummyVar(""),
        "cnr_formula": DummyVar("standard_noise"),
        "cnr_target_roi_id": DummyVar(""),
        "cnr_reference_roi_id": DummyVar(""),
        "cnr_noise_roi_id": DummyVar(""),
    }
    viewer.image_analysis_inputs = {}
    viewer.analysis_results = {
        "snr_preview": DummyVar(""),
        "snr_result": DummyVar(""),
        "cnr_preview": DummyVar(""),
        "cnr_result": DummyVar(""),
    }
    viewer.analysis_last_run = {}
    viewer._analysis_comboboxes = {}
    viewer._image_analysis_comboboxes = {}
    viewer._analysis_option_maps = {"roi": {}}
    viewer._image_analysis_option_maps = {}
    return viewer


def _compute_signature(viewer: DicomViewer, measurement: Measurement) -> dict[str, float]:
    metrics = viewer.compute_measurement(measurement, viewer._get_frame_pixel_array(measurement.frame_index))
    stats = metrics["signal_stats"] or {}
    return {
        "pixel_count": int(metrics["pixel_count"]),
        "width_px": int(metrics["width_px"]),
        "height_px": int(metrics["height_px"]),
        "area_px": int(metrics["area_px"]),
        "mean": float(stats.get("mean", 0.0)),
        "std": float(stats.get("std", 0.0)),
        "min": float(stats.get("min", 0.0)),
        "max": float(stats.get("max", 0.0)),
    }


def _assert_same_signature(case_name: str, reference_path: str, compare_path: str, reference: dict, actual: dict):
    for field_name in ["pixel_count", "width_px", "height_px", "area_px", "mean", "std", "min", "max"]:
        left = reference[field_name]
        right = actual[field_name]
        assert np.isclose(left, right), (
            f"ROI parity failed | case={case_name} | field={field_name} | "
            f"{reference_path}={left} | {compare_path}={right}"
        )


def _add_direct_roi(viewer: DicomViewer, case_name: str) -> Measurement:
    x0, y0, x1, y1 = CASE_BOUNDS[case_name]
    measurement = Measurement(
        id=f"direct_{case_name}",
        kind="roi",
        start=(float(x0), float(y0)),
        end=(float(x1), float(y1)),
        frame_index=0,
        geometry_key=viewer._get_current_geometry_key() or "",
        summary_text="",
        meta={"roi_type": "direct"},
    )
    viewer.persistent_measurements.append(measurement)
    return measurement


def _add_free_roi(viewer: DicomViewer, case_name: str) -> Measurement:
    x0, y0, x1, y1 = CASE_BOUNDS[case_name]
    measurement = viewer._append_persistent_measurement(
        "roi",
        (x0, y0),
        (x1 - 1, y1 - 1),
        extra_meta={"roi_type": "free"},
        roi_bounds_exclusive=False,
    )
    assert measurement is not None, f"free ROI creation failed for case={case_name}"
    return measurement


def _add_grid_roi(viewer: DicomViewer, case_name: str) -> Measurement:
    row, col = CASE_GRID_POSITIONS[case_name]
    measurement = viewer.select_roi_from_grid(row, col)
    assert measurement is not None, f"grid ROI creation failed for case={case_name}"
    return measurement


def _run_snr(viewer: DicomViewer, signal: Measurement, noise: Measurement) -> float:
    viewer.analysis_inputs["snr_signal_roi_id"].set(signal.id)
    viewer.analysis_inputs["snr_background_roi_id"].set(noise.id)
    viewer.calculate_snr_from_inputs()
    assert "snr" in viewer.analysis_last_run, "SNR path did not produce analysis_last_run['snr']"
    return float(viewer.analysis_last_run["snr"]["result"])


def _run_cnr(viewer: DicomViewer, formula: str, target: Measurement, reference: Measurement, noise: Measurement | None) -> float:
    viewer.analysis_inputs["cnr_formula"].set(formula)
    viewer.analysis_inputs["cnr_target_roi_id"].set(target.id)
    viewer.analysis_inputs["cnr_reference_roi_id"].set(reference.id)
    viewer.analysis_inputs["cnr_noise_roi_id"].set("" if noise is None else noise.id)
    viewer.calculate_cnr_from_inputs()
    assert "cnr" in viewer.analysis_last_run, "CNR path did not produce analysis_last_run['cnr']"
    return float(viewer.analysis_last_run["cnr"]["result"])


def test_roi_path_regression_parity():
    viewer = _build_headless_viewer()

    measurements_by_path = {
        "direct": {name: _add_direct_roi(viewer, name) for name in CASE_BOUNDS},
        "free": {name: _add_free_roi(viewer, name) for name in CASE_BOUNDS},
        "grid": {name: _add_grid_roi(viewer, name) for name in CASE_BOUNDS},
    }

    signatures: dict[str, dict[str, dict[str, float]]] = {}
    for path_name, per_case in measurements_by_path.items():
        signatures[path_name] = {}
        for case_name, measurement in per_case.items():
            signature = _compute_signature(viewer, measurement)
            roi_stats = viewer._roi_stats(measurement)
            assert roi_stats is not None, f"_roi_stats returned None | path={path_name} | case={case_name}"
            assert np.isclose(signature["mean"], roi_stats.mean), (
                f"Stats mismatch | path={path_name} | case={case_name} | field=mean | "
                f"compute_measurement={signature['mean']} | _roi_stats={roi_stats.mean}"
            )
            assert np.isclose(signature["std"], roi_stats.std), (
                f"Stats mismatch | path={path_name} | case={case_name} | field=std | "
                f"compute_measurement={signature['std']} | _roi_stats={roi_stats.std}"
            )
            assert np.isclose(signature["min"], roi_stats.min_val), (
                f"Stats mismatch | path={path_name} | case={case_name} | field=min | "
                f"compute_measurement={signature['min']} | _roi_stats={roi_stats.min_val}"
            )
            assert np.isclose(signature["max"], roi_stats.max_val), (
                f"Stats mismatch | path={path_name} | case={case_name} | field=max | "
                f"compute_measurement={signature['max']} | _roi_stats={roi_stats.max_val}"
            )
            assert signature["pixel_count"] == roi_stats.area_px, (
                f"Stats mismatch | path={path_name} | case={case_name} | field=pixel_count | "
                f"compute_measurement={signature['pixel_count']} | _roi_stats.area_px={roi_stats.area_px}"
            )
            signatures[path_name][case_name] = signature

    for case_name in CASE_BOUNDS:
        direct = signatures["direct"][case_name]
        free = signatures["free"][case_name]
        grid = signatures["grid"][case_name]
        _assert_same_signature(case_name, "direct", "free", direct, free)
        _assert_same_signature(case_name, "direct", "grid", direct, grid)

    snr_results = {}
    cnr_std_results = {}
    cnr_dual_results = {}
    for path_name, per_case in measurements_by_path.items():
        snr_results[path_name] = _run_snr(viewer, per_case["center"], per_case["bottom_edge"])
        cnr_std_results[path_name] = _run_cnr(
            viewer,
            "standard_noise",
            per_case["center"],
            per_case["right_edge"],
            per_case["bottom_edge"],
        )
        cnr_dual_results[path_name] = _run_cnr(
            viewer,
            "dual_variance",
            per_case["center"],
            per_case["right_edge"],
            None,
        )

    for path_name in ("free", "grid"):
        assert np.isclose(snr_results["direct"], snr_results[path_name]), (
            f"SNR mismatch | direct={snr_results['direct']} | {path_name}={snr_results[path_name]}"
        )
        assert np.isclose(cnr_std_results["direct"], cnr_std_results[path_name]), (
            f"CNR(standard_noise) mismatch | direct={cnr_std_results['direct']} | "
            f"{path_name}={cnr_std_results[path_name]}"
        )
        assert np.isclose(cnr_dual_results["direct"], cnr_dual_results[path_name]), (
            f"CNR(dual_variance) mismatch | direct={cnr_dual_results['direct']} | "
            f"{path_name}={cnr_dual_results[path_name]}"
        )
