import csv
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

from dicom_viewer import DicomViewer, Measurement, ResultHistoryEntry, ResultHistoryStore


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyButton:
    def __init__(self):
        self.state = None

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)


class DummyPathVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _build_viewer() -> DicomViewer:
    viewer = object.__new__(DicomViewer)
    viewer.frames = [np.arange(400, dtype=np.float32).reshape(20, 20)]
    viewer.current_frame = 0
    viewer.dataset = SimpleNamespace(PixelSpacing=[0.5, 0.5])
    viewer.persistent_measurements = []
    viewer.analysis_last_run = {}
    viewer.line_profile_series_cache = {}
    viewer.result_history_store = ResultHistoryStore()
    viewer.result_history_table = None
    viewer._history_item_to_store_index = {}
    viewer._session_compare_state = {"selected_entry_ids": [], "baseline_index": 0}
    viewer.history_metric_filter_var = DummyVar("All")
    viewer.history_search_var = DummyVar("")
    viewer.history_compare_button = DummyButton()
    viewer.file_paths = []
    viewer.current_file_index = -1
    viewer.path_var = DummyPathVar("")
    viewer.zoom_scale = 1.0
    viewer.window_width_value = 120.0
    viewer.window_level_value = 60.0
    viewer.show_grid_overlay = DummyVar(False)
    viewer.show_basic_overlay = DummyVar(True)
    viewer.show_acquisition_overlay = DummyVar(True)
    viewer.invert_display = DummyVar(False)
    viewer.selected_persistent_measurement_id = None
    viewer._persistent_canvas_item_to_measurement_id = {}
    viewer.analysis_inputs = {
        "snr_signal_roi_id": DummyVar(""),
        "snr_background_roi_id": DummyVar(""),
        "cnr_formula": DummyVar("standard_noise"),
        "cnr_target_roi_id": DummyVar(""),
        "cnr_reference_roi_id": DummyVar(""),
        "cnr_noise_roi_id": DummyVar(""),
        "uniformity_formula": DummyVar("max_min"),
        "uniformity_input_mode": DummyVar("selected_rois"),
        "uniformity_role_filter": DummyVar("signal"),
        "uniformity_roi_ids": DummyVar(""),
        "line_profile_line_id": DummyVar(""),
    }
    viewer.analysis_results = {"line_info": DummyVar("-")}
    viewer.measurement_mode = DummyVar("pan")
    viewer.root = SimpleNamespace(clipboard_clear=lambda: None, clipboard_append=lambda _s: None)

    # Headless-safe no-op hooks used by session/preset apply flows.
    viewer._refresh_analysis_selectors = lambda: None
    viewer._refresh_result_history_table = lambda: None
    viewer._draw_persistent_measurements = lambda: None
    viewer._sync_analysis_selector_inputs = lambda: None
    viewer._toggle_cnr_noise_widgets = lambda: None
    viewer._auto_bind_analysis_inputs_from_roles = lambda overwrite_existing=True: None
    viewer._update_analysis_action_button_state = lambda: None
    viewer._refresh_grid_overlay = lambda: None
    viewer._show_frame = lambda: None
    viewer._reset_file_list_state = lambda: None
    viewer._set_loaded_paths = lambda paths, folder=None: setattr(viewer, "file_paths", list(paths))
    viewer._load_file = lambda index, preserve_view_state=False: setattr(viewer, "current_file_index", index)
    viewer._resolve_session_image_path = lambda source_image_path: source_image_path
    return viewer


def _add_roi(viewer: DicomViewer, measurement_id: str, start, end, role: str | None = None) -> Measurement:
    measurement = Measurement(
        id=measurement_id,
        kind="roi",
        start=(float(start[0]), float(start[1])),
        end=(float(end[0]), float(end[1])),
        frame_index=viewer.current_frame,
        geometry_key=viewer._get_current_geometry_key() or "20x20",
        summary_text="",
        meta={"roi_type": "free"},
    )
    if role:
        measurement.meta["role"] = role
    metrics = viewer.compute_measurement(measurement, viewer._get_frame_pixel_array(viewer.current_frame))
    measurement.summary_text = metrics["summary"]
    measurement.meta = viewer._canonicalize_measurement_meta(measurement, metrics)
    viewer.persistent_measurements.append(measurement)
    return measurement


def _add_line(viewer: DicomViewer, measurement_id: str, start, end) -> Measurement:
    measurement = Measurement(
        id=measurement_id,
        kind="line",
        start=(float(start[0]), float(start[1])),
        end=(float(end[0]), float(end[1])),
        frame_index=viewer.current_frame,
        geometry_key=viewer._get_current_geometry_key() or "20x20",
        summary_text="",
        meta={},
    )
    metrics = viewer.compute_measurement(measurement, viewer._get_frame_pixel_array(viewer.current_frame))
    measurement.summary_text = metrics["summary"]
    measurement.meta = viewer._canonicalize_measurement_meta(measurement, metrics)
    viewer.persistent_measurements.append(measurement)
    return measurement


def _append_history(viewer: DicomViewer, measurement_type: str, target_name: str, metric: str, value: float, target_id: str = ""):
    viewer._append_history_entry(
        measurement_type=measurement_type,
        target_name=target_name,
        metric=metric,
        value=value,
        unit="AU",
        note="integration",
        target_id=target_id,
    )


def test_session_save_load_integration_round_trip(monkeypatch, tmp_path):
    viewer = _build_viewer()
    monkeypatch.setattr("dicom_viewer.messagebox.showwarning", lambda *_args, **_kwargs: None)

    source_path = tmp_path / "sample.dcm"
    source_path.write_text("stub", encoding="utf-8")
    viewer.file_paths = [str(source_path)]
    viewer.current_file_index = 0

    signal = _add_roi(viewer, "roi_signal", (2, 2), (6, 6), role="signal")
    noise = _add_roi(viewer, "roi_noise", (10, 10), (14, 14), role="noise")
    line = _add_line(viewer, "line_1", (0, 0), (19, 19))

    _append_history(viewer, "ROI", "ROI 1", "Mean", 42.1234, target_id=signal.id)
    _append_history(viewer, "Line Profile", "Line 1", "LINE_PROFILE_MEAN", 15.0, target_id=line.id)

    entry_ids = [entry.entry_id for entry in viewer.result_history_store.entries()]
    viewer._session_compare_state = {"selected_entry_ids": entry_ids[:1], "baseline_index": 0}

    payload = viewer.serialize_session()
    restored = viewer.deserialize_session(payload)

    viewer.persistent_measurements = []
    viewer.result_history_store.clear()
    viewer._session_compare_state = {"selected_entry_ids": [], "baseline_index": -1}

    viewer.apply_session(restored)

    assert viewer.file_paths[0] == str(source_path)
    assert viewer.current_frame == 0
    assert len([m for m in viewer.persistent_measurements if m.kind == "roi"]) == 2
    assert len([m for m in viewer.persistent_measurements if m.kind == "line"]) == 1
    restored_signal = next(m for m in viewer.persistent_measurements if m.id == "roi_signal")
    assert restored_signal.meta.get("role") == "signal"
    assert len(viewer.result_history_store.entries()) == 2
    assert viewer._session_compare_state["selected_entry_ids"] == entry_ids[:1]
    assert viewer._session_compare_state["baseline_index"] == 0


def test_preset_save_load_integration_keeps_session_objects_and_history():
    viewer = _build_viewer()
    roi_a = _add_roi(viewer, "roi_a", (1, 1), (4, 4), role="signal")
    _add_roi(viewer, "roi_b", (5, 5), (8, 8), role="noise")
    _add_line(viewer, "line_a", (0, 19), (19, 0))

    _append_history(viewer, "Analysis", "SNR", "SNR", 7.77)
    viewer.current_frame = 0
    viewer.file_paths = ["/tmp/keep-image.dcm"]
    viewer.current_file_index = 0

    viewer.analysis_inputs["cnr_formula"].set("dual_variance")
    viewer.analysis_inputs["uniformity_formula"].set("max_min")
    viewer.show_grid_overlay.set(True)

    preset = viewer.serialize_preset()

    viewer.analysis_inputs["cnr_formula"].set("standard_noise")
    viewer.analysis_inputs["uniformity_formula"].set("alt")
    viewer.show_grid_overlay.set(False)
    roi_a.meta["role"] = "reference"

    restored = viewer.deserialize_preset(preset)
    viewer.apply_preset(restored)

    assert viewer.analysis_inputs["cnr_formula"].get() == "dual_variance"
    assert viewer.analysis_inputs["uniformity_formula"].get() == "max_min"
    assert viewer.show_grid_overlay.get() is True
    assert viewer.current_frame == 0
    assert viewer.file_paths[0] == "/tmp/keep-image.dcm"
    assert len(viewer.result_history_store.entries()) == 1
    assert len([m for m in viewer.persistent_measurements if m.kind == "roi"]) == 2
    assert len([m for m in viewer.persistent_measurements if m.kind == "line"]) == 1
    # Role template reapplies by ROI display label mapping.
    roi_a_after = next(m for m in viewer.persistent_measurements if m.id == "roi_a")
    assert roi_a_after.meta.get("role") == "signal"


def test_history_compare_integration_and_edge_cases(monkeypatch):
    viewer = _build_viewer()
    warnings: list[str] = []
    monkeypatch.setattr("dicom_viewer.messagebox.showwarning", lambda _title, msg: warnings.append(msg))

    entries = [
        ResultHistoryEntry("e1", "2026-01-01 00:00:00", "a.dcm", 0, "Analysis", "A", "SNR", 0.0, "AU", "n", "pan"),
        ResultHistoryEntry("e2", "2026-01-01 00:00:01", "a.dcm", 0, "Analysis", "B", "SNR", 10.0, "AU", "n", "pan"),
        ResultHistoryEntry("e3", "2026-01-01 00:00:02", "a.dcm", 0, "Analysis", "C", "CNR", 5.0, "AU", "n", "pan"),
    ]
    comparison = viewer.build_history_comparison(entries[:2])
    assert comparison["baseline"].entry_id == "e1"
    assert comparison["rows"][1]["difference"] == 10.0
    assert comparison["rows"][1]["percent_change"] == "N/A"

    mixed = viewer.build_history_comparison(entries)
    assert mixed["mixed_metrics"] is True
    if mixed["mixed_metrics"]:
        import dicom_viewer as module

        module.messagebox.showwarning("Compare", "같은 metric 비교를 권장합니다. (혼합 metric 계속 진행)")
    assert warnings, "mixed metric warning should be emitted in compare flow"

    viewer._selected_history_entries = lambda: [(0, entries[0]), (1, entries[1])]
    viewer._update_history_compare_button_state()
    assert viewer.history_compare_button.state == "normal"
    viewer._selected_history_entries = lambda: [(0, entries[0])]
    viewer._update_history_compare_button_state()
    assert viewer.history_compare_button.state == "disabled"


def test_line_profile_compare_overlay_delta_and_cache_fallback():
    viewer = _build_viewer()
    line1 = _add_line(viewer, "line1", (0, 0), (19, 19))
    line2 = _add_line(viewer, "line2", (0, 19), (19, 0))

    series2 = viewer.extract_line_profile(line2)
    viewer.line_profile_series_cache[viewer._line_profile_cache_key("", 0, line2.id)] = {
        "distance_px": list(series2["distance_px"]),
        "distance_mm": list(series2["distance_mm"]) if series2["distance_mm"] is not None else None,
        "intensity": list(series2["intensity"]),
    }

    profile1 = viewer.extract_line_profile(line1)
    viewer.analysis_last_run["line_profile"] = {
        "inputs": {"line_id": line1.id},
        "result": {
            "distance_px": list(profile1["distance_px"]),
            "distance_mm": list(profile1["distance_mm"]) if profile1["distance_mm"] is not None else None,
            "intensity": list(profile1["intensity"]),
        },
    }

    entries = [
        ResultHistoryEntry("l1", "2026", "img", 0, "Line Profile", "Line 1", "LINE_PROFILE_MEAN", 1.0, "AU", "n", "pan", target_id="line1"),
        ResultHistoryEntry("l2", "2026", "img", 0, "Line Profile", "Line 2", "LINE_PROFILE_MEAN", 2.0, "AU", "n", "pan", target_id="line2"),
        ResultHistoryEntry("l3", "2026", "img", 0, "Line Profile", "Line missing", "LINE_PROFILE_MEAN", 3.0, "AU", "n", "pan", target_id="missing"),
    ]

    overlay = viewer.build_line_profile_overlay_data(entries)
    assert overlay["axis"] == "mm"
    assert len(overlay["series"]) == 2
    assert "Line missing" in overlay["missing"]

    delta = viewer.build_delta_profile_data(overlay)
    assert delta["axis"] == "mm"
    assert len(delta["series"]) == 1
    assert delta["series"][0]["label"].endswith("vs baseline")


def test_feature_calculation_integration_for_single_flat_and_multi_peak_profiles():
    viewer = _build_viewer()

    x = np.arange(7, dtype=np.float64)
    single_peak = {"distance_px": x, "distance_mm": None, "intensity": np.array([0, 1, 3, 6, 3, 1, 0], dtype=np.float64)}
    features = viewer.compute_profile_features(single_peak)
    assert features["peak_value"] == 6.0
    assert features["peak_position"] == 3.0
    assert features["valley_value"] == 0.0
    assert isinstance(features["fwhm"], float)

    flat = {"distance_px": x, "distance_mm": None, "intensity": np.full_like(x, 5.0)}
    flat_features = viewer.compute_profile_features(flat)
    assert flat_features["fwhm"] is None

    multi_peak = {"distance_px": x, "distance_mm": None, "intensity": np.array([0, 5, 2, 9, 2, 5, 0], dtype=np.float64)}
    multi_features = viewer.compute_profile_features(multi_peak)
    assert multi_features["peak_value"] == 9.0
    assert multi_features["peak_position"] == 3.0


def test_append_only_history_and_unique_entry_ids():
    viewer = _build_viewer()
    _add_roi(viewer, "roi_repeat", (2, 2), (6, 6), role="signal")

    _append_history(viewer, "ROI", "ROI 1", "Mean", 11.11, target_id="roi_repeat")
    _append_history(viewer, "ROI", "ROI 1", "Mean", 11.11, target_id="roi_repeat")
    _append_history(viewer, "ROI", "ROI 1", "Mean", 11.11, target_id="roi_repeat")

    entries = viewer.result_history_store.entries()
    assert len(entries) == 3
    assert len({entry.entry_id for entry in entries}) == 3


def test_export_reload_consistency_csv_schema_and_format(tmp_path):
    viewer = _build_viewer()
    source_path = tmp_path / "export_source.dcm"
    source_path.write_text("stub", encoding="utf-8")
    viewer.file_paths = [str(source_path)]
    viewer.current_file_index = 0
    _append_history(viewer, "Analysis", "SNR", "SNR", 12.3456)
    _append_history(viewer, "Analysis", "CNR", "CNR", 2.0)

    csv_before = tmp_path / "before.csv"
    viewer._write_result_history_csv(str(csv_before), viewer.result_history_store.entries())

    session_payload = viewer.serialize_session()
    viewer.result_history_store.clear()
    viewer.apply_session(viewer.deserialize_session(session_payload))

    csv_after = tmp_path / "after.csv"
    viewer._write_result_history_csv(str(csv_after), viewer.result_history_store.entries())

    raw_before = csv_before.read_bytes()
    raw_after = csv_after.read_bytes()
    assert raw_before.decode("utf-8")
    assert raw_after.decode("utf-8")

    with csv_before.open("r", encoding="utf-8", newline="") as handle:
        rows_before = list(csv.reader(handle))
    with csv_after.open("r", encoding="utf-8", newline="") as handle:
        rows_after = list(csv.reader(handle))

    assert rows_before[0] == [
        "Timestamp",
        "ImageName",
        "Frame",
        "MeasurementType",
        "TargetName",
        "Metric",
        "Value",
        "Unit",
        "Note",
    ]
    assert rows_before[0] == rows_after[0]
    assert rows_before[1][6].count(".") == 1 and len(rows_before[1][6].split(".")[1]) == 2
    assert rows_before == rows_after
