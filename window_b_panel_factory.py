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
    current_threshold_config: Any
    current_dicom_batch_execution_result: Any
    current_dicom_batch_execution_plan: Any
    current_dicom_batch_history_records: Any
    current_batch_qc_run: Any
    current_batch_qc_report_model: Any

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
    def get_dicom_batch_execution_result_summary_for_viewer(self, execution_result: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def render_dicom_batch_workspace_summary_text_for_viewer(self, execution_result: dict[str, Any] | None = None) -> str: ...
    def build_dicom_batch_history_records_for_viewer(self, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]]: ...
    def append_dicom_batch_history_records_for_viewer(self, history_path: str | None = None, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]] | None: ...
    def build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(self, execution_result: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]: ...
    def show_dicom_batch_history_bridge_viewer(self, execution_result: dict[str, Any] | None = None) -> str: ...
    def render_current_batch_qc_report_text_for_viewer(self, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str: ...
    def export_current_batch_qc_run_json_for_viewer(self, path: str | None = None) -> str | None: ...
    def export_current_batch_qc_run_csv_for_viewer(self, path: str | None = None) -> str | None: ...
    def export_current_batch_qc_report_text_for_viewer(self, path: str | None = None, metadata: dict[str, Any] | None = None) -> str | None: ...
    def export_current_batch_qc_report_pdf_for_viewer(self, path: str | None = None, metadata: dict[str, Any] | None = None) -> bytes | None: ...
    def show_current_batch_qc_report_viewer(self) -> str: ...
    def build_current_dicom_batch_execution_plan_for_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def run_current_dicom_batch_execution_plan_for_viewer(self, execution_plan: dict[str, Any] | None = None, analysis_executor: Any = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def get_dicom_batch_execution_plan_summary_for_viewer(self, execution_plan: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def render_dicom_batch_run_workspace_summary_text_for_viewer(self, execution_plan: dict[str, Any] | None = None, execution_result: dict[str, Any] | None = None) -> str: ...
    def preview_current_dicom_batch_execution_result_for_viewer(self, execution_result: dict[str, Any] | None = None) -> str: ...
    def create_dicom_batch_pixel_analysis_executor_for_viewer(self): ...
    def run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(self, execution_plan: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def preview_current_dicom_batch_pixel_executor_capability_for_viewer(self) -> str: ...
    def build_normalized_dicom_batch_execution_result_for_viewer(self, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> dict[str, Any]: ...
    def render_normalized_dicom_batch_execution_result_text_for_viewer(self, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> str: ...
    def export_normalized_dicom_batch_execution_result_json_for_viewer(self, path: str | None = None, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> str | None: ...
    def export_normalized_dicom_batch_execution_result_csv_for_viewer(self, path: str | None = None, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> str | None: ...
    def build_analysis_history_records_from_normalized_execution_for_viewer(self, normalized_execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]]: ...
    def append_normalized_execution_history_records_for_viewer(self, history_path: str | None = None, normalized_execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]] | None: ...
    def build_batch_qc_run_from_normalized_execution_for_viewer(self, normalized_execution_result: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, record_id_prefix: str | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]: ...
    def render_normalized_batch_qc_report_text_for_viewer(self, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str: ...
    def export_normalized_batch_qc_report_json_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str | None: ...
    def export_normalized_batch_qc_report_csv_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str | None: ...
    def export_normalized_batch_qc_report_text_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str | None: ...
    def export_normalized_batch_qc_report_pdf_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> bytes | None: ...
    def render_normalized_batch_workflow_summary_text_for_viewer(self) -> str: ...


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
    ttk.Label(header, text="Formula / Calculation", anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 8))
    ttk.Label(header, text="Result", anchor="w").grid(row=0, column=2, sticky="ew")

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


def build_window_b_batch_panel(
    parent: ttk.Frame,
    viewer_adapter: WindowBViewerAdapter,
    store: Any,
    batch_controller: Any = None,
) -> ttk.Frame:
    panel = ttk.Frame(parent, padding=(8, 8))
    panel.pack(fill="both", expand=True)
    panel.grid_columnconfigure(0, weight=1)
    panel.grid_rowconfigure(2, weight=1)

    summary = ttk.LabelFrame(panel, text="DICOM Batch Execution", padding=(8, 6))
    summary.grid(row=0, column=0, sticky="ew")
    summary_text_var = tk.StringVar(value="")
    ttk.Label(summary, textvariable=summary_text_var, justify="left", anchor="w").pack(fill="x")

    actions = ttk.Frame(panel)
    actions.grid(row=1, column=0, sticky="ew", pady=(8, 8))
    selected_threshold_var = tk.BooleanVar(value=False)
    strict_roi_var = tk.BooleanVar(value=bool(getattr(viewer_adapter, "current_dicom_batch_strict_roi_validation", False)))

    preview_frame = ttk.LabelFrame(panel, text="Batch Bridge Preview", padding=(8, 6))
    preview_frame.grid(row=2, column=0, sticky="nsew")
    preview_frame.grid_columnconfigure(0, weight=1)
    preview_frame.grid_rowconfigure(0, weight=1)
    preview_text = tk.Text(preview_frame, wrap="word", height=16)
    preview_text.grid(row=0, column=0, sticky="nsew")
    preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_text.yview)
    preview_scroll.grid(row=0, column=1, sticky="ns")
    preview_text.configure(yscrollcommand=preview_scroll.set)

    def _set_preview_text(text: str) -> None:
        preview_text.configure(state="normal")
        preview_text.delete("1.0", "end")
        preview_text.insert("1.0", text)
        preview_text.configure(state="disabled")

    def _refresh() -> None:
        summary_obj = viewer_adapter.get_dicom_batch_execution_result_summary_for_viewer()
        summary_text_var.set(
            f"has_execution_result={summary_obj.get('has_execution_result')} | run_id={summary_obj.get('run_id')} | "
            f"execution_plan_id={summary_obj.get('execution_plan_id')} | items={summary_obj.get('item_count')} | tasks={summary_obj.get('task_count')} | "
            f"completed={summary_obj.get('completed_task_count')} blocked={summary_obj.get('blocked_task_count')} "
            f"not_executed={summary_obj.get('not_executed_task_count')} error={summary_obj.get('error_task_count')} | "
            f"bridge_records={summary_obj.get('history_record_count')} | has_batch_qc_run={summary_obj.get('has_batch_qc_run')}"
        )
        _set_preview_text(viewer_adapter.render_dicom_batch_workspace_summary_text_for_viewer())

    def _preview_bridge() -> None:
        try:
            text = viewer_adapter.show_dicom_batch_history_bridge_viewer()
        except Exception as exc:
            text = f"preview_error: {exc}"
        _set_preview_text(f"{text}\n\n{viewer_adapter.render_dicom_batch_workspace_summary_text_for_viewer()}")

    def _build_records() -> None:
        try:
            viewer_adapter.build_dicom_batch_history_records_for_viewer()
        except Exception as exc:
            _set_preview_text(f"build_history_records_error: {exc}")
            return
        _refresh()

    def _append_records() -> None:
        try:
            out = viewer_adapter.append_dicom_batch_history_records_for_viewer()
        except Exception as exc:
            _set_preview_text(f"append_history_error: {exc}")
            return
        if out is None:
            _set_preview_text("append cancelled by user")
            return
        _refresh()

    def _build_qc() -> None:
        try:
            viewer_adapter.build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(
                use_selected_threshold_config=bool(selected_threshold_var.get())
            )
        except Exception as exc:
            _set_preview_text(f"build_batch_qc_error: {exc}")
            return
        _refresh()

    ttk.Button(actions, text="Refresh Batch Summary", command=_refresh).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Preview History Bridge", command=_preview_bridge).pack(side="left", padx=6)
    ttk.Button(actions, text="Build History Records", command=_build_records).pack(side="left", padx=6)
    ttk.Button(actions, text="Append Records to History JSONL", command=_append_records).pack(side="left", padx=6)
    ttk.Button(actions, text="Build Batch QC Run", command=_build_qc).pack(side="left", padx=6)
    ttk.Checkbutton(actions, text="Use selected threshold config", variable=selected_threshold_var).pack(side="left", padx=(12, 0))

    normalized_actions = ttk.LabelFrame(panel, text="Normalized Batch Workflow", padding=(8, 6))
    normalized_actions.grid(row=5, column=0, sticky="ew", pady=(8, 0))

    def _run_normalized_action(prefix: str, callback) -> None:
        try:
            out = callback()
            if out is None:
                _set_preview_text(f"{prefix}: cancelled")
            elif isinstance(out, str):
                _set_preview_text(out)
            elif isinstance(out, (list, dict)):
                summary_text = viewer_adapter.render_normalized_batch_workflow_summary_text_for_viewer()
                _set_preview_text(f"{prefix}: ok\n{summary_text}")
            else:
                _set_preview_text(f"{prefix}: ok")
        except Exception as exc:
            _set_preview_text(f"{prefix}: {exc}")

    ttk.Button(normalized_actions, text="Build Normalized Execution", command=lambda: _run_normalized_action("build_normalized_execution", viewer_adapter.build_normalized_dicom_batch_execution_result_for_viewer)).pack(side="left", padx=(0, 6))
    ttk.Button(normalized_actions, text="Preview Normalized Execution", command=lambda: _run_normalized_action("preview_normalized_execution", viewer_adapter.render_normalized_dicom_batch_execution_result_text_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Export Normalized JSON", command=lambda: _run_normalized_action("export_normalized_execution_json", viewer_adapter.export_normalized_dicom_batch_execution_result_json_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Export Normalized CSV", command=lambda: _run_normalized_action("export_normalized_execution_csv", viewer_adapter.export_normalized_dicom_batch_execution_result_csv_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Build Normalized History Records", command=lambda: _run_normalized_action("build_normalized_history", viewer_adapter.build_analysis_history_records_from_normalized_execution_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Append Normalized History JSONL", command=lambda: _run_normalized_action("append_normalized_history", viewer_adapter.append_normalized_execution_history_records_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Build Normalized Batch QC Run", command=lambda: _run_normalized_action("build_normalized_batch_qc", lambda: viewer_adapter.build_batch_qc_run_from_normalized_execution_for_viewer(use_selected_threshold_config=bool(selected_threshold_var.get())))).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Preview Normalized Batch QC Report", command=lambda: _run_normalized_action("preview_normalized_batch_qc_report", viewer_adapter.render_normalized_batch_qc_report_text_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Export Normalized Report JSON", command=lambda: _run_normalized_action("export_normalized_batch_qc_report_json", viewer_adapter.export_normalized_batch_qc_report_json_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Export Normalized Report CSV", command=lambda: _run_normalized_action("export_normalized_batch_qc_report_csv", viewer_adapter.export_normalized_batch_qc_report_csv_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Export Normalized Report Text", command=lambda: _run_normalized_action("export_normalized_batch_qc_report_text", viewer_adapter.export_normalized_batch_qc_report_text_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Export Normalized Report PDF", command=lambda: _run_normalized_action("export_normalized_batch_qc_report_pdf", viewer_adapter.export_normalized_batch_qc_report_pdf_for_viewer)).pack(side="left", padx=6)
    ttk.Button(normalized_actions, text="Refresh Normalized Workflow Summary", command=lambda: _run_normalized_action("normalized_workflow_summary", viewer_adapter.render_normalized_batch_workflow_summary_text_for_viewer)).pack(side="left", padx=6)

    plan_run = ttk.LabelFrame(panel, text="Batch Execution Plan / Run", padding=(8, 6))
    plan_run.grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _build_plan() -> None:
        try:
            viewer_adapter.build_current_dicom_batch_execution_plan_for_viewer()
            _set_preview_text(viewer_adapter.render_dicom_batch_run_workspace_summary_text_for_viewer())
        except Exception as exc:
            _set_preview_text(f"build_execution_plan_error: {exc}")

    def _run_plan() -> None:
        try:
            viewer_adapter.run_current_dicom_batch_execution_plan_for_viewer()
            _set_preview_text(viewer_adapter.render_dicom_batch_run_workspace_summary_text_for_viewer())
        except Exception as exc:
            _set_preview_text(f"run_batch_execution_error: {exc}")

    def _preview_result() -> None:
        try:
            _set_preview_text(viewer_adapter.preview_current_dicom_batch_execution_result_for_viewer())
        except Exception as exc:
            _set_preview_text(f"preview_execution_result_error: {exc}")

    ttk.Button(plan_run, text="Build Execution Plan", command=_build_plan).pack(side="left", padx=(0, 6))
    ttk.Button(plan_run, text="Run Batch Execution", command=_run_plan).pack(side="left", padx=6)
    ttk.Button(plan_run, text="Preview Execution Result", command=_preview_result).pack(side="left", padx=6)
    def _refresh_workflow_readiness() -> None:
        try:
            _set_preview_text(viewer_adapter.preview_current_dicom_batch_workflow_readiness_for_viewer(strict_roi_role_validation=bool(strict_roi_var.get())))
        except Exception as exc:
            _set_preview_text(f"workflow_readiness_error: {exc}")

    def _on_strict_roi_toggle() -> None:
        try:
            viewer_adapter.set_current_dicom_batch_strict_roi_validation_for_viewer(bool(strict_roi_var.get()))
        except Exception:
            pass

    def _validate_roi_roles() -> None:
        try:
            _set_preview_text(viewer_adapter.preview_current_dicom_batch_roi_role_validation_for_viewer())
        except Exception as exc:
            _set_preview_text(f"validate_roi_roles_error: {exc}")

    ttk.Button(plan_run, text="Validate ROI Roles", command=_validate_roi_roles).pack(side="left", padx=6)
    ttk.Button(plan_run, text="Refresh Workflow Readiness", command=_refresh_workflow_readiness).pack(side="left", padx=6)
    def _check_pixel_executor() -> None:
        try:
            _set_preview_text(viewer_adapter.preview_current_dicom_batch_pixel_executor_capability_for_viewer())
        except Exception as exc:
            _set_preview_text(f"check_pixel_executor_error: {exc}")

    def _run_pixel_execution() -> None:
        try:
            viewer_adapter.run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(strict_roi_role_validation=bool(strict_roi_var.get()))
            _set_preview_text(viewer_adapter.preview_current_dicom_batch_execution_result_for_viewer())
        except Exception as exc:
            _set_preview_text(f"run_pixel_batch_execution_error: {exc}")

    ttk.Button(plan_run, text="Check Pixel Executor", command=_check_pixel_executor).pack(side="left", padx=6)
    ttk.Button(plan_run, text="Run Pixel Batch Execution", command=_run_pixel_execution).pack(side="left", padx=6)
    ttk.Checkbutton(plan_run, text="Require valid ROI roles before pixel run", variable=strict_roi_var, command=_on_strict_roi_toggle).pack(side="left", padx=(10, 0))

    report_actions = ttk.LabelFrame(panel, text="Batch QC Report / Export", padding=(8, 6))
    report_actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def _report_preview() -> None:
        try:
            text = viewer_adapter.show_current_batch_qc_report_viewer()
        except Exception as exc:
            text = f"preview_batch_qc_report_error: {exc}"
        _set_preview_text(text)

    def _run_action(fn_name: str) -> None:
        try:
            out = getattr(viewer_adapter, fn_name)()
            _set_preview_text(f"{fn_name}: {'cancelled' if out is None else 'ok'}")
        except Exception as exc:
            _set_preview_text(f"{fn_name}_error: {exc}")

    ttk.Button(report_actions, text="Preview Batch QC Report", command=_report_preview).pack(side="left", padx=(0, 6))
    ttk.Button(report_actions, text="Export Batch QC JSON", command=lambda: _run_action("export_current_batch_qc_run_json_for_viewer")).pack(side="left", padx=6)
    ttk.Button(report_actions, text="Export Batch QC CSV", command=lambda: _run_action("export_current_batch_qc_run_csv_for_viewer")).pack(side="left", padx=6)
    ttk.Button(report_actions, text="Export Batch QC Text", command=lambda: _run_action("export_current_batch_qc_report_text_for_viewer")).pack(side="left", padx=6)
    ttk.Button(report_actions, text="Export Batch QC PDF", command=lambda: _run_action("export_current_batch_qc_report_pdf_for_viewer")).pack(side="left", padx=6)
    _refresh()

    setattr(viewer_adapter, "_window_b_batch_summary_var", summary_text_var)
    setattr(viewer_adapter, "_window_b_batch_preview_text", preview_text)
    setattr(viewer_adapter, "_window_b_batch_use_selected_threshold_var", selected_threshold_var)
    return panel
