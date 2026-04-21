from pathlib import Path
import copy
import csv
from dataclasses import dataclass, field
from datetime import datetime
import json
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


class DicomViewer:
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
        self.roi_propagation_enabled = tk.BooleanVar(value=False)
        self.roi_propagation_scope = tk.StringVar(value="next")
        self._active_preview_measurement: dict[str, Any] | None = None
        self._line_snap_anchor: tuple[int, int] | None = None
        self.crop_mode_active = tk.BooleanVar(value=False)
        self._active_crop_start: tuple[float, float] | None = None
        self._active_crop_end: tuple[float, float] | None = None
        self._active_crop_item_id: int | None = None
        self.persistent_measurements: list[Measurement] = []
        self.selected_persistent_measurement_id: str | None = None
        self.selected_persistent_measurement_ids: set[str] = set()
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

    def _build_ui(self) -> None:
        toolbar_container = ttk.Frame(self.root, padding=12)
        toolbar_container.pack(fill="x")
        self._build_toolbar_tabs(toolbar_container)
        self._build_status_row(toolbar_container)
        self._build_collapsible_info_panel()

        self.content_container = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        self.content_container.pack(fill="both", expand=True)
        self.content_container.columnconfigure(0, weight=1)
        self.content_container.rowconfigure(0, weight=1)

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

    def _build_toolbar_tabs(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="x")

        home_tab = self._add_toolbar_tab(notebook, "HOME")
        image_tab = self._add_toolbar_tab(notebook, "IMAGE")
        measure_tab = self._add_toolbar_tab(notebook, "MEASURE")
        export_tab = self._add_toolbar_tab(notebook, "EXPORT")

        self._build_home_toolbar(home_tab)
        self._build_image_toolbar(image_tab)
        self._build_measure_toolbar(measure_tab)
        self._build_export_toolbar(export_tab)

    @staticmethod
    def _add_toolbar_tab(notebook: ttk.Notebook, title: str) -> ttk.Frame:
        tab = ttk.Frame(notebook, padding=(8, 8, 8, 6))
        notebook.add(tab, text=title)
        return tab

    def _build_subtoolbar_sections(self, parent: ttk.Frame, section_names: list[str]) -> dict[str, ttk.Frame]:
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="x")
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
        wrapper.pack(fill="x")
        wrapper.columnconfigure(1, weight=1)
        canvas_background = self.ui_colors["bg_surface"]
        canvas = tk.Canvas(wrapper, height=156, highlightthickness=0, bg=canvas_background, bd=0)
        canvas.grid(row=0, column=1, sticky="ew")
        canvas.configure(yscrollincrement=16)
        y_scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        y_scrollbar.grid(row=0, column=3, sticky="ns", padx=(4, 0))
        canvas.configure(yscrollcommand=y_scrollbar.set)
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

        def _refresh_scroll_region(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            _update_nav_buttons()

        def _resize_inner(_event: tk.Event) -> None:
            canvas.itemconfigure(window_id, height=max(canvas.winfo_height(), strip.winfo_reqheight()))
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
        canvas.configure(xscrollcommand=lambda _first, _last: _update_nav_buttons())
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

    def _build_measure_toolbar(self, tab: ttk.Frame) -> None:
        strip = self._build_grouped_toolbar_strip(tab)

        draw_group = ttk.LabelFrame(strip, text="Draw", padding=(8, 6))
        draw_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Radiobutton(draw_group, text="Line", value="line", variable=self.measurement_mode).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(draw_group, text="ROI", value="roi", variable=self.measurement_mode).grid(row=0, column=1, padx=(6, 0), sticky="w")
        ttk.Radiobutton(draw_group, text="Pan", value="pan", variable=self.measurement_mode).grid(row=0, column=2, padx=(6, 0), sticky="w")

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

        selection_group = ttk.LabelFrame(strip, text="Selection", padding=(8, 6))
        selection_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(selection_group, text="Single: click measurement").grid(row=0, column=0, sticky="w")
        ttk.Label(selection_group, text="Multi: Ctrl + click toggle").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(selection_group, text="Clear Selected", command=self.clear_selected_measurement).grid(
            row=2, column=0, sticky="ew", pady=(6, 0)
        )

        measurement_group = ttk.LabelFrame(strip, text="Measurement", padding=(8, 6))
        measurement_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Label(measurement_group, text="ROI: Width / Height / Area").grid(row=0, column=0, sticky="w")
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

        analysis_group = ttk.LabelFrame(strip, text="Analysis", padding=(8, 6))
        analysis_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Button(analysis_group, text="SNR", command=self.start_guided_snr_workflow).grid(row=0, column=0, sticky="ew")
        ttk.Button(analysis_group, text="CNR", command=self.calculate_cnr_from_roles).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(analysis_group, text="Line Profile", command=self.show_line_profile_for_selected_line).grid(
            row=2, column=0, sticky="ew", pady=(4, 0)
        )
        ttk.Button(analysis_group, text="ROI 분류(CNR 고급)", command=self.assign_roi_role).grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(analysis_group, textvariable=self.snr_workflow_var).grid(row=4, column=0, sticky="w", pady=(4, 0))

        manage_group = ttk.LabelFrame(strip, text="Manage", padding=(8, 6))
        manage_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Button(manage_group, text="Undo", command=self.undo_last_measurement).grid(row=0, column=0, sticky="ew")
        ttk.Button(manage_group, text="Clear All", command=self.clear_persistent_measurements).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(manage_group, text="Export CSV", command=self.export_measurements_csv).grid(
            row=2, column=0, sticky="ew", pady=(4, 0)
        )

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

    def _build_collapsible_info_panel(self) -> None:
        self.info_panel_frame = ttk.Frame(self.root, padding=(12, 4, 12, 6))
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

    def _build_measurement_label_parts(self, kind: str, metrics: dict[str, Any]) -> tuple[str, str]:
        if kind == "line":
            primary = f"{self._format_mm_value(metrics['length_mm'])} mm"
            secondary = f"{metrics['length_px']:.1f} px"
            return primary, secondary

        width_px = int(round(metrics["width_px"]))
        height_px = int(round(metrics["height_px"]))
        area_px = int(round(metrics["area_px"]))
        primary = (
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
        chosen = (x + 8, y - 8, "sw")
        chosen_box = (chosen[0], chosen[1] - label_height - padding, chosen[0] + label_width + padding, chosen[1] + padding)
        for dx, dy in offsets:
            anchor = "sw" if dx >= 0 else "se"
            tx = x + dx
            ty = y + dy
            if anchor == "sw":
                bbox = (tx, ty - label_height - padding, tx + label_width + padding, ty + padding)
            else:
                bbox = (tx - label_width - padding, ty - label_height - padding, tx, ty + padding)
            overlaps = any(
                not (bbox[2] < ox0 or bbox[0] > ox1 or bbox[3] < oy0 or bbox[1] > oy1)
                for ox0, oy0, ox1, oy1 in occupied_boxes
            )
            if not overlaps:
                return tx, ty, anchor, bbox
        return chosen[0], chosen[1], chosen[2], chosen_box

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
        primary_label, secondary_label = self._build_measurement_label_parts("line", metrics)
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

    def _start_preview_measurement(self, event: tk.Event) -> None:
        if not self.frames or self.view_mode != "single":
            return
        mode = self.measurement_mode.get()
        if mode == "roi":
            self._create_grid_aligned_roi(event)
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
        if self.measurement_mode.get() == "roi":
            return
        if self._active_preview_measurement is None:
            return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        start_x, start_y = self._active_preview_measurement["start"]
        self._active_preview_measurement["end"] = (end_x, end_y)
        self.canvas.coords(self._active_preview_measurement["item_id"], start_x, start_y, end_x, end_y)

    def _finish_preview_measurement(self, event: tk.Event) -> None:
        if self.measurement_mode.get() == "roi":
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
        measurement = self._append_persistent_measurement(mode, image_start, image_end)
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
            self._draw_preview_measurements()
            self._draw_persistent_measurements()
            return
        created_measurement = self.select_roi_from_grid(row, col)
        if created_measurement is not None:
            self._apply_measurement_selection(created_measurement.id, toggle=ctrl_pressed)
        self._draw_preview_measurements()
        self._draw_persistent_measurements()

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
        x1 = int(np.clip(x0 + (cell_size_px * roi_cells_w), 0, max(width - 1, 0)))
        y1 = int(np.clip(y0 + (cell_size_px * roi_cells_h), 0, max(height - 1, 0)))
        measurement = self._append_persistent_measurement("roi", (x0, y0), (x1, y1))
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
            return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "snr": 0.0}
        mean_val = float(np.mean(roi_array))
        std_val = float(np.std(roi_array))
        min_val = float(np.min(roi_array))
        max_val = float(np.max(roi_array))
        snr_val = float(mean_val / std_val) if std_val > 0 else 0.0
        return {"mean": mean_val, "std": std_val, "min": min_val, "max": max_val, "snr": snr_val}

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
            roi_id = str((meta.get("roi_stats") or {}).get("roi_id", ""))
            if "_" in roi_id:
                row_text, col_text = roi_id.split("_", 1)
                if row_text.isdigit() and col_text.isdigit():
                    return {"row": int(row_text), "col": int(col_text)}
        return None

    def _canonicalize_measurement_meta(self, measurement: Measurement, metrics: dict[str, Any]) -> dict[str, Any]:
        raw_meta = dict(measurement.meta or {})
        grid_cell = self._extract_grid_cell_meta(raw_meta)
        roi_role = str(raw_meta.get("roi_role", "none"))
        canonical: dict[str, Any] = {
            "metrics": metrics,
            "roi_role": roi_role,
        }
        if measurement.kind == "roi":
            roi_stats = dict(metrics.get("roi_stats") or {})
            if grid_cell is not None:
                canonical["grid_cell"] = grid_cell
                roi_stats["roi_id"] = f"{grid_cell['row']}_{grid_cell['col']}"
            elif "roi_id" not in roi_stats:
                roi_stats["roi_id"] = measurement.id
            canonical["roi_stats"] = roi_stats
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
        roi_stats: dict[str, Any] | None = None
        if measurement.kind == "roi":
            roi_id = str(measurement.meta.get("roi_stats", {}).get("roi_id") or measurement.id)
            if image_array is None or image_array.ndim < 2:
                roi_stats = {
                    "roi_id": roi_id,
                    "mean": 0.0,
                    "std": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "snr": 0.0,
                    "pixel_width": int(dx_px),
                    "pixel_height": int(dy_px),
                    "width_mm": None if col_mm is None else float(dx_px * col_mm),
                    "height_mm": None if row_mm is None else float(dy_px * row_mm),
                }
            else:
                height, width = image_array.shape[:2]
                x0 = int(np.clip(min(start[0], end[0]), 0, max(width - 1, 0)))
                y0 = int(np.clip(min(start[1], end[1]), 0, max(height - 1, 0)))
                x1 = int(np.clip(max(start[0], end[0]), 0, max(width - 1, 0)))
                y1 = int(np.clip(max(start[1], end[1]), 0, max(height - 1, 0)))
                if x1 <= x0:
                    x1 = min(x0 + 1, width)
                if y1 <= y0:
                    y1 = min(y0 + 1, height)
                stats = self.compute_roi_statistics(image_array[y0:y1, x0:x1])
                roi_stats = {
                    "roi_id": roi_id,
                    "mean": stats["mean"],
                    "std": stats["std"],
                    "min": stats["min"],
                    "max": stats["max"],
                    "snr": stats["snr"],
                    "pixel_width": int(max(x1 - x0, 0)),
                    "pixel_height": int(max(y1 - y0, 0)),
                    "width_mm": None if col_mm is None else float(max(x1 - x0, 0) * col_mm),
                    "height_mm": None if row_mm is None else float(max(y1 - y0, 0) * row_mm),
                }

        result: dict[str, Any] = {
            "pixel_spacing_mm": spacing,
            "width_px": float(dx_px),
            "height_px": float(dy_px),
            "area_px": float(dx_px * dy_px),
            "length_px": float(np.hypot(dx_px, dy_px)),
            "width_mm": None if col_mm is None else float(dx_px * col_mm),
            "height_mm": None if row_mm is None else float(dy_px * row_mm),
            "area_mm2": None if (row_mm is None or col_mm is None) else float(dx_px * dy_px * row_mm * col_mm),
            "length_mm": None if (row_mm is None or col_mm is None) else float(np.hypot(dx_px * col_mm, dy_px * row_mm)),
            "roi_stats": roi_stats,
        }
        if measurement.kind == "roi":
            result["summary"] = self._format_roi_measurement_summary(result)
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
        width_mm_text = f"{self._format_mm_value(metrics['width_mm'])} mm"
        height_mm_text = f"{self._format_mm_value(metrics['height_mm'])} mm"
        area_mm_text = f"{self._format_mm_value(metrics['area_mm2'])} mm²"
        return (
            f"W: {width_mm_text} ({width_px} px)\n"
            f"H: {height_mm_text} ({height_px} px)\n"
            f"Area: {area_mm_text} ({area_px} px²)"
        )

    def _format_line_measurement_summary(self, metrics: dict[str, Any]) -> str:
        px_text = f"{metrics['length_px']:.1f}px"
        mm_value = self._format_mm_value(metrics["length_mm"])
        return f"{px_text} | {mm_value}mm"

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
            primary_label, secondary_label = self._build_measurement_label_parts("roi", metrics)
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
            primary_label, secondary_label = self._build_measurement_label_parts("line", metrics)
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
        self.selected_persistent_measurement_ids = set()
        self._persistent_canvas_item_to_measurement_id = {}
        self._cancel_guided_snr_workflow()
        self.canvas.delete("persistent_measurement")
        self.canvas.delete("temp_measurement")
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def undo_last_measurement(self) -> None:
        if not self.persistent_measurements:
            return
        removed = self.persistent_measurements.pop()
        state = self.guided_snr_state
        if state is not None and removed.id in {state.get("signal_id"), state.get("noise_id")}:
            self._cancel_guided_snr_workflow()
        self.selected_persistent_measurement_ids.discard(removed.id)
        if self.selected_persistent_measurement_id == removed.id:
            self.selected_persistent_measurement_id = None
        self._draw_preview_measurements()
        self._draw_persistent_measurements()
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def clear_selected_measurement(self) -> None:
        selected_ids = set(self.selected_persistent_measurement_ids)
        if self.selected_persistent_measurement_id is not None:
            selected_ids.add(self.selected_persistent_measurement_id)
        if not selected_ids:
            messagebox.showinfo("안내", "삭제할 측정을 먼저 선택하세요.")
            return
        remaining = [item for item in self.persistent_measurements if item.id not in selected_ids]
        if len(remaining) == len(self.persistent_measurements):
            self.selected_persistent_measurement_id = None
            self.selected_persistent_measurement_ids = set()
            self._draw_persistent_measurements()
            return
        state = self.guided_snr_state
        if state is not None and selected_ids.intersection({state.get("signal_id"), state.get("noise_id")}):
            self._cancel_guided_snr_workflow()
        self.persistent_measurements = remaining
        self.selected_persistent_measurement_id = None
        self.selected_persistent_measurement_ids = set()
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
            ctrl_pressed = bool(event.state & 0x4)
            self._apply_measurement_selection(measurement_id, toggle=ctrl_pressed)
            self._draw_persistent_measurements()
            return True
        return False

    def _apply_measurement_selection(self, measurement_id: str, toggle: bool = False) -> None:
        if toggle:
            if measurement_id in self.selected_persistent_measurement_ids:
                self.selected_persistent_measurement_ids.remove(measurement_id)
            else:
                self.selected_persistent_measurement_ids.add(measurement_id)
        else:
            self.selected_persistent_measurement_ids = {measurement_id}
        self.selected_persistent_measurement_id = next(iter(self.selected_persistent_measurement_ids), None)

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
    ) -> Measurement | None:
        geometry_key = self._get_current_geometry_key()
        if geometry_key is None:
            return None
        measurement = Measurement(
            id=str(uuid.uuid4()),
            kind=mode,
            start=(float(image_start[0]), float(image_start[1])),
            end=(float(image_end[0]), float(image_end[1])),
            frame_index=int(self.current_frame),
            geometry_key=geometry_key,
            summary_text="",
            meta={"roi_role": "none"},
        )
        metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
        measurement.summary_text = metrics["summary"]
        measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
        self.persistent_measurements.append(measurement)
        return measurement

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
            and max(x_values) < target_width
            and max(y_values) < target_height
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
            selected = measurement.id in self.selected_persistent_measurement_ids or measurement.id == self.selected_persistent_measurement_id
            if measurement.kind == "roi":
                outline = "#ffdc5e" if selected else "#ff7f50"
                item_id = self.canvas.create_rectangle(
                    sx, sy, ex, ey, outline=outline, width=3 if selected else 2, tags=("persistent_measurement",)
                )
                self.register_measurement_hit_target(item_id, measurement.id)
                if measurement.meta.get("grid_cell") is not None:
                    grid_roi_measurements.append(measurement)
                    continue
                primary_label, secondary_label = self._build_measurement_label_parts("roi", metrics)
                rect_box = (min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey))
                occupied_label_boxes.append(rect_box)
            else:
                color = "#e6ff7a" if selected else "#00ffaa"
                item_id = self.canvas.create_line(
                    sx, sy, ex, ey, fill=color, width=3 if selected else 2, tags=("persistent_measurement",)
                )
                self.register_measurement_hit_target(item_id, measurement.id)
                primary_label, secondary_label = self._build_measurement_label_parts("line", metrics)
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

    def _get_frame_pixel_array(self, frame_index: int) -> np.ndarray | None:
        if not self.frames or not (0 <= frame_index < len(self.frames)):
            return None
        frame = np.asarray(self.frames[frame_index], dtype=np.float32)
        if frame.ndim == 3:
            frame = frame.mean(axis=-1)
        if frame.ndim != 2:
            return None
        return frame

    def _sample_line_profile(self, measurement: Measurement) -> tuple[np.ndarray, np.ndarray] | None:
        frame = self._get_frame_pixel_array(measurement.frame_index)
        if frame is None:
            return None
        x0, y0 = measurement.start
        x1, y1 = measurement.end
        length = int(max(np.hypot(x1 - x0, y1 - y0), 1))
        xs = np.linspace(x0, x1, num=length)
        ys = np.linspace(y0, y1, num=length)
        xi = np.clip(np.round(xs).astype(int), 0, frame.shape[1] - 1)
        yi = np.clip(np.round(ys).astype(int), 0, frame.shape[0] - 1)
        intensity = frame[yi, xi]
        distance = np.linspace(0.0, float(np.hypot(x1 - x0, y1 - y0)), num=length)
        return distance, intensity

    def show_line_profile_for_selected_line(self) -> None:
        lines = [item for item in self.persistent_measurements if item.kind == "line"]
        if not lines:
            messagebox.showinfo("안내", "영구 Line 측정이 없습니다.")
            return
        measurement = lines[-1]
        profile = self._sample_line_profile(measurement)
        if profile is None:
            return
        distance, intensity = profile
        plt.figure(figsize=(7, 4))
        plt.plot(distance, intensity, color="#0a84ff")
        plt.xlabel("Distance (px)")
        plt.ylabel("Intensity")
        plt.title("Line Profile")
        plt.tight_layout()
        plt.show(block=False)
        save_path = filedialog.asksaveasfilename(
            title="라인 프로파일 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")],
        )
        if save_path:
            with open(save_path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["distance_px", "intensity"])
                for d, v in zip(distance, intensity):
                    writer.writerow([f"{float(d):.6f}", f"{float(v):.6f}"])

    def assign_roi_role(self) -> None:
        rois = [item for item in self.persistent_measurements if item.kind == "roi"]
        if not rois:
            messagebox.showinfo("안내", "영구 ROI 측정이 없습니다.")
            return
        role = simple_prompt(
            self.root,
            "ROI 분류 (SNR/CNR)",
            "분석용 ROI 분류 입력 (signal/background/noise 또는 none):",
        )
        if role is None:
            return
        role = role.strip().lower()
        if role not in {"none", "signal", "background", "noise"}:
            messagebox.showwarning("오류", "지원되지 않는 역할입니다.")
            return
        rois[-1].meta["roi_role"] = role
        self._draw_persistent_measurements()

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

    def _find_measurement_by_id(self, measurement_id: str | None) -> Measurement | None:
        if measurement_id is None:
            return None
        for measurement in self.persistent_measurements:
            if measurement.id == measurement_id:
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
            measurement.meta["roi_role"] = "signal"
            state["signal_id"] = measurement.id
            state["step"] = "noise"
            self.snr_workflow_var.set("SNR Step 2/2: Select Noise ROI")
            self._draw_persistent_measurements()
            messagebox.showinfo("SNR Workflow", "Step 2/2: Select Noise ROI")
            return
        if step == "noise":
            measurement.meta["roi_role"] = "noise"
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
        x0, y0 = measurement.start
        x1, y1 = measurement.end
        xmin, xmax = sorted((int(round(x0)), int(round(x1))))
        ymin, ymax = sorted((int(round(y0)), int(round(y1))))
        xmin = int(np.clip(xmin, 0, frame.shape[1] - 1))
        xmax = int(np.clip(xmax, 0, frame.shape[1] - 1))
        ymin = int(np.clip(ymin, 0, frame.shape[0] - 1))
        ymax = int(np.clip(ymax, 0, frame.shape[0] - 1))
        roi = frame[ymin : ymax + 1, xmin : xmax + 1]
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
        role_map = {"signal": None, "background": None, "noise": None}
        for measurement in self.persistent_measurements:
            if measurement.kind != "roi":
                continue
            role = measurement.meta.get("roi_role")
            if role in role_map and role_map[role] is None:
                role_map[role] = measurement
        if role_map["signal"] is None or role_map["noise"] is None or role_map["background"] is None:
            messagebox.showwarning("역할 부족", "CNR 계산에는 signal/background/noise ROI가 필요합니다.")
            return
        signal_stats = self._roi_stats(role_map["signal"])
        noise_stats = self._roi_stats(role_map["noise"])
        background_stats = self._roi_stats(role_map["background"])
        if signal_stats is None or noise_stats is None or background_stats is None:
            messagebox.showwarning("오류", "ROI 통계를 계산할 수 없습니다.")
            return
        signal_mean = signal_stats.mean
        noise_std = noise_stats.std
        if noise_std <= 0:
            messagebox.showwarning("오류", "noise ROI 표준편차가 0입니다.")
            return
        background_mean = background_stats.mean
        cnr = abs(signal_mean - background_mean) / noise_std
        messagebox.showinfo("CNR", f"CNR = {cnr:.4f}")

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
            label_summary = self.compute_measurement(
                measurement,
                self._get_frame_pixel_array(frame_index),
            )["summary"]
            if measurement.kind == "roi":
                draw.rectangle((sx, sy, ex, ey), outline="#ff7f50", width=2)
                if include_labels:
                    draw.text((ex + 4, ey - 14), label_summary, fill="white")
            else:
                draw.line((sx, sy, ex, ey), fill="#00ffaa", width=2)
                if include_labels:
                    draw.text((ex + 4, ey - 14), label_summary, fill="white")
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
        if self.view_mode == "multi" and 0 <= self.current_file_index < len(self.file_paths):
            self.open_multiview_tile(self.current_file_index)
            return "break"
        return ""

    def _handle_escape_shortcut(self, _event: tk.Event) -> str:
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
