import sys
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

from dicom_viewer import DicomViewer, MeasurementSet


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyButton:
    def __init__(self):
        self.state = "normal"

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]


class DummyCombobox:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _build_viewer() -> DicomViewer:
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
        "snr_ready_reason": DummyVar(""),
        "cnr_preview": DummyVar(""),
        "cnr_result": DummyVar(""),
    }
    viewer.analysis_last_run = {}
    viewer._analysis_comboboxes = {}
    viewer._image_analysis_comboboxes = {}
    viewer._analysis_option_maps = {"roi": {}}
    viewer._image_analysis_option_maps = {}
    viewer._analysis_action_buttons = {"snr": DummyButton(), "cnr": DummyButton()}
    return viewer


def _add_roi(viewer: DicomViewer, roi_id: str, start, end, role: str | None):
    measurement = viewer._append_persistent_measurement(
        "roi",
        start,
        end,
        extra_meta={"roi_type": "free", "role": role} if role else {"roi_type": "free"},
        roi_bounds_exclusive=True,
    )
    assert measurement is not None, f"failed to create roi {roi_id}"
    measurement.id = roi_id
    if role:
        measurement.meta["role"] = role
    return measurement


def test_roi_roles_auto_bind_snr_cnr_inputs_and_button_state():
    viewer = _build_viewer()
    signal = _add_roi(viewer, "roi_signal", (1, 1), (5, 5), "signal")
    background = _add_roi(viewer, "roi_background", (5, 1), (9, 5), "background")
    target = _add_roi(viewer, "roi_target", (1, 5), (5, 9), "target")
    reference = _add_roi(viewer, "roi_reference", (5, 5), (9, 9), "reference")
    noise = _add_roi(viewer, "roi_noise", (0, 0), (4, 4), "noise")

    viewer._auto_bind_analysis_inputs_from_roles(overwrite_existing=True)

    assert viewer.analysis_inputs["snr_signal_roi_id"].get() == signal.id
    assert viewer.analysis_inputs["snr_background_roi_id"].get() == background.id
    assert viewer.analysis_inputs["cnr_target_roi_id"].get() == target.id
    assert viewer.analysis_inputs["cnr_reference_roi_id"].get() == reference.id
    assert viewer.analysis_inputs["cnr_noise_roi_id"].get() == noise.id

    viewer.calculate_snr_from_inputs()
    viewer.calculate_cnr_from_inputs()

    assert "snr" in viewer.analysis_last_run
    assert "cnr" in viewer.analysis_last_run
    assert viewer._analysis_action_buttons["snr"].state == "normal"
    assert viewer._analysis_action_buttons["cnr"].state == "normal"


def test_roi_role_persists_through_measurement_set_serialization():
    viewer = _build_viewer()
    signal = _add_roi(viewer, "roi_signal", (1, 1), (5, 5), "signal")
    measurement_set = MeasurementSet(
        id="set1",
        name="role-set",
        geometry_key=viewer._get_current_geometry_key() or "",
        created_at="2026-04-22T00:00:00",
        measurements=[signal],
    )

    payload = viewer._serialize_measurement_set(measurement_set)
    restored_set = viewer._deserialize_measurement_set(payload)

    assert restored_set.measurements[0].meta.get("role") == "signal"


def test_snr_button_enabled_with_manual_selection_even_without_roles():
    viewer = _build_viewer()
    signal = _add_roi(viewer, "roi_signal_manual", (1, 1), (5, 5), role=None)
    noise = _add_roi(viewer, "roi_noise_manual", (5, 1), (9, 5), role=None)

    signal_label = "Signal Manual ROI"
    noise_label = "Noise Manual ROI"
    viewer._analysis_option_maps["roi"] = {
        signal_label: signal.id,
        noise_label: noise.id,
    }
    viewer._analysis_comboboxes = {
        "snr_signal": DummyCombobox(signal_label),
        "snr_noise": DummyCombobox(noise_label),
    }

    viewer._update_analysis_action_button_state()

    assert viewer._analysis_action_buttons["snr"].state == "normal"
    assert viewer.analysis_results["snr_ready_reason"].get().startswith("Ready:")


def test_snr_button_enabled_with_manual_ids_even_without_combobox_selection():
    viewer = _build_viewer()
    signal = _add_roi(viewer, "roi_signal_manual_ids", (1, 1), (5, 5), role=None)
    noise = _add_roi(viewer, "roi_noise_manual_ids", (5, 1), (9, 5), role=None)

    viewer.analysis_inputs["snr_signal_roi_id"].set(signal.id)
    viewer.analysis_inputs["snr_background_roi_id"].set(noise.id)
    viewer._analysis_comboboxes = {
        "snr_signal": DummyCombobox(""),
        "snr_noise": DummyCombobox(""),
    }

    viewer._update_analysis_action_button_state()

    assert viewer._analysis_action_buttons["snr"].state == "normal"
    assert "measurement" in viewer.analysis_results["snr_ready_reason"].get()


def test_cnr_button_enabled_with_manual_selection_even_without_roles():
    viewer = _build_viewer()
    target = _add_roi(viewer, "roi_target_manual", (1, 1), (5, 5), role=None)
    reference = _add_roi(viewer, "roi_reference_manual", (5, 1), (9, 5), role=None)
    noise = _add_roi(viewer, "roi_noise_manual", (1, 5), (5, 9), role=None)

    target_label = "Target Manual ROI"
    reference_label = "Reference Manual ROI"
    noise_label = "Noise Manual ROI"
    viewer.analysis_inputs["cnr_formula"].set("standard_noise")
    viewer._analysis_option_maps["roi"] = {
        target_label: target.id,
        reference_label: reference.id,
        noise_label: noise.id,
    }
    viewer._analysis_comboboxes = {
        "cnr_target": DummyCombobox(target_label),
        "cnr_reference": DummyCombobox(reference_label),
        "cnr_noise": DummyCombobox(noise_label),
    }

    viewer._update_analysis_action_button_state()

    assert viewer._analysis_action_buttons["cnr"].state == "normal"
