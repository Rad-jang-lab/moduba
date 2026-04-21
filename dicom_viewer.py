from pathlib import Path
import json
import csv
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk, simpledialog
from dataclasses import dataclass, field
from copy import deepcopy
from datetime import datetime
import re
from typing import Any
from uuid import uuid4

import numpy as np
import pydicom
from PIL import Image, ImageTk, ImageDraw
from pydicom.errors import InvalidDicomError
from dicom_loader import DicomLoader


@dataclass
class Measurement:
    type: str
    frame_index: int
    coords: tuple[int, int, int, int]
    summary_lines: list[str]
    meta: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class MeasurementSet:
    name: str
    geometry_key: dict[str, Any] | None
    measurements: list[Measurement]
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


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
        self.grid_density = tk.StringVar(value="fine")
        self.cursor_var = tk.StringVar(value="Cursor: -, -")
        self.measurement_mode = tk.StringVar(value="pan")
        self.enable_geometry_filter = tk.BooleanVar(value=True)
        self.include_metadata_stamp = tk.BooleanVar(value=False)
        self.temporary_measurements: list[dict[str, Any]] = []
        self._active_temporary_measurement: dict[str, Any] | None = None
        self.measurements: dict[str, Measurement] = {}
        self.measurement_order: list[str] = []
        self.measurement_sets: dict[str, MeasurementSet] = {}
        self.measurement_set_order: list[str] = []
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

        self.path_var = tk.StringVar(value="파일이 선택되지 않았습니다.")
        self.info_var = tk.StringVar(value="파일을 열면 현재 선택 영상의 요약이 표시됩니다.")
        self.image_var = tk.StringVar(value="이미지: - / -")
        self.frame_var = tk.StringVar(value="프레임: - / -")
        self.window_level_var = tk.StringVar(value="W/L: - / -")
        self.view_mode_var = tk.StringVar(value="보기: 단일")
        self.multiview_page_var = tk.StringVar(value="페이지: - / -")
        self.multiview_grid_var = tk.StringVar(value="격자: 3 x 2")
        self.source_var = tk.StringVar(value="소스: 단일 파일")
        self.compare_sync_status_var = tk.StringVar(value="비교 동기: Off")
        self.shortcut_var = tk.StringVar(
            value=(
                "단축키: F 창맞춤 | 0/Ctrl+0 100% | R W/L 리셋 | "
                "멀티뷰 화살표 선택 | Enter 열기 | Esc 멀티뷰 복귀 | "
                "Home/End 첫/마지막 | PgUp/PgDn 이전/다음 | Shift+PgUp/PgDn 프레임"
            )
        )
        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="x")

        self.open_file_button = ttk.Button(top, text="DICOM 열기", command=self.open_file)
        self.open_file_button.pack(side="left")
        self.open_folder_button = ttk.Button(top, text="폴더 열기", command=self.open_folder)
        self.open_folder_button.pack(side="left", padx=(8, 0))
        self.diagnose_button = ttk.Button(top, text="폴더 진단", command=self.diagnose_folder)
        self.diagnose_button.pack(side="left", padx=(8, 0))
        self.toggle_view_button = ttk.Button(top, text="단일/멀티 전환", command=self.toggle_view_mode)
        self.toggle_view_button.pack(side="left", padx=(16, 0))
        self.prev_image_button = ttk.Button(top, text="이전 이미지", command=lambda: self.change_file(-1))
        self.prev_image_button.pack(side="left", padx=(16, 0))
        self.next_image_button = ttk.Button(top, text="다음 이미지", command=lambda: self.change_file(1))
        self.next_image_button.pack(side="left", padx=(8, 0))
        self.prev_frame_button = ttk.Button(top, text="이전 프레임", command=lambda: self.change_frame(-1))
        self.prev_frame_button.pack(side="left", padx=(16, 0))
        self.next_frame_button = ttk.Button(top, text="다음 프레임", command=lambda: self.change_frame(1))
        self.next_frame_button.pack(side="left", padx=(8, 0))
        self.window_level_reset_button = ttk.Button(top, text="W/L 리셋", command=self.reset_window_level)
        self.window_level_reset_button.pack(side="left", padx=(16, 0))
        ttk.Checkbutton(
            top,
            text="Invert",
            variable=self.invert_display,
            command=self._refresh_single_view_image,
        ).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(
            top,
            text="Grid",
            variable=self.show_grid_overlay,
            command=self._refresh_grid_overlay,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(top, text="Grid 밀도").pack(side="left", padx=(8, 0))
        ttk.Combobox(
            top,
            state="readonly",
            width=8,
            textvariable=self.grid_density,
            values=("coarse", "fine"),
        ).pack(side="left", padx=(4, 0))
        self.grid_density.trace_add("write", self._on_grid_density_change)
        ttk.Radiobutton(top, text="Pan", value="pan", variable=self.measurement_mode).pack(side="left", padx=(12, 0))
        ttk.Radiobutton(top, text="ROI", value="roi", variable=self.measurement_mode).pack(side="left", padx=(4, 0))
        ttk.Radiobutton(top, text="Line", value="line", variable=self.measurement_mode).pack(side="left", padx=(4, 0))
        ttk.Checkbutton(
            top,
            text="Geometry Match Only",
            variable=self.enable_geometry_filter,
            command=self._refresh_measurement_render,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="임시 측정 지우기", command=self.clear_temporary_measurements).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="측정 지우기", command=self.clear_measurements).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="측정 세트 저장", command=self.create_measurement_set).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="측정 세트 적용", command=self._apply_selected_measurement_set).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="세트 JSON 저장", command=self.export_measurement_set_json).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="세트 JSON 불러오기", command=self.import_measurement_set_json).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="측정 CSV 저장", command=self.export_measurements_csv).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="라인 프로파일 보기", command=self._show_selected_line_profile).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="ROI 역할 지정", command=self.assign_roi_role).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="SNR 계산", command=self.calculate_snr).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="CNR 계산", command=self.calculate_cnr).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="SNR 결과 저장", command=self.save_snr_result).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="CNR 결과 저장", command=self.save_cnr_result).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="전체 SNR 저장", command=self.export_all_snr_results_csv).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="전체 CNR 저장", command=self.export_all_cnr_results_csv).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="화면 캡처 저장", command=self.export_view_screenshot).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="논문용 그림 저장", command=self.export_clean_figure).pack(side="left", padx=(4, 0))
        ttk.Checkbutton(
            top,
            text="Compare Mode",
            variable=self.compare_mode_enabled,
            command=self.toggle_compare_mode,
        ).pack(side="left", padx=(16, 0))
        ttk.Checkbutton(
            top,
            text="Sync",
            variable=self.compare_sync_enabled,
            command=self._update_compare_sync_status,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Swap Left/Right", command=self.swap_compare_panels).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(
            top,
            text="기본 정보 오버레이",
            variable=self.show_basic_overlay,
            command=self.refresh_overlay_display,
        ).pack(side="left", padx=(16, 0))
        ttk.Checkbutton(
            top,
            text="촬영 정보 오버레이",
            variable=self.show_acquisition_overlay,
            command=self.refresh_overlay_display,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="오버레이 항목 설정", command=self.open_overlay_settings).pack(side="left", padx=(12, 0))

        ttk.Label(top, textvariable=self.view_mode_var).pack(side="left", padx=(12, 0))
        ttk.Label(top, textvariable=self.compare_sync_status_var).pack(side="left", padx=(12, 0))
        ttk.Label(top, textvariable=self.source_var).pack(side="left", padx=(12, 0))
        ttk.Label(top, textvariable=self.image_var).pack(side="left", padx=(12, 0))
        ttk.Label(top, textvariable=self.frame_var).pack(side="left", padx=(12, 0))
        ttk.Label(top, textvariable=self.zoom_var).pack(side="left", padx=(12, 0))
        ttk.Label(top, textvariable=self.window_level_var).pack(side="left", padx=(12, 0))
        ttk.Label(top, textvariable=self.cursor_var).pack(side="left", padx=(12, 0))

        ttk.Label(self.root, textvariable=self.path_var, padding=(12, 0)).pack(fill="x")
        ttk.Label(self.root, textvariable=self.info_var, padding=(12, 6), justify="left", wraplength=1040).pack(fill="x")
        ttk.Label(self.root, textvariable=self.shortcut_var, padding=(12, 0, 12, 6)).pack(fill="x")

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
        self.canvas.bind("<ButtonPress-3>", self._start_window_level_drag)
        self.canvas.bind("<B3-Motion>", self._update_window_level_drag)
        self.canvas.bind("<ButtonRelease-3>", self._end_window_level_drag)
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

    def _bind_shortcuts(self) -> None:
        bindings = [
            ("f", self._handle_fit_shortcut),
            ("F", self._handle_fit_shortcut),
            ("0", self._handle_actual_size_shortcut),
            ("<Control-0>", self._handle_actual_size_shortcut),
            ("r", self._handle_window_level_reset_shortcut),
            ("R", self._handle_window_level_reset_shortcut),
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

        shadow_offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for index, (dx, dy) in enumerate(shadow_offsets):
            canvas.create_text(
                x + dx,
                y + dy,
                text=text,
                anchor=anchor,
                fill="black",
                font=font,
                justify=justify,
                width=max_width,
                tags=(f"{tag_prefix}_shadow_{index}", "overlay"),
            )

        canvas.create_text(
            x,
            y,
            text=text,
            anchor=anchor,
            fill="white",
            font=font,
            justify=justify,
            width=max_width,
            tags=(tag_prefix, "overlay"),
        )

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
        self.path_var.set("파일이 선택되지 않았습니다.")
        self.info_var.set("파일을 열면 현재 선택 영상의 요약이 표시됩니다.")
        self.cursor_var.set("Cursor: -, -")
        for field in self.overlay_field_definitions:
            self.current_overlay_values[field["key"]] = "N/A"
        self.canvas.delete("overlay")
        self.canvas.delete("grid_overlay")
        self.clear_temporary_measurements()
        self.clear_measurements()
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
        self.clear_temporary_measurements()
        self.clear_measurements()
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
        if self.measurement_mode.get() == "pan":
            self._start_pan(event)
            return
        self._start_temporary_measurement(event)

    def _handle_left_button_drag(self, event: tk.Event) -> None:
        if self.measurement_mode.get() == "pan":
            self._update_pan(event)
            return
        self._update_temporary_measurement(event)

    def _handle_left_button_release(self, event: tk.Event) -> None:
        if self.measurement_mode.get() == "pan":
            self._end_pan(event)
            return
        self._finish_temporary_measurement(event)

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

    def _canvas_to_image_pixel(self, canvas_x: float, canvas_y: float) -> tuple[int, int] | None:
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
        pixel_x = int(np.clip(np.floor(x_ratio * width), 0, width - 1))
        pixel_y = int(np.clip(np.floor(y_ratio * height), 0, height - 1))
        return pixel_x, pixel_y

    def _canvas_to_image_coords(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> tuple[int, int, int, int] | None:
        start = self._canvas_to_image_pixel(x1, y1)
        end = self._canvas_to_image_pixel(x2, y2)
        if start is None or end is None:
            return None
        return start[0], start[1], end[0], end[1]

    def _start_temporary_measurement(self, event: tk.Event) -> None:
        if not self.frames or self.view_mode != "single":
            return
        mode = self.measurement_mode.get()
        if mode not in {"roi", "line"}:
            return
        start_x = self.canvas.canvasx(event.x)
        start_y = self.canvas.canvasy(event.y)
        if mode == "roi":
            item_id = self.canvas.create_rectangle(
                start_x, start_y, start_x, start_y, outline="#ffd34d", width=2, dash=(4, 2), tags=("temp_measurement",)
            )
        else:
            item_id = self.canvas.create_line(
                start_x, start_y, start_x, start_y, fill="#7bdff2", width=2, tags=("temp_measurement",)
            )
        self._active_temporary_measurement = {
            "mode": mode,
            "item_id": item_id,
            "start": (start_x, start_y),
            "end": (start_x, start_y),
        }

    def _update_temporary_measurement(self, event: tk.Event) -> None:
        if self._active_temporary_measurement is None:
            return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        start_x, start_y = self._active_temporary_measurement["start"]
        self._active_temporary_measurement["end"] = (end_x, end_y)
        self.canvas.coords(self._active_temporary_measurement["item_id"], start_x, start_y, end_x, end_y)

    def _finish_temporary_measurement(self, event: tk.Event) -> None:
        if self._active_temporary_measurement is None:
            return
        self._update_temporary_measurement(event)
        mode = self._active_temporary_measurement["mode"]
        start_x, start_y = self._active_temporary_measurement["start"]
        end_x, end_y = self._active_temporary_measurement["end"]
        image_coords = self._canvas_to_image_coords(start_x, start_y, end_x, end_y)
        self.canvas.delete(self._active_temporary_measurement["item_id"])
        self._active_temporary_measurement = None
        if image_coords is None:
            return
        image_start = (image_coords[0], image_coords[1])
        image_end = (image_coords[2], image_coords[3])
        if mode == "roi":
            summary_lines = self._build_roi_measurement_summary(image_start, image_end)
        else:
            summary_lines = self._build_line_measurement_summary(image_start, image_end)
        measurement = self._create_measurement(
            mode=mode,
            frame_index=self.current_frame,
            start=image_start,
            end=image_end,
            summary_lines=summary_lines,
        )
        self.measurements[measurement.id] = measurement
        self.measurement_order.append(measurement.id)
        self.temporary_measurements.append(
            {
                "measurement_id": measurement.id,
                "mode": mode,
                "start": image_start,
                "end": image_end,
                "summary_lines": summary_lines,
            }
        )
        self._draw_persistent_measurements()
        self._draw_temporary_measurements()

    def _create_measurement(
        self,
        mode: str,
        frame_index: int,
        start: tuple[int, int],
        end: tuple[int, int],
        summary_lines: list[str],
    ) -> Measurement:
        x1, y1 = start
        x2, y2 = end
        return Measurement(
            type=mode,
            frame_index=frame_index,
            coords=(x1, y1, x2, y2),
            summary_lines=list(summary_lines),
            meta={
                "source": "temporary_tool",
                "geometry_key": self._get_current_geometry_key(),
                "roi_role": "none" if mode == "roi" else "",
            },
        )

    def _build_geometry_key(self) -> dict[str, Any] | None:
        if self.dataset is None or not self.frames:
            return None
        frame_array = np.asarray(self.frames[self.current_frame])
        if frame_array.ndim < 2:
            return None
        rows, cols = frame_array.shape[:2]
        return {
            "rows": int(rows),
            "cols": int(cols),
            "pixel_spacing": self._extract_spacing_tuple(getattr(self.dataset, "PixelSpacing", None)),
            "imager_pixel_spacing": self._extract_spacing_tuple(getattr(self.dataset, "ImagerPixelSpacing", None)),
        }

    def _extract_spacing_tuple(self, spacing_value) -> tuple[float, float] | None:
        if spacing_value is None:
            return None
        try:
            row_spacing = float(spacing_value[0])
            col_spacing = float(spacing_value[1])
        except (TypeError, ValueError, IndexError):
            return None
        return row_spacing, col_spacing

    def _get_current_geometry_key(self) -> dict[str, Any] | None:
        return self._build_geometry_key()

    def _geometry_matches(self, key1: dict[str, Any] | None, key2: dict[str, Any] | None) -> bool:
        if key1 is None or key2 is None:
            return False
        return (
            key1.get("rows") == key2.get("rows")
            and key1.get("cols") == key2.get("cols")
            and key1.get("pixel_spacing") == key2.get("pixel_spacing")
            and key1.get("imager_pixel_spacing") == key2.get("imager_pixel_spacing")
        )

    def _get_applicable_measurements(self) -> list[Measurement]:
        current_key = self._get_current_geometry_key()
        result: list[Measurement] = []
        for measurement_id in self.measurement_order:
            measurement = self.measurements.get(measurement_id)
            if measurement is None:
                continue
            measurement_key = measurement.meta.get("geometry_key")
            if self._geometry_matches(current_key, measurement_key):
                result.append(measurement)
        return result

    def _image_pixel_to_canvas(self, pixel_x: int, pixel_y: int) -> tuple[float, float] | None:
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
        canvas_x = left + (float(pixel_x) / width) * display_width
        canvas_y = top + (float(pixel_y) / height) * display_height
        return canvas_x, canvas_y

    def _image_to_canvas_coords(
        self, x1: int, y1: int, x2: int, y2: int
    ) -> tuple[float, float, float, float] | None:
        start = self._image_pixel_to_canvas(x1, y1)
        end = self._image_pixel_to_canvas(x2, y2)
        if start is None or end is None:
            return None
        return start[0], start[1], end[0], end[1]

    def _draw_persistent_measurements(self) -> None:
        self.canvas.delete("persistent_measurement")
        for measurement in self._get_renderable_persistent_measurements():
            x1, y1, x2, y2 = measurement.coords
            canvas_coords = self._image_to_canvas_coords(x1, y1, x2, y2)
            if canvas_coords is None:
                continue
            start_x, start_y, end_x, end_y = canvas_coords
            if measurement.type == "roi":
                self.canvas.create_rectangle(
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    outline="#ff9f43",
                    width=2,
                    tags=("persistent_measurement",),
                )
            elif measurement.type == "line":
                self.canvas.create_line(
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    fill="#54a0ff",
                    width=2,
                    tags=("persistent_measurement",),
                )
            else:
                continue

            label_lines = list(measurement.summary_lines)
            if measurement.type == "roi":
                roi_role = str(measurement.meta.get("roi_role", "none")).strip().lower() or "none"
                if roi_role != "none":
                    label_lines = [f"ROI [{roi_role}]"] + label_lines
            self.canvas.create_text(
                end_x + 6,
                end_y - 6,
                text="\n".join(label_lines),
                fill="white",
                anchor="sw",
                font=("TkDefaultFont", 9, "bold"),
                tags=("persistent_measurement",),
            )

    def _get_renderable_persistent_measurements(self) -> list[Measurement]:
        if self.enable_geometry_filter.get():
            measurements = self._get_applicable_measurements()
        else:
            measurements = [
                measurement
                for measurement_id in self.measurement_order
                if (measurement := self.measurements.get(measurement_id)) is not None
            ]
        return [
            measurement
            for measurement in measurements
            if measurement.frame_index == self.current_frame
        ]

    def _select_line_measurement(self) -> Measurement | None:
        line_measurements = [
            measurement
            for measurement in self._get_renderable_persistent_measurements()
            if measurement.type == "line"
        ]
        if not line_measurements:
            messagebox.showinfo("라인 프로파일", "현재 프레임에 라인 측정이 없습니다.")
            return None
        if len(line_measurements) == 1:
            return line_measurements[0]

        lines = []
        for index, measurement in enumerate(line_measurements, start=1):
            lines.append(f"{index}. {measurement.id[:8]} ({' | '.join(measurement.summary_lines)})")
        selection = simpledialog.askinteger(
            "라인 프로파일",
            "라인 측정 번호를 선택하세요:\n\n" + "\n".join(lines),
            parent=self.root,
            minvalue=1,
            maxvalue=len(line_measurements),
        )
        if selection is None:
            return None
        return line_measurements[selection - 1]

    def _extract_line_profile(
        self, measurement: Measurement
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
        if measurement.type != "line":
            raise ValueError("라인 측정만 프로파일 추출이 가능합니다.")
        if not (0 <= measurement.frame_index < len(self.frames)):
            raise ValueError("측정 프레임 인덱스가 현재 데이터 범위를 벗어났습니다.")

        frame = np.asarray(self.frames[measurement.frame_index])
        if frame.ndim < 2:
            raise ValueError("프로파일 추출을 지원하지 않는 프레임 형식입니다.")
        values_source = frame.astype(np.float32)
        if values_source.ndim == 3:
            values_source = np.mean(values_source, axis=-1)

        x1, y1, x2, y2 = measurement.coords
        dx = x2 - x1
        dy = y2 - y1
        sample_count = int(max(abs(dx), abs(dy))) + 1
        sample_count = max(sample_count, 2)

        x_samples = np.linspace(x1, x2, sample_count)
        y_samples = np.linspace(y1, y2, sample_count)
        x_indices = np.clip(np.rint(x_samples).astype(int), 0, values_source.shape[1] - 1)
        y_indices = np.clip(np.rint(y_samples).astype(int), 0, values_source.shape[0] - 1)
        values = values_source[y_indices, x_indices]

        distance_px = np.hypot(x_samples - x1, y_samples - y1)
        spacing = self._get_pixel_spacing()
        distance_mm = None
        if spacing is not None:
            row_spacing, col_spacing = spacing
            distance_mm = np.hypot((x_samples - x1) * col_spacing, (y_samples - y1) * row_spacing)
        return distance_px, values, distance_mm

    def show_line_profile(self, measurement: Measurement) -> None:
        try:
            distance_px, values, distance_mm = self._extract_line_profile(measurement)
        except Exception as exc:
            messagebox.showerror("라인 프로파일", f"프로파일을 생성하지 못했습니다.\n\n{exc}")
            return

        try:
            import matplotlib.pyplot as plt
        except Exception as exc:
            messagebox.showerror("라인 프로파일", f"matplotlib을 불러오지 못했습니다.\n\n{exc}")
            return

        plt.figure(figsize=(8, 4.5))
        plt.plot(distance_px, values, color="#1f77b4", label="Intensity")
        plt.xlabel("Distance (px)")
        plt.ylabel("Intensity")
        title = f"Line Profile - {measurement.id[:8]}"
        if distance_mm is not None:
            title += f" ({distance_mm[-1]:.2f} mm)"
        plt.title(title)
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.tight_layout()
        plt.show()

    def export_line_profile_csv(self, measurement: Measurement) -> None:
        try:
            distance_px, values, distance_mm = self._extract_line_profile(measurement)
        except Exception as exc:
            messagebox.showerror("라인 프로파일 CSV", f"프로파일 추출에 실패했습니다.\n\n{exc}")
            return

        path = filedialog.asksaveasfilename(
            title="라인 프로파일 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV files", ".csv"), ("All files", ".*")],
            initialfile=f"line_profile_{measurement.id[:8]}.csv",
        )
        if not path:
            return

        fieldnames = ["distance_px", "intensity"]
        if distance_mm is not None:
            fieldnames.append("distance_mm")

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fp:
                writer = csv.DictWriter(fp, fieldnames=fieldnames)
                writer.writeheader()
                for index in range(len(distance_px)):
                    row = {
                        "distance_px": f"{float(distance_px[index]):.6f}",
                        "intensity": f"{float(values[index]):.6f}",
                    }
                    if distance_mm is not None:
                        row["distance_mm"] = f"{float(distance_mm[index]):.6f}"
                    writer.writerow(row)
        except Exception as exc:
            messagebox.showerror("라인 프로파일 CSV", f"CSV 저장에 실패했습니다.\n\n{exc}")
            return

        messagebox.showinfo("라인 프로파일 CSV", f"라인 프로파일 CSV를 저장했습니다.\n\n{path}")

    def _show_selected_line_profile(self) -> None:
        measurement = self._select_line_measurement()
        if measurement is None:
            return
        self.show_line_profile(measurement)
        if messagebox.askyesno("라인 프로파일 CSV", "프로파일 CSV도 저장하시겠습니까?"):
            self.export_line_profile_csv(measurement)

    def _select_roi_measurement(
        self, title: str = "ROI 선택", candidates: list[Measurement] | None = None
    ) -> Measurement | None:
        roi_measurements = candidates
        if roi_measurements is None:
            roi_measurements = [
                measurement
                for measurement in self._get_renderable_persistent_measurements()
                if measurement.type == "roi"
            ]
        if not roi_measurements:
            messagebox.showinfo(title, "선택 가능한 ROI 측정이 없습니다.")
            return None
        if len(roi_measurements) == 1:
            return roi_measurements[0]

        lines = []
        for index, measurement in enumerate(roi_measurements, start=1):
            role = str(measurement.meta.get("roi_role", "none"))
            lines.append(f"{index}. {measurement.id[:8]} [{role}]")
        selection = simpledialog.askinteger(
            title,
            "ROI 번호를 선택하세요:\n\n" + "\n".join(lines),
            parent=self.root,
            minvalue=1,
            maxvalue=len(roi_measurements),
        )
        if selection is None:
            return None
        return roi_measurements[selection - 1]

    def _select_roi_role(self, current_role: str = "none") -> str | None:
        role_text = simpledialog.askstring(
            "ROI 역할 지정",
            f"역할을 입력하세요 (none/signal/background/noise)\n현재: {current_role}",
            parent=self.root,
        )
        if role_text is None:
            return None
        role = role_text.strip().lower()
        allowed_roles = {"none", "signal", "background", "noise"}
        if role not in allowed_roles:
            messagebox.showwarning("ROI 역할 지정", "허용되지 않는 역할입니다. none/signal/background/noise 중에서 선택하세요.")
            return None
        return role

    def assign_roi_role(self) -> None:
        measurement = self._select_roi_measurement(title="ROI 역할 지정")
        if measurement is None:
            return
        current_role = str(measurement.meta.get("roi_role", "none"))
        role = self._select_roi_role(current_role=current_role)
        if role is None:
            return
        measurement.meta["roi_role"] = role
        self._draw_persistent_measurements()
        messagebox.showinfo("ROI 역할 지정", f"ROI 역할을 설정했습니다.\n\n{measurement.id[:8]} -> {role}")

    def _get_roi_stats_from_measurement(self, measurement: Measurement) -> dict[str, float] | None:
        if measurement.type != "roi":
            return None
        if not (0 <= measurement.frame_index < len(self.frames)):
            return None
        frame = np.asarray(self.frames[measurement.frame_index])
        if frame.ndim < 2:
            return None

        x1, y1, x2, y2 = measurement.coords
        x_min, x_max = sorted((x1, x2))
        y_min, y_max = sorted((y1, y2))
        x_min = int(np.clip(x_min, 0, frame.shape[1] - 1))
        x_max = int(np.clip(x_max, 0, frame.shape[1] - 1))
        y_min = int(np.clip(y_min, 0, frame.shape[0] - 1))
        y_max = int(np.clip(y_max, 0, frame.shape[0] - 1))
        roi = frame[y_min : y_max + 1, x_min : x_max + 1]
        if roi.size == 0:
            return None

        values = roi.astype(np.float32)
        if values.ndim == 3:
            values = np.mean(values, axis=-1)
        return {
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "width_px": float(x_max - x_min + 1),
            "height_px": float(y_max - y_min + 1),
        }

    def _get_roi_measurements_by_role(self, role: str) -> list[Measurement]:
        role_normalized = role.strip().lower()
        return [
            measurement
            for measurement in self._get_renderable_persistent_measurements()
            if measurement.type == "roi" and str(measurement.meta.get("roi_role", "none")).strip().lower() == role_normalized
        ]

    @staticmethod
    def _analysis_result_columns() -> list[str]:
        return [
            "analysis_type",
            "frame_index",
            "signal_measurement_id",
            "background_measurement_id",
            "noise_measurement_id",
            "signal_mean",
            "background_mean",
            "noise_std",
            "result_value",
            "source_path",
            "sop_instance_uid",
            "series_instance_uid",
            "rows",
            "cols",
            "pixel_spacing",
            "imager_pixel_spacing",
        ]

    @staticmethod
    def _serialize_analysis_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return ",".join(str(item) for item in value)
        return str(value)

    def _build_analysis_context(self, measurement: Measurement) -> dict[str, str]:
        geometry_key = measurement.meta.get("geometry_key", {})
        return {
            "source_path": self._serialize_analysis_value(measurement.meta.get("source_path", "")),
            "sop_instance_uid": self._serialize_analysis_value(measurement.meta.get("sop_instance_uid", "")),
            "series_instance_uid": self._serialize_analysis_value(measurement.meta.get("series_instance_uid", "")),
            "rows": self._serialize_analysis_value(geometry_key.get("rows", "")),
            "cols": self._serialize_analysis_value(geometry_key.get("cols", "")),
            "pixel_spacing": self._serialize_analysis_value(geometry_key.get("pixel_spacing", "")),
            "imager_pixel_spacing": self._serialize_analysis_value(geometry_key.get("imager_pixel_spacing", "")),
        }

    def _build_snr_result(
        self, signal_measurement: Measurement, noise_measurement: Measurement
    ) -> dict[str, Any] | None:
        signal_stats = self._get_roi_stats_from_measurement(signal_measurement)
        noise_stats = self._get_roi_stats_from_measurement(noise_measurement)
        if signal_stats is None or noise_stats is None:
            return None
        noise_std = float(noise_stats["std"])
        if noise_std <= 0:
            return None
        context = self._build_analysis_context(signal_measurement)
        snr_value = float(signal_stats["mean"]) / noise_std
        return {
            "analysis_type": "SNR",
            "frame_index": signal_measurement.frame_index,
            "signal_measurement_id": signal_measurement.id,
            "background_measurement_id": "",
            "noise_measurement_id": noise_measurement.id,
            "signal_mean": float(signal_stats["mean"]),
            "background_mean": "",
            "noise_std": noise_std,
            "result_value": snr_value,
            **context,
        }

    def _build_cnr_result(
        self,
        signal_measurement: Measurement,
        background_measurement: Measurement,
        noise_measurement: Measurement,
    ) -> dict[str, Any] | None:
        signal_stats = self._get_roi_stats_from_measurement(signal_measurement)
        background_stats = self._get_roi_stats_from_measurement(background_measurement)
        noise_stats = self._get_roi_stats_from_measurement(noise_measurement)
        if signal_stats is None or background_stats is None or noise_stats is None:
            return None
        noise_std = float(noise_stats["std"])
        if noise_std <= 0:
            return None
        context = self._build_analysis_context(signal_measurement)
        cnr_value = abs(float(signal_stats["mean"]) - float(background_stats["mean"])) / noise_std
        return {
            "analysis_type": "CNR",
            "frame_index": signal_measurement.frame_index,
            "signal_measurement_id": signal_measurement.id,
            "background_measurement_id": background_measurement.id,
            "noise_measurement_id": noise_measurement.id,
            "signal_mean": float(signal_stats["mean"]),
            "background_mean": float(background_stats["mean"]),
            "noise_std": noise_std,
            "result_value": cnr_value,
            **context,
        }

    def export_analysis_result_csv(self, result_dict: dict[str, Any], prompt: bool = True) -> None:
        analysis_type = str(result_dict.get("analysis_type", "")).upper()
        default_name = "moduba_snr_result.csv" if analysis_type == "SNR" else "moduba_cnr_result.csv"
        path = filedialog.asksaveasfilename(
            title=f"{analysis_type or '분석'} 결과 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV files", ".csv"), ("All files", ".*")],
            initialfile=default_name,
        )
        if not path:
            return

        columns = self._analysis_result_columns()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fp:
                writer = csv.DictWriter(fp, fieldnames=columns)
                writer.writeheader()
                writer.writerow({key: self._serialize_analysis_value(result_dict.get(key, "")) for key in columns})
        except Exception as exc:
            messagebox.showerror("분석 결과 저장 실패", f"CSV 저장 중 오류가 발생했습니다.\n\n{exc}")
            return
        if prompt:
            messagebox.showinfo("분석 결과 저장", f"분석 결과를 CSV로 저장했습니다.\n\n{path}")

    def _export_analysis_rows_csv(self, rows: list[dict[str, Any]], analysis_type: str) -> None:
        if not rows:
            messagebox.showinfo(f"전체 {analysis_type} 저장", "저장할 유효 결과가 없습니다.")
            return
        default_name = "moduba_snr_result.csv" if analysis_type == "SNR" else "moduba_cnr_result.csv"
        path = filedialog.asksaveasfilename(
            title=f"전체 {analysis_type} 결과 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV files", ".csv"), ("All files", ".*")],
            initialfile=default_name,
        )
        if not path:
            return
        columns = self._analysis_result_columns()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fp:
                writer = csv.DictWriter(fp, fieldnames=columns)
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: self._serialize_analysis_value(row.get(key, "")) for key in columns})
        except Exception as exc:
            messagebox.showerror(f"전체 {analysis_type} 저장 실패", f"CSV 저장 중 오류가 발생했습니다.\n\n{exc}")
            return
        messagebox.showinfo(f"전체 {analysis_type} 저장", f"{len(rows)}개 결과를 CSV로 저장했습니다.\n\n{path}")

    def _run_interactive_snr(self) -> dict[str, Any] | None:
        signal_candidates = self._get_roi_measurements_by_role("signal")
        noise_candidates = self._get_roi_measurements_by_role("noise")
        if not signal_candidates or not noise_candidates:
            messagebox.showinfo("SNR 계산", "signal ROI와 noise ROI를 각각 최소 1개 지정해야 합니다.")
            return None

        signal_roi = self._select_roi_measurement("SNR - signal ROI 선택", signal_candidates)
        if signal_roi is None:
            return None
        noise_roi = self._select_roi_measurement("SNR - noise ROI 선택", noise_candidates)
        if noise_roi is None:
            return None

        result = self._build_snr_result(signal_roi, noise_roi)
        if result is None:
            messagebox.showwarning("SNR 계산", "noise ROI의 표준편차가 0이거나 ROI 통계를 계산할 수 없습니다.")
            return None
        return result

    def calculate_snr(self) -> None:
        result = self._run_interactive_snr()
        if result is None:
            return
        messagebox.showinfo(
            "SNR 계산 결과",
            (
                f"SNR = mean(signal) / std(noise)\n\n"
                f"signal mean: {float(result['signal_mean']):.4f}\n"
                f"noise std: {float(result['noise_std']):.4f}\n"
                f"SNR: {float(result['result_value']):.4f}"
            ),
        )
        if messagebox.askyesno("SNR 계산 결과", "계산 결과를 CSV로 저장하시겠습니까?"):
            self.export_analysis_result_csv(result)

    def _run_interactive_cnr(self) -> dict[str, Any] | None:
        signal_candidates = self._get_roi_measurements_by_role("signal")
        background_candidates = self._get_roi_measurements_by_role("background")
        noise_candidates = self._get_roi_measurements_by_role("noise")
        if not signal_candidates or not background_candidates or not noise_candidates:
            messagebox.showinfo("CNR 계산", "signal/background/noise ROI를 각각 최소 1개 지정해야 합니다.")
            return None

        signal_roi = self._select_roi_measurement("CNR - signal ROI 선택", signal_candidates)
        if signal_roi is None:
            return None
        background_roi = self._select_roi_measurement("CNR - background ROI 선택", background_candidates)
        if background_roi is None:
            return None
        noise_roi = self._select_roi_measurement("CNR - noise ROI 선택", noise_candidates)
        if noise_roi is None:
            return None

        result = self._build_cnr_result(signal_roi, background_roi, noise_roi)
        if result is None:
            messagebox.showwarning("CNR 계산", "noise ROI의 표준편차가 0이거나 ROI 통계를 계산할 수 없습니다.")
            return None
        return result

    def calculate_cnr(self) -> None:
        result = self._run_interactive_cnr()
        if result is None:
            return
        messagebox.showinfo(
            "CNR 계산 결과",
            (
                f"CNR = |mean(signal)-mean(background)| / std(noise)\n\n"
                f"signal mean: {float(result['signal_mean']):.4f}\n"
                f"background mean: {float(result['background_mean']):.4f}\n"
                f"noise std: {float(result['noise_std']):.4f}\n"
                f"CNR: {float(result['result_value']):.4f}"
            ),
        )
        if messagebox.askyesno("CNR 계산 결과", "계산 결과를 CSV로 저장하시겠습니까?"):
            self.export_analysis_result_csv(result)

    def save_snr_result(self) -> None:
        result = self._run_interactive_snr()
        if result is None:
            return
        self.export_analysis_result_csv(result)

    def save_cnr_result(self) -> None:
        result = self._run_interactive_cnr()
        if result is None:
            return
        self.export_analysis_result_csv(result)

    def export_all_snr_results_csv(self) -> None:
        signals = self._get_roi_measurements_by_role("signal")
        noises = self._get_roi_measurements_by_role("noise")
        rows = []
        for signal in signals:
            for noise in noises:
                result = self._build_snr_result(signal, noise)
                if result is not None:
                    rows.append(result)
        self._export_analysis_rows_csv(rows, "SNR")

    def export_all_cnr_results_csv(self) -> None:
        signals = self._get_roi_measurements_by_role("signal")
        backgrounds = self._get_roi_measurements_by_role("background")
        noises = self._get_roi_measurements_by_role("noise")
        rows = []
        for signal in signals:
            for background in backgrounds:
                for noise in noises:
                    result = self._build_cnr_result(signal, background, noise)
                    if result is not None:
                        rows.append(result)
        self._export_analysis_rows_csv(rows, "CNR")

    def _sanitize_filename_component(self, value: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value.strip())
        cleaned = re.sub(r"_+", "_", cleaned).strip("._")
        return cleaned or "unknown"

    def _get_export_filename_stub(self, prefix: str) -> str:
        parts = [prefix, f"frame{self.current_frame}"]
        if self.dataset is not None:
            series = str(getattr(self.dataset, "SeriesDescription", "")).strip()
            view_position = str(getattr(self.dataset, "ViewPosition", "")).strip()
            laterality = str(getattr(self.dataset, "ImageLaterality", "")).strip()
            sop_uid = str(getattr(self.dataset, "SOPInstanceUID", "")).strip()
            if series:
                parts.append(f"series{self._sanitize_filename_component(series)}")
            if view_position:
                parts.append(self._sanitize_filename_component(view_position))
            if laterality:
                parts.append(self._sanitize_filename_component(laterality))
            if sop_uid:
                parts.append(self._sanitize_filename_component(sop_uid[-8:]))
        return "_".join(parts)

    def _build_export_base_image(self) -> Image.Image | None:
        if not self.frames:
            return None
        frame = self.frames[self.current_frame]
        normalized = self._normalize_frame(frame)
        pil_image = Image.fromarray(normalized)
        return self._resize_image_for_display(pil_image)

    def _draw_measurements_on_pil(
        self,
        pil_image: Image.Image,
        image_origin: tuple[float, float],
        include_temporary: bool = True,
        include_persistent: bool = True,
        include_grid: bool = True,
    ) -> None:
        if self._image_bbox is None or not self.frames:
            return
        draw = ImageDraw.Draw(pil_image)
        left, top, right, bottom = self._image_bbox
        image_left, image_top = image_origin
        display_width = max(right - left, 1.0)
        display_height = max(bottom - top, 1.0)
        frame_array = np.asarray(self.frames[self.current_frame])
        frame_height, frame_width = frame_array.shape[:2]

        def image_to_export_coords(x: int, y: int) -> tuple[float, float]:
            x_canvas = left + (float(x) / frame_width) * display_width
            y_canvas = top + (float(y) / frame_height) * display_height
            return x_canvas - image_left, y_canvas - image_top
        origin_x, origin_y = image_to_export_coords(0, 0)

        if include_grid and self.show_grid_overlay.get():
            density = self.grid_density.get()
            columns, rows, major_step = (12, 12, 3) if density == "coarse" else (24, 24, 4)
            for column in range(1, columns):
                x = (display_width * column / columns)
                fill = "#7ad9ef" if (column % major_step) == 0 else "#4aaec7"
                draw.line([(origin_x + x, origin_y), (origin_x + x, origin_y + display_height)], fill=fill, width=1)
            for row in range(1, rows):
                y = (display_height * row / rows)
                fill = "#7ad9ef" if (row % major_step) == 0 else "#4aaec7"
                draw.line([(origin_x, origin_y + y), (origin_x + display_width, origin_y + y)], fill=fill, width=1)

        if include_persistent:
            for measurement in self._get_renderable_persistent_measurements():
                x1, y1, x2, y2 = measurement.coords
                sx, sy = image_to_export_coords(x1, y1)
                ex, ey = image_to_export_coords(x2, y2)
                if measurement.type == "roi":
                    draw.rectangle([(sx, sy), (ex, ey)], outline="#ff9f43", width=2)
                elif measurement.type == "line":
                    draw.line([(sx, sy), (ex, ey)], fill="#54a0ff", width=2)
                label_lines = list(measurement.summary_lines)
                if measurement.type == "roi":
                    role = str(measurement.meta.get("roi_role", "none")).strip().lower() or "none"
                    if role != "none":
                        label_lines = [f"ROI [{role}]"] + label_lines
                draw.text((ex + 6, ey - 6), "\n".join(label_lines), fill="white")

        if include_temporary:
            for measurement in self.temporary_measurements:
                sx, sy = image_to_export_coords(*measurement["start"])
                ex, ey = image_to_export_coords(*measurement["end"])
                if measurement["mode"] == "roi":
                    draw.rectangle([(sx, sy), (ex, ey)], outline="#ffd34d", width=2)
                else:
                    draw.line([(sx, sy), (ex, ey)], fill="#7bdff2", width=2)
                draw.text((ex + 6, ey - 6), "\n".join(measurement.get("summary_lines", [])), fill="white")

        if self.include_metadata_stamp.get():
            stamp = f"frame={self.current_frame}"
            draw.text((10, 10), stamp, fill="white")

    def export_clean_figure(self) -> None:
        base_image = self._build_export_base_image()
        if base_image is None:
            messagebox.showinfo("논문용 그림 저장", "저장할 이미지가 없습니다.")
            return
        export_image = base_image.copy()
        self._draw_measurements_on_pil(
            export_image,
            image_origin=(self._image_bbox[0], self._image_bbox[1]) if self._image_bbox is not None else (0.0, 0.0),
            include_temporary=True,
            include_persistent=True,
            include_grid=True,
        )
        path = filedialog.asksaveasfilename(
            title="논문용 그림 저장",
            defaultextension=".png",
            filetypes=[("PNG files", ".png"), ("JPEG files", ".jpg"), ("All files", ".")],
            initialfile=f"{self._get_export_filename_stub('moduba_clean')}.png",
        )
        if not path:
            return
        try:
            export_image.save(path)
        except Exception as exc:
            messagebox.showerror("논문용 그림 저장 실패", f"그림 저장 중 오류가 발생했습니다.\n\n{exc}")
            return
        messagebox.showinfo("논문용 그림 저장", f"논문용 그림을 저장했습니다.\n\n{path}")

    def export_view_screenshot(self) -> None:
        base_image = self._build_export_base_image()
        if base_image is None or self._image_bbox is None:
            messagebox.showinfo("화면 캡처 저장", "저장할 이미지가 없습니다.")
            return

        canvas_width = max(self.canvas.winfo_width(), 1)
        canvas_height = max(self.canvas.winfo_height(), 1)
        view_left = self.canvas.canvasx(0)
        view_top = self.canvas.canvasy(0)
        screenshot = Image.new("RGB", (canvas_width, canvas_height), "black")

        image_left = self._image_bbox[0] - view_left
        image_top = self._image_bbox[1] - view_top
        screenshot.paste(base_image, (int(round(image_left)), int(round(image_top))))
        self._draw_measurements_on_pil(
            screenshot,
            image_origin=(view_left, view_top),
            include_temporary=True,
            include_persistent=True,
            include_grid=True,
        )

        path = filedialog.asksaveasfilename(
            title="화면 캡처 저장",
            defaultextension=".png",
            filetypes=[("PNG files", ".png"), ("JPEG files", ".jpg"), ("All files", ".")],
            initialfile=f"{self._get_export_filename_stub('moduba_capture')}.png",
        )
        if not path:
            return
        try:
            screenshot.save(path)
        except Exception as exc:
            messagebox.showerror("화면 캡처 저장 실패", f"캡처 저장 중 오류가 발생했습니다.\n\n{exc}")
            return
        messagebox.showinfo("화면 캡처 저장", f"화면 캡처를 저장했습니다.\n\n{path}")

    def _draw_temporary_measurements(self) -> None:
        self.canvas.delete("temp_measurement")
        for measurement in self.temporary_measurements:
            start = self._image_pixel_to_canvas(*measurement["start"])
            end = self._image_pixel_to_canvas(*measurement["end"])
            if start is None or end is None:
                continue
            start_x, start_y = start
            end_x, end_y = end
            if measurement["mode"] == "roi":
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
            label = "\n".join(measurement.get("summary_lines", []))
            self.canvas.create_text(
                end_x + 6,
                end_y - 6,
                text=label,
                fill="white",
                anchor="sw",
                font=("TkDefaultFont", 9, "bold"),
                tags=("temp_measurement",),
            )

    def _build_roi_measurement_summary(self, start: tuple[int, int], end: tuple[int, int]) -> list[str]:
        frame = np.asarray(self.frames[self.current_frame])
        if frame.ndim < 2:
            width_px = abs(end[0] - start[0]) + 1
            height_px = abs(end[1] - start[1]) + 1
            return [f"ROI {width_px} x {height_px}px"]

        x0, x1 = sorted((start[0], end[0]))
        y0, y1 = sorted((start[1], end[1]))
        x1 = min(x1, frame.shape[1] - 1)
        y1 = min(y1, frame.shape[0] - 1)
        x0 = max(x0, 0)
        y0 = max(y0, 0)
        roi = frame[y0 : y1 + 1, x0 : x1 + 1]
        if roi.size == 0:
            return ["ROI: empty"]

        values = roi.astype(np.float32)
        if values.ndim == 3:
            values = np.mean(values, axis=-1)

        width_px = x1 - x0 + 1
        height_px = y1 - y0 + 1
        mean_value = float(np.mean(values))
        std_value = float(np.std(values))
        min_value = float(np.min(values))
        max_value = float(np.max(values))
        return [
            f"ROI {width_px} x {height_px}px",
            f"mean {mean_value:.2f} / std {std_value:.2f}",
            f"min {min_value:.2f} / max {max_value:.2f}",
        ]

    def _build_line_measurement_summary(self, start: tuple[int, int], end: tuple[int, int]) -> list[str]:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        pixel_length = float(np.hypot(dx, dy))
        lines = [f"Line {pixel_length:.2f}px"]

        spacing = self._get_pixel_spacing()
        if spacing is not None:
            row_spacing, col_spacing = spacing
            physical_length_mm = float(np.hypot(dy * row_spacing, dx * col_spacing))
            lines.append(f"{physical_length_mm:.2f} mm")
        return lines

    def _get_pixel_spacing(self) -> tuple[float, float] | None:
        if self.dataset is None:
            return None
        spacing_value = getattr(self.dataset, "PixelSpacing", None)
        if spacing_value is None:
            spacing_value = getattr(self.dataset, "ImagerPixelSpacing", None)
        if spacing_value is None:
            return None
        try:
            row_spacing = float(spacing_value[0])
            col_spacing = float(spacing_value[1])
        except (TypeError, ValueError, IndexError):
            return None
        if row_spacing <= 0 or col_spacing <= 0:
            return None
        return row_spacing, col_spacing

    def clear_temporary_measurements(self) -> None:
        self.temporary_measurements = []
        self._active_temporary_measurement = None
        self.canvas.delete("temp_measurement")

    def clear_measurements(self) -> None:
        self.measurements = {}
        self.measurement_order = []
        self.canvas.delete("persistent_measurement")
        if self.view_mode == "single" and self.frames:
            self._draw_persistent_measurements()

    def _refresh_measurement_render(self) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        self._draw_persistent_measurements()

    @staticmethod
    def _serialize_meta_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return ",".join(str(item) for item in value)
        return str(value)

    def export_measurements_csv(self) -> None:
        ordered_measurements = [
            measurement
            for measurement_id in self.measurement_order
            if (measurement := self.measurements.get(measurement_id)) is not None
        ]
        if not ordered_measurements:
            messagebox.showinfo("측정 CSV 저장", "내보낼 영구 측정값이 없습니다.")
            return

        path = filedialog.asksaveasfilename(
            title="측정 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV files", ".csv"), ("All files", ".*")],
            initialfile="moduba_measurements.csv",
        )
        if not path:
            return

        fieldnames = [
            "measurement_id",
            "measurement_type",
            "frame_index",
            "x1",
            "y1",
            "x2",
            "y2",
            "summary_text",
            "rows",
            "cols",
            "pixel_spacing",
            "imager_pixel_spacing",
            "source_path",
            "sop_instance_uid",
            "series_instance_uid",
        ]

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for measurement in ordered_measurements:
                    geometry_key = measurement.meta.get("geometry_key", {})
                    source_path = measurement.meta.get("source_path", "")
                    sop_instance_uid = measurement.meta.get("sop_instance_uid", "")
                    series_instance_uid = measurement.meta.get("series_instance_uid", "")
                    x1, y1, x2, y2 = measurement.coords
                    writer.writerow(
                        {
                            "measurement_id": measurement.id,
                            "measurement_type": measurement.type,
                            "frame_index": measurement.frame_index,
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                            "summary_text": " | ".join(measurement.summary_lines),
                            "rows": self._serialize_meta_value(geometry_key.get("rows")),
                            "cols": self._serialize_meta_value(geometry_key.get("cols")),
                            "pixel_spacing": self._serialize_meta_value(geometry_key.get("pixel_spacing")),
                            "imager_pixel_spacing": self._serialize_meta_value(geometry_key.get("imager_pixel_spacing")),
                            "source_path": self._serialize_meta_value(source_path),
                            "sop_instance_uid": self._serialize_meta_value(sop_instance_uid),
                            "series_instance_uid": self._serialize_meta_value(series_instance_uid),
                        }
                    )
        except Exception as exc:
            messagebox.showerror("측정 CSV 저장 실패", f"CSV 저장 중 오류가 발생했습니다.\n\n{exc}")
            return

        messagebox.showinfo("측정 CSV 저장 완료", f"측정 CSV를 저장했습니다.\n\n{path}")

    def create_measurement_set(self) -> None:
        if not self.measurements:
            messagebox.showinfo("측정 세트 저장", "저장할 영구 측정값이 없습니다.")
            return
        set_name = simpledialog.askstring("측정 세트 저장", "측정 세트 이름을 입력하세요:", parent=self.root)
        if not set_name:
            return

        geometry_key = self._get_current_geometry_key()
        if self.enable_geometry_filter.get():
            base_measurements = self._get_applicable_measurements()
        else:
            base_measurements = [
                measurement
                for measurement_id in self.measurement_order
                if (measurement := self.measurements.get(measurement_id)) is not None
            ]

        copied_measurements = deepcopy(base_measurements)
        if not copied_measurements:
            messagebox.showinfo("측정 세트 저장", "현재 기하학 조건에 맞는 측정값이 없습니다.")
            return

        measurement_set = MeasurementSet(
            name=set_name.strip() or "Unnamed Set",
            geometry_key=deepcopy(geometry_key),
            measurements=copied_measurements,
        )
        self.measurement_sets[measurement_set.id] = measurement_set
        self.measurement_set_order.append(measurement_set.id)
        messagebox.showinfo("측정 세트 저장", f"측정 세트를 저장했습니다.\n\n이름: {measurement_set.name}")

    def _apply_selected_measurement_set(self) -> None:
        selected_id = self._select_measurement_set_id(title="측정 세트 적용")
        if selected_id is None:
            return
        self.apply_measurement_set(selected_id)

    def _select_measurement_set_id(self, title: str = "측정 세트 선택") -> str | None:
        available_ids = [
            set_id
            for set_id in self.measurement_set_order
            if set_id in self.measurement_sets
        ]
        if not available_ids:
            messagebox.showinfo("측정 세트 적용", "적용 가능한 측정 세트가 없습니다.")
            return None

        lines = []
        for index, set_id in enumerate(available_ids, start=1):
            measurement_set = self.measurement_sets[set_id]
            lines.append(f"{index}. {measurement_set.name} ({len(measurement_set.measurements)}개)")
        selection = simpledialog.askinteger(
            title,
            "적용할 세트 번호를 입력하세요:\n\n" + "\n".join(lines),
            parent=self.root,
            minvalue=1,
            maxvalue=len(available_ids),
        )
        if selection is None:
            return None
        return available_ids[selection - 1]

    def apply_measurement_set(self, set_id: str) -> None:
        measurement_set = self.measurement_sets.get(set_id)
        if measurement_set is None:
            messagebox.showwarning("측정 세트 적용", "선택한 측정 세트를 찾을 수 없습니다.")
            return

        current_key = self._get_current_geometry_key()
        if not self._geometry_matches(current_key, measurement_set.geometry_key):
            messagebox.showwarning("측정 세트 적용", "현재 영상의 기하학 정보가 세트와 일치하지 않습니다.")
            return

        added_count = 0
        for original in measurement_set.measurements:
            copied = deepcopy(original)
            copied.id = uuid4().hex
            self.measurements[copied.id] = copied
            self.measurement_order.append(copied.id)
            added_count += 1

        self._draw_persistent_measurements()
        messagebox.showinfo("측정 세트 적용", f"측정 세트를 적용했습니다.\n\n추가된 측정: {added_count}개")

    def _measurement_to_dict(self, measurement: Measurement) -> dict[str, Any]:
        return {
            "id": measurement.id,
            "type": measurement.type,
            "frame_index": measurement.frame_index,
            "coords": list(measurement.coords),
            "summary_lines": list(measurement.summary_lines),
            "meta": deepcopy(measurement.meta),
        }

    def _measurement_set_to_dict(self, measurement_set: MeasurementSet) -> dict[str, Any]:
        return {
            "id": measurement_set.id,
            "name": measurement_set.name,
            "created_at": measurement_set.created_at,
            "geometry_key": deepcopy(measurement_set.geometry_key),
            "measurements": [self._measurement_to_dict(measurement) for measurement in measurement_set.measurements],
        }

    def _measurement_from_dict(self, data: dict[str, Any]) -> Measurement:
        required_fields = ("id", "type", "frame_index", "coords", "summary_lines")
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"measurement에 필수 키가 없습니다: {field_name}")

        coords = data["coords"]
        if not isinstance(coords, (list, tuple)) or len(coords) != 4:
            raise ValueError("measurement.coords 형식이 올바르지 않습니다.")
        coords_tuple = tuple(int(value) for value in coords)

        summary_lines_raw = data["summary_lines"]
        if not isinstance(summary_lines_raw, list):
            raise ValueError("measurement.summary_lines 형식이 올바르지 않습니다.")
        summary_lines = [str(line) for line in summary_lines_raw]

        meta = data.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}

        return Measurement(
            id=str(data["id"]),
            type=str(data["type"]),
            frame_index=int(data["frame_index"]),
            coords=coords_tuple,  # type: ignore[arg-type]
            summary_lines=summary_lines,
            meta=deepcopy(meta),
        )

    def _measurement_set_from_dict(self, data: dict[str, Any]) -> MeasurementSet:
        required_fields = ("id", "name", "created_at", "measurements")
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"measurement_set에 필수 키가 없습니다: {field_name}")

        measurements_raw = data["measurements"]
        if not isinstance(measurements_raw, list):
            raise ValueError("measurement_set.measurements 형식이 올바르지 않습니다.")
        measurements = [self._measurement_from_dict(item) for item in measurements_raw]

        geometry_key = data.get("geometry_key")
        if geometry_key is not None and not isinstance(geometry_key, dict):
            geometry_key = None

        return MeasurementSet(
            id=str(data["id"]),
            name=str(data["name"]),
            created_at=str(data["created_at"]),
            geometry_key=deepcopy(geometry_key),
            measurements=measurements,
        )

    def export_measurement_set_json(self) -> None:
        if not self.measurement_set_order:
            messagebox.showinfo("세트 JSON 저장", "저장할 측정 세트가 없습니다.")
            return

        set_id = self._select_measurement_set_id(title="JSON으로 저장할 세트 선택")
        if set_id is None:
            return
        measurement_set = self.measurement_sets.get(set_id)
        if measurement_set is None:
            messagebox.showwarning("세트 JSON 저장", "선택한 측정 세트를 찾을 수 없습니다.")
            return

        path = filedialog.asksaveasfilename(
            title="세트 JSON 저장",
            defaultextension=".json",
            filetypes=[("JSON files", ".json"), ("All files", ".*")],
            initialfile="moduba_measurement_set.json",
        )
        if not path:
            return

        payload = self._measurement_set_to_dict(measurement_set)
        try:
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)
        except Exception as exc:
            messagebox.showerror("세트 JSON 저장 실패", f"JSON 저장 중 오류가 발생했습니다.\n\n{exc}")
            return

        messagebox.showinfo("세트 JSON 저장", f"측정 세트를 JSON으로 저장했습니다.\n\n{path}")

    def import_measurement_set_json(self) -> None:
        path = filedialog.askopenfilename(
            title="세트 JSON 불러오기",
            filetypes=[("JSON files", ".json"), ("All files", ".*")],
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)
            if not isinstance(payload, dict):
                raise ValueError("JSON 루트는 객체(dict)여야 합니다.")
            measurement_set = self._measurement_set_from_dict(payload)
        except Exception as exc:
            messagebox.showerror("세트 JSON 불러오기 실패", f"JSON 불러오기 중 오류가 발생했습니다.\n\n{exc}")
            return

        imported_id = measurement_set.id
        if imported_id in self.measurement_sets:
            imported_id = uuid4().hex
            measurement_set.id = imported_id

        self.measurement_sets[imported_id] = measurement_set
        self.measurement_set_order.append(imported_id)
        messagebox.showinfo("세트 JSON 불러오기", f"측정 세트를 불러왔습니다.\n\n이름: {measurement_set.name}")

    def _draw_grid_overlay(self) -> None:
        self.canvas.delete("grid_overlay")
        if not self.show_grid_overlay.get() or self._image_bbox is None:
            return
        left, top, right, bottom = self._image_bbox
        width = right - left
        height = bottom - top
        density = self.grid_density.get()
        if density == "coarse":
            columns = 12
            rows = 12
            major_step = 3
        else:
            columns = 24
            rows = 24
            major_step = 4

        for column in range(1, columns):
            x = left + (width * column / columns)
            is_major = (column % major_step) == 0
            self.canvas.create_line(
                x,
                top,
                x,
                bottom,
                fill="#7ad9ef" if is_major else "#4aaec7",
                width=1 if is_major else 1,
                dash=() if is_major else (2, 3),
                tags=("grid_overlay",),
            )
        for row in range(1, rows):
            y = top + (height * row / rows)
            is_major = (row % major_step) == 0
            self.canvas.create_line(
                left,
                y,
                right,
                y,
                fill="#7ad9ef" if is_major else "#4aaec7",
                width=1 if is_major else 1,
                dash=() if is_major else (2, 3),
                tags=("grid_overlay",),
            )

    def _refresh_single_view_image(self) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        center_ratio = self._capture_view_center_ratio()
        self._show_frame()
        self._restore_view_center_ratio(center_ratio)

    def _refresh_grid_overlay(self) -> None:
        if self.view_mode != "single" or not self.frames:
            return
        self._draw_grid_overlay()

    def _on_grid_density_change(self, *_args: str) -> None:
        self._refresh_grid_overlay()

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
        new_index = self.current_frame + delta
        if not 0 <= new_index < len(self.frames):
            return
        self.current_frame = new_index
        self.clear_temporary_measurements()
        self._show_frame()

    def change_file(self, delta: int) -> None:
        if self.view_mode == "compare":
            return
        if not self.file_paths:
            return
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

    def go_to_file(self, index: int) -> None:
        if self.view_mode == "compare":
            return
        if not 0 <= index < len(self.file_paths):
            return
        if self.view_mode == "multi":
            self.current_file_index = index
            self.image_var.set(f"이미지: {self.current_file_index + 1} / {len(self.file_paths)}")
            self._ensure_multiview_selection_visible()
            self.render_multiview_page()
            return
        self._load_file(index, preserve_view_state=True)

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
        self._draw_temporary_measurements()
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

def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    DicomViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
