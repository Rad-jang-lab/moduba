import types

from dicom_viewer import DicomViewer, ROI_SELECTION_HIT_RADIUS_PX, RESIZE_GRIP_HIT_SIZE_PX
from domain_store import DomainStore
from window_b_manager import WindowBManager


class DummyEvent:
    def __init__(self, x=0, y=0, state=0):
        self.x = x
        self.y = y
        self.state = state


class DummyCanvas:
    def __init__(self):
        self.deleted = []
        self.overlap_args = None

    def canvasx(self, x):
        return float(x)

    def canvasy(self, y):
        return float(y)

    def coords(self, *_args):
        return None

    def delete(self, item_id):
        self.deleted.append(item_id)

    def find_overlapping(self, x0, y0, x1, y1):
        self.overlap_args = (x0, y0, x1, y1)
        return [101]


def _build_finish_viewer(mode: str = "roi") -> DicomViewer:
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.measurement_mode = types.SimpleNamespace(get=lambda: mode)
    viewer.roi_draw_mode = types.SimpleNamespace(get=lambda: "free")
    viewer.canvas = DummyCanvas()
    viewer._active_preview_measurement = {"mode": mode, "item_id": 1, "start": (1.0, 2.0), "end": (3.0, 4.0)}
    viewer._canvas_to_image_pixel = lambda x, y: (int(x), int(y))
    viewer._update_preview_measurement = lambda event: None
    viewer._draw_preview_measurements = lambda: None
    viewer._draw_persistent_measurements = lambda: None
    viewer._update_guided_snr_selection = lambda measurement: None
    viewer._refresh_analysis_selectors_called = 0
    viewer._update_analysis_action_button_state_called = 0
    viewer._refresh_analysis_selectors = lambda: setattr(
        viewer, "_refresh_analysis_selectors_called", viewer._refresh_analysis_selectors_called + 1
    )
    viewer._update_analysis_action_button_state = lambda: setattr(
        viewer,
        "_update_analysis_action_button_state_called",
        viewer._update_analysis_action_button_state_called + 1,
    )
    return viewer


def test_finish_free_roi_selects_created_roi():
    viewer = _build_finish_viewer("roi")
    selection_calls = []
    viewer._apply_measurement_selection = lambda measurement_id, toggle=False: selection_calls.append((measurement_id, toggle))
    measurement = types.SimpleNamespace(id="roi-new")
    viewer._append_persistent_measurement = lambda *_args, **_kwargs: measurement

    viewer._finish_preview_measurement(DummyEvent())

    assert selection_calls == [("roi-new", False)]


def test_finish_free_roi_refreshes_analysis_selectors():
    viewer = _build_finish_viewer("roi")
    viewer._apply_measurement_selection = lambda *_args, **_kwargs: None
    viewer._append_persistent_measurement = lambda *_args, **_kwargs: types.SimpleNamespace(id="roi-new")

    viewer._finish_preview_measurement(DummyEvent())

    assert viewer._refresh_analysis_selectors_called == 1
    assert viewer._update_analysis_action_button_state_called == 1


def test_line_measurement_does_not_trigger_roi_auto_selection_policy():
    viewer = _build_finish_viewer("line")
    selection_calls = []
    viewer._apply_measurement_selection = lambda measurement_id, toggle=False: selection_calls.append((measurement_id, toggle))
    viewer._append_persistent_measurement = lambda *_args, **_kwargs: types.SimpleNamespace(id="line-new")

    viewer._finish_preview_measurement(DummyEvent())

    assert selection_calls == []
    assert viewer._refresh_analysis_selectors_called == 0


def test_apply_measurement_selection_updates_domain_store_selection():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer.selected_persistent_measurement_id = None

    viewer._apply_measurement_selection("roi-new", toggle=False)

    assert viewer.selected_persistent_measurement_id == "roi-new"
    assert viewer.domain_store.state.selected_measurement_ids == ["roi-new"]


def test_finish_free_roi_updates_domain_store_selection():
    viewer = _build_finish_viewer("roi")
    viewer.domain_store = DomainStore()
    viewer._store_image_id = viewer.domain_store.add_image_context("/tmp/a.dcm", "a")
    viewer.selected_persistent_measurement_id = None
    viewer._append_persistent_measurement = lambda *_args, **_kwargs: types.SimpleNamespace(id="roi-new")
    viewer._apply_measurement_selection = DicomViewer._apply_measurement_selection.__get__(viewer, DicomViewer)

    viewer._finish_preview_measurement(DummyEvent())

    assert viewer.selected_persistent_measurement_id == "roi-new"
    assert viewer.domain_store.state.selected_measurement_ids == ["roi-new"]


def test_roi_selection_hit_radius_is_expanded():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.view_mode = "single"
    viewer.canvas = DummyCanvas()
    viewer._persistent_canvas_item_to_measurement_id = {101: "roi-1"}
    calls = []
    viewer._apply_measurement_selection = lambda measurement_id: calls.append(measurement_id)
    viewer._draw_persistent_measurements = lambda: None

    selected = viewer._select_persistent_measurement_at_event(DummyEvent(100, 200))

    assert selected is True
    assert calls == ["roi-1"]
    assert ROI_SELECTION_HIT_RADIUS_PX > 3
    assert viewer.canvas.overlap_args == (
        100 - ROI_SELECTION_HIT_RADIUS_PX,
        200 - ROI_SELECTION_HIT_RADIUS_PX,
        100 + ROI_SELECTION_HIT_RADIUS_PX,
        200 + ROI_SELECTION_HIT_RADIUS_PX,
    )


def test_attach_resize_grip_adds_sizegrip_to_root(monkeypatch):
    created = []

    class FakeFrame:
        def __init__(self, _window, width, height):
            created.append(("frame", width, height))

        def place(self, **kwargs):
            created.append(("place", kwargs))

        def place_propagate(self, flag):
            created.append(("propagate", flag))

        def lift(self):
            created.append(("lift",))

    class FakeSizegrip:
        def __init__(self, _parent):
            created.append(("sizegrip",))

        def pack(self, **kwargs):
            created.append(("pack", kwargs))

    monkeypatch.setattr("dicom_viewer.ttk.Frame", FakeFrame)
    monkeypatch.setattr("dicom_viewer.ttk.Sizegrip", FakeSizegrip)

    DicomViewer._attach_resize_grip(object())

    assert ("frame", RESIZE_GRIP_HIT_SIZE_PX, RESIZE_GRIP_HIT_SIZE_PX) in created
    assert any(item[0] == "sizegrip" for item in created)


def test_resize_grip_helper_handles_destroyed_window_safely(monkeypatch):
    class FakeFrame:
        def __init__(self, *_args, **_kwargs):
            pass

        def place(self, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("dicom_viewer.ttk.Frame", FakeFrame)
    monkeypatch.setattr("dicom_viewer.tk.TclError", RuntimeError)

    # no exception
    DicomViewer._attach_resize_grip(object())


def test_grid_roi_still_selects_created_roi():
    viewer = DicomViewer.__new__(DicomViewer)
    viewer.canvas = types.SimpleNamespace(canvasx=lambda x: float(x), canvasy=lambda y: float(y))
    viewer.get_grid_cell = lambda _x, _y: (2, 3)
    viewer._find_grid_roi_measurement_id_from_cell = lambda _row, _col: None
    viewer.select_roi_from_grid = lambda _row, _col: types.SimpleNamespace(id="grid-roi-1")
    selected_calls = []
    viewer._apply_measurement_selection = lambda measurement_id, toggle=False: selected_calls.append((measurement_id, toggle))
    viewer._show_frame = lambda: None

    viewer._create_grid_aligned_roi(DummyEvent(20, 40, 0))

    assert selected_calls == [("grid-roi-1", False)]


def test_window_b_create_window_adds_resize_grip(monkeypatch):
    calls = []

    monkeypatch.setattr(WindowBManager, "_attach_resize_grip", lambda self, window: calls.append(window))
    monkeypatch.setattr("window_b_manager.build_window_b_analysis_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr("window_b_manager.build_window_b_history_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr("window_b_manager.build_window_b_session_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr("window_b_manager.build_window_b_report_panel", lambda *args, **kwargs: None)

    class FakeWindow:
        def title(self, *_args):
            return None

        def geometry(self, *_args):
            return None

        def protocol(self, *_args):
            return None

        def rowconfigure(self, *_args, **_kwargs):
            return None

        def columnconfigure(self, *_args, **_kwargs):
            return None

        def winfo_exists(self):
            return True

        def winfo_viewable(self):
            return True

    class FakeNotebook:
        def __init__(self, _window):
            pass

        def grid(self, **_kwargs):
            return None

        def add(self, *_args, **_kwargs):
            return None

    class FakeFrame:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("window_b_manager.tk.Toplevel", lambda _root: FakeWindow())
    monkeypatch.setattr("window_b_manager.ttk.Notebook", FakeNotebook)
    monkeypatch.setattr("window_b_manager.ttk.Frame", FakeFrame)

    viewer = types.SimpleNamespace(
        domain_store=DomainStore(),
        analysis_result_controller=object(),
        history_controller=object(),
        session_controller=object(),
        report_export_controller=object(),
        _refresh_analysis_results_panel=lambda: None,
        _refresh_result_history_table=lambda: None,
    )
    manager = WindowBManager(root=object(), viewer=viewer)
    manager._create_window()

    assert len(calls) == 1
