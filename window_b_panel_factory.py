from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Protocol


class WindowBViewerAdapter(Protocol):
    """
    Window B panel factory 전용 최소 adapter 인터페이스.

    원칙:
    - controller/business logic를 수행하지 않는다.
    - 데이터 가공을 수행하지 않는다.
    - viewer callback/속성을 얇게 전달한다.
    """

    ui_colors: dict[str, str]
    history_metric_filter_var: Any
    history_search_var: Any

    analysis_results_table: Any
    analysis_results_canvas: Any
    analysis_results_rows_container: Any
    result_history_table: Any
    history_compare_button: Any

    def _relayout_analysis_result_rows(self) -> None: ...
    def _build_grouped_toolbar_strip(self, parent: ttk.Frame) -> ttk.Frame: ...
    def _build_signal_analysis_toolbar(self, strip: ttk.Frame) -> None: ...
    def _build_image_analysis_toolbar(self, tab: ttk.Frame) -> None: ...
    def _initialize_analysis_ui_bindings(self) -> None: ...
    def _refresh_result_history_table(self) -> None: ...
    def _on_history_row_selected(self, event: tk.Event) -> None: ...
    def delete_selected_history_rows(self) -> None: ...
    def clear_result_history(self) -> None: ...
    def copy_result_history_to_clipboard(self) -> None: ...
    def export_selected_result_history_csv(self) -> None: ...
    def export_result_history_csv(self) -> None: ...
    def compare_selected_history_rows(self) -> None: ...
    def export_analysis_results_csv(self) -> None: ...
    def export_analysis_results_json(self) -> None: ...
    def save_analysis_session(self) -> None: ...
    def load_analysis_session(self) -> None: ...
    def _reset_analysis_session_state(self) -> None: ...


def build_window_b_analysis_panel(
    parent: ttk.Frame,
    viewer_adapter: WindowBViewerAdapter,
    store: Any,
    analysis_controller: Any,
) -> ttk.Frame:
    panel = ttk.Frame(parent)
    panel.pack(fill="both", expand=True)
    panel.grid_rowconfigure(0, weight=1)
    panel.grid_columnconfigure(0, weight=1)

    outer_canvas = tk.Canvas(panel, highlightthickness=0, bd=0)
    outer_canvas.grid(row=0, column=0, sticky="nsew")
    outer_scrollbar = ttk.Scrollbar(panel, orient="vertical", command=outer_canvas.yview)
    outer_scrollbar.grid(row=0, column=1, sticky="ns")
    outer_canvas.configure(yscrollcommand=outer_scrollbar.set)

    content_frame = ttk.Frame(outer_canvas)
    content_window = outer_canvas.create_window((0, 0), window=content_frame, anchor="nw")

    def _sync_outer_scroll_region(_event: tk.Event) -> None:
        outer_canvas.configure(scrollregion=outer_canvas.bbox("all"))

    def _sync_outer_content_width(event: tk.Event) -> None:
        outer_canvas.itemconfigure(content_window, width=event.width)

    content_frame.bind("<Configure>", _sync_outer_scroll_region)
    outer_canvas.bind("<Configure>", _sync_outer_content_width)

    analysis_notebook = ttk.Notebook(content_frame)
    analysis_notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
    signal_tab = ttk.Frame(analysis_notebook, padding=(4, 4, 4, 4))
    image_tab = ttk.Frame(analysis_notebook, padding=(4, 4, 4, 4))
    analysis_notebook.add(signal_tab, text="Signal Analysis")
    analysis_notebook.add(image_tab, text="Image Analysis")

    signal_container = ttk.Frame(signal_tab)
    signal_container.pack(fill="both", expand=True)
    viewer_adapter._build_signal_analysis_toolbar(signal_container)
    viewer_adapter._build_image_analysis_toolbar(image_tab)
    viewer_adapter._initialize_analysis_ui_bindings()

    results_panel = ttk.LabelFrame(content_frame, text="Analysis Results", padding=(8, 6))
    results_panel.grid(row=1, column=0, sticky="nsew")
    header = ttk.Frame(results_panel)
    header.grid(row=0, column=0, sticky="ew", columnspan=2)
    header.columnconfigure(0, weight=1, minsize=340)
    header.columnconfigure(1, weight=0, minsize=190)
    header.columnconfigure(2, weight=0, minsize=130)
    ttk.Label(header, text="ROI / Analysis / Metric", anchor="w").grid(row=0, column=0, sticky="ew", padx=(2, 8))
    ttk.Label(header, text="Result", anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 8))
    ttk.Label(header, text="Status / Remark", anchor="w").grid(row=0, column=2, sticky="ew")

    canvas = tk.Canvas(
        results_panel,
        background="#FFFFFF",
        highlightthickness=1,
        # [viewer_adapter 의존]
        # 목적: Window B 패널 색상값을 viewer UI 테마와 동일하게 유지
        # 분류: UI refresh / viewport styling
        # 향후: Window B 전용 theme provider로 분리 가능
        highlightbackground=viewer_adapter.ui_colors["border"],
        bd=0,
    )
    canvas.grid(row=1, column=0, sticky="nsew", columnspan=2)
    scrollbar = ttk.Scrollbar(results_panel, orient="vertical", command=canvas.yview)
    scrollbar.grid(row=1, column=2, sticky="ns")
    canvas.configure(yscrollcommand=scrollbar.set)

    rows_container = ttk.Frame(canvas)
    rows_window = canvas.create_window((0, 0), window=rows_container, anchor="nw")

    def _sync_scroll_region(_event: tk.Event) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _sync_row_container_width(_event: tk.Event) -> None:
        canvas.itemconfigure(rows_window, width=_event.width)
        # [viewer_adapter 의존]
        # 목적: 결과 행 레이아웃 재정렬 callback 위임
        # 분류: UI refresh
        # 향후: panel-local relayout helper로 분리 가능
        viewer_adapter._relayout_analysis_result_rows()

    rows_container.bind("<Configure>", _sync_scroll_region)
    canvas.bind("<Configure>", _sync_row_container_width)

    def _is_descendant_of_results_panel(widget: tk.Misc | None) -> bool:
        current = widget
        while current is not None:
            if current == results_panel:
                return True
            current = current.master
        return False

    def _scroll_results_canvas(units: int) -> None:
        if units != 0:
            canvas.yview_scroll(units, "units")

    def _on_results_mousewheel(event: tk.Event) -> str | None:
        if not _is_descendant_of_results_panel(event.widget):
            return None
        delta = int(event.delta)
        if delta == 0:
            return "break"
        _scroll_results_canvas(int(-delta / 120))
        return "break"

    def _on_results_button4(_event: tk.Event) -> str | None:
        _scroll_results_canvas(-1)
        return "break"

    def _on_results_button5(_event: tk.Event) -> str | None:
        _scroll_results_canvas(1)
        return "break"

    canvas.bind_all("<MouseWheel>", _on_results_mousewheel, add="+")
    rows_container.bind_all(
        "<Button-4>",
        lambda event: _on_results_button4(event) if _is_descendant_of_results_panel(event.widget) else None,
        add="+",
    )
    rows_container.bind_all(
        "<Button-5>",
        lambda event: _on_results_button5(event) if _is_descendant_of_results_panel(event.widget) else None,
        add="+",
    )

    # [viewer_adapter 의존]
    # 목적: 기존 export callback 의미를 변경 없이 전달
    # 분류: report/export callback
    # 향후: report controller action entrypoint로 직접 연결 가능
    ttk.Button(results_panel, text="Export Results CSV", command=viewer_adapter.export_analysis_results_csv).grid(row=2, column=0, sticky="ew", pady=(6, 0), padx=(0, 4))
    ttk.Button(results_panel, text="Export Results JSON", command=viewer_adapter.export_analysis_results_json).grid(row=2, column=1, sticky="ew", pady=(6, 0), padx=(4, 0))
    results_panel.grid_columnconfigure(0, weight=1)
    results_panel.grid_columnconfigure(1, weight=1)
    results_panel.grid_rowconfigure(1, weight=1)
    content_frame.grid_columnconfigure(0, weight=1)
    content_frame.grid_rowconfigure(0, weight=0)
    content_frame.grid_rowconfigure(1, weight=1)

    def _is_descendant_of_content(widget: tk.Misc | None) -> bool:
        current = widget
        while current is not None:
            if current == content_frame:
                return True
            current = current.master
        return False

    def _is_descendant_of_treeview(widget: tk.Misc | None) -> bool:
        current = widget
        while current is not None:
            if isinstance(current, ttk.Treeview):
                return True
            current = current.master
        return False

    def _scroll_outer_canvas(units: int) -> None:
        if units == 0:
            return
        top, bottom = outer_canvas.yview()
        viewport_span = bottom - top
        if viewport_span >= 1.0:
            return
        if units < 0 and top <= 0.0:
            return
        if units > 0 and bottom >= 1.0:
            return
        outer_canvas.yview_scroll(units, "units")

        clamped_top, clamped_bottom = outer_canvas.yview()
        if clamped_top < 0.0:
            outer_canvas.yview_moveto(0.0)
        elif clamped_bottom > 1.0:
            clamped_span = clamped_bottom - clamped_top
            outer_canvas.yview_moveto(max(0.0, 1.0 - clamped_span))

        content_coords = outer_canvas.coords(content_window)
        if len(content_coords) >= 2 and content_coords[1] > 0.0:
            outer_canvas.coords(content_window, content_coords[0], 0.0)

    def _on_outer_mousewheel(event: tk.Event) -> str | None:
        if not _is_descendant_of_content(event.widget):
            return None
        if _is_descendant_of_results_panel(event.widget) or _is_descendant_of_treeview(event.widget):
            return None
        delta = int(event.delta)
        if delta == 0:
            return "break"
        _scroll_outer_canvas(int(-delta / 120))
        return "break"

    outer_canvas.bind_all("<MouseWheel>", _on_outer_mousewheel, add="+")
    outer_canvas.bind_all(
        "<Button-4>",
        lambda event: (_scroll_outer_canvas(-1), "break")[1]
        if _is_descendant_of_content(event.widget)
        and not _is_descendant_of_results_panel(event.widget)
        and not _is_descendant_of_treeview(event.widget)
        else None,
        add="+",
    )
    outer_canvas.bind_all(
        "<Button-5>",
        lambda event: (_scroll_outer_canvas(1), "break")[1]
        if _is_descendant_of_content(event.widget)
        and not _is_descendant_of_results_panel(event.widget)
        and not _is_descendant_of_treeview(event.widget)
        else None,
        add="+",
    )
    # [viewer_adapter 의존]
    # 목적: 기존 viewer 기반 refresh 루프에서 참조하는 widget 핸들 등록
    # 분류: legacy compatibility
    # 향후: Window B 전용 view-state 객체로 대체 가능
    viewer_adapter.analysis_results_table = results_panel
    viewer_adapter.analysis_results_canvas = canvas
    viewer_adapter.analysis_results_rows_container = rows_container
    return panel


def build_window_b_history_panel(
    parent: ttk.Frame,
    viewer_adapter: WindowBViewerAdapter,
    store: Any,
    history_controller: Any,
) -> ttk.Frame:
    panel = ttk.LabelFrame(parent, text="Measurement History", padding=(8, 6))
    panel.pack(fill="both", expand=True)
    toolbar = ttk.Frame(panel)
    toolbar.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 6))
    ttk.Label(toolbar, text="Type Filter").pack(side="left")
    # [viewer_adapter 의존]
    # 목적: 기존 history filter/search tk variable를 재사용
    # 분류: selection / filter state
    # 향후: Window B state container로 분리 가능
    filter_combo = ttk.Combobox(
        toolbar,
        state="readonly",
        width=16,
        values=["All", "ROI", "Analysis", "Line Profile"],
        textvariable=viewer_adapter.history_metric_filter_var,
    )
    filter_combo.pack(side="left", padx=(6, 12))
    # [viewer_adapter 의존]
    # 목적: 필터 변경 시 기존 targeted refresh callback 호출
    # 분류: UI refresh
    # 향후: history service + event hook으로 치환 가능
    filter_combo.bind("<<ComboboxSelected>>", lambda _event: viewer_adapter._refresh_result_history_table())
    ttk.Label(toolbar, text="Search").pack(side="left")
    search_entry = ttk.Entry(toolbar, textvariable=viewer_adapter.history_search_var, width=32)
    search_entry.pack(side="left", padx=(6, 0))
    search_entry.bind("<KeyRelease>", lambda _event: viewer_adapter._refresh_result_history_table())
    columns = (
        "timestamp",
        "image",
        "frame",
        "type",
        "target",
        "metric",
        "value",
        "mean",
        "std",
        "min",
        "max",
        "area",
        "length_px",
        "length_mm",
        "peaks",
        "valleys",
        "unit",
        "note",
    )
    tree = ttk.Treeview(panel, columns=columns, show="headings", height=16, selectmode="extended", style="ResultHistory.Treeview")
    headers = {
        "timestamp": "Timestamp",
        "image": "Image Name",
        "frame": "Frame Index",
        "type": "Measurement Type",
        "target": "ROI / Line Name",
        "metric": "Metric",
        "value": "Value",
        "mean": "Mean",
        "std": "Std",
        "min": "Min",
        "max": "Max",
        "area": "Area",
        "length_px": "Length(px)",
        "length_mm": "Length(mm)",
        "peaks": "Peaks",
        "valleys": "Valleys",
        "unit": "Unit",
        "note": "Note",
    }
    widths = {
        "timestamp": 170,
        "image": 160,
        "frame": 90,
        "type": 140,
        "target": 140,
        "metric": 120,
        "value": 90,
        "mean": 90,
        "std": 90,
        "min": 90,
        "max": 90,
        "area": 90,
        "length_px": 95,
        "length_mm": 95,
        "peaks": 80,
        "valleys": 80,
        "unit": 90,
        "note": 320,
    }
    for key in columns:
        tree.heading(key, text=headers[key])
        tree.column(key, width=widths[key], anchor="w")
    tree.grid(row=1, column=0, columnspan=5, sticky="nsew")
    # [viewer_adapter 의존]
    # 목적: history row selection 콜백 의미를 기존과 동일 유지
    # 분류: selection callback
    # 향후: Window B 전용 selection handler로 분리 가능
    tree.bind("<<TreeviewSelect>>", viewer_adapter._on_history_row_selected, add="+")
    scrollbar = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
    scrollbar.grid(row=1, column=5, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)
    # [viewer_adapter 의존]
    # 목적: History action callback을 기존 viewer 경로로 그대로 위임
    # 분류: session/history action callback, report/export callback
    # 향후: history/report controller action entrypoint 직접 연결 가능
    ttk.Button(panel, text="Delete Selected", command=viewer_adapter.delete_selected_history_rows).grid(row=2, column=0, sticky="ew", pady=(6, 0), padx=(0, 4))
    ttk.Button(panel, text="Clear All", command=viewer_adapter.clear_result_history).grid(row=2, column=1, sticky="ew", pady=(6, 0), padx=4)
    ttk.Button(panel, text="Copy Clipboard", command=viewer_adapter.copy_result_history_to_clipboard).grid(row=2, column=2, sticky="ew", pady=(6, 0), padx=4)
    ttk.Button(panel, text="Export Selected CSV", command=viewer_adapter.export_selected_result_history_csv).grid(row=2, column=3, sticky="ew", pady=(6, 0), padx=4)
    ttk.Button(panel, text="Export All CSV", command=viewer_adapter.export_result_history_csv).grid(row=2, column=4, sticky="ew", pady=(6, 0), padx=(4, 0))
    compare_button = ttk.Button(panel, text="Compare Selected", command=viewer_adapter.compare_selected_history_rows, state="disabled")
    compare_button.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(6, 0))
    for col in range(5):
        panel.grid_columnconfigure(col, weight=1)
    panel.grid_rowconfigure(1, weight=1)
    # [viewer_adapter 의존]
    # 목적: 기존 viewer refresh/compare가 참조하는 widget 핸들 등록
    # 분류: legacy compatibility
    # 향후: Window B 전용 table state 객체 도입 시 제거 가능
    viewer_adapter.result_history_table = tree
    viewer_adapter.history_compare_button = compare_button
    return panel


def build_window_b_session_panel(
    parent: ttk.Frame,
    viewer_adapter: WindowBViewerAdapter,
    store: Any,
    session_controller: Any,
) -> ttk.Frame:
    row = ttk.Frame(parent)
    row.pack(fill="x", anchor="nw")
    ttk.Label(row, text="Session Actions").pack(side="left")
    # [viewer_adapter 의존]
    # 목적: session action callback을 기존 의미 그대로 전달
    # 분류: session callback
    # 향후: session controller action provider 직접 매핑 가능
    ttk.Button(row, text="Save Session", command=viewer_adapter.save_analysis_session).pack(side="left", padx=(12, 4))
    ttk.Button(row, text="Load Session", command=viewer_adapter.load_analysis_session).pack(side="left", padx=4)
    ttk.Button(row, text="Reset Session", command=viewer_adapter._reset_analysis_session_state).pack(side="left", padx=4)
    return row


def build_window_b_report_panel(
    parent: ttk.Frame,
    viewer_adapter: WindowBViewerAdapter,
    store: Any,
    report_controller: Any,
) -> ttk.Frame:
    row = ttk.Frame(parent)
    row.pack(fill="x", anchor="nw")
    ttk.Label(row, text="Report / Export").pack(side="left")
    # [viewer_adapter 의존]
    # 목적: report/export callback을 기존 실행 경로 그대로 유지
    # 분류: report/export callback
    # 향후: report controller action provider로 직접 연결 가능
    ttk.Button(row, text="Export Analysis JSON", command=viewer_adapter.export_analysis_results_json).pack(side="left", padx=(12, 4))
    ttk.Button(row, text="Export Analysis CSV", command=viewer_adapter.export_analysis_results_csv).pack(side="left", padx=4)
    ttk.Button(row, text="Export Selected History CSV", command=viewer_adapter.export_selected_result_history_csv).pack(side="left", padx=4)
    ttk.Button(row, text="Export All History CSV", command=viewer_adapter.export_result_history_csv).pack(side="left", padx=4)
    return row
