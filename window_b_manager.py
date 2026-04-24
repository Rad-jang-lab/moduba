from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable
from window_b_panel_factory import (
    build_window_b_analysis_panel,
    build_window_b_history_panel,
    build_window_b_session_panel,
    build_window_b_report_panel,
)


class WindowBManager:
    """Window B lifecycle manager (single Toplevel instance, withdraw/reopen strategy)."""

    def __init__(self, root: tk.Tk, viewer: Any) -> None:
        self.root = root
        self.viewer = viewer
        self._window: tk.Toplevel | None = None
        self._dirty_while_closed = False
        self._is_built = False

    def open(self) -> None:
        if self._window is None or not self._window.winfo_exists():
            self._create_window()
        assert self._window is not None
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()
        if self._dirty_while_closed:
            self.refresh_all()
            self._dirty_while_closed = False

    def close(self) -> None:
        if self._window is None or not self._window.winfo_exists():
            return
        self._window.withdraw()

    def is_open(self) -> bool:
        if self._window is None or not self._window.winfo_exists():
            return False
        return bool(self._window.winfo_viewable())

    def mark_dirty(self) -> None:
        self._dirty_while_closed = True

    def refresh_all(self) -> None:
        if not self.is_open():
            self.mark_dirty()
            return
        # selector re-query 기반 targeted refresh
        self.viewer._refresh_analysis_results_panel()
        self.viewer._refresh_result_history_table()

    def refresh_history(self) -> None:
        if not self.is_open():
            self.mark_dirty()
            return
        self.viewer._refresh_result_history_table()

    def _create_window(self) -> None:
        self._window = tk.Toplevel(self.root)
        self._window.title("Window B - Analysis / History / Session / Report")
        self._window.geometry("1080x760")
        # 장시간 유지 작업창 정책: transient 미사용 (taskbar 독립 유지)
        self._window.protocol("WM_DELETE_WINDOW", self.close)
        self._window.rowconfigure(0, weight=1)
        self._window.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(self._window)
        notebook.grid(row=0, column=0, sticky="nsew")

        analysis_tab = ttk.Frame(notebook, padding=(8, 8))
        history_tab = ttk.Frame(notebook, padding=(8, 8))
        session_tab = ttk.Frame(notebook, padding=(8, 8))
        report_tab = ttk.Frame(notebook, padding=(8, 8))
        notebook.add(analysis_tab, text="Analysis")
        notebook.add(history_tab, text="History")
        notebook.add(session_tab, text="Session")
        notebook.add(report_tab, text="Report")

        build_window_b_analysis_panel(
            analysis_tab,
            viewer_adapter=self.viewer,
            store=self.viewer.domain_store,
            analysis_controller=self.viewer.analysis_result_controller,
        )
        build_window_b_history_panel(
            history_tab,
            viewer_adapter=self.viewer,
            store=self.viewer.domain_store,
            history_controller=self.viewer.history_controller,
        )
        build_window_b_session_panel(
            session_tab,
            viewer_adapter=self.viewer,
            store=self.viewer.domain_store,
            session_controller=self.viewer.session_controller,
        )
        build_window_b_report_panel(
            report_tab,
            viewer_adapter=self.viewer,
            store=self.viewer.domain_store,
            report_controller=self.viewer.report_export_controller,
        )
        self._is_built = True
        self.refresh_all()

    def bind_store_events(self) -> None:
        event_map: dict[str, Callable[[dict[str, Any]], None]] = {
            "measurement_added": lambda _meta: self.refresh_all(),
            "measurement_updated": lambda _meta: self.refresh_all(),
            "measurement_deleted": lambda _meta: self.refresh_all(),
            "frame_changed": lambda _meta: self.refresh_all(),
            "selection_changed": lambda _meta: self.refresh_all(),
            "role_changed": lambda _meta: self.refresh_all(),
            "analysis_completed": lambda _meta: self.refresh_all(),
            "session_loaded": lambda _meta: self.refresh_all(),
        }
        for event_name, handler in event_map.items():
            self.viewer.domain_store.events.subscribe(event_name, handler)
