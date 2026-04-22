from pathlib import Path
import copy
import csv
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional
import uuid

import matplotlib.pyplot as plt
import numpy as np
import pydicom
from PIL import Image, ImageDraw, ImageTk
from pydicom.errors import InvalidDicomError
from dicom_loader import DicomLoader


@dataclass
class Measurement:
    id: str
    kind: str
    start: tuple[float, float]
    end: tuple[float, float]
    frame_index: int
    geometry_key: str
    summary_text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeasurementSet:
    id: str
    name: str
    geometry_key: str
    created_at: str
    measurements: list[Measurement] = field(default_factory=list)


@dataclass
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class RoiStats:
    mean: float
    std: float
    min_val: float
    max_val: float
    area_px: int


@dataclass
class RectRoi:
    roi_id: str
    image_rect: Rect
    stats: Optional[RoiStats] = None
    selected: bool = False
    visible: bool = True


@dataclass
class ResultHistoryEntry:
    entry_id: str
    timestamp: str
    image_name: str
    frame_index: int
    measurement_type: str
    target_name: str
    metric: str
    value: float
    unit: str
    note: str
    measurement_mode: str
    source_image_path: str = ""
    target_id: str = ""
    related_target_ids: list[str] = field(default_factory=list)

    def to_row(self) -> tuple[str, str, str, str, str, str, str, str, str]:
        return (
            self.timestamp,
            self.image_name,
            str(self.frame_index),
            self.measurement_type,
            self.target_name,
            self.metric,
            f"{self.value:.2f}",
            self.unit,
            self.note,
        )


class ResultHistoryStore:
    def __init__(self) -> None:
        self._entries: list[ResultHistoryEntry] = []

    def append(self, entry: ResultHistoryEntry) -> None:
        self._entries.append(entry)

    def remove_indices(self, indices: list[int]) -> None:
        for index in sorted(set(indices), reverse=True):
            if 0 <= index < len(self._entries):
                self._entries.pop(index)

    def clear(self) -> None:
        self._entries.clear()

    def entries(self) -> list[ResultHistoryEntry]:
        return list(self._entries)

    def filtered_entries(self, measurement_type: str = "All", search_text: str = "") -> list[tuple[int, ResultHistoryEntry]]:
        query = search_text.strip().lower()
        selected_type = measurement_type.strip()
        rows: list[tuple[int, ResultHistoryEntry]] = []
        for index, entry in enumerate(self._entries):
            if selected_type and selected_type != "All" and entry.measurement_type != selected_type:
                continue
            if query:
                haystack = f"{entry.image_name} {entry.target_name} {entry.metric}".lower()
                if query not in haystack:
                    continue
            rows.append((index, entry))
        return rows


SESSION_SCHEMA_VERSION = "1.0"
PRESET_SCHEMA_VERSION = "1.0"


class DicomViewer:
    _UUID_PATTERN = re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DICOM Viewer")
        self.root.geometry("1100x800")

        self.dataset = None
        self.frames = []
        self.current_frame = 0
        self.file_paths = []
        self.current_file_index = -1
        self.current_folder_path: str | None = None
        self.loaded_from_folder = False
        self.photo_image = None
        self._last_canvas_size = (0, 0)
        self.dicom_loader = DicomLoader()
        self._metadata_cache: dict[str, pydicom.dataset.FileDataset] = {}
        self.window_width_value: float | None = None
        self.window_level_value: float | None = None
        self.default_window_width: float | None = None
        self.default_window_level: float | None = None
        self.window_level_range = (0.0, 1.0)
        self._window_drag_origin: tuple[int, int] | None = None
        self._window_drag_base: tuple[float, float] | None = None
        self.invert_display = tk.BooleanVar(value=False)
        self.show_grid_overlay = tk.BooleanVar(value=False)
        self.include_overlays_in_export = tk.BooleanVar(value=True)
        self.grid_spacing_presets_px = (2, 4, 6, 8, 10, 12, 16, 20, 24, 32)
        self.grid_spacing_mode = tk.StringVar(value="8")
        self.grid_spacing_custom_px = tk.IntVar(value=8)
        self.grid_spacing_px = tk.IntVar(value=8)
        self.grid_roi_size_presets = ("1x1", "2x2", "3x3", "4x4", "6x6", "8x8")
        self.grid_roi_size_mode = tk.StringVar(value="1x1")
        self.grid_roi_width_cells = tk.IntVar(value=1)
        self.grid_roi_height_cells = tk.IntVar(value=1)
        self.grid_roi_size_cells = tk.IntVar(value=1)
        self.grid_cell_size_var = tk.StringVar(value="Grid cell size: 8 px")
        self.cursor_var = tk.StringVar(value="Cursor: -, -")
        self.measurement_mode = tk.StringVar(value="pan")
        self.roi_draw_mode = tk.StringVar(value="grid")
        self.roi_propagation_enabled = tk.BooleanVar(value=False)
        self.roi_propagation_scope = tk.StringVar(value="next")
        self._active_preview_measurement: dict[str, Any] | None = None
        self._line_snap_anchor: tuple[int, int] | None = None
        self._polygon_points: list[tuple[int, int]] = []
        self._polygon_cursor_point: tuple[int, int] | None = None
        self._draw_tool_buttons: dict[str, tk.Button] = {}
        self.crop_mode_active = tk.BooleanVar(value=False)
        self._active_crop_start: tuple[float, float] | None = None
        self._active_crop_end: tuple[float, float] | None = None
        self._active_crop_item_id: int | None = None
        self.persistent_measurements: list[Measurement] = []
        self.selected_persistent_measurement_id: str | None = None
        self._persistent_canvas_item_to_measurement_id: dict[int, str] = {}
        self.measurement_sets: dict[str, MeasurementSet] = {}
        self._image_bbox: tuple[float, float, float, float] | None = None
        self.zoom_scale = 1.0
        self.min_zoom_scale = 0.05
        self.max_zoom_scale = 32.0
        self._zoom_limit_notice: str | None = None
        self.zoom_var = tk.StringVar(value="Zoom: -")
        self.view_mode = "single"
        self.multiview_cols = 3
        self.multiview_rows = 2
        self.multiview_page = 0
        self.multiview_tile_padding = 8
        self.multiview_popup: tk.Toplevel | None = None
        self.multiview_hover_cols = self.multiview_cols
        self.multiview_hover_rows = self.multiview_rows
        self.multiview_grid_labels: list[tuple[int, int, tk.Label]] = []
        self.multiview_thumbnail_cache: dict[tuple[str, int, int], ImageTk.PhotoImage] = {}
        self.multiview_thumbnail_page_keys: dict[int, set[tuple[str, int, int]]] = {}
        self.multiview_info_cache: dict[str, str] = {}
        self.multiview_tile_images: list[ImageTk.PhotoImage] = []
        self.multiview_tile_widgets: dict[int, dict[str, tk.Widget]] = {}
        self.multiview_tile_meta_cache: dict[str, tuple[str, str]] = {}
        self.multiview_thumbnail_queue: list[tuple[int, str, int, int, int]] = []
        self.multiview_render_token = 0
        self._multiview_thumbnail_job: str | None = None
        self._multiview_resize_job: str | None = None
        self.multiview_cache_page_window = 1
        self.show_basic_overlay = tk.BooleanVar(value=True)
        self.show_acquisition_overlay = tk.BooleanVar(value=True)
        self.compare_mode_enabled = tk.BooleanVar(value=False)
        self.compare_sync_enabled = tk.BooleanVar(value=False)
        self.compare_sync_mode = "index"
        self.overlay_settings_popup: tk.Toplevel | None = None
        self.show_overlay_advanced = tk.BooleanVar(value=False)
        self.overlay_advanced_button_var = tk.StringVar(value="고급 항목 펼치기")
        self.overlay_field_definitions = self._build_overlay_field_definitions()
        self.overlay_field_lookup = {field["key"]: field for field in self.overlay_field_definitions}
        self.overlay_field_vars = {
            field["key"]: tk.BooleanVar(value=bool(field["default_visible"]))
            for field in self.overlay_field_definitions
        }
        self.overlay_settings_path = Path(__file__).with_name("dicom_viewer_overlay_settings.json")
        self.current_overlay_values: dict[str, str] = {
            field["key"]: "N/A"
            for field in self.overlay_field_definitions
        }
        self.overlay_settings_left_frame: ttk.Frame | None = None
        self.overlay_settings_right_frame: ttk.Frame | None = None
        self.overlay_reset_button_var = tk.StringVar(value="기본값 복원")
        self.compare_panels: dict[str, dict[str, Any]] = {}
        self.compare_overlay_field_keys = {
            "left": [
                "patient_id",
                "study_date",
                "modality",
            ],
            "right": [
                "ei",
                "di",
                "kvp",
                "mas",
                "sid",
                "view_position",
            ],
        }
        self.compare_restore_state: dict[str, Any] | None = None
        self._load_overlay_preferences()

        self.path_var = tk.StringVar(value="")
        self.info_var = tk.StringVar(value="")
        self.image_var = tk.StringVar(value="이미지: - / -")
        self.frame_var = tk.StringVar(value="프레임: - / -")
        self.window_level_var = tk.StringVar(value="W/L: - / -")
        self.view_mode_var = tk.StringVar(value="보기: 단일")
        self.multiview_page_var = tk.StringVar(value="페이지: - / -")
        self.multiview_grid_var = tk.StringVar(value="격자: 3 x 2")
        self.source_var = tk.StringVar(value="소스: 단일 파일")
        self.compare_sync_status_var = tk.StringVar(value="비교 동기: Off")
        self.snr_workflow_var = tk.StringVar(value="SNR: Idle")
        self.guided_snr_state: dict[str, Any] | None = None
        self.signal_analysis_inputs: dict[str, tk.StringVar] = {
            "snr_signal_roi_id": tk.StringVar(value=""),
            "snr_background_roi_id": tk.StringVar(value=""),
            "cnr_formula": tk.StringVar(value="standard_noise"),
            "cnr_target_roi_id": tk.StringVar(value=""),
            "cnr_reference_roi_id": tk.StringVar(value=""),
            "cnr_noise_roi_id": tk.StringVar(value=""),
            "uniformity_formula": tk.StringVar(value="max_min"),
            "uniformity_input_mode": tk.StringVar(value="selected_rois"),
            "uniformity_role_filter": tk.StringVar(value="signal"),
            "uniformity_roi_ids": tk.StringVar(value=""),
            "line_profile_line_id": tk.StringVar(value=""),
        }
        self.signal_analysis_results: dict[str, tk.StringVar] = {
            "snr_preview": tk.StringVar(value="Preview: -"),
            "snr_result": tk.StringVar(value="Result: -"),
            "snr_ready_reason": tk.StringVar(value="Ready: 입력 대기"),
            "cnr_preview": tk.StringVar(value="Preview: -"),
            "cnr_result": tk.StringVar(value="Result: -"),
            "uniformity_preview": tk.StringVar(value="Preview: -"),
            "uniformity_result": tk.StringVar(value="Result: -"),
            "line_info": tk.StringVar(value="Line: -"),
        }
        self.image_analysis_inputs: dict[str, tk.StringVar] = {
            "reference_image_id": tk.StringVar(value=""),
            "target_image_id": tk.StringVar(value=""),
            "scope_type": tk.StringVar(value="full"),
            "scope_roi_id": tk.StringVar(value=""),
        }
        self.image_analysis_results: dict[str, tk.StringVar] = {
            "image_formula": tk.StringVar(value="Formula: MSE/PSNR/SSIM/Histogram"),
            "image_result": tk.StringVar(value="Result: -"),
        }
        self.analysis_inputs = self.signal_analysis_inputs
        self.analysis_results = self.signal_analysis_results
        self._analysis_option_maps: dict[str, dict[str, str]] = {
            "roi": {},
            "line": {},
        }
        self._image_analysis_option_maps: dict[str, dict[str, str]] = {
            "image": {},
            "roi": {},
        }
        self.analysis_last_run: dict[str, dict[str, Any]] = {}
        self._analysis_comboboxes: dict[str, ttk.Combobox] = {}
        self._analysis_selector_vars: dict[str, tk.StringVar] = {}
        self._image_analysis_comboboxes: dict[str, ttk.Combobox] = {}
        self._cnr_noise_widgets: list[tk.Widget] = []
        self._analysis_action_buttons: dict[str, ttk.Button] = {}
        self._uniformity_roi_listbox: tk.Listbox | None = None
        self.analysis_results_table: ttk.Frame | None = None
        self.analysis_results_canvas: tk.Canvas | None = None
        self.analysis_results_rows_container: ttk.Frame | None = None
        self._analysis_results_row_widgets: list[dict[str, Any]] = []
        self._analysis_results_selected_index: int | None = None
        self.result_history_store = ResultHistoryStore()
        self.result_history_table: ttk.Treeview | None = None
        self.history_metric_filter_var = tk.StringVar(value="All")
        self.history_search_var = tk.StringVar(value="")
        self._history_item_to_store_indices: dict[str, list[int]] = {}
        self.history_compare_button: ttk.Button | None = None
        self.line_profile_series_cache: dict[str, dict[str, Any]] = {}
        self._session_compare_state: dict[str, Any] = {"selected_entry_ids": [], "baseline_index": 0}
        self.shortcut_var = tk.StringVar(
            value=(
                "단축키: F 창맞춤 | 0/Ctrl+0 100% | R W/L 리셋 | "
                "S Grid ROI 요약 | "
                "멀티뷰 화살표 선택 | Enter 열기 | Esc 멀티뷰 복귀 | "
                "Home/End 첫/마지막 | PgUp/PgDn 이전/다음 | Shift+PgUp/PgDn 프레임"
            )
        )
        self.info_panel_expanded = tk.BooleanVar(value=False)
        self.info_toggle_var = tk.StringVar(value="정보 표시")
        self.info_panel_frame: ttk.Frame | None = None
        self.path_info_label: ttk.Label | None = None
        self.summary_info_label: ttk.Label | None = None
        self.shortcut_info_label: ttk.Label | None = None
        self.main_vertical_split: tk.PanedWindow | None = None
        self.top_controls_container: ttk.Frame | None = None
        self.viewer_container: ttk.Frame | None = None
        self.controls_min_height = 170
        self.viewer_min_height = 280
        self.ui_colors = {
            "bg_root": "#FAFAFA",
            "bg_surface": "#FFFFFF",
            "bg_section": "#F2F4F7",
            "border": "#E5E7EB",
            "text_primary": "#1F2937",
            "text_secondary": "#6B7280",
            "button_default": "#EEF1F5",
            "button_hover": "#E4E9F0",
            "button_active": "#DCEAFE",
            "overlay_bg": "#111827",
            "overlay_border": "#374151",
            "overlay_text": "#F9FAFB",
        }
        self._configure_ui_styles()
        self._build_ui()
        self.measurement_mode.trace_add("write", self._on_measurement_mode_changed)
        self._on_measurement_mode_changed()

    def _configure_ui_styles(self) -> None:
        style = ttk.Style(self.root)
        self.root.configure(bg=self.ui_colors["bg_root"])
        style.configure(".", background=self.ui_colors["bg_root"], foreground=self.ui_colors["text_primary"])
        style.configure("TFrame", background=self.ui_colors["bg_root"])
        style.configure("TLabel", background=self.ui_colors["bg_root"], foreground=self.ui_colors["text_primary"])
        style.configure("TLabelframe", background=self.ui_colors["bg_section"], bordercolor=self.ui_colors["border"], relief="solid")
        style.configure("TLabelframe.Label", background=self.ui_colors["bg_section"], foreground=self.ui_colors["text_primary"])
        style.configure(
            "TButton",
            background=self.ui_colors["button_default"],
            foreground=self.ui_colors["text_primary"],
            bordercolor=self.ui_colors["border"],
            focusthickness=1,
            focuscolor=self.ui_colors["border"],
            padding=(8, 4),
        )
        style.map(
            "TButton",
            background=[
                ("pressed", self.ui_colors["button_active"]),
                ("active", self.ui_colors["button_hover"]),
                ("disabled", "#F3F4F6"),
            ],
            foreground=[("disabled", "#9CA3AF")],
        )
        style.configure("ToolbarNav.TButton", padding=(8, 4), font=("TkDefaultFont", 10, "bold"))
        style.map(
            "ToolbarNav.TButton",
            foreground=[("disabled", "#9CA3AF"), ("!disabled", self.ui_colors["text_primary"])],
            background=[
                ("pressed", self.ui_colors["button_active"]),
                ("active", self.ui_colors["button_hover"]),
                ("!disabled", self.ui_colors["button_default"]),
                ("disabled", "#F3F4F6"),
            ],
            relief=[("pressed", "sunken"), ("!pressed", "raised")],
        )
        style.configure(
            "AnalysisResults.Treeview",
            rowheight=22,
            fieldbackground="#FFFFFF",
            background="#FFFFFF",
            bordercolor=self.ui_colors["border"],
        )
        style.map(
            "AnalysisResults.Treeview",
            background=[("selected", "#DCEAFE")],
            foreground=[("selected", self.ui_colors["text_primary"])],
        )

    def _build_ui(self) -> None:
        self.main_vertical_split = tk.PanedWindow(
            self.root,
            orient=tk.VERTICAL,
            sashrelief=tk.RAISED,
            sashwidth=8,
            opaqueresize=True,
            bg=self.ui_colors["bg_root"],
            bd=0,
            relief="flat",
        )
        self.main_vertical_split.pack(fill="both", expand=True)

        toolbar_container = ttk.Frame(self.main_vertical_split, padding=12)
        self.top_controls_container = toolbar_container
        self._build_toolbar_tabs(toolbar_container)
        self._build_status_row(toolbar_container)
        self._build_collapsible_info_panel(toolbar_container)
        self.main_vertical_split.add(toolbar_container, minsize=self.controls_min_height, stretch="never")

        self.content_container = ttk.Frame(self.main_vertical_split, padding=(12, 0, 12, 12))
        self.viewer_container = self.content_container
        self.content_container.columnconfigure(0, weight=1)
        self.content_container.rowconfigure(0, weight=1)
        self.main_vertical_split.add(self.content_container, minsize=self.viewer_min_height, stretch="always")

        self.single_view_container = ttk.Frame(self.content_container)
        self.single_view_container.grid(row=0, column=0, sticky="nsew")
        self.single_view_container.columnconfigure(0, weight=1)
        self.single_view_container.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.single_view_container, bg="black", highlightthickness=0)
        x_scroll = ttk.Scrollbar(self.single_view_container, orient="horizontal", command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(self.single_view_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>", self._handle_left_button_press)
        self.canvas.bind("<B1-Motion>", self._handle_left_button_drag)
        self.canvas.bind("<ButtonRelease-1>", self._handle_left_button_release)
        self.canvas.bind("<Motion>", self._update_cursor_coordinates)
        self.canvas.bind("<ButtonPress-3>", self._handle_right_button_press)
        self.canvas.bind("<B3-Motion>", self._handle_right_button_drag)
        self.canvas.bind("<ButtonRelease-3>", self._handle_right_button_release)
        self.canvas.bind("<MouseWheel>", self._handle_mousewheel)
        self.canvas.bind("<Button-4>", self._handle_mousewheel)
        self.canvas.bind("<Button-5>", self._handle_mousewheel)

        self.multiview_container = ttk.Frame(self.content_container)
        self.multiview_container.grid(row=0, column=0, sticky="nsew")
        self.multiview_container.columnconfigure(0, weight=1)
        self.multiview_container.rowconfigure(1, weight=1)

        self.compare_container = ttk.Frame(self.content_container)
        self.compare_container.grid(row=0, column=0, sticky="nsew")
        self.compare_container.columnconfigure(0, weight=1)
        self.compare_container.columnconfigure(1, weight=1)
        self.compare_container.rowconfigure(0, weight=1)

        self.compare_panels = {
            "left": self._create_compare_panel(self.compare_container, "left", "좌측 비교"),
            "right": self._create_compare_panel(self.compare_container, "right", "우측 비교"),
        }
        self.left_view_state = self.compare_panels["left"]
        self.right_view_state = self.compare_panels["right"]

        multiview_toolbar = ttk.Frame(self.multiview_container, padding=(0, 0, 0, 8))
        multiview_toolbar.grid(row=0, column=0, sticky="ew")
        multiview_toolbar.columnconfigure(5, weight=1)

        ttk.Button(multiview_toolbar, text="격자 선택", command=self.open_multiview_grid_selector).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(multiview_toolbar, text="이전 페이지", command=lambda: self.change_multiview_page(-1)).grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        ttk.Button(multiview_toolbar, text="다음 페이지", command=lambda: self.change_multiview_page(1)).grid(
            row=0, column=2, sticky="w", padx=(8, 0)
        )
        ttk.Label(multiview_toolbar, textvariable=self.multiview_grid_var).grid(
            row=0, column=3, sticky="w", padx=(12, 0)
        )
        ttk.Label(multiview_toolbar, textvariable=self.multiview_page_var).grid(
            row=0, column=4, sticky="w", padx=(12, 0)
        )

        self.multiview_body = ttk.Frame(self.multiview_container)
        self.multiview_body.grid(row=1, column=0, sticky="nsew")
        self.multiview_body.bind("<Configure>", self._on_multiview_resize)

        self.multiview_container.grid_remove()
        self.compare_container.grid_remove()
        self._bind_shortcuts()
        self._update_multiview_controls()
        self._update_compare_controls()
        self.root.after(0, self._set_initial_split_sash)

    def _set_initial_split_sash(self) -> None:
        if self.main_vertical_split is None:
            return
        total_height = max(self.main_vertical_split.winfo_height(), self.root.winfo_height())
        desired_controls_height = int(np.clip(total_height * 0.32, self.controls_min_height, 360))
        max_controls_height = max(total_height - self.viewer_min_height, self.controls_min_height)
        target_y = min(desired_controls_height, max_controls_height)
        try:
            self.main_vertical_split.sash_place(0, 0, target_y)
        except tk.TclError:
            return

    def _build_toolbar_tabs(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)

        home_tab = self._add_toolbar_tab(notebook, "HOME")
        image_tab = self._add_toolbar_tab(notebook, "IMAGE")
        measure_tab = self._add_toolbar_tab(notebook, "MEASURE")
        analysis_tab = self._add_toolbar_tab(notebook, "ANALYSIS")
        export_tab = self._add_toolbar_tab(notebook, "EXPORT")

        self._build_home_toolbar(home_tab)
        self._build_image_toolbar(image_tab)
        self._build_measure_toolbar(measure_tab)
        self._build_analysis_toolbar(analysis_tab)
        self._build_export_toolbar(export_tab)

    @staticmethod
    def _add_toolbar_tab(notebook: ttk.Notebook, title: str) -> ttk.Frame:
        tab = ttk.Frame(notebook, padding=(8, 8, 8, 6))
        notebook.add(tab, text=title)
        return tab

    def _build_subtoolbar_sections(self, parent: ttk.Frame, section_names: list[str]) -> dict[str, ttk.Frame]:
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=1)

        selector_row = ttk.Frame(wrapper)
        selector_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        selector_row.columnconfigure(1, weight=1)
        ttk.Label(selector_row, text="Section").grid(row=0, column=0, sticky="w")

        selected_section = tk.StringVar(value=section_names[0])
        selector = ttk.Combobox(
            selector_row,
            state="readonly",
            values=tuple(section_names),
            textvariable=selected_section,
            width=14,
        )
        selector.grid(row=0, column=1, sticky="w", padx=(6, 0))

        body = ttk.Frame(wrapper)
        body.grid(row=1, column=0, sticky="ew")
        body.columnconfigure(0, weight=1)
        section_frames: dict[str, ttk.Frame] = {}
        for name in section_names:
            frame = ttk.Frame(body)
            frame.grid(row=0, column=0, sticky="ew")
            section_frames[name] = frame

        def show_section(name: str) -> None:
            if name not in section_frames:
                return
            for section_name, frame in section_frames.items():
                if section_name == name:
                    frame.grid()
                else:
                    frame.grid_remove()
            selected_section.set(name)

        def step_section(step: int) -> None:
            current = selected_section.get()
            if current not in section_names:
                show_section(section_names[0])
                return
            index = section_names.index(current)
            show_section(section_names[(index + step) % len(section_names)])

        ttk.Button(selector_row, text="◀", width=3, command=lambda: step_section(-1)).grid(row=0, column=2, padx=(8, 2))
        ttk.Button(selector_row, text="▶", width=3, command=lambda: step_section(1)).grid(row=0, column=3)
        selector.bind("<<ComboboxSelected>>", lambda _event: show_section(selected_section.get()))
        show_section(section_names[0])
        return section_frames

    def _build_grouped_toolbar_strip(self, parent: ttk.Frame) -> ttk.Frame:
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="both", expand=True)
        wrapper.rowconfigure(0, weight=1)
        wrapper.rowconfigure(1, weight=0)
        wrapper.columnconfigure(1, weight=1)
        canvas_background = self.ui_colors["bg_surface"]
        canvas = tk.Canvas(wrapper, highlightthickness=0, bg=canvas_background, bd=0)
        canvas.grid(row=0, column=1, sticky="nsew")
        canvas.configure(yscrollincrement=16)
        x_scrollbar = ttk.Scrollbar(wrapper, orient="horizontal", command=canvas.xview)
        x_scrollbar.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        y_scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        y_scrollbar.grid(row=0, column=3, sticky="ns", padx=(4, 0))
        left_button = ttk.Button(
            wrapper,
            text="◀",
            width=3,
            command=lambda: canvas.xview_scroll(-2, "units"),
            style="ToolbarNav.TButton",
        )
        right_button = ttk.Button(
            wrapper,
            text="▶",
            width=3,
            command=lambda: canvas.xview_scroll(2, "units"),
            style="ToolbarNav.TButton",
        )
        left_button.grid(row=0, column=0, padx=(0, 4))
        right_button.grid(row=0, column=2, padx=(4, 0))

        strip = ttk.Frame(canvas, padding=(0, 2))
        window_id = canvas.create_window((0, 0), window=strip, anchor="nw")

        def _update_nav_buttons() -> None:
            left_start, right_end = canvas.xview()
            left_button.configure(state="disabled" if left_start <= 0.001 else "normal")
            right_button.configure(state="disabled" if right_end >= 0.999 else "normal")

        def _on_xscroll(first: str, last: str) -> None:
            x_scrollbar.set(first, last)
            _update_nav_buttons()

        def _refresh_scroll_region(_event: tk.Event | None = None) -> None:
            canvas.update_idletasks()
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            strip_width = strip.winfo_reqwidth()
            strip_height = strip.winfo_reqheight()
            canvas.itemconfigure(window_id, width=strip_width, height=strip_height)
            canvas.configure(scrollregion=(0, 0, strip_width, strip_height))
            requires_horizontal_scroll = strip_width > canvas_width + 1
            requires_vertical_scroll = strip_height > canvas_height + 1
            if requires_horizontal_scroll:
                x_scrollbar.grid()
            else:
                x_scrollbar.grid_remove()
                canvas.xview_moveto(0.0)
            if requires_vertical_scroll:
                y_scrollbar.grid()
            else:
                y_scrollbar.grid_remove()
                canvas.yview_moveto(0.0)
            _update_nav_buttons()

        def _resize_inner(_event: tk.Event) -> None:
            _refresh_scroll_region()

        def _on_mousewheel(event: tk.Event) -> None:
            if event.state & 0x0001:
                delta = -2 if event.delta > 0 else 2
                canvas.xview_scroll(delta, "units")
            else:
                delta = -2 if event.delta > 0 else 2
                canvas.yview_scroll(delta, "units")
            _update_nav_buttons()

        def _on_linux_mousewheel(event: tk.Event) -> None:
            if event.num == 4:
                canvas.yview_scroll(-2, "units")
            elif event.num == 5:
                canvas.yview_scroll(2, "units")
            _update_nav_buttons()

        strip.bind("<Configure>", _refresh_scroll_region)
        canvas.bind("<Configure>", _resize_inner)
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Shift-MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", _on_linux_mousewheel)
        canvas.bind("<Button-5>", _on_linux_mousewheel)

        def _bind_wheel(widget: tk.Misc) -> None:
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            widget.bind("<Shift-MouseWheel>", _on_mousewheel, add="+")
            widget.bind("<Button-4>", _on_linux_mousewheel, add="+")
            widget.bind("<Button-5>", _on_linux_mousewheel, add="+")
            for child in widget.winfo_children():
                _bind_wheel(child)

        strip.bind("<Map>", lambda _event: _bind_wheel(strip), add="+")
        canvas.configure(xscrollcommand=_on_xscroll, yscrollcommand=y_scrollbar.set)
        _update_nav_buttons()
        return strip

    def _build_home_toolbar(self, tab: ttk.Frame) -> None:
        sections = self._build_subtoolbar_sections(tab, ["View", "Compare", "Overlay", "Output"])

        self.diagnose_button = ttk.Button(sections["View"], text="폴더 진단", command=self.diagnose_folder)
        self.diagnose_button.pack(side="left")
        self.toggle_view_button = ttk.Button(sections["View"], text="단일/멀티 전환", command=self.toggle_view_mode)
        self.toggle_view_button.pack(side="left", padx=(8, 0))

        ttk.Checkbutton(
            sections["Compare"],
            text="Compare Mode",
            variable=self.compare_mode_enabled,
            command=self.toggle_compare_mode,
        ).pack(side="left")
        ttk.Checkbutton(
            sections["Compare"],
            text="Sync",
            variable=self.compare_sync_enabled,
            command=self._update_compare_sync_status,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Compare"], text="Swap Left/Right", command=self.swap_compare_panels).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(
            sections["Overlay"],
            text="기본 정보 오버레이",
            variable=self.show_basic_overlay,
            command=self.refresh_overlay_display,
        ).pack(side="left")
        ttk.Checkbutton(
            sections["Overlay"],
            text="촬영 정보 오버레이",
            variable=self.show_acquisition_overlay,
            command=self.refresh_overlay_display,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Overlay"], text="오버레이 항목 설정", command=self.open_overlay_settings).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(
            sections["Output"],
            text="ROI/Line 오버레이 포함",
            variable=self.include_overlays_in_export,
        ).pack(side="left")
        ttk.Button(sections["Output"], text="현재 이미지 저장", command=self.export_current_image).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Output"], text="측정 CSV 저장", command=self.export_measurements_csv).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Output"], text="프레임 일괄 저장", command=self.export_all_frames).pack(side="left", padx=(8, 0))

    def _build_image_toolbar(self, tab: ttk.Frame) -> None:
        sections = self._build_subtoolbar_sections(tab, ["File", "Navigate", "Display", "Transform"])

        self.open_file_button = ttk.Button(sections["File"], text="DICOM 열기", command=self.open_file)
        self.open_file_button.pack(side="left")
        self.open_folder_button = ttk.Button(sections["File"], text="폴더 열기", command=self.open_folder)
        self.open_folder_button.pack(side="left", padx=(8, 0))
        ttk.Button(sections["File"], text="Save Session", command=self.save_analysis_session).pack(side="left", padx=(12, 0))
        ttk.Button(sections["File"], text="Load Session", command=self.load_analysis_session).pack(side="left", padx=(8, 0))
        ttk.Button(sections["File"], text="Save Preset", command=self.save_measurement_preset).pack(side="left", padx=(12, 0))
        ttk.Button(sections["File"], text="Load Preset", command=self.load_measurement_preset).pack(side="left", padx=(8, 0))

        self.prev_image_button = ttk.Button(sections["Navigate"], text="이전 이미지", command=lambda: self.change_file(-1))
        self.prev_image_button.pack(side="left")
        self.next_image_button = ttk.Button(sections["Navigate"], text="다음 이미지", command=lambda: self.change_file(1))
        self.next_image_button.pack(side="left", padx=(8, 0))
        self.prev_frame_button = ttk.Button(sections["Navigate"], text="이전 프레임", command=lambda: self.change_frame(-1))
        self.prev_frame_button.pack(side="left", padx=(16, 0))
        self.next_frame_button = ttk.Button(sections["Navigate"], text="다음 프레임", command=lambda: self.change_frame(1))
        self.next_frame_button.pack(side="left", padx=(8, 0))

        self.window_level_reset_button = ttk.Button(sections["Display"], text="W/L 리셋", command=self.reset_window_level)
        self.window_level_reset_button.pack(side="left")
        ttk.Checkbutton(
            sections["Display"],
            text="Invert",
            variable=self.invert_display,
            command=self._refresh_single_view_image,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Transform"], text="Crop 선택", command=self.enable_crop_mode).pack(side="left")
        ttk.Button(sections["Transform"], text="Crop 취소", command=self.cancel_crop_mode).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Transform"], text="Rotate 90°", command=lambda: self.rotate_current_image(90)).pack(side="left", padx=(16, 0))
        ttk.Button(sections["Transform"], text="Rotate 180°", command=lambda: self.rotate_current_image(180)).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Transform"], text="Rotate 270°", command=lambda: self.rotate_current_image(270)).pack(side="left", padx=(8, 0))

    def _build_draw_tool_panel(self, parent: ttk.Widget) -> None:
        parent.columnconfigure(0, weight=1)
        for row, (label, mode) in enumerate(
            [("Pan", "pan"), ("Line", "line"), ("ROI", "roi"), ("Polygon", "polygon")]
        ):
            button = tk.Button(
                parent,
                text=label,
                width=10,
                anchor="w",
                relief="raised",
                command=lambda target=mode: self._set_measurement_mode(target),
            )
            button.grid(row=row, column=0, sticky="ew", pady=(0, 4))
            self._draw_tool_buttons[mode] = button
        ttk.Separator(parent, orient="horizontal").grid(row=4, column=0, sticky="ew", pady=(2, 6))
        ttk.Label(parent, text="ROI mode").grid(row=5, column=0, sticky="w")
        ttk.Radiobutton(parent, text="Grid ROI", value="grid", variable=self.roi_draw_mode).grid(row=6, column=0, sticky="w")
        ttk.Radiobutton(parent, text="Free ROI", value="free", variable=self.roi_draw_mode).grid(row=7, column=0, sticky="w")
        ttk.Label(parent, text="Grid ON → polygon snap").grid(row=8, column=0, sticky="w", pady=(6, 0))

    def _set_measurement_mode(self, mode: str) -> None:
        self.measurement_mode.set(mode)

    def _on_measurement_mode_changed(self, *_args: Any) -> None:
        active_mode = self.measurement_mode.get()
        for mode, button in self._draw_tool_buttons.items():
            is_active = mode == active_mode
            button.configure(
                bg="#2f7dd1" if is_active else "#f2f4f7",
                fg="#ffffff" if is_active else "#1f2937",
                relief="sunken" if is_active else "raised",
            )
        if active_mode != "polygon":
            self._cancel_polygon_draft()
        elif self.view_mode == "single":
            self.cursor_var.set("Cursor: Polygon 모드 (점 추가 후 첫 점 클릭 또는 Enter로 닫기)")

    def _build_measure_toolbar(self, tab: ttk.Frame) -> None:
        strip = self._build_grouped_toolbar_strip(tab)

        tools_group = ttk.LabelFrame(strip, text="Tools", padding=(8, 6))
        tools_group.pack(side="left", padx=(0, 8), fill="y")
        self._build_draw_tool_panel(tools_group)

        grid_group = ttk.LabelFrame(strip, text="Grid", padding=(8, 6))
        grid_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Checkbutton(
            grid_group,
            text="Show Grid",
            variable=self.show_grid_overlay,
            command=self._refresh_grid_overlay,
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(grid_group, text="Grid spacing (cell size)").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.grid_spacing_combobox = ttk.Combobox(
            grid_group,
            width=6,
            state="readonly",
            values=tuple(str(value) for value in self.grid_spacing_presets_px) + ("Custom",),
            textvariable=self.grid_spacing_mode,
        )
        self.grid_spacing_combobox.grid(row=1, column=1, padx=(4, 0), pady=(4, 0), sticky="w")
        ttk.Entry(grid_group, width=5, textvariable=self.grid_spacing_custom_px).grid(row=1, column=2, padx=(4, 0), pady=(4, 0), sticky="w")
        ttk.Label(grid_group, textvariable=self.grid_cell_size_var).grid(row=2, column=0, columnspan=5, sticky="w", pady=(4, 0))
        ttk.Label(grid_group, text="ROI size (cells)").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.grid_roi_size_combobox = ttk.Combobox(
            grid_group,
            width=8,
            state="readonly",
            values=self.grid_roi_size_presets + ("Custom",),
            textvariable=self.grid_roi_size_mode,
        )
        self.grid_roi_size_combobox.grid(row=3, column=1, padx=(4, 0), pady=(6, 0), sticky="w")
        ttk.Entry(grid_group, width=4, textvariable=self.grid_roi_width_cells).grid(row=3, column=2, padx=(4, 0), pady=(6, 0), sticky="w")
        ttk.Label(grid_group, text="x").grid(row=3, column=3, padx=(2, 2), pady=(6, 0), sticky="w")
        ttk.Entry(grid_group, width=4, textvariable=self.grid_roi_height_cells).grid(row=3, column=4, pady=(6, 0), sticky="w")
        self.grid_spacing_mode.trace_add("write", self._on_grid_spacing_mode_changed)
        self.grid_spacing_custom_px.trace_add("write", self._on_grid_spacing_custom_changed)
        self.grid_roi_size_mode.trace_add("write", self._on_grid_roi_size_mode_changed)
        self.grid_roi_width_cells.trace_add("write", self._on_grid_roi_dimension_changed)
        self.grid_roi_height_cells.trace_add("write", self._on_grid_roi_dimension_changed)
        self._sync_grid_spacing_from_mode()
        self._sync_grid_roi_size_from_mode()

        measurement_group = ttk.LabelFrame(strip, text="Measurement", padding=(8, 6))
        measurement_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(measurement_group, text="ROI Geometry: X/Y, Width, Height, Area").grid(row=0, column=0, sticky="w")
        ttk.Label(measurement_group, text="Display: mm first, px second").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(measurement_group, text="Grid ROI Summary", command=self._show_grid_roi_combined_summary).grid(
            row=2, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Checkbutton(
            measurement_group,
            text="ROI Propagation",
            variable=self.roi_propagation_enabled,
        ).grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Radiobutton(
            measurement_group,
            text="Next frame/image",
            value="next",
            variable=self.roi_propagation_scope,
        ).grid(row=4, column=0, sticky="w")
        ttk.Radiobutton(
            measurement_group,
            text="All navigated targets",
            value="all",
            variable=self.roi_propagation_scope,
        ).grid(row=5, column=0, sticky="w")

        manage_group = ttk.LabelFrame(strip, text="Manage", padding=(8, 6))
        manage_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Button(manage_group, text="Undo", command=self.undo_last_measurement).grid(row=0, column=0, sticky="ew")
        ttk.Button(manage_group, text="Clear All", command=self.clear_persistent_measurements).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(manage_group, text="Delete Selected", command=self.clear_selected_measurement).grid(
            row=2, column=0, sticky="ew", pady=(4, 0)
        )
        ttk.Button(manage_group, text="Export CSV", command=self.export_measurements_csv).grid(
            row=3, column=0, sticky="ew", pady=(4, 0)
        )
        ttk.Button(manage_group, text="Set ROI Role", command=self.assign_roi_role).grid(
            row=4, column=0, sticky="ew", pady=(4, 0)
        )

    def _build_analysis_toolbar(self, tab: ttk.Frame) -> None:
        analysis_notebook = ttk.Notebook(tab)
        analysis_notebook.pack(fill="both", expand=True)

        signal_tab = ttk.Frame(analysis_notebook, padding=(4, 4, 4, 4))
        image_tab = ttk.Frame(analysis_notebook, padding=(4, 4, 4, 4))
        history_tab = ttk.Frame(analysis_notebook, padding=(4, 4, 4, 4))
        analysis_notebook.add(signal_tab, text="Signal Analysis")
        analysis_notebook.add(image_tab, text="Image Analysis")
        analysis_notebook.add(history_tab, text="Results History")

        signal_strip = self._build_grouped_toolbar_strip(signal_tab)
        self._build_signal_analysis_toolbar(signal_strip)
        self._build_image_analysis_toolbar(image_tab)
        self._build_results_history_panel(history_tab)
        self.analysis_inputs["cnr_formula"].trace_add("write", self._update_cnr_formula_ui)
        self.analysis_inputs["uniformity_input_mode"].trace_add("write", self._update_uniformity_input_ui)
        self.image_analysis_inputs["scope_type"].trace_add("write", self._update_image_scope_ui)
        self._update_cnr_formula_ui()
        self._update_uniformity_input_ui()
        self._update_image_scope_ui()
        self._refresh_analysis_selectors()

    def _build_signal_analysis_toolbar(self, strip: ttk.Frame) -> None:
        for key in ("snr_signal", "snr_noise", "cnr_target", "cnr_reference", "cnr_noise"):
            self._analysis_selector_vars[key] = tk.StringVar(value="")

        snr_group = ttk.LabelFrame(strip, text="SNR", padding=(8, 6))
        snr_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(snr_group, text="Input: Signal ROI").grid(row=0, column=0, sticky="w")
        self._analysis_comboboxes["snr_signal"] = ttk.Combobox(
            snr_group,
            state="readonly",
            width=42,
            textvariable=self._analysis_selector_vars["snr_signal"],
        )
        self._analysis_comboboxes["snr_signal"].grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(snr_group, text="Input: Background ROI").grid(row=2, column=0, sticky="w")
        self._analysis_comboboxes["snr_noise"] = ttk.Combobox(
            snr_group,
            state="readonly",
            width=42,
            textvariable=self._analysis_selector_vars["snr_noise"],
        )
        self._analysis_comboboxes["snr_noise"].grid(row=3, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(snr_group, text="Formula: mean(Signal ROI) / std(Background ROI)").grid(row=4, column=0, sticky="w")
        ttk.Label(snr_group, textvariable=self.signal_analysis_results["snr_preview"]).grid(row=5, column=0, sticky="w", pady=(2, 0))
        ttk.Label(snr_group, textvariable=self.signal_analysis_results["snr_result"]).grid(row=6, column=0, sticky="w", pady=(2, 0))
        self._analysis_action_buttons["snr"] = ttk.Button(snr_group, text="Calculate SNR", command=self.calculate_snr_from_inputs)
        self._analysis_action_buttons["snr"].grid(row=7, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(snr_group, textvariable=self.signal_analysis_results["snr_ready_reason"]).grid(row=8, column=0, sticky="w", pady=(2, 0))

        cnr_group = ttk.LabelFrame(strip, text="CNR", padding=(8, 6))
        cnr_group.pack(side="left", padx=(0, 8), fill="y")
        formula_cards = ttk.LabelFrame(cnr_group, text="Formula Selection", padding=(6, 4))
        formula_cards.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Radiobutton(formula_cards, text="Option A | |S_A - S_B| / sigma_o", value="standard_noise", variable=self.analysis_inputs["cnr_formula"]).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(formula_cards, text="Option B | |S_A - S_B| / sqrt(sigma_A^2 + sigma_B^2)", value="dual_variance", variable=self.analysis_inputs["cnr_formula"]).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(cnr_group, text="Input: Signal ROI").grid(row=1, column=0, sticky="w")
        self._analysis_comboboxes["cnr_target"] = ttk.Combobox(
            cnr_group,
            state="readonly",
            width=42,
            textvariable=self._analysis_selector_vars["cnr_target"],
        )
        self._analysis_comboboxes["cnr_target"].grid(row=2, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(cnr_group, text="Input: Reference ROI").grid(row=3, column=0, sticky="w")
        self._analysis_comboboxes["cnr_reference"] = ttk.Combobox(
            cnr_group,
            state="readonly",
            width=42,
            textvariable=self._analysis_selector_vars["cnr_reference"],
        )
        self._analysis_comboboxes["cnr_reference"].grid(row=4, column=0, sticky="ew", pady=(2, 4))
        noise_label = ttk.Label(cnr_group, text="Input: Background ROI")
        noise_label.grid(row=5, column=0, sticky="w")
        self._analysis_comboboxes["cnr_noise"] = ttk.Combobox(
            cnr_group,
            state="readonly",
            width=42,
            textvariable=self._analysis_selector_vars["cnr_noise"],
        )
        self._analysis_comboboxes["cnr_noise"].grid(row=6, column=0, sticky="ew", pady=(2, 4))
        self._cnr_noise_widgets = [noise_label, self._analysis_comboboxes["cnr_noise"]]
        ttk.Label(cnr_group, textvariable=self.signal_analysis_results["cnr_preview"]).grid(row=7, column=0, sticky="w", pady=(2, 0))
        ttk.Label(cnr_group, textvariable=self.signal_analysis_results["cnr_result"]).grid(row=8, column=0, sticky="w", pady=(2, 0))
        self._analysis_action_buttons["cnr"] = ttk.Button(cnr_group, text="Calculate CNR", command=self.calculate_cnr_from_inputs)
        self._analysis_action_buttons["cnr"].grid(row=9, column=0, sticky="ew", pady=(6, 0))

        uniformity_group = ttk.LabelFrame(strip, text="Uniformity", padding=(8, 6))
        uniformity_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(uniformity_group, text="Formula").grid(row=0, column=0, sticky="w")
        uniformity_formula_combo = ttk.Combobox(
            uniformity_group,
            state="readonly",
            width=40,
            values=[
                "max_min | 1 - (max-min)/(max+min)",
                "std_mean | 1 - std/mean",
            ],
        )
        uniformity_formula_combo.grid(row=1, column=0, sticky="ew", pady=(2, 4))
        uniformity_formula_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_uniformity_formula_selected())
        self._analysis_comboboxes["uniformity_formula"] = uniformity_formula_combo

        ttk.Label(uniformity_group, text="ROI Input").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(
            uniformity_group,
            text="Selected ROI set",
            value="selected_rois",
            variable=self.analysis_inputs["uniformity_input_mode"],
        ).grid(row=3, column=0, sticky="w")
        ttk.Radiobutton(
            uniformity_group,
            text="Role-based ROI set",
            value="role_group",
            variable=self.analysis_inputs["uniformity_input_mode"],
        ).grid(row=4, column=0, sticky="w")

        self._uniformity_roi_listbox = tk.Listbox(uniformity_group, selectmode=tk.EXTENDED, height=5, exportselection=False, width=44)
        self._uniformity_roi_listbox.grid(row=5, column=0, sticky="ew", pady=(4, 4))
        ttk.Label(uniformity_group, text="Role filter (csv)").grid(row=6, column=0, sticky="w")
        ttk.Entry(uniformity_group, textvariable=self.analysis_inputs["uniformity_role_filter"], width=42).grid(row=7, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(uniformity_group, textvariable=self.signal_analysis_results["uniformity_preview"]).grid(row=8, column=0, sticky="w", pady=(2, 0))
        ttk.Label(uniformity_group, textvariable=self.signal_analysis_results["uniformity_result"]).grid(row=9, column=0, sticky="w", pady=(2, 0))
        ttk.Button(uniformity_group, text="Calculate Uniformity", command=self.calculate_uniformity_from_inputs).grid(row=10, column=0, sticky="ew", pady=(6, 0))

        line_group = ttk.LabelFrame(strip, text="Line Profile", padding=(8, 6))
        line_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(line_group, text="Input: Profile Line").grid(row=0, column=0, sticky="w")
        self._analysis_comboboxes["line_profile"] = ttk.Combobox(line_group, state="readonly", width=42)
        self._analysis_comboboxes["line_profile"].grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(line_group, text="Formula: intensity(x) sampled along selected line").grid(row=2, column=0, sticky="w")
        ttk.Label(line_group, textvariable=self.signal_analysis_results["line_info"]).grid(row=3, column=0, sticky="w", pady=(2, 0))
        ttk.Button(line_group, text="Show Line Profile", command=self.show_line_profile_for_selected_line).grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(line_group, text="Show Feature Details", command=self.show_line_profile_feature_details).grid(row=5, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(line_group, text="Export Profile CSV", command=self.export_selected_line_profile_csv).grid(row=6, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(line_group, textvariable=self.snr_workflow_var).grid(row=7, column=0, sticky="w", pady=(2, 0))

        self._build_analysis_results_panel(strip)
        self._bind_analysis_selector_events()

    def _bind_analysis_selector_events(self) -> None:
        for key in ("snr_signal", "snr_noise", "cnr_target", "cnr_reference", "cnr_noise"):
            combo = self._analysis_comboboxes.get(key)
            if combo is None:
                continue
            combo.bind("<<ComboboxSelected>>", self._on_analysis_selector_changed, add="+")
        line_combo = self._analysis_comboboxes.get("line_profile")
        if line_combo is not None:
            line_combo.bind("<<ComboboxSelected>>", self._on_line_profile_selection_changed, add="+")

    def _on_analysis_selector_changed(self, _event: tk.Event | None = None) -> None:
        self._sync_analysis_input_from_combobox("roi", "snr_signal", "snr_signal_roi_id")
        self._sync_analysis_input_from_combobox("roi", "snr_noise", "snr_background_roi_id")
        self._sync_analysis_input_from_combobox("roi", "cnr_target", "cnr_target_roi_id")
        self._sync_analysis_input_from_combobox("roi", "cnr_reference", "cnr_reference_roi_id")
        self._sync_analysis_input_from_combobox("roi", "cnr_noise", "cnr_noise_roi_id")
        self._update_analysis_action_button_state()

    def _on_line_profile_selection_changed(self, _event: tk.Event | None = None) -> None:
        self._sync_analysis_input_from_combobox("line", "line_profile", "line_profile_line_id")
        measurement = self._get_selected_measurement_from_analysis("line", "line_profile_line_id", "line_profile")
        if measurement is None:
            self.analysis_results["line_info"].set("Line: Select Profile Line")
            return
        profile = self.extract_line_profile(measurement)
        if profile is None:
            self.analysis_results["line_info"].set("Line: Profile unavailable")
            return
        summary = self.summarize_line_profile(profile)
        line_index = self._line_index_for_measurement_id(measurement.id)
        line_label = f"Line {line_index}" if line_index is not None else measurement.id[:8]
        self.analysis_results["line_info"].set(
            f"{line_label} | n={summary['sample_count']} | min={summary['min_intensity']:.2f} | "
            f"max={summary['max_intensity']:.2f} | mean={summary['mean_intensity']:.2f}"
        )

    def _sync_analysis_input_from_combobox(self, kind: str, combobox_key: str, input_key: str) -> None:
        combobox = self._analysis_comboboxes.get(combobox_key)
        if combobox is None:
            return
        selected_label = combobox.get().strip()
        if not selected_label:
            return
        option_map = self._analysis_option_maps.get(kind, {})
        mapped_id = option_map.get(selected_label, "")
        if mapped_id:
            self.analysis_inputs[input_key].set(mapped_id)

    def _build_image_analysis_toolbar(self, tab: ttk.Frame) -> None:
        frame = ttk.Frame(tab)
        frame.pack(fill="x")
        pairing_group = ttk.LabelFrame(frame, text="Image Pairing", padding=(8, 6))
        pairing_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(pairing_group, text="Reference Image").grid(row=0, column=0, sticky="w")
        self._image_analysis_comboboxes["reference_image"] = ttk.Combobox(pairing_group, state="readonly", width=52)
        self._image_analysis_comboboxes["reference_image"].grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(pairing_group, text="Target Image").grid(row=2, column=0, sticky="w")
        self._image_analysis_comboboxes["target_image"] = ttk.Combobox(pairing_group, state="readonly", width=52)
        self._image_analysis_comboboxes["target_image"].grid(row=3, column=0, sticky="ew", pady=(2, 4))
        ttk.Button(pairing_group, text="현재 이미지를 Reference로", command=self._set_current_image_as_reference).grid(row=4, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(pairing_group, text="현재 이미지를 Target으로", command=self._set_current_image_as_target).grid(row=5, column=0, sticky="ew", pady=(4, 0))

        scope_group = ttk.LabelFrame(frame, text="Scope", padding=(8, 6))
        scope_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Radiobutton(scope_group, text="Full Image", value="full", variable=self.image_analysis_inputs["scope_type"]).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(scope_group, text="Selected ROI", value="roi", variable=self.image_analysis_inputs["scope_type"]).grid(row=1, column=0, sticky="w")
        self._image_analysis_comboboxes["scope_roi"] = ttk.Combobox(scope_group, state="readonly", width=42)
        self._image_analysis_comboboxes["scope_roi"].grid(row=2, column=0, sticky="ew", pady=(6, 0))

        result_group = ttk.LabelFrame(frame, text="Image Metrics", padding=(8, 6))
        result_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(result_group, textvariable=self.image_analysis_results["image_formula"]).grid(row=0, column=0, sticky="w")
        ttk.Label(result_group, textvariable=self.image_analysis_results["image_result"]).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(result_group, text="Calculate SSIM / PSNR / MSE / HIST", command=self.calculate_image_comparison_metrics).grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _build_analysis_results_panel(self, strip: ttk.Frame) -> None:
        panel = ttk.LabelFrame(strip, text="Analysis Results", padding=(8, 6))
        panel.pack(side="left", padx=(0, 8), fill="both", expand=True)
        header = ttk.Frame(panel)
        header.grid(row=0, column=0, sticky="ew", columnspan=2)
        header.columnconfigure(0, weight=0, minsize=220)
        header.columnconfigure(1, weight=0, minsize=180)
        header.columnconfigure(2, weight=1, minsize=300)
        ttk.Label(header, text="Item", anchor="w").grid(row=0, column=0, sticky="ew", padx=(2, 8))
        ttk.Label(header, text="Value", anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(header, text="Note", anchor="w").grid(row=0, column=2, sticky="ew")

        canvas = tk.Canvas(
            panel,
            background="#FFFFFF",
            highlightthickness=1,
            highlightbackground=self.ui_colors["border"],
            bd=0,
        )
        canvas.grid(row=1, column=0, sticky="nsew", columnspan=2)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=1, column=2, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        rows_container = ttk.Frame(canvas)
        rows_window = canvas.create_window((0, 0), window=rows_container, anchor="nw")

        def _sync_scroll_region(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_row_container_width(_event: tk.Event) -> None:
            canvas.itemconfigure(rows_window, width=_event.width)
            self._relayout_analysis_result_rows()

        rows_container.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _sync_row_container_width)

        ttk.Button(panel, text="Export Results CSV", command=self.export_analysis_results_csv).grid(row=2, column=0, sticky="ew", pady=(6, 0), padx=(0, 4))
        ttk.Button(panel, text="Export Results JSON", command=self.export_analysis_results_json).grid(row=2, column=1, sticky="ew", pady=(6, 0), padx=(4, 0))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self.analysis_results_table = panel
        self.analysis_results_canvas = canvas
        self.analysis_results_rows_container = rows_container

    def _build_results_history_panel(self, tab: ttk.Frame) -> None:
        panel = ttk.LabelFrame(tab, text="Measurement History", padding=(8, 6))
        panel.pack(fill="both", expand=True)
        toolbar = ttk.Frame(panel)
        toolbar.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 6))
        ttk.Label(toolbar, text="Type Filter").pack(side="left")
        filter_combo = ttk.Combobox(
            toolbar,
            state="readonly",
            width=16,
            values=["All", "ROI", "Analysis", "Line Profile"],
            textvariable=self.history_metric_filter_var,
        )
        filter_combo.pack(side="left", padx=(6, 12))
        filter_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_result_history_table())
        ttk.Label(toolbar, text="Search").pack(side="left")
        search_entry = ttk.Entry(toolbar, textvariable=self.history_search_var, width=32)
        search_entry.pack(side="left", padx=(6, 0))
        search_entry.bind("<KeyRelease>", lambda _event: self._refresh_result_history_table())
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
        tree.bind("<<TreeviewSelect>>", self._on_history_row_selected, add="+")
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        scrollbar.grid(row=1, column=5, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        ttk.Button(panel, text="Delete Selected", command=self.delete_selected_history_rows).grid(row=2, column=0, sticky="ew", pady=(6, 0), padx=(0, 4))
        ttk.Button(panel, text="Clear All", command=self.clear_result_history).grid(row=2, column=1, sticky="ew", pady=(6, 0), padx=4)
        ttk.Button(panel, text="Copy Clipboard", command=self.copy_result_history_to_clipboard).grid(row=2, column=2, sticky="ew", pady=(6, 0), padx=4)
        ttk.Button(panel, text="Export Selected CSV", command=self.export_selected_result_history_csv).grid(row=2, column=3, sticky="ew", pady=(6, 0), padx=4)
        ttk.Button(panel, text="Export All CSV", command=self.export_result_history_csv).grid(row=2, column=4, sticky="ew", pady=(6, 0), padx=(4, 0))
        compare_button = ttk.Button(panel, text="Compare Selected", command=self.compare_selected_history_rows, state="disabled")
        compare_button.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(6, 0))
        for col in range(5):
            panel.grid_columnconfigure(col, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self.result_history_table = tree
        self.history_compare_button = compare_button

    @staticmethod
    def _history_export_columns() -> tuple[str, ...]:
        return ("Timestamp", "ImageName", "Frame", "MeasurementType", "TargetName", "Metric", "Value", "Unit", "Note")

    def _current_image_name(self) -> str:
        file_paths = getattr(self, "file_paths", [])
        current_file_index = int(getattr(self, "current_file_index", -1))
        if file_paths and 0 <= current_file_index < len(file_paths):
            return Path(file_paths[current_file_index]).name
        path_text = ""
        if hasattr(self, "path_var") and self.path_var is not None:
            try:
                path_text = self.path_var.get().strip()
            except Exception:
                path_text = ""
        if path_text:
            return Path(path_text).name
        return "N/A"

    def _current_history_context(self) -> dict[str, Any]:
        measurement_mode = "unknown"
        if hasattr(self, "measurement_mode") and self.measurement_mode is not None:
            try:
                measurement_mode = str(self.measurement_mode.get())
            except Exception:
                measurement_mode = "unknown"
        return {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "image_name": self._current_image_name(),
            "image_path": self._get_current_image_path() if hasattr(self, "_get_current_image_path") else "",
            "frame_index": int(self.current_frame),
            "measurement_mode": measurement_mode,
        }

    def _append_history_entry(
        self,
        measurement_type: str,
        target_name: str,
        metric: str,
        value: float,
        unit: str,
        note: str,
        measurement_mode: str = "",
        target_id: str = "",
        related_target_ids: list[str] | None = None,
    ) -> None:
        if not hasattr(self, "result_history_store") or self.result_history_store is None:
            self.result_history_store = ResultHistoryStore()
        context = self._current_history_context()
        entry = ResultHistoryEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=context["timestamp"],
            image_name=context["image_name"],
            frame_index=context["frame_index"],
            measurement_type=measurement_type,
            target_name=target_name,
            metric=metric,
            value=float(value),
            unit=unit,
            note=note,
            measurement_mode=measurement_mode or context["measurement_mode"],
            source_image_path=str(context.get("image_path", "")),
            target_id=target_id,
            related_target_ids=list(related_target_ids or []),
        )
        self.result_history_store.append(entry)
        self._refresh_result_history_table()

    @staticmethod
    def _serialize_history_entry(entry: ResultHistoryEntry) -> dict[str, Any]:
        return {
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp,
            "image_name": entry.image_name,
            "frame_index": int(entry.frame_index),
            "measurement_type": entry.measurement_type,
            "target_name": entry.target_name,
            "metric": entry.metric,
            "value": float(entry.value),
            "unit": entry.unit,
            "note": entry.note,
            "measurement_mode": entry.measurement_mode,
            "source_image_path": entry.source_image_path,
            "target_id": entry.target_id,
            "related_target_ids": list(entry.related_target_ids),
        }

    @staticmethod
    def _deserialize_history_entry(payload: dict[str, Any]) -> ResultHistoryEntry:
        return ResultHistoryEntry(
            entry_id=str(payload.get("entry_id") or uuid.uuid4()),
            timestamp=str(payload.get("timestamp", "")),
            image_name=str(payload.get("image_name", "N/A")),
            frame_index=int(payload.get("frame_index", 0)),
            measurement_type=str(payload.get("measurement_type", "")),
            target_name=str(payload.get("target_name", "")),
            metric=str(payload.get("metric", "")),
            value=float(payload.get("value", 0.0)),
            unit=str(payload.get("unit", "")),
            note=str(payload.get("note", "")),
            measurement_mode=str(payload.get("measurement_mode", "unknown")),
            source_image_path=str(payload.get("source_image_path", "")),
            target_id=str(payload.get("target_id", "")),
            related_target_ids=[str(item) for item in (payload.get("related_target_ids") or [])],
        )

    def _refresh_result_history_table(self) -> None:
        table = getattr(self, "result_history_table", None)
        if table is None:
            return
        selected_type = self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All"
        search_text = self.history_search_var.get() if hasattr(self, "history_search_var") else ""
        grouped_rows = self.build_grouped_history_view(selected_type, search_text)
        self.render_grouped_history_table(grouped_rows)
        self._restore_history_selection()
        self._update_history_compare_button_state()

    @staticmethod
    def _metric_bucket_key(metric_name: str) -> str | None:
        normalized = metric_name.strip().lower().replace(" ", "")
        if normalized in {"mean"}:
            return "mean"
        if normalized in {"std", "stddev", "standarddeviation"}:
            return "std"
        if normalized in {"min", "minimum"}:
            return "min"
        if normalized in {"max", "maximum"}:
            return "max"
        if normalized.startswith("area"):
            return "area"
        if normalized in {"length(px)", "lengthpx"}:
            return "length_px"
        if normalized in {"length(mm)", "lengthmm"}:
            return "length_mm"
        if normalized.startswith("peaks"):
            return "peaks"
        if normalized.startswith("valleys"):
            return "valleys"
        return None

    def group_history_entries(self, rows: list[tuple[int, ResultHistoryEntry]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, int, str, str], dict[str, Any]] = {}
        for store_index, entry in rows:
            key = (
                entry.timestamp,
                entry.image_name,
                int(entry.frame_index),
                entry.measurement_type,
                entry.target_name,
            )
            payload = grouped.setdefault(
                key,
                {
                    "timestamp": entry.timestamp,
                    "image_name": entry.image_name,
                    "frame_index": str(entry.frame_index),
                    "measurement_type": entry.measurement_type,
                    "target_name": entry.target_name,
                    "metric": "",
                    "value": "",
                    "mean": "",
                    "std": "",
                    "min": "",
                    "max": "",
                    "area": "",
                    "length_px": "",
                    "length_mm": "",
                    "peaks": "",
                    "valleys": "",
                    "unit": "",
                    "note": "",
                    "store_indices": [],
                    "entry_ids": [],
                    "primary_entry": entry,
                },
            )
            payload["store_indices"].append(store_index)
            payload["entry_ids"].append(entry.entry_id)
            bucket = self._metric_bucket_key(entry.metric)
            value_text = f"{entry.value:.2f}"
            if bucket is not None:
                payload[bucket] = value_text
            elif not payload["metric"]:
                payload["metric"] = entry.metric
                payload["value"] = value_text
            notes = [line for line in [payload["note"], entry.note] if line]
            payload["note"] = "\n".join(dict.fromkeys(notes))
            units = [item for item in [payload["unit"], entry.unit] if item]
            payload["unit"] = ", ".join(dict.fromkeys(units))
        return sorted(
            grouped.values(),
            key=lambda row: (row["timestamp"], row["image_name"], row["frame_index"], row["measurement_type"], row["target_name"]),
            reverse=True,
        )

    def build_grouped_history_view(self, measurement_type: str = "All", search_text: str = "") -> list[dict[str, Any]]:
        raw_rows = self.result_history_store.filtered_entries(measurement_type, "")
        grouped_rows = self.group_history_entries(raw_rows)
        query = search_text.strip().lower()
        if not query:
            return grouped_rows
        filtered: list[dict[str, Any]] = []
        for row in grouped_rows:
            haystack = " ".join(
                [
                    str(row.get("image_name", "")),
                    str(row.get("target_name", "")),
                    str(row.get("measurement_type", "")),
                    str(row.get("metric", "")),
                    str(row.get("note", "")),
                ]
            ).lower()
            if query in haystack:
                filtered.append(row)
        return filtered

    def render_grouped_history_table(self, grouped_rows: list[dict[str, Any]]) -> None:
        table = getattr(self, "result_history_table", None)
        if table is None:
            return
        self._history_item_to_store_indices = {}
        for item_id in table.get_children():
            table.delete(item_id)
        row_values: list[tuple[str, ...]] = []
        for row in grouped_rows:
            values = (
                str(row.get("timestamp", "")),
                str(row.get("image_name", "")),
                str(row.get("frame_index", "")),
                str(row.get("measurement_type", "")),
                str(row.get("target_name", "")),
                str(row.get("metric", "")),
                str(row.get("value", "")),
                str(row.get("mean", "")),
                str(row.get("std", "")),
                str(row.get("min", "")),
                str(row.get("max", "")),
                str(row.get("area", "")),
                str(row.get("length_px", "")),
                str(row.get("length_mm", "")),
                str(row.get("peaks", "")),
                str(row.get("valleys", "")),
                str(row.get("unit", "")),
                str(row.get("note", "")),
            )
            item_id = table.insert("", "end", values=values)
            self._history_item_to_store_indices[item_id] = list(row.get("store_indices", []))
            row_values.append(values)
        self._update_treeview_row_height_for_notes(table, "ResultHistory.Treeview", row_values, note_index=17)

    def _update_treeview_row_height_for_notes(
        self,
        table: ttk.Treeview,
        style_name: str,
        rows: list[tuple[str, ...]],
        note_index: int,
    ) -> None:
        default_font = tkfont.nametofont("TkDefaultFont")
        line_height = default_font.metrics("linespace")
        note_width = int(table.column("note", "width")) - 12
        note_width = max(48, note_width)
        max_lines = 1
        for values in rows:
            if note_index >= len(values):
                continue
            note_text = str(values[note_index] or "")
            line_count = 0
            for paragraph in note_text.split("\n"):
                if not paragraph:
                    line_count += 1
                    continue
                width = 0
                line_count += 1
                for char in paragraph:
                    char_width = default_font.measure(char)
                    if width + char_width > note_width and width > 0:
                        line_count += 1
                        width = char_width
                    else:
                        width += char_width
            max_lines = max(max_lines, line_count)
        row_height = max(22, (line_height * max_lines) + 8)
        ttk.Style(self.root).configure(style_name, rowheight=row_height)

    def _selected_history_entries(self) -> list[tuple[int, ResultHistoryEntry]]:
        table = self.result_history_table
        if table is None:
            return []
        selected: list[tuple[int, ResultHistoryEntry]] = []
        all_entries = self.result_history_store.entries()
        seen_indices: set[int] = set()
        for item_id in table.selection():
            for store_index in self._history_item_to_store_indices.get(item_id, []):
                if store_index in seen_indices:
                    continue
                if not (0 <= store_index < len(all_entries)):
                    continue
                selected.append((store_index, all_entries[store_index]))
                seen_indices.add(store_index)
        return selected

    def delete_selected_history_rows(self) -> None:
        table = self.result_history_table
        if table is None:
            return
        selected_rows = self._selected_history_entries()
        if not selected_rows:
            messagebox.showinfo("Results History", "삭제할 행을 선택하세요.")
            return
        indices = [index for index, _entry in selected_rows]
        self.result_history_store.remove_indices(indices)
        self._refresh_result_history_table()

    def clear_result_history(self) -> None:
        self.result_history_store.clear()
        self._refresh_result_history_table()

    def _write_result_history_csv(self, path: str, entries: list[ResultHistoryEntry]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self._history_export_columns())
            for entry in entries:
                writer.writerow(
                    [
                        entry.timestamp,
                        entry.image_name,
                        str(entry.frame_index),
                        entry.measurement_type,
                        entry.target_name,
                        entry.metric,
                        f"{entry.value:.2f}",
                        entry.unit,
                        entry.note,
                    ]
                )

    @staticmethod
    def _grouped_history_export_columns() -> tuple[str, ...]:
        return (
            "Timestamp",
            "ImageName",
            "Frame",
            "MeasurementType",
            "TargetName",
            "Metric",
            "Value",
            "Mean",
            "Std",
            "Min",
            "Max",
            "Area",
            "Length(px)",
            "Length(mm)",
            "Peaks",
            "Valleys",
            "Unit",
            "Note",
        )

    def _write_grouped_result_history_csv(self, path: str, grouped_rows: list[dict[str, Any]]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self._grouped_history_export_columns())
            for row in grouped_rows:
                writer.writerow(
                    [
                        row.get("timestamp", ""),
                        row.get("image_name", ""),
                        row.get("frame_index", ""),
                        row.get("measurement_type", ""),
                        row.get("target_name", ""),
                        row.get("metric", ""),
                        row.get("value", ""),
                        row.get("mean", ""),
                        row.get("std", ""),
                        row.get("min", ""),
                        row.get("max", ""),
                        row.get("area", ""),
                        row.get("length_px", ""),
                        row.get("length_mm", ""),
                        row.get("peaks", ""),
                        row.get("valleys", ""),
                        row.get("unit", ""),
                        row.get("note", ""),
                    ]
                )

    def export_result_history_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Results History CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        grouped_rows = self.build_grouped_history_view(
            self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All",
            self.history_search_var.get() if hasattr(self, "history_search_var") else "",
        )
        self._write_grouped_result_history_csv(path, grouped_rows)
        messagebox.showinfo("저장 완료", f"Results History CSV 저장 완료:\n{path}")

    def export_selected_result_history_csv(self) -> None:
        selected_rows = self._selected_history_entries()
        if not selected_rows:
            messagebox.showinfo("Results History", "내보낼 행을 선택하세요.")
            return
        path = filedialog.asksaveasfilename(
            title="선택된 Results History CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        selected_indices = {index for index, _entry in selected_rows}
        grouped_rows = [
            row
            for row in self.build_grouped_history_view(
                self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All",
                self.history_search_var.get() if hasattr(self, "history_search_var") else "",
            )
            if selected_indices.intersection(set(row.get("store_indices", [])))
        ]
        self._write_grouped_result_history_csv(path, grouped_rows)
        messagebox.showinfo("저장 완료", f"선택 행 CSV 저장 완료:\n{path}")

    def copy_result_history_to_clipboard(self) -> None:
        selected_rows = self._selected_history_entries()
        selected_indices = {index for index, _entry in selected_rows}
        grouped_rows = self.build_grouped_history_view(
            self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All",
            self.history_search_var.get() if hasattr(self, "history_search_var") else "",
        )
        if selected_indices:
            grouped_rows = [row for row in grouped_rows if selected_indices.intersection(set(row.get("store_indices", [])))]
        lines = [",".join(self._grouped_history_export_columns())]
        for row in grouped_rows:
            values = [
                str(row.get("timestamp", "")),
                str(row.get("image_name", "")),
                str(row.get("frame_index", "")),
                str(row.get("measurement_type", "")),
                str(row.get("target_name", "")),
                str(row.get("metric", "")),
                str(row.get("value", "")),
                str(row.get("mean", "")),
                str(row.get("std", "")),
                str(row.get("min", "")),
                str(row.get("max", "")),
                str(row.get("area", "")),
                str(row.get("length_px", "")),
                str(row.get("length_mm", "")),
                str(row.get("peaks", "")),
                str(row.get("valleys", "")),
                str(row.get("unit", "")),
                str(row.get("note", "")).replace("\n", " | "),
            ]
            lines.append(",".join(values))
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        messagebox.showinfo("Results History", "히스토리를 클립보드에 복사했습니다.")

    def _on_history_row_selected(self, _event: tk.Event | None = None) -> None:
        selected_rows = self._selected_history_entries()
        self._session_compare_state["selected_entry_ids"] = [entry.entry_id for _index, entry in selected_rows]
        self._session_compare_state["baseline_index"] = 0
        self._update_history_compare_button_state()
        table = self.result_history_table
        if table is None:
            return
        selection = list(table.selection())
        if len(selection) != 1:
            return
        all_entries = self.result_history_store.entries()
        store_indices = self._history_item_to_store_indices.get(selection[0], [])
        if not store_indices:
            return
        primary_index = store_indices[0]
        if not (0 <= primary_index < len(all_entries)):
            return
        entry = all_entries[primary_index]
        self.activate_history_entry(entry)

    def _restore_history_selection(self, selected_entry_ids: list[str] | None = None) -> None:
        table = self.result_history_table
        if table is None:
            return
        wanted_ids = list(selected_entry_ids or self._session_compare_state.get("selected_entry_ids", []))
        if not wanted_ids:
            return
        all_entries = self.result_history_store.entries()
        id_to_items: dict[str, set[str]] = {}
        for item_id, store_indices in self._history_item_to_store_indices.items():
            for store_index in store_indices:
                if not (0 <= store_index < len(all_entries)):
                    continue
                entry_id = all_entries[store_index].entry_id
                id_to_items.setdefault(entry_id, set()).add(item_id)
        item_ids: list[str] = []
        for entry_id in wanted_ids:
            item_ids.extend(sorted(id_to_items.get(entry_id, set())))
        if item_ids:
            table.selection_set(item_ids)

    def _update_history_compare_button_state(self) -> None:
        button = self.history_compare_button
        if button is None:
            return
        table = self.result_history_table
        selected_count = len(table.selection()) if table is not None else 0
        if 2 <= selected_count <= 5:
            button.configure(state="normal")
        else:
            button.configure(state="disabled")

    @staticmethod
    def _format_percent_change(current: float, baseline: float) -> str:
        if abs(baseline) < 1e-12:
            return "N/A"
        return f"{((current - baseline) / baseline) * 100.0:.2f}%"

    def _line_profile_cache_key(self, source_image_path: str, frame_index: int, target_id: str) -> str:
        return f"{source_image_path}|{int(frame_index)}|{target_id}"

    def resolve_line_profile_series(self, entry: ResultHistoryEntry) -> dict[str, Any] | None:
        if entry.measurement_type != "Line Profile" or not entry.target_id:
            return None
        cache_key = self._line_profile_cache_key(entry.source_image_path, entry.frame_index, entry.target_id)
        if cache_key in self.line_profile_series_cache:
            return self.line_profile_series_cache[cache_key]
        latest_line_profile = self.analysis_last_run.get("line_profile", {})
        latest_inputs = latest_line_profile.get("inputs", {})
        latest_result = latest_line_profile.get("result", {})
        if latest_inputs.get("line_id") == entry.target_id and latest_result.get("distance_px"):
            series = {
                "distance_px": list(latest_result.get("distance_px", [])),
                "distance_mm": latest_result.get("distance_mm"),
                "intensity": list(latest_result.get("intensity", [])),
            }
            self.line_profile_series_cache[cache_key] = series
            return series
        measurement = self._find_measurement_by_id(entry.target_id, expected_kind="line")
        if measurement is None:
            return None
        profile = self.extract_line_profile(measurement)
        if profile is None:
            return None
        series = {
            "distance_px": np.asarray(profile.get("distance_px", []), dtype=np.float64).tolist(),
            "distance_mm": None
            if profile.get("distance_mm") is None
            else np.asarray(profile.get("distance_mm", []), dtype=np.float64).tolist(),
            "intensity": np.asarray(profile.get("intensity", []), dtype=np.float64).tolist(),
        }
        self.line_profile_series_cache[cache_key] = series
        return series

    def build_line_profile_overlay_data(self, entries: list[ResultHistoryEntry]) -> dict[str, Any]:
        profile_entries = [entry for entry in entries if entry.measurement_type == "Line Profile"]
        if not profile_entries:
            return {"series": [], "axis": "px", "missing": []}
        deduped: list[ResultHistoryEntry] = []
        seen_keys: set[tuple[str, str, int]] = set()
        for entry in profile_entries:
            key = (entry.source_image_path, entry.target_id, int(entry.frame_index))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(entry)
        series_data: list[dict[str, Any]] = []
        missing_labels: list[str] = []
        for index, entry in enumerate(deduped):
            series = self.resolve_line_profile_series(entry)
            if series is None:
                missing_labels.append(entry.target_name or entry.metric)
                continue
            distance_px = np.asarray(series.get("distance_px", []), dtype=np.float64)
            intensity = np.asarray(series.get("intensity", []), dtype=np.float64)
            if distance_px.size == 0 or intensity.size == 0:
                missing_labels.append(entry.target_name or entry.metric)
                continue
            distance_mm_raw = series.get("distance_mm")
            distance_mm = None if distance_mm_raw is None else np.asarray(distance_mm_raw, dtype=np.float64)
            feature_input = {
                "distance_px": distance_px,
                "distance_mm": distance_mm,
                "intensity": intensity,
            }
            features = self.compute_profile_features(feature_input)
            series_data.append(
                {
                    "label": entry.target_name or entry.metric,
                    "distance_px": distance_px,
                    "distance_mm": distance_mm,
                    "intensity": intensity,
                    "is_baseline": index == 0,
                    "features": features,
                }
            )
        use_mm_axis = bool(series_data) and all(
            item["distance_mm"] is not None and len(item["distance_mm"]) == len(item["intensity"])
            for item in series_data
        )
        return {
            "series": series_data,
            "axis": "mm" if use_mm_axis else "px",
            "missing": missing_labels,
        }

    def render_line_profile_overlay_chart(self, parent: tk.Widget, overlay_data: dict[str, Any]) -> None:
        canvas = tk.Canvas(parent, bg="white", height=220, highlightthickness=1, highlightbackground="#d1d5db")
        canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        series = overlay_data.get("series", [])
        if not series:
            canvas.create_text(12, 12, text="Line profile data unavailable", anchor="nw", fill="#6b7280")
            return
        axis_key = "distance_mm" if overlay_data.get("axis") == "mm" else "distance_px"
        all_x = np.concatenate([np.asarray(item[axis_key], dtype=np.float64) for item in series])
        all_y = np.concatenate([np.asarray(item["intensity"], dtype=np.float64) for item in series])
        x_min, x_max = float(np.min(all_x)), float(np.max(all_x))
        y_min, y_max = float(np.min(all_y)), float(np.max(all_y))
        if abs(x_max - x_min) < 1e-9:
            x_max = x_min + 1.0
        if abs(y_max - y_min) < 1e-9:
            y_max = y_min + 1.0
        width = max(canvas.winfo_reqwidth(), 900)
        height = 220
        left, top, right, bottom = 56, 18, width - 16, height - 34
        canvas.create_line(left, bottom, right, bottom, fill="#9ca3af")
        canvas.create_line(left, top, left, bottom, fill="#9ca3af")
        colors = ("#2563eb", "#dc2626", "#16a34a", "#a855f7", "#f59e0b")
        for index, item in enumerate(series):
            xs = np.asarray(item[axis_key], dtype=np.float64)
            ys = np.asarray(item["intensity"], dtype=np.float64)
            points: list[float] = []
            for x_value, y_value in zip(xs, ys):
                px = left + (float(x_value - x_min) / float(x_max - x_min)) * (right - left)
                py = bottom - (float(y_value - y_min) / float(y_max - y_min)) * (bottom - top)
                points.extend([px, py])
            color = colors[index % len(colors)]
            width_px = 3 if item.get("is_baseline") else 2
            dash = () if item.get("is_baseline") else (4, 2)
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=width_px, dash=dash, smooth=True)
            self.render_profile_feature_markers(canvas, xs, ys, x_min, x_max, y_min, y_max, left, right, top, bottom, color)
            legend_y = top + index * 16
            canvas.create_line(right - 210, legend_y + 8, right - 188, legend_y + 8, fill=color, width=width_px, dash=dash)
            canvas.create_text(right - 182, legend_y + 8, text=item["label"], anchor="w", fill="#111827")
        x_label = "Distance (mm)" if overlay_data.get("axis") == "mm" else "Distance (px)"
        canvas.create_text((left + right) / 2, height - 12, text=x_label, fill="#374151")
        canvas.create_text(12, (top + bottom) / 2, text="Intensity", fill="#374151", angle=90)

    def find_half_max_crossings(
        self,
        x_values: np.ndarray,
        y_values: np.ndarray,
        peak_index: int,
        half_max: float,
    ) -> tuple[float | None, float | None]:
        left_cross: float | None = None
        right_cross: float | None = None
        for index in range(peak_index, 0, -1):
            y1, y0 = float(y_values[index]), float(y_values[index - 1])
            if (y1 - half_max) * (y0 - half_max) <= 0 and abs(y1 - y0) > 1e-12:
                ratio = (half_max - y0) / (y1 - y0)
                left_cross = float(x_values[index - 1] + ratio * (x_values[index] - x_values[index - 1]))
                break
        for index in range(peak_index, len(y_values) - 1):
            y0, y1 = float(y_values[index]), float(y_values[index + 1])
            if (y0 - half_max) * (y1 - half_max) <= 0 and abs(y1 - y0) > 1e-12:
                ratio = (half_max - y0) / (y1 - y0)
                right_cross = float(x_values[index] + ratio * (x_values[index + 1] - x_values[index]))
                break
        return left_cross, right_cross

    def compute_fwhm(self, x_values: np.ndarray, y_values: np.ndarray, peak_index: int, peak_value: float) -> dict[str, Any]:
        if len(x_values) < 3 or len(y_values) < 3 or peak_value <= 0:
            return {"fwhm": None, "half_max": None, "left_cross": None, "right_cross": None}
        half_max = float(peak_value * 0.5)
        left_cross, right_cross = self.find_half_max_crossings(x_values, y_values, peak_index, half_max)
        if left_cross is None or right_cross is None or right_cross <= left_cross:
            return {"fwhm": None, "half_max": half_max, "left_cross": left_cross, "right_cross": right_cross}
        return {
            "fwhm": float(right_cross - left_cross),
            "half_max": half_max,
            "left_cross": left_cross,
            "right_cross": right_cross,
        }

    def compute_profile_features(self, profile: dict[str, Any]) -> dict[str, Any]:
        intensity = np.asarray(profile.get("intensity", []), dtype=np.float64)
        if intensity.size == 0:
            return {
                "peak_value": None,
                "peak_position": None,
                "valley_value": None,
                "valley_position": None,
                "fwhm": None,
                "distance_unit": "px",
                "half_max": None,
                "fwhm_left": None,
                "fwhm_right": None,
            }
        distance_mm_raw = profile.get("distance_mm")
        distance_mm = None if distance_mm_raw is None else np.asarray(distance_mm_raw, dtype=np.float64)
        use_mm = distance_mm is not None and len(distance_mm) == len(intensity)
        x_values = distance_mm if use_mm else np.asarray(profile.get("distance_px", []), dtype=np.float64)
        if len(x_values) != len(intensity):
            x_values = np.linspace(0.0, float(len(intensity) - 1), num=len(intensity))
        peak_index = int(np.argmax(intensity))
        valley_index = int(np.argmin(intensity))
        peak_value = float(intensity[peak_index])
        valley_value = float(intensity[valley_index])
        fwhm_data = self.compute_fwhm(x_values, intensity, peak_index, peak_value)
        return {
            "peak_value": peak_value,
            "peak_position": float(x_values[peak_index]),
            "valley_value": valley_value,
            "valley_position": float(x_values[valley_index]),
            "fwhm": fwhm_data["fwhm"],
            "distance_unit": "mm" if use_mm else "px",
            "half_max": fwhm_data["half_max"],
            "fwhm_left": fwhm_data["left_cross"],
            "fwhm_right": fwhm_data["right_cross"],
        }

    def render_profile_feature_markers(
        self,
        canvas: tk.Canvas,
        x_values: np.ndarray,
        y_values: np.ndarray,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        left: float,
        right: float,
        top: float,
        bottom: float,
        color: str,
    ) -> None:
        if len(x_values) < 2 or len(y_values) < 2:
            return
        profile = {"distance_px": x_values, "distance_mm": None, "intensity": y_values}
        features = self.compute_profile_features(profile)
        peak_pos = features.get("peak_position")
        peak_val = features.get("peak_value")
        if peak_pos is None or peak_val is None:
            return
        px = left + (float(peak_pos - x_min) / float(x_max - x_min)) * (right - left)
        py = bottom - (float(peak_val - y_min) / float(y_max - y_min)) * (bottom - top)
        canvas.create_oval(px - 3, py - 3, px + 3, py + 3, fill=color, outline="")
        left_cross = features.get("fwhm_left")
        right_cross = features.get("fwhm_right")
        half_max = features.get("half_max")
        if left_cross is None or right_cross is None or half_max is None:
            return
        x1 = left + (float(left_cross - x_min) / float(x_max - x_min)) * (right - left)
        x2 = left + (float(right_cross - x_min) / float(x_max - x_min)) * (right - left)
        yh = bottom - (float(half_max - y_min) / float(y_max - y_min)) * (bottom - top)
        canvas.create_line(x1, yh, x2, yh, fill=color, width=2)

    def build_delta_profile_data(self, overlay_data: dict[str, Any]) -> dict[str, Any]:
        series = list(overlay_data.get("series", []))
        if len(series) <= 1:
            return {"series": [], "axis": overlay_data.get("axis", "px")}
        baseline = next((item for item in series if item.get("is_baseline")), series[0])
        axis_key = "distance_mm" if overlay_data.get("axis") == "mm" else "distance_px"
        baseline_x = np.asarray(baseline.get(axis_key, []), dtype=np.float64)
        baseline_y = np.asarray(baseline.get("intensity", []), dtype=np.float64)
        delta_series: list[dict[str, Any]] = []
        for item in series:
            if item is baseline:
                continue
            target_y = np.asarray(item.get("intensity", []), dtype=np.float64)
            usable = min(len(baseline_x), len(baseline_y), len(target_y))
            if usable <= 1:
                continue
            delta_series.append(
                {
                    "label": f"{item['label']} vs baseline",
                    "x": baseline_x[:usable],
                    "delta": target_y[:usable] - baseline_y[:usable],
                }
            )
        return {
            "series": delta_series,
            "axis": overlay_data.get("axis", "px"),
            "baseline_label": baseline.get("label", "baseline"),
        }

    def render_delta_profile_chart(self, parent: tk.Widget, delta_data: dict[str, Any]) -> None:
        series = list(delta_data.get("series", []))
        if not series:
            return
        canvas = tk.Canvas(parent, bg="white", height=200, highlightthickness=1, highlightbackground="#d1d5db")
        canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        all_x = np.concatenate([np.asarray(item["x"], dtype=np.float64) for item in series])
        all_y = np.concatenate([np.asarray(item["delta"], dtype=np.float64) for item in series] + [np.asarray([0.0])])
        x_min, x_max = float(np.min(all_x)), float(np.max(all_x))
        y_min, y_max = float(np.min(all_y)), float(np.max(all_y))
        if abs(x_max - x_min) < 1e-9:
            x_max = x_min + 1.0
        if abs(y_max - y_min) < 1e-9:
            y_max = y_min + 1.0
        width = max(canvas.winfo_reqwidth(), 900)
        height = 200
        left, top, right, bottom = 56, 16, width - 16, height - 32
        canvas.create_line(left, bottom, right, bottom, fill="#9ca3af")
        canvas.create_line(left, top, left, bottom, fill="#9ca3af")
        zero_py = bottom - (0.0 - y_min) / (y_max - y_min) * (bottom - top)
        canvas.create_line(left, zero_py, right, zero_py, fill="#64748b", dash=(3, 3))
        colors = ("#dc2626", "#16a34a", "#a855f7", "#f59e0b")
        for index, item in enumerate(series):
            xs = np.asarray(item["x"], dtype=np.float64)
            ys = np.asarray(item["delta"], dtype=np.float64)
            points: list[float] = []
            for x_value, y_value in zip(xs, ys):
                px = left + (float(x_value - x_min) / float(x_max - x_min)) * (right - left)
                py = bottom - (float(y_value - y_min) / float(y_max - y_min)) * (bottom - top)
                points.extend([px, py])
            color = colors[index % len(colors)]
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=2, smooth=True)
            legend_y = top + index * 16
            canvas.create_line(right - 260, legend_y + 8, right - 238, legend_y + 8, fill=color, width=2)
            canvas.create_text(right - 232, legend_y + 8, text=item["label"], anchor="w", fill="#111827")
        x_label = "Distance (mm)" if delta_data.get("axis") == "mm" else "Distance (px)"
        canvas.create_text((left + right) / 2, height - 12, text=x_label, fill="#374151")
        canvas.create_text(12, (top + bottom) / 2, text="ΔIntensity", fill="#374151", angle=90)

    def build_history_comparison(self, entries: list[ResultHistoryEntry]) -> dict[str, Any]:
        baseline = entries[0]
        mixed_metrics = len({entry.metric for entry in entries}) > 1
        values = [float(entry.value) for entry in entries]
        min_value = min(values)
        max_value = max(values)
        baseline_features: dict[str, Any] | None = None
        if baseline.measurement_type == "Line Profile":
            baseline_series = self.resolve_line_profile_series(baseline)
            if baseline_series is not None:
                baseline_features = self.compute_profile_features(
                    {
                        "distance_px": np.asarray(baseline_series.get("distance_px", []), dtype=np.float64),
                        "distance_mm": None
                        if baseline_series.get("distance_mm") is None
                        else np.asarray(baseline_series.get("distance_mm", []), dtype=np.float64),
                        "intensity": np.asarray(baseline_series.get("intensity", []), dtype=np.float64),
                    }
                )
        rows: list[dict[str, Any]] = []
        for entry in entries:
            difference = float(entry.value - baseline.value)
            entry_features: dict[str, Any] | None = None
            if entry.measurement_type == "Line Profile":
                series = self.resolve_line_profile_series(entry)
                if series is not None:
                    entry_features = self.compute_profile_features(
                        {
                            "distance_px": np.asarray(series.get("distance_px", []), dtype=np.float64),
                            "distance_mm": None
                            if series.get("distance_mm") is None
                            else np.asarray(series.get("distance_mm", []), dtype=np.float64),
                            "intensity": np.asarray(series.get("intensity", []), dtype=np.float64),
                        }
                    )
            delta_peak_pos = None
            delta_peak_value = None
            delta_fwhm = None
            if baseline_features is not None and entry_features is not None:
                if isinstance(entry_features.get("peak_position"), (int, float)) and isinstance(
                    baseline_features.get("peak_position"), (int, float)
                ):
                    delta_peak_pos = float(entry_features["peak_position"] - baseline_features["peak_position"])
                if isinstance(entry_features.get("peak_value"), (int, float)) and isinstance(
                    baseline_features.get("peak_value"), (int, float)
                ):
                    delta_peak_value = float(entry_features["peak_value"] - baseline_features["peak_value"])
                if isinstance(entry_features.get("fwhm"), (int, float)) and isinstance(baseline_features.get("fwhm"), (int, float)):
                    delta_fwhm = float(entry_features["fwhm"] - baseline_features["fwhm"])
            rows.append(
                {
                    "entry": entry,
                    "difference": difference,
                    "percent_change": self._format_percent_change(float(entry.value), float(baseline.value)),
                    "is_baseline": entry is baseline,
                    "is_min": abs(entry.value - min_value) < 1e-12,
                    "is_max": abs(entry.value - max_value) < 1e-12,
                    "features": entry_features,
                    "delta_peak_position": delta_peak_pos,
                    "delta_peak_value": delta_peak_value,
                    "delta_fwhm": delta_fwhm,
                }
            )
        return {
            "baseline": baseline,
            "rows": rows,
            "mixed_metrics": mixed_metrics,
            "metric_name": baseline.metric,
        }

    def format_comparison_table(self, comparison: dict[str, Any]) -> list[tuple[str, ...]]:
        formatted: list[tuple[str, ...]] = []
        for row in comparison["rows"]:
            entry: ResultHistoryEntry = row["entry"]
            features = row.get("features") or {}
            badge = ""
            if row["is_min"]:
                badge = "MIN"
            if row["is_max"]:
                badge = "MAX" if not badge else "MIN/MAX"
            note_short = entry.note.replace("\n", " | ")
            if len(note_short) > 80:
                note_short = f"{note_short[:77]}..."
            peak_value_text = "-"
            peak_pos_text = "-"
            fwhm_text = "-"
            if isinstance(features.get("peak_value"), (int, float)):
                peak_value_text = f"{float(features['peak_value']):.2f}"
            if isinstance(features.get("peak_position"), (int, float)):
                peak_pos_text = f"{float(features['peak_position']):.2f}"
            if isinstance(features.get("fwhm"), (int, float)):
                fwhm_text = f"{float(features['fwhm']):.2f}"
            d_peak_pos = row.get("delta_peak_position")
            d_peak_value = row.get("delta_peak_value")
            d_fwhm = row.get("delta_fwhm")
            formatted.append(
                (
                    entry.timestamp,
                    entry.image_name,
                    str(entry.frame_index),
                    entry.measurement_type,
                    entry.target_name,
                    entry.metric,
                    f"{entry.value:.2f}",
                    entry.unit,
                    "-" if row["is_baseline"] else f"{row['difference']:.2f}",
                    "-" if row["is_baseline"] else row["percent_change"],
                    peak_value_text,
                    peak_pos_text,
                    fwhm_text,
                    "-" if d_peak_value is None or row["is_baseline"] else f"{float(d_peak_value):.2f}",
                    "-" if d_peak_pos is None or row["is_baseline"] else f"{float(d_peak_pos):.2f}",
                    "-" if d_fwhm is None or row["is_baseline"] else f"{float(d_fwhm):.2f}",
                    badge,
                    note_short,
                )
            )
        return formatted

    def render_history_comparison(self, comparison: dict[str, Any]) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Results History Compare")
        dialog.geometry("1540x760")
        header_text = (
            f"Baseline: {comparison['baseline'].metric} @ {comparison['baseline'].timestamp} "
            f"({comparison['baseline'].target_name})"
        )
        ttk.Label(dialog, text=header_text).pack(anchor="w", padx=8, pady=(8, 4))
        columns = (
            "timestamp",
            "image",
            "frame",
            "type",
            "target",
            "metric",
            "value",
            "unit",
            "diff",
            "pct",
            "peak_i",
            "peak_pos",
            "fwhm",
            "d_peak_i",
            "d_peak_pos",
            "d_fwhm",
            "highlight",
            "note",
        )
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=14)
        headers = {
            "timestamp": "Timestamp",
            "image": "Image Name",
            "frame": "Frame",
            "type": "Measurement Type",
            "target": "Target Name",
            "metric": "Metric",
            "value": "Value",
            "unit": "Unit",
            "diff": "Difference",
            "pct": "Percent Change",
            "peak_i": "Peak I",
            "peak_pos": "Peak Pos",
            "fwhm": "FWHM",
            "d_peak_i": "ΔPeak I",
            "d_peak_pos": "ΔPeak Pos",
            "d_fwhm": "ΔFWHM",
            "highlight": "Min/Max",
            "note": "Note",
        }
        widths = {
            "timestamp": 150,
            "image": 120,
            "frame": 60,
            "type": 110,
            "target": 110,
            "metric": 90,
            "value": 70,
            "unit": 60,
            "diff": 85,
            "pct": 95,
            "peak_i": 80,
            "peak_pos": 80,
            "fwhm": 80,
            "d_peak_i": 85,
            "d_peak_pos": 90,
            "d_fwhm": 80,
            "highlight": 80,
            "note": 220,
        }
        for key in columns:
            tree.heading(key, text=headers[key])
            tree.column(key, width=widths[key], anchor="w")
        tree.tag_configure("baseline_row", background="#ecfeff")
        tree.tag_configure("min_row", background="#eff6ff")
        tree.tag_configure("max_row", background="#fef3c7")
        tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        for row_tuple, row in zip(self.format_comparison_table(comparison), comparison["rows"]):
            tags: list[str] = []
            if row["is_baseline"]:
                tags.append("baseline_row")
            if row["is_min"]:
                tags.append("min_row")
            if row["is_max"]:
                tags.append("max_row")
            tree.insert("", "end", values=row_tuple, tags=tuple(tags))
        overlay_data = self.build_line_profile_overlay_data([row["entry"] for row in comparison["rows"]])
        if overlay_data.get("series") or overlay_data.get("missing"):
            subtitle = ttk.Label(dialog, text="Line Profile Overlay", font=("TkDefaultFont", 9, "bold"))
            subtitle.pack(anchor="w", padx=8, pady=(2, 4))
            self.render_line_profile_overlay_chart(dialog, overlay_data)
            delta_data = self.build_delta_profile_data(overlay_data)
            if delta_data.get("series"):
                delta_title = ttk.Label(dialog, text="Delta Profile (vs baseline)", font=("TkDefaultFont", 9, "bold"))
                delta_title.pack(anchor="w", padx=8, pady=(0, 4))
                self.render_delta_profile_chart(dialog, delta_data)
            missing = overlay_data.get("missing", [])
            if missing:
                ttk.Label(
                    dialog,
                    text=f"profile data unavailable: {', '.join(missing)}",
                    foreground="#92400e",
                ).pack(anchor="w", padx=8, pady=(0, 8))

    def compare_selected_history_rows(self) -> None:
        table = self.result_history_table
        if table is None:
            return
        selected_items = list(table.selection())
        if len(selected_items) < 2:
            messagebox.showinfo("Compare", "비교하려면 2개 이상 선택하세요.")
            return
        if len(selected_items) > 5:
            messagebox.showinfo("Compare", "한 번에 최대 5개까지만 비교할 수 있습니다.")
            return
        all_entries = self.result_history_store.entries()
        entries: list[ResultHistoryEntry] = []
        for item_id in selected_items:
            store_indices = self._history_item_to_store_indices.get(item_id, [])
            if not store_indices:
                continue
            store_index = store_indices[0]
            if 0 <= store_index < len(all_entries):
                entries.append(all_entries[store_index])
        if len(entries) < 2:
            messagebox.showinfo("Compare", "비교 가능한 결과를 찾지 못했습니다.")
            return
        comparison = self.build_history_comparison(entries)
        if comparison["mixed_metrics"]:
            messagebox.showwarning("Compare", "같은 metric 비교를 권장합니다. (혼합 metric 계속 진행)")
        self.render_history_comparison(comparison)

    def resolve_history_entry_target(self, entry: ResultHistoryEntry) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "ok",
            "image_found": False,
            "frame_found": False,
            "measurement": None,
            "related_measurements": [],
            "message": "",
        }
        target_path = entry.source_image_path
        if self.file_paths:
            file_index = -1
            if target_path and target_path in self.file_paths:
                file_index = self.file_paths.index(target_path)
            elif entry.image_name:
                for index, path in enumerate(self.file_paths):
                    if Path(path).name == entry.image_name:
                        file_index = index
                        break
            if file_index >= 0 and file_index != self.current_file_index:
                self._load_file(file_index, preserve_view_state=False)
            result["image_found"] = file_index >= 0
        else:
            result["image_found"] = True

        frame_index = int(entry.frame_index)
        if self.frames and 0 <= frame_index < len(self.frames):
            if self.current_frame != frame_index:
                self.current_frame = frame_index
                self._show_frame()
            result["frame_found"] = True
        else:
            result["frame_found"] = False

        measurement = None
        if entry.target_id:
            expected_kind = "roi" if entry.measurement_type == "ROI" else ("line" if entry.measurement_type == "Line Profile" else None)
            measurement = self._find_measurement_by_id(entry.target_id, expected_kind=expected_kind)
        if measurement is None and entry.measurement_type == "ROI":
            display_map = self._build_roi_display_name_map()
            for measurement_id, label in display_map.items():
                if label == entry.target_name:
                    measurement = self._find_measurement_by_id(measurement_id, expected_kind="roi")
                    break
        if measurement is None and entry.measurement_type == "Line Profile":
            for candidate in self.persistent_measurements:
                if candidate.kind != "line":
                    continue
                line_index = self._line_index_for_measurement_id(candidate.id)
                if f"Line {line_index}" == entry.target_name:
                    measurement = candidate
                    break
        result["measurement"] = measurement
        related: list[Measurement] = []
        for related_id in entry.related_target_ids:
            found = self._find_measurement_by_id(related_id)
            if found is not None:
                related.append(found)
        result["related_measurements"] = related

        if not result["image_found"]:
            result["status"] = "partial"
            result["message"] = "Original target not available"
        elif not result["frame_found"]:
            result["status"] = "partial"
            result["message"] = "Image found but frame unavailable"
        elif measurement is None and entry.measurement_type in {"ROI", "Line Profile"}:
            result["status"] = "partial"
            result["message"] = "Image/frame found but ROI/Line no longer exists"
        return result

    def highlight_measurement_target(self, measurement: Measurement | None, related: list[Measurement] | None = None) -> None:
        if measurement is not None:
            self.selected_persistent_measurement_id = measurement.id
        elif related:
            self.selected_persistent_measurement_id = related[0].id
        else:
            self.selected_persistent_measurement_id = None
        self._draw_persistent_measurements()

    def activate_history_entry(self, entry: ResultHistoryEntry) -> None:
        resolved = self.resolve_history_entry_target(entry)
        measurement = resolved.get("measurement")
        related = resolved.get("related_measurements", [])
        self.highlight_measurement_target(measurement, related)

        if entry.measurement_type == "Line Profile" and isinstance(measurement, Measurement):
            self.analysis_inputs["line_profile_line_id"].set(measurement.id)
            self._sync_analysis_display_value("line", "line_profile", "line_profile_line_id")
            self._on_line_profile_selection_changed()
        elif entry.measurement_type == "Analysis":
            if related:
                self.highlight_measurement_target(related[0], related)
            metric = entry.metric
            self.analysis_results["line_info"].set(f"History metric selected: {metric}")

        message = str(resolved.get("message", "")).strip()
        if message:
            self.info_var.set(message)
        else:
            self.info_var.set(
                f"History selected: {entry.measurement_type} | {entry.target_name} | Frame {entry.frame_index + 1}"
            )

    def _refresh_analysis_selectors(self) -> None:
        roi_options = self._build_roi_analysis_options()
        line_options = self._build_line_analysis_options()
        self._analysis_option_maps["roi"] = {label: measurement_id for measurement_id, label in roi_options}
        self._analysis_option_maps["line"] = {label: measurement_id for measurement_id, label in line_options}
        roi_labels = [label for _, label in roi_options]
        line_labels = [label for _, label in line_options]
        for key in ("snr_signal", "snr_noise", "cnr_target", "cnr_reference", "cnr_noise"):
            if key in self._analysis_comboboxes:
                self._analysis_comboboxes[key]["values"] = roi_labels
        if "line_profile" in self._analysis_comboboxes:
            self._analysis_comboboxes["line_profile"]["values"] = line_labels
        self._sync_analysis_display_value("roi", "snr_signal", "snr_signal_roi_id")
        self._sync_analysis_display_value("roi", "snr_noise", "snr_background_roi_id")
        self._sync_analysis_display_value("roi", "cnr_target", "cnr_target_roi_id")
        self._sync_analysis_display_value("roi", "cnr_reference", "cnr_reference_roi_id")
        self._sync_analysis_display_value("roi", "cnr_noise", "cnr_noise_roi_id")
        self._sync_analysis_display_value("line", "line_profile", "line_profile_line_id")
        uniformity_formula_combo = self._analysis_comboboxes.get("uniformity_formula")
        if uniformity_formula_combo is not None:
            formula_key = self.analysis_inputs["uniformity_formula"].get()
            if formula_key == "std_mean":
                uniformity_formula_combo.set("std_mean | 1 - std/mean")
            else:
                uniformity_formula_combo.set("max_min | 1 - (max-min)/(max+min)")
        listbox = self._uniformity_roi_listbox
        if listbox is not None:
            uniformity_ids_var = self.analysis_inputs.get("uniformity_roi_ids")
            raw_selected_ids = "" if uniformity_ids_var is None else uniformity_ids_var.get()
            selected_ids = {
                roi_id.strip()
                for roi_id in raw_selected_ids.split(",")
                if roi_id.strip()
            }
            listbox.delete(0, tk.END)
            selected_indexes: list[int] = []
            for index, (measurement_id, label) in enumerate(roi_options):
                listbox.insert(tk.END, label)
                if measurement_id in selected_ids:
                    selected_indexes.append(index)
            for index in selected_indexes:
                listbox.selection_set(index)
        self._auto_bind_analysis_inputs_from_roles(overwrite_existing=False)
        self._update_uniformity_input_ui()
        self._refresh_analysis_results_panel()
        self._refresh_image_analysis_selectors()

    def _refresh_image_analysis_selectors(self) -> None:
        image_options = self._build_image_analysis_options()
        roi_options = self._build_roi_analysis_options()
        self._image_analysis_option_maps["image"] = {label: image_id for image_id, label in image_options}
        self._image_analysis_option_maps["roi"] = {label: measurement_id for measurement_id, label in roi_options}
        image_labels = [label for _, label in image_options]
        roi_labels = [label for _, label in roi_options]
        for key in ("reference_image", "target_image"):
            if key in self._image_analysis_comboboxes:
                self._image_analysis_comboboxes[key]["values"] = image_labels
        if "scope_roi" in self._image_analysis_comboboxes:
            self._image_analysis_comboboxes["scope_roi"]["values"] = roi_labels
        self._sync_image_analysis_display_value("image", "reference_image", "reference_image_id")
        self._sync_image_analysis_display_value("image", "target_image", "target_image_id")
        self._sync_image_analysis_display_value("roi", "scope_roi", "scope_roi_id")

    def _build_image_analysis_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for index, path in enumerate(self.file_paths):
            options.append((path, f"Image {index + 1}: {Path(path).name}"))
        if not options and self.path_var.get().strip():
            current = self.path_var.get().strip()
            options.append((current, f"Current: {Path(current).name}"))
        return options

    def _update_cnr_formula_ui(self, *_args: object) -> None:
        formula = self.analysis_inputs["cnr_formula"].get()
        show_noise = formula == "standard_noise"
        for widget in self._cnr_noise_widgets:
            if show_noise:
                widget.grid()
            else:
                widget.grid_remove()
        if not show_noise:
            self.analysis_inputs["cnr_noise_roi_id"].set("")
            if "cnr_noise" in self._analysis_comboboxes:
                self._analysis_comboboxes["cnr_noise"].set("")
            self.analysis_results["cnr_preview"].set("Formula: |S_A - S_B| / sqrt(sigma_A^2 + sigma_B^2)")
        else:
            self.analysis_results["cnr_preview"].set("Formula: |S_A - S_B| / sigma_o")
        self.analysis_results["cnr_result"].set("Result: -")
        self._auto_bind_analysis_inputs_from_roles(overwrite_existing=False)
        self._update_analysis_action_button_state()

    def _on_uniformity_formula_selected(self) -> None:
        combo = self._analysis_comboboxes.get("uniformity_formula")
        if combo is None:
            return
        label = combo.get().strip().lower()
        if label.startswith("std_mean"):
            self.analysis_inputs["uniformity_formula"].set("std_mean")
        else:
            self.analysis_inputs["uniformity_formula"].set("max_min")
        self.analysis_results["uniformity_result"].set("Result: -")

    def _update_uniformity_input_ui(self, *_args: object) -> None:
        mode = self.analysis_inputs["uniformity_input_mode"].get()
        listbox = self._uniformity_roi_listbox
        if listbox is not None:
            if mode == "selected_rois":
                listbox.configure(state="normal")
            else:
                listbox.configure(state="disabled")
        self.analysis_results["uniformity_result"].set("Result: -")

    def _update_image_scope_ui(self, *_args: object) -> None:
        is_roi_scope = self.image_analysis_inputs["scope_type"].get() == "roi"
        scope_combobox = self._image_analysis_comboboxes.get("scope_roi")
        if scope_combobox is None:
            return
        if is_roi_scope:
            scope_combobox.grid()
        else:
            scope_combobox.grid_remove()
            self.image_analysis_inputs["scope_roi_id"].set("")
            scope_combobox.set("")

    def _sync_image_analysis_display_value(self, kind: str, combobox_key: str, input_key: str) -> None:
        combobox = self._image_analysis_comboboxes.get(combobox_key)
        if combobox is None:
            return
        selected_id = self.image_analysis_inputs[input_key].get()
        if not selected_id:
            combobox.set("")
            return
        option_map = self._image_analysis_option_maps.get(kind, {})
        for label, option_id in option_map.items():
            if option_id == selected_id:
                combobox.set(label)
                return
        self.image_analysis_inputs[input_key].set("")
        combobox.set("")

    def _sync_analysis_display_value(self, kind: str, combobox_key: str, input_key: str) -> None:
        combobox = self._analysis_comboboxes.get(combobox_key)
        if combobox is None:
            return
        selected_id = self.analysis_inputs[input_key].get()
        option_map = self._analysis_option_maps.get(kind, {})
        if not selected_id:
            current_label = combobox.get().strip()
            if current_label and current_label in option_map:
                return
            combobox.set("")
            return
        for label, measurement_id in option_map.items():
            if measurement_id == selected_id:
                combobox.set(label)
                return
        self.analysis_inputs[input_key].set("")
        combobox.set("")

    @staticmethod
    def _valid_roi_roles() -> tuple[str, ...]:
        return ("signal", "background", "noise", "target", "reference")

    def _normalize_roi_role(self, role_value: Any) -> str | None:
        if role_value is None:
            return None
        role = str(role_value).strip().lower()
        return role if role in self._valid_roi_roles() else None

    def _get_measurement_roi_role(self, measurement: Measurement | None) -> str | None:
        if measurement is None or measurement.kind != "roi":
            return None
        return self._normalize_roi_role((measurement.meta or {}).get("role"))

    def _find_roi_by_role(self, role: str) -> Measurement | None:
        normalized_role = self._normalize_roi_role(role)
        if normalized_role is None:
            return None
        current_geometry = self._get_current_geometry_key()
        for measurement in reversed(self.persistent_measurements):
            if measurement.kind != "roi":
                continue
            if not self._geometry_matches(measurement.geometry_key, current_geometry):
                continue
            if measurement.frame_index != self.current_frame:
                continue
            if self._get_measurement_roi_role(measurement) == normalized_role:
                return measurement
        return None

    def _reset_signal_analysis_results(self) -> None:
        if "snr_preview" in self.analysis_results:
            self.analysis_results["snr_preview"].set("Preview: -")
        if "snr_result" in self.analysis_results:
            self.analysis_results["snr_result"].set("Result: -")
        if "cnr_preview" in self.analysis_results:
            if self.analysis_inputs.get("cnr_formula") is not None and self.analysis_inputs["cnr_formula"].get() == "dual_variance":
                self.analysis_results["cnr_preview"].set("Formula: |S_A - S_B| / sqrt(sigma_A^2 + sigma_B^2)")
            else:
                self.analysis_results["cnr_preview"].set("Formula: |S_A - S_B| / sigma_o")
        if "cnr_result" in self.analysis_results:
            self.analysis_results["cnr_result"].set("Result: -")
        if "uniformity_preview" in self.analysis_results:
            self.analysis_results["uniformity_preview"].set("Preview: -")
        if "uniformity_result" in self.analysis_results:
            self.analysis_results["uniformity_result"].set("Result: -")

    def _update_analysis_action_button_state(self) -> None:
        action_buttons = getattr(self, "_analysis_action_buttons", {})
        snr_button = action_buttons.get("snr")
        cnr_button = action_buttons.get("cnr")
        signal_roi = self._find_roi_by_role("signal")
        snr_noise_roi = self._find_roi_by_role("background") or self._find_roi_by_role("noise")
        manual_signal_roi = self._peek_selected_measurement_from_analysis("roi", "snr_signal_roi_id", "snr_signal")
        manual_snr_noise_roi = self._peek_selected_measurement_from_analysis("roi", "snr_background_roi_id", "snr_noise")
        cnr_target_roi = self._find_roi_by_role("target")
        cnr_reference_roi = self._find_roi_by_role("reference")
        cnr_noise_roi = self._find_roi_by_role("noise")
        manual_cnr_target_roi = self._peek_selected_measurement_from_analysis("roi", "cnr_target_roi_id", "cnr_target")
        manual_cnr_reference_roi = self._peek_selected_measurement_from_analysis("roi", "cnr_reference_roi_id", "cnr_reference")
        manual_cnr_noise_roi = self._peek_selected_measurement_from_analysis("roi", "cnr_noise_roi_id", "cnr_noise")
        formula_var = self.analysis_inputs.get("cnr_formula")
        formula = formula_var.get() if formula_var is not None else "standard_noise"

        if snr_button is not None:
            role_ready = signal_roi is not None and snr_noise_roi is not None
            manual_ready = manual_signal_roi is not None and manual_snr_noise_roi is not None
            snr_ready = role_ready or manual_ready
            snr_button.configure(state="normal" if snr_ready else "disabled")
            snr_reason_var = self.analysis_results.get("snr_ready_reason")
            if snr_reason_var is not None:
                missing_reasons: list[str] = []
                if signal_roi is None and manual_signal_roi is None:
                    missing_reasons.append("signal ROI 미선택")
                if snr_noise_roi is None and manual_snr_noise_roi is None:
                    missing_reasons.append("background/noise ROI 미선택")
                if snr_ready:
                    source_text = "role-based measurement" if role_ready else "manual measurement"
                    snr_reason_var.set(f"Ready: {source_text}")
                else:
                    if len(missing_reasons) == 2:
                        snr_reason_var.set("Select Signal ROI and Noise ROI")
                    elif "signal ROI 미선택" in missing_reasons:
                        snr_reason_var.set("Signal ROI not selected")
                    elif "background/noise ROI 미선택" in missing_reasons:
                        snr_reason_var.set("Noise ROI not selected")
                    else:
                        snr_reason_var.set("ROI selection required")
        if cnr_button is not None:
            needs_noise = formula == "standard_noise"
            role_ready = cnr_target_roi is not None and cnr_reference_roi is not None and (cnr_noise_roi is not None or not needs_noise)
            manual_ready = manual_cnr_target_roi is not None and manual_cnr_reference_roi is not None and (
                manual_cnr_noise_roi is not None or not needs_noise
            )
            cnr_ready = role_ready or manual_ready
            cnr_button.configure(state="normal" if cnr_ready else "disabled")

    def _auto_bind_analysis_inputs_from_roles(self, overwrite_existing: bool = False) -> None:
        role_assignment = {
            "snr_signal_roi_id": self._find_roi_by_role("signal"),
            "snr_background_roi_id": self._find_roi_by_role("background") or self._find_roi_by_role("noise"),
            "cnr_target_roi_id": self._find_roi_by_role("target"),
            "cnr_reference_roi_id": self._find_roi_by_role("reference"),
            "cnr_noise_roi_id": self._find_roi_by_role("noise"),
        }
        for input_key, measurement in role_assignment.items():
            var = self.analysis_inputs.get(input_key)
            if var is None:
                continue
            if measurement is None:
                if overwrite_existing:
                    var.set("")
                continue
            if overwrite_existing or not var.get():
                var.set(measurement.id)
        self._sync_analysis_display_value("roi", "snr_signal", "snr_signal_roi_id")
        self._sync_analysis_display_value("roi", "snr_noise", "snr_background_roi_id")
        self._sync_analysis_display_value("roi", "cnr_target", "cnr_target_roi_id")
        self._sync_analysis_display_value("roi", "cnr_reference", "cnr_reference_roi_id")
        self._sync_analysis_display_value("roi", "cnr_noise", "cnr_noise_roi_id")
        self._update_analysis_action_button_state()

    def _build_roi_analysis_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        roi_display_names = self._build_roi_display_name_map()
        for measurement in self._iter_visible_roi_measurements():
            metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
            signal_stats = dict(metrics.get("signal_stats") or {})
            mean = float(signal_stats.get("mean", 0.0))
            min_val = float(signal_stats.get("min", 0.0))
            std = float(signal_stats.get("std", 0.0))
            area_mm2 = metrics.get("area_mm2")
            area_text = f"{area_mm2:.1f} mm²" if isinstance(area_mm2, (int, float)) else f"{metrics['area_px']:.1f} px²"
            roi_name = roi_display_names.get(measurement.id, self._format_roi_label(0))
            label = (
                f"{roi_name} | Min {min_val:.1f} | Mean {mean:.1f} | "
                f"SD {std:.1f} | Area {area_text}"
            )
            options.append((measurement.id, self._sanitize_ui_text(label)))
        return options

    def _iter_visible_roi_measurements(self) -> list[Measurement]:
        current_geometry = self._get_current_geometry_key()
        return [
            measurement
            for measurement in self.persistent_measurements
            if measurement.kind == "roi"
            and self._geometry_matches(measurement.geometry_key, current_geometry)
            and measurement.frame_index == self.current_frame
        ]

    @staticmethod
    def _format_roi_label(index_zero_based: int) -> str:
        return f"ROI {index_zero_based + 1}"

    def _get_roi_display_index(self, measurement_id: str) -> int | None:
        roi_index = 0
        for measurement in self._iter_visible_roi_measurements():
            roi_index += 1
            if measurement.id == measurement_id:
                return roi_index
        return None

    def _build_line_analysis_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        current_geometry = self._get_current_geometry_key()
        line_index = 0
        for measurement in self.persistent_measurements:
            if measurement.kind != "line":
                continue
            if not self._geometry_matches(measurement.geometry_key, current_geometry):
                continue
            if measurement.frame_index != self.current_frame:
                continue
            line_index += 1
            metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
            label = f"Line ROI {line_index} | length {metrics['length_px']:.1f} px"
            options.append((measurement.id, label))
        return options

    def _build_roi_display_name_map(self) -> dict[str, str]:
        display_map: dict[str, str] = {}
        for index, measurement in enumerate(self._iter_visible_roi_measurements()):
            display_map[measurement.id] = self._format_roi_label(index)
        return display_map

    def _display_name_for_roi_id(self, roi_id: str | None) -> str:
        if not roi_id:
            return self._format_roi_label(0)
        return self._build_roi_display_name_map().get(roi_id, self._format_roi_label(0))

    def _sanitize_ui_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = self._UUID_PATTERN.sub("", text)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = cleaned.replace(" |  | ", " | ").replace(" | | ", " | ")
        cleaned = cleaned.strip(" |,")
        return cleaned if cleaned else "-"

    def _is_analysis_compatible_measurement(self, measurement: Measurement) -> bool:
        current_geometry = self._get_current_geometry_key()
        return self._geometry_matches(measurement.geometry_key, current_geometry) and measurement.frame_index == self.current_frame

    def _collect_analysis_factors(self, measurement: Measurement) -> dict[str, Any]:
        return {
            "measurement_id": measurement.id,
            "frame_index": int(measurement.frame_index),
            "geometry_key": measurement.geometry_key,
            "pixel_spacing_mm": self._get_pixel_spacing_mm(),
            "roi_type": measurement.meta.get("roi_type"),
            "roi_role": self._get_measurement_roi_role(measurement),
        }

    @staticmethod
    def _format_analysis_stats(stats: dict[str, Any]) -> str:
        ordered_keys = ("mean", "std", "min", "max", "pixel_count", "length_px", "sample_count")
        parts: list[str] = []
        for key in ordered_keys:
            if key not in stats:
                continue
            value = stats[key]
            if isinstance(value, float):
                parts.append(f"{key}={value:.4f}")
            else:
                parts.append(f"{key}={value}")
        for key, value in stats.items():
            if key in ordered_keys:
                continue
            parts.append(f"{key}={value}")
        return ", ".join(parts)

    def _build_roi_stats_result_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        current_geometry = self._get_current_geometry_key()
        for measurement in self.persistent_measurements:
            if measurement.kind != "roi":
                continue
            if measurement.frame_index != self.current_frame:
                continue
            if not self._geometry_matches(measurement.geometry_key, current_geometry):
                continue
            metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
            signal_stats = dict(metrics.get("signal_stats") or {})
            stats = {
                "mean": float(signal_stats.get("mean", 0.0)),
                "std": float(signal_stats.get("std", 0.0)),
                "min": float(signal_stats.get("min", 0.0)),
                "max": float(signal_stats.get("max", 0.0)),
                "pixel_count": int(signal_stats.get("pixel_count", metrics.get("pixel_count", 0))),
            }
            role = self._get_measurement_roi_role(measurement)
            rows.append(
                {
                    "metric_name": "ROI_STATS",
                    "formula_mode": "ROI_STATS | single_roi_summary",
                    "roi_ids": [measurement.id],
                    "roles": [] if role is None else [role],
                    "stats": stats,
                    "result_value": float(stats["mean"]),
                    "item_name": self._display_name_for_roi_id(measurement.id),
                    "note_text": "Current frame ROI statistics",
                    "result_text": f"Mean: {stats['mean']:.2f}, SD: {stats['std']:.2f}",
                    "developer_meta": {
                        "source": "roi_stats_snapshot",
                        "measurement_id": measurement.id,
                    },
                }
            )
        return rows

    def _build_analysis_last_run_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        snr = self.analysis_last_run.get("snr")
        if snr is not None:
            factors = snr.get("factors") or {}
            status = str(snr.get("status", "success"))
            reason = str(snr.get("reason", ""))
            result_raw = snr.get("result")
            result_value = float(result_raw) if isinstance(result_raw, (int, float)) else None
            preview_text = str(snr.get("preview_text", snr.get("preview", "")))
            result_text = str(snr.get("result_text", ""))
            if not result_text:
                if result_value is not None:
                    result_text = f"{result_value:.4f}"
                elif reason:
                    result_text = f"{status}: {reason}"
                else:
                    result_text = status
            roles = []
            for key in ("signal", "noise"):
                role = (factors.get(key) or {}).get("roi_role")
                if role:
                    roles.append(str(role))
            stats: dict[str, Any] = {
                "status": status,
                "preview": preview_text,
            }
            signal_mean = snr.get("mean_signal")
            noise_std = snr.get("std_noise")
            if isinstance(signal_mean, (int, float)):
                stats["mean_signal"] = float(signal_mean)
            if isinstance(noise_std, (int, float)):
                stats["std_noise"] = float(noise_std)
            if reason:
                stats["reason"] = reason
            rows.append(
                {
                    "metric_name": "SNR",
                    "formula_mode": f"{str(snr.get('formula', 'mean(Signal ROI) / std(Noise ROI)'))} [{status}]",
                    "roi_ids": [
                        str(snr.get("signal_roi_id", (snr.get("inputs") or {}).get("signal_roi_id", ""))),
                        str(snr.get("noise_roi_id", (snr.get("inputs") or {}).get("noise_roi_id", ""))),
                    ],
                    "roles": roles,
                    "stats": stats,
                    "result_value": result_value,
                    "item_name": "SNR",
                    "note_text": "Calculated from signal mean and noise SD",
                    "result_text": (f"{result_value:.2f}" if isinstance(result_value, (int, float)) else result_text),
                    "developer_meta": snr,
                }
            )

        cnr = self.analysis_last_run.get("cnr")
        if cnr is not None:
            inputs = cnr.get("inputs") or {}
            factors = cnr.get("factors") or {}
            status = str(cnr.get("status", "success"))
            reason = str(cnr.get("reason", ""))
            result_raw = cnr.get("result")
            result_value = float(result_raw) if isinstance(result_raw, (int, float)) else None
            result_text = str(cnr.get("result_text", ""))
            if not result_text:
                if result_value is not None:
                    result_text = f"{result_value:.4f}"
                elif reason:
                    result_text = f"{status}: {reason}"
                else:
                    result_text = status
            roles = []
            for key in ("region_a", "region_b", "noise"):
                role = (factors.get(key) or {}).get("roi_role")
                if role:
                    roles.append(str(role))
            roi_ids = [
                str(inputs.get("region_a_roi_id", "")),
                str(inputs.get("region_b_roi_id", "")),
            ]
            noise_id = inputs.get("noise_roi_id")
            if noise_id:
                roi_ids.append(str(noise_id))
            stats: dict[str, Any] = {
                "status": status,
            }
            for stat_key in ("numerator", "denominator", "target_mean", "reference_mean", "noise_std", "target_std", "reference_std"):
                stat_value = cnr.get(stat_key)
                if isinstance(stat_value, (int, float)):
                    stats[stat_key] = float(stat_value)
            preview_text = str(cnr.get("preview_text", ""))
            if preview_text:
                stats["preview"] = preview_text
            if reason:
                stats["reason"] = reason
            rows.append(
                {
                    "metric_name": "CNR",
                    "formula_mode": f"{str(inputs.get('formula', 'standard_noise'))} [{status}]",
                    "roi_ids": roi_ids,
                    "roles": roles,
                    "stats": stats,
                    "result_value": result_value,
                    "item_name": "CNR",
                    "note_text": "Contrast difference divided by noise term",
                    "result_text": (f"{result_value:.2f}" if isinstance(result_value, (int, float)) else result_text),
                    "developer_meta": cnr,
                }
            )

        uniformity = self.analysis_last_run.get("uniformity")
        if uniformity is not None:
            inputs = uniformity.get("inputs") or {}
            result = uniformity.get("result") or {}
            status = str(uniformity.get("status", "success"))
            reason = str(uniformity.get("reason", ""))
            result_value_raw = result.get("value")
            result_value = float(result_value_raw) if isinstance(result_value_raw, (int, float)) else None
            result_text = str(uniformity.get("result_text", ""))
            if not result_text:
                if result_value is not None:
                    result_text = f"{result_value:.4f}"
                elif reason:
                    result_text = f"{status}: {reason}"
                else:
                    result_text = status
            stats = dict(uniformity.get("stats") or {})
            stats["status"] = status
            preview_text = str(uniformity.get("preview_text", ""))
            if preview_text:
                stats["preview"] = preview_text
            if reason:
                stats["reason"] = reason
            rows.append(
                {
                    "metric_name": "UNIFORMITY",
                    "formula_mode": f"{str(result.get('formula_label', inputs.get('formula', '')))} [{status}]",
                    "roi_ids": [str(item) for item in inputs.get("roi_ids", [])],
                    "roles": [],
                    "stats": stats,
                    "result_value": result_value,
                    "item_name": "Uniformity",
                    "note_text": "Uniformity score in percent",
                    "result_text": (f"{result_value:.2f}" if isinstance(result_value, (int, float)) else result_text),
                    "developer_meta": uniformity,
                }
            )

        line = self.analysis_last_run.get("line_profile")
        if line is not None:
            result = line.get("result") or {}
            line_stats = {
                "length_px": float(result.get("length_px", 0.0)),
                "sample_count": int(result.get("sample_count", 0)),
                "length_mm": result.get("length_mm"),
                "min_intensity": float(result.get("min_intensity", 0.0)),
                "max_intensity": float(result.get("max_intensity", 0.0)),
                "mean_intensity": float(result.get("mean_intensity", 0.0)),
                "std_intensity": float(result.get("std_intensity", 0.0)),
                "peak_count": int(result.get("peak_count", 0)),
                "valley_count": int(result.get("valley_count", 0)),
                "peak_value": result.get("peak_value"),
                "peak_position": result.get("peak_position"),
                "fwhm": result.get("fwhm"),
                "distance_unit": result.get("distance_unit", "px"),
            }
            if isinstance(line_stats.get("fwhm"), (int, float)):
                fwhm_display = f"{float(line_stats['fwhm']):.2f}{line_stats['distance_unit']}"
            else:
                fwhm_display = "N/A"
            line_note = (
                f"Samples: {line_stats['sample_count']} | Length: {line_stats['length_px']:.2f} px | "
                f"Mean: {line_stats['mean_intensity']:.2f} | Std: {line_stats['std_intensity']:.2f} | "
                f"FWHM: {fwhm_display}"
            )
            rows.append(
                {
                    "metric_name": "LINE_PROFILE_SUMMARY",
                    "formula_mode": "intensity(x) sampled along selected line",
                    "roi_ids": [str((line.get("inputs") or {}).get("line_id", ""))],
                    "roles": [],
                    "stats": line_stats,
                    "result_value": float(line_stats["mean_intensity"]),
                    "item_name": "Line Profile",
                    "note_text": line_note,
                    "result_text": f"{line_stats['mean_intensity']:.2f}",
                    "developer_meta": line,
                }
            )
        return rows

    def _build_analysis_result_rows(self) -> list[dict[str, Any]]:
        rows = self._build_analysis_last_run_rows() + self._build_roi_stats_result_rows()
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            normalized_rows.append(
                {
                    "metric_name": str(row.get("metric_name", "")),
                    "formula_mode": str(row.get("formula_mode", "")),
                    "roi_ids": [item for item in row.get("roi_ids", []) if item],
                    "roles": [item for item in row.get("roles", []) if item],
                    "stats": dict(row.get("stats") or {}),
                    "result_value": row.get("result_value"),
                    "result_text": str(row.get("result_text", "")),
                    "item_name": str(row.get("item_name", row.get("metric_name", ""))),
                    "note_text": str(row.get("note_text", "")),
                    "developer_meta": dict(row.get("developer_meta") or {}),
                }
            )
        return normalized_rows

    @staticmethod
    def _analysis_result_formula_map() -> dict[str, dict[str, Any]]:
        return {
            "SNR": {
                "formula": "SNR = μ_ROI / σ_noise",
                "symbols": [
                    "μ_ROI: ROI 평균 신호",
                    "σ_noise: 잡음 표준편차",
                ],
                "meaning": [
                    "영상 선명도 지표",
                    "SNR이 높을수록 → 노이즈 감소, 영상 품질 향상",
                ],
            },
            "CNR": {
                "formula": "CNR = |μ1 - μ2| / σ_noise",
                "symbols": [
                    "μ1, μ2: 비교 대상 ROI 평균 신호",
                    "σ_noise: 잡음 표준편차",
                ],
                "meaning": [
                    "조직 구분 능력 지표",
                    "CNR이 높을수록 → 병변 식별이 용이",
                    "(Rose Criterion: 약 3~5 이상에서 시각적 검출 가능)",
                ],
            },
            "UNIFORMITY": {
                "formula": "Uniformity(%) = (1 - (max - min) / (max + min)) × 100",
                "symbols": [
                    "max, min: ROI 최대/최소 평균값",
                ],
                "meaning": [
                    "영상 균일도 지표",
                    "값이 높을수록 → 균일성 양호",
                ],
            },
        }

    @staticmethod
    def _format_numeric_for_note(value: Any) -> str:
        return f"{float(value):.2f}" if isinstance(value, (int, float)) else "N/A"

    def _build_analysis_note_text(self, row: dict[str, Any]) -> str:
        metric_name = str(row.get("metric_name", "")).upper()
        formulas = self._analysis_result_formula_map()
        stats = dict(row.get("stats") or {})
        result_value = row.get("result_value")

        if metric_name == "SNR":
            signal_mean = stats.get("mean_signal")
            noise_std = stats.get("std_noise")
            if isinstance(signal_mean, (int, float)) and isinstance(noise_std, (int, float)) and isinstance(result_value, (int, float)):
                config = formulas["SNR"]
                return (
                    f"{config['formula']}\n"
                    f"= {self._format_numeric_for_note(signal_mean)} / {self._format_numeric_for_note(noise_std)}\n"
                    f"= {self._format_numeric_for_note(result_value)}\n\n"
                    f"{config['symbols'][0]}\n"
                    f"{config['symbols'][1]}\n\n"
                    f"{config['meaning'][0]}\n"
                    f"{config['meaning'][1]}"
                )
        elif metric_name == "CNR":
            target_mean = stats.get("target_mean")
            reference_mean = stats.get("reference_mean")
            noise_std = stats.get("noise_std")
            if (
                isinstance(target_mean, (int, float))
                and isinstance(reference_mean, (int, float))
                and isinstance(noise_std, (int, float))
                and isinstance(result_value, (int, float))
            ):
                config = formulas["CNR"]
                return (
                    f"{config['formula']}\n"
                    f"= |{self._format_numeric_for_note(target_mean)} - {self._format_numeric_for_note(reference_mean)}| / {self._format_numeric_for_note(noise_std)}\n"
                    f"= {self._format_numeric_for_note(result_value)}\n\n"
                    f"{config['symbols'][0]}\n"
                    f"{config['symbols'][1]}\n\n"
                    f"{config['meaning'][0]}\n"
                    f"{config['meaning'][1]}\n\n"
                    f"{config['meaning'][2]}"
                )
        elif metric_name == "UNIFORMITY":
            max_value = stats.get("max")
            min_value = stats.get("min")
            if isinstance(max_value, (int, float)) and isinstance(min_value, (int, float)) and isinstance(result_value, (int, float)):
                config = formulas["UNIFORMITY"]
                return (
                    f"{config['formula']}\n"
                    f"= (1 - ({self._format_numeric_for_note(max_value)} - {self._format_numeric_for_note(min_value)}) / "
                    f"({self._format_numeric_for_note(max_value)} + {self._format_numeric_for_note(min_value)})) × 100\n"
                    f"= {self._format_numeric_for_note(result_value)} %\n\n"
                    f"{config['symbols'][0]}\n\n"
                    f"{config['meaning'][0]}\n"
                    f"{config['meaning'][1]}"
                )

        return f"Derived metric\n= {self._format_numeric_for_note(result_value)}"

    def _format_analysis_value_text(self, row: dict[str, Any]) -> str:
        result_value = row.get("result_value")
        if isinstance(result_value, (int, float)):
            return f"{float(result_value):.2f}"
        return "-"

    def _append_analysis_history_row(self, row: dict[str, Any], unit: str, related_target_ids: list[str] | None = None) -> None:
        result_value = row.get("result_value")
        if not isinstance(result_value, (int, float)):
            return
        self._append_history_entry(
            measurement_type="Analysis",
            target_name=str(row.get("item_name", row.get("metric_name", "Analysis"))),
            metric=str(row.get("metric_name", "Analysis")),
            value=float(result_value),
            unit=unit,
            note=self._build_analysis_note_text(row),
            measurement_mode="analysis",
            related_target_ids=related_target_ids,
        )

    @staticmethod
    def _group_analysis_rows_for_panel(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        metric_rows: list[dict[str, Any]] = []
        snapshot_rows: list[dict[str, Any]] = []
        for row in rows:
            metric_name = str(row.get("metric_name", "")).upper()
            if metric_name == "ROI_STATS":
                snapshot_rows.append(row)
            else:
                metric_rows.append(row)

        ordered: list[dict[str, Any]] = []
        if metric_rows:
            ordered.append(
                {
                    "category": "SECTION",
                    "metric_name": "Results",
                    "formula_mode": "",
                    "roi_ids": [],
                    "roles": [],
                    "stats": {},
                    "result_value": None,
                    "result_text": "",
                }
            )
            for row in metric_rows:
                merged = dict(row)
                merged["category"] = "METRIC"
                ordered.append(merged)
        if snapshot_rows:
            ordered.append(
                {
                    "category": "SECTION",
                    "metric_name": "ROI Stats",
                    "formula_mode": "",
                    "roi_ids": [],
                    "roles": [],
                    "stats": {},
                    "result_value": None,
                    "result_text": "",
                }
            )
            for row in snapshot_rows:
                merged = dict(row)
                merged["category"] = "ROI_SNAPSHOT"
                ordered.append(merged)
        return ordered

    def _refresh_analysis_results_panel(self) -> None:
        rows_container = getattr(self, "analysis_results_rows_container", None)
        if rows_container is None:
            return
        for child in rows_container.winfo_children():
            child.destroy()
        self._analysis_results_row_widgets = []
        self._analysis_results_selected_index = None
        grouped_rows = self._group_analysis_rows_for_panel(self._build_analysis_result_rows())
        data_row_index = 0
        for row_index, row in enumerate(grouped_rows):
            category = str(row.get("category", "METRIC"))
            item_text = row["metric_name"] if category == "SECTION" else row.get("item_name", row["metric_name"])
            note_text = self._build_analysis_note_text(row) if category != "SECTION" else ""
            value_text = self._format_analysis_value_text(row) if category != "SECTION" else ""
            if category == "SECTION":
                item_text = f"[{item_text}]"
            item_value = self._sanitize_ui_text(str(item_text))
            value_value = self._sanitize_ui_text("" if value_text is None else str(value_text))
            note_value = note_text
            if category == "SECTION":
                background = "#F8FAFC"
                font = ("TkDefaultFont", 10, "bold")
            else:
                background = "#FFFFFF" if data_row_index % 2 == 0 else "#F6F7F9"
                font = ("TkDefaultFont", 10)
                data_row_index += 1
            row_frame = tk.Frame(rows_container, bg=background, highlightthickness=0, bd=0)
            row_frame.grid(row=row_index, column=0, sticky="ew")
            row_frame.grid_columnconfigure(0, weight=0, minsize=220)
            row_frame.grid_columnconfigure(1, weight=0, minsize=180)
            row_frame.grid_columnconfigure(2, weight=1, minsize=300)

            item_label = tk.Label(row_frame, text=item_value, anchor="w", justify="left", bg=background, fg=self.ui_colors["text_primary"], font=font, padx=8, pady=4)
            value_label = tk.Label(row_frame, text=value_value, anchor="w", justify="left", bg=background, fg=self.ui_colors["text_primary"], font=font, padx=6, pady=4)
            note_label = tk.Label(row_frame, text=note_value, anchor="w", justify="left", bg=background, fg=self.ui_colors["text_primary"], font=("TkDefaultFont", 9), padx=6, pady=4)
            item_label.grid(row=0, column=0, sticky="nsew")
            value_label.grid(row=0, column=1, sticky="nsew")
            note_label.grid(row=0, column=2, sticky="nsew")

            separator = tk.Frame(rows_container, height=1, bg=self.ui_colors["border"])
            separator.grid(row=(row_index * 2) + 1, column=0, sticky="ew")
            row_frame.grid_configure(row=row_index * 2)

            row_widgets = {
                "frame": row_frame,
                "labels": (item_label, value_label, note_label),
                "base_bg": background,
                "is_section": category == "SECTION",
            }
            self._analysis_results_row_widgets.append(row_widgets)
            for widget in (row_frame, item_label, value_label, note_label):
                widget.bind("<Button-1>", lambda _event, idx=row_index: self._select_analysis_results_row(idx))

        rows_container.grid_columnconfigure(0, weight=1)
        self._relayout_analysis_result_rows()

    def _select_analysis_results_row(self, row_index: int) -> None:
        self._analysis_results_selected_index = row_index
        selected_bg = "#DCEAFE"
        for index, row in enumerate(self._analysis_results_row_widgets):
            background = selected_bg if index == row_index else str(row["base_bg"])
            frame = row["frame"]
            labels = row["labels"]
            frame.configure(bg=background)
            for label in labels:
                label.configure(bg=background)

    def _relayout_analysis_result_rows(self) -> None:
        container = self.analysis_results_rows_container
        if container is None:
            return
        container.update_idletasks()
        width = max(int(container.winfo_width()), 400)
        item_width = 220
        value_width = 180
        note_width = max(240, width - item_width - value_width - 40)
        for row in self._analysis_results_row_widgets:
            labels = row["labels"]
            labels[0].configure(wraplength=item_width - 16)
            labels[1].configure(wraplength=value_width - 12)
            labels[2].configure(wraplength=note_width - 12)

    def _build_analysis_export_payload(self) -> dict[str, Any]:
        rows = self._build_analysis_result_rows()
        user_rows = [
            {
                "metric_name": row["metric_name"],
                "formula_mode": row["formula_mode"],
                "roi_ids": row["roi_ids"],
                "roles": row["roles"],
                "stats": row["stats"],
                "result_value": row["result_value"],
                "result_text": row["result_text"],
            }
            for row in rows
        ]
        return {
            "user_schema": {
                "version": "1.0",
                "generated_at": datetime.utcnow().isoformat(),
                "rows": user_rows,
            },
            "developer_meta": {
                "analysis_last_run": copy.deepcopy(self.analysis_last_run),
                "internal_rows": rows,
            },
        }

    def export_analysis_results_json(self) -> None:
        payload = self._build_analysis_export_payload()
        path = filedialog.asksaveasfilename(
            title="분석 결과 JSON 저장",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("저장 완료", f"Analysis JSON 저장 완료:\n{path}")

    def export_analysis_results_csv(self) -> None:
        payload = self._build_analysis_export_payload()
        path = filedialog.asksaveasfilename(
            title="분석 결과 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "metric_name",
                    "formula_mode",
                    "roi_ids",
                    "roles",
                    "mean",
                    "std",
                    "min",
                    "max",
                    "pixel_count",
                    "result_value",
                    "result_text",
                ]
            )
            for row in payload["user_schema"]["rows"]:
                stats = row.get("stats") or {}
                writer.writerow(
                    [
                        row.get("metric_name", ""),
                        row.get("formula_mode", ""),
                        ",".join(row.get("roi_ids", [])),
                        ",".join(row.get("roles", [])),
                        stats.get("mean", ""),
                        stats.get("std", ""),
                        stats.get("min", ""),
                        stats.get("max", ""),
                        stats.get("pixel_count", ""),
                        row.get("result_value", ""),
                        row.get("result_text", ""),
                    ]
                )
        messagebox.showinfo("저장 완료", f"Analysis CSV 저장 완료:\n{path}")

    def _get_selected_measurement_from_analysis(self, kind: str, input_key: str, combobox_key: str) -> Measurement | None:
        input_store = self.analysis_inputs if input_key in self.analysis_inputs else self.image_analysis_inputs
        if combobox_key in self._analysis_comboboxes:
            selected_label = self._analysis_comboboxes[combobox_key].get()
            option_map = self._analysis_option_maps.get(kind, {})
        else:
            selected_label = self._image_analysis_comboboxes.get(combobox_key).get() if combobox_key in self._image_analysis_comboboxes else ""
            option_map = self._image_analysis_option_maps.get(kind, {})
        if selected_label:
            mapped_id = option_map.get(selected_label, "")
            if mapped_id:
                input_store[input_key].set(mapped_id)
        selected_id = input_store[input_key].get()
        selected = self._find_measurement_by_id(selected_id, expected_kind=kind)
        if selected is None:
            return None
        if not self._is_analysis_compatible_measurement(selected):
            input_store[input_key].set("")
            if combobox_key in self._analysis_comboboxes:
                self._analysis_comboboxes[combobox_key].set("")
            elif combobox_key in self._image_analysis_comboboxes:
                self._image_analysis_comboboxes[combobox_key].set("")
            return None
        return selected

    def _read_analysis_selected_id(self, kind: str, input_key: str, combobox_key: str) -> str:
        input_store = self.analysis_inputs if input_key in self.analysis_inputs else self.image_analysis_inputs
        selected_id = input_store[input_key].get()
        if combobox_key in self._analysis_comboboxes:
            selected_label = self._analysis_comboboxes[combobox_key].get()
            option_map = self._analysis_option_maps.get(kind, {})
        else:
            selected_label = self._image_analysis_comboboxes.get(combobox_key).get() if combobox_key in self._image_analysis_comboboxes else ""
            option_map = self._image_analysis_option_maps.get(kind, {})
        if selected_label:
            mapped_id = option_map.get(selected_label, "")
            if mapped_id:
                selected_id = mapped_id
        return selected_id

    def _peek_selected_measurement_from_analysis(self, kind: str, input_key: str, combobox_key: str) -> Measurement | None:
        selected_id = self._read_analysis_selected_id(kind, input_key, combobox_key)
        selected = self._find_measurement_by_id(selected_id, expected_kind=kind)
        if selected is None:
            return None
        if not self._is_analysis_compatible_measurement(selected):
            return None
        return selected

    def _build_export_toolbar(self, tab: ttk.Frame) -> None:
        sections = self._build_subtoolbar_sections(tab, ["Measurement Sets", "Image Export"])
        ttk.Button(sections["Measurement Sets"], text="Save Measurement Set", command=self.save_measurement_set).pack(side="left")
        ttk.Button(sections["Measurement Sets"], text="Load Measurement Set", command=self.apply_measurement_set).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Measurement Sets"], text="Export Measurement Sets (JSON)", command=self.export_measurement_sets_json).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Measurement Sets"], text="Import Measurement Sets (JSON)", command=self.import_measurement_sets_json).pack(side="left", padx=(8, 0))
        ttk.Button(sections["Image Export"], text="뷰 내보내기", command=self.export_view_screenshot).pack(side="left")
        ttk.Button(sections["Image Export"], text="Figure 내보내기", command=self.export_clean_figure).pack(side="left", padx=(8, 0))

    def _build_status_row(self, parent: ttk.Frame) -> None:
        status = ttk.Frame(parent)
        status.pack(fill="x", pady=(10, 0))
        ttk.Label(status, textvariable=self.view_mode_var).pack(side="left")
        ttk.Label(status, textvariable=self.compare_sync_status_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.source_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.image_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.frame_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.zoom_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.window_level_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.cursor_var).pack(side="left", padx=(12, 0))
        ttk.Button(status, textvariable=self.info_toggle_var, command=self._toggle_info_panel).pack(side="right")

    def _build_collapsible_info_panel(self, parent: ttk.Frame) -> None:
        self.info_panel_frame = ttk.Frame(parent, padding=(12, 4, 12, 6))
        self.path_info_label = ttk.Label(self.info_panel_frame, textvariable=self.path_var)
        self.path_info_label.pack(fill="x", anchor="w")
        self.summary_info_label = ttk.Label(
            self.info_panel_frame,
            textvariable=self.info_var,
            justify="left",
            wraplength=1040,
            foreground=self.ui_colors["text_secondary"],
        )
        self.summary_info_label.pack(fill="x", anchor="w", pady=(2, 0))
        self.shortcut_info_label = ttk.Label(
            self.info_panel_frame,
            textvariable=self.shortcut_var,
            foreground=self.ui_colors["text_secondary"],
        )
        self.shortcut_info_label.pack(fill="x", anchor="w", pady=(2, 0))

        self.path_var.trace_add("write", self._sync_info_panel_visibility)
        self.info_var.trace_add("write", self._sync_info_panel_visibility)
        self.info_panel_expanded.trace_add("write", self._sync_info_panel_visibility)
        self._sync_info_panel_visibility()

    def _toggle_info_panel(self) -> None:
        self.info_panel_expanded.set(not self.info_panel_expanded.get())

    def _sync_info_panel_visibility(self, *_args: object) -> None:
        has_path = bool(self.path_var.get().strip())
        has_info = bool(self.info_var.get().strip())
        has_content = has_path or has_info
        is_expanded = self.info_panel_expanded.get()
        self.info_toggle_var.set("정보 숨기기" if is_expanded else "정보 표시")

        if self.info_panel_frame is None:
            return

        if is_expanded and has_content:
            self.info_panel_frame.pack(fill="x")
            if self.path_info_label is not None:
                if has_path:
                    self.path_info_label.pack(fill="x", anchor="w")
                else:
                    self.path_info_label.pack_forget()
            if self.summary_info_label is not None:
                if has_info:
                    self.summary_info_label.pack(fill="x", anchor="w", pady=(2, 0))
                else:
                    self.summary_info_label.pack_forget()
            if self.shortcut_info_label is not None:
                self.shortcut_info_label.pack(fill="x", anchor="w", pady=(2, 0))
        else:
            self.info_panel_frame.pack_forget()

    def _bind_shortcuts(self) -> None:
        bindings = [
            ("f", self._handle_fit_shortcut),
            ("F", self._handle_fit_shortcut),
            ("0", self._handle_actual_size_shortcut),
            ("<Control-0>", self._handle_actual_size_shortcut),
            ("r", self._handle_window_level_reset_shortcut),
            ("R", self._handle_window_level_reset_shortcut),
            ("s", self._handle_grid_roi_summary_shortcut),
            ("S", self._handle_grid_roi_summary_shortcut),
            ("<Left>", self._handle_left_shortcut),
            ("<Right>", self._handle_right_shortcut),
            ("<Up>", self._handle_up_shortcut),
            ("<Down>", self._handle_down_shortcut),
            ("<Return>", self._handle_enter_shortcut),
            ("<Escape>", self._handle_escape_shortcut),
            ("<Home>", self._handle_first_image_shortcut),
            ("<End>", self._handle_last_image_shortcut),
            ("<Prior>", self._handle_prev_image_shortcut),
            ("<Next>", self._handle_next_image_shortcut),
            ("<Shift-Prior>", self._handle_prev_frame_shortcut),
            ("<Shift-Next>", self._handle_next_frame_shortcut),
            ("<Control-z>", self._handle_undo_shortcut),
            ("<Delete>", self._handle_delete_selected_shortcut),
        ]
        for sequence, handler in bindings:
            self.root.bind(sequence, handler)

    def _create_compare_panel(self, parent: ttk.Frame, side: str, title: str) -> dict[str, Any]:
        panel: dict[str, Any] = {
            "side": side,
            "title_var": tk.StringVar(value=title),
            "path_var": tk.StringVar(value="폴더를 열어 비교 대상을 선택해 주세요."),
            "info_var": tk.StringVar(value="비교용 폴더를 열면 현재 선택 영상 요약이 표시됩니다."),
            "compare_index_var": tk.StringVar(value=f"{'Left' if side == 'left' else 'Right'} - / -"),
            "sync_note_var": tk.StringVar(value=""),
            "image_var": tk.StringVar(value="이미지: - / -"),
            "frame_var": tk.StringVar(value="프레임: - / -"),
            "zoom_var": tk.StringVar(value="Zoom: -"),
            "window_level_var": tk.StringVar(value="W/L: - / -"),
            "file_paths": [],
            "current_file_index": -1,
            "current_folder_path": None,
            "dataset": None,
            "frames": [],
            "current_frame": 0,
            "photo_image": None,
            "zoom_scale": 1.0,
            "window_width_value": None,
            "window_level_value": None,
            "default_window_width": None,
            "default_window_level": None,
            "window_level_range": (0.0, 1.0),
            "window_drag_origin": None,
            "window_drag_base": None,
            "overlay_values": {field["key"]: "N/A" for field in self.overlay_field_definitions},
            "last_canvas_size": (0, 0),
        }

        column = 0 if side == "left" else 1
        shell = ttk.LabelFrame(parent, text=title, padding=8)
        shell.grid(row=0, column=column, sticky="nsew", padx=(0, 6) if side == "left" else (6, 0))
        shell.columnconfigure(0, weight=1)
        panel["shell"] = shell

        toolbar = ttk.Frame(shell)
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Button(toolbar, text="폴더 열기", command=lambda target=side: self._compare_open_folder(target)).pack(side="left")
        ttk.Label(
            toolbar,
            textvariable=panel["compare_index_var"],
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left", padx=(12, 0))
        ttk.Button(toolbar, text="이전 이미지", command=lambda target=side: self._compare_change_file(target, -1)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(toolbar, text="다음 이미지", command=lambda target=side: self._compare_change_file(target, 1)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(toolbar, text="이전 프레임", command=lambda target=side: self._compare_change_frame(target, -1)).pack(
            side="left", padx=(12, 0)
        )
        ttk.Button(toolbar, text="다음 프레임", command=lambda target=side: self._compare_change_frame(target, 1)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(toolbar, text="창맞춤", command=lambda target=side: self._compare_fit_to_window(target)).pack(
            side="left", padx=(12, 0)
        )
        ttk.Button(toolbar, text="100%", command=lambda target=side: self._compare_reset_zoom_to_actual_size(target)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(toolbar, text="W/L 리셋", command=lambda target=side: self._compare_reset_window_level(target)).pack(
            side="left", padx=(12, 0)
        )

        status = ttk.Frame(shell)
        status.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for idx in range(4):
            status.columnconfigure(idx, weight=1)
        ttk.Label(status, textvariable=panel["image_var"]).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=panel["frame_var"]).grid(row=0, column=1, sticky="w")
        ttk.Label(status, textvariable=panel["zoom_var"]).grid(row=0, column=2, sticky="w")
        ttk.Label(status, textvariable=panel["window_level_var"]).grid(row=0, column=3, sticky="w")

        ttk.Label(shell, textvariable=panel["path_var"]).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(shell, textvariable=panel["sync_note_var"], foreground="#1f5f99").grid(
            row=3, column=0, sticky="ew", pady=(4, 0)
        )
        ttk.Label(shell, textvariable=panel["info_var"]).grid(row=4, column=0, sticky="ew", pady=(6, 0))

        canvas_frame = ttk.Frame(shell)
        canvas_frame.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        shell.rowconfigure(5, weight=1)

        canvas = tk.Canvas(canvas_frame, bg="black", highlightthickness=0)
        x_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        canvas.bind("<Configure>", lambda event, target=side: self._compare_on_canvas_resize(target, event))
        canvas.bind("<ButtonPress-1>", lambda event, target=side: self._compare_start_pan(target, event))
        canvas.bind("<B1-Motion>", lambda event, target=side: self._compare_update_pan(target, event))
        canvas.bind("<ButtonRelease-1>", lambda event, target=side: self._compare_end_pan(target, event))
        canvas.bind("<ButtonPress-3>", lambda event, target=side: self._compare_start_window_level_drag(target, event))
        canvas.bind("<B3-Motion>", lambda event, target=side: self._compare_update_window_level_drag(target, event))
        canvas.bind("<ButtonRelease-3>", lambda event, target=side: self._compare_end_window_level_drag(target, event))
        canvas.bind("<MouseWheel>", lambda event, target=side: self._compare_handle_mousewheel(target, event))
        canvas.bind("<Button-4>", lambda event, target=side: self._compare_handle_mousewheel(target, event))
        canvas.bind("<Button-5>", lambda event, target=side: self._compare_handle_mousewheel(target, event))

        panel["canvas"] = canvas
        return panel

    def _update_compare_controls(self) -> None:
        in_compare_mode = self.view_mode == "compare"
        state = "disabled" if in_compare_mode else "normal"
        for button in (
            self.open_file_button,
            self.open_folder_button,
            self.diagnose_button,
            self.toggle_view_button,
            self.prev_image_button,
            self.next_image_button,
            self.prev_frame_button,
            self.next_frame_button,
            self.window_level_reset_button,
        ):
            button.configure(state=state)
        if in_compare_mode:
            self.source_var.set("소스: 비교 모드")
        else:
            self._update_multiview_controls()
        self._update_compare_sync_status()

    def _update_compare_sync_status(self) -> None:
        if self.view_mode != "compare":
            self.compare_sync_status_var.set("비교 동기: Off")
            return
        if self.compare_sync_enabled.get():
            self.compare_sync_status_var.set("비교 동기: Index Sync")
            return
        self.compare_sync_status_var.set("비교 동기: Off")

    def _update_compare_panel_position_label(self, panel: dict[str, Any]) -> None:
        prefix = "Left" if panel["side"] == "left" else "Right"
        total = len(panel["file_paths"])
        index = panel["current_file_index"] + 1 if 0 <= panel["current_file_index"] < total else "-"
        panel["compare_index_var"].set(f"{prefix} {index} / {total if total else '-'}")

    def _capture_single_view_restore_state(self) -> None:
        if self.view_mode != "single" or not self.frames or self.current_file_index < 0:
            self.compare_restore_state = None
            return
        self.compare_restore_state = {
            "current_file_index": self.current_file_index,
            "current_frame": self.current_frame,
            "zoom_scale": self.zoom_scale,
            "center_ratio": self._capture_view_center_ratio(),
            "window_width_value": self.window_width_value,
            "window_level_value": self.window_level_value,
        }

    def _restore_single_view_state_after_compare(self) -> bool:
        state = self.compare_restore_state
        self.compare_restore_state = None
        if not state or not self.file_paths:
            return False
        index = state.get("current_file_index", -1)
        if not 0 <= index < len(self.file_paths):
            return False
        self._load_file(index, preserve_view_state=False)
        if self.frames:
            target_frame = min(max(int(state.get("current_frame", 0)), 0), len(self.frames) - 1)
            self.current_frame = target_frame
            zoom_scale = float(np.clip(state.get("zoom_scale", self.zoom_scale), self.min_zoom_scale, self.max_zoom_scale))
            self.zoom_scale = zoom_scale
            if state.get("window_width_value") is not None and state.get("window_level_value") is not None:
                self.window_width_value = state["window_width_value"]
                self.window_level_value = state["window_level_value"]
                self._update_window_level_label()
            self._show_frame(preserve_center_ratio=state.get("center_ratio"))
        return True

    def refresh_overlay_display(self) -> None:
        self._save_overlay_preferences()
        if self.view_mode == "single" and self.frames:
            self._show_frame()
            return
        if self.view_mode == "compare":
            for panel in self.compare_panels.values():
                if panel["frames"]:
                    self._compare_show_frame(panel["side"])

    def _load_overlay_preferences(self) -> None:
        try:
            if not self.overlay_settings_path.exists():
                return
            payload = json.loads(self.overlay_settings_path.read_text(encoding="utf-8"))
        except Exception:
            return

        if isinstance(payload.get("show_basic_overlay"), bool):
            self.show_basic_overlay.set(payload["show_basic_overlay"])
        if isinstance(payload.get("show_acquisition_overlay"), bool):
            self.show_acquisition_overlay.set(payload["show_acquisition_overlay"])
        if isinstance(payload.get("show_overlay_advanced"), bool):
            self.show_overlay_advanced.set(payload["show_overlay_advanced"])
        self.overlay_advanced_button_var.set(
            "고급 항목 숨기기" if self.show_overlay_advanced.get() else "고급 항목 펼치기"
        )

        selected_fields = payload.get("selected_fields")
        if isinstance(selected_fields, dict):
            for key, value in selected_fields.items():
                if key in self.overlay_field_vars and isinstance(value, bool):
                    self.overlay_field_vars[key].set(value)

        field_orders = payload.get("field_orders")
        if isinstance(field_orders, dict):
            for key, value in field_orders.items():
                field = self.overlay_field_lookup.get(key)
                if field is not None and isinstance(value, int):
                    field["order"] = value

    def _save_overlay_preferences(self) -> None:
        payload = {
            "show_basic_overlay": bool(self.show_basic_overlay.get()),
            "show_acquisition_overlay": bool(self.show_acquisition_overlay.get()),
            "show_overlay_advanced": bool(self.show_overlay_advanced.get()),
            "selected_fields": {
                key: bool(var.get())
                for key, var in self.overlay_field_vars.items()
            },
            "field_orders": {
                field["key"]: int(field["order"])
                for field in self.overlay_field_definitions
            },
        }
        try:
            self.overlay_settings_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return

    def _build_overlay_field_definitions(self) -> list[dict[str, Any]]:
        fields = [
            {
                "key": "patient_name",
                "label": "PatientName",
                "section": "left",
                "default_visible": True,
                "advanced": False,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["PatientName"]),
            },
            {
                "key": "patient_id",
                "label": "PatientID",
                "section": "left",
                "default_visible": True,
                "advanced": False,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["PatientID"]),
            },
            {
                "key": "study_date",
                "label": "StudyDate",
                "section": "left",
                "default_visible": True,
                "advanced": False,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_study_date_value]),
            },
            {
                "key": "modality",
                "label": "Modality",
                "section": "left",
                "default_visible": True,
                "advanced": False,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["Modality"]),
            },
            {
                "key": "study_description",
                "label": "StudyDescription",
                "section": "left",
                "default_visible": True,
                "advanced": False,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(
                    dataset, ["StudyDescription", "PerformedProcedureStepDescription"]
                ),
            },
            {
                "key": "series_description",
                "label": "SeriesDescription",
                "section": "left",
                "default_visible": True,
                "advanced": False,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["SeriesDescription", "ProtocolName"]),
            },
            {
                "key": "instance_number",
                "label": "InstanceNumber",
                "section": "left",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["InstanceNumber"]),
            },
            {
                "key": "accession_number",
                "label": "AccessionNumber",
                "section": "left",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["AccessionNumber"]),
            },
            {
                "key": "protocol_name",
                "label": "ProtocolName",
                "section": "left",
                "default_visible": False,
                "advanced": True,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["ProtocolName"]),
            },
            {
                "key": "acquisition_datetime",
                "label": "AcquisitionDateTime",
                "section": "left",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_acquisition_datetime_value]),
            },
            {
                "key": "patient_position",
                "label": "PatientPosition",
                "section": "left",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["PatientPosition"]),
            },
            {
                "key": "ei",
                "label": "EI",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["ExposureIndex"]),
            },
            {
                "key": "di",
                "label": "DI",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["DeviationIndex"]),
            },
            {
                "key": "kvp",
                "label": "kVp",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["KVP"]),
            },
            {
                "key": "ma",
                "label": "mA",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["XRayTubeCurrent"]),
            },
            {
                "key": "exposure_time",
                "label": "Exposure Time",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["ExposureTime", "ExposureTimeInms"]),
            },
            {
                "key": "mas",
                "label": "mAs",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_mas_value]),
            },
            {
                "key": "exposure",
                "label": "Exposure",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["Exposure", "ExposureInuAs"]),
            },
            {
                "key": "sid",
                "label": "SID",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["DistanceSourceToDetector"]),
            },
            {
                "key": "body_part_examined",
                "label": "Body Part Examined",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_body_part_value]),
            },
            {
                "key": "view_position",
                "label": "View Position",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["ViewPosition"]),
            },
            {
                "key": "laterality",
                "label": "Laterality",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_laterality_value]),
            },
            {
                "key": "photometric_interpretation",
                "label": "Photometric Interpretation",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["PhotometricInterpretation"]),
            },
            {
                "key": "rows_columns",
                "label": "Rows / Columns",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_rows_columns_value]),
            },
            {
                "key": "bits_stored",
                "label": "Bits Stored",
                "section": "right",
                "default_visible": True,
                "advanced": False,
                "single_line": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["BitsStored"]),
            },
            {
                "key": "manufacturer",
                "label": "Manufacturer",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["Manufacturer"]),
            },
            {
                "key": "station_name",
                "label": "StationName",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["StationName"]),
            },
            {
                "key": "detector_id",
                "label": "DetectorID",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["DetectorID"]),
            },
            {
                "key": "transfer_syntax_uid",
                "label": "TransferSyntaxUID",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_transfer_syntax_value]),
            },
            {
                "key": "image_type",
                "label": "ImageType",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["ImageType"]),
            },
            {
                "key": "pixel_spacing",
                "label": "PixelSpacing",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_pixel_spacing_value]),
            },
            {
                "key": "imager_pixel_spacing",
                "label": "ImagerPixelSpacing",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, [self._format_imager_pixel_spacing_value]),
            },
            {
                "key": "grid",
                "label": "Grid",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["Grid"]),
            },
            {
                "key": "focal_spot",
                "label": "FocalSpot",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["FocalSpots", "FocalSpot"]),
            },
            {
                "key": "software_versions",
                "label": "SoftwareVersions",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["SoftwareVersions"]),
            },
            {
                "key": "exposure_control_mode",
                "label": "ExposureControlMode",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "value_getter": lambda dataset: self._get_first_available_value(dataset, ["ExposureControlMode"]),
            },
            {
                "key": "acquisition_device_processing_description",
                "label": "AcquisitionDeviceProcessingDescription",
                "section": "right",
                "default_visible": False,
                "advanced": True,
                "wrap_priority": True,
                "value_getter": lambda dataset: self._get_first_available_value(
                    dataset, ["AcquisitionDeviceProcessingDescription"]
                ),
            },
        ]
        section_orders = {"left": 0, "right": 0}
        for field in fields:
            default_order = section_orders[field["section"]]
            field["default_order"] = default_order
            field["order"] = default_order
            section_orders[field["section"]] += 1
        return fields

    def open_overlay_settings(self) -> None:
        if self.overlay_settings_popup is not None and self.overlay_settings_popup.winfo_exists():
            self.overlay_settings_popup.lift()
            return

        popup = tk.Toplevel(self.root)
        popup.title("오버레이 항목 설정")
        popup.transient(self.root)
        popup.resizable(False, True)
        popup.protocol("WM_DELETE_WINDOW", self.close_overlay_settings)
        self.overlay_settings_popup = popup

        container = ttk.Frame(popup, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="오버레이 항목 설정").grid(row=0, column=0, sticky="w")
        ttk.Button(
            header,
            textvariable=self.overlay_advanced_button_var,
            command=self.toggle_overlay_advanced_fields,
        ).grid(row=0, column=1, sticky="e", padx=(0, 8))
        ttk.Button(
            header,
            textvariable=self.overlay_reset_button_var,
            command=self.reset_overlay_field_defaults,
        ).grid(row=0, column=2, sticky="e")

        left_frame = ttk.LabelFrame(container, text="좌측 기본 정보", padding=8)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(10, 0))
        right_frame = ttk.LabelFrame(container, text="우측 촬영 정보", padding=8)
        right_frame.grid(row=1, column=1, sticky="nsew", pady=(10, 0))
        self.overlay_settings_left_frame = left_frame
        self.overlay_settings_right_frame = right_frame
        self._rebuild_overlay_settings_fields()

    def close_overlay_settings(self) -> None:
        if self.overlay_settings_popup is not None and self.overlay_settings_popup.winfo_exists():
            self.overlay_settings_popup.destroy()
        self.overlay_settings_popup = None
        self.overlay_settings_left_frame = None
        self.overlay_settings_right_frame = None

    def toggle_overlay_advanced_fields(self) -> None:
        self.show_overlay_advanced.set(not self.show_overlay_advanced.get())
        self.overlay_advanced_button_var.set(
            "고급 항목 숨기기" if self.show_overlay_advanced.get() else "고급 항목 펼치기"
        )
        self._save_overlay_preferences()
        self._rebuild_overlay_settings_fields()

    def _rebuild_overlay_settings_fields(self) -> None:
        if self.overlay_settings_left_frame is None or self.overlay_settings_right_frame is None:
            return

        for frame in (self.overlay_settings_left_frame, self.overlay_settings_right_frame):
            for child in frame.winfo_children():
                child.destroy()

        show_advanced = self.show_overlay_advanced.get()
        row_map = {"left": 0, "right": 0}
        frame_map = {"left": self.overlay_settings_left_frame, "right": self.overlay_settings_right_frame}
        ordered_fields = sorted(
            self.overlay_field_definitions,
            key=lambda field: (field["section"], field["order"], field["default_order"]),
        )
        for field in ordered_fields:
            if field["advanced"] and not show_advanced:
                continue
            section = field["section"]
            frame = frame_map[section]
            row = row_map[section]
            frame.columnconfigure(0, weight=1)
            ttk.Checkbutton(
                frame,
                text=field["label"],
                variable=self.overlay_field_vars[field["key"]],
                command=lambda key=field["key"]: self._on_overlay_field_visibility_change(key),
            ).grid(row=row, column=0, sticky="w")
            ttk.Button(
                frame,
                text="↑",
                width=3,
                command=lambda key=field["key"]: self.move_overlay_field(key, -1),
                state=self._get_overlay_move_button_state(field["key"], -1),
            ).grid(row=row, column=1, padx=(6, 2))
            ttk.Button(
                frame,
                text="↓",
                width=3,
                command=lambda key=field["key"]: self.move_overlay_field(key, 1),
                state=self._get_overlay_move_button_state(field["key"], 1),
            ).grid(row=row, column=2)
            row_map[section] += 1

    def _on_overlay_field_visibility_change(self, _key: str) -> None:
        self._save_overlay_preferences()
        self._rebuild_overlay_settings_fields()
        self.refresh_overlay_display()

    def _get_visible_overlay_fields_in_section(self, section: str) -> list[dict[str, Any]]:
        return [
            field
            for field in sorted(
                self.overlay_field_definitions,
                key=lambda entry: (entry["order"], entry["default_order"]),
            )
            if field["section"] == section and self.overlay_field_vars[field["key"]].get()
        ]

    def _get_overlay_move_button_state(self, key: str, direction: int) -> str:
        field = self.overlay_field_lookup[key]
        if not self.overlay_field_vars[key].get():
            return "disabled"
        visible_fields = self._get_visible_overlay_fields_in_section(field["section"])
        visible_keys = [entry["key"] for entry in visible_fields]
        if key not in visible_keys:
            return "disabled"
        index = visible_keys.index(key)
        target_index = index + direction
        if not 0 <= target_index < len(visible_keys):
            return "disabled"
        return "normal"

    def move_overlay_field(self, key: str, direction: int) -> None:
        field = self.overlay_field_lookup.get(key)
        if field is None or not self.overlay_field_vars[key].get():
            return
        visible_fields = self._get_visible_overlay_fields_in_section(field["section"])
        visible_keys = [entry["key"] for entry in visible_fields]
        if key not in visible_keys:
            return
        index = visible_keys.index(key)
        target_index = index + direction
        if not 0 <= target_index < len(visible_keys):
            return
        target_field = self.overlay_field_lookup[visible_keys[target_index]]
        field["order"], target_field["order"] = target_field["order"], field["order"]
        self._save_overlay_preferences()
        self._rebuild_overlay_settings_fields()
        self.refresh_overlay_display()

    def reset_overlay_field_defaults(self) -> None:
        self.show_basic_overlay.set(True)
        self.show_acquisition_overlay.set(True)
        self.show_overlay_advanced.set(False)
        self.overlay_advanced_button_var.set("고급 항목 펼치기")
        for field in self.overlay_field_definitions:
            field["order"] = field["default_order"]
            self.overlay_field_vars[field["key"]].set(bool(field["default_visible"]))
        self._save_overlay_preferences()
        self._rebuild_overlay_settings_fields()
        self.refresh_overlay_display()

    def _can_use_multiview(self) -> bool:
        return self.loaded_from_folder and bool(self.file_paths)

    def _update_multiview_controls(self) -> None:
        if self._can_use_multiview():
            self.toggle_view_button.configure(state="normal")
            if self.current_folder_path:
                self.source_var.set(f"소스: 폴더 ({Path(self.current_folder_path).name})")
            else:
                self.source_var.set("소스: 폴더")
            return

        self.toggle_view_button.configure(state="disabled")
        self.source_var.set("소스: 단일 파일")

    def _set_loaded_paths(self, paths: list[str], folder: str | None = None) -> None:
        self.file_paths = paths
        self.current_folder_path = folder
        self.loaded_from_folder = folder is not None
        self._update_multiview_controls()

    def toggle_view_mode(self) -> None:
        if self.view_mode == "compare":
            return
        if self.view_mode == "single":
            self.enter_multiview_mode()
        else:
            self.enter_single_view_mode(load_selected=True)

    def toggle_compare_mode(self) -> None:
        if self.compare_mode_enabled.get():
            self.enter_compare_mode()
            return
        self.exit_compare_mode()

    def enter_compare_mode(self) -> None:
        self._capture_single_view_restore_state()
        self.compare_mode_enabled.set(True)
        self._cancel_multiview_thumbnail_job()
        self.close_multiview_grid_selector()
        self.view_mode = "compare"
        self.view_mode_var.set("보기: 비교")
        self.single_view_container.grid_remove()
        self.multiview_container.grid_remove()
        self.compare_container.grid()
        self.canvas.delete("overlay")
        self._update_compare_controls()

    def exit_compare_mode(self) -> None:
        self.compare_mode_enabled.set(False)
        self.compare_container.grid_remove()
        self._update_compare_controls()
        self.enter_single_view_mode(load_selected=bool(self.file_paths))
        if self._restore_single_view_state_after_compare():
            return

    def enter_single_view_mode(self, load_selected: bool = True) -> None:
        self.compare_mode_enabled.set(False)
        self.view_mode = "single"
        self.view_mode_var.set("보기: 단일")
        self._cancel_multiview_thumbnail_job()
        self.compare_container.grid_remove()
        self.multiview_container.grid_remove()
        self.single_view_container.grid()
        self.close_multiview_grid_selector()
        self._update_compare_controls()

        if load_selected and self.file_paths and self.current_file_index < 0:
            self.current_file_index = 0
        if load_selected and self.file_paths and 0 <= self.current_file_index < len(self.file_paths):
            self._load_file(self.current_file_index, preserve_view_state=False)
        elif self.frames:
            self._show_frame()

    def enter_multiview_mode(self) -> None:
        if not self.file_paths:
            messagebox.showinfo("멀티뷰", "먼저 DICOM 파일 또는 폴더를 열어 주세요.")
            return

        if not self._can_use_multiview():
            messagebox.showinfo("멀티뷰", "멀티뷰는 `폴더 열기` 또는 폴더 진단으로 불러온 목록에서만 사용할 수 있습니다.")
            return

        self.compare_mode_enabled.set(False)
        self.view_mode = "multi"
        self.view_mode_var.set("보기: 멀티")
        self.compare_container.grid_remove()
        self.single_view_container.grid_remove()
        self.multiview_container.grid()
        self.canvas.delete("overlay")
        self._update_compare_controls()
        self._ensure_multiview_selection_visible()
        self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")
        self.render_multiview_page()

    def _ensure_multiview_selection_visible(self) -> None:
        if not self.file_paths:
            self.multiview_page = 0
            return

        if self.current_file_index < 0:
            self.current_file_index = 0

        page_size = self._get_multiview_page_size()
        self.multiview_page = min(
            max(self.current_file_index // page_size, 0),
            max(self._get_multiview_total_pages() - 1, 0),
        )

    def _get_multiview_page_size(self) -> int:
        return self.multiview_cols * self.multiview_rows

    def _get_multiview_total_pages(self) -> int:
        if not self.file_paths:
            return 1
        page_size = self._get_multiview_page_size()
        return max((len(self.file_paths) + page_size - 1) // page_size, 1)

    def _get_multiview_page_bounds(self, page: int | None = None) -> tuple[int, int]:
        target_page = self.multiview_page if page is None else page
        start = max(target_page, 0) * self._get_multiview_page_size()
        end = min(start + self._get_multiview_page_size(), len(self.file_paths))
        return start, end

    def change_multiview_page(self, delta: int) -> None:
        if not self.file_paths:
            return
        self._move_multiview_page(delta)

    def _move_multiview_page(self, delta: int, preserve_slot: bool = True) -> None:
        if not self.file_paths:
            return
        total_pages = self._get_multiview_total_pages()
        new_page = min(max(self.multiview_page + delta, 0), total_pages - 1)
        if new_page == self.multiview_page:
            return
        if preserve_slot:
            self._select_multiview_page_slot(new_page)
        self.multiview_page = new_page
        self.render_multiview_page()

    def _go_to_multiview_page(self, page_index: int, preserve_slot: bool = True) -> None:
        if not self.file_paths:
            return
        total_pages = self._get_multiview_total_pages()
        new_page = min(max(page_index, 0), total_pages - 1)
        if new_page == self.multiview_page:
            return
        if preserve_slot:
            self._select_multiview_page_slot(new_page)
        self.multiview_page = new_page
        self.render_multiview_page()

    def _select_multiview_page_slot(self, page_index: int) -> None:
        if not self.file_paths:
            return
        page_size = self._get_multiview_page_size()
        if self.current_file_index < 0:
            slot = 0
        else:
            slot = self.current_file_index % page_size
        start, end = self._get_multiview_page_bounds(page_index)
        if end <= start:
            return
        self.current_file_index = min(start + slot, end - 1)
        self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")

    def _move_multiview_selection(self, delta: int) -> None:
        if self.view_mode != "multi" or not self.file_paths:
            return
        if self.current_file_index < 0:
            self.current_file_index = 0
        new_index = min(max(self.current_file_index + delta, 0), len(self.file_paths) - 1)
        if new_index == self.current_file_index:
            return
        self.current_file_index = new_index
        self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")
        self._ensure_multiview_selection_visible()
        self.render_multiview_page()

    def _on_multiview_resize(self, _event: tk.Event) -> None:
        if self.view_mode != "multi":
            return
        if self._multiview_resize_job is not None:
            self.root.after_cancel(self._multiview_resize_job)
        self._multiview_resize_job = self.root.after(80, self._render_multiview_page_if_visible)

    def _render_multiview_page_if_visible(self) -> None:
        self._multiview_resize_job = None
        if self.view_mode == "multi":
            self.render_multiview_page()

    def render_multiview_page(self) -> None:
        if self.view_mode != "multi":
            return

        self._cancel_multiview_thumbnail_job()
        self.multiview_render_token += 1
        self.multiview_tile_images = []
        self.multiview_tile_widgets = {}
        self.multiview_thumbnail_queue = []
        for child in self.multiview_body.winfo_children():
            child.destroy()

        total_pages = self._get_multiview_total_pages()
        self.multiview_page = min(max(self.multiview_page, 0), total_pages - 1)
        self.multiview_grid_var.set(f"격자: {self.multiview_cols} x {self.multiview_rows}")
        self.multiview_page_var.set(f"페이지: {self.multiview_page + 1} / {total_pages}")

        if not self.file_paths:
            ttk.Label(self.multiview_body, text="표시할 파일이 없습니다.").pack(expand=True)
            return

        width = max(self.multiview_body.winfo_width(), 400)
        height = max(self.multiview_body.winfo_height(), 300)
        pad = self.multiview_tile_padding
        tile_width = max((width - pad * (self.multiview_cols + 1)) // self.multiview_cols, 80)
        tile_height = max((height - pad * (self.multiview_rows + 1)) // self.multiview_rows, 100)

        for column in range(self.multiview_cols):
            self.multiview_body.columnconfigure(column, weight=1)
        for row in range(self.multiview_rows):
            self.multiview_body.rowconfigure(row, weight=1)

        start, end = self._get_multiview_page_bounds()
        page_paths = self.file_paths[start:end]

        for offset, path in enumerate(page_paths):
            file_index = start + offset
            row = offset // self.multiview_cols
            column = offset % self.multiview_cols
            self._build_multiview_tile(
                parent=self.multiview_body,
                path=path,
                file_index=file_index,
                row=row,
                column=column,
                tile_width=tile_width,
                tile_height=tile_height,
                page_index=self.multiview_page,
            )

        self._update_multiview_selected_status()
        self._queue_multiview_page_thumbnails(
            page_paths=page_paths,
            start_index=start,
            tile_width=tile_width,
            tile_height=tile_height,
            page_index=self.multiview_page,
            render_token=self.multiview_render_token,
        )
        self._evict_multiview_thumbnail_cache(self.multiview_page)

    def _build_multiview_tile(
        self,
        parent: ttk.Frame,
        path: str,
        file_index: int,
        row: int,
        column: int,
        tile_width: int,
        tile_height: int,
        page_index: int,
    ) -> None:
        is_selected = file_index == self.current_file_index
        tile = tk.Frame(
            parent,
            bg="#1f1f1f",
            highlightthickness=3 if is_selected else 1,
            highlightbackground="#4fa3ff" if is_selected else "#5a5a5a",
            width=tile_width,
            height=tile_height,
        )
        tile.grid(row=row, column=column, padx=self.multiview_tile_padding, pady=self.multiview_tile_padding, sticky="nsew")
        tile.grid_propagate(False)
        tile.rowconfigure(0, weight=1)
        tile.columnconfigure(0, weight=1)

        image_height = max(tile_height - 48, 40)
        thumb_label = tk.Label(
            tile,
            bg="#111111",
            fg="#d8d8d8",
            text="로딩 준비 중",
            anchor="center",
        )
        thumb_label.grid(row=0, column=0, sticky="nsew")
        display_name, secondary_text = self._get_multiview_tile_info(path, file_index, tile_width)
        name_label = tk.Label(
            tile,
            text=display_name,
            bg="#1f1f1f",
            fg="white",
            anchor="w",
            padx=6,
            font=("TkDefaultFont", 9, "bold"),
        )
        name_label.grid(row=1, column=0, sticky="ew")
        meta_label = tk.Label(
            tile,
            text=secondary_text,
            bg="#1f1f1f",
            fg="#b0b0b0",
            anchor="w",
            padx=6,
            font=("TkDefaultFont", 8),
        )
        meta_label.grid(row=2, column=0, sticky="ew")

        self.multiview_tile_widgets[file_index] = {
            "tile": tile,
            "thumb": thumb_label,
            "name": name_label,
            "meta": meta_label,
        }

        self._bind_multiview_tile_events(tile, file_index)
        self._bind_multiview_tile_events(thumb_label, file_index)
        self._bind_multiview_tile_events(name_label, file_index)
        self._bind_multiview_tile_events(meta_label, file_index)

    def _bind_multiview_tile_events(self, widget: tk.Widget, file_index: int) -> None:
        widget.bind("<Button-1>", lambda _event, index=file_index: self.select_multiview_tile(index))
        widget.bind("<Double-Button-1>", lambda _event, index=file_index: self.open_multiview_tile(index))

    def select_multiview_tile(self, file_index: int) -> None:
        if not 0 <= file_index < len(self.file_paths):
            return
        self.current_file_index = file_index
        self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")
        self._update_multiview_selected_status()
        self.render_multiview_page()

    def open_multiview_tile(self, file_index: int) -> None:
        if not 0 <= file_index < len(self.file_paths):
            return
        self.current_file_index = file_index
        self.enter_single_view_mode(load_selected=True)

    def _get_multiview_tile_info(self, path: str, file_index: int, tile_width: int) -> tuple[str, str]:
        cache_key = f"{path}|{tile_width}"
        cached = self.multiview_tile_meta_cache.get(cache_key)
        if cached is not None:
            return cached

        basename = Path(path).name
        max_chars = max((tile_width - 24) // 7, 8)
        display_name = self._ellipsize_text(basename, max_chars)
        info_text = self.multiview_info_cache.get(path)
        if info_text is None:
            info_text = f"#{file_index + 1}"
            self.multiview_info_cache[path] = info_text

        result = (display_name, info_text)
        self.multiview_tile_meta_cache[cache_key] = result
        return result

    @staticmethod
    def _ellipsize_text(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        if max_chars <= 3:
            return "." * max_chars
        return f"{text[:max_chars - 3]}..."

    def _get_multiview_thumbnail(self, path: str, width: int, height: int, page_index: int) -> ImageTk.PhotoImage | None:
        key = (path, width, height)
        cached = self._get_cached_multiview_thumbnail(path, width, height, page_index)
        if cached is not None:
            return cached

        try:
            dataset, frames = self.dicom_loader.get_decoded_file(path)
            if not frames:
                return None
            preview = self._build_multiview_thumbnail_image(dataset, frames[0], width, height)
            photo = ImageTk.PhotoImage(preview)
        except Exception:
            return None

        self.multiview_thumbnail_cache[key] = photo
        self._register_multiview_thumbnail_key(page_index, key)
        return photo

    def _get_cached_multiview_thumbnail(
        self,
        path: str,
        width: int,
        height: int,
        page_index: int,
    ) -> ImageTk.PhotoImage | None:
        key = (path, width, height)
        cached = self.multiview_thumbnail_cache.get(key)
        if cached is not None:
            self._register_multiview_thumbnail_key(page_index, key)
        return cached

    def _register_multiview_thumbnail_key(self, page_index: int, key: tuple[str, int, int]) -> None:
        page_keys = self.multiview_thumbnail_page_keys.setdefault(page_index, set())
        page_keys.add(key)

    def _evict_multiview_thumbnail_cache(self, current_page: int) -> None:
        keep_pages = {
            page
            for page in range(
                max(current_page - self.multiview_cache_page_window, 0),
                min(current_page + self.multiview_cache_page_window, self._get_multiview_total_pages() - 1) + 1,
            )
        }
        stale_pages = [page for page in self.multiview_thumbnail_page_keys if page not in keep_pages]
        for page in stale_pages:
            for key in self.multiview_thumbnail_page_keys.pop(page, set()):
                self.multiview_thumbnail_cache.pop(key, None)

    def _clear_multiview_thumbnail_cache(self) -> None:
        self._cancel_multiview_thumbnail_job()
        self.multiview_thumbnail_cache = {}
        self.multiview_thumbnail_page_keys = {}
        self.multiview_tile_widgets = {}
        self.multiview_thumbnail_queue = []

    def _cancel_multiview_thumbnail_job(self) -> None:
        if self._multiview_thumbnail_job is not None:
            self.root.after_cancel(self._multiview_thumbnail_job)
        self._multiview_thumbnail_job = None

    def _queue_multiview_page_thumbnails(
        self,
        page_paths: list[str],
        start_index: int,
        tile_width: int,
        tile_height: int,
        page_index: int,
        render_token: int,
    ) -> None:
        image_width = max(tile_width - 12, 1)
        image_height = max(tile_height - 60, 1)
        prioritized = []
        selected_offset = self.current_file_index - start_index
        if 0 <= selected_offset < len(page_paths):
            prioritized.append(selected_offset)
        prioritized.extend(offset for offset in range(len(page_paths)) if offset != selected_offset)

        for offset in prioritized:
            path = page_paths[offset]
            file_index = start_index + offset
            photo = self._get_cached_multiview_thumbnail(path, image_width, image_height, page_index)
            if photo is not None:
                self._apply_multiview_thumbnail_widget(file_index, photo)
                continue
            self.multiview_thumbnail_queue.append((file_index, path, image_width, image_height, page_index))

        if self.multiview_thumbnail_queue:
            self._multiview_thumbnail_job = self.root.after(
                1,
                lambda token=render_token: self._process_multiview_thumbnail_queue(token),
            )

    def _process_multiview_thumbnail_queue(self, render_token: int) -> None:
        self._multiview_thumbnail_job = None
        if self.view_mode != "multi" or render_token != self.multiview_render_token:
            return
        if not self.multiview_thumbnail_queue:
            return

        file_index, path, width, height, page_index = self.multiview_thumbnail_queue.pop(0)
        photo = self._get_multiview_thumbnail(path, width, height, page_index)
        if photo is not None:
            self._apply_multiview_thumbnail_widget(file_index, photo)
        else:
            widgets = self.multiview_tile_widgets.get(file_index)
            if widgets is not None:
                widgets["thumb"].configure(text="미리보기 실패", image="", fg="#f0f0f0", bg="#2a2a2a")

        if self.multiview_thumbnail_queue:
            self._multiview_thumbnail_job = self.root.after(
                1,
                lambda token=render_token: self._process_multiview_thumbnail_queue(token),
            )

    def _apply_multiview_thumbnail_widget(self, file_index: int, photo: ImageTk.PhotoImage) -> None:
        widgets = self.multiview_tile_widgets.get(file_index)
        if widgets is None:
            return
        widgets["thumb"].configure(image=photo, text="", bg="black")
        self.multiview_tile_images.append(photo)

    def _build_multiview_thumbnail_image(self, dataset, frame: np.ndarray, width: int, height: int) -> Image.Image:
        normalized = self._normalize_frame_for_dataset(
            dataset=dataset,
            frame=frame,
            window_width=self._get_window_width_from_dataset(dataset),
            window_level=self._get_window_center_from_dataset(dataset),
        )
        image = Image.fromarray(normalized)
        image.thumbnail((max(width, 1), max(height, 1)), Image.Resampling.BILINEAR)
        return image

    def _update_multiview_selected_status(self) -> None:
        if self.view_mode != "multi" or not 0 <= self.current_file_index < len(self.file_paths):
            return
        path = self.file_paths[self.current_file_index]
        self.path_var.set(path)
        self._update_selection_info_panel(path)

    def _get_metadata_dataset(self, path: str):
        cached = self._metadata_cache.get(path)
        if cached is not None:
            return cached
        dataset = pydicom.dcmread(path, stop_before_pixels=True)
        self._metadata_cache[path] = dataset
        return dataset

    @staticmethod
    def _is_missing_info_value(value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, pydicom.multival.MultiValue):
            return len(value) == 0
        return False

    def _format_info_value(self, value) -> str:
        if self._is_missing_info_value(value):
            return "N/A"
        if isinstance(value, pydicom.multival.MultiValue):
            return ", ".join(self._format_info_value(item) for item in value if not self._is_missing_info_value(item)) or "N/A"
        text = str(value).strip()
        return text if text else "N/A"

    def _get_candidate_value(self, dataset, candidate):
        if callable(candidate):
            return candidate(dataset)
        value = getattr(dataset, candidate, None)
        if self._is_missing_info_value(value):
            return None
        return self._format_info_value(value)

    def _get_first_available_value(self, dataset, candidates: list) -> str:
        for candidate in candidates:
            value = self._get_candidate_value(dataset, candidate)
            if value is not None and value != "N/A":
                return value
        return "N/A"

    @staticmethod
    def _format_study_date_value(dataset) -> str | None:
        value = getattr(dataset, "StudyDate", None)
        if value is None:
            return None
        text = str(value).strip()
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        return text or None

    @staticmethod
    def _format_acquisition_datetime_value(dataset) -> str | None:
        value = getattr(dataset, "AcquisitionDateTime", None)
        if value is None:
            return None
        text = str(value).strip()
        if len(text) >= 14 and text[:14].isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}"
        return text or None

    @staticmethod
    def _format_spacing_value(value) -> str | None:
        if value is None:
            return None
        if isinstance(value, pydicom.multival.MultiValue):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return " x ".join(cleaned) if cleaned else None
        text = str(value).strip()
        return text or None

    def _format_pixel_spacing_value(self, dataset) -> str | None:
        return self._format_spacing_value(getattr(dataset, "PixelSpacing", None))

    def _format_imager_pixel_spacing_value(self, dataset) -> str | None:
        return self._format_spacing_value(getattr(dataset, "ImagerPixelSpacing", None))

    @staticmethod
    def _format_rows_columns_value(dataset) -> str | None:
        rows = getattr(dataset, "Rows", None)
        columns = getattr(dataset, "Columns", None)
        if rows is None or columns is None:
            return None
        return f"{columns} x {rows}"

    @staticmethod
    def _format_transfer_syntax_value(dataset) -> str | None:
        file_meta = getattr(dataset, "file_meta", None)
        transfer_syntax = getattr(file_meta, "TransferSyntaxUID", None)
        if transfer_syntax is None:
            return None
        return str(transfer_syntax)

    @staticmethod
    def _format_body_part_value(dataset) -> str | None:
        value = getattr(dataset, "BodyPartExamined", None)
        if value not in (None, ""):
            return str(value)
        sequence = getattr(dataset, "AnatomicRegionSequence", None)
        if not sequence:
            return None
        item = sequence[0]
        code_meaning = getattr(item, "CodeMeaning", None)
        return str(code_meaning).strip() if code_meaning else None

    @staticmethod
    def _format_laterality_value(dataset) -> str | None:
        for keyword in ("Laterality", "ImageLaterality"):
            value = getattr(dataset, keyword, None)
            if value not in (None, ""):
                return str(value)
        return None

    @staticmethod
    def _format_mas_value(dataset) -> str | None:
        direct = getattr(dataset, "ExposureInmAs", None)
        if direct not in (None, ""):
            return str(direct)

        tube_current = getattr(dataset, "XRayTubeCurrent", None)
        exposure_time = getattr(dataset, "ExposureTime", None)
        if tube_current in (None, "") or exposure_time in (None, ""):
            return None

        try:
            tube_current_ma = float(tube_current)
            exposure_time_ms = float(exposure_time)
        except (TypeError, ValueError):
            return None
        calculated_mas = tube_current_ma * exposure_time_ms / 1000.0
        return f"{calculated_mas:.3f} (calculated)"

    def _build_status_summary(self, dataset, frames: list[np.ndarray] | None = None) -> str:
        patient_name = self._get_first_available_value(dataset, ["PatientName"])
        modality = self._get_first_available_value(dataset, ["Modality"])
        study_date = self._get_first_available_value(dataset, [self._format_study_date_value])
        instance_number = self._get_first_available_value(dataset, ["InstanceNumber"])
        parts = [
            f"환자: {patient_name}",
            f"모달리티: {modality}",
            f"촬영일: {study_date}",
            f"Instance: {instance_number}",
        ]
        if frames is not None:
            parts.append(f"프레임: {len(frames)}")
        return " | ".join(parts)

    def _collect_overlay_values(self, dataset) -> dict[str, str]:
        values: dict[str, str] = {}
        for field in self.overlay_field_definitions:
            value = field["value_getter"](dataset)
            values[field["key"]] = value if value not in (None, "") else "N/A"
        return values

    def _update_overlay_data_for_dataset(self, dataset, path: str, frames: list[np.ndarray] | None = None) -> None:
        self.path_var.set(path)
        self.info_var.set(self._build_status_summary(dataset, frames))
        self.current_overlay_values = self._collect_overlay_values(dataset)

    def _update_selection_info_panel(self, path: str) -> None:
        try:
            dataset = self._get_metadata_dataset(path)
        except Exception as exc:
            self.path_var.set(path)
            self.info_var.set(f"메타데이터 읽기 실패: {exc}")
            for field in self.overlay_field_definitions:
                self.current_overlay_values[field["key"]] = "N/A"
            return
        self._update_overlay_data_for_dataset(dataset, path)

    def _get_visible_overlay_entries(
        self,
        section: str,
        overlay_values: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        values = self.current_overlay_values if overlay_values is None else overlay_values
        entries = []
        for field in sorted(
            self.overlay_field_definitions,
            key=lambda entry: (entry["section"], entry["order"], entry["default_order"]),
        ):
            if field["section"] != section:
                continue
            if not self.overlay_field_vars[field["key"]].get():
                continue
            entries.append(
                {
                    "key": field["key"],
                    "label": field["label"],
                    "value": values.get(field["key"], "N/A"),
                    "wrap_priority": bool(field.get("wrap_priority", False)),
                    "single_line": bool(field.get("single_line", False)),
                }
            )
        return entries

    def _draw_overlay_block(
        self,
        canvas: tk.Canvas,
        entries: list[dict[str, str]],
        anchor: str,
        x: float,
        y: float,
        justify: str,
        tag_prefix: str,
        max_width: int,
        conservative: bool,
    ) -> None:
        if not entries:
            return
        font = tkfont.nametofont("TkDefaultFont")
        text = self._format_overlay_entries(entries, max_width=max_width, font=font, conservative=conservative)
        if not text:
            return

        text_id = canvas.create_text(
            x,
            y,
            text=text,
            anchor=anchor,
            fill=self.ui_colors["overlay_text"],
            font=font,
            justify=justify,
            width=max_width,
            tags=(tag_prefix, "overlay"),
        )
        canvas.itemconfig(text_id, state="disabled")
        shadow_offsets = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]
        for index, (dx, dy) in enumerate(shadow_offsets):
            shadow_id = canvas.create_text(
                x + dx,
                y + dy,
                text=text,
                anchor=anchor,
                fill="#0B1220",
                font=font,
                justify=justify,
                width=max_width,
                tags=(f"{tag_prefix}_shadow_{index}", "overlay"),
            )
            canvas.itemconfig(shadow_id, state="disabled")
            canvas.tag_lower(f"{tag_prefix}_shadow_{index}", text_id)

    def _build_measurement_label_parts(
        self,
        kind: str,
        metrics: dict[str, Any],
        measurement: Measurement | None = None,
    ) -> tuple[str, str]:
        if kind == "line":
            primary = f"{self._format_mm_value(metrics['length_mm'])} mm"
            secondary = f"{metrics['length_px']:.1f} px"
            return primary, secondary
        if kind == "polygon":
            primary = f"Area {self._format_mm_value(metrics['area_mm2'])} mm²"
            secondary = f"{metrics['area_px']:.1f} px²"
            return primary, secondary

        width_px = int(round(metrics["width_px"]))
        height_px = int(round(metrics["height_px"]))
        area_px = int(round(metrics["area_px"]))
        roi_label = self._format_roi_label(0)
        if measurement is not None:
            roi_label = self._display_name_for_roi_id(measurement.id)
        primary = (
            f"{roi_label} | "
            f"W {self._format_mm_value(metrics['width_mm'])}mm  "
            f"H {self._format_mm_value(metrics['height_mm'])}mm  "
            f"A {self._format_mm_value(metrics['area_mm2'])}mm²"
        )
        secondary = f"{width_px}×{height_px}px  {area_px}px²"
        return primary, secondary

    def _draw_measurement_label(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        primary_text: str,
        secondary_text: str,
        tags: tuple[str, ...],
        anchor: str = "sw",
        non_interactive: bool = False,
    ) -> list[int]:
        primary_id = canvas.create_text(
            x,
            y,
            text=primary_text,
            fill="#F9FAFB",
            anchor=anchor,
            font=("TkDefaultFont", 9, "bold"),
            tags=tags,
        )
        item_ids = [primary_id]
        if secondary_text:
            secondary_id = canvas.create_text(
                x,
                y + 14,
                text=secondary_text,
                fill="#CBD5E1",
                anchor=anchor,
                font=("TkDefaultFont", 8),
                tags=tags,
            )
            item_ids.append(secondary_id)
        if non_interactive:
            for item_id in item_ids:
                canvas.itemconfig(item_id, state="disabled")
        return item_ids

    def _resolve_roi_label_position(
        self,
        x: float,
        y: float,
        primary_text: str,
        secondary_text: str,
        occupied_boxes: list[tuple[float, float, float, float]],
    ) -> tuple[float, float, str, tuple[float, float, float, float]]:
        primary_font = tkfont.Font(font=("TkDefaultFont", 9, "bold"))
        secondary_font = tkfont.Font(font=("TkDefaultFont", 8))
        primary_lines = primary_text.splitlines() or [primary_text]
        secondary_lines = secondary_text.splitlines() if secondary_text else []
        line_gap = 3
        label_height = len(primary_lines) * primary_font.metrics("linespace")
        if secondary_lines:
            label_height += line_gap + len(secondary_lines) * secondary_font.metrics("linespace")
        label_width = max(
            [primary_font.measure(line) for line in primary_lines]
            + [secondary_font.measure(line) for line in secondary_lines or [""]]
        )
        padding = 4
        offsets = [(8, -8), (8, 12), (-8, -8), (-8, 12), (14, -22), (-14, -22), (14, 24), (-14, 24)]
        canvas_width = max(float(self.canvas.winfo_width()), 1.0)
        canvas_height = max(float(self.canvas.winfo_height()), 1.0)

        def adjust_candidate(tx: float, ty: float, anchor_name: str) -> tuple[float, float, tuple[float, float, float, float]]:
            if anchor_name == "sw":
                box = (tx, ty - label_height - padding, tx + label_width + padding, ty + padding)
                shift_x = 0.0
                if box[0] < 1:
                    shift_x = 1 - box[0]
                elif box[2] > canvas_width - 1:
                    shift_x = (canvas_width - 1) - box[2]
                shift_y = 0.0
                if box[1] < 1:
                    shift_y = 1 - box[1]
                elif box[3] > canvas_height - 1:
                    shift_y = (canvas_height - 1) - box[3]
                adjusted_tx = tx + shift_x
                adjusted_ty = ty + shift_y
                adjusted_box = (
                    adjusted_tx,
                    adjusted_ty - label_height - padding,
                    adjusted_tx + label_width + padding,
                    adjusted_ty + padding,
                )
                return adjusted_tx, adjusted_ty, adjusted_box
            box = (tx - label_width - padding, ty - label_height - padding, tx, ty + padding)
            shift_x = 0.0
            if box[0] < 1:
                shift_x = 1 - box[0]
            elif box[2] > canvas_width - 1:
                shift_x = (canvas_width - 1) - box[2]
            shift_y = 0.0
            if box[1] < 1:
                shift_y = 1 - box[1]
            elif box[3] > canvas_height - 1:
                shift_y = (canvas_height - 1) - box[3]
            adjusted_tx = tx + shift_x
            adjusted_ty = ty + shift_y
            adjusted_box = (
                adjusted_tx - label_width - padding,
                adjusted_ty - label_height - padding,
                adjusted_tx,
                adjusted_ty + padding,
            )
            return adjusted_tx, adjusted_ty, adjusted_box

        chosen = (x + 8, y - 8, "sw")
        chosen_x, chosen_y, chosen_box = adjust_candidate(chosen[0], chosen[1], chosen[2])
        for dx, dy in offsets:
            anchor = "sw" if dx >= 0 else "se"
            tx = x + dx
            ty = y + dy
            tx, ty, bbox = adjust_candidate(tx, ty, anchor)
            overlaps = any(
                not (bbox[2] < ox0 or bbox[0] > ox1 or bbox[3] < oy0 or bbox[1] > oy1)
                for ox0, oy0, ox1, oy1 in occupied_boxes
            )
            if not overlaps:
                return tx, ty, anchor, bbox
        return chosen_x, chosen_y, chosen[2], chosen_box

    def _truncate_text_to_width(self, text: str, max_width: int, font: tkfont.Font) -> str:
        if font.measure(text) <= max_width:
            return text
        ellipsis = "..."
        available = max(max_width - font.measure(ellipsis), 0)
        trimmed = text
        while trimmed and font.measure(trimmed) > available:
            trimmed = trimmed[:-1]
        return f"{trimmed}{ellipsis}" if trimmed else ellipsis

    def _wrap_text_to_lines(
        self,
        text: str,
        max_width: int,
        max_lines: int,
        font: tkfont.Font,
    ) -> list[str]:
        if text == "N/A":
            return [text]

        words = text.split()
        if not words:
            return [text]

        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.measure(candidate) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""
            if len(lines) >= max_lines:
                break

            if font.measure(word) <= max_width:
                current = word
            else:
                lines.append(self._truncate_text_to_width(word, max_width, font))
                if len(lines) >= max_lines:
                    current = ""
                    break

        if current and len(lines) < max_lines:
            lines.append(current)

        original_text = " ".join(words)
        rendered_text = " ".join(lines)
        if rendered_text != original_text and lines:
            lines[-1] = self._truncate_text_to_width(lines[-1], max_width, font)
            if not lines[-1].endswith("..."):
                lines[-1] = self._truncate_text_to_width(f"{lines[-1]}...", max_width, font)
        return lines[:max_lines] or [self._truncate_text_to_width(text, max_width, font)]

    def _format_overlay_entries(
        self,
        entries: list[dict[str, str]],
        max_width: int,
        font: tkfont.Font,
        conservative: bool,
    ) -> str:
        value_width = max(max_width - 130, 90 if conservative else 120)
        wrapped_lines: list[str] = []

        for entry in entries:
            label = entry["label"]
            value = entry["value"]
            if entry.get("single_line"):
                line_text = f"{label}: {value}"
                wrapped_lines.append(self._truncate_text_to_width(line_text, max_width, font))
                continue

            if entry.get("wrap_priority"):
                max_lines = 2 if conservative else 3
                value_lines = self._wrap_text_to_lines(value, value_width, max_lines, font)
                wrapped_lines.append(f"{label}: {value_lines[0]}")
                indent = " " * (len(label) + 2)
                for continuation in value_lines[1:]:
                    wrapped_lines.append(f"{indent}{continuation}")
                continue

            line_text = f"{label}: {value}"
            wrapped_lines.append(self._truncate_text_to_width(line_text, max_width, font))

        return "\n".join(wrapped_lines)

    def _get_overlay_layout(
        self,
        canvas: tk.Canvas,
        photo_image: ImageTk.PhotoImage | None,
    ) -> tuple[float, float, float, int, bool]:
        visible_left = canvas.canvasx(0)
        visible_top = canvas.canvasy(0)
        visible_right = canvas.canvasx(canvas.winfo_width())
        margin = 16

        image_width = photo_image.width() if photo_image is not None else 0
        image_height = photo_image.height() if photo_image is not None else 0
        content_width = max(canvas.winfo_width(), image_width)
        content_height = max(canvas.winfo_height(), image_height)
        image_left = (content_width - image_width) / 2
        image_right = image_left + image_width

        left_margin_width = max(image_left - visible_left, 0)
        right_margin_width = max(visible_right - image_right, 0)
        conservative = left_margin_width < 180 or right_margin_width < 180

        preferred_width = 280 if conservative else 340
        left_width = min(max(int(left_margin_width) - margin * 2, 0), preferred_width)
        right_width = min(max(int(right_margin_width) - margin * 2, 0), preferred_width)

        overlay_width = max(left_width, right_width)
        if overlay_width < 180:
            fallback = max(int((visible_right - visible_left) * (0.24 if conservative else 0.30)), 180)
            overlay_width = min(fallback, 320 if conservative else 360)

        left_x = visible_left + margin if left_margin_width >= overlay_width + margin * 2 else visible_left + margin
        right_x = (
            visible_right - margin
            if right_margin_width >= overlay_width + margin * 2
            else visible_right - margin
        )
        return left_x, visible_top + margin, right_x, overlay_width, conservative

    def _draw_single_view_overlays(self) -> None:
        self.canvas.delete("overlay")
        if self.view_mode != "single" or not self.frames:
            return

        left_x, top_y, right_x, overlay_width, conservative = self._get_overlay_layout(self.canvas, self.photo_image)

        if self.show_basic_overlay.get():
            self._draw_overlay_block(
                canvas=self.canvas,
                entries=self._get_visible_overlay_entries("left"),
                anchor="nw",
                x=left_x,
                y=top_y,
                justify="left",
                tag_prefix="overlay_left",
                max_width=overlay_width,
                conservative=conservative,
            )

        if self.show_acquisition_overlay.get():
            self._draw_overlay_block(
                canvas=self.canvas,
                entries=self._get_visible_overlay_entries("right"),
                anchor="ne",
                x=right_x,
                y=top_y,
                justify="right",
                tag_prefix="overlay_right",
                max_width=overlay_width,
                conservative=conservative,
            )

    def _draw_compare_overlays(self, panel: dict[str, Any]) -> None:
        canvas = panel["canvas"]
        canvas.delete("overlay")
        if self.view_mode != "compare" or not panel["frames"]:
            return

        left_x, top_y, right_x, overlay_width, conservative = self._get_overlay_layout(
            canvas,
            panel["photo_image"],
        )
        if self.show_basic_overlay.get():
            self._draw_overlay_block(
                canvas=canvas,
                entries=self._get_compare_overlay_entries(panel, "left"),
                anchor="nw",
                x=left_x,
                y=top_y,
                justify="left",
                tag_prefix=f"{panel['side']}_overlay_left",
                max_width=overlay_width,
                conservative=conservative,
            )
        if self.show_acquisition_overlay.get():
            self._draw_overlay_block(
                canvas=canvas,
                entries=self._get_compare_overlay_entries(panel, "right"),
                anchor="ne",
                x=right_x,
                y=top_y,
                justify="right",
                tag_prefix=f"{panel['side']}_overlay_right",
                max_width=overlay_width,
                conservative=conservative,
            )

    def _get_compare_overlay_entries(self, panel: dict[str, Any], section: str) -> list[dict[str, str]]:
        entries = []
        for key in self.compare_overlay_field_keys[section]:
            field = self.overlay_field_lookup.get(key)
            if field is None:
                continue
            entries.append(
                {
                    "key": field["key"],
                    "label": field["label"],
                    "value": panel["overlay_values"].get(field["key"], "N/A"),
                    "wrap_priority": bool(field.get("wrap_priority", False)),
                    "single_line": bool(field.get("single_line", False)),
                }
            )
        return entries

    def open_multiview_grid_selector(self) -> None:
        if self.multiview_popup is not None and self.multiview_popup.winfo_exists():
            self.multiview_popup.lift()
            return

        popup = tk.Toplevel(self.root)
        popup.title("격자 선택")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.protocol("WM_DELETE_WINDOW", self.close_multiview_grid_selector)
        self.multiview_popup = popup
        self.multiview_hover_cols = self.multiview_cols
        self.multiview_hover_rows = self.multiview_rows
        self.multiview_grid_labels = []

        container = ttk.Frame(popup, padding=12)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="격자 선택").grid(row=0, column=0, sticky="w")

        preview_var = tk.StringVar(value=f"{self.multiview_cols} x {self.multiview_rows}")
        ttk.Label(container, textvariable=preview_var).grid(row=0, column=1, sticky="e", padx=(12, 0))

        grid_frame = tk.Frame(container, bg="#d0d0d0")
        grid_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))

        for row in range(5):
            for column in range(10):
                cell = tk.Label(
                    grid_frame,
                    width=2,
                    height=1,
                    bg="white",
                    relief="solid",
                    borderwidth=1,
                )
                cell.grid(row=row, column=column, padx=1, pady=1)
                cell.bind(
                    "<Enter>",
                    lambda _event, c=column + 1, r=row + 1: self._update_multiview_grid_hover(c, r, preview_var),
                )
                cell.bind(
                    "<Button-1>",
                    lambda _event, c=column + 1, r=row + 1: self._apply_multiview_grid_selection(c, r),
                )
                self.multiview_grid_labels.append((column + 1, row + 1, cell))

        self._refresh_multiview_grid_hover(preview_var)

    def close_multiview_grid_selector(self) -> None:
        if self.multiview_popup is not None and self.multiview_popup.winfo_exists():
            self.multiview_popup.destroy()
        self.multiview_popup = None
        self.multiview_grid_labels = []

    def _update_multiview_grid_hover(self, cols: int, rows: int, preview_var: tk.StringVar) -> None:
        self.multiview_hover_cols = cols
        self.multiview_hover_rows = rows
        self._refresh_multiview_grid_hover(preview_var)

    def _refresh_multiview_grid_hover(self, preview_var: tk.StringVar) -> None:
        preview_var.set(f"{self.multiview_hover_cols} x {self.multiview_hover_rows}")
        for cols, rows, label in self.multiview_grid_labels:
            if cols <= self.multiview_hover_cols and rows <= self.multiview_hover_rows:
                label.configure(bg="#4fa3ff")
            else:
                label.configure(bg="white")

    def _apply_multiview_grid_selection(self, cols: int, rows: int) -> None:
        self.multiview_cols = min(max(cols, 1), 10)
        self.multiview_rows = min(max(rows, 1), 5)
        self._clear_multiview_thumbnail_cache()
        self.multiview_grid_var.set(f"격자: {self.multiview_cols} x {self.multiview_rows}")
        self._ensure_multiview_selection_visible()
        self.render_multiview_page()
        self.close_multiview_grid_selector()

    def _get_compare_panel(self, side: str) -> dict[str, Any]:
        return self.compare_panels[side]

    def _compare_open_folder(self, side: str) -> None:
        folder = filedialog.askdirectory(title=f"{'좌측' if side == 'left' else '우측'} 비교 폴더 선택")
        if not folder:
            return

        candidate_paths, excluded = self._collect_folder_candidates(folder)
        if not candidate_paths:
            messagebox.showwarning(
                "표시 가능한 DICOM 없음",
                self._build_quick_folder_message(folder, candidate_paths, excluded),
            )
            return

        panel = self._get_compare_panel(side)
        panel["file_paths"] = candidate_paths
        panel["current_folder_path"] = folder
        panel["sync_note_var"].set("")
        self._compare_load_file(side, 0)
        self._sync_compare_partner(side, 0)
        messagebox.showinfo(
            f"{'좌측' if side == 'left' else '우측'} 비교 폴더 열기",
            self._build_quick_folder_message(folder, candidate_paths, excluded),
        )

    def _compare_load_file(self, side: str, index: int, preserve_view_state: bool = False) -> None:
        panel = self._get_compare_panel(side)
        file_paths = panel["file_paths"]
        if not 0 <= index < len(file_paths):
            return

        preserved_zoom = None
        preserved_center_ratio = None
        if preserve_view_state and panel["frames"]:
            preserved_zoom = float(np.clip(panel["zoom_scale"], self.min_zoom_scale, self.max_zoom_scale))
            preserved_center_ratio = self._compare_capture_view_center_ratio(panel)

        path = file_paths[index]
        try:
            dataset, frames = self.dicom_loader.get_decoded_file(path)
        except Exception as exc:
            messagebox.showerror("열기 실패", f"파일을 읽는 중 오류가 발생했습니다.\n\n{path}\n\n{exc}")
            return

        panel["dataset"] = dataset
        panel["frames"] = frames
        panel["current_file_index"] = index
        panel["current_frame"] = 0
        self._compare_initialize_window_level(panel, dataset, frames)
        if preserve_view_state and preserved_zoom is not None:
            panel["zoom_scale"] = preserved_zoom
        else:
            self._compare_initialize_zoom(panel, frames[0] if frames else None)
        self._metadata_cache[path] = dataset
        panel["path_var"].set(path)
        panel["info_var"].set(self._build_status_summary(dataset, frames))
        panel["image_var"].set(f"이미지: {index + 1} / {len(file_paths)}")
        panel["overlay_values"] = self._collect_overlay_values(dataset)
        self._update_compare_panel_position_label(panel)
        self._compare_show_frame(
            side,
            center_view=not preserve_view_state,
            preserve_center_ratio=preserved_center_ratio,
        )

    def _get_compare_partner_side(self, side: str) -> str:
        return "right" if side == "left" else "left"

    def _get_compare_synced_index(self, source_side: str, requested_index: int) -> int | None:
        if self.compare_sync_mode != "index":
            return None
        partner = self._get_compare_panel(self._get_compare_partner_side(source_side))
        if not partner["file_paths"]:
            return None
        return min(max(requested_index, 0), len(partner["file_paths"]) - 1)

    def _sync_compare_partner(self, source_side: str, requested_index: int) -> None:
        if self.view_mode != "compare" or not self.compare_sync_enabled.get():
            return
        target_index = self._get_compare_synced_index(source_side, requested_index)
        if target_index is None:
            return
        partner_side = self._get_compare_partner_side(source_side)
        partner = self._get_compare_panel(partner_side)
        if target_index != requested_index:
            partner["sync_note_var"].set(
                f"Index Sync 보정 적용: 요청 {requested_index + 1} -> 표시 {target_index + 1}"
            )
        else:
            partner["sync_note_var"].set("Index Sync 적용 중")
        if partner["current_file_index"] == target_index and partner["frames"]:
            return
        self._compare_load_file(partner_side, target_index, preserve_view_state=True)

    def _compare_initialize_window_level(self, panel: dict[str, Any], dataset, frames: list[np.ndarray]) -> None:
        if not frames:
            panel["window_width_value"] = None
            panel["window_level_value"] = None
            panel["default_window_width"] = None
            panel["default_window_level"] = None
            panel["window_level_range"] = (0.0, 1.0)
            panel["window_level_var"].set("W/L: - / -")
            return

        frame_min, frame_max = self._get_frame_value_range(frames)
        dynamic_range = max(frame_max - frame_min, 1.0)
        panel["window_level_range"] = (frame_min, frame_max)

        if self._supports_window_level(frames[0]):
            center = self._get_window_center_from_dataset(dataset)
            width = self._get_window_width_from_dataset(dataset)
            if center is None:
                center = (frame_min + frame_max) / 2.0
            if width is None or width <= 1:
                width = dynamic_range

            panel["default_window_level"] = float(np.clip(center, frame_min - dynamic_range, frame_max + dynamic_range))
            panel["default_window_width"] = float(np.clip(width, 1.0, dynamic_range * 16.0))
            panel["window_level_value"] = panel["default_window_level"]
            panel["window_width_value"] = panel["default_window_width"]
        else:
            panel["default_window_level"] = None
            panel["default_window_width"] = None
            panel["window_level_value"] = None
            panel["window_width_value"] = None

        self._compare_update_window_level_label(panel)

    def _compare_update_window_level_label(self, panel: dict[str, Any]) -> None:
        if panel["window_width_value"] is None or panel["window_level_value"] is None:
            panel["window_level_var"].set("W/L: RGB 또는 자동 조절 없음")
            return
        panel["window_level_var"].set(
            f"W/L: {panel['window_width_value']:.1f} / {panel['window_level_value']:.1f}"
        )

    def _compare_change_file(self, side: str, delta: int) -> None:
        panel = self._get_compare_panel(side)
        if not panel["file_paths"]:
            return
        new_index = panel["current_file_index"] + delta
        if not 0 <= new_index < len(panel["file_paths"]):
            return
        panel["sync_note_var"].set("")
        self._compare_load_file(side, new_index, preserve_view_state=True)
        self._sync_compare_partner(side, new_index)

    def swap_compare_panels(self) -> None:
        if self.view_mode != "compare":
            return
        left = self.left_view_state
        right = self.right_view_state
        swap_keys = [
            "file_paths",
            "current_file_index",
            "current_folder_path",
            "dataset",
            "frames",
            "current_frame",
            "photo_image",
            "zoom_scale",
            "window_width_value",
            "window_level_value",
            "default_window_width",
            "default_window_level",
            "window_level_range",
            "window_drag_origin",
            "window_drag_base",
            "overlay_values",
        ]
        snapshot = {key: left[key] for key in swap_keys}
        for key in swap_keys:
            left[key] = right[key]
        for key, value in snapshot.items():
            right[key] = value

        for panel in (left, right):
            panel["sync_note_var"].set("")
            self._update_compare_panel_position_label(panel)
            if panel["file_paths"] and 0 <= panel["current_file_index"] < len(panel["file_paths"]):
                current_path = panel["file_paths"][panel["current_file_index"]]
                panel["path_var"].set(current_path)
                if panel["dataset"] is not None:
                    panel["info_var"].set(self._build_status_summary(panel["dataset"], panel["frames"]))
                panel["image_var"].set(f"이미지: {panel['current_file_index'] + 1} / {len(panel['file_paths'])}")
                if panel["frames"]:
                    panel["frame_var"].set(f"프레임: {panel['current_frame'] + 1} / {len(panel['frames'])}")
                    self._compare_update_window_level_label(panel)
                    self._compare_show_frame(panel["side"], preserve_center_ratio=self._compare_capture_view_center_ratio(panel))
                else:
                    panel["canvas"].delete("all")
            else:
                panel["path_var"].set("폴더를 열어 비교 대상을 선택해 주세요.")
                panel["info_var"].set("비교용 폴더를 열면 현재 선택 영상 요약이 표시됩니다.")
                panel["image_var"].set("이미지: - / -")
                panel["frame_var"].set("프레임: - / -")
                panel["zoom_var"].set("Zoom: -")
                panel["window_level_var"].set("W/L: - / -")
                panel["compare_index_var"].set(f"{'Left' if panel['side'] == 'left' else 'Right'} - / -")
                panel["canvas"].delete("all")

    def _compare_change_frame(self, side: str, delta: int) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"]:
            return
        new_index = panel["current_frame"] + delta
        if not 0 <= new_index < len(panel["frames"]):
            return
        panel["current_frame"] = new_index
        self._compare_show_frame(side)

    def _compare_show_frame(
        self,
        side: str,
        center_view: bool = False,
        preserve_center_ratio: tuple[float, float] | None = None,
    ) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"]:
            return
        frame = panel["frames"][panel["current_frame"]]
        center_ratio = preserve_center_ratio
        if center_ratio is None:
            center_ratio = self._compare_capture_view_center_ratio(panel)
        panel["photo_image"] = self._compare_frame_to_photoimage(panel, frame)
        canvas = panel["canvas"]
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        content_width = max(canvas_width, panel["photo_image"].width())
        content_height = max(canvas_height, panel["photo_image"].height())
        center_x = content_width / 2
        center_y = content_height / 2

        canvas.delete("all")
        canvas.create_image(center_x, center_y, image=panel["photo_image"], anchor="center")
        canvas.config(scrollregion=(0, 0, content_width, content_height))
        if center_view:
            self._compare_center_view_for_content(panel, content_width, content_height)
        else:
            self._compare_restore_view_center_ratio(panel, center_ratio)
        self._draw_compare_overlays(panel)
        panel["frame_var"].set(f"프레임: {panel['current_frame'] + 1} / {len(panel['frames'])}")
        panel["zoom_var"].set(f"Zoom: {panel['zoom_scale'] * 100:.0f}%")

    def _compare_frame_to_photoimage(self, panel: dict[str, Any], frame: np.ndarray) -> ImageTk.PhotoImage:
        normalized = self._normalize_frame_for_dataset(
            dataset=panel["dataset"],
            frame=frame,
            window_width=panel["window_width_value"],
            window_level=panel["window_level_value"],
        )
        image = Image.fromarray(normalized)
        resized = self._compare_resize_image_for_display(panel, image)
        return ImageTk.PhotoImage(resized)

    def _compare_resize_image_for_display(self, panel: dict[str, Any], image: Image.Image) -> Image.Image:
        scale = self._compare_get_effective_zoom_scale(panel, image)
        if scale == 1.0:
            return image

        width, height = image.size
        resized_width = max(int(round(width * scale)), 1)
        resized_height = max(int(round(height * scale)), 1)
        resample = Image.Resampling.LANCZOS if scale < 1.0 else Image.Resampling.BICUBIC
        return image.resize((resized_width, resized_height), resample)

    def _compare_initialize_zoom(self, panel: dict[str, Any], frame: np.ndarray | None) -> None:
        if frame is None:
            panel["zoom_scale"] = 1.0
            panel["zoom_var"].set("Zoom: -")
            return
        frame_array = np.asarray(frame)
        if frame_array.ndim == 2:
            height, width = frame_array.shape
        elif frame_array.ndim == 3:
            height, width = frame_array.shape[:2]
        else:
            panel["zoom_scale"] = 1.0
            panel["zoom_var"].set("Zoom: -")
            return
        panel["zoom_scale"] = self._compare_calculate_fit_scale(panel, width, height)
        panel["zoom_var"].set(f"Zoom: {panel['zoom_scale'] * 100:.0f}%")

    def _compare_calculate_fit_scale(self, panel: dict[str, Any], width: int, height: int) -> float:
        canvas = panel["canvas"]
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return 1.0
        return min(canvas_width / width, canvas_height / height, 1.0)

    def _compare_get_effective_zoom_scale(self, panel: dict[str, Any], image: Image.Image) -> float:
        fit_scale = self._compare_calculate_fit_scale(panel, *image.size)
        if panel["zoom_scale"] <= 0:
            panel["zoom_scale"] = fit_scale
        return float(np.clip(panel["zoom_scale"], self.min_zoom_scale, self.max_zoom_scale))

    def _compare_fit_to_window(self, side: str) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"]:
            return
        frame = np.asarray(panel["frames"][panel["current_frame"]])
        if frame.ndim == 2:
            height, width = frame.shape
        elif frame.ndim == 3:
            height, width = frame.shape[:2]
        else:
            return
        panel["zoom_scale"] = self._compare_calculate_fit_scale(panel, width, height)
        self._compare_show_frame(side, center_view=True)

    def _compare_reset_zoom_to_actual_size(self, side: str) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"]:
            return
        panel["zoom_scale"] = 1.0
        self._compare_show_frame(side, center_view=True)

    def _compare_reset_window_level(self, side: str) -> None:
        panel = self._get_compare_panel(side)
        if panel["default_window_width"] is None or panel["default_window_level"] is None:
            return
        panel["window_width_value"] = panel["default_window_width"]
        panel["window_level_value"] = panel["default_window_level"]
        self._compare_update_window_level_label(panel)
        if panel["frames"]:
            self._compare_show_frame(side)

    def _compare_on_canvas_resize(self, side: str, event: tk.Event) -> None:
        panel = self._get_compare_panel(side)
        canvas_size = (event.width, event.height)
        if canvas_size == panel["last_canvas_size"]:
            return
        center_ratio = self._compare_capture_view_center_ratio(panel)
        panel["last_canvas_size"] = canvas_size
        if panel["frames"] and event.width > 1 and event.height > 1:
            self._compare_show_frame(side)
            self._compare_restore_view_center_ratio(panel, center_ratio)

    def _compare_start_pan(self, side: str, event: tk.Event) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"]:
            return
        panel["canvas"].scan_mark(event.x, event.y)

    def _compare_update_pan(self, side: str, event: tk.Event) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"]:
            return
        panel["canvas"].scan_dragto(event.x, event.y, gain=1)
        self._draw_compare_overlays(panel)

    def _compare_end_pan(self, side: str, _event: tk.Event) -> None:
        panel = self._get_compare_panel(side)
        if panel["frames"]:
            self._draw_compare_overlays(panel)

    def _compare_start_window_level_drag(self, side: str, event: tk.Event) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"] or panel["window_width_value"] is None or panel["window_level_value"] is None:
            return
        panel["window_drag_origin"] = (event.x, event.y)
        panel["window_drag_base"] = (panel["window_width_value"], panel["window_level_value"])

    def _compare_update_window_level_drag(self, side: str, event: tk.Event) -> None:
        panel = self._get_compare_panel(side)
        if panel["window_drag_origin"] is None or panel["window_drag_base"] is None:
            return
        start_x, start_y = panel["window_drag_origin"]
        base_width, base_level = panel["window_drag_base"]
        frame_min, frame_max = panel["window_level_range"]
        dynamic_range = max(frame_max - frame_min, 1.0)
        width_delta = (event.x - start_x) * max(dynamic_range / 256.0, 1.0)
        level_delta = (start_y - event.y) * max(dynamic_range / 256.0, 1.0)
        panel["window_width_value"] = float(np.clip(base_width + width_delta, 1.0, dynamic_range * 16.0))
        panel["window_level_value"] = float(
            np.clip(base_level + level_delta, frame_min - dynamic_range * 8.0, frame_max + dynamic_range * 8.0)
        )
        self._compare_update_window_level_label(panel)
        self._compare_show_frame(side)

    def _compare_end_window_level_drag(self, side: str, _event: tk.Event) -> None:
        panel = self._get_compare_panel(side)
        panel["window_drag_origin"] = None
        panel["window_drag_base"] = None

    def _compare_handle_mousewheel(self, side: str, event: tk.Event) -> str:
        direction = self._get_mousewheel_direction(event)
        if direction == 0:
            return "break"
        if self._is_ctrl_pressed(event):
            self._compare_zoom_with_mousewheel(side, direction)
        else:
            self._compare_change_file(side, direction)
        return "break"

    def _compare_zoom_with_mousewheel(self, side: str, direction: int) -> None:
        panel = self._get_compare_panel(side)
        if not panel["frames"]:
            return
        center_ratio = self._compare_capture_view_center_ratio(panel)
        zoom_step = 1.15
        if direction < 0:
            panel["zoom_scale"] *= zoom_step
        else:
            panel["zoom_scale"] /= zoom_step
        panel["zoom_scale"] = float(np.clip(panel["zoom_scale"], self.min_zoom_scale, self.max_zoom_scale))
        self._compare_show_frame(side)
        self._compare_restore_view_center_ratio(panel, center_ratio)

    def _compare_capture_view_center_ratio(self, panel: dict[str, Any]) -> tuple[float, float]:
        canvas = panel["canvas"]
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        bbox = canvas.bbox("all")
        content_width = max(bbox[2] if bbox else canvas_width, 1)
        content_height = max(bbox[3] if bbox else canvas_height, 1)
        center_x = canvas.canvasx(canvas_width / 2)
        center_y = canvas.canvasy(canvas_height / 2)
        return center_x / content_width, center_y / content_height

    def _compare_restore_view_center_ratio(self, panel: dict[str, Any], center_ratio: tuple[float, float]) -> None:
        center_x_ratio, center_y_ratio = center_ratio
        canvas = panel["canvas"]
        bbox = canvas.bbox("all")
        content_width = max(bbox[2] if bbox else canvas.winfo_width(), 1)
        content_height = max(bbox[3] if bbox else canvas.winfo_height(), 1)
        self._compare_set_view_center(panel, center_x_ratio * content_width, center_y_ratio * content_height)

    def _compare_set_view_center(self, panel: dict[str, Any], center_x: float, center_y: float) -> None:
        canvas = panel["canvas"]
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        bbox = canvas.bbox("all")
        content_width = max(bbox[2] if bbox else canvas_width, canvas_width, 1)
        content_height = max(bbox[3] if bbox else canvas_height, canvas_height, 1)
        x_offset = max(center_x - canvas_width / 2, 0.0)
        y_offset = max(center_y - canvas_height / 2, 0.0)
        max_x_offset = max(content_width - canvas_width, 0.0)
        max_y_offset = max(content_height - canvas_height, 0.0)
        x_offset = min(x_offset, max_x_offset)
        y_offset = min(y_offset, max_y_offset)
        canvas.xview_moveto(0.0 if content_width <= canvas_width else x_offset / content_width)
        canvas.yview_moveto(0.0 if content_height <= canvas_height else y_offset / content_height)

    def _compare_center_view_for_content(self, panel: dict[str, Any], content_width: float, content_height: float) -> None:
        self._compare_set_view_center(panel, content_width / 2, content_height / 2)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="DICOM 파일 선택",
            filetypes=[
                ("DICOM 파일", "*.dcm *.DCM"),
                ("모든 파일", "*.*"),
            ],
        )
        if not path:
            return
        keep_multiview = self.view_mode == "multi"
        self._reset_file_list_state()
        self._set_loaded_paths([path], folder=None)
        self._load_file(0)
        if not self._can_use_multiview():
            self.enter_single_view_mode(load_selected=False)
        if keep_multiview and self._can_use_multiview():
            self.enter_multiview_mode()

    def open_folder(self) -> None:
        folder = filedialog.askdirectory(title="DICOM 폴더 선택")
        if not folder:
            return

        candidate_paths, excluded = self._collect_folder_candidates(folder)
        if not candidate_paths:
            messagebox.showwarning(
                "표시 가능한 DICOM 없음",
                self._build_quick_folder_message(folder, candidate_paths, excluded),
            )
            return

        keep_multiview = self.view_mode == "multi"
        self._reset_file_list_state()
        self._set_loaded_paths(candidate_paths, folder=folder)
        self._load_file(0)
        if keep_multiview:
            self.enter_multiview_mode()

        messagebox.showinfo(
            "폴더 열기 결과",
            self._build_quick_folder_message(folder, candidate_paths, excluded),
        )

    def diagnose_folder(self) -> None:
        folder = filedialog.askdirectory(title="진단할 폴더 선택")
        if not folder:
            return

        diagnosis = self._diagnose_folder_contents(folder)
        self._show_diagnosis_window(folder, diagnosis)

        if diagnosis["normal_dicom"]:
            keep_multiview = self.view_mode == "multi"
            self._reset_file_list_state()
            self._set_loaded_paths(diagnosis["normal_dicom"], folder=folder)
            self.current_file_index = -1
            self._load_file(0)
            if keep_multiview:
                self.enter_multiview_mode()

    def _reset_file_list_state(self) -> None:
        self.file_paths = []
        self.current_file_index = -1
        self.current_folder_path = None
        self.loaded_from_folder = False
        self.dicom_loader.clear_cache()
        self._metadata_cache = {}
        self._clear_multiview_thumbnail_cache()
        self.multiview_info_cache = {}
        self.multiview_tile_meta_cache = {}
        self.multiview_tile_images = []
        self.multiview_page = 0
        self.window_width_value = None
        self.window_level_value = None
        self.default_window_width = None
        self.default_window_level = None
        self.window_level_range = (0.0, 1.0)
        self._window_drag_origin = None
        self._window_drag_base = None
        self.zoom_scale = 1.0
        self._zoom_limit_notice = None
        self.zoom_var.set("Zoom: -")
        self.window_level_var.set("W/L: - / -")
        self.multiview_page_var.set("페이지: - / -")
        self.path_var.set("")
        self.info_var.set("")
        self.cursor_var.set("Cursor: -, -")
        for field in self.overlay_field_definitions:
            self.current_overlay_values[field["key"]] = "N/A"
        self.canvas.delete("overlay")
        self.canvas.delete("grid_overlay")
        self.clear_preview_overlay()
        self.cancel_crop_mode()
        self._image_bbox = None
        self.close_multiview_grid_selector()
        self._update_multiview_controls()

    def _collect_folder_candidates(self, folder: str) -> tuple[list[str], dict[str, str]]:
        candidates = []
        excluded = {}

        for path in self._iter_folder_files(folder):
            reason = self._get_quick_scan_exclusion_reason(path)
            if reason is None:
                candidates.append(path)
            else:
                excluded[path] = reason

        return candidates, excluded

    def _get_quick_scan_exclusion_reason(self, path: str) -> str | None:
        try:
            dataset = pydicom.dcmread(path, stop_before_pixels=True)
        except InvalidDicomError:
            return "DICOM 형식이 아닌 파일입니다."
        except Exception as exc:
            return f"DICOM 메타데이터를 읽지 못했습니다: {exc}"

        image_candidate_reason = self._get_non_image_dicom_reason(dataset, path)
        if image_candidate_reason is not None:
            return image_candidate_reason

        return None

    def _get_non_image_dicom_reason(self, dataset, path: str) -> str | None:
        sop_class_uid = str(getattr(dataset, "SOPClassUID", ""))
        if sop_class_uid == "1.2.840.10008.1.3.10":
            return "DICOMDIR 디렉터리 객체입니다."

        filename = Path(path).name.upper()
        if filename == "DICOMDIR":
            return "DICOMDIR 디렉터리 객체입니다."

        has_rows = hasattr(dataset, "Rows")
        has_columns = hasattr(dataset, "Columns")
        has_photometric = hasattr(dataset, "PhotometricInterpretation")
        if has_rows and has_columns:
            return None
        if has_photometric:
            return None

        modality = str(getattr(dataset, "Modality", "")).upper()
        if modality in {"OT", "DOC", "KO", "PR", "SR"}:
            return f"영상 표시 대상이 아닌 DICOM 객체입니다. Modality: {modality or 'Unknown'}"

        return "영상 DICOM 후보로 판단할 수 있는 기본 태그가 없습니다."

    def _diagnose_folder_contents(self, folder: str) -> dict[str, list[str]]:
        result = {
            "normal_dicom": [],
            "non_dicom": [],
            "no_pixel_data": [],
            "compressed_dicom": [],
            "compressed_unsupported": [],
            "multiframe_dicom": [],
            "display_failures": [],
            "compressed_details": {},
            "excluded_reasons": {},
        }

        for path in self._iter_folder_files(folder):
            metadata_dataset = None
            metadata_error = None
            try:
                metadata_dataset = pydicom.dcmread(path, stop_before_pixels=True)
            except InvalidDicomError as exc:
                metadata_error = "DICOM 형식이 아닌 파일입니다."
            except Exception as exc:
                metadata_error = f"DICOM 메타데이터를 읽지 못했습니다: {exc}"

            if metadata_error is not None:
                self._record_excluded_file(result, "non_dicom", path, metadata_error)
                continue

            transfer_syntax = self.dicom_loader.get_transfer_syntax(metadata_dataset)
            is_compressed = bool(getattr(transfer_syntax, "is_compressed", False)) if transfer_syntax else False
            if is_compressed:
                result["compressed_dicom"].append(path)
                result["compressed_details"][path] = self._build_compressed_detail(metadata_dataset, displayable=False)

            frame_count = self._get_number_of_frames(metadata_dataset)
            if frame_count > 1:
                result["multiframe_dicom"].append(path)

            try:
                display_dataset, _ = self.dicom_loader.get_decoded_file(path)
            except ValueError as exc:
                category = self._categorize_display_failure(str(exc), transfer_syntax)
                self._record_excluded_file(result, category, path, str(exc))
                continue

            if is_compressed:
                result["compressed_details"][path] = self._build_compressed_detail(
                    display_dataset,
                    displayable=True,
                )
            result["normal_dicom"].append(path)

        return result

    def _build_quick_folder_message(
        self,
        folder: str,
        candidate_paths: list[str],
        excluded: dict[str, str],
    ) -> str:
        lines = [
            f"폴더: {folder}",
            f"탐색 목록 등록: {len(candidate_paths)}개",
            f"빠른 제외: {len(excluded)}개",
            "",
            "등록된 파일:",
            self._build_name_block(candidate_paths),
            "",
            "제외된 파일:",
            self._build_excluded_name_block(excluded),
            "",
            "상세 검증이 필요하면 `폴더 진단`을 사용해 주세요.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _iter_folder_files(folder: str) -> list[str]:
        return [
            str(path)
            for path in sorted(Path(folder).iterdir(), key=lambda item: item.name.lower())
            if path.is_file()
        ]

    @staticmethod
    def _get_number_of_frames(dataset) -> int:
        value = getattr(dataset, "NumberOfFrames", 1)
        try:
            return max(int(value), 1)
        except (TypeError, ValueError):
            return 1

    def _build_compressed_detail(self, dataset, displayable: bool) -> dict[str, str]:
        transfer_syntax = self.dicom_loader.get_transfer_syntax(dataset)
        is_compressed = bool(getattr(transfer_syntax, "is_compressed", False)) if transfer_syntax else False
        decoder_available = self.dicom_loader.has_transfer_syntax_handler(transfer_syntax) if transfer_syntax else True
        return {
            "transfer_syntax_uid": str(transfer_syntax) if transfer_syntax else "Unknown",
            "is_compressed": "예" if is_compressed else "아니오",
            "decoder_available": "예" if decoder_available else "아니오",
            "displayable": "예" if displayable else "아니오",
        }

    def _build_folder_summary(self, diagnosis: dict[str, list[str]]) -> str:
        return (
            f"표시 가능한 일반 DICOM: {len(diagnosis['normal_dicom'])}\n"
            f"비DICOM 또는 손상된 파일: {len(diagnosis['non_dicom'])}\n"
            f"Pixel Data가 없는 DICOM: {len(diagnosis['no_pixel_data'])}\n"
            f"표시 단계 실패: {len(diagnosis['display_failures'])}\n"
            f"압축 DICOM(Pixel Data 있음): {len(diagnosis['compressed_dicom'])}\n"
            f"디코더가 없는 압축 DICOM: {len(diagnosis['compressed_unsupported'])}\n"
            f"멀티프레임 DICOM: {len(diagnosis['multiframe_dicom'])}"
        )

    def _build_folder_load_message(self, diagnosis: dict[str, list[str]], has_loadable: bool) -> str:
        if not has_loadable:
            return (
                "선택한 폴더에서 화면에 표시할 수 있는 일반 DICOM 이미지를 찾지 못했습니다.\n\n"
                f"{self._build_folder_summary(diagnosis)}\n\n"
                f"정상 목록:\n{self._build_name_block(diagnosis['normal_dicom'])}\n\n"
                f"제외 목록:\n{self._build_excluded_block(diagnosis)}\n\n"
                "압축 DICOM만 있는 경우에는 필요한 픽셀 디코더를 설치한 뒤 다시 시도해 주세요."
            )

        return (
            f"정상 DICOM {len(diagnosis['normal_dicom'])}개만 불러와서 표시합니다.\n"
            f"정상 목록:\n{self._build_name_block(diagnosis['normal_dicom'])}\n\n"
            f"제외 목록:\n{self._build_excluded_block(diagnosis)}\n\n"
            f"{self._build_folder_summary(diagnosis)}"
        )

    def _show_diagnosis_window(self, folder: str, diagnosis: dict[str, list[str]]) -> None:
        window = tk.Toplevel(self.root)
        window.title("폴더 진단 결과")
        window.geometry("1120x760")

        container = ttk.Frame(window, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="폴더 진단 결과").grid(row=0, column=0, sticky="w")
        ttk.Button(
            header,
            text="결과 저장",
            command=lambda: self._save_diagnosis_report(folder, diagnosis),
        ).grid(row=0, column=1, sticky="e")

        ttk.Label(header, text=f"폴더: {folder}", justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        summary_frame = ttk.LabelFrame(container, text="요약", padding=10)
        summary_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self._populate_summary_grid(summary_frame, diagnosis)

        text_frame = ttk.LabelFrame(container, text="상세 파일 목록", padding=10)
        text_frame.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        text = tk.Text(text_frame, wrap="none")
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        h_scrollbar = ttk.Scrollbar(text_frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=scrollbar.set, xscrollcommand=h_scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        text.insert("1.0", self._build_diagnosis_report(folder, diagnosis, include_names=True))
        text.configure(state="disabled")

    def _populate_summary_grid(self, parent: ttk.LabelFrame, diagnosis: dict[str, list[str]]) -> None:
        entries = [
            ("일반 DICOM", len(diagnosis["normal_dicom"])),
            ("비DICOM/손상", len(diagnosis["non_dicom"])),
            ("Pixel Data 없음", len(diagnosis["no_pixel_data"])),
            ("표시 실패", len(diagnosis["display_failures"])),
            ("압축 DICOM", len(diagnosis["compressed_dicom"])),
            ("디코더 없음", len(diagnosis["compressed_unsupported"])),
            ("멀티프레임", len(diagnosis["multiframe_dicom"])),
        ]
        for column in range(4):
            parent.columnconfigure(column, weight=1)

        for index, (label, count) in enumerate(entries):
            row = index // 4
            column = index % 4
            card = ttk.Frame(parent, padding=8, relief="ridge")
            card.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
            ttk.Label(card, text=label).pack(anchor="w")
            ttk.Label(card, text=str(count)).pack(anchor="w", pady=(4, 0))

        message = self._build_diagnosis_guidance(diagnosis)
        ttk.Label(parent, text=message, justify="left").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(10, 0)
        )

    def _build_diagnosis_guidance(self, diagnosis: dict[str, list[str]]) -> str:
        normal_count = len(diagnosis["normal_dicom"])
        if normal_count == 0:
            return (
                "안내: 현재 폴더에는 즉시 표시 가능한 일반 DICOM이 없습니다. "
                "압축 DICOM은 디코더 가능 여부뿐 아니라 실제 픽셀 디코딩 성공 여부까지 확인해서 분류합니다."
            )

        excluded_count = (
            len(diagnosis["non_dicom"])
            + len(diagnosis["no_pixel_data"])
            + len(diagnosis["compressed_unsupported"])
            + len(diagnosis["display_failures"])
        )
        if excluded_count > 0:
            return (
                f"안내: 일반 DICOM {normal_count}개는 바로 표시할 수 있고, "
                f"제외된 파일 {excluded_count}개는 원인을 확인한 뒤 다시 점검할 수 있습니다."
            )

        return "안내: 이 폴더의 파일은 모두 표시 가능한 일반 DICOM 기준을 만족합니다."

    def _build_diagnosis_report(
        self,
        folder: str,
        diagnosis: dict[str, list[str]],
        include_names: bool = False,
    ) -> str:
        lines = [
            f"일반 DICOM: {len(diagnosis['normal_dicom'])}",
            f"비DICOM 또는 손상된 파일: {len(diagnosis['non_dicom'])}",
            f"Pixel Data가 없는 DICOM: {len(diagnosis['no_pixel_data'])}",
            f"표시 단계 실패: {len(diagnosis['display_failures'])}",
            f"압축 DICOM(Pixel Data 있음): {len(diagnosis['compressed_dicom'])}",
            f"디코더가 없는 압축 DICOM: {len(diagnosis['compressed_unsupported'])}",
            f"멀티프레임 DICOM: {len(diagnosis['multiframe_dicom'])}",
        ]

        if not include_names:
            return "\n".join(lines)

        sections = []
        category_order = [
            ("normal_dicom", "일반 DICOM"),
            ("non_dicom", "비DICOM 또는 손상된 파일"),
            ("no_pixel_data", "Pixel Data가 없는 DICOM"),
            ("display_failures", "표시 단계 실패"),
            ("compressed_dicom", "압축 DICOM(Pixel Data 있음)"),
            ("compressed_unsupported", "디코더가 없는 압축 DICOM"),
            ("multiframe_dicom", "멀티프레임 DICOM"),
        ]
        sections.append(f"폴더: {folder}")
        sections.append("")
        sections.extend(lines)
        for key, title in category_order:
            sections.append("")
            sections.append(f"[{title}] {len(diagnosis[key])}개")
            if diagnosis[key]:
                sections.extend(self._build_category_lines(folder, diagnosis, key))
            else:
                sections.append(" -")
        return "\n".join(sections)

    def _build_category_lines(
        self,
        folder: str,
        diagnosis: dict[str, list[str]],
        key: str,
    ) -> list[str]:
        lines = []
        for path in diagnosis[key]:
            relative_path = self._format_relative_path(folder, path)
            detail = self._format_diagnosis_detail(diagnosis, key, path)
            if detail:
                lines.append(f" - {relative_path} | {detail}")
            else:
                lines.append(f" - {relative_path}")
        return lines

    def _format_diagnosis_detail(
        self,
        diagnosis: dict[str, list[str]],
        key: str,
        path: str,
    ) -> str:
        if key in {"non_dicom", "no_pixel_data", "display_failures", "compressed_unsupported"}:
            reason = diagnosis["excluded_reasons"].get(path)
            if not reason:
                return ""
            if key == "compressed_unsupported":
                detail = diagnosis["compressed_details"].get(path)
                if detail:
                    return (
                        f"{reason} | Transfer Syntax UID={detail['transfer_syntax_uid']}, "
                        f"압축={detail['is_compressed']}, 디코더 가능={detail['decoder_available']}"
                    )
            return reason

        if key != "compressed_dicom":
            return ""

        detail = diagnosis["compressed_details"].get(path)
        if not detail:
            return ""

        return (
            f"Transfer Syntax UID={detail['transfer_syntax_uid']}, "
            f"압축={detail['is_compressed']}, "
            f"디코더 가능={detail['decoder_available']}, "
            f"표시 가능={detail['displayable']}"
        )

    @staticmethod
    def _record_excluded_file(
        diagnosis: dict[str, list[str]],
        category: str,
        path: str,
        reason: str,
    ) -> None:
        diagnosis[category].append(path)
        diagnosis["excluded_reasons"][path] = reason

    def _categorize_display_failure(self, reason: str, transfer_syntax) -> str:
        if "DICOM 형식이 아닌 파일" in reason or "DICOM 파일을 읽지 못했습니다." in reason:
            return "non_dicom"
        if "Pixel Data가 없는 DICOM 파일" in reason:
            return "no_pixel_data"
        if "전송구문을 해제할 수 있는 픽셀 디코더가 없습니다" in reason:
            if transfer_syntax is not None and not self.dicom_loader.has_transfer_syntax_handler(transfer_syntax):
                return "compressed_unsupported"
        return "display_failures"

    def _build_name_block(self, paths: list[str], limit: int = 20) -> str:
        if not paths:
            return " -"
        lines = [f" - {Path(path).name}" for path in paths[:limit]]
        if len(paths) > limit:
            lines.append(f" - ... 외 {len(paths) - limit}개")
        return "\n".join(lines)

    def _build_excluded_block(self, diagnosis: dict[str, list[str]], limit: int = 20) -> str:
        excluded_paths = (
            diagnosis["non_dicom"]
            + diagnosis["no_pixel_data"]
            + diagnosis["compressed_unsupported"]
            + diagnosis["display_failures"]
        )
        if not excluded_paths:
            return " - 제외된 파일 없음"

        lines = []
        for path in excluded_paths[:limit]:
            reason = diagnosis["excluded_reasons"].get(path, "이유 정보 없음")
            lines.append(f" - {Path(path).name}: {reason}")
        if len(excluded_paths) > limit:
            lines.append(f" - ... 외 {len(excluded_paths) - limit}개")
        return "\n".join(lines)

    def _build_excluded_name_block(self, excluded: dict[str, str], limit: int = 20) -> str:
        if not excluded:
            return " - 제외된 파일 없음"

        lines = []
        items = list(excluded.items())
        for path, reason in items[:limit]:
            lines.append(f" - {Path(path).name}: {reason}")
        if len(items) > limit:
            lines.append(f" - ... 외 {len(items) - limit}개")
        return "\n".join(lines)

    def _save_diagnosis_report(self, folder: str, diagnosis: dict[str, list[str]]) -> None:
        default_name = f"dicom_diagnosis_{Path(folder).name or 'folder'}.txt"
        path = filedialog.asksaveasfilename(
            title="진단 결과 저장",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
        )
        if not path:
            return

        report = self._build_diagnosis_report(folder, diagnosis, include_names=True)
        try:
            Path(path).write_text(report, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("저장 실패", f"진단 결과를 저장하지 못했습니다.\n\n{exc}")
            return

        messagebox.showinfo("저장 완료", f"진단 결과를 저장했습니다.\n\n{path}")

    @staticmethod
    def _format_relative_path(folder: str, path: str) -> str:
        base = Path(folder)
        try:
            return str(Path(path).relative_to(base))
        except ValueError:
            return path

    def _load_file(self, index: int, preserve_view_state: bool = False) -> None:
        if not 0 <= index < len(self.file_paths):
            return

        preserved_zoom = None
        preserved_center_ratio = None
        if preserve_view_state and self.frames:
            preserved_zoom = float(np.clip(self.zoom_scale, self.min_zoom_scale, self.max_zoom_scale))
            preserved_center_ratio = self._capture_view_center_ratio()

        path = self.file_paths[index]
        try:
            dataset, frames = self.dicom_loader.get_decoded_file(path)
        except Exception as exc:
            messagebox.showerror("열기 실패", f"파일을 읽는 중 오류가 발생했습니다.\n\n{path}\n\n{exc}")
            return

        self.dataset = dataset
        self.frames = frames
        self.current_file_index = index
        self.current_frame = 0
        self._update_grid_cell_size_label()
        self.clear_preview_overlay()
        self._initialize_window_level(dataset, frames)
        if preserve_view_state and preserved_zoom is not None:
            self.zoom_scale = preserved_zoom
            self._zoom_limit_notice = None
        else:
            self._initialize_zoom(frames[0] if frames else None)
        self._metadata_cache[path] = dataset
        self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")
        self._update_overlay_data_for_dataset(dataset, path, frames)
        self._show_frame(
            center_view=not preserve_view_state,
            preserve_center_ratio=preserved_center_ratio,
        )

    def _initialize_window_level(self, dataset, frames: list[np.ndarray]) -> None:
        if not frames:
            self.window_width_value = None
            self.window_level_value = None
            self.default_window_width = None
            self.default_window_level = None
            self.window_level_range = (0.0, 1.0)
            self.window_level_var.set("W/L: - / -")
            return

        frame_min, frame_max = self._get_frame_value_range(frames)
        dynamic_range = max(frame_max - frame_min, 1.0)
        self.window_level_range = (frame_min, frame_max)

        if self._supports_window_level(frames[0]):
            center = self._get_window_center_from_dataset(dataset)
            width = self._get_window_width_from_dataset(dataset)
            if center is None:
                center = (frame_min + frame_max) / 2.0
            if width is None or width <= 1:
                width = dynamic_range

            self.default_window_level = float(np.clip(center, frame_min - dynamic_range, frame_max + dynamic_range))
            self.default_window_width = float(np.clip(width, 1.0, dynamic_range * 16.0))
            self.window_level_value = self.default_window_level
            self.window_width_value = self.default_window_width
        else:
            self.default_window_level = None
            self.default_window_width = None
            self.window_level_value = None
            self.window_width_value = None

        self._update_window_level_label()

    def _get_frame_value_range(self, frames: list[np.ndarray]) -> tuple[float, float]:
        minimum = min(float(np.min(frame)) for frame in frames)
        maximum = max(float(np.max(frame)) for frame in frames)
        return minimum, maximum

    @staticmethod
    def _supports_window_level(frame: np.ndarray) -> bool:
        return np.asarray(frame).ndim == 2

    @staticmethod
    def _first_numeric_value(value) -> float | None:
        if value is None:
            return None
        if isinstance(value, pydicom.multival.MultiValue):
            if not value:
                return None
            value = value[0]
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_window_center_from_dataset(self, dataset) -> float | None:
        return self._first_numeric_value(getattr(dataset, "WindowCenter", None))

    def _get_window_width_from_dataset(self, dataset) -> float | None:
        return self._first_numeric_value(getattr(dataset, "WindowWidth", None))

    def _update_window_level_label(self) -> None:
        if self.window_width_value is None or self.window_level_value is None:
            self.window_level_var.set("W/L: RGB 또는 자동 조절 없음")
            return
        self.window_level_var.set(
            f"W/L: {self.window_width_value:.1f} / {self.window_level_value:.1f}"
        )

    def reset_window_level(self) -> None:
        if self.view_mode != "single":
            return
        if self.default_window_width is None or self.default_window_level is None:
            return
        self.window_width_value = self.default_window_width
        self.window_level_value = self.default_window_level
        self._update_window_level_label()
        if self.frames:
            self._show_frame()

    def _start_window_level_drag(self, event: tk.Event) -> None:
        if not self.frames or self.window_width_value is None or self.window_level_value is None:
            return
        self._window_drag_origin = (event.x, event.y)
        self._window_drag_base = (self.window_width_value, self.window_level_value)

    def _update_window_level_drag(self, event: tk.Event) -> None:
        if self._window_drag_origin is None or self._window_drag_base is None:
            return

        start_x, start_y = self._window_drag_origin
        base_width, base_level = self._window_drag_base
        frame_min, frame_max = self.window_level_range
        dynamic_range = max(frame_max - frame_min, 1.0)
        width_delta = (event.x - start_x) * max(dynamic_range / 256.0, 1.0)
        level_delta = (start_y - event.y) * max(dynamic_range / 256.0, 1.0)

        self.window_width_value = float(np.clip(base_width + width_delta, 1.0, dynamic_range * 16.0))
        self.window_level_value = float(
            np.clip(base_level + level_delta, frame_min - dynamic_range * 8.0, frame_max + dynamic_range * 8.0)
        )
        self._update_window_level_label()
        self._show_frame()

    def _end_window_level_drag(self, _event: tk.Event) -> None:
        self._window_drag_origin = None
        self._window_drag_base = None

    def _handle_left_button_press(self, event: tk.Event) -> None:
        if self.crop_mode_active.get():
            self._start_crop_selection(event)
            return
        if self.measurement_mode.get() == "polygon":
            if self._select_persistent_measurement_at_event(event):
                return
            self._handle_polygon_click(event)
            return
        if self._should_use_grid_snapped_line_mode() and not self._is_ctrl_pressed(event):
            self._handle_grid_snapped_line_click(event)
            return
        if self._select_persistent_measurement_at_event(event):
            return
        if self.measurement_mode.get() == "pan":
            self._start_pan(event)
            return
        self._start_preview_measurement(event)

    def _handle_left_button_drag(self, event: tk.Event) -> None:
        if self.crop_mode_active.get():
            self._update_crop_selection(event)
            return
        if self._should_use_grid_snapped_line_mode():
            self._update_grid_snapped_line_preview(event)
            return
        if self.measurement_mode.get() == "pan":
            self._update_pan(event)
            return
        self._update_preview_measurement(event)

    def _handle_left_button_release(self, event: tk.Event) -> None:
        if self.crop_mode_active.get():
            self._finish_crop_selection(event)
            return
        if self._should_use_grid_snapped_line_mode():
            self._update_grid_snapped_line_preview(event)
            return
        if self.measurement_mode.get() == "pan":
            self._end_pan(event)
            return
        self._finish_preview_measurement(event)

    def _handle_right_button_press(self, event: tk.Event) -> None:
        self._start_window_level_drag(event)

    def _handle_right_button_drag(self, event: tk.Event) -> None:
        self._update_window_level_drag(event)

    def _handle_right_button_release(self, event: tk.Event) -> None:
        self._end_window_level_drag(event)

    def _start_pan(self, event: tk.Event) -> None:
        if not self.frames:
            return
        self.canvas.scan_mark(event.x, event.y)

    def _update_pan(self, event: tk.Event) -> None:
        if not self.frames:
            return
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def _end_pan(self, _event: tk.Event) -> None:
        if self.view_mode == "single":
            self._draw_single_view_overlays()
        return

    def enable_crop_mode(self) -> None:
        if not self.frames or self.view_mode != "single":
            messagebox.showinfo("안내", "Crop은 단일 보기에서 이미지를 연 상태에서만 사용할 수 있습니다.")
            return
        self.crop_mode_active.set(True)
        self.cursor_var.set("Cursor: Crop 모드 (드래그하여 영역 선택)")

    def cancel_crop_mode(self) -> None:
        self.crop_mode_active.set(False)
        self._active_crop_start = None
        self._active_crop_end = None
        if self._active_crop_item_id is not None:
            self.canvas.delete(self._active_crop_item_id)
            self._active_crop_item_id = None

    def _start_crop_selection(self, event: tk.Event) -> None:
        start = self._canvas_to_image_coords(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if start is None:
            return
        self._active_crop_start = start
        self._active_crop_end = start
        if self._active_crop_item_id is not None:
            self.canvas.delete(self._active_crop_item_id)
        start_canvas = self._image_coords_to_canvas(*start)
        if start_canvas is None:
            return
        sx, sy = start_canvas
        self._active_crop_item_id = self.canvas.create_rectangle(
            sx,
            sy,
            sx,
            sy,
            outline="#ffd34d",
            width=2,
            dash=(4, 2),
            tags=("temp_measurement",),
        )

    def _update_crop_selection(self, event: tk.Event) -> None:
        if self._active_crop_start is None or self._active_crop_item_id is None:
            return
        end = self._canvas_to_image_coords(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if end is None:
            return
        self._active_crop_end = end
        start_canvas = self._image_coords_to_canvas(*self._active_crop_start)
        end_canvas = self._image_coords_to_canvas(*end)
        if start_canvas is None or end_canvas is None:
            return
        sx, sy = start_canvas
        ex, ey = end_canvas
        self.canvas.coords(self._active_crop_item_id, sx, sy, ex, ey)

    def _finish_crop_selection(self, event: tk.Event) -> None:
        self._update_crop_selection(event)
        if self._active_crop_start is None or self._active_crop_end is None:
            return
        x0 = int(np.floor(min(self._active_crop_start[0], self._active_crop_end[0])))
        y0 = int(np.floor(min(self._active_crop_start[1], self._active_crop_end[1])))
        x1 = int(np.ceil(max(self._active_crop_start[0], self._active_crop_end[0])))
        y1 = int(np.ceil(max(self._active_crop_start[1], self._active_crop_end[1])))
        self.cancel_crop_mode()
        self.apply_crop(x0, y0, x1, y1)

    def _confirm_measurement_reset_for_transform(self, action_name: str) -> bool:
        if not self.persistent_measurements:
            return True
        keep_going = messagebox.askyesno(
            "측정 초기화 확인",
            f"{action_name}을(를) 적용하면 현재 측정값 좌표 정합성이 보장되지 않아 측정을 초기화합니다.\n계속하시겠습니까?",
        )
        if not keep_going:
            return False
        self.clear_persistent_measurements()
        return True

    def apply_crop(self, x0: int, y0: int, x1: int, y1: int) -> None:
        if not self.frames:
            return
        frame = np.asarray(self.frames[self.current_frame])
        if frame.ndim < 2:
            return
        height, width = frame.shape[:2]
        x0 = int(np.clip(min(x0, x1), 0, width - 1))
        y0 = int(np.clip(min(y0, y1), 0, height - 1))
        x1 = int(np.clip(max(x0 + 1, x1), 1, width))
        y1 = int(np.clip(max(y0 + 1, y1), 1, height))
        if x1 - x0 < 2 or y1 - y0 < 2:
            messagebox.showwarning("Crop 취소", "최소 2x2 px 이상의 영역을 선택해 주세요.")
            return
        if not self._confirm_measurement_reset_for_transform("Crop"):
            return
        self.frames = [np.asarray(frame_item)[y0:y1, x0:x1].copy() for frame_item in self.frames]
        self._initialize_window_level(self.dataset, self.frames)
        self.fit_to_window()

    def rotate_current_image(self, angle: int) -> None:
        if not self.frames:
            return
        rotation_map = {90: 1, 180: 2, 270: 3}
        if angle not in rotation_map:
            return
        if not self._confirm_measurement_reset_for_transform(f"Rotate {angle}°"):
            return
        k = rotation_map[angle]
        self.frames = [np.rot90(np.asarray(frame_item), k=k).copy() for frame_item in self.frames]
        self._initialize_window_level(self.dataset, self.frames)
        self.fit_to_window()

    def _update_cursor_coordinates(self, event: tk.Event) -> None:
        if not self.frames:
            self.cursor_var.set("Cursor: -, -")
            return
        coords = self._canvas_to_image_pixel(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if coords is None:
            self.cursor_var.set("Cursor: -, -")
            return
        x, y = coords
        self.cursor_var.set(f"Cursor: ({x}, {y})")
        if self.measurement_mode.get() == "polygon":
            self._update_polygon_preview(event)

    def _should_use_grid_snapped_line_mode(self) -> bool:
        return self.measurement_mode.get() == "line" and self.show_grid_overlay.get() and self.view_mode == "single"

    def _snap_image_point_to_grid_intersection(self, point: tuple[int, int]) -> tuple[int, int]:
        if not self.frames:
            return point
        frame_array = np.asarray(self.frames[self.current_frame])
        if frame_array.ndim < 2:
            return point
        height, width = frame_array.shape[:2]
        spacing = self._get_grid_spacing_px()
        x, y = point
        snapped_x = int(np.clip(round(x / spacing) * spacing, 0, width - 1))
        snapped_y = int(np.clip(round(y / spacing) * spacing, 0, height - 1))
        return snapped_x, snapped_y

    def _handle_grid_snapped_line_click(self, event: tk.Event) -> None:
        click_point = self._canvas_to_image_pixel(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if click_point is None:
            return
        snapped = self._snap_image_point_to_grid_intersection(click_point)
        if self._line_snap_anchor is None:
            self._line_snap_anchor = snapped
            canvas_point = self._image_pixel_to_canvas(snapped[0], snapped[1])
            if canvas_point is None:
                return
            sx, sy = canvas_point
            self.canvas.delete("temp_measurement")
            self._active_preview_measurement = {
                "mode": "line_snap",
                "start": snapped,
            }
            self.canvas.create_line(sx, sy, sx, sy, fill="#7bdff2", width=2, tags=("temp_measurement",))
            return

        measurement = self._append_persistent_measurement("line", self._line_snap_anchor, snapped)
        if measurement is not None:
            self._update_guided_snr_selection(measurement)
        self._line_snap_anchor = None
        self._active_preview_measurement = None
        self.canvas.delete("temp_measurement")
        self._draw_persistent_measurements()

    def _update_grid_snapped_line_preview(self, event: tk.Event) -> None:
        if self._line_snap_anchor is None:
            return
        cursor_point = self._canvas_to_image_pixel(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if cursor_point is None:
            return
        snapped = self._snap_image_point_to_grid_intersection(cursor_point)
        start_canvas = self._image_pixel_to_canvas(self._line_snap_anchor[0], self._line_snap_anchor[1])
        end_canvas = self._image_pixel_to_canvas(snapped[0], snapped[1])
        if start_canvas is None or end_canvas is None:
            return
        sx, sy = start_canvas
        ex, ey = end_canvas
        self.canvas.delete("temp_measurement")
        self.canvas.create_line(sx, sy, ex, ey, fill="#7bdff2", width=2, tags=("temp_measurement",))
        preview_measurement = Measurement(
            id="preview",
            kind="line",
            start=(float(self._line_snap_anchor[0]), float(self._line_snap_anchor[1])),
            end=(float(snapped[0]), float(snapped[1])),
            frame_index=int(self.current_frame),
            geometry_key=self._get_current_geometry_key() or "",
            summary_text="",
            meta={},
        )
        metrics = self.compute_measurement(preview_measurement, self._get_frame_pixel_array(self.current_frame))
        primary_label, secondary_label = self._build_measurement_label_parts("line", metrics, preview_measurement)
        self._draw_measurement_label(
            self.canvas,
            ex + 6,
            ey - 6,
            primary_label,
            secondary_label,
            tags=("temp_measurement",),
            anchor="sw",
        )

    def _canvas_to_image_pixel(self, canvas_x: float, canvas_y: float) -> tuple[int, int] | None:
        image_coords = self._canvas_to_image_coords(canvas_x, canvas_y)
        if image_coords is None:
            return None
        x_coord, y_coord = image_coords
        frame_array = np.asarray(self.frames[self.current_frame])
        if frame_array.ndim < 2:
            return None
        height, width = frame_array.shape[:2]
        return int(np.clip(np.floor(x_coord), 0, width - 1)), int(np.clip(np.floor(y_coord), 0, height - 1))

    def _canvas_to_image_coords(self, canvas_x: float, canvas_y: float) -> tuple[float, float] | None:
        if self._image_bbox is None or not self.frames:
            return None
        left, top, right, bottom = self._image_bbox
        if canvas_x < left or canvas_x >= right or canvas_y < top or canvas_y >= bottom:
            return None

        frame_array = np.asarray(self.frames[self.current_frame])
        if frame_array.ndim < 2:
            return None
        height, width = frame_array.shape[:2]
        display_width = max(right - left, 1.0)
        display_height = max(bottom - top, 1.0)
        x_ratio = (canvas_x - left) / display_width
        y_ratio = (canvas_y - top) / display_height
        return float(np.clip(x_ratio * width, 0, max(width - 1, 0))), float(np.clip(y_ratio * height, 0, max(height - 1, 0)))

    def _cancel_polygon_draft(self) -> None:
        self._polygon_points = []
        self._polygon_cursor_point = None
        self.canvas.delete("temp_measurement")

    def _get_polygon_point_from_event(self, event: tk.Event) -> tuple[int, int] | None:
        point = self._canvas_to_image_pixel(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if point is None:
            return None
        if self.show_grid_overlay.get():
            return self._snap_image_point_to_grid_intersection(point)
        return point

    def _handle_polygon_click(self, event: tk.Event) -> None:
        point = self._get_polygon_point_from_event(event)
        if point is None:
            return
        if self._polygon_points and point == self._polygon_points[-1]:
            return
        if len(self._polygon_points) >= 3 and np.hypot(point[0] - self._polygon_points[0][0], point[1] - self._polygon_points[0][1]) <= 2.0:
            self._finalize_polygon_measurement()
            return
        self._polygon_points.append(point)
        self._polygon_cursor_point = point
        self._draw_polygon_draft()

    def _update_polygon_preview(self, event: tk.Event) -> None:
        if not self._polygon_points:
            return
        point = self._get_polygon_point_from_event(event)
        if point is None:
            return
        self._polygon_cursor_point = point
        self._draw_polygon_draft()

    def _draw_polygon_draft(self) -> None:
        self.canvas.delete("temp_measurement")
        if not self._polygon_points:
            return
        canvas_points: list[float] = []
        for x, y in self._polygon_points:
            canvas_point = self._image_pixel_to_canvas(x, y)
            if canvas_point is None:
                return
            canvas_points.extend(canvas_point)
        if len(canvas_points) >= 4:
            self.canvas.create_line(*canvas_points, fill="#7bdff2", width=2, tags=("temp_measurement",))
        for x, y in self._polygon_points:
            center = self._image_pixel_to_canvas(x, y)
            if center is None:
                continue
            cx, cy = center
            self.canvas.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="#7bdff2", outline="#7bdff2", tags=("temp_measurement",))
        if self._polygon_cursor_point is not None and self._polygon_points:
            start = self._image_pixel_to_canvas(*self._polygon_points[-1])
            end = self._image_pixel_to_canvas(*self._polygon_cursor_point)
            if start is not None and end is not None:
                self.canvas.create_line(*start, *end, fill="#7bdff2", width=1, dash=(3, 2), tags=("temp_measurement",))

    def _finalize_polygon_measurement(self) -> None:
        if len(self._polygon_points) < 3:
            self._cancel_polygon_draft()
            return
        points = list(self._polygon_points)
        points_closed = points + [points[0]]
        segment_lengths = [
            float(np.hypot(points_closed[i + 1][0] - points_closed[i][0], points_closed[i + 1][1] - points_closed[i][1]))
            for i in range(len(points))
        ]
        for index in range(len(points)):
            self._append_persistent_measurement("line", points_closed[index], points_closed[index + 1])
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        self._append_persistent_measurement(
            "polygon",
            (min(xs), min(ys)),
            (max(xs), max(ys)),
            extra_meta={
                "points": [[int(x), int(y)] for x, y in points],
                "closed": True,
                "segment_lengths_px": segment_lengths,
            },
        )
        self._cancel_polygon_draft()
        self._draw_persistent_measurements()

    def _start_preview_measurement(self, event: tk.Event) -> None:
        if not self.frames or self.view_mode != "single":
            return
        mode = self.measurement_mode.get()
        if mode == "roi":
            if self.roi_draw_mode.get() == "grid":
                self._create_grid_aligned_roi(event)
                return
            start_x = self.canvas.canvasx(event.x)
            start_y = self.canvas.canvasy(event.y)
            item_id = self.canvas.create_rectangle(
                start_x,
                start_y,
                start_x,
                start_y,
                outline="#ffd34d",
                width=2,
                tags=("temp_measurement",),
            )
            self._active_preview_measurement = {
                "mode": "roi",
                "item_id": item_id,
                "start": (start_x, start_y),
                "end": (start_x, start_y),
            }
            return
        if mode != "line":
            return
        start_x = self.canvas.canvasx(event.x)
        start_y = self.canvas.canvasy(event.y)
        item_id = self.canvas.create_line(
            start_x, start_y, start_x, start_y, fill="#7bdff2", width=2, tags=("temp_measurement",)
        )
        self._active_preview_measurement = {
            "mode": mode,
            "item_id": item_id,
            "start": (start_x, start_y),
            "end": (start_x, start_y),
        }

    def _update_preview_measurement(self, event: tk.Event) -> None:
        if self._active_preview_measurement is None:
            return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        start_x, start_y = self._active_preview_measurement["start"]
        self._active_preview_measurement["end"] = (end_x, end_y)
        self.canvas.coords(self._active_preview_measurement["item_id"], start_x, start_y, end_x, end_y)

    def _finish_preview_measurement(self, event: tk.Event) -> None:
        if self.measurement_mode.get() == "roi" and self.roi_draw_mode.get() == "grid":
            return
        if self._active_preview_measurement is None:
            return
        self._update_preview_measurement(event)
        mode = self._active_preview_measurement["mode"]
        start_x, start_y = self._active_preview_measurement["start"]
        end_x, end_y = self._active_preview_measurement["end"]
        image_start = self._canvas_to_image_pixel(start_x, start_y)
        image_end = self._canvas_to_image_pixel(end_x, end_y)
        self.canvas.delete(self._active_preview_measurement["item_id"])
        self._active_preview_measurement = None
        if image_start is None or image_end is None:
            return
        extra_meta: dict[str, Any] | None = None
        if mode == "roi":
            extra_meta = {"roi_type": "free"}
        measurement = self._append_persistent_measurement(mode, image_start, image_end, extra_meta=extra_meta)
        if measurement is not None:
            self._update_guided_snr_selection(measurement)
        self._draw_preview_measurements()
        self._draw_persistent_measurements()

    @staticmethod
    def _safe_positive_int(value: Any, fallback: int = 1) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return max(fallback, 1)
        return max(parsed, 1)

    def _sync_grid_spacing_from_mode(self) -> None:
        if self.grid_spacing_mode.get() == "Custom":
            spacing = self._safe_positive_int(self.grid_spacing_custom_px.get(), fallback=int(self.grid_spacing_px.get()))
        else:
            spacing = self._safe_positive_int(self.grid_spacing_mode.get(), fallback=8)
        self.grid_spacing_px.set(spacing)
        self._update_grid_cell_size_label()

    def _on_grid_spacing_mode_changed(self, *_args: Any) -> None:
        self._sync_grid_spacing_from_mode()
        self._refresh_grid_overlay()

    def _on_grid_spacing_custom_changed(self, *_args: Any) -> None:
        if self.grid_spacing_mode.get() != "Custom":
            return
        self._sync_grid_spacing_from_mode()
        self._refresh_grid_overlay()

    def _get_grid_spacing_px(self) -> int:
        return self._safe_positive_int(self.grid_spacing_px.get(), fallback=8)

    def _update_grid_cell_size_label(self) -> None:
        spacing_px = self._get_grid_spacing_px()
        spacing_mm = self._get_pixel_spacing_mm()
        if spacing_mm is None:
            self.grid_cell_size_var.set(f"Grid cell size: {spacing_px} px")
            return
        row_mm, col_mm = spacing_mm
        cell_h_mm = spacing_px * row_mm
        cell_w_mm = spacing_px * col_mm
        if abs(cell_h_mm - cell_w_mm) < 1e-3:
            self.grid_cell_size_var.set(f"Grid cell size: {spacing_px} px ({cell_w_mm:.2f} mm)")
            return
        self.grid_cell_size_var.set(
            f"Grid cell size: {spacing_px} px ({cell_w_mm:.2f} x {cell_h_mm:.2f} mm)"
        )

    def _sync_grid_roi_size_from_mode(self) -> None:
        mode_value = self.grid_roi_size_mode.get()
        if mode_value != "Custom" and "x" in mode_value:
            width_text, height_text = mode_value.split("x", 1)
            self.grid_roi_width_cells.set(self._safe_positive_int(width_text, fallback=1))
            self.grid_roi_height_cells.set(self._safe_positive_int(height_text, fallback=1))
        self.grid_roi_size_cells.set(self._safe_positive_int(self.grid_roi_width_cells.get(), fallback=1))

    def _on_grid_roi_size_mode_changed(self, *_args: Any) -> None:
        self._sync_grid_roi_size_from_mode()

    def _on_grid_roi_dimension_changed(self, *_args: Any) -> None:
        self.grid_roi_size_cells.set(self._safe_positive_int(self.grid_roi_width_cells.get(), fallback=1))

    def _get_grid_roi_size_cells(self) -> tuple[int, int]:
        width = self._safe_positive_int(self.grid_roi_width_cells.get(), fallback=1)
        height = self._safe_positive_int(self.grid_roi_height_cells.get(), fallback=1)
        return width, height

    def _create_grid_aligned_roi(self, event: tk.Event) -> None:
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        cell = self.get_grid_cell(canvas_x, canvas_y)
        if cell is None:
            return
        row, col = cell
        existing_measurement_id = self._find_grid_roi_measurement_id_from_cell(row, col)
        ctrl_pressed = bool(event.state & 0x4)
        if existing_measurement_id is not None:
            self._apply_measurement_selection(existing_measurement_id, toggle=ctrl_pressed)
            self._show_frame()
            return
        created_measurement = self.select_roi_from_grid(row, col)
        if created_measurement is not None:
            self._apply_measurement_selection(created_measurement.id, toggle=ctrl_pressed)
        self._show_frame()

    def get_grid_cell(self, canvas_x: float, canvas_y: float) -> tuple[int, int] | None:
        image_point = self._canvas_to_image_pixel(canvas_x, canvas_y)
        if image_point is None:
            return None
        cell_size_px = self._get_grid_spacing_px()
        row = int(image_point[1] // cell_size_px)
        col = int(image_point[0] // cell_size_px)
        return row, col

    def select_roi_from_grid(self, row: int, col: int) -> Measurement | None:
        frame_array = np.asarray(self.frames[self.current_frame])
        if frame_array.ndim < 2:
            return None
        height, width = frame_array.shape[:2]
        cell_size_px = self._get_grid_spacing_px()
        roi_cells_w, roi_cells_h = self._get_grid_roi_size_cells()
        x0 = int(np.clip(col * cell_size_px, 0, max(width - 1, 0)))
        y0 = int(np.clip(row * cell_size_px, 0, max(height - 1, 0)))
        x1 = int(np.clip(x0 + (cell_size_px * roi_cells_w), 0, width))
        y1 = int(np.clip(y0 + (cell_size_px * roi_cells_h), 0, height))
        measurement = self._append_persistent_measurement(
            "roi",
            (x0, y0),
            (x1, y1),
            extra_meta={"roi_type": "grid"},
            roi_bounds_exclusive=True,
        )
        if measurement is None:
            return None
        measurement.meta["grid_cell"] = {"row": int(row), "col": int(col)}
        metrics = self.compute_measurement(measurement, frame_array)
        measurement.summary_text = metrics["summary"]
        measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
        return measurement

    @staticmethod
    def compute_roi_statistics(roi_array: np.ndarray) -> dict[str, float]:
        if roi_array.size == 0:
            return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        mean_val = float(np.mean(roi_array))
        std_val = float(np.std(roi_array))
        min_val = float(np.min(roi_array))
        max_val = float(np.max(roi_array))
        return {"mean": mean_val, "std": std_val, "min": min_val, "max": max_val}

    @staticmethod
    def _normalize_roi_bounds(
        image_shape: tuple[int, ...],
        start: tuple[int | float, int | float],
        end: tuple[int | float, int | float],
        ensure_non_empty: bool = True,
    ) -> tuple[int, int, int, int]:
        if len(image_shape) < 2:
            return 0, 0, 0, 0
        height = int(image_shape[0])
        width = int(image_shape[1])
        if width <= 0 or height <= 0:
            return 0, 0, 0, 0
        x0_raw = min(int(round(start[0])), int(round(end[0])))
        y0_raw = min(int(round(start[1])), int(round(end[1])))
        x1_raw = max(int(round(start[0])), int(round(end[0])))
        y1_raw = max(int(round(start[1])), int(round(end[1])))
        x0 = int(np.clip(x0_raw, 0, width))
        y0 = int(np.clip(y0_raw, 0, height))
        x1 = int(np.clip(x1_raw, 0, width))
        y1 = int(np.clip(y1_raw, 0, height))
        if ensure_non_empty:
            if x1 <= x0:
                if x0 >= width:
                    x0 = max(width - 1, 0)
                    x1 = width
                else:
                    x1 = min(x0 + 1, width)
            if y1 <= y0:
                if y0 >= height:
                    y0 = max(height - 1, 0)
                    y1 = height
                else:
                    y1 = min(y0 + 1, height)
        return x0, y0, x1, y1

    def _extract_roi_pixels(
        self,
        image_array: np.ndarray | None,
        start: tuple[int | float, int | float],
        end: tuple[int | float, int | float],
        ensure_non_empty: bool = True,
    ) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        if image_array is None or image_array.ndim < 2:
            return np.array([]), (0, 0, 0, 0)
        x0, y0, x1, y1 = self._normalize_roi_bounds(image_array.shape, start, end, ensure_non_empty=ensure_non_empty)
        if x1 <= x0 or y1 <= y0:
            return np.array([]), (x0, y0, x1, y1)
        return image_array[y0:y1, x0:x1], (x0, y0, x1, y1)

    @staticmethod
    def _extract_grid_cell_meta(meta: dict[str, Any]) -> dict[str, int] | None:
        grid_cell = meta.get("grid_cell")
        if isinstance(grid_cell, dict):
            try:
                return {"row": int(grid_cell["row"]), "col": int(grid_cell["col"])}
            except (KeyError, TypeError, ValueError):
                pass
        legacy_source = str(meta.get("source_mode", ""))
        if legacy_source == "grid_roi":
            roi_id = str((meta.get("roi_stats") or meta.get("signal_stats") or {}).get("roi_id", ""))
            if "_" in roi_id:
                row_text, col_text = roi_id.split("_", 1)
                if row_text.isdigit() and col_text.isdigit():
                    return {"row": int(row_text), "col": int(col_text)}
        return None

    def _canonicalize_measurement_meta(self, measurement: Measurement, metrics: dict[str, Any]) -> dict[str, Any]:
        raw_meta = dict(measurement.meta or {})
        grid_cell = self._extract_grid_cell_meta(raw_meta)
        geometry = dict(metrics.get("geometry") or {})
        analysis = dict(metrics.get("analysis") or {})
        canonical: dict[str, Any] = {
            "metrics": metrics,
            "geometry": geometry,
            "analysis": analysis,
        }
        if measurement.kind == "roi":
            roi_type = str(raw_meta.get("roi_type") or ("grid" if grid_cell is not None else "free"))
            canonical["roi_type"] = roi_type
            role = self._normalize_roi_role(raw_meta.get("role"))
            if role is not None:
                canonical["role"] = role
            signal_stats = dict(metrics.get("signal_stats") or {})
            if grid_cell is not None:
                canonical["grid_cell"] = grid_cell
                signal_stats["roi_id"] = f"{grid_cell['row']}_{grid_cell['col']}"
            elif "roi_id" not in signal_stats:
                signal_stats["roi_id"] = measurement.id
            canonical["signal_stats"] = signal_stats
        if measurement.kind == "polygon":
            points = raw_meta.get("points", [])
            if isinstance(points, list):
                canonical["points"] = points
            canonical["closed"] = bool(raw_meta.get("closed", True))
            segments = raw_meta.get("segment_lengths_px", [])
            if isinstance(segments, list):
                canonical["segment_lengths_px"] = [float(value) for value in segments]
        return canonical

    def _find_grid_roi_measurement_id_from_cell(self, row: int, col: int) -> str | None:
        for item in self._current_grid_roi_measurements():
            cell_meta = item.meta.get("grid_cell", {})
            if int(cell_meta.get("row", -1)) == int(row) and int(cell_meta.get("col", -1)) == int(col):
                return item.id
        return None

    def _current_grid_roi_measurements(self) -> list[Measurement]:
        current_geometry = self._get_current_geometry_key()
        return [
            item
            for item in self.persistent_measurements
            if item.kind == "roi"
            and item.meta.get("grid_cell") is not None
            and item.frame_index == self.current_frame
            and self._geometry_matches(item.geometry_key, current_geometry)
        ]

    @staticmethod
    def _grid_roi_bounds_from_points(start: tuple[int, int], end: tuple[int, int]) -> Rect:
        x0 = int(round(min(start[0], end[0])))
        y0 = int(round(min(start[1], end[1])))
        x1 = int(round(max(start[0], end[0])))
        y1 = int(round(max(start[1], end[1])))
        return Rect(x1=float(x0), y1=float(y0), x2=float(x1), y2=float(y1))

    @staticmethod
    def _grid_roi_bounds_connected(left: Rect, right: Rect) -> bool:
        horizontal_touch = (left.x2 == right.x1 or right.x2 == left.x1) and min(left.y2, right.y2) > max(left.y1, right.y1)
        vertical_touch = (left.y2 == right.y1 or right.y2 == left.y1) and min(left.x2, right.x2) > max(left.x1, right.x1)
        return horizontal_touch or vertical_touch

    def _build_grid_roi_regions(self, measurements: list[Measurement | dict[str, Any]]) -> list[dict[str, Any]]:
        cells: list[RectRoi] = []
        for item in measurements:
            if isinstance(item, Measurement):
                start = (int(round(item.start[0])), int(round(item.start[1])))
                end = (int(round(item.end[0])), int(round(item.end[1])))
                is_grid_roi = item.meta.get("grid_cell") is not None
                measurement_id = item.id
            else:
                start = tuple(item.get("start", (0, 0)))
                end = tuple(item.get("end", (0, 0)))
                meta = dict(item.get("meta") or {})
                is_grid_roi = self._extract_grid_cell_meta(meta) is not None
                measurement_id = None
            if not is_grid_roi:
                continue
            bounds = self._grid_roi_bounds_from_points(start, end)
            area = max(int(bounds.x2 - bounds.x1), 0) * max(int(bounds.y2 - bounds.y1), 0)
            cells.append(
                RectRoi(
                    roi_id=str(measurement_id or ""),
                    image_rect=bounds,
                    stats=RoiStats(mean=0.0, std=0.0, min_val=0.0, max_val=0.0, area_px=area),
                )
            )
        if not cells:
            return []

        regions: list[dict[str, Any]] = []
        visited: set[int] = set()
        for index, cell in enumerate(cells):
            if index in visited:
                continue
            stack = [index]
            member_indices: list[int] = []
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                member_indices.append(current)
                current_bounds = cells[current].image_rect
                for other in range(len(cells)):
                    if other in visited or other == current:
                        continue
                    if self._grid_roi_bounds_connected(current_bounds, cells[other].image_rect):
                        stack.append(other)

            members = [cells[i] for i in member_indices]
            x0 = min(member.image_rect.x1 for member in members)
            y0 = min(member.image_rect.y1 for member in members)
            x1 = max(member.image_rect.x2 for member in members)
            y1 = max(member.image_rect.y2 for member in members)
            regions.append(
                {
                    "bounds": Rect(x1=x0, y1=y0, x2=x1, y2=y1),
                    "area_px": sum(member.stats.area_px for member in members if member.stats is not None),
                    "measurement_ids": {member.roi_id for member in members if member.roi_id},
                }
            )
        return regions

    def _format_grid_roi_region_summary(self, width_px: int, height_px: int, area_px: int) -> str:
        spacing = self._get_pixel_spacing_mm()
        if spacing is None:
            width_mm_text = "N/A mm"
            height_mm_text = "N/A mm"
            area_mm_text = "N/A mm²"
        else:
            row_mm, col_mm = spacing
            width_mm_text = f"{width_px * col_mm:.1f} mm"
            height_mm_text = f"{height_px * row_mm:.1f} mm"
            area_mm_text = f"{area_px * row_mm * col_mm:.1f} mm²"
        return (
            f"W: {width_mm_text} ({width_px} px)\n"
            f"H: {height_mm_text} ({height_px} px)\n"
            f"Area: {area_mm_text} ({area_px} px²)"
        )

    def _show_grid_roi_combined_summary(self) -> bool:
        selected = self._current_grid_roi_measurements()
        if not selected:
            return False
        regions = self._build_grid_roi_regions(selected)
        if not regions:
            return False
        lines: list[str] = []
        for index, region in enumerate(regions, start=1):
            bounds: Rect = region["bounds"]
            x0, y0, x1, y1 = bounds.x1, bounds.y1, bounds.x2, bounds.y2
            width_px = int(max(x1 - x0, 0))
            height_px = int(max(y1 - y0, 0))
            summary = self._format_grid_roi_region_summary(width_px, height_px, int(region["area_px"]))
            lines.append(f"Region {index}\n{summary}")
        messagebox.showinfo("Grid ROI Combined Summary", "\n\n".join(lines))
        return True

    def _get_pixel_spacing_mm(self) -> tuple[float, float] | None:
        if self.dataset is None:
            return None
        value = getattr(self.dataset, "PixelSpacing", None)
        if value is None:
            value = getattr(self.dataset, "ImagerPixelSpacing", None)
        if value is None:
            return None
        try:
            row = float(value[0])
            col = float(value[1] if len(value) > 1 else value[0])
            if row <= 0 or col <= 0:
                return None
            return row, col
        except Exception:
            return None

    def compute_measurement(self, measurement: Measurement, image_array: np.ndarray | None) -> dict[str, Any]:
        start = (int(round(measurement.start[0])), int(round(measurement.start[1])))
        end = (int(round(measurement.end[0])), int(round(measurement.end[1])))
        dx_px = abs(end[0] - start[0])
        dy_px = abs(end[1] - start[1])
        spacing = self._get_pixel_spacing_mm()
        row_mm = spacing[0] if spacing is not None else None
        col_mm = spacing[1] if spacing is not None else None
        signal_stats: dict[str, Any] | None = None
        analysis: dict[str, Any] = {}
        roi_x = int(min(start[0], end[0]))
        roi_y = int(min(start[1], end[1]))
        roi_width_px = int(dx_px)
        roi_height_px = int(dy_px)
        pixel_count = int(max(roi_width_px, 0) * max(roi_height_px, 0))
        polygon_points: list[tuple[float, float]] = []
        polygon_segment_lengths_px: list[float] = []
        polygon_segment_lengths_mm: list[float] = []
        polygon_area_px = 0.0
        polygon_area_mm2: float | None = None
        if measurement.kind == "roi":
            legacy_stats = measurement.meta.get("signal_stats") or measurement.meta.get("roi_stats") or {}
            roi_id = str(legacy_stats.get("roi_id") or measurement.id)
            if image_array is None or image_array.ndim < 2:
                signal_stats = {
                    "roi_id": roi_id,
                    "mean": 0.0,
                    "std": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "pixel_count": int(pixel_count),
                }
            else:
                roi_pixels, (x0, y0, x1, y1) = self._extract_roi_pixels(image_array, measurement.start, measurement.end)
                stats = self.compute_roi_statistics(roi_pixels)
                roi_width_px = int(max(x1 - x0, 0))
                roi_height_px = int(max(y1 - y0, 0))
                roi_x = int(x0)
                roi_y = int(y0)
                pixel_count = int(roi_width_px * roi_height_px)
                signal_stats = {
                    "roi_id": roi_id,
                    "mean": stats["mean"],
                    "std": stats["std"],
                    "min": stats["min"],
                    "max": stats["max"],
                    "pixel_count": pixel_count,
                }
            std_value = float(signal_stats.get("std", 0.0)) if signal_stats is not None else 0.0
            mean_value = float(signal_stats.get("mean", 0.0)) if signal_stats is not None else 0.0
            analysis["snr"] = 0.0 if std_value <= 0 else float(mean_value / std_value)
            dx_px = roi_width_px
            dy_px = roi_height_px

        if measurement.kind == "polygon":
            raw_points = measurement.meta.get("points", [])
            if isinstance(raw_points, list):
                for item in raw_points:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        polygon_points.append((float(item[0]), float(item[1])))
            if len(polygon_points) >= 3:
                closed = polygon_points + [polygon_points[0]]
                polygon_segment_lengths_px = [
                    float(np.hypot(closed[i + 1][0] - closed[i][0], closed[i + 1][1] - closed[i][1]))
                    for i in range(len(polygon_points))
                ]
                if row_mm is not None and col_mm is not None:
                    polygon_segment_lengths_mm = [
                        float(
                            np.hypot(
                                (closed[i + 1][0] - closed[i][0]) * col_mm,
                                (closed[i + 1][1] - closed[i][1]) * row_mm,
                            )
                        )
                        for i in range(len(polygon_points))
                    ]
                area_sum = 0.0
                for i in range(len(polygon_points)):
                    x0, y0 = polygon_points[i]
                    x1, y1 = polygon_points[(i + 1) % len(polygon_points)]
                    area_sum += x0 * y1 - x1 * y0
                polygon_area_px = abs(area_sum) * 0.5
                if row_mm is not None and col_mm is not None:
                    polygon_area_mm2 = float(polygon_area_px * row_mm * col_mm)
                dx_px = int(max(point[0] for point in polygon_points) - min(point[0] for point in polygon_points))
                dy_px = int(max(point[1] for point in polygon_points) - min(point[1] for point in polygon_points))

        geometry: dict[str, Any] = {
            "x": float(roi_x if measurement.kind == "roi" else min(start[0], end[0])),
            "y": float(roi_y if measurement.kind == "roi" else min(start[1], end[1])),
            "width_px": float(dx_px),
            "height_px": float(dy_px),
            "area_px": float(polygon_area_px if measurement.kind == "polygon" else dx_px * dy_px),
            "length_px": float(
                np.sum(polygon_segment_lengths_px) if measurement.kind == "polygon" and polygon_segment_lengths_px else np.hypot(dx_px, dy_px)
            ),
            "width_mm": None if col_mm is None else float(dx_px * col_mm),
            "height_mm": None if row_mm is None else float(dy_px * row_mm),
            "area_mm2": polygon_area_mm2
            if measurement.kind == "polygon"
            else (None if (row_mm is None or col_mm is None) else float(dx_px * dy_px * row_mm * col_mm)),
            "length_mm": None
            if (row_mm is None or col_mm is None)
            else (
                float(np.sum(polygon_segment_lengths_mm))
                if measurement.kind == "polygon" and polygon_segment_lengths_mm
                else float(np.hypot(dx_px * col_mm, dy_px * row_mm))
            ),
            "pixel_count": int(pixel_count if measurement.kind == "roi" else max(dx_px, 0) * max(dy_px, 0)),
        }

        result: dict[str, Any] = {
            "pixel_spacing_mm": spacing,
            "geometry": geometry,
            "signal_stats": signal_stats,
            "analysis": analysis,
            "width_px": geometry["width_px"],
            "height_px": geometry["height_px"],
            "area_px": geometry["area_px"],
            "length_px": geometry["length_px"],
            "width_mm": geometry["width_mm"],
            "height_mm": geometry["height_mm"],
            "area_mm2": geometry["area_mm2"],
            "length_mm": geometry["length_mm"],
            "pixel_count": geometry["pixel_count"],
            "segment_lengths_px": polygon_segment_lengths_px,
            "segment_lengths_mm": polygon_segment_lengths_mm,
            "point_count": len(polygon_points),
        }
        if measurement.kind == "roi":
            result["summary"] = self._format_roi_measurement_summary(result)
        elif measurement.kind == "polygon":
            result["summary"] = self._format_polygon_measurement_summary(result)
        else:
            result["summary"] = self._format_line_measurement_summary(result)
        return result

    @staticmethod
    def _format_mm_value(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.2f}"

    def _format_roi_measurement_summary(self, metrics: dict[str, Any]) -> str:
        width_px = int(round(metrics["width_px"]))
        height_px = int(round(metrics["height_px"]))
        area_px = int(round(metrics["area_px"]))
        geometry = dict(metrics.get("geometry") or {})
        x_px = int(round(float(geometry.get("x", 0.0))))
        y_px = int(round(float(geometry.get("y", 0.0))))
        width_mm_text = f"{self._format_mm_value(metrics['width_mm'])} mm"
        height_mm_text = f"{self._format_mm_value(metrics['height_mm'])} mm"
        area_mm_text = f"{self._format_mm_value(metrics['area_mm2'])} mm²"
        return (
            f"X,Y: ({x_px}, {y_px})\n"
            f"W: {width_mm_text} ({width_px} px)\n"
            f"H: {height_mm_text} ({height_px} px)\n"
            f"Area: {area_mm_text} ({area_px} px²)"
        )

    def _format_line_measurement_summary(self, metrics: dict[str, Any]) -> str:
        px_text = f"{metrics['length_px']:.1f}px"
        mm_value = self._format_mm_value(metrics["length_mm"])
        return f"{px_text} | {mm_value}mm"

    def _format_polygon_measurement_summary(self, metrics: dict[str, Any]) -> str:
        area_mm_text = f"{self._format_mm_value(metrics['area_mm2'])} mm²"
        perimeter_mm_text = f"{self._format_mm_value(metrics['length_mm'])} mm"
        return (
            f"Poly {int(metrics.get('point_count', 0))}pts\n"
            f"Perimeter: {perimeter_mm_text} ({metrics['length_px']:.1f} px)\n"
            f"Area: {area_mm_text} ({metrics['area_px']:.1f} px²)"
        )

    def _image_pixel_to_canvas(self, pixel_x: int, pixel_y: int) -> tuple[float, float] | None:
        return self._image_coords_to_canvas(float(pixel_x), float(pixel_y))

    def _image_coords_to_canvas(self, image_x: float, image_y: float) -> tuple[float, float] | None:
        if self._image_bbox is None or not self.frames:
            return None
        frame_array = np.asarray(self.frames[self.current_frame])
        if frame_array.ndim < 2:
            return None
        height, width = frame_array.shape[:2]
        if width <= 0 or height <= 0:
            return None
        left, top, right, bottom = self._image_bbox
        display_width = right - left
        display_height = bottom - top
        canvas_x = left + (float(image_x) / width) * display_width
        canvas_y = top + (float(image_y) / height) * display_height
        return canvas_x, canvas_y

    def _draw_preview_measurements(self) -> None:
        self.canvas.delete("temp_measurement")
        if self._active_preview_measurement is None:
            return
        mode = self._active_preview_measurement.get("mode")
        start = self._active_preview_measurement.get("start")
        end = self._active_preview_measurement.get("end")
        if start is None or end is None:
            return
        start_x, start_y = start
        end_x, end_y = end
        image_start = self._canvas_to_image_pixel(start_x, start_y)
        image_end = self._canvas_to_image_pixel(end_x, end_y)
        if mode == "roi":
            self.canvas.create_rectangle(
                start_x,
                start_y,
                end_x,
                end_y,
                outline="#ffd34d",
                width=2,
                dash=(4, 2),
                tags=("temp_measurement",),
            )
            if image_start is None or image_end is None:
                return
            preview_measurement = Measurement(
                id="preview",
                kind="roi",
                start=(float(image_start[0]), float(image_start[1])),
                end=(float(image_end[0]), float(image_end[1])),
                frame_index=int(self.current_frame),
                geometry_key=self._get_current_geometry_key() or "",
                summary_text="",
                meta={},
            )
            metrics = self.compute_measurement(preview_measurement, self._get_frame_pixel_array(self.current_frame))
            primary_label, secondary_label = self._build_measurement_label_parts("roi", metrics, preview_measurement)
        else:
            self.canvas.create_line(
                start_x,
                start_y,
                end_x,
                end_y,
                fill="#7bdff2",
                width=2,
                tags=("temp_measurement",),
            )
            if image_start is None or image_end is None:
                return
            preview_measurement = Measurement(
                id="preview",
                kind="line",
                start=(float(image_start[0]), float(image_start[1])),
                end=(float(image_end[0]), float(image_end[1])),
                frame_index=int(self.current_frame),
                geometry_key=self._get_current_geometry_key() or "",
                summary_text="",
                meta={},
            )
            metrics = self.compute_measurement(preview_measurement, self._get_frame_pixel_array(self.current_frame))
            primary_label, secondary_label = self._build_measurement_label_parts("line", metrics, preview_measurement)
        self._draw_measurement_label(
            self.canvas,
            end_x + 6,
            end_y - 6,
            primary_label,
            secondary_label,
            tags=("temp_measurement",),
            anchor="sw",
        )

    def clear_preview_overlay(self) -> None:
        self._active_preview_measurement = None
        self._line_snap_anchor = None
        self.canvas.delete("temp_measurement")
        self._active_crop_item_id = None

    def clear_persistent_measurements(self) -> None:
        self.persistent_measurements = []
        self.selected_persistent_measurement_id = None
        self._persistent_canvas_item_to_measurement_id = {}
        self._cancel_guided_snr_workflow()
        self.canvas.delete("persistent_measurement")
        self.canvas.delete("temp_measurement")
        self._refresh_analysis_selectors()
        self._update_analysis_action_button_state()
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def undo_last_measurement(self) -> None:
        if not self.persistent_measurements:
            return
        removed = self.persistent_measurements.pop()
        state = self.guided_snr_state
        if state is not None and removed.id in {state.get("signal_id"), state.get("noise_id")}:
            self._cancel_guided_snr_workflow()
        if self.selected_persistent_measurement_id == removed.id:
            self.selected_persistent_measurement_id = None
        self._draw_preview_measurements()
        self._draw_persistent_measurements()
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def clear_selected_measurement(self) -> None:
        selected_id = self.selected_persistent_measurement_id
        if selected_id is None:
            messagebox.showinfo("안내", "삭제할 측정을 먼저 선택하세요.")
            return
        remaining = [item for item in self.persistent_measurements if item.id != selected_id]
        if len(remaining) == len(self.persistent_measurements):
            self.selected_persistent_measurement_id = None
            self._draw_persistent_measurements()
            return
        state = self.guided_snr_state
        if state is not None and selected_id in {state.get("signal_id"), state.get("noise_id")}:
            self._cancel_guided_snr_workflow()
        self.persistent_measurements = remaining
        self.selected_persistent_measurement_id = None
        self._draw_preview_measurements()
        self._draw_persistent_measurements()
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def _select_persistent_measurement_at_event(self, event: tk.Event) -> bool:
        if self.view_mode != "single":
            return False
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        overlapping = list(reversed(self.canvas.find_overlapping(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3)))
        for item_id in overlapping:
            measurement_id = self._persistent_canvas_item_to_measurement_id.get(item_id)
            if measurement_id is None:
                continue
            self._apply_measurement_selection(measurement_id)
            self._draw_persistent_measurements()
            return True
        return False

    def _apply_measurement_selection(self, measurement_id: str, toggle: bool = False) -> None:
        if toggle and self.selected_persistent_measurement_id == measurement_id:
            self.selected_persistent_measurement_id = None
            return
        self.selected_persistent_measurement_id = measurement_id

    def register_measurement_hit_target(self, item_id: int, measurement_id: str) -> None:
        self._persistent_canvas_item_to_measurement_id[item_id] = measurement_id

    def _get_current_geometry_key(self) -> str | None:
        return self._get_geometry_key_for_frame(self.current_frame)

    def _get_geometry_key_for_frame(self, frame_index: int) -> str | None:
        if self.dataset is None or not self.frames:
            return None
        if not (0 <= frame_index < len(self.frames)):
            return None
        frame = np.asarray(self.frames[frame_index])
        if frame.ndim < 2:
            return None
        key = {
            "rows": int(frame.shape[0]),
            "cols": int(frame.shape[1]),
            "spacing": getattr(self.dataset, "PixelSpacing", None),
            "thickness": getattr(self.dataset, "SliceThickness", None),
            "orientation": getattr(self.dataset, "ImageOrientationPatient", None),
            "position": getattr(self.dataset, "ImagePositionPatient", None),
            "sop": getattr(self.dataset, "SOPInstanceUID", None),
            "frame_index": int(frame_index),
        }
        return json.dumps(key, sort_keys=True, default=str)

    @staticmethod
    def _geometry_matches(left: str | None, right: str | None) -> bool:
        return bool(left) and bool(right) and left == right

    def _append_persistent_measurement(
        self,
        mode: str,
        image_start: tuple[int, int],
        image_end: tuple[int, int],
        extra_meta: dict[str, Any] | None = None,
        roi_bounds_exclusive: bool = False,
    ) -> Measurement | None:
        geometry_key = self._get_current_geometry_key()
        if geometry_key is None:
            return None
        start_point = (float(image_start[0]), float(image_start[1]))
        end_point = (float(image_end[0]), float(image_end[1]))
        if mode == "roi":
            frame_array = self._get_frame_pixel_array(self.current_frame)
            if frame_array is None:
                return None
            if roi_bounds_exclusive:
                x0, y0, x1, y1 = self._normalize_roi_bounds(frame_array.shape, image_start, image_end)
            else:
                x0_raw = min(int(round(image_start[0])), int(round(image_end[0])))
                y0_raw = min(int(round(image_start[1])), int(round(image_end[1])))
                x1_raw = max(int(round(image_start[0])), int(round(image_end[0]))) + 1
                y1_raw = max(int(round(image_start[1])), int(round(image_end[1]))) + 1
                x0, y0, x1, y1 = self._normalize_roi_bounds(frame_array.shape, (x0_raw, y0_raw), (x1_raw, y1_raw))
            start_point = (float(x0), float(y0))
            end_point = (float(x1), float(y1))
        measurement = Measurement(
            id=str(uuid.uuid4()),
            kind=mode,
            start=start_point,
            end=end_point,
            frame_index=int(self.current_frame),
            geometry_key=geometry_key,
            summary_text="",
            meta={**(extra_meta or {})},
        )
        metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
        measurement.summary_text = metrics["summary"]
        measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
        self.persistent_measurements.append(measurement)
        self._append_measurement_history_entries(measurement, metrics)
        return measurement

    def _append_measurement_history_entries(self, measurement: Measurement, metrics: dict[str, Any]) -> None:
        if measurement.kind == "roi":
            target = self._display_name_for_roi_id(measurement.id)
            signal_stats = dict(metrics.get("signal_stats") or {})
            self._append_history_entry("ROI", target, "Mean", float(signal_stats.get("mean", 0.0)), "a.u.", "ROI 평균 신호", target_id=measurement.id)
            self._append_history_entry("ROI", target, "Std", float(signal_stats.get("std", 0.0)), "a.u.", "ROI 신호 표준편차", target_id=measurement.id)
            self._append_history_entry("ROI", target, "Min", float(signal_stats.get("min", 0.0)), "a.u.", "ROI 최소 신호", target_id=measurement.id)
            self._append_history_entry("ROI", target, "Max", float(signal_stats.get("max", 0.0)), "a.u.", "ROI 최대 신호", target_id=measurement.id)
            self._append_history_entry("ROI", target, "Area", float(metrics.get("area_px", 0.0)), "px²", "ROI 면적", target_id=measurement.id)
            return
        if measurement.kind == "line":
            line_index = self._line_index_for_measurement_id(measurement.id)
            target = f"Line {line_index}" if line_index is not None else "Line"
            self._append_history_entry("Line Profile", target, "Length(px)", float(metrics.get("length_px", 0.0)), "px", "선 길이", target_id=measurement.id)
            length_mm = metrics.get("length_mm")
            if isinstance(length_mm, (int, float)):
                self._append_history_entry("Line Profile", target, "Length(mm)", float(length_mm), "mm", "물리 길이", target_id=measurement.id)

    def _line_index_for_measurement_id(self, measurement_id: str) -> int | None:
        current_geometry = self._get_current_geometry_key()
        line_index = 0
        for measurement in self.persistent_measurements:
            if measurement.kind != "line":
                continue
            if not self._geometry_matches(measurement.geometry_key, current_geometry):
                continue
            if measurement.frame_index != self.current_frame:
                continue
            line_index += 1
            if measurement.id == measurement_id:
                return line_index
        return None

    def _propagate_rois_from_geometry(
        self,
        source_geometry_key: str | None,
        source_frame_index: int,
        navigation_step: int = 1,
    ) -> None:
        if not self.roi_propagation_enabled.get():
            return
        if source_geometry_key is None:
            return
        target_geometry_key = self._get_current_geometry_key()
        if target_geometry_key is None or target_geometry_key == source_geometry_key:
            return
        scope = self.roi_propagation_scope.get()
        if scope == "next" and abs(navigation_step) != 1:
            return

        source_rois = [
            measurement
            for measurement in self.persistent_measurements
            if measurement.kind == "roi"
            and measurement.frame_index == source_frame_index
            and self._geometry_matches(measurement.geometry_key, source_geometry_key)
        ]
        if not source_rois:
            return
        target_frame = np.asarray(self.frames[self.current_frame]) if self.frames else None
        if target_frame is None or target_frame.ndim < 2:
            return
        target_height, target_width = target_frame.shape[:2]

        for source in source_rois:
            if not self._roi_fits_target_frame(source, target_width, target_height):
                continue
            if self._has_equivalent_roi_for_target(source, target_geometry_key, self.current_frame):
                continue
            propagated = Measurement(
                id=str(uuid.uuid4()),
                kind="roi",
                start=(float(source.start[0]), float(source.start[1])),
                end=(float(source.end[0]), float(source.end[1])),
                frame_index=int(self.current_frame),
                geometry_key=target_geometry_key,
                summary_text="",
                meta=dict(source.meta or {}),
            )
            propagated.meta["propagated_from"] = source.id
            metrics = self.compute_measurement(propagated, self._get_frame_pixel_array(propagated.frame_index))
            propagated.summary_text = metrics["summary"]
            propagated.meta = self._canonicalize_measurement_meta(propagated, metrics)
            self.persistent_measurements.append(propagated)

    @staticmethod
    def _roi_fits_target_frame(source: Measurement, target_width: int, target_height: int) -> bool:
        x_values = (source.start[0], source.end[0])
        y_values = (source.start[1], source.end[1])
        return (
            min(x_values) >= 0
            and min(y_values) >= 0
            and max(x_values) <= target_width
            and max(y_values) <= target_height
        )

    @staticmethod
    def _roi_coordinates_match(left: Measurement, right: Measurement) -> bool:
        return (
            abs(left.start[0] - right.start[0]) < 0.5
            and abs(left.start[1] - right.start[1]) < 0.5
            and abs(left.end[0] - right.end[0]) < 0.5
            and abs(left.end[1] - right.end[1]) < 0.5
        )

    def _has_equivalent_roi_for_target(
        self,
        source: Measurement,
        target_geometry_key: str,
        target_frame_index: int,
    ) -> bool:
        for measurement in self.persistent_measurements:
            if measurement.kind != "roi":
                continue
            if measurement.frame_index != target_frame_index:
                continue
            if not self._geometry_matches(measurement.geometry_key, target_geometry_key):
                continue
            if self._roi_coordinates_match(measurement, source):
                return True
        return False

    def _draw_persistent_measurements(self) -> None:
        self.canvas.delete("persistent_measurement")
        self._persistent_canvas_item_to_measurement_id = {}
        current_geometry = self._get_current_geometry_key()
        grid_roi_measurements: list[Measurement] = []
        occupied_label_boxes: list[tuple[float, float, float, float]] = []
        for measurement in self.persistent_measurements:
            if not self._geometry_matches(current_geometry, measurement.geometry_key):
                continue
            start = self._image_coords_to_canvas(*measurement.start)
            end = self._image_coords_to_canvas(*measurement.end)
            if start is None or end is None:
                continue
            sx, sy = start
            ex, ey = end
            frame_array = self._get_frame_pixel_array(measurement.frame_index)
            metrics = self.compute_measurement(measurement, frame_array)
            measurement.summary_text = metrics["summary"]
            measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
            selected = measurement.id == self.selected_persistent_measurement_id
            if measurement.kind == "roi":
                outline = "#ffdc5e" if selected else "#ff7f50"
                item_id = self.canvas.create_rectangle(
                    sx, sy, ex, ey, outline=outline, width=3 if selected else 2, tags=("persistent_measurement",)
                )
                self.register_measurement_hit_target(item_id, measurement.id)
                roi_index = self._get_roi_display_index(measurement.id)
                if roi_index is not None:
                    badge_x = min(sx, ex) + 4
                    badge_y = min(sy, ey) + 4
                    badge_id = self.canvas.create_text(
                        badge_x,
                        badge_y,
                        text=f"{roi_index}",
                        fill="#111827",
                        anchor="nw",
                        font=("TkDefaultFont", 9, "bold"),
                        tags=("persistent_measurement",),
                    )
                    badge_bounds = self.canvas.bbox(badge_id)
                    if badge_bounds is not None:
                        bx0, by0, bx1, by1 = badge_bounds
                        bg_id = self.canvas.create_rectangle(
                            bx0 - 3,
                            by0 - 1,
                            bx1 + 3,
                            by1 + 1,
                            outline="",
                            fill="#fef08a",
                            tags=("persistent_measurement",),
                        )
                        self.canvas.tag_raise(badge_id, bg_id)
                        self.canvas.itemconfig(bg_id, state="disabled")
                    self.canvas.itemconfig(badge_id, state="disabled")
                if measurement.meta.get("grid_cell") is not None:
                    grid_roi_measurements.append(measurement)
                    continue
                primary_label, secondary_label = self._build_measurement_label_parts("roi", metrics, measurement)
                rect_box = (min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey))
                occupied_label_boxes.append(rect_box)
            elif measurement.kind == "line":
                color = "#e6ff7a" if selected else "#00ffaa"
                item_id = self.canvas.create_line(
                    sx, sy, ex, ey, fill=color, width=3 if selected else 2, tags=("persistent_measurement",)
                )
                self.register_measurement_hit_target(item_id, measurement.id)
                primary_label, secondary_label = self._build_measurement_label_parts("line", metrics, measurement)
            else:
                raw_points = measurement.meta.get("points", [])
                polygon_canvas: list[float] = []
                for point in raw_points:
                    if not isinstance(point, (list, tuple)) or len(point) < 2:
                        continue
                    canvas_point = self._image_pixel_to_canvas(int(point[0]), int(point[1]))
                    if canvas_point is None:
                        continue
                    polygon_canvas.extend(canvas_point)
                if len(polygon_canvas) < 6:
                    continue
                fill_color = "#ffe97f" if selected else "#8be9fd"
                item_id = self.canvas.create_polygon(
                    *polygon_canvas,
                    outline=fill_color,
                    fill="",
                    width=3 if selected else 2,
                    tags=("persistent_measurement",),
                )
                self.register_measurement_hit_target(item_id, measurement.id)
                primary_label = f"Poly {int(metrics.get('point_count', 0))}pts"
                secondary_label = f"Area {metrics['area_px']:.1f}px²"
                ex = sum(polygon_canvas[0::2]) / (len(polygon_canvas) // 2)
                ey = sum(polygon_canvas[1::2]) / (len(polygon_canvas) // 2)
            if measurement.kind == "roi":
                label_x, label_y, anchor, label_box = self._resolve_roi_label_position(
                    ex,
                    ey,
                    primary_label,
                    secondary_label,
                    occupied_label_boxes,
                )
                occupied_label_boxes.append(label_box)
            else:
                label_x, label_y, anchor = ex + 6, ey - 6, "sw"
            self._draw_measurement_label(
                self.canvas,
                label_x,
                label_y,
                primary_label,
                secondary_label,
                tags=("persistent_measurement",),
                anchor=anchor,
                non_interactive=True,
            )

        regions = self._build_grid_roi_regions(grid_roi_measurements)
        placed_boxes: list[tuple[float, float, float, float]] = []
        for region in regions:
            bounds: Rect = region["bounds"]
            x0, y0, x1, y1 = bounds.x1, bounds.y1, bounds.x2, bounds.y2
            width_px = int(max(x1 - x0, 0))
            height_px = int(max(y1 - y0, 0))
            label = self._format_grid_roi_region_summary(width_px, height_px, int(region["area_px"]))
            start = self._image_coords_to_canvas(float(x0), float(y0))
            end = self._image_coords_to_canvas(float(x1), float(y1))
            if start is None or end is None:
                continue
            sx, sy = start
            ex, _ = end
            lines = label.count("\n") + 1
            x = (sx + ex) / 2
            y = sy - 6
            estimated_width = max(len(line) for line in label.splitlines()) * 6
            estimated_height = lines * 14
            while any(
                not (x + estimated_width / 2 < bx0 or x - estimated_width / 2 > bx1 or y < by0 or y - estimated_height > by1)
                for bx0, by0, bx1, by1 in placed_boxes
            ):
                y += estimated_height + 4
            label_id = self.canvas.create_text(
                x,
                y,
                text=label,
                fill="#f8f8f8",
                anchor="s",
                font=("TkDefaultFont", 9, "bold"),
                tags=("persistent_measurement",),
            )
            self.canvas.itemconfig(label_id, state="disabled")
            placed_boxes.append((x - estimated_width / 2, y, x + estimated_width / 2, y - estimated_height))
        self._refresh_analysis_selectors()

    def export_measurements_csv(self) -> None:
        if not self.persistent_measurements:
            messagebox.showinfo("안내", "내보낼 영구 측정값이 없습니다.")
            return
        path = filedialog.asksaveasfilename(
            title="측정 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "id",
                    "kind",
                    "frame_index",
                    "start_x",
                    "start_y",
                    "end_x",
                    "end_y",
                    "summary",
                    "width_px",
                    "height_px",
                    "area_px",
                    "length_px",
                    "width_mm",
                    "height_mm",
                    "area_mm2",
                    "length_mm",
                    "geometry_key",
                    "meta",
                ]
            )
            for item in self.persistent_measurements:
                metrics = self.compute_measurement(item, self._get_frame_pixel_array(item.frame_index))
                item.summary_text = metrics["summary"]
                item.meta = self._canonicalize_measurement_meta(item, metrics)
                writer.writerow(
                    [
                        item.id,
                        item.kind,
                        item.frame_index,
                        f"{item.start[0]:.4f}",
                        f"{item.start[1]:.4f}",
                        f"{item.end[0]:.4f}",
                        f"{item.end[1]:.4f}",
                        item.summary_text,
                        f"{metrics['width_px']:.4f}",
                        f"{metrics['height_px']:.4f}",
                        f"{metrics['area_px']:.4f}",
                        f"{metrics['length_px']:.4f}",
                        "" if metrics["width_mm"] is None else f"{metrics['width_mm']:.4f}",
                        "" if metrics["height_mm"] is None else f"{metrics['height_mm']:.4f}",
                        "" if metrics["area_mm2"] is None else f"{metrics['area_mm2']:.4f}",
                        "" if metrics["length_mm"] is None else f"{metrics['length_mm']:.4f}",
                        item.geometry_key,
                        json.dumps(item.meta, ensure_ascii=False, sort_keys=True),
                    ]
                )
        messagebox.showinfo("저장 완료", f"CSV 저장 완료:\n{path}")

    def _serialize_measurement_set(self, measurement_set: MeasurementSet) -> dict[str, Any]:
        for measurement in measurement_set.measurements:
            metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
            measurement.summary_text = metrics["summary"]
            measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
        return {
            "id": measurement_set.id,
            "name": measurement_set.name,
            "geometry_key": measurement_set.geometry_key,
            "created_at": measurement_set.created_at,
            "measurements": [
                {
                    "id": measurement.id,
                    "kind": measurement.kind,
                    "start": list(measurement.start),
                    "end": list(measurement.end),
                    "frame_index": measurement.frame_index,
                    "geometry_key": measurement.geometry_key,
                    "summary_text": measurement.summary_text,
                    "meta": measurement.meta,
                }
                for measurement in measurement_set.measurements
            ],
        }

    def _deserialize_measurement_set(self, payload: dict[str, Any]) -> MeasurementSet:
        measurements: list[Measurement] = []
        for item in payload.get("measurements", []):
            measurement = Measurement(
                id=str(item.get("id", uuid.uuid4())),
                kind=str(item.get("kind", "line")),
                start=(float(item["start"][0]), float(item["start"][1])),
                end=(float(item["end"][0]), float(item["end"][1])),
                frame_index=int(item.get("frame_index", 0)),
                geometry_key=str(item.get("geometry_key", "")),
                summary_text=str(item.get("summary_text", "")),
                meta=dict(item.get("meta") or {}),
            )
            metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
            measurement.summary_text = metrics["summary"]
            measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
            measurements.append(measurement)
        return MeasurementSet(
            id=str(payload.get("id", uuid.uuid4())),
            name=str(payload.get("name", "Imported Set")),
            geometry_key=str(payload.get("geometry_key", "")),
            created_at=str(payload.get("created_at", datetime.utcnow().isoformat())),
            measurements=measurements,
        )

    def save_measurement_set(self) -> None:
        if not self.persistent_measurements:
            messagebox.showinfo("안내", "저장할 영구 측정값이 없습니다.")
            return
        geometry_key = self._get_current_geometry_key()
        if geometry_key is None:
            return
        name = simple_prompt(self.root, "세트 이름", "측정 세트 이름을 입력하세요:")
        if not name:
            return
        selected = [m for m in self.persistent_measurements if self._geometry_matches(m.geometry_key, geometry_key)]
        measurement_set = MeasurementSet(
            id=str(uuid.uuid4()),
            name=name,
            geometry_key=geometry_key,
            created_at=datetime.utcnow().isoformat(),
            measurements=copy.deepcopy(selected),
        )
        self.measurement_sets[measurement_set.id] = measurement_set
        messagebox.showinfo("저장 완료", f"세트 저장: {measurement_set.name} ({len(selected)}개)")

    def apply_measurement_set(self) -> None:
        if not self.measurement_sets:
            messagebox.showinfo("안내", "적용할 측정 세트가 없습니다.")
            return
        geometry_key = self._get_current_geometry_key()
        if geometry_key is None:
            return
        candidates = [item for item in self.measurement_sets.values() if self._geometry_matches(item.geometry_key, geometry_key)]
        if not candidates:
            messagebox.showwarning("기하 불일치", "현재 영상 기하와 일치하는 세트가 없습니다.")
            return
        selected = candidates[-1]
        copied = copy.deepcopy(selected.measurements)
        for item in copied:
            item.id = str(uuid.uuid4())
        self.persistent_measurements.extend(copied)
        self._draw_persistent_measurements()
        messagebox.showinfo("적용 완료", f"{selected.name} 세트를 추가 적용했습니다.")

    def export_measurement_sets_json(self) -> None:
        if not self.measurement_sets:
            messagebox.showinfo("안내", "내보낼 세트가 없습니다.")
            return
        path = filedialog.asksaveasfilename(
            title="측정 세트 JSON 저장",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        payload = {"measurement_sets": [self._serialize_measurement_set(item) for item in self.measurement_sets.values()]}
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("저장 완료", f"JSON 저장 완료:\n{path}")

    def import_measurement_sets_json(self) -> None:
        path = filedialog.askopenfilename(title="측정 세트 JSON 선택", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
        if not path:
            return
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        imported = 0
        for item in payload.get("measurement_sets", []):
            measurement_set = self._deserialize_measurement_set(item)
            while measurement_set.id in self.measurement_sets:
                measurement_set.id = str(uuid.uuid4())
            self.measurement_sets[measurement_set.id] = measurement_set
            imported += 1
        messagebox.showinfo("불러오기 완료", f"{imported}개 세트를 가져왔습니다.")

    @staticmethod
    def _serialize_measurement_for_session(measurement: Measurement) -> dict[str, Any]:
        return {
            "id": measurement.id,
            "type": measurement.kind,
            "frame_index": int(measurement.frame_index),
            "start": [float(measurement.start[0]), float(measurement.start[1])],
            "end": [float(measurement.end[0]), float(measurement.end[1])],
            "geometry_key": measurement.geometry_key,
            "label": measurement.summary_text,
            "meta": copy.deepcopy(measurement.meta),
            "role": str((measurement.meta or {}).get("role", "")),
            "points": copy.deepcopy((measurement.meta or {}).get("points", [])),
        }

    @staticmethod
    def _deserialize_measurement_for_session(payload: dict[str, Any]) -> Measurement:
        start = payload.get("start") or [0.0, 0.0]
        end = payload.get("end") or [0.0, 0.0]
        return Measurement(
            id=str(payload.get("id") or uuid.uuid4()),
            kind=str(payload.get("type", "line")),
            start=(float(start[0]), float(start[1])),
            end=(float(end[0]), float(end[1])),
            frame_index=int(payload.get("frame_index", 0)),
            geometry_key=str(payload.get("geometry_key", "")),
            summary_text=str(payload.get("label", "")),
            meta=dict(payload.get("meta") or {}),
        )

    def serialize_session(self) -> dict[str, Any]:
        current_path = self._get_current_image_path()
        roi_items = [item for item in self.persistent_measurements if item.kind == "roi"]
        line_items = [item for item in self.persistent_measurements if item.kind == "line"]
        return {
            "version": SESSION_SCHEMA_VERSION,
            "created_at": datetime.utcnow().isoformat(),
            "app": "moduba",
            "source_image_path": current_path,
            "frame_index": int(self.current_frame),
            "display": {
                "window_width": self.window_width_value,
                "window_level": self.window_level_value,
                "invert": bool(self.invert_display.get()),
                "zoom_scale": float(self.zoom_scale),
                "show_grid_overlay": bool(self.show_grid_overlay.get()),
            },
            "roi_list": [self._serialize_measurement_for_session(item) for item in roi_items],
            "line_list": [self._serialize_measurement_for_session(item) for item in line_items],
            "analysis_options": {key: var.get() for key, var in self.analysis_inputs.items()},
            "results_history": [self._serialize_history_entry(item) for item in self.result_history_store.entries()],
            "compare_state": {
                "selected_history_row_ids": list(self._session_compare_state.get("selected_entry_ids", [])),
                "baseline_index": int(self._session_compare_state.get("baseline_index", 0)),
            },
        }

    def deserialize_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        version = str(payload.get("version", "0"))
        display = dict(payload.get("display") or {})
        history_rows = [self._deserialize_history_entry(item) for item in (payload.get("results_history") or [])]
        roi_list = [self._deserialize_measurement_for_session(item) for item in (payload.get("roi_list") or [])]
        line_list = [self._deserialize_measurement_for_session(item) for item in (payload.get("line_list") or [])]
        return {
            "version": version,
            "source_image_path": str(payload.get("source_image_path", "")),
            "frame_index": int(payload.get("frame_index", 0)),
            "display": display,
            "analysis_options": dict(payload.get("analysis_options") or {}),
            "roi_list": roi_list,
            "line_list": line_list,
            "results_history": history_rows,
            "compare_state": dict(payload.get("compare_state") or {}),
        }

    def _reset_analysis_session_state(self) -> None:
        self.persistent_measurements.clear()
        self.selected_persistent_measurement_id = None
        self._persistent_canvas_item_to_measurement_id.clear()
        self.result_history_store.clear()
        self._session_compare_state = {"selected_entry_ids": [], "baseline_index": 0}
        self.line_profile_series_cache.clear()
        self.analysis_last_run = {}
        self._refresh_analysis_selectors()
        self._refresh_result_history_table()

    def _resolve_session_image_path(self, source_image_path: str) -> str:
        if source_image_path and Path(source_image_path).exists():
            return source_image_path
        if source_image_path:
            replacement = filedialog.askopenfilename(
                title="Session image not found - DICOM 파일 재지정",
                filetypes=[("DICOM 파일", "*.dcm *.DCM"), ("모든 파일", "*.*")],
            )
            if replacement:
                return replacement
        return ""

    def apply_session(self, session_data: dict[str, Any]) -> None:
        source_image_path = self._resolve_session_image_path(session_data.get("source_image_path", ""))
        self._reset_analysis_session_state()
        if source_image_path:
            self._reset_file_list_state()
            self._set_loaded_paths([source_image_path], folder=None)
            self._load_file(0, preserve_view_state=False)
        else:
            messagebox.showwarning("Session Load", "image not found: 이미지 경로를 확인하세요.")

        if self.frames:
            requested_frame = int(session_data.get("frame_index", 0))
            if 0 <= requested_frame < len(self.frames):
                self.current_frame = requested_frame

        display = session_data.get("display") or {}
        self.window_width_value = display.get("window_width")
        self.window_level_value = display.get("window_level")
        self.invert_display.set(bool(display.get("invert", False)))
        self.show_grid_overlay.set(bool(display.get("show_grid_overlay", False)))
        try:
            self.zoom_scale = float(display.get("zoom_scale", self.zoom_scale))
        except (TypeError, ValueError):
            pass
        if self.frames:
            self._show_frame()

        restored_measurements: list[Measurement] = []
        for measurement in list(session_data.get("roi_list") or []) + list(session_data.get("line_list") or []):
            frame_array = self._get_frame_pixel_array(measurement.frame_index)
            metrics = self.compute_measurement(measurement, frame_array)
            measurement.summary_text = metrics.get("summary", measurement.summary_text)
            measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
            restored_measurements.append(measurement)
        self.persistent_measurements = restored_measurements
        self._draw_persistent_measurements()

        for key, value in (session_data.get("analysis_options") or {}).items():
            if key in self.analysis_inputs:
                self.analysis_inputs[key].set(str(value))
        self._refresh_analysis_selectors()
        self._sync_analysis_selector_inputs()
        self._toggle_cnr_noise_widgets()

        for entry in session_data.get("results_history", []):
            self.result_history_store.append(entry)
        compare_state = dict(session_data.get("compare_state") or {})
        self._session_compare_state = {
            "selected_entry_ids": list(compare_state.get("selected_history_row_ids") or []),
            "baseline_index": int(compare_state.get("baseline_index", 0)),
        }
        self._refresh_result_history_table()
        self._restore_history_selection(self._session_compare_state.get("selected_entry_ids", []))

    def save_analysis_session(self) -> None:
        path = filedialog.asksaveasfilename(
            title="세션 저장",
            defaultextension=".moduba.json",
            filetypes=[("Moduba Session", "*.moduba.json"), ("JSON", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        payload = self.serialize_session()
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Session Save", f"세션 저장 완료:\n{path}")

    def load_analysis_session(self) -> None:
        path = filedialog.askopenfilename(
            title="세션 불러오기",
            filetypes=[("Moduba Session", "*.moduba.json"), ("JSON", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        session_data = self.deserialize_session(payload)
        if session_data["version"] != SESSION_SCHEMA_VERSION:
            messagebox.showwarning(
                "Session Version",
                f"세션 버전 불일치: file={session_data['version']}, app={SESSION_SCHEMA_VERSION}\n가능한 항목만 복원합니다.",
            )
        self.apply_session(session_data)

    @staticmethod
    def _preset_analysis_option_keys() -> tuple[str, ...]:
        return (
            "cnr_formula",
            "uniformity_formula",
            "uniformity_input_mode",
            "uniformity_role_filter",
        )

    def _collect_roi_role_template(self) -> dict[str, str]:
        role_map: dict[str, str] = {}
        display_map = self._build_roi_display_name_map()
        for measurement in self.persistent_measurements:
            if measurement.kind != "roi":
                continue
            role = self._get_measurement_roi_role(measurement)
            if role is None:
                continue
            label = display_map.get(measurement.id)
            if label:
                role_map[role] = label
        return role_map

    def serialize_preset(self) -> dict[str, Any]:
        analysis_options = {
            key: self.analysis_inputs[key].get()
            for key in self._preset_analysis_option_keys()
            if key in self.analysis_inputs
        }
        return {
            "version": PRESET_SCHEMA_VERSION,
            "created_at": datetime.utcnow().isoformat(),
            "app": "moduba",
            "kind": "measurement_preset",
            "analysis_options": analysis_options,
            "measurement_roles": self._collect_roi_role_template(),
            "ui_defaults": {
                "show_grid_overlay": bool(self.show_grid_overlay.get()),
                "show_basic_overlay": bool(self.show_basic_overlay.get()),
                "show_acquisition_overlay": bool(self.show_acquisition_overlay.get()),
            },
            "repeat_rules": {
                "uniformity_role_filter": self.analysis_inputs["uniformity_role_filter"].get(),
                "line_profile_mode": "summary_only",
            },
        }

    def deserialize_preset(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": str(payload.get("version", "0")),
            "analysis_options": dict(payload.get("analysis_options") or {}),
            "measurement_roles": {str(k): str(v) for k, v in dict(payload.get("measurement_roles") or {}).items()},
            "ui_defaults": dict(payload.get("ui_defaults") or {}),
            "repeat_rules": dict(payload.get("repeat_rules") or {}),
        }

    def apply_preset(self, preset_data: dict[str, Any]) -> None:
        for key, value in preset_data.get("analysis_options", {}).items():
            if key in self.analysis_inputs:
                self.analysis_inputs[key].set(str(value))

        for key, value in preset_data.get("ui_defaults", {}).items():
            if key == "show_grid_overlay":
                self.show_grid_overlay.set(bool(value))
            elif key == "show_basic_overlay":
                self.show_basic_overlay.set(bool(value))
            elif key == "show_acquisition_overlay":
                self.show_acquisition_overlay.set(bool(value))

        role_templates = dict(preset_data.get("measurement_roles") or {})
        if role_templates:
            label_to_id = {label: measurement_id for measurement_id, label in self._build_roi_display_name_map().items()}
            for role, label in role_templates.items():
                measurement_id = label_to_id.get(label)
                measurement = self._find_measurement_by_id(measurement_id, expected_kind="roi")
                normalized = self._normalize_roi_role(role)
                if measurement is None or normalized is None:
                    continue
                measurement.meta = dict(measurement.meta or {})
                measurement.meta["role"] = normalized
                metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
                measurement.summary_text = metrics["summary"]
                measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)

        self._refresh_grid_overlay()
        self._refresh_analysis_selectors()
        self._sync_analysis_selector_inputs()
        self._toggle_cnr_noise_widgets()
        self._auto_bind_analysis_inputs_from_roles(overwrite_existing=True)
        self._update_analysis_action_button_state()
        self._draw_persistent_measurements()

    def save_measurement_preset(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Preset 저장",
            defaultextension=".moduba.preset.json",
            filetypes=[("Moduba Preset", "*.moduba.preset.json"), ("JSON", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        payload = self.serialize_preset()
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Preset Save", f"Preset 저장 완료:\n{path}")

    def load_measurement_preset(self) -> None:
        path = filedialog.askopenfilename(
            title="Preset 불러오기",
            filetypes=[("Moduba Preset", "*.moduba.preset.json"), ("JSON", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        preset_data = self.deserialize_preset(payload)
        if preset_data["version"] != PRESET_SCHEMA_VERSION:
            messagebox.showwarning(
                "Preset Version",
                f"Preset 버전 불일치: file={preset_data['version']}, app={PRESET_SCHEMA_VERSION}\n가능한 항목만 적용합니다.",
            )
        self.apply_preset(preset_data)

    def _get_frame_pixel_array(self, frame_index: int) -> np.ndarray | None:
        if not self.frames or not (0 <= frame_index < len(self.frames)):
            return None
        frame = np.asarray(self.frames[frame_index], dtype=np.float32)
        if frame.ndim == 3:
            frame = frame.mean(axis=-1)
        if frame.ndim != 2:
            return None
        return frame

    def extract_line_profile(self, measurement: Measurement) -> dict[str, Any] | None:
        frame = self._get_frame_pixel_array(measurement.frame_index)
        if frame is None:
            return None
        x0, y0 = measurement.start
        x1, y1 = measurement.end
        sample_count = int(max(np.ceil(np.hypot(x1 - x0, y1 - y0)) + 1, 2))
        xs = np.linspace(x0, x1, num=sample_count, dtype=np.float64)
        ys = np.linspace(y0, y1, num=sample_count, dtype=np.float64)
        xi = np.clip(np.round(xs).astype(int), 0, frame.shape[1] - 1)
        yi = np.clip(np.round(ys).astype(int), 0, frame.shape[0] - 1)
        intensity = frame[yi, xi].astype(np.float64)
        distance_px = np.zeros(sample_count, dtype=np.float64)
        if sample_count > 1:
            step_px = np.hypot(np.diff(xs), np.diff(ys))
            distance_px[1:] = np.cumsum(step_px)
        spacing = self._get_pixel_spacing_mm()
        distance_mm: np.ndarray | None = None
        if spacing is not None:
            row_mm, col_mm = float(spacing[0]), float(spacing[1])
            distance_mm = np.zeros(sample_count, dtype=np.float64)
            if sample_count > 1:
                step_mm = np.hypot(np.diff(xs) * col_mm, np.diff(ys) * row_mm)
                distance_mm[1:] = np.cumsum(step_mm)
        return {
            "distance_px": distance_px,
            "distance_mm": distance_mm,
            "intensity": intensity,
            "sample_count": int(sample_count),
            "start": (float(x0), float(y0)),
            "end": (float(x1), float(y1)),
        }

    def summarize_line_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        intensity = np.asarray(profile.get("intensity", []), dtype=np.float64)
        if intensity.size == 0:
            return {
                "sample_count": 0,
                "min_intensity": 0.0,
                "max_intensity": 0.0,
                "mean_intensity": 0.0,
                "std_intensity": 0.0,
                "length_px": 0.0,
                "length_mm": None,
                "peak_count": 0,
                "valley_count": 0,
            }
        distance_px = np.asarray(profile.get("distance_px", []), dtype=np.float64)
        distance_mm_raw = profile.get("distance_mm")
        distance_mm = None if distance_mm_raw is None else np.asarray(distance_mm_raw, dtype=np.float64)
        peaks = np.where((intensity[1:-1] > intensity[:-2]) & (intensity[1:-1] > intensity[2:]))[0] + 1
        valleys = np.where((intensity[1:-1] < intensity[:-2]) & (intensity[1:-1] < intensity[2:]))[0] + 1
        features = self.compute_profile_features(profile)
        return {
            "sample_count": int(intensity.size),
            "min_intensity": float(np.min(intensity)),
            "max_intensity": float(np.max(intensity)),
            "mean_intensity": float(np.mean(intensity)),
            "std_intensity": float(np.std(intensity)),
            "length_px": float(distance_px[-1]) if distance_px.size else 0.0,
            "length_mm": None if distance_mm is None or distance_mm.size == 0 else float(distance_mm[-1]),
            "peak_count": int(peaks.size),
            "valley_count": int(valleys.size),
            "peak_value": features.get("peak_value"),
            "peak_position": features.get("peak_position"),
            "valley_value": features.get("valley_value"),
            "valley_position": features.get("valley_position"),
            "fwhm": features.get("fwhm"),
            "distance_unit": features.get("distance_unit", "px"),
        }

    def render_line_profile_chart(self, measurement: Measurement, profile: dict[str, Any], summary: dict[str, Any]) -> None:
        distance_px = np.asarray(profile.get("distance_px", []), dtype=np.float64)
        distance_mm_raw = profile.get("distance_mm")
        distance_mm = None if distance_mm_raw is None else np.asarray(distance_mm_raw, dtype=np.float64)
        intensity = np.asarray(profile.get("intensity", []), dtype=np.float64)
        if intensity.size == 0:
            return
        line_index = self._line_index_for_measurement_id(measurement.id)
        line_label = f"Line {line_index}" if line_index is not None else measurement.id[:8]
        use_mm_axis = distance_mm is not None and distance_mm.size == intensity.size
        x_values = distance_mm if use_mm_axis else distance_px
        x_label = "Distance (mm)" if use_mm_axis else "Distance (px)"
        plt.figure(figsize=(7, 4))
        plt.plot(x_values, intensity, color="#0a84ff")
        plt.xlabel(x_label)
        plt.ylabel("Intensity")
        plt.title(f"{line_label} | n={summary['sample_count']} | L={summary['length_px']:.2f}px")
        plt.tight_layout()
        plt.show(block=False)

    def show_line_profile_for_selected_line(self) -> None:
        context = self._prepare_selected_line_profile_context(show_warning=True)
        if context is None:
            return
        measurement = context["measurement"]
        profile = context["profile"]
        summary = context["summary"]
        metrics = context["metrics"]
        line_label = context["line_label"]
        fwhm_text = "N/A" if summary["fwhm"] is None else f"{summary['fwhm']:.2f}{summary['distance_unit']}"
        self.analysis_results["line_info"].set(
            f"{line_label} | mean {summary['mean_intensity']:.2f} | peak {summary['peak_value']:.2f} | FWHM {fwhm_text}"
        )
        self.analysis_last_run["line_profile"] = {
            "inputs": {
                "line_id": measurement.id,
            },
            "factors": self._collect_analysis_factors(measurement),
            "result": {
                "length_px": float(metrics["length_px"]),
                "length_mm": summary["length_mm"],
                "sample_count": int(summary["sample_count"]),
                "min_intensity": float(summary["min_intensity"]),
                "max_intensity": float(summary["max_intensity"]),
                "mean_intensity": float(summary["mean_intensity"]),
                "std_intensity": float(summary["std_intensity"]),
                "peak_count": int(summary["peak_count"]),
                "valley_count": int(summary["valley_count"]),
                "peak_value": summary["peak_value"],
                "peak_position": summary["peak_position"],
                "valley_value": summary["valley_value"],
                "valley_position": summary["valley_position"],
                "fwhm": summary["fwhm"],
                "distance_unit": summary["distance_unit"],
                "distance_px": np.asarray(profile["distance_px"], dtype=np.float64).tolist(),
                "distance_mm": None
                if profile.get("distance_mm") is None
                else np.asarray(profile["distance_mm"], dtype=np.float64).tolist(),
                "intensity": np.asarray(profile["intensity"], dtype=np.float64).tolist(),
            },
        }
        cache_key = self._line_profile_cache_key(self._get_current_image_path(), self.current_frame, measurement.id)
        self.line_profile_series_cache[cache_key] = {
            "distance_px": np.asarray(profile.get("distance_px", []), dtype=np.float64).tolist(),
            "distance_mm": None
            if profile.get("distance_mm") is None
            else np.asarray(profile.get("distance_mm", []), dtype=np.float64).tolist(),
            "intensity": np.asarray(profile.get("intensity", []), dtype=np.float64).tolist(),
        }
        self._refresh_analysis_results_panel()
        fwhm_summary = "N/A" if summary["fwhm"] is None else f"{summary['fwhm']:.2f}{summary['distance_unit']}"
        mean_note = (
            f"samples={summary['sample_count']}, peak={summary['peak_value']:.2f}, "
            f"fwhm={fwhm_summary}"
        )
        self._append_history_entry(
            measurement_type="Line Profile",
            target_name=line_label,
            metric="ProfileMean",
            value=float(summary["mean_intensity"]),
            unit="a.u.",
            note=mean_note,
            measurement_mode="analysis",
            target_id=measurement.id,
        )
        self._append_history_entry(
            measurement_type="Line Profile",
            target_name=line_label,
            metric="ProfileStd",
            value=float(summary["std_intensity"]),
            unit="a.u.",
            note=f"samples={summary['sample_count']}, peaks={summary['peak_count']}, valleys={summary['valley_count']}",
            measurement_mode="analysis",
            target_id=measurement.id,
        )
        self._append_history_entry(
            measurement_type="Line Profile",
            target_name=line_label,
            metric="Length(px)",
            value=float(summary["length_px"]),
            unit="px",
            note="Profile axis length",
            measurement_mode="analysis",
            target_id=measurement.id,
        )
        if isinstance(summary["length_mm"], (int, float)):
            self._append_history_entry(
                measurement_type="Line Profile",
                target_name=line_label,
                metric="Length(mm)",
                value=float(summary["length_mm"]),
                unit="mm",
                note="Pixel spacing 반영 길이",
                measurement_mode="analysis",
                target_id=measurement.id,
            )
        self._append_history_entry(
            measurement_type="Line Profile",
            target_name=line_label,
            metric="ProfileMin",
            value=float(summary["min_intensity"]),
            unit="a.u.",
            note="Profile minimum intensity",
            measurement_mode="analysis",
            target_id=measurement.id,
        )
        self._append_history_entry(
            measurement_type="Line Profile",
            target_name=line_label,
            metric="ProfileMax",
            value=float(summary["max_intensity"]),
            unit="a.u.",
            note="Profile maximum intensity",
            measurement_mode="analysis",
            target_id=measurement.id,
        )
        if isinstance(summary.get("peak_value"), (int, float)):
            self._append_history_entry(
                measurement_type="Line Profile",
                target_name=line_label,
                metric="PeakValue",
                value=float(summary["peak_value"]),
                unit="a.u.",
                note=f"peak_position={summary['peak_position']:.2f} {summary['distance_unit']}",
                measurement_mode="analysis",
                target_id=measurement.id,
            )
        if isinstance(summary.get("fwhm"), (int, float)):
            self._append_history_entry(
                measurement_type="Line Profile",
                target_name=line_label,
                metric="FWHM",
                value=float(summary["fwhm"]),
                unit=str(summary["distance_unit"]),
                note="Full Width at Half Maximum",
                measurement_mode="analysis",
                target_id=measurement.id,
            )
        self.render_line_profile_chart(measurement, profile, summary)

    def _prepare_selected_line_profile_context(self, show_warning: bool = False) -> dict[str, Any] | None:
        measurement = self._get_selected_measurement_from_analysis("line", "line_profile_line_id", "line_profile")
        if measurement is None:
            self.analysis_results["line_info"].set("Line: Select Profile Line")
            if show_warning:
                messagebox.showinfo("안내", "Profile Line을 선택하세요.")
            return None
        profile = self.extract_line_profile(measurement)
        if profile is None:
            if show_warning:
                messagebox.showwarning("Line Profile", "선택한 라인에서 프로파일을 계산할 수 없습니다.")
            return None
        summary = self.summarize_line_profile(profile)
        metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
        line_index = self._line_index_for_measurement_id(measurement.id)
        line_label = f"Line {line_index}" if line_index is not None else measurement.id[:8]
        return {
            "measurement": measurement,
            "profile": profile,
            "summary": summary,
            "metrics": metrics,
            "line_label": line_label,
        }

    def show_line_profile_feature_details(self) -> None:
        context = self._prepare_selected_line_profile_context(show_warning=True)
        if context is None:
            return
        summary = context["summary"]
        line_label = context["line_label"]
        peak_text = (
            "N/A"
            if not isinstance(summary.get("peak_value"), (int, float))
            else f"{float(summary['peak_value']):.2f} @ {float(summary['peak_position']):.2f} {summary['distance_unit']}"
        )
        valley_text = (
            "N/A"
            if not isinstance(summary.get("valley_value"), (int, float))
            else f"{float(summary['valley_value']):.2f} @ {float(summary['valley_position']):.2f} {summary['distance_unit']}"
        )
        fwhm_text = "N/A" if not isinstance(summary.get("fwhm"), (int, float)) else f"{float(summary['fwhm']):.2f} {summary['distance_unit']}"
        messagebox.showinfo(
            "Line Profile Details",
            (
                f"{line_label}\n"
                f"Samples: {summary['sample_count']}\n"
                f"Length: {summary['length_px']:.2f} px"
                + ("" if summary["length_mm"] is None else f" ({float(summary['length_mm']):.2f} mm)")
                + "\n"
                f"Mean/Std: {summary['mean_intensity']:.2f} / {summary['std_intensity']:.2f}\n"
                f"Peak: {peak_text}\n"
                f"Valley: {valley_text}\n"
                f"FWHM: {fwhm_text}"
            ),
        )

    def export_selected_line_profile_csv(self) -> None:
        context = self._prepare_selected_line_profile_context(show_warning=True)
        if context is None:
            return
        profile = context["profile"]
        line_label = str(context["line_label"]).replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="라인 프로파일 CSV 저장",
            defaultextension=".csv",
            initialfile=f"{line_label}_profile.csv",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")],
        )
        if not path:
            return
        distance_px = np.asarray(profile.get("distance_px", []), dtype=np.float64)
        distance_mm = None if profile.get("distance_mm") is None else np.asarray(profile.get("distance_mm", []), dtype=np.float64)
        intensity = np.asarray(profile.get("intensity", []), dtype=np.float64)
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["distance_px", "distance_mm", "intensity"])
            for index, value in enumerate(intensity):
                mm_value = "" if distance_mm is None else f"{float(distance_mm[index]):.6f}"
                writer.writerow([f"{float(distance_px[index]):.6f}", mm_value, f"{float(value):.6f}"])
        messagebox.showinfo("Line Profile Export", f"CSV 저장 완료:\n{path}")

    def _parse_uniformity_role_filter(self) -> set[str]:
        raw = self.analysis_inputs["uniformity_role_filter"].get()
        parsed = {item.strip().lower() for item in raw.split(",") if item.strip()}
        valid_roles = set(self._valid_roi_roles())
        return {item for item in parsed if item in valid_roles}

    def _collect_uniformity_roi_set(self) -> tuple[list[Measurement], str]:
        mode = self.analysis_inputs["uniformity_input_mode"].get()
        current_geometry = self._get_current_geometry_key()
        if mode == "role_group":
            roles = self._parse_uniformity_role_filter()
            if not roles:
                return [], "role_group(empty role filter)"
            candidates = [
                measurement
                for measurement in self.persistent_measurements
                if measurement.kind == "roi"
                and measurement.frame_index == self.current_frame
                and self._geometry_matches(measurement.geometry_key, current_geometry)
                and self._get_measurement_roi_role(measurement) in roles
            ]
            return candidates, f"role_group({','.join(sorted(roles))})"

        selected_ids: list[str] = []
        listbox = self._uniformity_roi_listbox
        if listbox is not None:
            option_map = self._analysis_option_maps.get("roi", {})
            labels = list(option_map.keys())
            for index in listbox.curselection():
                if 0 <= index < len(labels):
                    measurement_id = option_map.get(labels[index], "")
                    if measurement_id:
                        selected_ids.append(measurement_id)
        if not selected_ids:
            raw_ids = self.analysis_inputs["uniformity_roi_ids"].get()
            selected_ids = [item.strip() for item in raw_ids.split(",") if item.strip()]
        else:
            self.analysis_inputs["uniformity_roi_ids"].set(",".join(selected_ids))
        selected_lookup = set(selected_ids)
        candidates = [
            measurement
            for measurement in self.persistent_measurements
            if measurement.kind == "roi"
            and measurement.id in selected_lookup
            and measurement.frame_index == self.current_frame
            and self._geometry_matches(measurement.geometry_key, current_geometry)
        ]
        return candidates, "selected_rois"

    def _uniformity_formula_definitions(self) -> dict[str, dict[str, Any]]:
        return {
            "max_min": {
                "label": "U_max_min = (1 - (max - min) / (max + min)) * 100",
                "calculator": lambda stats: None
                if (stats["max"] + stats["min"]) <= 0
                else float((1.0 - ((stats["max"] - stats["min"]) / (stats["max"] + stats["min"]))) * 100.0),
            },
            "std_mean": {
                "label": "U_std = (1 - std / mean) * 100",
                "calculator": lambda stats: None
                if stats["mean"] <= 0
                else float((1.0 - (stats["std"] / stats["mean"])) * 100.0),
            },
        }

    def calculate_uniformity_from_inputs(self) -> None:
        roi_set, source = self._collect_uniformity_roi_set()
        roi_ids = [measurement.id for measurement in roi_set]
        formula_key = self.analysis_inputs["uniformity_formula"].get()
        formulas = self._uniformity_formula_definitions()
        selected_formula = formulas.get(formula_key, formulas["max_min"])
        uniformity_payload: dict[str, Any] = {
            "metric": "uniformity",
            "status": "missing",
            "reason": "",
            "preview_text": "",
            "result_text": "",
            "inputs": {
                "source": source,
                "roi_count": int(len(roi_set)),
                "roi_ids": roi_ids,
                "formula": formula_key,
                "formula_label": selected_formula["label"],
            },
            "factors": [self._collect_analysis_factors(measurement) for measurement in roi_set],
            "stats": {},
            "result": {
                "value": None,
                "formula": formula_key,
                "formula_label": selected_formula["label"],
            },
        }
        if not roi_set:
            preview_text = "ROI set not selected"
            result_text = "Uniformity unavailable"
            self.analysis_results["uniformity_preview"].set("ROI selection required")
            self.analysis_results["uniformity_result"].set(result_text)
            uniformity_payload["status"] = "missing"
            uniformity_payload["reason"] = "no ROI set"
            uniformity_payload["preview_text"] = f"Preview: {preview_text}"
            uniformity_payload["result_text"] = result_text
            self.analysis_last_run["uniformity"] = uniformity_payload
            self._refresh_analysis_results_panel()
            messagebox.showinfo("Uniformity", "Uniformity 계산에 사용할 ROI 집합이 비어 있습니다.")
            return
        samples: list[np.ndarray] = []
        for measurement in roi_set:
            frame = self._get_frame_pixel_array(measurement.frame_index)
            roi_pixels, _bounds = self._extract_roi_pixels(frame, measurement.start, measurement.end, ensure_non_empty=False)
            if roi_pixels.size > 0:
                samples.append(roi_pixels.reshape(-1))
        if not samples:
            preview_text = "Selected ROIs are empty"
            result_text = "Uniformity unavailable"
            self.analysis_results["uniformity_preview"].set(preview_text)
            self.analysis_results["uniformity_result"].set(result_text)
            uniformity_payload["status"] = "missing"
            uniformity_payload["reason"] = "ROI pixels unavailable"
            uniformity_payload["preview_text"] = f"Preview: {preview_text}"
            uniformity_payload["result_text"] = result_text
            self.analysis_last_run["uniformity"] = uniformity_payload
            self._refresh_analysis_results_panel()
            messagebox.showinfo("Uniformity", "선택된 ROI에서 유효한 픽셀을 찾지 못했습니다.")
            return
        values = np.concatenate(samples)
        aggregate_stats = {
            "max": float(np.max(values)),
            "min": float(np.min(values)),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "pixel_count": int(values.size),
        }
        uniformity_payload["stats"] = aggregate_stats
        uniformity_payload["inputs"] = {
            "source": source,
            "roi_count": int(len(roi_set)),
            "roi_ids": roi_ids,
            "formula": formula_key,
            "formula_label": selected_formula["label"],
        }
        uniformity_payload["factors"] = [self._collect_analysis_factors(measurement) for measurement in roi_set]
        uniformity_value = selected_formula["calculator"](aggregate_stats)
        preview_text = f"{len(roi_set)} ROIs selected"
        if uniformity_value is None:
            result_text = "Uniformity unavailable"
            self.analysis_results["uniformity_preview"].set(preview_text)
            self.analysis_results["uniformity_result"].set(result_text)
            uniformity_payload["status"] = "invalid"
            uniformity_payload["reason"] = "invalid denominator"
            uniformity_payload["preview_text"] = f"Preview: {preview_text}"
            uniformity_payload["result_text"] = result_text
            uniformity_payload["result"] = {
                "value": None,
                "formula": formula_key,
                "formula_label": selected_formula["label"],
            }
            self.analysis_last_run["uniformity"] = uniformity_payload
            self._refresh_analysis_results_panel()
            messagebox.showwarning("Uniformity", "선택한 공식에서 분모가 0 또는 음수입니다.")
            return
        result_text = f"Uniformity: {uniformity_value:.2f}"
        self.analysis_results["uniformity_preview"].set(preview_text)
        self.analysis_results["uniformity_result"].set(result_text)
        uniformity_payload["status"] = "success"
        uniformity_payload["reason"] = ""
        uniformity_payload["preview_text"] = f"Preview: {preview_text}"
        uniformity_payload["result_text"] = result_text
        uniformity_payload["result"] = {
            "value": float(uniformity_value),
            "formula": formula_key,
            "formula_label": selected_formula["label"],
        }
        self.analysis_last_run["uniformity"] = uniformity_payload
        self._refresh_analysis_results_panel()
        self._append_analysis_history_row(
            {
                "metric_name": "UNIFORMITY",
                "item_name": "Uniformity",
                "stats": aggregate_stats,
                "result_value": float(uniformity_value),
            },
            unit="%",
            related_target_ids=roi_ids,
        )

    def calculate_snr_from_inputs(self) -> None:
        self._auto_bind_analysis_inputs_from_roles(overwrite_existing=False)
        signal_roi = self._get_selected_measurement_from_analysis("roi", "snr_signal_roi_id", "snr_signal")
        noise_roi = self._get_selected_measurement_from_analysis("roi", "snr_background_roi_id", "snr_noise")
        signal_roi_id = signal_roi.id if signal_roi is not None else self._read_analysis_selected_id("roi", "snr_signal_roi_id", "snr_signal")
        noise_roi_id = noise_roi.id if noise_roi is not None else self._read_analysis_selected_id("roi", "snr_background_roi_id", "snr_noise")
        snr_payload: dict[str, Any] = {
            "status": "missing",
            "reason": "",
            "signal_roi_id": signal_roi_id,
            "noise_roi_id": noise_roi_id,
            "mean_signal": None,
            "std_noise": None,
            "inputs": {
                "signal_roi_id": signal_roi_id,
                "noise_roi_id": noise_roi_id,
            },
            "factors": {
                "signal": {} if signal_roi is None else self._collect_analysis_factors(signal_roi),
                "noise": {} if noise_roi is None else self._collect_analysis_factors(noise_roi),
            },
            "formula": "mean(Signal ROI) / std(Noise ROI)",
            "preview": "",
            "preview_text": "",
            "result": None,
            "result_text": "",
        }
        if signal_roi is None or noise_roi is None:
            missing: list[str] = []
            if signal_roi is None:
                missing.append("signal role(또는 Signal ROI 수동 선택)")
            if noise_roi is None:
                missing.append("background/noise role(또는 Noise ROI 수동 선택)")
            reason = " + ".join(missing)
            preview_text = "ROI selection required"
            result_text = "SNR unavailable"
            self.analysis_results["snr_preview"].set(preview_text)
            self.analysis_results["snr_result"].set(result_text)
            snr_payload["status"] = "missing"
            snr_payload["reason"] = reason
            snr_payload["preview"] = preview_text
            snr_payload["preview_text"] = f"Preview: {preview_text}"
            snr_payload["result_text"] = result_text
            self.analysis_last_run["snr"] = snr_payload
            self._refresh_analysis_results_panel()
            messagebox.showinfo("SNR", "SNR 계산에 필요한 ROI가 부족합니다.\nrole 지정 또는 수동 선택을 확인하세요.")
            return
        signal_metrics = self.compute_measurement(signal_roi, self._get_frame_pixel_array(signal_roi.frame_index))
        noise_metrics = self.compute_measurement(noise_roi, self._get_frame_pixel_array(noise_roi.frame_index))
        signal_mean = float((signal_metrics.get("signal_stats") or {}).get("mean", 0.0))
        noise_std = float((noise_metrics.get("signal_stats") or {}).get("std", 0.0))
        preview_text = "Signal ROI selected / Noise ROI selected"
        self.analysis_results["snr_preview"].set(preview_text)
        snr_payload["signal_roi_id"] = signal_roi.id
        snr_payload["noise_roi_id"] = noise_roi.id
        snr_payload["inputs"] = {
            "signal_roi_id": signal_roi.id,
            "noise_roi_id": noise_roi.id,
        }
        snr_payload["factors"] = {
            "signal": self._collect_analysis_factors(signal_roi),
            "noise": self._collect_analysis_factors(noise_roi),
        }
        snr_payload["mean_signal"] = float(signal_mean)
        snr_payload["std_noise"] = float(noise_std)
        snr_payload["preview"] = f"{signal_mean:.4f} / {noise_std:.4f}"
        snr_payload["preview_text"] = f"Preview: {preview_text}"
        if noise_std <= 0:
            result_text = "SNR unavailable"
            self.analysis_results["snr_result"].set(result_text)
            snr_payload["status"] = "invalid"
            snr_payload["reason"] = "noise std <= 0"
            snr_payload["result"] = None
            snr_payload["result_text"] = result_text
            self.analysis_last_run["snr"] = snr_payload
            self._refresh_analysis_results_panel()
            messagebox.showwarning("SNR", "Noise ROI 표준편차가 0입니다.")
            return
        snr = signal_mean / noise_std
        result_text = f"Signal Mean: {signal_mean:.2f} | Noise SD: {noise_std:.2f} | SNR: {snr:.2f}"
        self.analysis_results["snr_result"].set(result_text)
        snr_payload["status"] = "success"
        snr_payload["reason"] = ""
        snr_payload["result"] = float(snr)
        snr_payload["result_text"] = result_text
        self.analysis_last_run["snr"] = snr_payload
        self._refresh_analysis_results_panel()
        self._append_analysis_history_row(
            {
                "metric_name": "SNR",
                "item_name": "SNR",
                "stats": {"mean_signal": signal_mean, "std_noise": noise_std},
                "result_value": float(snr),
            },
            unit="ratio",
            related_target_ids=[signal_roi.id, noise_roi.id],
        )

    def calculate_cnr_from_inputs(self) -> None:
        self._auto_bind_analysis_inputs_from_roles(overwrite_existing=False)
        formula = self.analysis_inputs["cnr_formula"].get()
        target_roi = self._get_selected_measurement_from_analysis("roi", "cnr_target_roi_id", "cnr_target")
        reference_roi = self._get_selected_measurement_from_analysis("roi", "cnr_reference_roi_id", "cnr_reference")
        noise_roi = None
        if formula == "standard_noise":
            noise_roi = self._get_selected_measurement_from_analysis("roi", "cnr_noise_roi_id", "cnr_noise")
        target_roi_id = target_roi.id if target_roi is not None else self._read_analysis_selected_id("roi", "cnr_target_roi_id", "cnr_target")
        reference_roi_id = reference_roi.id if reference_roi is not None else self._read_analysis_selected_id("roi", "cnr_reference_roi_id", "cnr_reference")
        noise_roi_id = ""
        if formula == "standard_noise":
            noise_roi_id = noise_roi.id if noise_roi is not None else self._read_analysis_selected_id("roi", "cnr_noise_roi_id", "cnr_noise")
        cnr_payload: dict[str, Any] = {
            "status": "missing",
            "reason": "",
            "formula": formula,
            "preview_text": "",
            "result_text": "",
            "inputs": {
                "formula": formula,
                "region_a_roi_id": target_roi_id,
                "region_b_roi_id": reference_roi_id,
                "noise_roi_id": None if formula != "standard_noise" else noise_roi_id,
            },
            "factors": {
                "region_a": {} if target_roi is None else self._collect_analysis_factors(target_roi),
                "region_b": {} if reference_roi is None else self._collect_analysis_factors(reference_roi),
                "noise": None if noise_roi is None else self._collect_analysis_factors(noise_roi),
            },
            "numerator": None,
            "denominator": None,
            "target_mean": None,
            "reference_mean": None,
            "noise_std": None,
            "target_std": None,
            "reference_std": None,
            "result": None,
        }
        if target_roi is None or reference_roi is None or (formula == "standard_noise" and noise_roi is None):
            missing: list[str] = []
            if target_roi is None:
                missing.append("target role(또는 Region A ROI 수동 선택)")
            if reference_roi is None:
                missing.append("reference role(또는 Region B ROI 수동 선택)")
            if formula == "standard_noise" and noise_roi is None:
                missing.append("noise role(또는 Noise ROI 수동 선택)")
            reason = " + ".join(missing)
            preview_text = "ROI selection required"
            result_text = "CNR unavailable"
            self.analysis_results["cnr_preview"].set(preview_text)
            self.analysis_results["cnr_result"].set(result_text)
            cnr_payload["status"] = "missing"
            cnr_payload["reason"] = reason
            cnr_payload["preview_text"] = f"Preview: {preview_text}"
            cnr_payload["result_text"] = result_text
            self.analysis_last_run["cnr"] = cnr_payload
            self._refresh_analysis_results_panel()
            messagebox.showinfo("CNR", "CNR 계산에 필요한 ROI가 부족합니다.\nrole 지정 또는 수동 선택을 확인하세요.")
            return
        target_metrics = self.compute_measurement(target_roi, self._get_frame_pixel_array(target_roi.frame_index))
        reference_metrics = self.compute_measurement(reference_roi, self._get_frame_pixel_array(reference_roi.frame_index))
        target_mean = float((target_metrics.get("signal_stats") or {}).get("mean", 0.0))
        reference_mean = float((reference_metrics.get("signal_stats") or {}).get("mean", 0.0))
        numerator = abs(target_mean - reference_mean)
        cnr_payload["inputs"] = {
            "formula": formula,
            "region_a_roi_id": target_roi.id,
            "region_b_roi_id": reference_roi.id,
            "noise_roi_id": None if noise_roi is None else noise_roi.id,
        }
        cnr_payload["factors"] = {
            "region_a": self._collect_analysis_factors(target_roi),
            "region_b": self._collect_analysis_factors(reference_roi),
            "noise": None if noise_roi is None else self._collect_analysis_factors(noise_roi),
        }
        cnr_payload["target_mean"] = float(target_mean)
        cnr_payload["reference_mean"] = float(reference_mean)
        cnr_payload["numerator"] = float(numerator)
        if formula == "standard_noise":
            assert noise_roi is not None
            noise_metrics = self.compute_measurement(noise_roi, self._get_frame_pixel_array(noise_roi.frame_index))
            noise_std = float((noise_metrics.get("signal_stats") or {}).get("std", 0.0))
            preview_text = "Target ROI selected / Reference ROI selected / Noise ROI selected"
            self.analysis_results["cnr_preview"].set(preview_text)
            denominator = noise_std
            invalid_msg = "Noise ROI 표준편차가 0입니다."
            cnr_payload["noise_std"] = float(noise_std)
        else:
            target_std = float((target_metrics.get("signal_stats") or {}).get("std", 0.0))
            reference_std = float((reference_metrics.get("signal_stats") or {}).get("std", 0.0))
            denominator = float(np.sqrt(target_std * target_std + reference_std * reference_std))
            preview_text = "Target ROI selected / Reference ROI selected"
            self.analysis_results["cnr_preview"].set(preview_text)
            invalid_msg = "Region A/Region B 분산 기반 분모가 0입니다."
            cnr_payload["target_std"] = float(target_std)
            cnr_payload["reference_std"] = float(reference_std)
        cnr_payload["preview_text"] = f"Preview: {preview_text}"
        cnr_payload["denominator"] = float(denominator)
        if denominator <= 0:
            result_text = "CNR unavailable"
            self.analysis_results["cnr_result"].set(result_text)
            cnr_payload["status"] = "invalid"
            cnr_payload["reason"] = "denominator <= 0"
            cnr_payload["result"] = None
            cnr_payload["result_text"] = result_text
            self.analysis_last_run["cnr"] = cnr_payload
            self._refresh_analysis_results_panel()
            messagebox.showwarning("CNR", invalid_msg)
            return
        cnr = numerator / denominator
        result_text = f"Target Mean: {target_mean:.2f} | Reference Mean: {reference_mean:.2f} | CNR: {cnr:.2f}"
        self.analysis_results["cnr_result"].set(result_text)
        cnr_payload["status"] = "success"
        cnr_payload["reason"] = ""
        cnr_payload["result"] = float(cnr)
        cnr_payload["result_text"] = result_text
        self.analysis_last_run["cnr"] = cnr_payload
        self._refresh_analysis_results_panel()
        history_stats = {"target_mean": target_mean, "reference_mean": reference_mean}
        if formula == "standard_noise":
            history_stats["noise_std"] = cnr_payload.get("noise_std")
        else:
            history_stats["noise_std"] = denominator
        self._append_analysis_history_row(
            {
                "metric_name": "CNR",
                "item_name": "CNR",
                "stats": history_stats,
                "result_value": float(cnr),
            },
            unit="ratio",
            related_target_ids=[target_roi.id, reference_roi.id] + ([] if noise_roi is None else [noise_roi.id]),
        )

    def _set_current_image_as_reference(self) -> None:
        path = self._get_current_image_path()
        if not path:
            return
        self.image_analysis_inputs["reference_image_id"].set(path)
        self._sync_image_analysis_display_value("image", "reference_image", "reference_image_id")

    def _set_current_image_as_target(self) -> None:
        path = self._get_current_image_path()
        if not path:
            return
        self.image_analysis_inputs["target_image_id"].set(path)
        self._sync_image_analysis_display_value("image", "target_image", "target_image_id")

    def _get_current_image_path(self) -> str:
        file_paths = getattr(self, "file_paths", [])
        current_file_index = int(getattr(self, "current_file_index", -1))
        if file_paths and 0 <= current_file_index < len(file_paths):
            return file_paths[current_file_index]
        if hasattr(self, "path_var") and self.path_var is not None:
            try:
                return self.path_var.get().strip()
            except Exception:
                return ""
        return ""

    def _resolve_image_analysis_selection(self, input_key: str, combobox_key: str, kind: str) -> str:
        label = self._image_analysis_comboboxes.get(combobox_key).get() if combobox_key in self._image_analysis_comboboxes else ""
        if label:
            mapped = self._image_analysis_option_maps.get(kind, {}).get(label, "")
            if mapped:
                self.image_analysis_inputs[input_key].set(mapped)
        return self.image_analysis_inputs[input_key].get()

    def _load_analysis_image_array(self, image_id: str) -> np.ndarray | None:
        if not image_id:
            return None
        try:
            _dataset, frames = self.dicom_loader.get_decoded_file(image_id)
        except Exception:
            return None
        if not frames:
            return None
        frame = np.asarray(frames[0], dtype=np.float64)
        if frame.ndim > 2:
            frame = frame[..., 0]
        return frame

    @staticmethod
    def _compute_simple_ssim(reference: np.ndarray, target: np.ndarray) -> float:
        ref = reference.astype(np.float64)
        tar = target.astype(np.float64)
        c1 = (0.01 * 255) ** 2
        c2 = (0.03 * 255) ** 2
        mu_x = float(np.mean(ref))
        mu_y = float(np.mean(tar))
        sigma_x = float(np.var(ref))
        sigma_y = float(np.var(tar))
        sigma_xy = float(np.mean((ref - mu_x) * (tar - mu_y)))
        numerator = (2 * mu_x * mu_y + c1) * (2 * sigma_xy + c2)
        denominator = (mu_x**2 + mu_y**2 + c1) * (sigma_x + sigma_y + c2)
        if denominator == 0:
            return 0.0
        return float(numerator / denominator)

    def calculate_image_comparison_metrics(self) -> None:
        reference_id = self._resolve_image_analysis_selection("reference_image_id", "reference_image", "image")
        target_id = self._resolve_image_analysis_selection("target_image_id", "target_image", "image")
        if not reference_id or not target_id:
            self.image_analysis_results["image_result"].set("Result: Select reference and target image")
            return
        reference = self._load_analysis_image_array(reference_id)
        target = self._load_analysis_image_array(target_id)
        if reference is None or target is None:
            self.image_analysis_results["image_result"].set("Result: Failed to load image pair")
            return
        min_h = min(reference.shape[0], target.shape[0])
        min_w = min(reference.shape[1], target.shape[1])
        reference = reference[:min_h, :min_w]
        target = target[:min_h, :min_w]
        if self.image_analysis_inputs["scope_type"].get() == "roi":
            self._resolve_image_analysis_selection("scope_roi_id", "scope_roi", "roi")
            roi = self._get_selected_measurement_from_analysis("roi", "scope_roi_id", "scope_roi")
            if roi is None:
                self.image_analysis_results["image_result"].set("Result: Select scope ROI")
                return
            roi_pixels, (x0, y0, x1, y1) = self._extract_roi_pixels(reference, roi.start, roi.end, ensure_non_empty=False)
            if roi_pixels.size == 0 or x1 <= x0 or y1 <= y0:
                self.image_analysis_results["image_result"].set("Result: Invalid ROI scope")
                return
            reference = reference[y0:y1, x0:x1]
            target = target[y0:y1, x0:x1]
        diff = reference - target
        mse = float(np.mean(diff**2))
        max_val = float(max(np.max(reference), np.max(target), 1.0))
        psnr = float("inf") if mse <= 0 else float(20 * np.log10(max_val / np.sqrt(mse)))
        ssim = self._compute_simple_ssim(reference, target)
        hist_ref, _ = np.histogram(reference, bins=64, range=(np.min(reference), np.max(reference) + 1e-6), density=True)
        hist_tar, _ = np.histogram(target, bins=64, range=(np.min(target), np.max(target) + 1e-6), density=True)
        hist_corr = float(np.corrcoef(hist_ref, hist_tar)[0, 1]) if np.std(hist_ref) > 0 and np.std(hist_tar) > 0 else 0.0
        scope_text = "Full Image" if self.image_analysis_inputs["scope_type"].get() == "full" else "Selected ROI"
        self.image_analysis_results["image_formula"].set(f"Formula: scope={scope_text}, SSIM/PSNR/MSE/HIST")
        self.image_analysis_results["image_result"].set(
            f"Result: MSE={mse:.4f} | PSNR={psnr:.4f} | SSIM={ssim:.4f} | HIST corr={hist_corr:.4f}"
        )

    def assign_roi_role(self) -> None:
        selected = self._find_measurement_by_id(self.selected_persistent_measurement_id, expected_kind="roi")
        if selected is None:
            messagebox.showinfo("ROI Role", "먼저 ROI를 선택하세요.")
            return
        current_role = self._get_measurement_roi_role(selected) or "none"
        prompt = (
            "ROI role을 입력하세요.\n"
            "가능한 값: signal, background, noise, target, reference\n"
            "비우거나 none 입력 시 role 해제"
        )
        raw_value = simpledialog.askstring("ROI Role", prompt, initialvalue=current_role, parent=self.root)
        if raw_value is None:
            return
        normalized = self._normalize_roi_role(raw_value)
        if normalized is None and raw_value.strip() and raw_value.strip().lower() != "none":
            messagebox.showwarning("ROI Role", "유효하지 않은 role 입니다. signal/background/noise/target/reference 중 하나를 입력하세요.")
            return
        selected.meta = dict(selected.meta or {})
        if normalized is None:
            selected.meta.pop("role", None)
            action_text = "해제"
        else:
            selected.meta["role"] = normalized
            action_text = f"설정: {normalized}"
        metrics = self.compute_measurement(selected, self._get_frame_pixel_array(selected.frame_index))
        selected.summary_text = metrics["summary"]
        selected.meta = self._canonicalize_measurement_meta(selected, metrics)
        self.analysis_last_run = {}
        self._reset_signal_analysis_results()
        self._refresh_analysis_selectors()
        self._auto_bind_analysis_inputs_from_roles(overwrite_existing=True)
        self._update_analysis_action_button_state()
        self._draw_persistent_measurements()
        messagebox.showinfo("ROI Role", f"ROI role {action_text}")

    def start_guided_snr_workflow(self) -> None:
        if not self.frames:
            messagebox.showinfo("안내", "SNR 계산을 위한 이미지를 먼저 열어주세요.")
            return
        self.guided_snr_state = {
            "step": "signal",
            "frame_index": int(self.current_frame),
            "geometry_key": self._get_current_geometry_key(),
            "signal_id": None,
            "noise_id": None,
        }
        self.measurement_mode.set("roi")
        self.snr_workflow_var.set("SNR Step 1/2: Select Signal ROI")
        messagebox.showinfo("SNR Workflow", "Step 1/2: Select Signal ROI")

    def _cancel_guided_snr_workflow(self) -> None:
        self.guided_snr_state = None
        self.snr_workflow_var.set("SNR: Idle")

    def _find_measurement_by_id(self, measurement_id: str | None, expected_kind: str | None = None) -> Measurement | None:
        if measurement_id is None:
            return None
        for measurement in self.persistent_measurements:
            if measurement.id == measurement_id:
                if expected_kind is not None and measurement.kind != expected_kind:
                    return None
                return measurement
        return None

    def _update_guided_snr_selection(self, measurement: Measurement) -> None:
        state = self.guided_snr_state
        if state is None or measurement.kind != "roi":
            return
        if measurement.meta.get("grid_cell") is not None:
            return
        if state.get("geometry_key") and not self._geometry_matches(measurement.geometry_key, state.get("geometry_key")):
            return
        step = state.get("step")
        if step == "signal":
            state["signal_id"] = measurement.id
            state["step"] = "noise"
            self.snr_workflow_var.set("SNR Step 2/2: Select Noise ROI")
            self._draw_persistent_measurements()
            messagebox.showinfo("SNR Workflow", "Step 2/2: Select Noise ROI")
            return
        if step == "noise":
            state["noise_id"] = measurement.id
            self._draw_persistent_measurements()
            self._finalize_guided_snr_workflow()

    def _compute_snr(self, signal_roi: Measurement, noise_roi: Measurement) -> tuple[float, float, float] | None:
        signal_stats = self._roi_stats(signal_roi)
        noise_stats = self._roi_stats(noise_roi)
        if signal_stats is None or noise_stats is None:
            return None
        signal_mean = signal_stats.mean
        noise_std = noise_stats.std
        if noise_std <= 0:
            return None
        return signal_mean, noise_std, signal_mean / noise_std

    def _finalize_guided_snr_workflow(self) -> None:
        state = self.guided_snr_state
        if state is None:
            return
        signal_roi = self._find_measurement_by_id(state.get("signal_id"))
        noise_roi = self._find_measurement_by_id(state.get("noise_id"))
        if signal_roi is None or noise_roi is None:
            self.snr_workflow_var.set("SNR: Failed (ROI missing)")
            self.guided_snr_state = None
            self.measurement_mode.set("pan")
            messagebox.showwarning("SNR Workflow", "Signal 또는 Noise ROI를 찾을 수 없습니다.")
            return
        snr_result = self._compute_snr(signal_roi, noise_roi)
        self.guided_snr_state = None
        if snr_result is None:
            self.snr_workflow_var.set("SNR: Failed")
            self.measurement_mode.set("pan")
            messagebox.showwarning("SNR Workflow", "SNR 계산에 실패했습니다. Noise ROI 표준편차를 확인하세요.")
            return
        signal_mean, noise_std, snr = snr_result
        self.snr_workflow_var.set(f"SNR Complete: {snr:.4f}")
        self.measurement_mode.set("pan")
        messagebox.showinfo(
            "SNR Result",
            f"SNR = {snr:.4f}\nSignal mean = {signal_mean:.4f}\nNoise std = {noise_std:.4f}",
        )

    def _roi_stats(self, measurement: Measurement) -> RoiStats | None:
        frame = self._get_frame_pixel_array(measurement.frame_index)
        if frame is None:
            return None
        roi, (_x0, _y0, _x1, _y1) = self._extract_roi_pixels(frame, measurement.start, measurement.end, ensure_non_empty=False)
        if roi.size == 0:
            return None
        return RoiStats(
            mean=float(np.mean(roi)),
            std=float(np.std(roi)),
            min_val=float(np.min(roi)),
            max_val=float(np.max(roi)),
            area_px=int(roi.size),
        )

    def calculate_cnr_from_roles(self) -> None:
        self.calculate_cnr_from_inputs()

    def _render_measurements_on_image(
        self,
        image: Image.Image,
        frame_index: int,
        include_labels: bool = True,
        include_grid: bool = False,
    ) -> Image.Image:
        composed = image.convert("RGB")
        draw = ImageDraw.Draw(composed)
        width, height = composed.size
        frame = np.asarray(self.frames[frame_index])
        source_h, source_w = frame.shape[:2]
        current_geometry = self._get_geometry_key_for_frame(frame_index)
        for measurement in self.persistent_measurements:
            if not self._geometry_matches(current_geometry, measurement.geometry_key):
                continue
            if measurement.frame_index != frame_index:
                continue
            sx = measurement.start[0] / max(source_w, 1) * width
            sy = measurement.start[1] / max(source_h, 1) * height
            ex = measurement.end[0] / max(source_w, 1) * width
            ey = measurement.end[1] / max(source_h, 1) * height
            metrics = self.compute_measurement(
                measurement,
                self._get_frame_pixel_array(frame_index),
            )
            label_summary = metrics["summary"]
            if measurement.kind == "roi":
                draw.rectangle((sx, sy, ex, ey), outline="#ff7f50", width=2)
                if include_labels:
                    roi_label = self._display_name_for_roi_id(measurement.id)
                    draw.text((ex + 4, ey - 14), f"{roi_label}\n{label_summary}", fill="white")
            elif measurement.kind == "line":
                draw.line((sx, sy, ex, ey), fill="#00ffaa", width=2)
                if include_labels:
                    draw.text((ex + 4, ey - 14), label_summary, fill="white")
            else:
                points = measurement.meta.get("points", [])
                scaled_points: list[tuple[float, float]] = []
                if isinstance(points, list):
                    for point in points:
                        if not isinstance(point, (list, tuple)) or len(point) < 2:
                            continue
                        scaled_points.append(
                            (
                                float(point[0]) / max(source_w, 1) * width,
                                float(point[1]) / max(source_h, 1) * height,
                            )
                        )
                if len(scaled_points) >= 3:
                    draw.polygon(scaled_points, outline="#8be9fd")
                    if include_labels:
                        centroid_x = sum(point[0] for point in scaled_points) / len(scaled_points)
                        centroid_y = sum(point[1] for point in scaled_points) / len(scaled_points)
                        draw.text((centroid_x + 4, centroid_y - 14), label_summary, fill="white")
        if include_grid:
            spacing = self._get_grid_spacing_px()
            source_step_x = spacing / max(source_w, 1)
            source_step_y = spacing / max(source_h, 1)
            x = source_step_x
            while x < 1.0:
                draw_x = int(width * x)
                draw.line((draw_x, 0, draw_x, height), fill="#5bc0de", width=1)
                x += source_step_x
            y = source_step_y
            while y < 1.0:
                draw_y = int(height * y)
                draw.line((0, draw_y, width, draw_y), fill="#5bc0de", width=1)
                y += source_step_y
        return composed

    def export_view_screenshot(self) -> None:
        self.export_current_image()

    def _compose_export_frame_image(self, frame_index: int, include_overlays: bool, include_grid: bool) -> Image.Image:
        frame = self.frames[frame_index]
        base = Image.fromarray(self._normalize_frame(frame))
        if include_overlays:
            return self._render_measurements_on_image(
                base,
                frame_index=frame_index,
                include_labels=True,
                include_grid=include_grid,
            )
        return base

    def export_current_image(self) -> None:
        if not self.frames:
            return
        path = filedialog.asksaveasfilename(title="현재 이미지 저장", defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        image = self._compose_export_frame_image(
            frame_index=self.current_frame,
            include_overlays=self.include_overlays_in_export.get(),
            include_grid=self.show_grid_overlay.get(),
        )
        image.save(path)
        messagebox.showinfo("저장 완료", f"현재 이미지를 저장했습니다.\n{path}")

    def export_all_frames(self) -> None:
        if len(self.frames) <= 1:
            messagebox.showinfo("안내", "일괄 저장은 2개 이상의 프레임이 있을 때 사용할 수 있습니다.")
            return
        directory = filedialog.askdirectory(title="프레임 일괄 저장 폴더 선택")
        if not directory:
            return
        base_name = Path(self.file_paths[self.current_file_index]).stem if 0 <= self.current_file_index < len(self.file_paths) else "frame"
        saved_count = 0
        for frame_index in range(len(self.frames)):
            image = self._compose_export_frame_image(
                frame_index=frame_index,
                include_overlays=self.include_overlays_in_export.get(),
                include_grid=self.show_grid_overlay.get(),
            )
            output_path = Path(directory) / f"{base_name}_frame_{frame_index + 1:04d}.png"
            image.save(output_path)
            saved_count += 1
        messagebox.showinfo("저장 완료", f"{saved_count}개 프레임을 저장했습니다.\n{directory}")

    def export_clean_figure(self) -> None:
        if not self.frames:
            return
        path = filedialog.asksaveasfilename(title="Clean Figure 저장", defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        frame = self.frames[self.current_frame]
        base = Image.fromarray(self._normalize_frame(frame))
        image = self._render_measurements_on_image(base, frame_index=self.current_frame, include_labels=False, include_grid=False)
        image.save(path)
        messagebox.showinfo("저장 완료", f"Figure를 저장했습니다.\n{path}")

    def _draw_grid_overlay(self) -> None:
        self.canvas.delete("grid_overlay")
        if not self.show_grid_overlay.get() or self._image_bbox is None:
            return
        if not self.frames:
            return
        frame_array = np.asarray(self.frames[self.current_frame])
        if frame_array.ndim < 2:
            return
        left, top, right, bottom = self._image_bbox
        height, width = frame_array.shape[:2]
        spacing = self._get_grid_spacing_px()
        for column in range(spacing, width, spacing):
            point = self._image_coords_to_canvas(float(column), 0.0)
            if point is None:
                continue
            x, _ = point
            self.canvas.create_line(x, top, x, bottom, fill="#5bc0de", width=1, dash=(1, 2), tags=("grid_overlay",))
        for row in range(spacing, height, spacing):
            point = self._image_coords_to_canvas(0.0, float(row))
            if point is None:
                continue
            _, y = point
            self.canvas.create_line(left, y, right, y, fill="#5bc0de", width=1, dash=(1, 2), tags=("grid_overlay",))

    def _refresh_single_view_image(self) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        center_ratio = self._capture_view_center_ratio()
        self._show_frame()
        self._restore_view_center_ratio(center_ratio)

    def _refresh_grid_overlay(self) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        if not self.show_grid_overlay.get() and self._line_snap_anchor is not None:
            self.clear_preview_overlay()
        self._draw_grid_overlay()

    def _handle_mousewheel(self, event: tk.Event) -> str:
        direction = self._get_mousewheel_direction(event)
        if direction == 0:
            return "break"

        if self._is_ctrl_pressed(event):
            self._zoom_with_mousewheel(direction)
        else:
            self.change_file(direction)
        return "break"

    def _zoom_with_mousewheel(self, direction: int) -> None:
        if not self.frames:
            return
        center_ratio = self._capture_view_center_ratio()
        zoom_step = 1.15
        if direction < 0:
            requested_scale = self.zoom_scale * zoom_step
            if requested_scale >= self.max_zoom_scale:
                self.zoom_scale = self.max_zoom_scale
                self._show_zoom_limit_message("max")
            else:
                self.zoom_scale = requested_scale
                self._zoom_limit_notice = None
        else:
            requested_scale = self.zoom_scale / zoom_step
            if requested_scale <= self.min_zoom_scale:
                self.zoom_scale = self.min_zoom_scale
                self._show_zoom_limit_message("min")
            else:
                self.zoom_scale = requested_scale
                self._zoom_limit_notice = None

        self.zoom_scale = float(np.clip(self.zoom_scale, self.min_zoom_scale, self.max_zoom_scale))
        self._show_frame()
        self._restore_view_center_ratio(center_ratio)

    def _show_zoom_limit_message(self, limit_type: str) -> None:
        if self._zoom_limit_notice == limit_type:
            return
        self._zoom_limit_notice = limit_type
        if limit_type == "max":
            messagebox.showinfo("확대 한계", "최대 크기입니다.")
        elif limit_type == "min":
            messagebox.showinfo("축소 한계", "최소 크기입니다.")

    def _handle_fit_shortcut(self, _event: tk.Event) -> str:
        self.fit_to_window()
        return "break"

    def _handle_actual_size_shortcut(self, _event: tk.Event) -> str:
        self.reset_zoom_to_actual_size()
        return "break"

    def _handle_window_level_reset_shortcut(self, _event: tk.Event) -> str:
        self.reset_window_level()
        return "break"

    def _handle_grid_roi_summary_shortcut(self, _event: tk.Event) -> str:
        self._show_grid_roi_combined_summary()
        return "break"

    def _handle_left_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._move_multiview_selection(-1)
            return "break"
        return ""

    def _handle_right_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._move_multiview_selection(1)
            return "break"
        return ""

    def _handle_up_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._move_multiview_selection(-self.multiview_cols)
            return "break"
        return ""

    def _handle_down_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._move_multiview_selection(self.multiview_cols)
            return "break"
        return ""

    def _handle_enter_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "single" and self.measurement_mode.get() == "polygon" and len(self._polygon_points) >= 3:
            self._finalize_polygon_measurement()
            return "break"
        if self.view_mode == "multi" and 0 <= self.current_file_index < len(self.file_paths):
            self.open_multiview_tile(self.current_file_index)
            return "break"
        return ""

    def _handle_escape_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "single" and self.measurement_mode.get() == "polygon" and self._polygon_points:
            self._cancel_polygon_draft()
            self.cursor_var.set("Cursor: Polygon 초안 취소됨")
            return "break"
        if self.view_mode == "single" and self._can_use_multiview():
            self.enter_multiview_mode()
            return "break"
        return ""

    def _handle_first_image_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._go_to_multiview_page(0, preserve_slot=True)
            return "break"
        if self.file_paths:
            self.go_to_file(0)
        return "break"

    def _handle_last_image_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._go_to_multiview_page(self._get_multiview_total_pages() - 1, preserve_slot=True)
            return "break"
        if self.file_paths:
            self.go_to_file(len(self.file_paths) - 1)
        return "break"

    def _handle_prev_image_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._move_multiview_page(-1, preserve_slot=True)
            return "break"
        self.change_file(-1)
        return "break"

    def _handle_next_image_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "multi":
            self._move_multiview_page(1, preserve_slot=True)
            return "break"
        self.change_file(1)
        return "break"

    def _handle_prev_frame_shortcut(self, _event: tk.Event) -> str:
        if len(self.frames) > 1:
            self.change_frame(-1)
        return "break"

    def _handle_next_frame_shortcut(self, _event: tk.Event) -> str:
        if len(self.frames) > 1:
            self.change_frame(1)
        return "break"

    def _handle_undo_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "single":
            self.undo_last_measurement()
            return "break"
        return ""

    def _handle_delete_selected_shortcut(self, _event: tk.Event) -> str:
        if self.view_mode == "single":
            self.clear_selected_measurement()
            return "break"
        return ""

    @staticmethod
    def _get_mousewheel_direction(event: tk.Event) -> int:
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1

        delta = getattr(event, "delta", 0)
        if delta > 0:
            return -1
        if delta < 0:
            return 1
        return 0

    @staticmethod
    def _is_ctrl_pressed(event: tk.Event) -> bool:
        return bool(getattr(event, "state", 0) & 0x0004)

    def _build_info_text(self, dataset, frames: list[np.ndarray]) -> str:
        patient_name = str(getattr(dataset, "PatientName", "Unknown"))
        modality = getattr(dataset, "Modality", "Unknown")
        rows = getattr(dataset, "Rows", "?")
        columns = getattr(dataset, "Columns", "?")
        frame_count = len(frames)
        photometric = getattr(dataset, "PhotometricInterpretation", "Unknown")
        return (
            f"환자명: {patient_name} | 모달리티: {modality} | "
            f"해상도: {columns} x {rows} | 프레임 수: {frame_count} | "
            f"Photometric: {photometric}"
        )

    def change_frame(self, delta: int) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        source_geometry_key = self._get_current_geometry_key()
        source_frame_index = int(self.current_frame)
        new_index = self.current_frame + delta
        if not 0 <= new_index < len(self.frames):
            return
        self.current_frame = new_index
        self._propagate_rois_from_geometry(source_geometry_key, source_frame_index, navigation_step=delta)
        self.clear_preview_overlay()
        self._show_frame()

    def change_file(self, delta: int) -> None:
        if self.view_mode == "compare":
            return
        if not self.file_paths:
            return
        source_geometry_key = self._get_current_geometry_key()
        source_frame_index = int(self.current_frame)
        new_index = self.current_file_index + delta
        if not 0 <= new_index < len(self.file_paths):
            return
        if self.view_mode == "multi":
            self.current_file_index = new_index
            self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")
            self._ensure_multiview_selection_visible()
            self.render_multiview_page()
            return
        self._load_file(new_index, preserve_view_state=True)
        self._propagate_rois_from_geometry(source_geometry_key, source_frame_index, navigation_step=delta)
        self._draw_persistent_measurements()

    def go_to_file(self, index: int) -> None:
        if self.view_mode == "compare":
            return
        if not 0 <= index < len(self.file_paths):
            return
        previous_index = self.current_file_index
        source_geometry_key = self._get_current_geometry_key()
        source_frame_index = int(self.current_frame)
        if self.view_mode == "multi":
            self.current_file_index = index
            self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")
            self._ensure_multiview_selection_visible()
            self.render_multiview_page()
            return
        self._load_file(index, preserve_view_state=True)
        step = 0 if previous_index < 0 or index == previous_index else (1 if index > previous_index else -1)
        self._propagate_rois_from_geometry(source_geometry_key, source_frame_index, navigation_step=step)
        self._draw_persistent_measurements()

    def _show_frame(
        self,
        center_view: bool = False,
        preserve_center_ratio: tuple[float, float] | None = None,
    ) -> None:
        frame = self.frames[self.current_frame]
        center_ratio = preserve_center_ratio
        if center_ratio is None:
            center_ratio = self._capture_view_center_ratio()
        self.photo_image = self._frame_to_photoimage(frame)
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        content_width = max(canvas_width, self.photo_image.width())
        content_height = max(canvas_height, self.photo_image.height())
        center_x = content_width / 2
        center_y = content_height / 2

        self.canvas.delete("all")
        self.canvas.create_image(center_x, center_y, image=self.photo_image, anchor="center")
        self._image_bbox = (
            center_x - (self.photo_image.width() / 2),
            center_y - (self.photo_image.height() / 2),
            center_x + (self.photo_image.width() / 2),
            center_y + (self.photo_image.height() / 2),
        )
        self.canvas.config(
            scrollregion=(
                0,
                0,
                content_width,
                content_height,
            )
        )
        if center_view:
            self._center_view_for_content(content_width, content_height)
        else:
            self._restore_view_center_ratio(center_ratio)
        self._draw_single_view_overlays()
        self._draw_grid_overlay()
        self._draw_persistent_measurements()
        self._draw_preview_measurements()
        self.frame_var.set(f"프레임: {self.current_frame + 1} / {len(self.frames)}")
        self._update_zoom_label()

    def _on_canvas_resize(self, event: tk.Event) -> None:
        canvas_size = (event.width, event.height)
        if canvas_size == self._last_canvas_size:
            return
        center_ratio = self._capture_view_center_ratio()
        self._last_canvas_size = canvas_size
        if self.frames and event.width > 1 and event.height > 1:
            self._show_frame()
            self._restore_view_center_ratio(center_ratio)

    def _frame_to_photoimage(self, frame: np.ndarray) -> ImageTk.PhotoImage:
        normalized = self._normalize_frame(frame)
        image = Image.fromarray(normalized)
        resized = self._resize_image_for_display(image)
        return ImageTk.PhotoImage(resized)

    def _resize_image_for_display(self, image: Image.Image) -> Image.Image:
        scale = self._get_effective_zoom_scale(image)
        if scale == 1.0:
            return image

        width, height = image.size
        resized_width = max(int(round(width * scale)), 1)
        resized_height = max(int(round(height * scale)), 1)
        if scale < 1.0:
            resample = Image.Resampling.LANCZOS
        else:
            resample = Image.Resampling.BICUBIC
        return image.resize((resized_width, resized_height), resample)

    def _initialize_zoom(self, frame: np.ndarray | None) -> None:
        if frame is None:
            self.zoom_scale = 1.0
            self.zoom_var.set("Zoom: -")
            return
        frame_array = np.asarray(frame)
        if frame_array.ndim == 2:
            height, width = frame_array.shape
        elif frame_array.ndim == 3:
            height, width = frame_array.shape[:2]
        else:
            self.zoom_scale = 1.0
            self.zoom_var.set("Zoom: -")
            return
        self.zoom_scale = self._calculate_fit_scale(width, height)
        self._update_zoom_label()

    def _calculate_fit_scale(self, width: int, height: int) -> float:
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return 1.0
        return min(canvas_width / width, canvas_height / height, 1.0)

    def _get_effective_zoom_scale(self, image: Image.Image) -> float:
        fit_scale = self._calculate_fit_scale(*image.size)
        if self.zoom_scale <= 0:
            self.zoom_scale = fit_scale
        return float(np.clip(self.zoom_scale, self.min_zoom_scale, self.max_zoom_scale))

    def fit_to_window(self) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        frame = np.asarray(self.frames[self.current_frame])
        if frame.ndim == 2:
            height, width = frame.shape
        elif frame.ndim == 3:
            height, width = frame.shape[:2]
        else:
            return
        self.zoom_scale = self._calculate_fit_scale(width, height)
        self._zoom_limit_notice = None
        self._show_frame(center_view=True)

    def reset_zoom_to_actual_size(self) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        self.zoom_scale = 1.0
        self._zoom_limit_notice = None
        self._show_frame(center_view=True)

    def _update_zoom_label(self) -> None:
        self.zoom_var.set(f"Zoom: {self.zoom_scale * 100:.0f}%")

    def _capture_view_center_ratio(self) -> tuple[float, float]:
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        content_width = max(self.canvas.bbox("all")[2] if self.canvas.bbox("all") else canvas_width, 1)
        content_height = max(self.canvas.bbox("all")[3] if self.canvas.bbox("all") else canvas_height, 1)
        center_x = self.canvas.canvasx(canvas_width / 2)
        center_y = self.canvas.canvasy(canvas_height / 2)
        return center_x / content_width, center_y / content_height

    def _restore_view_center_ratio(self, center_ratio: tuple[float, float]) -> None:
        center_x_ratio, center_y_ratio = center_ratio
        content_width = max(self.canvas.bbox("all")[2] if self.canvas.bbox("all") else self.canvas.winfo_width(), 1)
        content_height = max(self.canvas.bbox("all")[3] if self.canvas.bbox("all") else self.canvas.winfo_height(), 1)
        self._set_view_center(center_x_ratio * content_width, center_y_ratio * content_height)

    def _set_view_center(self, center_x: float, center_y: float) -> None:
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        content_width = max(self.canvas.bbox("all")[2] if self.canvas.bbox("all") else canvas_width, canvas_width, 1)
        content_height = max(self.canvas.bbox("all")[3] if self.canvas.bbox("all") else canvas_height, canvas_height, 1)
        x_offset = max(center_x - canvas_width / 2, 0.0)
        y_offset = max(center_y - canvas_height / 2, 0.0)
        max_x_offset = max(content_width - canvas_width, 0.0)
        max_y_offset = max(content_height - canvas_height, 0.0)
        x_offset = min(x_offset, max_x_offset)
        y_offset = min(y_offset, max_y_offset)
        self.canvas.xview_moveto(0.0 if content_width <= canvas_width else x_offset / content_width)
        self.canvas.yview_moveto(0.0 if content_height <= canvas_height else y_offset / content_height)

    def _center_view_for_content(self, content_width: float, content_height: float) -> None:
        self._set_view_center(content_width / 2, content_height / 2)

    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        return self._normalize_frame_for_dataset(
            dataset=self.dataset,
            frame=frame,
            window_width=self.window_width_value,
            window_level=self.window_level_value,
        )

    def _normalize_frame_for_dataset(
        self,
        dataset,
        frame: np.ndarray,
        window_width: float | None,
        window_level: float | None,
    ) -> np.ndarray:
        array = np.asarray(frame, dtype=np.float32)
        if array.ndim == 2:
            array = self._apply_window_level_to_array(array, window_width, window_level)
            array = self._scale_to_uint8(array)
            array = self._apply_photometric_interpretation(array, dataset)
            if self.invert_display.get():
                return 255 - array
            return array

        if array.ndim == 3 and array.shape[-1] == 3:
            channels = [self._scale_to_uint8(array[..., index]) for index in range(3)]
            rgb = np.stack(channels, axis=-1)
            if self.invert_display.get():
                return 255 - rgb
            return rgb

        raise ValueError(f"지원하지 않는 프레임 형식입니다: {array.shape}")

    def _apply_photometric_interpretation(self, array: np.ndarray, dataset) -> np.ndarray:
        photometric = str(getattr(dataset, "PhotometricInterpretation", "")).upper()
        if photometric == "MONOCHROME1":
            # MONOCHROME1 means lower values should appear brighter, so invert after
            # window/level clipping and 8-bit scaling.
            return 255 - array
        return array

    def _apply_window_level(self, array: np.ndarray) -> np.ndarray:
        return self._apply_window_level_to_array(
            array,
            self.window_width_value,
            self.window_level_value,
        )

    def _apply_window_level_to_array(
        self,
        array: np.ndarray,
        window_width: float | None,
        window_level: float | None,
    ) -> np.ndarray:
        if window_level is None or window_width is None:
            return array
        center = float(window_level)
        width = float(window_width)
        if width <= 1:
            width = 1.0

        lower = center - width / 2.0
        upper = center + width / 2.0
        return np.clip(array, lower, upper)

    @staticmethod
    def _scale_to_uint8(array: np.ndarray) -> np.ndarray:
        minimum = float(np.min(array))
        maximum = float(np.max(array))
        if maximum == minimum:
            return np.zeros(array.shape, dtype=np.uint8)
        scaled = (array - minimum) / (maximum - minimum)
        return np.clip(scaled * 255.0, 0, 255).astype(np.uint8)


def simple_prompt(parent: tk.Misc, title: str, prompt: str) -> str | None:
    return simpledialog.askstring(title, prompt, parent=parent)


def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    DicomViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
