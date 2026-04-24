import sys
from pathlib import Path
import types
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

from domain_store import DomainStore
from dicom_viewer import DicomViewer, Measurement
from window_b_services import HistoryController, SessionController, ReportExportController
from window_b_manager import WindowBManager


def test_roi_change_reflects_in_selector_immediately() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")

    measurement_id = store.add_measurement(
        image_id=image_id,
        kind="roi",
        start=(0.0, 0.0),
        end=(1.0, 1.0),
        frame_index=0,
        geometry_key="g1",
        summary_text="ROI #1",
    )

    frame_measurements = store.select_measurements_for_image(image_id, frame_index=0)
    assert {item.measurement_id for item in frame_measurements} == {measurement_id}


def test_frame_change_updates_analysis_target() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")

    first_id = store.add_measurement(image_id, "roi", (0.0, 0.0), (1.0, 1.0), 0, "g1", "F0")
    second_id = store.add_measurement(image_id, "roi", (0.0, 0.0), (1.0, 1.0), 1, "g2", "F1")

    inputs_before = store.select_analysis_inputs(image_id, frame_index=0)
    assert set(inputs_before["unassigned"]) == {first_id}

    store.set_frame(image_id, frame_index=1)
    inputs_after = store.select_analysis_inputs(image_id, frame_index=1)
    assert set(inputs_after["unassigned"]) == {second_id}


def test_role_change_rebuilds_analysis_candidates() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")
    measurement_id = store.add_measurement(image_id, "roi", (0.0, 0.0), (1.0, 1.0), 0, "g1", "ROI")

    inputs_before = store.select_analysis_inputs(image_id, frame_index=0)
    assert set(inputs_before.keys()) == {"unassigned"}

    store.set_role(measurement_id, "signal")
    inputs_after = store.select_analysis_inputs(image_id, frame_index=0)
    assert set(inputs_after.keys()) == {"signal"}
    assert inputs_after["signal"] == [measurement_id]


def test_session_save_load_keeps_atomic_snapshot_consistent() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")
    measurement_id = store.add_measurement(image_id, "roi", (0.0, 0.0), (1.0, 1.0), 0, "g1", "ROI")
    store.set_selection(image_id, [measurement_id])

    snapshot = store.save_session("s-1", "Session 1")

    store.delete_measurement(measurement_id)
    assert store.select_measurements_for_image(image_id) == []

    store.load_session({**snapshot, "session_id": "s-1"})

    recovered = store.select_measurements_for_image(image_id)
    assert len(recovered) == 1
    assert recovered[0].measurement_id == measurement_id
    assert store.state.selected_measurement_ids == [measurement_id]


def test_required_event_contracts_emit_metadata_only() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")

    received: list[dict[str, object]] = []
    for event_name in (
        "measurement_added",
        "measurement_updated",
        "measurement_deleted",
        "selection_changed",
        "frame_changed",
        "role_changed",
        "analysis_requested",
        "analysis_completed",
        "session_saved",
        "session_loaded",
    ):
        store.events.subscribe(event_name, received.append)

    measurement_id = store.add_measurement(image_id, "roi", (0.0, 0.0), (1.0, 1.0), 0, "g1", "ROI")
    store.update_measurement(measurement_id, summary_text="updated")
    store.set_selection(image_id, [measurement_id])
    store.set_frame(image_id, 1)
    store.set_role(measurement_id, "noise")
    run_id = store.request_analysis(image_id, "SNR", [measurement_id])
    store.complete_analysis(run_id, [{"metric": "SNR", "value": 23.4, "unit": "dB", "target_id": measurement_id}])
    snapshot = store.save_session("s-2", "Session 2")
    store.load_session({**snapshot, "session_id": "s-2"})
    store.delete_measurement(measurement_id)

    seen_types = {event["event_type"] for event in received}
    assert seen_types == {
        "measurement_added",
        "measurement_updated",
        "measurement_deleted",
        "selection_changed",
        "frame_changed",
        "role_changed",
        "analysis_requested",
        "analysis_completed",
        "session_saved",
        "session_loaded",
    }

    for event in received:
        for value in event.values():
            assert not hasattr(value, "__dict__")


def test_event_handler_requeries_selector_using_metadata_payload() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")
    observed_roles: list[str] = []

    def _on_role_changed(payload: dict[str, object]) -> None:
        measurement_id = str(payload["measurement_id"])
        measurement = store.state.measurements[measurement_id]
        observed_roles.append(str(measurement.role))

    store.events.subscribe("role_changed", _on_role_changed)
    measurement_id = store.add_measurement(image_id, "roi", (0.0, 0.0), (1.0, 1.0), 0, "g1", "ROI")
    store.set_role(measurement_id, "signal")

    assert observed_roles == ["signal"]


def test_history_and_session_selectors_return_expected_entries() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")
    measurement_id = store.add_measurement(image_id, "roi", (0.0, 0.0), (1.0, 1.0), 0, "g1", "ROI")
    run_id = store.request_analysis(image_id, "SNR", [measurement_id])
    store.complete_analysis(run_id, [{"metric": "SNR", "value": 21.0, "unit": "dB", "target_id": measurement_id}])
    store.save_session("s-1", "Session 1")

    history_entries = store.select_history_entries(image_id=image_id)
    sessions = store.select_study_sessions()

    assert len(history_entries) == 1
    assert history_entries[0].run_id == run_id
    assert [item.session_id for item in sessions] == ["s-1"]


def test_snapshot_contains_measurement_geometry_for_selector_only_rebuild() -> None:
    store = DomainStore()
    image_id = store.add_image_context("/tmp/a.dcm", "a")
    measurement_id = store.add_measurement(
        image_id=image_id,
        kind="roi",
        start=(3.0, 4.0),
        end=(8.0, 9.0),
        frame_index=0,
        geometry_key="g1",
        summary_text="ROI",
    )
    snapshot = store.snapshot()
    restored = DomainStore()
    restored.load_session({**snapshot, "session_id": "s-1"})
    rows = restored.select_measurements_for_image(image_id, frame_index=0)
    assert len(rows) == 1
    assert rows[0].measurement_id == measurement_id
    assert rows[0].start == (3.0, 4.0)
    assert rows[0].end == (8.0, 9.0)


def test_measurement_actions_keep_store_in_sync_for_add_update_delete() -> None:
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer.selected_persistent_measurement_id = None
    viewer.guided_snr_state = None
    viewer.view_mode = "single"
    viewer._draw_preview_measurements = lambda: None
    viewer._draw_persistent_measurements = lambda: None
    viewer._draw_single_view_overlays = lambda: None
    viewer._cancel_guided_snr_workflow = lambda: None
    viewer._get_measurement_roi_role = lambda measurement: (measurement.meta or {}).get("role")

    measurement = Measurement(
        id="m-1",
        kind="roi",
        start=(0.0, 0.0),
        end=(2.0, 2.0),
        frame_index=0,
        geometry_key="g1",
        summary_text="ROI",
        meta={"role": "signal"},
    )
    viewer._action_add_measurement_to_store(measurement)
    assert set(viewer.domain_store.state.measurements.keys()) == {"m-1"}

    measurement.summary_text = "ROI updated"
    measurement.meta["role"] = "noise"
    viewer._action_update_measurement_in_store(measurement)
    assert viewer.domain_store.state.measurements["m-1"].summary_text == "ROI updated"
    assert viewer.domain_store.state.measurements["m-1"].role == "noise"

    viewer.selected_persistent_measurement_id = "m-1"
    viewer.domain_store.set_selection(viewer._store_image_id, ["m-1"])
    viewer.clear_selected_measurement()
    assert viewer.domain_store.state.measurements == {}


def test_history_selector_reads_from_store_payload_without_legacy_store() -> None:
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer.analysis_groups = viewer.domain_store.state.analysis_groups
    viewer.study_sessions = viewer.domain_store.state.sessions
    viewer.result_history_store = type(
        "HistoryStub",
        (),
        {"entries": lambda self: [], "append": lambda self, _entry: None},
    )()
    viewer._ensure_domain_store = lambda: None
    from dicom_viewer import ResultHistoryEntry
    entry = ResultHistoryEntry(
        entry_id="e-1",
        timestamp="2026-01-01 00:00:00",
        image_name="a",
        frame_index=0,
        measurement_type="ROI",
        target_name="ROI 1",
        metric="Mean",
        value=1.0,
        unit="a.u.",
        note="n",
        measurement_mode="roi",
    )
    viewer._action_history_append_entry = DicomViewer._action_history_append_entry.__get__(viewer, DicomViewer)
    viewer._select_result_history_entries = DicomViewer._select_result_history_entries.__get__(viewer, DicomViewer)
    viewer._action_history_append_entry(entry)
    rows = viewer._select_result_history_entries()
    assert len(rows) == 1
    assert rows[0].entry_id == "e-1"


def test_legacy_session_payload_can_be_migrated_to_store_snapshot() -> None:
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer._get_measurement_roi_role = DicomViewer._get_measurement_roi_role.__get__(viewer, DicomViewer)
    viewer._migrate_legacy_session_to_store_snapshot = DicomViewer._migrate_legacy_session_to_store_snapshot.__get__(viewer, DicomViewer)
    from dicom_viewer import Measurement

    session_data = {
        "source_image_path": "/tmp/a.dcm",
        "frame_index": 0,
        "roi_list": [
            Measurement(
                id="m-legacy",
                kind="roi",
                start=(1.0, 2.0),
                end=(3.0, 4.0),
                frame_index=0,
                geometry_key="g1",
                summary_text="ROI",
                meta={},
            )
        ],
        "line_list": [],
        "results_history": [],
        "analysis_groups": [],
        "study_sessions": [],
    }
    snapshot = viewer._migrate_legacy_session_to_store_snapshot(session_data)
    loaded = DomainStore()
    loaded.load_session({**snapshot, "session_id": "migrated"})
    rows = loaded.select_measurements_for_image(loaded.state.selected_image_id or "")
    assert len(rows) == 1
    assert rows[0].measurement_id == "m-legacy"


def test_draw_projection_is_built_from_store_selector_not_legacy_list() -> None:
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer.current_frame = 0
    viewer._ensure_domain_store = lambda: None
    viewer._get_current_geometry_key = lambda: "g1"
    viewer._geometry_matches = lambda left, right: DicomViewer._geometry_matches(left, right)
    viewer.domain_store.add_measurement(
        image_id=viewer._store_image_id,
        kind="roi",
        start=(2.0, 2.0),
        end=(4.0, 4.0),
        frame_index=0,
        geometry_key="g1",
        summary_text="store",
        measurement_id="store-only",
    )

    rows = viewer._select_measurement_draw_projections()
    assert [row.measurement_id for row in rows] == ["store-only"]


def test_draw_rebuilds_runtime_objects_from_projection_and_updates_store() -> None:
    class CanvasStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
            self._next = 1

        def delete(self, *_args):
            return None

        def create_rectangle(self, *args, **kwargs):
            self.calls.append(("create_rectangle", args, kwargs))
            self._next += 1
            return self._next

        def create_line(self, *args, **kwargs):
            self.calls.append(("create_line", args, kwargs))
            self._next += 1
            return self._next

        def create_polygon(self, *args, **kwargs):
            self.calls.append(("create_polygon", args, kwargs))
            self._next += 1
            return self._next

        def create_text(self, *args, **kwargs):
            self.calls.append(("create_text", args, kwargs))
            self._next += 1
            return self._next

        def bbox(self, _item_id):
            return (0, 0, 10, 10)

        def tag_raise(self, *_args):
            return None

        def itemconfig(self, *_args, **_kwargs):
            return None

    viewer = DicomViewer.__new__(DicomViewer)
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer.current_frame = 0
    viewer.canvas = CanvasStub()
    viewer.selected_persistent_measurement_id = None
    viewer._ensure_domain_store = lambda: None
    viewer._get_current_geometry_key = lambda: "g1"
    viewer._geometry_matches = lambda left, right: DicomViewer._geometry_matches(left, right)
    viewer._image_coords_to_canvas = lambda x, y: (x, y)
    viewer._get_frame_pixel_array = lambda _frame_index: np.zeros((16, 16), dtype=np.float32)
    viewer.compute_measurement = lambda _measurement, _frame: {"summary": "updated", "area_px": 4.0}
    viewer._canonicalize_measurement_meta = lambda measurement, _metrics: dict(measurement.meta or {})
    viewer._get_roi_display_index = lambda _measurement_id: None
    viewer._build_measurement_label_parts = lambda _kind, _metrics, _measurement: ("ROI", "meta")
    viewer._resolve_roi_label_position = lambda ex, ey, _p, _s, _occ: (ex, ey, "sw", (0.0, 0.0, 1.0, 1.0))
    viewer._draw_measurement_label = lambda *_args, **_kwargs: None
    viewer._build_grid_roi_regions = lambda _rows: []
    viewer._format_grid_roi_region_summary = lambda *_args, **_kwargs: "grid"
    viewer._refresh_analysis_selectors = lambda: None
    viewer._get_measurement_roi_role = lambda measurement: (measurement.meta or {}).get("role")
    viewer._action_update_measurement_in_store = DicomViewer._action_update_measurement_in_store.__get__(viewer, DicomViewer)

    viewer.domain_store.add_measurement(
        image_id=viewer._store_image_id,
        kind="roi",
        start=(1.0, 1.0),
        end=(3.0, 3.0),
        frame_index=0,
        geometry_key="g1",
        summary_text="initial",
        measurement_id="store-measurement",
    )

    viewer._draw_persistent_measurements()

    drawn_rectangles = [call for call in viewer.canvas.calls if call[0] == "create_rectangle"]
    assert len(drawn_rectangles) >= 1
    assert viewer.domain_store.state.measurements["store-measurement"].summary_text == "updated"


def test_legacy_bridge_and_measurement_list_references_are_removed_from_runtime_code() -> None:
    source = Path("dicom_viewer.py").read_text(encoding="utf-8")
    assert "_legacy_bridge_" not in source
    assert "self.persistent_measurements" not in source


def test_history_session_report_controllers_work_with_selector_results() -> None:
    history_controller = HistoryController()
    report_controller = ReportExportController()
    session_controller = SessionController()

    grouped_rows = [
        {
            "image_name": "a",
            "target_name": "ROI 1",
            "measurement_type": "ROI",
            "metric": "Mean",
            "note": "ok",
            "store_indices": [1],
        }
    ]
    flat_rows = history_controller.build_flat_history_view(grouped_rows, search_text="roi")
    assert len(flat_rows) == 1
    selected = report_controller.filter_selected_rows(flat_rows, {1})
    assert len(selected) == 1

    payload = session_controller.build_serialize_payload(
        {
            "schema_version": "1.0",
            "source_image_path": "/tmp/a.dcm",
            "frame_index": 0,
            "display": {"zoom_scale": 1.0},
            "roi_list": [],
            "line_list": [],
            "analysis_options": {},
            "results_history": [],
            "analysis_groups": [],
            "study_sessions": [],
            "active_study_id": "",
            "active_group_id": "",
            "compare_state": {"selected_history_row_ids": [], "baseline_index": 0},
            "store_snapshot": {"snapshot_timestamp": "2026-01-01T00:00:00Z", "state": {}},
        }
    )
    assert payload["version"] == "1.0"
    assert payload["store_snapshot_timestamp"] == "2026-01-01T00:00:00Z"


def test_window_b_manager_closed_state_refresh_is_safe_noop() -> None:
    viewer = type(
        "ViewerStub",
        (),
        {"_refresh_analysis_results_panel": lambda self: None, "_refresh_result_history_table": lambda self: None},
    )()
    manager = WindowBManager.__new__(WindowBManager)
    manager.root = None
    manager.viewer = viewer
    manager._window = None
    manager._dirty_while_closed = False
    manager._is_built = False
    manager.refresh_all()
    assert manager._dirty_while_closed is True


def test_a_entrypoints_delegate_session_and_history_export_to_window_b() -> None:
    viewer = DicomViewer.__new__(DicomViewer)
    calls: list[str] = []
    viewer.open_window_b = lambda: calls.append("open")
    viewer.window_b_manager = type("Mgr", (), {"refresh_all": lambda self: calls.append("refresh_all"), "refresh_history": lambda self: calls.append("refresh_history")})()
    viewer.save_analysis_session = lambda: calls.append("save")
    viewer.load_analysis_session = lambda: calls.append("load")
    viewer.export_result_history_csv = lambda: calls.append("export_all")
    viewer.export_selected_result_history_csv = lambda: calls.append("export_selected")

    viewer._open_window_b_and_refresh_all = DicomViewer._open_window_b_and_refresh_all.__get__(viewer, DicomViewer)
    viewer._open_window_b_and_refresh_history = DicomViewer._open_window_b_and_refresh_history.__get__(viewer, DicomViewer)
    viewer.save_analysis_session_via_window_b = DicomViewer.save_analysis_session_via_window_b.__get__(viewer, DicomViewer)
    viewer.load_analysis_session_via_window_b = DicomViewer.load_analysis_session_via_window_b.__get__(viewer, DicomViewer)
    viewer.export_result_history_csv_via_window_b = DicomViewer.export_result_history_csv_via_window_b.__get__(viewer, DicomViewer)
    viewer.export_selected_result_history_csv_via_window_b = DicomViewer.export_selected_result_history_csv_via_window_b.__get__(viewer, DicomViewer)

    viewer.save_analysis_session_via_window_b()
    viewer.load_analysis_session_via_window_b()
    viewer.export_result_history_csv_via_window_b()
    viewer.export_selected_result_history_csv_via_window_b()

    assert "open" in calls
    assert "refresh_all" in calls
    assert "refresh_history" in calls
    assert "save" in calls and "load" in calls
    assert "export_all" in calls and "export_selected" in calls


def test_window_b_manager_no_longer_calls_viewer_private_panel_builders() -> None:
    source = Path("window_b_manager.py").read_text(encoding="utf-8")
    assert "viewer._build_analysis_results_panel" not in source
    assert "viewer._build_results_history_panel" not in source
    assert "build_window_b_analysis_panel" in source
    assert "build_window_b_history_panel" in source


def test_window_b_panel_factory_declares_adapter_boundary() -> None:
    source = Path("window_b_panel_factory.py").read_text(encoding="utf-8")
    assert "class WindowBViewerAdapter(Protocol)" in source
    assert "[viewer_adapter 의존]" in source


def test_legacy_builder_call_paths_are_auditable() -> None:
    source = Path("dicom_viewer.py").read_text(encoding="utf-8")
    assert source.count("_build_analysis_results_panel(") == 2  # definition + single call site
    assert source.count("_build_results_history_panel(") == 1  # definition only
    assert "[DEPRECATED]" in source
