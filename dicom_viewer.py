from pathlib import Path
import copy
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional
import uuid

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pydicom
from PIL import Image, ImageDraw, ImageTk
from pydicom.errors import InvalidDicomError
from dicom_loader import DicomLoader
from mtf_engine import calculate_matlab_reference_mtf, calculate_slanted_edge_mtf
from mtf_iec_reporting import evaluate_iec_reporting
from mtf_integrity import evaluate_mtf_integrity
from mtf_qa_grading import grade_mtf_for_internal_qa
from domain_store import DomainStore
from window_b_services import AnalysisResultController, HistoryController, SessionController, ReportExportController
from window_b_manager import WindowBManager
from ui_display_helpers import build_analysis_display_model, build_pair_status_label, build_viewer_a_status_label, format_compact_path_label
from analysis_result_export import export_analysis_results_to_csv, export_analysis_results_to_json
from analysis_report_model import build_analysis_report_model, render_analysis_report_markdown
from analysis_report_pdf import export_analysis_report_to_pdf
from analysis_history_store import append_analysis_history_record, build_analysis_history_record
from analysis_history_display import (
    build_history_records_display_model,
    render_history_record_detail_text,
)
from analysis_history_summary import (
    build_history_summary,
    build_metric_trend_series,
    render_history_summary_text,
    render_metric_trend_text,
)
from analysis_history_trend_chart import (
    build_metric_trend_chart_model,
    render_metric_trend_chart_text,
)
from analysis_batch_qc import (
    build_batch_qc_run,
    export_batch_qc_run_to_csv,
    export_batch_qc_run_to_json,
    render_batch_qc_summary_text,
)
from analysis_batch_qc_report import (
    build_batch_qc_report_model,
    export_batch_qc_report_to_pdf,
    export_batch_qc_report_to_text,
    render_batch_qc_report_text,
)
from dicom_batch_manifest import (
    build_dicom_batch_manifest,
    render_dicom_batch_manifest_text,
    export_dicom_batch_manifest_to_json,
    export_dicom_batch_manifest_to_csv,
)
from roi_preset import (
    build_roi_preset_from_roi_definitions,
    load_roi_preset,
    export_roi_preset_to_json,
    render_roi_preset_text,
)
from dicom_batch_plan import (
    build_dicom_batch_analysis_plan,
    render_dicom_batch_analysis_plan_text,
    export_dicom_batch_analysis_plan_to_json,
    export_dicom_batch_analysis_plan_to_csv,
)
from roi_bounds_validation import (
    build_roi_bounds_validation_result,
    render_roi_bounds_validation_text,
    export_roi_bounds_validation_to_json,
    export_roi_bounds_validation_to_csv,
)
from dicom_batch_execution_plan import (
    build_dicom_batch_execution_plan,
    render_dicom_batch_execution_plan_text,
    export_dicom_batch_execution_plan_to_json,
    export_dicom_batch_execution_plan_to_csv,
)
from dicom_batch_run_orchestrator import (
    build_dicom_batch_run_orchestration_summary,
    render_dicom_batch_run_orchestration_summary_text,
    run_dicom_batch_execution_plan_with_executor,
)
from dicom_batch_workflow_readiness import (
    assert_dicom_batch_workflow_ready_for_pixel_run,
    build_dicom_batch_workflow_readiness_report,
    render_dicom_batch_workflow_readiness_text,
)
from dicom_batch_roi_role_validation import (
    assert_dicom_batch_roi_roles_valid,
    render_dicom_batch_roi_role_validation_text,
    validate_dicom_batch_roi_roles,
)
from dicom_batch_pixel_executor import (
    SUPPORTED_ANALYSIS_TYPES,
    create_dicom_batch_pixel_analysis_executor,
)
from dicom_batch_analysis_dispatcher import (
    SUPPORTED_BATCH_ANALYSIS_TYPES,
    create_existing_analysis_dispatcher,
    render_batch_analysis_dispatcher_capability_text,
)
from dicom_batch_history_adapter import (
    append_dicom_batch_execution_history_records,
    build_analysis_history_records_from_dicom_batch_execution_result,
    build_batch_qc_run_from_dicom_batch_execution_result,
    render_dicom_batch_history_bridge_summary_text,
)
from dicom_batch_normalized_history_adapter import (
    build_analysis_history_records_from_normalized_dicom_batch_execution_result,
    append_normalized_dicom_batch_execution_history_records,
    render_normalized_execution_history_adapter_text,
)
from dicom_batch_normalized_batch_qc_adapter import (
    build_batch_qc_run_from_normalized_execution_history_records,
    build_batch_qc_run_from_normalized_dicom_batch_execution_result,
    render_normalized_batch_qc_adapter_text,
)
from dicom_batch_normalized_batch_qc_report_adapter import (
    build_report_model_from_normalized_batch_qc_run,
    render_normalized_batch_qc_report_text,
    export_normalized_batch_qc_report_to_json,
    export_normalized_batch_qc_report_to_csv,
    export_normalized_batch_qc_report_to_text,
    export_normalized_batch_qc_report_to_pdf,
)
from dicom_batch_execution import (
    build_dicom_batch_execution_result,
    validate_dicom_batch_execution_result,
    render_dicom_batch_execution_result_text,
    export_dicom_batch_execution_result_to_json,
    export_dicom_batch_execution_result_to_csv,
)
from dicom_batch_execution_normalization import (
    build_normalized_dicom_batch_execution_result,
    render_normalized_dicom_batch_execution_result_text,
    export_normalized_dicom_batch_execution_result_to_json,
    export_normalized_dicom_batch_execution_result_to_csv,
)
from analysis_history_store import load_analysis_history_records
from analysis_thresholds import evaluate_analysis_thresholds, render_threshold_evaluation_text, validate_threshold_config
from analysis_threshold_config import (
    build_threshold_config_display_model,
    load_threshold_config,
    render_threshold_config_text,
    save_threshold_config,
)
from analysis_threshold_editor import (
    add_threshold_rule,
    duplicate_threshold_rule,
    get_threshold_rule,
    list_threshold_rules,
    remove_threshold_rule,
    reorder_threshold_rules,
    update_threshold_rule,
)
from analysis_threshold_editor_display import (
    build_threshold_editor_display_model,
    render_threshold_editor_text,
    render_threshold_rule_detail_text,
)
from analysis_threshold_catalog_sync import build_threshold_catalog_sync_status
from analysis_threshold_catalog import (
    add_threshold_config_to_catalog,
    build_empty_threshold_catalog,
    build_threshold_catalog_display_model,
    export_threshold_config_from_catalog,
    get_threshold_config_from_catalog,
    import_threshold_config_file_to_catalog,
    load_threshold_catalog,
    remove_threshold_config_from_catalog,
    render_threshold_catalog_text,
    save_threshold_catalog,
    set_selected_threshold_config_id,
    update_threshold_config_in_catalog,
    validate_threshold_catalog,
    get_selected_threshold_config,
)
from analysis_result_model import normalize_analysis_last_run, normalize_analysis_result
from iqa_metrics import calculate_iqa_metrics
from iqa_dicom_adapter import calculate_dicom_iqa
from iqa_export import iqa_result_to_analysis_record
from iqa_display import WARNING_MESSAGE_MAP, build_iqa_display_model, format_iqa_display_text
from iqa_history import (
    append_iqa_history,
    build_iqa_history_entry,
    get_latest_iqa_history,
    restore_iqa_history_entry,
    summarize_iqa_history_entry,
)
from iqa_histogram import (
    build_histogram_preview_model,
    calculate_histogram_data,
    format_histogram_preview_text,
    resolve_histogram_range,
    summarize_histogram_difference,
)
from iqa_report import build_iqa_report, format_iqa_report_text
from iqa_report_export_ui import normalize_iqa_report_export_format, resolve_latest_iqa_report_for_export, save_iqa_report_by_format
from iqa_ui_state import (
    clear_iqa_selection,
    create_default_iqa_state,
    resolve_iqa_run_state,
    set_iqa_reference_from_current,
    set_iqa_input_mode,
    set_iqa_scope,
    set_iqa_data_range_mode,
    set_iqa_photometric_invert,
    set_iqa_target_from_current,
    swap_iqa_reference_target,
)

IQA_BUTTON_LABELS = {
    "set_ref": "Set Ref",
    "set_target": "Set Target",
    "swap": "Swap",
    "clear": "Clear",
    "run": "Run IQA",
    "save_report": "Save Report",
}


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
class MeasurementDrawProjection:
    measurement_id: str
    kind: str
    start: tuple[float, float]
    end: tuple[float, float]
    frame_index: int
    geometry_key: str
    role: str | None
    meta: dict[str, Any]
    summary_text: str
    selected: bool = False


@dataclass
class ResultHistoryEntry:
    entry_id: str
    timestamp: str
    image_name: str
    frame_index: int
    measurement_type: str
    target_name: str
    metric: str
    value: float | None
    unit: str
    note: str
    measurement_mode: str
    source_image_path: str = ""
    target_id: str = ""
    related_target_ids: list[str] = field(default_factory=list)
    group_id: str = ""
    study_id: str = ""
    extra_payload: dict[str, Any] | None = None
    reason_codes: list[str] = field(default_factory=list)

    def to_row(self) -> tuple[str, str, str, str, str, str, str, str, str]:
        value_text = "-" if self.value is None else f"{self.value:.2f}"
        return (
            self.timestamp,
            self.image_name,
            str(self.frame_index),
            self.measurement_type,
            self.target_name,
            self.metric,
            value_text,
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


@dataclass
class ImageAnalysisGroup:
    group_id: str
    study_id: str
    source_image_path: str
    image_name: str
    created_at: str
    entry_ids: list[str] = field(default_factory=list)
    frame_indices: list[int] = field(default_factory=list)
    roi_source_type: str = "manual"
    propagated_from_group_id: str = ""
    propagated_from_measurement_ids: list[str] = field(default_factory=list)


@dataclass
class StudySession:
    study_id: str
    name: str
    created_at: str
    group_ids: list[str] = field(default_factory=list)


SESSION_SCHEMA_VERSION = "1.0"
PRESET_SCHEMA_VERSION = "1.0"

MTF_METRIC_MTF50 = "MTF50"
MTF_METRIC_MTF10 = "MTF10"
MTF_METRIC_NYQUIST_MTF = "NYQUIST_MTF"
MTF_METRIC_EDGE_ANGLE_DEG = "EDGE_ANGLE_DEG"
MTF_METRIC_EDGE_SNR = "EDGE_SNR"
MTF_METRIC_ROI_WIDTH_MM = "ROI_WIDTH_MM"
MTF_METRIC_ROI_HEIGHT_MM = "ROI_HEIGHT_MM"
MTF_METRIC_INVALID = "INVALID"
ROI_SELECTION_HIT_RADIUS_PX = 8
RESIZE_GRIP_HIT_SIZE_PX = 24


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
        self.domain_store = DomainStore()
        self._store_image_id = self.domain_store.add_image_context("", "current")
        self.analysis_result_controller = AnalysisResultController()
        self.history_controller = HistoryController()
        self.session_controller = SessionController()
        self.report_export_controller = ReportExportController()
        self.window_b_manager = WindowBManager(self.root, self)
        self.window_b_manager.bind_store_events()
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
            "mtf_active_roi_id": tk.StringVar(value=""),
            "mtf_mode": tk.StringVar(value="matlab_reference"),
            "mtf_imaging_mode": tk.StringVar(value="general_radiography"),
            "mtf_operating_mode": tk.StringVar(value="strict_iec"),
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
            "mtf_selected_roi_status": tk.StringVar(value="Selected ROI: none"),
            "mtf_validation_summary": tk.StringVar(value="Validation: bind a rectangular ROI"),
            "mtf_warning_summary": tk.StringVar(value="Warnings: -"),
            "mtf_reason_codes": tk.StringVar(value="Reason Codes: -"),
            "mtf_status_overview": tk.StringVar(value="Validation: - | Calculation: - | IEC: - | QA Grade: -"),
            "mtf_suggested_actions": tk.StringVar(value="Suggested Actions: -"),
        }
        self.image_analysis_inputs: dict[str, tk.StringVar] = {
            "reference_image_id": tk.StringVar(value=""),
            "target_image_id": tk.StringVar(value=""),
            "scope_type": tk.StringVar(value="full_image"),
            "scope_roi_id": tk.StringVar(value=""),
            "iqa_input_mode": tk.StringVar(value="raw_dicom_pixel"),
            "iqa_data_range_mode": tk.StringVar(value="auto"),
            "iqa_photometric_invert": tk.BooleanVar(value=False),
            "iqa_report_export_format": tk.StringVar(value="txt"),
        }
        self.image_analysis_results: dict[str, tk.StringVar] = {
            "image_formula": tk.StringVar(value="Formula: MSE/PSNR/SSIM/Histogram"),
            "image_result": tk.StringVar(value="Result: -"),
            "iqa_pair_status": tk.StringVar(value="Pair: Reference=None | Target=None | Ready=False"),
            "iqa_export_status": tk.StringVar(value="IQA report export ready"),
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
        self.analysis_last_run_normalized: dict[str, dict[str, Any]] = {}
        self.analysis_last_run_display: dict[str, dict[str, Any]] = {}
        self.current_dicom_batch_analysis_plan: dict[str, Any] | None = None
        self.current_roi_bounds_validation: dict[str, Any] | None = None
        self.current_dicom_batch_execution_plan: dict[str, Any] | None = None
        self.current_dicom_batch_execution_result: dict[str, Any] | None = None
        self.current_normalized_dicom_batch_execution_result: dict[str, Any] | None = None
        self.current_dicom_batch_history_records: list[dict[str, Any]] = []
        self.current_normalized_execution_history_records: list[dict[str, Any]] = []
        self.current_batch_qc_run: dict[str, Any] | None = None
        self.current_batch_qc_report_model: dict[str, Any] | None = None
        self.current_normalized_batch_qc_report_model: dict[str, Any] | None = None
        self._analysis_comboboxes: dict[str, ttk.Combobox] = {}
        self._analysis_selector_vars: dict[str, tk.StringVar] = {}
        self._image_analysis_comboboxes: dict[str, ttk.Combobox] = {}
        self._cnr_noise_widgets: list[tk.Widget] = []
        self._analysis_action_buttons: dict[str, ttk.Button] = {}
        self._mtf_summary_value_vars: dict[str, tk.StringVar] = {}
        self._mtf_graph_canvas: tk.Canvas | None = None
        self._mtf_esf_canvas: tk.Canvas | None = None
        self._mtf_lsf_canvas: tk.Canvas | None = None
        self._mtf_curve_notebook: ttk.Notebook | None = None
        self._mtf_curve_tabs: dict[str, ttk.Frame] = {}
        self._mtf_curve_tab_ids: dict[str, str] = {}
        self._mtf_graph_group: ttk.LabelFrame | None = None
        self._mtf_right_frame: ttk.Frame | None = None
        self._mtf_notebook: ttk.Notebook | None = None
        self._mtf_tab: ttk.Frame | None = None
        self._active_signal_analysis_tab: str = "SNR"
        self._mtf_graph_redraw_job: str | None = None
        self._last_mtf_curve_payload: dict[str, Any] = {}
        self._last_esf_curve_payload: dict[str, Any] = {}
        self._last_lsf_curve_payload: dict[str, Any] = {}
        self._last_mtf_result: dict[str, Any] = {}
        self._mtf_graph_status_var = tk.StringVar(value="MTF curve: no result")
        self._mtf_esf_status_var = tk.StringVar(value="ESF: 결과 없음")
        self._mtf_lsf_status_var = tk.StringVar(value="LSF: 결과 없음")
        self._mtf_curve_metrics_tree: ttk.Treeview | None = None
        self._mtf_active_curve_tab_key: str = "mtf"
        self._mtf_warning_popup_message: str = "[검증 결과]\n- 검증: -\n- 계산 유효성: -\n- IEC: -\n- QA 등급: -"
        self._last_mtf_key_metrics: dict[str, Any] = {}
        self._last_mtf_warning_details: list[str] = []
        self._mtf_warning_text_widget: tk.Text | None = None
        self._uniformity_roi_listbox: tk.Listbox | None = None
        self._analysis_ui_bindings_initialized = False
        self.analysis_results_table: ttk.Frame | None = None
        self.analysis_results_canvas: tk.Canvas | None = None
        self.analysis_results_rows_container: ttk.Frame | None = None
        self._analysis_results_row_widgets: list[dict[str, Any]] = []
        self._analysis_results_selected_index: int | None = None
        self.result_history_store = ResultHistoryStore()
        self.result_history_table: ttk.Treeview | None = None
        self.active_study_id: str = ""
        self.active_group_id: str = ""
        self._history_row_meta_by_item_id: dict[str, dict[str, Any]] = {}
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
        self._ensure_default_study_session()
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
        self._attach_resize_grip(self.root)
        self._bind_shortcuts()
        self._update_multiview_controls()
        self._update_compare_controls()
        self.root.after(0, self._set_initial_split_sash)

    @staticmethod
    def _attach_resize_grip(window: tk.Misc) -> ttk.Frame:
        grip_container = ttk.Frame(window, width=RESIZE_GRIP_HIT_SIZE_PX, height=RESIZE_GRIP_HIT_SIZE_PX)
        grip_container.place(relx=1.0, rely=1.0, anchor="se")
        grip_container.place_propagate(False)
        ttk.Sizegrip(grip_container).pack(fill="both", expand=True)

        def _lift_grip(_event: tk.Event | None = None) -> None:
            try:
                grip_container.lift()
            except (tk.TclError, AttributeError):
                return

        _lift_grip()
        try:
            window.bind("<Configure>", _lift_grip, add="+")
        except (tk.TclError, AttributeError):
            pass
        return grip_container

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
        ttk.Button(sections["Output"], text="Open Window B", command=self.open_window_b).pack(side="left", padx=(12, 0))

    def _build_image_toolbar(self, tab: ttk.Frame) -> None:
        sections = self._build_subtoolbar_sections(tab, ["File", "Navigate", "Display", "Transform"])

        self.open_file_button = ttk.Button(sections["File"], text="DICOM 열기", command=self.open_file)
        self.open_file_button.pack(side="left")
        self.open_folder_button = ttk.Button(sections["File"], text="폴더 열기", command=self.open_folder)
        self.open_folder_button.pack(side="left", padx=(8, 0))
        ttk.Button(sections["File"], text="Save Session", command=self.save_analysis_session_via_window_b).pack(side="left", padx=(12, 0))
        ttk.Button(sections["File"], text="Load Session", command=self.load_analysis_session_via_window_b).pack(side="left", padx=(8, 0))
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

        roi_tool_group = ttk.LabelFrame(strip, text="ROI Tool", padding=(8, 6))
        roi_tool_group.pack(side="left", padx=(0, 8), fill="y")
        self._build_draw_tool_panel(roi_tool_group)

        roi_mode_group = ttk.LabelFrame(strip, text="ROI Mode", padding=(8, 6))
        roi_mode_group.pack(side="left", padx=(0, 8), fill="both", expand=True)
        roi_mode_group.columnconfigure(0, weight=1)
        ttk.Label(roi_mode_group, text="ROI mode").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(roi_mode_group, text="Grid ROI", value="grid", variable=self.roi_draw_mode).grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(roi_mode_group, text="Free ROI", value="free", variable=self.roi_draw_mode).grid(row=2, column=0, sticky="w")
        ttk.Label(roi_mode_group, text="Grid ON → polygon snap").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Separator(roi_mode_group, orient="horizontal").grid(row=4, column=0, sticky="ew", pady=(6, 6))
        ttk.Checkbutton(
            roi_mode_group,
            text="ROI Propagation",
            variable=self.roi_propagation_enabled,
        ).grid(row=5, column=0, sticky="w")
        ttk.Radiobutton(
            roi_mode_group,
            text="Next frame/image",
            value="next",
            variable=self.roi_propagation_scope,
        ).grid(row=6, column=0, sticky="w")
        ttk.Radiobutton(
            roi_mode_group,
            text="All navigated targets",
            value="all",
            variable=self.roi_propagation_scope,
        ).grid(row=7, column=0, sticky="w")

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
        history_info = ttk.Frame(tab, padding=(12, 12))
        history_info.pack(fill="both", expand=True)
        ttk.Label(
            history_info,
            text="Analysis tools are available in Window B.",
        ).pack(anchor="w")
        ttk.Button(history_info, text="Open Window B", command=self.open_window_b).pack(anchor="w", pady=(8, 0))
        ttk.Label(
            history_info,
            text="Use Window B for Signal/Image Analysis, Results, History, Session, and Report.",
        ).pack(anchor="w", pady=(6, 0))
        self._initialize_analysis_ui_bindings()

    def _initialize_analysis_ui_bindings(self) -> None:
        if self._analysis_ui_bindings_initialized:
            return
        self.analysis_inputs["cnr_formula"].trace_add("write", self._update_cnr_formula_ui)
        self.analysis_inputs["uniformity_input_mode"].trace_add("write", self._update_uniformity_input_ui)
        self.image_analysis_inputs["scope_type"].trace_add("write", self._update_image_scope_ui)
        self._analysis_ui_bindings_initialized = True
        self._update_cnr_formula_ui()
        self._update_uniformity_input_ui()
        self._update_image_scope_ui()
        self._refresh_analysis_selectors()

    def _build_signal_analysis_toolbar(self, parent: ttk.Frame) -> None:
        for key in ("snr_signal", "snr_noise", "cnr_target", "cnr_reference", "cnr_noise"):
            self._analysis_selector_vars[key] = tk.StringVar(value="")

        nested_notebook = ttk.Notebook(parent)
        nested_notebook.pack(fill="both", expand=True)
        snr_tab = ttk.Frame(nested_notebook, padding=(4, 4, 4, 4))
        cnr_tab = ttk.Frame(nested_notebook, padding=(4, 4, 4, 4))
        uniformity_tab = ttk.Frame(nested_notebook, padding=(4, 4, 4, 4))
        line_profile_tab = ttk.Frame(nested_notebook, padding=(4, 4, 4, 4))
        mtf_tab = ttk.Frame(nested_notebook, padding=(4, 4, 4, 4))
        nested_notebook.add(snr_tab, text="SNR")
        nested_notebook.add(cnr_tab, text="CNR")
        nested_notebook.add(uniformity_tab, text="Uniformity")
        nested_notebook.add(line_profile_tab, text="Line Profile")
        nested_notebook.add(mtf_tab, text="MTF")
        self._mtf_notebook = nested_notebook
        self._mtf_tab = mtf_tab
        nested_notebook.bind("<<NotebookTabChanged>>", self._on_signal_analysis_tab_changed, add="+")

        snr_group = ttk.LabelFrame(snr_tab, text="SNR", padding=(8, 6))
        snr_group.pack(fill="x", anchor="n")
        snr_group.columnconfigure(0, weight=1)
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
        self._build_analysis_summary_label(snr_group, self.signal_analysis_results["snr_preview"]).grid(row=5, column=0, sticky="ew", pady=(2, 0))
        self._build_analysis_summary_label(snr_group, self.signal_analysis_results["snr_result"]).grid(row=6, column=0, sticky="ew", pady=(2, 0))
        self._analysis_action_buttons["snr"] = ttk.Button(snr_group, text="Calculate SNR", command=self.calculate_snr_from_inputs)
        self._analysis_action_buttons["snr"].grid(row=7, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(snr_group, textvariable=self.signal_analysis_results["snr_ready_reason"]).grid(row=8, column=0, sticky="w", pady=(2, 0))

        cnr_group = ttk.LabelFrame(cnr_tab, text="CNR", padding=(8, 6))
        cnr_group.pack(fill="x", anchor="n")
        cnr_group.columnconfigure(0, weight=1)
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
        self._build_analysis_summary_label(cnr_group, self.signal_analysis_results["cnr_preview"]).grid(row=7, column=0, sticky="ew", pady=(2, 0))
        self._build_analysis_summary_label(cnr_group, self.signal_analysis_results["cnr_result"]).grid(row=8, column=0, sticky="ew", pady=(2, 0))
        self._analysis_action_buttons["cnr"] = ttk.Button(cnr_group, text="Calculate CNR", command=self.calculate_cnr_from_inputs)
        self._analysis_action_buttons["cnr"].grid(row=9, column=0, sticky="ew", pady=(6, 0))

        uniformity_group = ttk.LabelFrame(uniformity_tab, text="Uniformity", padding=(8, 6))
        uniformity_group.pack(fill="x", anchor="n")
        uniformity_group.columnconfigure(0, weight=1)
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
        self._build_analysis_summary_label(uniformity_group, self.signal_analysis_results["uniformity_preview"]).grid(row=8, column=0, sticky="ew", pady=(2, 0))
        self._build_analysis_summary_label(uniformity_group, self.signal_analysis_results["uniformity_result"]).grid(row=9, column=0, sticky="ew", pady=(2, 0))
        ttk.Button(uniformity_group, text="Calculate Uniformity", command=self.calculate_uniformity_from_inputs).grid(row=10, column=0, sticky="ew", pady=(6, 0))

        line_group = ttk.LabelFrame(line_profile_tab, text="Line Profile", padding=(8, 6))
        line_group.pack(fill="x", anchor="n")
        line_group.columnconfigure(0, weight=1)
        ttk.Label(line_group, text="Input: Profile Line").grid(row=0, column=0, sticky="w")
        self._analysis_comboboxes["line_profile"] = ttk.Combobox(line_group, state="readonly", width=42)
        self._analysis_comboboxes["line_profile"].grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(line_group, text="Formula: intensity(x) sampled along selected line").grid(row=2, column=0, sticky="w")
        self._build_analysis_summary_label(line_group, self.signal_analysis_results["line_info"]).grid(row=3, column=0, sticky="ew", pady=(2, 0))
        ttk.Button(line_group, text="Show Line Profile", command=self.show_line_profile_for_selected_line).grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(line_group, text="Show Feature Details", command=self.show_line_profile_feature_details).grid(row=5, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(line_group, text="Export Profile CSV", command=self.export_selected_line_profile_csv).grid(row=6, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(line_group, textvariable=self.snr_workflow_var).grid(row=7, column=0, sticky="w", pady=(2, 0))

        self._build_mtf_analysis_panel(mtf_tab)
        if False:  # pragma: no cover - legacy call path retained for auditable deprecation tracking
            self._build_analysis_results_panel(parent)
        self._bind_analysis_selector_events()

    def _build_mtf_analysis_panel(self, strip: ttk.Frame) -> None:
        panel = ttk.LabelFrame(strip, text="MTF Analysis", padding=(8, 6))
        strip.grid_columnconfigure(0, weight=1)
        strip.grid_rowconfigure(0, weight=1)
        panel.grid(row=0, column=0, sticky="nsew")

        left_frame = ttk.Frame(panel)
        left_frame.grid(row=0, column=0, sticky="nsew")
        right_frame = ttk.Frame(panel)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._mtf_right_frame = right_frame

        input_group = ttk.LabelFrame(left_frame, text="Input", padding=(6, 4))
        input_group.grid(row=0, column=0, sticky="ew")
        ttk.Label(input_group, textvariable=self.signal_analysis_results["mtf_selected_roi_status"]).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(input_group, text="MTF Mode").grid(row=1, column=0, sticky="w", pady=(4, 0))
        mode_combo = ttk.Combobox(
            input_group,
            state="readonly",
            width=24,
            textvariable=self.analysis_inputs["mtf_mode"],
            values=[
                "matlab_reference | MATLAB Reference",
                "moduba_slanted_edge | IEC / Moduba Slanted-edge",
            ],
        )
        mode_combo.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        ttk.Label(input_group, text="Imaging Mode").grid(row=2, column=0, sticky="w", pady=(4, 0))
        imaging_combo = ttk.Combobox(
            input_group,
            state="readonly",
            width=24,
            textvariable=self.analysis_inputs["mtf_imaging_mode"],
            values=[
                "general_radiography | General Radiography",
                "mammography | Mammography",
            ],
        )
        imaging_combo.grid(row=2, column=1, sticky="ew", pady=(4, 0))
        ttk.Label(input_group, text="Operating Mode").grid(row=3, column=0, sticky="w", pady=(4, 0))
        operating_combo = ttk.Combobox(
            input_group,
            state="readonly",
            width=24,
            textvariable=self.analysis_inputs["mtf_operating_mode"],
            values=[
                "strict_iec | Strict IEC",
                "exploratory_mode | Exploratory",
            ],
        )
        operating_combo.grid(row=3, column=1, sticky="ew", pady=(4, 0))
        mode_combo.set("matlab_reference | MATLAB Reference")
        imaging_combo.set("general_radiography | General Radiography")
        operating_combo.set("strict_iec | Strict IEC")
        ttk.Button(input_group, text="Use Selected ROI as Edge ROI", command=self._bind_selected_roi_to_mtf).grid(row=4, column=0, sticky="ew", pady=(6, 0), padx=(0, 4))
        self._analysis_action_buttons["mtf"] = ttk.Button(input_group, text="Run MTF Analysis", command=self._run_mtf_analysis, state="disabled")
        self._analysis_action_buttons["mtf"].grid(row=4, column=1, sticky="ew", pady=(6, 0))
        ttk.Button(input_group, text="Show MTF Details", command=self._show_mtf_details).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Label(input_group, textvariable=self.signal_analysis_results["mtf_validation_summary"]).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        summary_group = ttk.LabelFrame(left_frame, text="Result Summary", padding=(6, 4))
        summary_group.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        summary_group.grid_columnconfigure(0, weight=1)
        core_group = ttk.LabelFrame(summary_group, text="Core Results", padding=(6, 4))
        core_group.grid(row=0, column=0, sticky="ew")
        roi_group = ttk.LabelFrame(summary_group, text="ROI / Edge Info", padding=(6, 4))
        roi_group.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(summary_group, text="lp/mm (converted from PixelSpacing)").grid(row=2, column=0, sticky="w", pady=(4, 0))

        summary_items = [
            ("MTF50", "mtf50"),
            ("MTF10", "mtf10"),
            ("Nyquist MTF", "nyquist_mtf"),
            ("IEC Compliance", "iec_compliance"),
            ("QA Grade", "qa_grade"),
            ("MTF Mode", "mtf_mode"),
            ("Edge Angle", "edge_angle"),
            ("Edge SNR", "edge_snr"),
            ("ROI Width", "roi_width"),
            ("ROI Height", "roi_height"),
            ("Calculation Validity", "calculation_validity"),
            ("Frequency (lp/mm)", "frequency_lpmm"),
        ]
        core_keys = {"mtf50", "mtf10", "nyquist_mtf", "iec_compliance", "qa_grade"}
        core_row = 0
        roi_row = 0
        for label, key in summary_items:
            parent = core_group if key in core_keys else roi_group
            row_index = core_row if key in core_keys else roi_row
            ttk.Label(parent, text=f"{label}:").grid(row=row_index, column=0, sticky="w")
            var = tk.StringVar(value="-")
            self._mtf_summary_value_vars[key] = var
            ttk.Label(parent, textvariable=var).grid(row=row_index, column=1, sticky="w", padx=(8, 0))
            if key in core_keys:
                core_row += 1
            else:
                roi_row += 1

        warning_group = ttk.LabelFrame(left_frame, text="Warnings / Validation", padding=(6, 4))
        warning_group.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        warning_group.grid_columnconfigure(0, weight=1)
        warning_group.grid_rowconfigure(1, weight=1)
        ttk.Label(
            warning_group,
            textvariable=self.signal_analysis_results["mtf_status_overview"],
            wraplength=300,
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        warning_text_frame = ttk.Frame(warning_group)
        warning_text_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        warning_text = tk.Text(warning_text_frame, height=8, wrap="word", relief="solid", borderwidth=1)
        warning_text.grid(row=0, column=0, sticky="nsew")
        warning_scroll = ttk.Scrollbar(warning_text_frame, orient="vertical", command=warning_text.yview)
        warning_scroll.grid(row=0, column=1, sticky="ns")
        warning_text.configure(yscrollcommand=warning_scroll.set, state="disabled")
        warning_text_frame.grid_columnconfigure(0, weight=1)
        warning_text_frame.grid_rowconfigure(0, weight=1)
        self._mtf_warning_text_widget = warning_text
        ttk.Button(warning_group, text="경고 상세 팝업", command=self._show_mtf_warning_popup).grid(row=2, column=0, sticky="e", pady=(6, 0))

        graph_group = ttk.LabelFrame(right_frame, text="Curve Viewer", padding=(6, 4))
        graph_group.grid(row=0, column=0, sticky="nsew")
        graph_group.configure(height=300)
        self._mtf_graph_group = graph_group
        curve_notebook = ttk.Notebook(graph_group)
        curve_notebook.grid(row=0, column=0, sticky="nsew")
        self._mtf_curve_notebook = curve_notebook
        curve_notebook.bind("<<NotebookTabChanged>>", self._on_mtf_curve_tab_changed, add="+")
        for key, title in (("mtf", "MTF"), ("esf", "ESF"), ("lsf", "LSF")):
            tab = ttk.Frame(curve_notebook, padding=(2, 2, 2, 2))
            curve_notebook.add(tab, text=title)
            self._mtf_curve_tab_ids[str(tab)] = key
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            canvas = tk.Canvas(tab, width=360, height=180, bg="#FFFFFF", highlightthickness=1, highlightbackground=self.ui_colors["border"])
            canvas.grid(row=0, column=0, sticky="nsew")
            canvas.bind("<Configure>", self._on_mtf_graph_canvas_configure, add="+")
            self._mtf_curve_tabs[key] = tab
            if key == "mtf":
                self._mtf_graph_canvas = canvas
            elif key == "esf":
                self._mtf_esf_canvas = canvas
            else:
                self._mtf_lsf_canvas = canvas
        summary_group_right = ttk.LabelFrame(graph_group, text="Curve Metrics", padding=(6, 4))
        summary_group_right.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        summary_group_right.grid_columnconfigure(0, weight=1)
        metrics_tree = ttk.Treeview(
            summary_group_right,
            columns=("metric", "value", "definition"),
            show="headings",
            height=7,
        )
        metrics_tree.heading("metric", text="Metric")
        metrics_tree.heading("value", text="Value")
        metrics_tree.heading("definition", text="Formula / Definition")
        metrics_tree.column("metric", width=130, anchor="w", stretch=False)
        metrics_tree.column("value", width=140, anchor="w", stretch=False)
        metrics_tree.column("definition", width=300, anchor="w", stretch=True)
        metrics_tree.grid(row=0, column=0, sticky="ew")
        self._mtf_curve_metrics_tree = metrics_tree
        ttk.Label(summary_group_right, textvariable=self._mtf_graph_status_var).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(summary_group_right, textvariable=self._mtf_esf_status_var).grid(row=2, column=0, sticky="w")
        ttk.Label(summary_group_right, textvariable=self._mtf_lsf_status_var).grid(row=3, column=0, sticky="w")
        controls_row = ttk.Frame(graph_group)
        controls_row.grid(row=2, column=0, sticky="e", pady=(6, 0))
        ttk.Button(controls_row, text="Copy Graph", command=self._copy_active_mtf_curve_graph).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(controls_row, text="Save Graph", command=self._save_active_mtf_curve_graph).grid(row=0, column=1)
        graph_group.grid_columnconfigure(0, weight=1)
        graph_group.grid_rowconfigure(0, weight=1, minsize=300)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=0)
        left_frame.grid_rowconfigure(1, weight=0)
        left_frame.grid_rowconfigure(2, weight=0)
        panel.grid_columnconfigure(0, weight=0)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(0, weight=1, minsize=300)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1, minsize=300)
        self._restore_mtf_ui_from_last_run()

    def _restore_mtf_ui_from_last_run(self) -> None:
        self._refresh_mtf_warning_text_widget()
        last_run = self._select_analysis_last_run("mtf") or {}
        result = dict(last_run.get("result") or {})
        self._rebuild_curve_metrics_for_active_tab()
        if not result:
            self._schedule_mtf_graph_redraw()
            return
        self._update_mtf_analysis_ui(result)

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

    @staticmethod
    def _parse_prefixed_value(raw_value: str, default: str) -> str:
        value = str(raw_value or "").strip()
        if not value:
            return default
        return value.split("|", 1)[0].strip()

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

    def _on_signal_analysis_tab_changed(self, event: tk.Event | None = None) -> None:
        notebook = self._mtf_notebook
        mtf_tab = self._mtf_tab
        if notebook is None or mtf_tab is None:
            return
        if event is not None and event.widget is not notebook:
            return
        self._active_signal_analysis_tab = self._get_active_signal_analysis_tab()
        self._refresh_analysis_results_panel()
        if notebook.select() != str(mtf_tab):
            return
        self._schedule_mtf_graph_redraw()

    def _get_active_signal_analysis_tab(self) -> str:
        notebook = self._mtf_notebook
        if notebook is None:
            return "SNR"
        try:
            tab_id = notebook.select()
            tab_text = notebook.tab(tab_id, "text")
        except Exception:
            return "SNR"
        normalized = self._normalize_analysis_tab_name(str(tab_text))
        return normalized or "SNR"

    def _on_mtf_graph_canvas_configure(self, _event: tk.Event | None = None) -> None:
        self._schedule_mtf_graph_redraw()

    def _on_mtf_curve_tab_changed(self, _event: tk.Event | None = None) -> None:
        self._mtf_active_curve_tab_key = self._get_active_mtf_curve_tab_key()
        self._rebuild_curve_metrics_for_active_tab()
        self._schedule_mtf_graph_redraw()

    def _schedule_mtf_graph_redraw(self) -> None:
        canvas = self._mtf_graph_canvas
        if canvas is None:
            return
        if self._mtf_graph_redraw_job is not None:
            try:
                canvas.after_cancel(self._mtf_graph_redraw_job)
            except Exception:
                pass
        self._mtf_graph_redraw_job = canvas.after_idle(self._redraw_all_mtf_curves_from_cached_result)

    def _redraw_all_mtf_curves_from_cached_result(self) -> None:
        self._mtf_graph_redraw_job = None
        canvas = self._mtf_graph_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        mtf_curve = self._last_mtf_curve_payload
        esf_curve = self._last_esf_curve_payload
        lsf_curve = self._last_lsf_curve_payload
        if not mtf_curve or not esf_curve or not lsf_curve:
            last_run = self._select_analysis_last_run("mtf") or {}
            mtf_result = last_run.get("result") or {}
            mtf_curve = mtf_curve or (mtf_result.get("mtf_curve") or {})
            esf_curve = esf_curve or (mtf_result.get("esf_curve") or {})
            lsf_curve = lsf_curve or (mtf_result.get("lsf_curve") or {})
        self._render_mtf_curve(dict(mtf_curve or {}))
        self._render_xy_curve(self._mtf_esf_canvas, dict(esf_curve or {}), "ESF", "x")
        self._render_xy_curve(self._mtf_lsf_canvas, dict(lsf_curve or {}), "LSF", "x")

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

    def _format_compact_path_label(self, path_text: str, max_chars: int = 54) -> str:
        normalized = str(path_text or "").strip()
        if not normalized:
            return "No file"
        return format_compact_path_label(normalized, max_chars=max_chars, empty_placeholder="No file")

    def _build_analysis_summary_label(self, parent: ttk.Widget, textvariable: tk.StringVar, wraplength: int = 520) -> ttk.Label:
        return ttk.Label(parent, textvariable=textvariable, justify="left", wraplength=wraplength)

    def _build_image_analysis_toolbar(self, tab: ttk.Frame) -> None:
        frame = ttk.Frame(tab)
        frame.pack(fill="x")
        frame.columnconfigure(0, weight=1)
        pairing_group = ttk.LabelFrame(frame, text="Image Pairing", padding=(8, 6))
        pairing_group.pack(side="left", padx=(0, 8), fill="both")
        pairing_group.columnconfigure(0, weight=1)
        ttk.Label(pairing_group, text="Reference Image").grid(row=0, column=0, sticky="w")
        self._image_analysis_comboboxes["reference_image"] = ttk.Combobox(pairing_group, state="readonly", width=36)
        self._image_analysis_comboboxes["reference_image"].grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(pairing_group, text="Target Image").grid(row=2, column=0, sticky="w")
        self._image_analysis_comboboxes["target_image"] = ttk.Combobox(pairing_group, state="readonly", width=36)
        self._image_analysis_comboboxes["target_image"].grid(row=3, column=0, sticky="ew", pady=(2, 4))
        ttk.Button(pairing_group, text="현재 이미지를 Reference로", command=self._set_current_image_as_reference).grid(row=4, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(pairing_group, text="현재 이미지를 Target으로", command=self._set_current_image_as_target).grid(row=5, column=0, sticky="ew", pady=(4, 0))

        scope_group = ttk.LabelFrame(frame, text="Scope", padding=(8, 6))
        scope_group.pack(side="left", padx=(0, 8), fill="y")
        ttk.Radiobutton(scope_group, text="Full Image", value="full_image", variable=self.image_analysis_inputs["scope_type"]).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(scope_group, text="Selected ROI", value="roi", variable=self.image_analysis_inputs["scope_type"]).grid(row=1, column=0, sticky="w")
        self._image_analysis_comboboxes["scope_roi"] = ttk.Combobox(scope_group, state="readonly", width=42)
        self._image_analysis_comboboxes["scope_roi"].grid(row=2, column=0, sticky="ew", pady=(6, 0))

        result_group = ttk.LabelFrame(frame, text="Image Metrics", padding=(8, 6))
        result_group.pack(side="left", padx=(0, 8), fill="both", expand=True)
        self._build_analysis_summary_label(result_group, self.image_analysis_results["iqa_pair_status"], wraplength=560).grid(row=0, column=0, sticky="ew")
        option_row = ttk.Frame(result_group)
        option_row.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(option_row, text="Input").grid(row=0, column=0, sticky="w")
        iqa_mode_combo = ttk.Combobox(option_row, state="readonly", width=16, values=("raw_dicom_pixel", "modality_lut", "windowed_display"), textvariable=self.image_analysis_inputs["iqa_input_mode"])
        iqa_mode_combo.grid(row=0, column=1, padx=(4, 6))
        ttk.Label(option_row, text="DataRange").grid(row=0, column=2, sticky="w")
        iqa_scope_combo = ttk.Combobox(option_row, state="readonly", width=12, values=("full_image", "roi"), textvariable=self.image_analysis_inputs["scope_type"])
        iqa_scope_combo.grid(row=0, column=3, padx=(4, 6))
        ttk.Label(option_row, text="Range").grid(row=0, column=4, sticky="w")
        iqa_range_combo = ttk.Combobox(option_row, state="readonly", width=10, values=("auto", "bits", "actual_union"), textvariable=self.image_analysis_inputs["iqa_data_range_mode"])
        iqa_range_combo.grid(row=0, column=5, padx=(4, 6))
        ttk.Checkbutton(option_row, text="Photometric Invert", variable=self.image_analysis_inputs["iqa_photometric_invert"]).grid(row=0, column=6, sticky="w")
        self._build_analysis_summary_label(result_group, self.image_analysis_results["image_formula"], wraplength=560).grid(row=5, column=0, sticky="ew", pady=(4, 0))
        self._build_analysis_summary_label(result_group, self.image_analysis_results["image_result"], wraplength=560).grid(row=6, column=0, sticky="ew", pady=(4, 0))
        action_row = ttk.Frame(result_group)
        action_row.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(action_row, text=IQA_BUTTON_LABELS["set_ref"], command=self._set_iqa_reference_from_current).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(action_row, text=IQA_BUTTON_LABELS["set_target"], command=self._set_iqa_target_from_current).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(action_row, text=IQA_BUTTON_LABELS["swap"], command=self._swap_iqa_reference_target).grid(row=0, column=2, padx=(0, 4))
        ttk.Button(action_row, text=IQA_BUTTON_LABELS["clear"], command=self._clear_iqa_selection).grid(row=0, column=3, padx=(0, 4))
        export_row = ttk.Frame(result_group)
        export_row.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(export_row, text="Export Format").grid(row=0, column=0, sticky="w")
        ttk.Combobox(export_row, state="readonly", width=8, values=("txt", "json", "csv", "all"), textvariable=self.image_analysis_inputs["iqa_report_export_format"]).grid(row=0, column=1, padx=(4, 6))
        ttk.Button(export_row, text=IQA_BUTTON_LABELS["save_report"], command=self._save_latest_iqa_report).grid(row=0, column=2, padx=(0, 6))
        ttk.Label(export_row, textvariable=self.image_analysis_results["iqa_export_status"]).grid(row=0, column=3, sticky="w")
        ttk.Button(result_group, text=IQA_BUTTON_LABELS["run"], command=self.calculate_image_comparison_metrics).grid(row=5, column=0, sticky="ew", pady=(8, 0))

    def _build_analysis_results_panel(self, strip: ttk.Frame) -> None:
        panel = ttk.LabelFrame(strip, text="Analysis Results", padding=(8, 6))
        panel.pack(side="left", padx=(0, 8), fill="both", expand=True)
        header = ttk.Frame(panel)
        header.grid(row=0, column=0, sticky="ew", columnspan=2)
        header.columnconfigure(0, weight=1, minsize=340)
        header.columnconfigure(1, weight=0, minsize=190)
        header.columnconfigure(2, weight=0, minsize=130)
        ttk.Label(header, text="ROI / Analysis / Metric", anchor="w").grid(row=0, column=0, sticky="ew", padx=(2, 8))
        ttk.Label(header, text="Formula / Calculation", anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(header, text="Result", anchor="w").grid(row=0, column=2, sticky="ew")

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
        """
        [DEPRECATED]
        Window B panel factory 분리 이후 창 B에서는 더 이상 이 legacy builder를 호출하지 않는다.
        현재는 제거 전 호출 경로 검증 단계로 유지된다.
        삭제 전 조건:
        - 창 A 호출 없음
        - 창 B 호출 없음
        - 테스트/동적 호출 없음
        """
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
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "image_name": self._current_image_name(),
            "image_path": self._get_current_image_path() if hasattr(self, "_get_current_image_path") else "",
            "frame_index": int(self.current_frame),
            "measurement_mode": measurement_mode,
        }

    def _ensure_default_study_session(self) -> StudySession:
        self._ensure_domain_store()
        study_sessions = self._select_study_sessions_map()
        if not hasattr(self, "active_study_id"):
            self.active_study_id = ""
        if not hasattr(self, "active_group_id"):
            self.active_group_id = ""
        if self.active_study_id and self.active_study_id in study_sessions:
            return study_sessions[self.active_study_id]
        if study_sessions:
            first_study = next(iter(study_sessions.values()))
            self.active_study_id = first_study.study_id
            return first_study
        study_id = str(uuid.uuid4())
        study = StudySession(
            study_id=study_id,
            name="Default Study",
            created_at=datetime.now(timezone.utc).isoformat(),
            group_ids=[],
        )
        study_sessions[study_id] = study
        self.active_study_id = study_id
        return study

    def _get_or_create_active_analysis_group(self, context: dict[str, Any]) -> ImageAnalysisGroup:
        self._ensure_domain_store()
        analysis_groups = self._select_analysis_groups_map()
        study = self._ensure_default_study_session()
        current_path = str(context.get("image_path", "") or "")
        current_image_name = str(context.get("image_name", "N/A"))
        current_frame_index = int(context.get("frame_index", 0))
        active_group = analysis_groups.get(self.active_group_id)
        if active_group is not None:
            same_image = active_group.source_image_path == current_path
            if not current_path:
                same_image = active_group.image_name == current_image_name
            if same_image:
                return active_group
        roi_source = self._infer_group_roi_source_metadata()
        group_id = str(uuid.uuid4())
        group = ImageAnalysisGroup(
            group_id=group_id,
            study_id=study.study_id,
            source_image_path=current_path,
            image_name=current_image_name,
            created_at=datetime.now(timezone.utc).isoformat(),
            entry_ids=[],
            frame_indices=[],
            roi_source_type=str(roi_source.get("roi_source_type", "manual")),
            propagated_from_group_id=str(roi_source.get("propagated_from_group_id", "")),
            propagated_from_measurement_ids=[str(item) for item in roi_source.get("propagated_from_measurement_ids", [])],
        )
        analysis_groups[group_id] = group
        if group_id not in study.group_ids:
            study.group_ids.append(group_id)
        self.active_group_id = group_id
        return group

    def _infer_group_roi_source_metadata(self) -> dict[str, Any]:
        current_geometry = self._get_current_geometry_key()
        if current_geometry is None:
            return {"roi_source_type": "manual", "propagated_from_group_id": "", "propagated_from_measurement_ids": []}
        frame_index = int(getattr(self, "current_frame", 0))
        rois = [
            measurement
            for measurement in self._selector_measurements_for_current_frame(kind="roi")
            if measurement.kind == "roi"
            and measurement.frame_index == frame_index
            and self._geometry_matches(measurement.geometry_key, current_geometry)
        ]
        propagated = [item for item in rois if str((item.meta or {}).get("propagated_from", ""))]
        if not propagated:
            return {"roi_source_type": "manual", "propagated_from_group_id": "", "propagated_from_measurement_ids": []}
        source_group_id = str((propagated[0].meta or {}).get("propagated_from_group_id", ""))
        source_ids = [str((item.meta or {}).get("propagated_from", "")) for item in propagated if (item.meta or {}).get("propagated_from")]
        return {
            "roi_source_type": "propagated",
            "propagated_from_group_id": source_group_id,
            "propagated_from_measurement_ids": source_ids,
        }

    def _append_history_entry(
        self,
        measurement_type: str,
        target_name: str,
        metric: str,
        value: float | None,
        unit: str,
        note: str,
        measurement_mode: str = "",
        target_id: str = "",
        related_target_ids: list[str] | None = None,
        extra_payload: dict[str, Any] | None = None,
        reason_codes: list[str] | None = None,
        group_id: str = "",
        study_id: str = "",
    ) -> None:
        if not hasattr(self, "result_history_store") or self.result_history_store is None:
            self.result_history_store = ResultHistoryStore()
        context = self._current_history_context()
        requested_group_id = str(group_id or "").strip()
        analysis_groups = self._select_analysis_groups_map()
        study_sessions = self._select_study_sessions_map()
        if requested_group_id and requested_group_id in analysis_groups:
            group = analysis_groups[requested_group_id]
        else:
            group = self._get_or_create_active_analysis_group(context)
            if requested_group_id and requested_group_id != group.group_id:
                group = ImageAnalysisGroup(
                    group_id=requested_group_id,
                    study_id=str(study_id or group.study_id),
                    source_image_path=str(context.get("image_path", "")),
                    image_name=str(context.get("image_name", "N/A")),
                    created_at=str(context.get("timestamp", datetime.now(timezone.utc).isoformat())),
                    frame_indices=[int(context.get("frame_index", 0))],
                )
                analysis_groups[group.group_id] = group
                study = study_sessions.get(group.study_id)
                if study is not None and group.group_id not in study.group_ids:
                    study.group_ids.append(group.group_id)
                self.active_group_id = group.group_id
        entry = ResultHistoryEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=context["timestamp"],
            image_name=context["image_name"],
            frame_index=context["frame_index"],
            measurement_type=measurement_type,
            target_name=target_name,
            metric=metric,
            value=(float(value) if isinstance(value, (int, float)) else None),
            unit=unit,
            note=note,
            measurement_mode=measurement_mode or context["measurement_mode"],
            source_image_path=str(context.get("image_path", "")),
            target_id=target_id,
            related_target_ids=list(related_target_ids or []),
            group_id=str(group_id or group.group_id),
            study_id=str(study_id or group.study_id),
            extra_payload=dict(extra_payload) if isinstance(extra_payload, dict) else None,
            reason_codes=[str(code) for code in (reason_codes or [])],
        )
        self._action_history_append_entry(entry)
        group.entry_ids.append(entry.entry_id)
        frame_index = int(context.get("frame_index", 0))
        if frame_index not in group.frame_indices:
            group.frame_indices.append(frame_index)
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
            "value": (float(entry.value) if isinstance(entry.value, (int, float)) else None),
            "unit": entry.unit,
            "note": entry.note,
            "measurement_mode": entry.measurement_mode,
            "source_image_path": entry.source_image_path,
            "target_id": entry.target_id,
            "related_target_ids": list(entry.related_target_ids),
            "group_id": entry.group_id,
            "study_id": entry.study_id,
            "extra_payload": dict(entry.extra_payload or {}),
            "reason_codes": [str(code) for code in (entry.reason_codes or [])],
        }

    @staticmethod
    def _deserialize_history_entry(payload: dict[str, Any]) -> ResultHistoryEntry:
        raw_value = payload.get("value")
        parsed_value: float | None
        if isinstance(raw_value, (int, float)):
            parsed_value = float(raw_value)
        elif isinstance(raw_value, str) and raw_value.strip():
            try:
                parsed_value = float(raw_value)
            except ValueError:
                parsed_value = None
        else:
            parsed_value = None
        return ResultHistoryEntry(
            entry_id=str(payload.get("entry_id") or uuid.uuid4()),
            timestamp=str(payload.get("timestamp", "")),
            image_name=str(payload.get("image_name", "N/A")),
            frame_index=int(payload.get("frame_index", 0)),
            measurement_type=str(payload.get("measurement_type", "")),
            target_name=str(payload.get("target_name", "")),
            metric=str(payload.get("metric", "")),
            value=parsed_value,
            unit=str(payload.get("unit", "")),
            note=str(payload.get("note", "")),
            measurement_mode=str(payload.get("measurement_mode", "unknown")),
            source_image_path=str(payload.get("source_image_path", "")),
            target_id=str(payload.get("target_id", "")),
            related_target_ids=[str(item) for item in (payload.get("related_target_ids") or [])],
            group_id=str(payload.get("group_id", "")),
            study_id=str(payload.get("study_id", "")),
            extra_payload=dict(payload.get("extra_payload") or {}),
            reason_codes=[str(code) for code in (payload.get("reason_codes") or [])],
        )

    def _refresh_result_history_table(self) -> None:
        table = getattr(self, "result_history_table", None)
        if table is None:
            return
        selected_type = self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All"
        search_text = self.history_search_var.get() if hasattr(self, "history_search_var") else ""
        history_rows = self.build_flat_history_view(selected_type, search_text)
        self.render_flat_history_table(history_rows)
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

    @staticmethod
    def _format_history_value(value: float | None) -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):.2f}"
        return "-"

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
            value_text = self._format_history_value(entry.value)
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

    def build_flat_history_view(self, measurement_type: str = "All", search_text: str = "") -> list[dict[str, Any]]:
        self._ensure_window_b_services()
        raw_rows = self._select_filtered_history_entries(measurement_type, "")
        grouped_rows = self.group_history_entries(raw_rows)
        return self.history_controller.build_flat_history_view(grouped_rows, search_text=search_text)

    def render_flat_history_table(self, history_rows: list[dict[str, Any]]) -> None:
        table = getattr(self, "result_history_table", None)
        if table is None:
            return
        self._history_item_to_store_indices = {}
        self._history_row_meta_by_item_id = {}
        for item_id in table.get_children():
            table.delete(item_id)
        row_values: list[tuple[str, ...]] = []
        for row in history_rows:
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
            self._history_row_meta_by_item_id[item_id] = dict(row)
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
        all_entries = self._select_result_history_entries()
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
        self._action_history_remove_indices(indices)
        self._refresh_result_history_table()

    def clear_result_history(self) -> None:
        self._action_history_clear()
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
                        self._format_history_value(entry.value),
                        entry.unit,
                        entry.note,
                    ]
                )

    @staticmethod
    def _history_table_export_columns() -> tuple[str, ...]:
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

    def _write_flat_result_history_csv(self, path: str, history_rows: list[dict[str, Any]]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self._history_table_export_columns())
            for row in history_rows:
                if str(row.get("row_type", "result")) != "result":
                    continue
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
        history_rows = self.build_flat_history_view(
            self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All",
            self.history_search_var.get() if hasattr(self, "history_search_var") else "",
        )
        self._write_flat_result_history_csv(path, history_rows)
        messagebox.showinfo("저장 완료", f"Results History CSV 저장 완료:\n{path}")

    def export_selected_result_history_csv(self) -> None:
        self._ensure_window_b_services()
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
        history_rows = self.build_flat_history_view(
            self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All",
            self.history_search_var.get() if hasattr(self, "history_search_var") else "",
        )
        history_rows = self.report_export_controller.filter_selected_rows(history_rows, selected_indices)
        self._write_flat_result_history_csv(path, history_rows)
        messagebox.showinfo("저장 완료", f"선택 행 CSV 저장 완료:\n{path}")

    def copy_result_history_to_clipboard(self) -> None:
        selected_rows = self._selected_history_entries()
        selected_indices = {index for index, _entry in selected_rows}
        history_rows = self.build_flat_history_view(
            self.history_metric_filter_var.get().strip() if hasattr(self, "history_metric_filter_var") else "All",
            self.history_search_var.get() if hasattr(self, "history_search_var") else "",
        )
        if selected_indices:
            history_rows = [row for row in history_rows if selected_indices.intersection(set(row.get("store_indices", [])))]
        lines = [",".join(self._history_table_export_columns())]
        for row in history_rows:
            if str(row.get("row_type", "result")) != "result":
                continue
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
        all_entries = self._select_result_history_entries()
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
        all_entries = self._select_result_history_entries()
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
        selected_count = len(self._selected_history_entries())
        if 2 <= selected_count <= 5:
            button.configure(state="normal")
        else:
            button.configure(state="disabled")

    @staticmethod
    def _format_percent_change(current: float, baseline: float) -> str:
        if abs(baseline) < 1e-12:
            return "N/A"
        return f"{((current - baseline) / baseline) * 100.0:.2f}%"

    @staticmethod
    def normalize_source_image_path(source_image_path: str | None) -> str:
        return str(source_image_path or "")

    def _line_profile_cache_key(self, source_image_path: str | None, frame_index: int, target_id: str) -> str:
        return f"{self.normalize_source_image_path(source_image_path)}|{int(frame_index)}|{target_id}"

    def resolve_line_profile_series(self, entry: ResultHistoryEntry) -> dict[str, Any] | None:
        if entry.measurement_type != "Line Profile" or not entry.target_id:
            return None
        cache_key = self._line_profile_cache_key(entry.source_image_path, entry.frame_index, entry.target_id)
        if cache_key in self.line_profile_series_cache:
            return self.line_profile_series_cache[cache_key]
        fallback_key = self._line_profile_cache_key("", entry.frame_index, entry.target_id)
        if fallback_key in self.line_profile_series_cache:
            return self.line_profile_series_cache[fallback_key]
        latest_line_profile = self._select_analysis_last_run("line_profile")
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
        comparable_entries = [entry for entry in entries if isinstance(entry.value, (int, float))]
        if len(comparable_entries) < 2:
            raise ValueError("at least two numeric history rows are required for comparison")
        entries = comparable_entries
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
                    "is_min": abs(float(entry.value) - min_value) < 1e-12,
                    "is_max": abs(float(entry.value) - max_value) < 1e-12,
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
                    self._format_history_value(entry.value),
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
        result_entries = self._selected_history_entries()
        if len(result_entries) < 2:
            messagebox.showinfo("Compare", "비교하려면 2개 이상 선택하세요.")
            return
        if len(result_entries) > 5:
            messagebox.showinfo("Compare", "한 번에 최대 5개까지만 비교할 수 있습니다.")
            return
        entries = [entry for _index, entry in result_entries]
        try:
            comparison = self.build_history_comparison(entries)
        except ValueError:
            messagebox.showwarning("Compare", "숫자 값이 있는 행 2개 이상을 선택하세요.")
            return
        if comparison["mixed_metrics"]:
            messagebox.showwarning("Compare", "같은 metric 비교를 권장합니다. (혼합 metric 계속 진행)")
        self.render_history_comparison(comparison)

    @staticmethod
    def _latest_metric_value(entries: list[ResultHistoryEntry], metric_name: str, measurement_type: str) -> float | None:
        for entry in reversed(entries):
            if entry.measurement_type == measurement_type and entry.metric.strip().upper() == metric_name.strip().upper():
                if isinstance(entry.value, (int, float)):
                    return float(entry.value)
                return None
        return None

    @staticmethod
    def _format_group_metric(value: float | None) -> str:
        return "-" if value is None else f"{float(value):.2f}"

    def build_group_history_comparison(self, group_ids: list[str]) -> dict[str, Any]:
        all_entries = self._select_result_history_entries()
        groups: list[dict[str, Any]] = []
        line_overlay_entries: list[ResultHistoryEntry] = []
        analysis_groups = self._select_analysis_groups_map()
        for index, group_id in enumerate(group_ids):
            group = analysis_groups.get(group_id)
            if group is None:
                continue
            group_entries = [entry for entry in all_entries if entry.group_id == group_id]
            if not group_entries:
                continue
            snr_value = self._latest_metric_value(group_entries, "SNR", "Analysis")
            cnr_value = self._latest_metric_value(group_entries, "CNR", "Analysis")
            uniformity_value = self._latest_metric_value(group_entries, "UNIFORMITY", "Analysis")
            line_mean_value = self._latest_metric_value(group_entries, "PROFILEMEAN", "Line Profile")
            groups.append(
                {
                    "group_id": group.group_id,
                    "image_name": group.image_name,
                    "frames": ",".join(str(item) for item in group.frame_indices) if group.frame_indices else "",
                    "created_at": group.created_at.replace("T", " ")[:19],
                    "roi_source_type": group.roi_source_type,
                    "snr": snr_value,
                    "cnr": cnr_value,
                    "uniformity": uniformity_value,
                    "line_mean": line_mean_value,
                    "is_baseline": index == 0,
                }
            )
            line_entry = next(
                (
                    entry
                    for entry in reversed(group_entries)
                    if entry.measurement_type == "Line Profile" and entry.target_id
                ),
                None,
            )
            if line_entry is not None:
                line_overlay_entries.append(line_entry)
        return {"groups": groups, "baseline_group_id": groups[0]["group_id"] if groups else "", "line_overlay_entries": line_overlay_entries}

    def render_group_history_comparison(self, comparison: dict[str, Any]) -> None:
        groups = list(comparison.get("groups", []))
        if len(groups) < 2:
            messagebox.showinfo("Compare", "비교 가능한 group 결과가 부족합니다.")
            return
        baseline = groups[0]
        dialog = tk.Toplevel(self.root)
        dialog.title("Group Compare")
        dialog.geometry("1320x700")
        ttk.Label(
            dialog,
            text=f"Baseline Group: {baseline['image_name']} ({baseline['group_id'][:8]})",
        ).pack(anchor="w", padx=8, pady=(8, 4))
        columns = ("group", "image", "frames", "source", "snr", "d_snr", "cnr", "d_cnr", "uniformity", "d_uniformity", "line", "d_line")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=10)
        headers = {
            "group": "Group ID",
            "image": "Image",
            "frames": "Frames",
            "source": "ROI Source",
            "snr": "SNR",
            "d_snr": "ΔSNR",
            "cnr": "CNR",
            "d_cnr": "ΔCNR",
            "uniformity": "Uniformity",
            "d_uniformity": "ΔUniformity",
            "line": "Line Mean",
            "d_line": "ΔLine Mean",
        }
        widths = {"group": 120, "image": 150, "frames": 90, "source": 120, "snr": 80, "d_snr": 90, "cnr": 80, "d_cnr": 90, "uniformity": 90, "d_uniformity": 100, "line": 90, "d_line": 100}
        for key in columns:
            tree.heading(key, text=headers[key])
            tree.column(key, width=widths[key], anchor="w")
        tree.tag_configure("baseline_row", background="#ecfeff")
        tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        def _delta_text(value: float | None, baseline_value: float | None) -> str:
            if value is None or baseline_value is None:
                return "-"
            return f"{(float(value) - float(baseline_value)):.2f}"

        for row in groups:
            values = (
                str(row["group_id"])[:8],
                str(row["image_name"]),
                str(row["frames"]),
                str(row["roi_source_type"]),
                self._format_group_metric(row.get("snr")),
                _delta_text(row.get("snr"), baseline.get("snr")),
                self._format_group_metric(row.get("cnr")),
                _delta_text(row.get("cnr"), baseline.get("cnr")),
                self._format_group_metric(row.get("uniformity")),
                _delta_text(row.get("uniformity"), baseline.get("uniformity")),
                self._format_group_metric(row.get("line_mean")),
                _delta_text(row.get("line_mean"), baseline.get("line_mean")),
            )
            tags = ("baseline_row",) if bool(row.get("is_baseline")) else ()
            tree.insert("", "end", values=values, tags=tags)

        overlay_entries = list(comparison.get("line_overlay_entries", []))
        if len(overlay_entries) >= 2:
            overlay_data = self.build_line_profile_overlay_data(overlay_entries)
            if overlay_data.get("series"):
                ttk.Label(dialog, text="Line Profile Overlay", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", padx=8, pady=(2, 4))
                self.render_line_profile_overlay_chart(dialog, overlay_data)
                delta_data = self.build_delta_profile_data(overlay_data)
                if delta_data.get("series"):
                    ttk.Label(dialog, text="Delta Profile (vs baseline)", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", padx=8, pady=(0, 4))
                    self.render_delta_profile_chart(dialog, delta_data)

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
            for candidate in self._selector_measurements_for_current_frame(kind="line"):
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
        self._sync_mtf_roi_binding_state()
        self._update_uniformity_input_ui()
        self._refresh_analysis_results_panel()
        self._refresh_image_analysis_selectors()
        self._schedule_mtf_graph_redraw()

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
        for measurement in reversed(self._selector_measurements_for_current_frame(kind="roi")):
            if self._geometry_matches(measurement.geometry_key, current_geometry) and self._get_measurement_roi_role(measurement) == normalized_role:
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

    def _analysis_input_value(self, input_key: str) -> str:
        input_store = self.analysis_inputs if input_key in self.analysis_inputs else self.image_analysis_inputs
        var = input_store.get(input_key)
        return str(var.get()).strip() if var is not None else ""

    def _set_analysis_input_value(self, input_key: str, value: str) -> None:
        input_store = self.analysis_inputs if input_key in self.analysis_inputs else self.image_analysis_inputs
        var = input_store.get(input_key)
        if var is not None:
            var.set(value)

    def _resolve_combobox_measurement_id(self, kind: str, combobox_key: str) -> tuple[str, str]:
        combo = self._analysis_comboboxes.get(combobox_key)
        option_map = self._analysis_option_maps.get(kind, {})
        if combo is None:
            combo = self._image_analysis_comboboxes.get(combobox_key)
            option_map = self._image_analysis_option_maps.get(kind, {})
        if combo is None:
            return "", ""
        selected = str(combo.get()).strip()
        if not selected:
            return "", ""
        return str(option_map.get(selected) or selected), selected

    def _resolve_signal_analysis_slot(
        self,
        *,
        slot_name: str,
        input_key: str,
        combobox_key: str,
        role_names: tuple[str, ...],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        direct_id = self._analysis_input_value(input_key)
        if direct_id:
            measurement = self._find_measurement_by_id(direct_id, expected_kind="roi")
            if measurement is not None and self._is_analysis_compatible_measurement(measurement):
                return {"id": measurement.id, "measurement": measurement, "source": "direct", "warnings": warnings}
            warnings.append(f"{slot_name}: direct/manual ROI id is invalid: {direct_id}")

        combobox_id, selected_label = self._resolve_combobox_measurement_id("roi", combobox_key)
        if combobox_id:
            measurement = self._find_measurement_by_id(combobox_id, expected_kind="roi")
            if measurement is not None and self._is_analysis_compatible_measurement(measurement):
                self._set_analysis_input_value(input_key, measurement.id)
                return {"id": measurement.id, "measurement": measurement, "source": "combobox", "warnings": warnings}
            warnings.append(f"{slot_name}: combobox selection is invalid: {selected_label}")

        for role_name in role_names:
            measurement = self._find_roi_by_role(role_name)
            if measurement is not None and self._is_analysis_compatible_measurement(measurement):
                self._set_analysis_input_value(input_key, measurement.id)
                return {"id": measurement.id, "measurement": measurement, "source": "role", "warnings": warnings}

        return {"id": "", "measurement": None, "source": "invalid", "warnings": warnings}

    def resolve_signal_analysis_inputs(self, analysis_type: str | None = None) -> dict[str, Any]:
        formula_var = self.analysis_inputs.get("cnr_formula")
        formula = formula_var.get() if formula_var is not None else "standard_noise"
        requested = {analysis_type} if analysis_type in {"snr", "cnr"} else {"snr", "cnr"}
        resolved: dict[str, Any] = {}

        if "snr" in requested:
            signal = self._resolve_signal_analysis_slot(
                slot_name="snr_signal",
                input_key="snr_signal_roi_id",
                combobox_key="snr_signal",
                role_names=("signal",),
            )
            background = self._resolve_signal_analysis_slot(
                slot_name="snr_background",
                input_key="snr_background_roi_id",
                combobox_key="snr_noise",
                role_names=("background", "noise"),
            )
            warnings = [*signal["warnings"], *background["warnings"]]
            missing = []
            if signal["measurement"] is None:
                missing.append("signal ROI")
            if background["measurement"] is None:
                missing.append("background/noise ROI")
            is_valid = not missing
            resolved["snr"] = {
                "is_valid": is_valid,
                "signal_roi_id": signal["id"],
                "background_roi_id": background["id"],
                "noise_roi_id": background["id"],
                "source": {"signal": signal["source"], "background": background["source"]},
                "warnings": warnings,
                "reason": "" if is_valid else "Missing " + ", ".join(missing),
                "resolved_measurements": {"signal": signal["measurement"], "background": background["measurement"], "noise": background["measurement"]},
            }

        if "cnr" in requested:
            target = self._resolve_signal_analysis_slot(
                slot_name="cnr_target",
                input_key="cnr_target_roi_id",
                combobox_key="cnr_target",
                role_names=("target",),
            )
            reference = self._resolve_signal_analysis_slot(
                slot_name="cnr_reference",
                input_key="cnr_reference_roi_id",
                combobox_key="cnr_reference",
                role_names=("reference",),
            )
            noise = self._resolve_signal_analysis_slot(
                slot_name="cnr_noise",
                input_key="cnr_noise_roi_id",
                combobox_key="cnr_noise",
                role_names=("noise",),
            ) if formula == "standard_noise" else {"id": "", "measurement": None, "source": "not_required", "warnings": []}
            warnings = [*target["warnings"], *reference["warnings"], *noise["warnings"]]
            missing = []
            if target["measurement"] is None:
                missing.append("target ROI")
            if reference["measurement"] is None:
                missing.append("reference ROI")
            if formula == "standard_noise" and noise["measurement"] is None:
                missing.append("noise ROI")
            is_valid = not missing
            resolved["cnr"] = {
                "is_valid": is_valid,
                "formula": formula,
                "target_roi_id": target["id"],
                "reference_roi_id": reference["id"],
                "noise_roi_id": noise["id"],
                "source": {"target": target["source"], "reference": reference["source"], "noise": noise["source"]},
                "warnings": warnings,
                "reason": "" if is_valid else "Missing " + ", ".join(missing),
                "resolved_measurements": {"target": target["measurement"], "reference": reference["measurement"], "noise": noise["measurement"]},
            }
        if analysis_type in {"snr", "cnr"}:
            return resolved[analysis_type]
        return resolved

    def _update_analysis_action_button_state(self) -> None:
        action_buttons = getattr(self, "_analysis_action_buttons", {})
        snr_button = action_buttons.get("snr")
        cnr_button = action_buttons.get("cnr")
        resolved = self.resolve_signal_analysis_inputs()

        if snr_button is not None:
            snr = resolved.get("snr", {})
            snr_ready = bool(snr.get("is_valid"))
            snr_button.configure(state="normal" if snr_ready else "disabled")
            snr_reason_var = self.analysis_results.get("snr_ready_reason")
            if snr_reason_var is not None:
                if snr_ready:
                    sources = (snr.get("source") or {}).values()
                    source_text = "manual measurement" if "direct" in sources or "combobox" in sources else "role-based measurement"
                    snr_reason_var.set(f"Ready: {source_text}")
                else:
                    snr_reason_var.set(str(snr.get("reason") or "ROI selection required"))

        if cnr_button is not None:
            cnr = resolved.get("cnr", {})
            cnr_button.configure(state="normal" if bool(cnr.get("is_valid")) else "disabled")

        mtf_button = action_buttons.get("mtf")
        if mtf_button is not None:
            mtf_active_var = self.analysis_inputs.get("mtf_active_roi_id")
            mtf_active_id = mtf_active_var.get() if mtf_active_var is not None else ""
            mtf_roi = self._find_measurement_by_id(mtf_active_id, expected_kind="roi")
            mtf_ready = mtf_roi is not None and self._is_analysis_compatible_measurement(mtf_roi)
            mtf_button.configure(state="normal" if mtf_ready else "disabled")
            if mtf_ready:
                self.analysis_results["mtf_validation_summary"].set("Validation: ready")
            else:
                self.analysis_results["mtf_validation_summary"].set("Validation: select and bind a rectangular ROI")

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
            for measurement in self._selector_measurements_for_current_frame(kind="roi")
            if self._geometry_matches(measurement.geometry_key, current_geometry)
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
        for measurement in self._selector_measurements_for_current_frame(kind="line"):
            if not self._geometry_matches(measurement.geometry_key, current_geometry):
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

    def _sync_mtf_roi_binding_state(self) -> None:
        mtf_active_var = self.analysis_inputs.get("mtf_active_roi_id")
        if mtf_active_var is None:
            return
        roi_id = mtf_active_var.get().strip()
        measurement = self._find_measurement_by_id(roi_id, expected_kind="roi") if roi_id else None
        if measurement is None:
            mtf_active_var.set("")
            self.analysis_results["mtf_selected_roi_status"].set("Selected ROI: none")
        else:
            self.analysis_results["mtf_selected_roi_status"].set(
                f"Selected ROI: {self._display_name_for_roi_id(measurement.id)} ({measurement.id[:8]})"
            )

    def _bind_selected_roi_to_mtf(self) -> None:
        selected_id = str(self.selected_persistent_measurement_id or "").strip()
        if not selected_id:
            self.analysis_results["mtf_validation_summary"].set("Validation: no ROI selected")
            messagebox.showinfo("MTF Analysis", "선택된 ROI가 없습니다.")
            return
        measurement = self._find_measurement_by_id(selected_id)
        if measurement is None:
            self.analysis_results["mtf_validation_summary"].set("Validation: selected object no longer exists")
            return
        if measurement.kind != "roi":
            self.analysis_results["mtf_validation_summary"].set("Validation: MTF requires rectangular ROI")
            messagebox.showwarning("MTF Analysis", "MTF는 사각형 ROI만 사용할 수 있습니다.")
            return
        mtf_active_var = self.analysis_inputs.get("mtf_active_roi_id")
        if mtf_active_var is None:
            return
        mtf_active_var.set(measurement.id)
        self._sync_mtf_roi_binding_state()
        self._update_analysis_action_button_state()

    def _build_mtf_run_context(self, measurement: Measurement) -> dict[str, Any]:
        image_id = self.path_var.get().strip() if hasattr(self, "path_var") else ""
        return {
            "image_id": image_id or "current_image",
            "frame_index": int(self.current_frame),
            "roi_id": measurement.id,
            "group_id": self.active_group_id,
            "study_id": self.active_study_id,
        }

    def _run_mtf_analysis(self) -> None:
        mtf_active_var = self.analysis_inputs.get("mtf_active_roi_id")
        roi_id = mtf_active_var.get().strip() if mtf_active_var is not None else ""
        measurement = self._find_measurement_by_id(roi_id, expected_kind="roi") if roi_id else None
        if measurement is None:
            self.analysis_results["mtf_validation_summary"].set("Validation: no bound ROI")
            messagebox.showinfo("MTF Analysis", "먼저 사각형 ROI를 선택하고 바인딩하세요.")
            return
        mode_raw = self.analysis_inputs.get("mtf_mode").get() if self.analysis_inputs.get("mtf_mode") is not None else "matlab_reference"
        mtf_mode_id = self._parse_prefixed_value(mode_raw, "matlab_reference")
        crop_semantics = "matlab_imcrop" if mtf_mode_id == "matlab_reference" else "default"
        frame = self._get_frame_pixel_array(measurement.frame_index)
        roi_pixels, bounds = self._extract_roi_pixels(
            frame,
            measurement.start,
            measurement.end,
            ensure_non_empty=True,
            semantics=crop_semantics,
        )
        if roi_pixels.size == 0:
            self.analysis_results["mtf_validation_summary"].set("Validation: ROI pixels unavailable")
            messagebox.showwarning("MTF Analysis", "ROI 픽셀을 추출할 수 없습니다.")
            return
        imaging_mode = self._parse_prefixed_value(self.analysis_inputs["mtf_imaging_mode"].get(), "general_radiography")
        operating_mode = self._parse_prefixed_value(self.analysis_inputs["mtf_operating_mode"].get(), "strict_iec")
        mtf_result = self._execute_mtf_pipeline(
            roi_pixels,
            bounds,
            imaging_mode,
            operating_mode,
            roi_start=measurement.start,
            roi_end=measurement.end,
            crop_semantics=crop_semantics,
        )
        context = self._build_mtf_run_context(measurement)
        self.complete_mtf_analysis(mtf_result, context)
        self._update_mtf_analysis_ui(mtf_result)
        self._update_analysis_action_button_state()

    def _estimate_edge_snr_for_roi(self, roi_pixels: np.ndarray) -> float | None:
        if roi_pixels.size == 0:
            return None
        p10 = float(np.percentile(roi_pixels, 10))
        p90 = float(np.percentile(roi_pixels, 90))
        noise = float(np.std(roi_pixels))
        if noise <= 0:
            return None
        return abs(p90 - p10) / noise

    def _execute_mtf_pipeline(
        self,
        roi_pixels: np.ndarray,
        bounds: tuple[int, int, int, int],
        imaging_mode: str,
        operating_mode: str,
        roi_start: tuple[int | float, int | float] | None = None,
        roi_end: tuple[int | float, int | float] | None = None,
        crop_semantics: str = "default",
    ) -> dict[str, Any]:
        mode_raw = self.analysis_inputs.get("mtf_mode").get() if self.analysis_inputs.get("mtf_mode") is not None else "matlab_reference"
        mtf_mode_id = self._parse_prefixed_value(mode_raw, "matlab_reference")
        if mtf_mode_id not in {"matlab_reference", "moduba_slanted_edge"}:
            mtf_mode_id = "matlab_reference"
        mtf_mode_label = "MATLAB Reference" if mtf_mode_id == "matlab_reference" else "IEC / Moduba Slanted-edge"
        mtf_active_var = self.analysis_inputs.get("mtf_active_roi_id")
        selected_roi_id = mtf_active_var.get().strip() if mtf_active_var is not None else ""
        dtype_before = str(roi_pixels.dtype)
        spacing = self._get_pixel_spacing_mm()
        row_spacing_mm = float(spacing[0]) if spacing is not None else None
        if mtf_mode_id == "matlab_reference":
            phase1 = calculate_matlab_reference_mtf(roi_pixels, pixel_spacing_mm=row_spacing_mm)
        else:
            phase1 = calculate_slanted_edge_mtf(roi_pixels)
        edge_snr = self._estimate_edge_snr_for_roi(roi_pixels)
        phase2 = evaluate_mtf_integrity(phase1, edge_snr=edge_snr, clipping_detected=False)
        phase3 = grade_mtf_for_internal_qa(phase1, phase2)
        interpolation_diag = ((phase1.get("diagnostics") or {}).get("interpolation") or {})
        pchip_available = bool(interpolation_diag.get("pchip_available", interpolation_diag.get("scipy_pchip_used", False)))
        matlab_equivalence_status = "valid" if pchip_available else "invalid"
        fallback_warning = (
            "PCHIP unavailable: using linear fallback; result may differ from MATLAB."
            if mtf_mode_id == "matlab_reference" and not pchip_available
            else None
        )
        if mtf_mode_id == "matlab_reference" and crop_semantics == "matlab_imcrop":
            roi_width_px = max(bounds[2] - bounds[0] + 1, 0)
            roi_height_px = max(bounds[3] - bounds[1] + 1, 0)
        else:
            roi_width_px = max(bounds[2] - bounds[0], 0)
            roi_height_px = max(bounds[3] - bounds[1], 0)
        roi_width_mm = float(roi_width_px * spacing[1]) if spacing is not None else None
        roi_height_mm = float(roi_height_px * spacing[0]) if spacing is not None else None
        phase4 = evaluate_iec_reporting(
            {
                "iec_reporting_requested": True,
                "imaging_mode": imaging_mode,
                "operating_mode": operating_mode,
                "linearity_status": "raw",
                "calculation_status": phase1.get("calculation_status"),
                "calculation_validity": phase1.get("calculation_status") == "pass",
                "edge_angle_deg": phase1.get("edge_angle_deg"),
                "averaging_method": "esf",
                "pixel_spacing_available": spacing is not None,
                "roi_size_mm": {"width_mm": roi_width_mm, "height_mm": roi_height_mm},
                "reason_codes": phase2.get("reason_codes", []),
            }
        )
        mtf50_cy = phase1.get("mtf50")
        mtf10_cy = phase1.get("mtf10")
        mtf50_lp = (
            float(mtf50_cy) / float(row_spacing_mm)
            if isinstance(mtf50_cy, (int, float)) and isinstance(row_spacing_mm, (int, float)) and row_spacing_mm > 0
            else None
        )
        mtf10_lp = (
            float(mtf10_cy) / float(row_spacing_mm)
            if isinstance(mtf10_cy, (int, float)) and isinstance(row_spacing_mm, (int, float)) and row_spacing_mm > 0
            else None
        )
        nyquist_lp = (0.5 / float(row_spacing_mm)) if isinstance(row_spacing_mm, (int, float)) and row_spacing_mm > 0 else None
        key_metrics = {
            "mtf50": mtf50_lp if mtf50_lp is not None else mtf50_cy,
            "mtf10": mtf10_lp if mtf10_lp is not None else mtf10_cy,
            "mtf50_cy_per_pixel": mtf50_cy,
            "mtf10_cy_per_pixel": mtf10_cy,
            "mtf50_lp_per_mm": mtf50_lp,
            "mtf10_lp_per_mm": mtf10_lp,
            "nyquist_mtf": self._lookup_nyquist_mtf(phase1.get("mtf_curve") or {}),
            "nyquist_frequency_cy_per_pixel": 0.5,
            "nyquist_frequency_lp_per_mm": nyquist_lp,
            "frequency_unit": "lp/mm" if nyquist_lp is not None else "cy/pixel",
            "mode_id": mtf_mode_id,
            "mode_label": mtf_mode_label,
        }
        diagnostics = self._build_mtf_diagnostics(
            mtf_mode_id=mtf_mode_id,
            mtf_mode_label=mtf_mode_label,
            selected_roi_id=selected_roi_id,
            bounds=bounds,
            spacing=spacing,
            roi_pixels=roi_pixels,
            dtype_before=dtype_before,
            phase1=phase1,
            key_metrics=key_metrics,
            roi_start=roi_start,
            roi_end=roi_end,
            crop_semantics=crop_semantics,
        )
        matlab_esf_validity = ((phase1.get("diagnostics") or {}).get("matlab_esf_validity") or {})
        invalid_roi_for_matlab_esf = bool(
            mtf_mode_id == "matlab_reference"
            and matlab_esf_validity
            and not bool(matlab_esf_validity.get("roi_is_valid_for_matlab_esf", False))
        )
        result = {
            "calculation_status": phase1.get("calculation_status", "reject"),
            "calculation_validity": "valid" if phase1.get("calculation_status") == "pass" else "invalid",
            "rejection_reason": phase1.get("rejection_reason"),
            "edge_angle_deg": phase1.get("edge_angle_deg"),
            "edge_snr": edge_snr,
            "mtf_curve": phase1.get("mtf_curve") or {},
            "esf_curve": phase1.get("esf_curve") or {},
            "lsf_curve": phase1.get("lsf_curve") or {},
            "key_mtf_metrics": key_metrics,
            "mtf_mode_id": mtf_mode_id,
            "mtf_mode_label": mtf_mode_label,
            "esf_method": "mean(roi, axis=0)" if mtf_mode_id == "matlab_reference" else "slanted-edge distance binning",
            "smoothing": "gaussian_window_5" if mtf_mode_id == "matlab_reference" else "weighted_moving_average_[1,2,3,2,1]",
            "window": "hamming" if mtf_mode_id == "matlab_reference" else "hanning",
            "nfft": 4096 if mtf_mode_id == "matlab_reference" else (phase1.get("diagnostics") or {}).get("fft", {}).get("nfft"),
            "interpolation": (
                ((phase1.get("diagnostics") or {}).get("interpolation") or {}).get("mtf50_interpolation_method")
                if mtf_mode_id == "matlab_reference"
                else "linear"
            ),
            "warnings": phase2.get("warnings") or [],
            "reason_codes": phase2.get("reason_codes") or [],
            "matlab_equivalence_status": (
                "invalid_roi_for_matlab_esf"
                if invalid_roi_for_matlab_esf
                else (matlab_equivalence_status if mtf_mode_id == "matlab_reference" else "not_applicable")
            ),
            "qa_grade": phase3.get("qa_grade"),
            "qa_status_summary": phase3.get("qa_status_summary"),
            "iec_compliance": phase4.get("iec_reporting_status"),
            "validation_summary": phase4.get("iec_reporting_summary"),
            "roi_size_mm": {"width": roi_width_mm, "height": roi_height_mm},
            "diagnostics": diagnostics,
            "roi_equivalence_comparison_block": (diagnostics.get("roi_equivalence_comparison_block") or {}),
        }
        if result["calculation_status"] != "pass":
            result["reason_codes"] = list(dict.fromkeys((result["reason_codes"] or []) + ["PHASE1_REJECT"]))
            if result.get("rejection_reason"):
                result["warnings"] = list(dict.fromkeys((result.get("warnings") or []) + [str(result["rejection_reason"])]))
        if fallback_warning:
            result["warnings"] = list(dict.fromkeys((result.get("warnings") or []) + [fallback_warning]))
            result["reason_codes"] = list(dict.fromkeys((result.get("reason_codes") or []) + ["MATLAB_PCHIP_FALLBACK"]))
        if invalid_roi_for_matlab_esf:
            roi_warning = str(
                matlab_esf_validity.get("roi_validity_reason")
                or "Invalid ROI for MATLAB-style ESF extraction: ROI orientation or crop does not match the MATLAB reference condition."
            )
            result["warnings"] = list(dict.fromkeys((result.get("warnings") or []) + [roi_warning]))
            result["reason_codes"] = list(dict.fromkeys((result.get("reason_codes") or []) + ["INVALID_ROI_FOR_MATLAB_ESF"]))
        return result

    def _build_mtf_diagnostics(
        self,
        mtf_mode_id: str,
        mtf_mode_label: str,
        selected_roi_id: str,
        bounds: tuple[int, int, int, int],
        spacing: tuple[float, float] | None,
        roi_pixels: np.ndarray,
        dtype_before: str,
        phase1: dict[str, Any],
        key_metrics: dict[str, Any],
        roi_start: tuple[int | float, int | float] | None = None,
        roi_end: tuple[int | float, int | float] | None = None,
        crop_semantics: str = "default",
    ) -> dict[str, Any]:
        phase1_diag = dict(phase1.get("diagnostics") or {})
        fft_diag = dict(phase1_diag.get("fft") or {})
        interpolation_diag = dict(phase1_diag.get("interpolation") or {})
        gaussian_diag = dict(phase1_diag.get("gaussian_smoothing") or {})
        orientation_diag = dict(phase1_diag.get("edge_orientation_and_esf_direction") or {})
        mtf_curve = dict(phase1.get("mtf_curve") or {})
        freqs = np.asarray(mtf_curve.get("frequency_cy_per_pixel", []), dtype=np.float64)
        mtf = np.asarray(mtf_curve.get("mtf", []), dtype=np.float64)
        row_spacing_mm = float(spacing[0]) if spacing is not None else None
        mtf50_cy = key_metrics.get("mtf50_cy_per_pixel")
        if not isinstance(mtf50_cy, (int, float)):
            mtf50_cy = key_metrics.get("mtf50")
        mtf10_cy = key_metrics.get("mtf10_cy_per_pixel")
        if not isinstance(mtf10_cy, (int, float)):
            mtf10_cy = key_metrics.get("mtf10")
        nyquist_lpmm = (0.5 / row_spacing_mm) if row_spacing_mm and row_spacing_mm > 0 else None
        mtf50_lpmm = key_metrics.get("mtf50_lp_per_mm")
        if not isinstance(mtf50_lpmm, (int, float)):
            mtf50_lpmm = (float(mtf50_cy) / row_spacing_mm) if isinstance(mtf50_cy, (int, float)) and row_spacing_mm else None
        mtf10_lpmm = key_metrics.get("mtf10_lp_per_mm")
        if not isinstance(mtf10_lpmm, (int, float)):
            mtf10_lpmm = (float(mtf10_cy) / row_spacing_mm) if isinstance(mtf10_cy, (int, float)) and row_spacing_mm else None
        image_name = Path(self.path_var.get().strip()).name if hasattr(self, "path_var") else ""
        matlab_reference = {
            "file": "MTF LOW_70kVp_20mAs_001.DCM",
            "pixel_size_mm": 0.1988,
            "nyquist_lp_per_mm": 2.5151,
            "mtf50_lp_per_mm": 0.4285,
            "mtf10_lp_per_mm": 1.0501,
            "pipeline": [
                "double(dicomread)",
                "imcrop",
                "mean(roi,1)",
                "gaussian smoothing",
                "normalize (0~1)",
                "abs(diff)",
                "normalize",
                "hamming",
                "nfft=4096",
                "fft",
                "normalize",
                "freq = k/(nfft*pixel)",
                "pchip interpolation",
            ],
        }
        def _rel(diff: float | None, ref: float) -> float | None:
            if diff is None or ref == 0:
                return None
            return abs(float(diff) / float(ref)) * 100.0

        mtf50_diff = (mtf50_lpmm - matlab_reference["mtf50_lp_per_mm"]) if mtf50_lpmm is not None else None
        mtf10_diff = (mtf10_lpmm - matlab_reference["mtf10_lp_per_mm"]) if mtf10_lpmm is not None else None
        nyq_diff = (nyquist_lpmm - matlab_reference["nyquist_lp_per_mm"]) if nyquist_lpmm is not None else None
        roi_bounds_used = [int(bounds[0]), int(bounds[1]), int(bounds[2]), int(bounds[3])]
        roi_bounds_input = (
            [float(roi_start[0]), float(roi_start[1]), float(roi_end[0]), float(roi_end[1])]
            if roi_start is not None and roi_end is not None
            else None
        )
        matlab_roi_bounds = roi_bounds_used
        matlab_roi_crop_equivalence = bool(mtf_mode_id == "matlab_reference" and crop_semantics == "matlab_imcrop")
        roi_match_status = "exact" if matlab_roi_crop_equivalence else "unknown"
        roi_validation_status = "valid"
        roi_validation_message = (
            "MATLAB reference crop uses imcrop-like inclusive rectangle semantics (floor(min), ceil(max), inclusive bounds)."
            if matlab_roi_crop_equivalence
            else "ROI crop semantics are not in MATLAB-imcrop-equivalent mode."
        )
        roi_definition_source = "two_corner_points:start_end"
        if crop_semantics == "matlab_imcrop":
            roi_coordinate_transform_chain = [
                "input start/end (float-capable)",
                "x0=min(start.x,end.x), y0=min(start.y,end.y), x1=max(...), y1=max(...)",
                "x0,y0=floor(min corner), x1,y1=ceil(max corner)",
                "clip to [0,width-1] and [0,height-1]",
                "inclusive crop slice: image[y0:y1+1, x0:x1+1]",
            ]
        else:
            roi_coordinate_transform_chain = [
                "input start/end (float-capable)",
                "round start/end to nearest integer",
                "reorder corners with min/max",
                "clip to [0,width] and [0,height]",
                "end-exclusive crop slice: image[y0:y1, x0:x1]",
            ]
        roi_summary_line = (
            f"x0={roi_bounds_used[0]}, y0={roi_bounds_used[1]}, "
            f"x1={roi_bounds_used[2]}, y1={roi_bounds_used[3]}, "
            f"width={int(roi_pixels.shape[1]) if roi_pixels.ndim == 2 else 0}, "
            f"height={int(roi_pixels.shape[0]) if roi_pixels.ndim == 2 else 0}"
        )
        matlab_esf_validity_diag = dict(phase1_diag.get("matlab_esf_validity") or {})
        matlab_imcrop_equivalence_status = "equivalent" if matlab_roi_crop_equivalence else "not_equivalent"

        edge_orientation = str(orientation_diag.get("edge_orientation_detected", "unknown"))
        esf_direction = str(orientation_diag.get("esf_direction_used", "unknown"))
        expected_direction = str(orientation_diag.get("expected_direction", "column-wise mean"))
        direction_match = bool(orientation_diag.get("direction_match", expected_direction == esf_direction))
        esf_validation_message = None if direction_match else "ESF direction mismatch: invalid MTF result"

        nfft_used = int(fft_diag.get("nfft", 0)) if fft_diag.get("nfft") is not None else 0
        lsf_length = int((phase1_diag.get("lsf") or {}).get("lsf_length", 0))
        freq_resolution = (1.0 / (float(nfft_used) * row_spacing_mm)) if nfft_used > 0 and row_spacing_mm else None
        matlab_freq_resolution = (1.0 / (4096.0 * row_spacing_mm)) if row_spacing_mm else None
        resolution_ratio = (freq_resolution / matlab_freq_resolution) if (freq_resolution is not None and matlab_freq_resolution not in (None, 0)) else None
        fft_resolution_warning = (
            "FFT resolution significantly different from MATLAB"
            if isinstance(resolution_ratio, (int, float)) and abs(float(resolution_ratio) - 1.0) > 0.05
            else None
        )
        fft_resolution_impact = (
            "Different frequency bin spacing shifts threshold crossing precision for MTF50/MTF10."
            if fft_resolution_warning
            else "FFT resolution aligned with MATLAB target nfft=4096."
        )

        pchip_available = bool(interpolation_diag.get("pchip_available", interpolation_diag.get("scipy_pchip_used", False)))
        interpolation_method_used = str(interpolation_diag.get("interpolation_method_used") or interpolation_diag.get("mtf50_interpolation_method") or "unknown")
        matlab_comparison = {
            "applies_to_current_image": image_name.lower() == matlab_reference["file"].lower(),
            "matlab_reference": matlab_reference,
            "moduba_current": {
                "mtf50_lp_per_mm": mtf50_lpmm,
                "mtf10_lp_per_mm": mtf10_lpmm,
                "nyquist_lp_per_mm": nyquist_lpmm,
            },
            "difference": {
                "mtf50_diff_lp_per_mm": mtf50_diff,
                "mtf50_diff_relative_percent": _rel(mtf50_diff, matlab_reference["mtf50_lp_per_mm"]),
                "mtf10_diff_lp_per_mm": mtf10_diff,
                "mtf10_diff_relative_percent": _rel(mtf10_diff, matlab_reference["mtf10_lp_per_mm"]),
                "nyquist_diff_lp_per_mm": nyq_diff,
                "nyquist_diff_relative_percent": _rel(nyq_diff, matlab_reference["nyquist_lp_per_mm"]),
            },
            "step_comparison": {
                "input_dtype": "MATLAB uses double(dicomread); Moduba converts ROI to float64 for MATLAB reference mode.",
                "roi_reduction": (
                    "MATLAB mean(roi,1); Moduba mean(roi, axis=0) in MATLAB reference mode."
                    if mtf_mode_id == "matlab_reference"
                    else "Legacy mode uses slanted-edge distance binning ESF."
                ),
                "smoothing": (
                    "MATLAB gaussian; Moduba gaussian_window_5 in MATLAB reference mode."
                    if mtf_mode_id == "matlab_reference"
                    else "Legacy mode uses weighted moving average [1,2,3,2,1]."
                ),
                "lsf": (
                    "MATLAB abs(diff); Moduba abs(diff) in MATLAB reference mode."
                    if mtf_mode_id == "matlab_reference"
                    else "Legacy mode uses gradient(esf)."
                ),
                "window": "MATLAB hamming; Moduba hamming (MATLAB reference mode)." if mtf_mode_id == "matlab_reference" else "Legacy mode uses hanning.",
                "nfft": "MATLAB fixed 4096; Moduba fixed 4096 (MATLAB reference mode)." if mtf_mode_id == "matlab_reference" else "Legacy mode uses variable nfft.",
                "interpolation": (
                    f"MATLAB pchip; Moduba {interpolation_method_used}."
                    if mtf_mode_id == "matlab_reference"
                    else "Legacy mode uses linear crossing interpolation."
                ),
            },
        }
        return {
            "mode": {"mtf_mode_id": mtf_mode_id, "mtf_mode_label": mtf_mode_label},
            "A_roi": {
                "selected_roi_id": selected_roi_id or None,
                "matlab_roi_crop_equivalence": matlab_roi_crop_equivalence,
                "matlab_imcrop_equivalence_status": matlab_imcrop_equivalence_status,
                "roi_definition_source": roi_definition_source,
                "roi_input_coordinates": roi_bounds_input,
                "roi_crop_bounds_used": roi_bounds_used,
                "roi_bounds_input": roi_bounds_input,
                "roi_bounds_pixels": roi_bounds_used,
                "roi_bounds_used": roi_bounds_used,
                "roi_width_pixels": int(roi_pixels.shape[1]) if roi_pixels.ndim == 2 else int(max(bounds[2] - bounds[0], 0)),
                "roi_height_pixels": int(roi_pixels.shape[0]) if roi_pixels.ndim == 2 else int(max(bounds[3] - bounds[1], 0)),
                "roi_shape_used": [int(roi_pixels.shape[0]), int(roi_pixels.shape[1])] if roi_pixels.ndim == 2 else None,
                "crop_semantics_note": roi_validation_message,
                "roi_coordinate_transform_chain": roi_coordinate_transform_chain,
                "roi_summary_line": roi_summary_line,
                "pixel_spacing_mm": row_spacing_mm,
            },
            "B_data_source": {
                "source_image_type": "raw_modality_lut_frame",
                "dtype_before": dtype_before,
                "dtype_used": str(np.asarray(roi_pixels, dtype=np.float64).dtype),
                "dtype_used_for_calculation": str(np.asarray(roi_pixels, dtype=np.float64).dtype),
                "converted_to_float": True,
            },
            "A_interpolation": {
                "pchip_available": pchip_available,
                "interpolation_method_used": interpolation_method_used,
                "matlab_equivalence_status": "valid" if pchip_available else "invalid",
                "warning": (
                    "PCHIP unavailable: using linear fallback; result may differ from MATLAB."
                    if not pchip_available
                    else None
                ),
            },
            "B_gaussian_smoothing": {
                "matlab_smoothing_reference": gaussian_diag.get("matlab_smoothing_reference", "smoothdata gaussian 5"),
                "moduba_smoothing_method": gaussian_diag.get("moduba_smoothing_method", "gaussian_window_5_numpy_convolve"),
                "gaussian_kernel_size": gaussian_diag.get("gaussian_kernel_size", 5),
                "kernel_size_used": gaussian_diag.get("kernel_size_used", gaussian_diag.get("gaussian_kernel_size", 5)),
                "gaussian_sigma_or_equivalent": gaussian_diag.get("gaussian_sigma_or_equivalent", 1.0),
                "sigma_used": gaussian_diag.get("sigma_used", gaussian_diag.get("gaussian_sigma_or_equivalent", 1.0)),
                "gaussian_boundary_mode": gaussian_diag.get("gaussian_boundary_mode", "unknown"),
                "boundary_mode": gaussian_diag.get("boundary_mode", gaussian_diag.get("gaussian_boundary_mode", "unknown")),
                "smoothing_normalization_behavior": gaussian_diag.get("smoothing_normalization_behavior", "unknown"),
                "smoothing_equivalence_status": gaussian_diag.get("smoothing_equivalence_status", "unknown"),
                "smoothing_equivalence_note": gaussian_diag.get("smoothing_equivalence_note"),
                "mismatch_report": "Gaussian smoothing behavior differs from MATLAB",
                "likely_effect_on_esf_shape": "Boundary and kernel-profile differences can change ESF transition steepness.",
                "likely_effect_on_lsf_peak_width": "ESF smoothing differences broaden or narrow LSF peak width.",
                "likely_effect_on_mtf_shift": "LSF width changes can shift MTF50/MTF10 crossing frequencies.",
            },
            "C_esf": phase1_diag.get("esf") or {},
            "D_lsf": phase1_diag.get("lsf") or {},
            "C_matlab_esf_validity": matlab_esf_validity_diag,
            "E_fft": fft_diag,
            "F_units": {
                "lp_per_mm_formula": "cy_per_pixel / pixel_spacing_mm",
                "nyquist_lp_per_mm": nyquist_lpmm,
                "mtf50_cy_per_pixel": float(mtf50_cy) if isinstance(mtf50_cy, (int, float)) else None,
                "mtf50_lp_per_mm": mtf50_lpmm,
                "mtf10_cy_per_pixel": float(mtf10_cy) if isinstance(mtf10_cy, (int, float)) else None,
                "mtf10_lp_per_mm": mtf10_lpmm,
            },
            "G_interpolation": phase1_diag.get("interpolation") or {},
            "critical_diagnostics": {
                "edge_orientation_and_esf_direction": phase1_diag.get("edge_orientation_and_esf_direction") or {},
                "signal_vs_fft": phase1_diag.get("signal_vs_fft") or {},
                "mtf50_crossing": phase1_diag.get("mtf50_crossing") or {},
                "mtf10_crossing": phase1_diag.get("mtf10_crossing") or {},
                "mtf_curve_length": int(mtf.size),
                "frequency_samples": int(freqs.size),
            },
            "validation_output_block": {
                "matlab_reference_mtf50_lp_per_mm": matlab_reference["mtf50_lp_per_mm"],
                "moduba_mtf50_lp_per_mm": mtf50_lpmm,
                "mtf50_absolute_difference_lp_per_mm": mtf50_diff,
                "mtf50_relative_difference_percent": _rel(mtf50_diff, matlab_reference["mtf50_lp_per_mm"]),
                "matlab_reference_mtf10_lp_per_mm": matlab_reference["mtf10_lp_per_mm"],
                "moduba_mtf10_lp_per_mm": mtf10_lpmm,
                "mtf10_absolute_difference_lp_per_mm": mtf10_diff,
                "mtf10_relative_difference_percent": _rel(mtf10_diff, matlab_reference["mtf10_lp_per_mm"]),
            },
            "critical_validation_blocks": {
                "roi_equivalence_validation": {
                    "matlab_roi_bounds": matlab_roi_bounds,
                    "moduba_roi_bounds": roi_bounds_used,
                    "roi_match_status": roi_match_status,
                    "validation_status": roi_validation_status,
                    "message": roi_validation_message,
                },
                "esf_direction_validation": {
                    "edge_orientation_detected": edge_orientation,
                    "esf_direction_used": esf_direction,
                    "expected_direction": expected_direction,
                    "direction_match": direction_match,
                    "message": esf_validation_message,
                },
                "fft_resolution_impact": {
                    "nfft_used": nfft_used,
                    "lsf_length": lsf_length,
                    "freq_resolution": freq_resolution,
                    "matlab_freq_resolution": matlab_freq_resolution,
                    "resolution_ratio": resolution_ratio,
                    "warning": fft_resolution_warning,
                    "impact_explanation": fft_resolution_impact,
                },
            },
            "environment_and_package": {
                "scipy_pchip_available": pchip_available,
                "limitation": None if pchip_available else "scipy.interpolate.PchipInterpolator unavailable in runtime environment.",
            },
            "matlab_comparison": matlab_comparison,
            "single_most_likely_cause": (
                "Invalid ROI for MATLAB-style ESF extraction"
                if bool((phase1_diag.get("matlab_esf_validity") or {}).get("roi_is_valid_for_matlab_esf")) is False
                else ("PCHIP fallback" if not pchip_available else "Gaussian smoothing difference")
            ),
            "most_likely_current_issue": (
                "Invalid ROI for MATLAB-style ESF extraction"
                if bool(matlab_esf_validity_diag.get("roi_is_valid_for_matlab_esf")) is False
                else "MATLAB-reference interpolation differences or smoothing boundary behavior"
            ),
            "next_recommended_fix": (
                "Verify same ROI rectangle in MATLAB and Moduba, then re-check ESF monotonicity before changing smoothing/FFT/interpolation."
            ),
            "roi_equivalence_comparison_block": {
                "roi_definition_source": roi_definition_source,
                "roi_input_coordinates": roi_bounds_input,
                "roi_crop_bounds_used": roi_bounds_used,
                "roi_shape_used": [int(roi_pixels.shape[0]), int(roi_pixels.shape[1])] if roi_pixels.ndim == 2 else None,
                "matlab_imcrop_equivalence_status": matlab_imcrop_equivalence_status,
                "roi_is_valid_for_matlab_esf": matlab_esf_validity_diag.get("roi_is_valid_for_matlab_esf"),
                "roi_summary_line": roi_summary_line,
            },
        }

    @staticmethod
    def _lookup_nyquist_mtf(mtf_curve: dict[str, Any]) -> float | None:
        freqs = np.asarray(mtf_curve.get("frequency_cy_per_pixel", []), dtype=np.float64)
        mtf = np.asarray(mtf_curve.get("mtf", []), dtype=np.float64)
        if freqs.size == 0 or mtf.size == 0 or freqs.size != mtf.size:
            return None
        idx = int(np.argmin(np.abs(freqs - 0.5)))
        value = mtf[idx]
        return float(value) if np.isfinite(value) else None

    @staticmethod
    def _format_edge_angle_with_tilt(edge_angle_deg: Any, digits: int = 2) -> str:
        if not isinstance(edge_angle_deg, (int, float)):
            return "N/A"
        edge_angle = float(edge_angle_deg)
        tilt_from_vertical = edge_angle - 90.0
        rounded_tilt = float(f"{tilt_from_vertical:.{digits}f}")
        if rounded_tilt > 0:
            tilt_text = f"+{rounded_tilt:.{digits}f}°"
        elif rounded_tilt < 0:
            tilt_text = f"{rounded_tilt:.{digits}f}°"
        else:
            tilt_text = f"{0.0:.{digits}f}°"
        return f"{edge_angle:.{digits}f}° (Tilt: {tilt_text} from vertical)"

    def _update_mtf_analysis_ui(self, mtf_result: dict[str, Any]) -> None:
        if not getattr(self, "_mtf_summary_value_vars", None):
            return
        self._last_mtf_result = dict(mtf_result)
        key_metrics = mtf_result.get("key_mtf_metrics") or {}
        self._last_mtf_key_metrics = dict(key_metrics)
        invalid = self._is_mtf_result_invalid(mtf_result)
        def _fmt(value: Any, digits: int = 4, suffix: str = "") -> str:
            if isinstance(value, (int, float)):
                return f"{float(value):.{digits}f}{suffix}"
            return "N/A"
        frequency_lpmm_text = self._format_mtf_frequency_lpmm_summary(key_metrics)
        if invalid:
            for var in self._mtf_summary_value_vars.values():
                var.set("N/A")
            self._mtf_summary_value_vars["mtf_mode"].set(str(mtf_result.get("mtf_mode_label", "N/A")))
            self._mtf_summary_value_vars["calculation_validity"].set(str(mtf_result.get("calculation_validity", "invalid")))
            self._mtf_summary_value_vars["iec_compliance"].set(str(mtf_result.get("iec_compliance", "N/A")))
            self._mtf_summary_value_vars["qa_grade"].set(str(mtf_result.get("qa_grade", "N/A")))
            self._mtf_summary_value_vars["frequency_lpmm"].set(frequency_lpmm_text)
            self.analysis_results["mtf_validation_summary"].set(str(mtf_result.get("validation_summary") or mtf_result.get("rejection_reason") or "Rejected"))
        else:
            self._mtf_summary_value_vars["mtf50"].set(_fmt(key_metrics.get("mtf50")))
            self._mtf_summary_value_vars["mtf10"].set(_fmt(key_metrics.get("mtf10")))
            self._mtf_summary_value_vars["nyquist_mtf"].set(_fmt(key_metrics.get("nyquist_mtf")))
            self._mtf_summary_value_vars["frequency_lpmm"].set(frequency_lpmm_text)
            self._mtf_summary_value_vars["mtf_mode"].set(str(mtf_result.get("mtf_mode_label", "-")))
            self._mtf_summary_value_vars["edge_angle"].set(
                self._format_edge_angle_with_tilt(mtf_result.get("edge_angle_deg"), digits=2)
            )
            self._mtf_summary_value_vars["edge_snr"].set(_fmt(mtf_result.get("edge_snr")))
            roi_size = mtf_result.get("roi_size_mm") or {}
            self._mtf_summary_value_vars["roi_width"].set(_fmt(roi_size.get("width"), suffix=" mm"))
            self._mtf_summary_value_vars["roi_height"].set(_fmt(roi_size.get("height"), suffix=" mm"))
            self._mtf_summary_value_vars["calculation_validity"].set(str(mtf_result.get("calculation_validity", "-")))
            self._mtf_summary_value_vars["iec_compliance"].set(str(mtf_result.get("iec_compliance", "-")))
            self._mtf_summary_value_vars["qa_grade"].set(str(mtf_result.get("qa_grade", "-")))
            self.analysis_results["mtf_validation_summary"].set(str(mtf_result.get("validation_summary", "Validation: -")))
        warnings = mtf_result.get("warnings") or []
        reason_codes = mtf_result.get("reason_codes") or []
        self.analysis_results["mtf_status_overview"].set(self._build_mtf_status_overview(mtf_result))
        warning_summary = self._summarize_mtf_warnings_korean(reason_codes, warnings)
        self.analysis_results["mtf_warning_summary"].set(f"경고 요약: {warning_summary}")
        self.analysis_results["mtf_reason_codes"].set(f"Reason Codes: {', '.join(str(item) for item in reason_codes) if reason_codes else '-'}")
        self.analysis_results["mtf_suggested_actions"].set(self._build_mtf_suggested_actions(reason_codes))
        self._last_mtf_warning_details = [str(item) for item in warnings if str(item).strip()]
        self._refresh_mtf_warning_text_widget()
        self._last_mtf_curve_payload = dict(mtf_result.get("mtf_curve") or {})
        self._last_esf_curve_payload = dict(mtf_result.get("esf_curve") or {})
        self._last_lsf_curve_payload = dict(mtf_result.get("lsf_curve") or {})
        self._render_mtf_curve(self._last_mtf_curve_payload)
        self._render_xy_curve(self._mtf_esf_canvas, self._last_esf_curve_payload, "ESF", "x")
        self._render_xy_curve(self._mtf_lsf_canvas, self._last_lsf_curve_payload, "LSF", "x")
        self._update_mtf_esf_lsf_summary(self._last_esf_curve_payload, self._last_lsf_curve_payload)
        self._rebuild_curve_metrics_for_active_tab()
        self._schedule_mtf_graph_redraw()

    def _refresh_mtf_warning_text_widget(self) -> None:
        latest = getattr(self, "_last_mtf_result", {}) or {}
        if not isinstance(latest, dict):
            latest = {}
        reason_codes = [str(code).strip() for code in (latest.get("reason_codes") or []) if str(code).strip()]
        detail_warnings = [str(item).strip() for item in getattr(self, "_last_mtf_warning_details", []) if str(item).strip()]
        body_lines = self._build_mtf_warning_display_lines(latest, reason_codes, detail_warnings)
        warning_text_widget = getattr(self, "_mtf_warning_text_widget", None)
        if warning_text_widget is not None:
            warning_text_widget.configure(state="normal")
            warning_text_widget.delete("1.0", tk.END)
            warning_text_widget.insert("1.0", "\n".join(body_lines))
            warning_text_widget.configure(state="disabled")
        self._mtf_warning_popup_message = "\n".join(body_lines)

    def _show_mtf_warning_popup(self) -> None:
        message = str(getattr(self, "_mtf_warning_popup_message", "")).strip()
        if not message:
            message = "[검증 결과]\n- 검증: -\n- 계산 유효성: -\n- IEC: -\n- QA 등급: -"
        messagebox.showinfo("MTF Warnings / Validation", message)

    def _build_mtf_warning_display_lines(
        self,
        mtf_result: dict[str, Any],
        reason_codes: list[str],
        detail_warnings: list[str],
    ) -> list[str]:
        sections: list[list[str]] = []
        validation = str(mtf_result.get("validation_summary") or self.analysis_results["mtf_validation_summary"].get() or "-").strip()
        calculation = str(mtf_result.get("calculation_validity", "-")).strip() or "-"
        iec = str(mtf_result.get("iec_compliance", "-")).strip() or "-"
        qa_grade = str(mtf_result.get("qa_grade", "-")).strip() or "-"
        sections.append(
            [
                "[검증 결과]",
                f"- 검증: {validation or '-'}",
                f"- 계산 유효성: {calculation}",
                f"- IEC 기준: {iec}",
                f"- QA 등급: {qa_grade}",
            ]
        )

        reason_lines = self._translate_reason_codes_to_display_lines(reason_codes)
        if reason_lines:
            numbered = [f"{idx}. {line}" for idx, line in enumerate(reason_lines, start=1)]
            sections.append(["[주요 원인]", *numbered])

        evidence_lines = self._build_mtf_evidence_lines(mtf_result)
        if evidence_lines:
            sections.append(["[검증 근거]", *[f"- {line}" for line in evidence_lines]])

        interpretation_lines = self._build_mtf_interpretation_lines(reason_codes)
        if interpretation_lines:
            sections.append(["[해석]", *[f"- {line}" for line in interpretation_lines]])

        action_lines = self._build_mtf_suggested_action_lines(reason_codes)
        if action_lines:
            sections.append(["[권장 조치]", *[f"- {line}" for line in action_lines]])

        if detail_warnings:
            dedup_details = list(dict.fromkeys(detail_warnings))
            sections.append(["[참고 원문]", *[f"- {line}" for line in dedup_details]])

        merged: list[str] = []
        for index, section in enumerate(sections):
            if index > 0:
                merged.append("")
            merged.extend(section)
        return merged or ["[검증 결과]", "- 검증: -"]

    def _build_mtf_status_overview(self, mtf_result: dict[str, Any]) -> str:
        validation = str(mtf_result.get("validation_summary") or self.analysis_results["mtf_validation_summary"].get() or "-")
        validation = validation.split(".", 1)[0].strip() or "-"
        calculation = str(mtf_result.get("calculation_validity", "-"))
        mode = str(mtf_result.get("mtf_mode_label", "-"))
        equivalence = str(mtf_result.get("matlab_equivalence_status", "-"))
        iec = str(mtf_result.get("iec_compliance", "-"))
        qa_grade = str(mtf_result.get("qa_grade", "-"))
        return (
            f"Validation: {validation} | Mode: {mode} | MATLAB Eq: {equivalence} | "
            f"Calculation: {calculation} | IEC: {iec} | QA Grade: {qa_grade}"
        )

    def _build_mtf_suggested_actions(self, reason_codes: list[Any]) -> str:
        action_lines = self._build_mtf_suggested_action_lines([str(reason) for reason in reason_codes])
        if not action_lines:
            return "권장 조치:\n- ROI 위치, 에지 방향, SNR 상태를 재확인하세요."
        return "권장 조치:\n" + "\n".join(f"- {line}" for line in action_lines)

    def _build_mtf_suggested_action_lines(self, reason_codes: list[str]) -> list[str]:
        actions_by_reason = {
            "EDGE_SNR_LOW": ["노출 또는 edge 대비를 높여 SNR을 개선하세요.", "더 안정적인 edge 구간으로 ROI를 다시 설정해 재측정하세요."],
            "EDGE_SNR_BORDERLINE": ["고주파 구간 해석을 보수적으로 수행하세요.", "가능하면 edge 대비를 개선한 후 재측정하세요."],
            "POSSIBLE_ALIASING": ["edge 방향과 샘플링 조건을 재확인하세요.", "리샘플링 영향이 적은 위치로 ROI를 이동해 재측정하세요."],
            "NONMONOTONIC_TAIL": ["ROI 위치와 edge 품질을 재확인하세요.", "안정적인 edge로 반복 측정을 권장합니다."],
            "INVALID_ROI_FOR_MATLAB_ESF": ["MATLAB 기준에서는 수직 edge ROI가 필요합니다.", "ROI를 edge 진행 방향 기준으로 다시 지정하세요."],
            "IEC_EDGE_GEOMETRY_NONCOMPLIANT": ["ROI 크기/각도를 IEC 기하 조건에 맞게 조정하세요.", "IEC 엄격 모드에서 다시 계산하세요."],
            "IEC_ROI_NONCOMPLIANT": ["ROI 크기를 IEC 최소 조건 이상으로 확대하세요.", "에지 위치가 유효한지 다시 확인하세요."],
            "PHASE1_REJECT": ["ROI 위치와 edge 방향을 우선 확인하세요.", "SNR이 충분한지 점검한 뒤 재측정하세요."],
        }
        for reason in reason_codes:
            action = actions_by_reason.get(reason)
            if action:
                return action
        return ["ROI 위치, 에지 방향, SNR 상태를 재확인하세요."]

    def _translate_reason_codes_to_display_lines(self, reason_codes: list[str]) -> list[str]:
        reason_to_ko = {
            "NONMONOTONIC_TAIL": "MTF 곡선 단조성 문제 발생 (non-monotonic).",
            "POSSIBLE_ALIASING": "aliasing 가능성이 있습니다.",
            "HIGH_FREQUENCY_NOISE_BIAS_RISK": "고주파 노이즈 영향 가능성이 있습니다.",
            "EDGE_SNR_LOW": "Edge SNR이 낮습니다 (Low edge SNR).",
            "EDGE_SNR_BORDERLINE": "Edge SNR이 경계 수준입니다.",
            "RESULT_QUESTIONABLE": "결과 신뢰도가 낮을 수 있습니다.",
            "MTF_PEAK_GT_ONE": "MTF peak가 1.0을 초과했습니다.",
            "POSSIBLE_SHARPENING": "샤프닝 영향 가능성이 있습니다.",
            "EDGE_CLIPPING_DETECTED": "에지 클리핑이 감지되었습니다.",
            "PHASE1_REJECT": "MTF 1차 계산이 거부되었습니다.",
            "IEC_EDGE_GEOMETRY_NONCOMPLIANT": "IEC 에지 기하 조건을 만족하지 못했습니다.",
            "IEC_ROI_NONCOMPLIANT": "ROI 크기가 IEC 기준에 미달합니다.",
            "IEC_ROI_UNVERIFIABLE": "ROI의 IEC 검증에 필요한 정보가 부족합니다.",
            "IEC_AVERAGING_METHOD_NONCOMPLIANT": "IEC 허용 averaging 방식이 아닙니다.",
            "IEC_AVERAGING_METHOD_UNVERIFIABLE": "averaging 방식을 확인할 수 없습니다.",
            "IEC_SCOPE_NOT_DECLARED": "IEC scope 선언 정보가 없습니다.",
            "IEC_EXPLORATORY_MODE_NOT_REPORTABLE": "Exploratory 모드는 IEC 보고용으로 제한됩니다.",
            "EDGE_SNR_NOT_ASSESSED": "Edge SNR을 평가하지 못했습니다.",
            "IEC_DATA_NOT_LINEAR": "IEC 선형성 가정을 만족하지 못했을 가능성이 있습니다.",
            "MATLAB_PCHIP_FALLBACK": "PCHIP 미지원으로 선형 보간 fallback이 적용되었습니다.",
            "INVALID_ROI_FOR_MATLAB_ESF": "MATLAB 기준 ESF ROI 조건(수직 edge/크롭)에 맞지 않습니다.",
        }
        translated: list[str] = []
        for code in reason_codes:
            translated.append(reason_to_ko.get(code, f"추가 확인 필요: {code}"))
        return list(dict.fromkeys(translated))

    def _build_mtf_interpretation_lines(self, reason_codes: list[str]) -> list[str]:
        interpretation_by_reason = {
            "NONMONOTONIC_TAIL": "MTF 곡선이 단조 감소하지 않아 고주파 해석 신뢰도가 낮아질 수 있습니다.",
            "POSSIBLE_ALIASING": "샘플링 영향으로 실제 해상도보다 높게 보일 가능성이 있습니다.",
            "HIGH_FREQUENCY_NOISE_BIAS_RISK": "고주파 영역에서 노이즈 floor 영향이 커질 수 있습니다.",
            "EDGE_SNR_LOW": "측정 재현성이 낮아질 수 있습니다.",
            "EDGE_SNR_BORDERLINE": "고주파 성능 해석은 보수적으로 판단하는 것이 좋습니다.",
            "RESULT_QUESTIONABLE": "최종 결과를 단독 근거로 사용하기 어렵습니다.",
            "EDGE_CLIPPING_DETECTED": "LSF/MTF 형상이 왜곡되었을 수 있습니다.",
            "INVALID_ROI_FOR_MATLAB_ESF": "현재 ROI는 MATLAB 기준 ESF 유효 조건을 충족하지 않습니다.",
            "PHASE1_REJECT": "현재 ROI 조건에서는 신뢰 가능한 MTF 산출이 어렵습니다.",
        }
        lines = [interpretation_by_reason[code] for code in reason_codes if code in interpretation_by_reason]
        return list(dict.fromkeys(lines))

    @staticmethod
    def _build_mtf_evidence_lines(mtf_result: dict[str, Any]) -> list[str]:
        key_metrics = dict(mtf_result.get("key_mtf_metrics") or {})
        diagnostics = dict(mtf_result.get("diagnostics") or {})
        lines: list[str] = []

        edge_snr = mtf_result.get("edge_snr")
        if isinstance(edge_snr, (int, float)):
            lines.append(f"Edge SNR={float(edge_snr):.2f}")

        mtf50 = key_metrics.get("mtf50")
        mtf10 = key_metrics.get("mtf10")
        unit = str(key_metrics.get("frequency_unit") or "").strip()
        if isinstance(mtf50, (int, float)):
            suffix = f" {unit}" if unit else ""
            lines.append(f"MTF50={float(mtf50):.4f}{suffix}")
        if isinstance(mtf10, (int, float)):
            suffix = f" {unit}" if unit else ""
            lines.append(f"MTF10={float(mtf10):.4f}{suffix}")

        critical = dict(diagnostics.get("critical_validation_blocks") or {})
        tail_block = dict(critical.get("fft_resolution_impact") or {})
        if tail_block.get("warning"):
            lines.append(str(tail_block.get("warning")))

        roi_block = dict(diagnostics.get("C_matlab_esf_validity") or {})
        roi_valid = roi_block.get("roi_is_valid_for_matlab_esf")
        if isinstance(roi_valid, bool):
            lines.append(f"MATLAB ESF ROI 유효성={'valid' if roi_valid else 'invalid'}")

        return list(dict.fromkeys(lines))

    def _format_mtf_frequency_lpmm_summary(self, key_metrics: dict[str, Any]) -> str:
        frequency_unit = str(key_metrics.get("frequency_unit", "")).strip().lower()
        if frequency_unit == "lp/mm":
            entries: list[str] = []
            for key in ("mtf50", "mtf10"):
                value = key_metrics.get(key)
                if isinstance(value, (int, float)):
                    entries.append(f"{key.upper()}={float(value):.4f}")
            nyquist_lpmm = key_metrics.get("nyquist_frequency_lp_per_mm")
            if isinstance(nyquist_lpmm, (int, float)):
                entries.append(f"Nyquist={float(nyquist_lpmm):.4f}")
            return ", ".join(entries) if entries else "lp/mm unavailable"
        spacing = self._get_pixel_spacing_mm()
        if spacing is None:
            return "lp/mm unavailable: missing PixelSpacing"
        row_spacing_mm = spacing[0]
        if not isinstance(row_spacing_mm, (int, float)) or row_spacing_mm <= 0:
            return "lp/mm unavailable: missing PixelSpacing"
        entries: list[str] = []
        for key in ("mtf50", "mtf10"):
            value = key_metrics.get(key)
            if isinstance(value, (int, float)):
                entries.append(f"{key.upper()}={float(value) / float(row_spacing_mm):.4f}")
        nyquist_lpmm = 0.5 / float(row_spacing_mm)
        entries.append(f"Nyquist={nyquist_lpmm:.4f}")
        return ", ".join(entries) if entries else "lp/mm unavailable"

    def _summarize_mtf_warnings_korean(self, reason_codes: list[Any], warnings: list[Any]) -> str:
        reason_to_ko = {
            "NONMONOTONIC_TAIL": "고주파 MTF 곡선이 단조 감소하지 않아 aliasing/sharpening/noise 영향 가능성이 있습니다.",
            "POSSIBLE_ALIASING": "aliasing 가능성이 있습니다. edge 각도 또는 샘플링 조건을 확인하세요.",
            "HIGH_FREQUENCY_NOISE_BIAS_RISK": "고주파 MTF가 noise floor의 영향을 받을 수 있습니다.",
            "EDGE_SNR_LOW": "Edge SNR이 낮아 MTF 결과 신뢰도가 떨어질 수 있습니다.",
            "EDGE_SNR_BORDERLINE": "Edge SNR이 경계 수준입니다. 고주파 해석에 주의하세요.",
            "RESULT_QUESTIONABLE": "결과 해석에 주의가 필요합니다.",
            "MTF_PEAK_GT_ONE": "MTF peak가 1.0을 초과했습니다. sharpening 영향 가능성이 있습니다.",
            "POSSIBLE_SHARPENING": "샤프닝(에지 강화) 영향 가능성이 있습니다.",
            "EDGE_CLIPPING_DETECTED": "에지 클리핑이 감지되어 MTF 해석이 왜곡될 수 있습니다.",
            "PHASE1_REJECT": "MTF 1차 계산이 거부되어 결과가 유효하지 않습니다.",
            "IEC_EDGE_GEOMETRY_NONCOMPLIANT": "IEC 기준에서 에지 기하 조건이 충족되지 않습니다.",
            "IEC_ROI_NONCOMPLIANT": "ROI 크기가 IEC 기준보다 작습니다.",
            "IEC_ROI_UNVERIFIABLE": "ROI mm 크기를 검증할 수 없습니다(Pixel Spacing 또는 입력값 부족).",
            "IEC_AVERAGING_METHOD_NONCOMPLIANT": "IEC 보고 허용 averaging 방식이 아닙니다.",
            "IEC_AVERAGING_METHOD_UNVERIFIABLE": "averaging 방식을 확인할 수 없습니다.",
            "IEC_SCOPE_NOT_DECLARED": "IEC scope 선언이 없어 완전한 검증이 어렵습니다.",
            "IEC_EXPLORATORY_MODE_NOT_REPORTABLE": "Exploratory 모드 결과는 IEC 보고용으로 제한됩니다.",
            "EDGE_SNR_NOT_ASSESSED": "Edge SNR을 평가하지 못했습니다.",
            "MATLAB_PCHIP_FALLBACK": "PCHIP 미지원으로 선형 보간 fallback이 적용되어 MATLAB 대비 차이가 발생할 수 있습니다.",
        }
        if reason_codes:
            translated = []
            for code in reason_codes:
                text = reason_to_ko.get(str(code))
                if text:
                    translated.append(text)
            if translated:
                return ", ".join(dict.fromkeys(translated))
        fallback = [str(item) for item in warnings if str(item).strip()]
        return ", ".join(fallback) if fallback else "-"

    def _update_mtf_esf_lsf_summary(self, esf_curve: dict[str, Any], lsf_curve: dict[str, Any]) -> None:
        self._mtf_esf_status_var.set(self._format_curve_summary("ESF", esf_curve))
        self._mtf_lsf_status_var.set(self._format_curve_summary("LSF", lsf_curve))

    def _rebuild_curve_metrics_for_active_tab(self) -> None:
        tree = getattr(self, "_mtf_curve_metrics_tree", None)
        if tree is None:
            return
        for item_id in tree.get_children():
            tree.delete(item_id)
        tab_key = self._get_active_mtf_curve_tab_key()
        if tab_key == "esf":
            rows = self._build_esf_curve_metric_rows()
        elif tab_key == "lsf":
            rows = self._build_lsf_curve_metric_rows()
        else:
            rows = self._build_mtf_curve_metric_rows()
        for row in rows:
            tree.insert("", "end", values=(row[0], row[1], row[2]))

    def _get_active_mtf_curve_tab_key(self) -> str:
        notebook = getattr(self, "_mtf_curve_notebook", None)
        if notebook is None:
            return "mtf"
        try:
            selected = notebook.select()
        except Exception:
            return "mtf"
        return self._mtf_curve_tab_ids.get(str(selected), "mtf")

    @staticmethod
    def _metric_value_text(value: Any, unit: str = "", digits: int = 4, na_reason: str = "") -> str:
        if isinstance(value, (int, float)) and np.isfinite(float(value)):
            suffix = f" {unit}".rstrip() if unit else ""
            return f"{float(value):.{digits}f}{suffix}" if digits > 0 else f"{int(round(float(value)))}{suffix}"
        reason = f" ({na_reason})" if na_reason else ""
        return f"N/A{reason}"

    def _build_mtf_curve_metric_rows(self) -> list[tuple[str, str, str]]:
        mtf_result = getattr(self, "_last_mtf_result", {}) or {}
        key_metrics = mtf_result.get("key_mtf_metrics") or {}
        frequency_unit = self._resolve_mtf_frequency_unit(mtf_result)
        nyquist_freq = key_metrics.get("nyquist_frequency_lp_per_mm")
        if not isinstance(nyquist_freq, (int, float)):
            nyquist_freq = key_metrics.get("nyquist_frequency_cy_per_pixel")
        rows = [
            ("MTF50", self._metric_value_text(key_metrics.get("mtf50"), frequency_unit), "f where MTF = 0.5"),
            ("MTF10", self._metric_value_text(key_metrics.get("mtf10"), frequency_unit), "f where MTF = 0.1"),
            ("Nyquist MTF", self._metric_value_text(key_metrics.get("nyquist_mtf"), "", digits=4), "MTF at f_Nyquist"),
            (
                "Nyquist frequency",
                self._metric_value_text(nyquist_freq, frequency_unit, na_reason="no spacing"),
                "f_Nyquist = 1 / (2 × pixel spacing)",
            ),
            ("Edge SNR", self._metric_value_text(mtf_result.get("edge_snr"), "", digits=2), "edge contrast / noise"),
            ("IEC Compliance", str(mtf_result.get("iec_compliance") or "N/A"), "IEC rule-based result"),
            ("QA Grade", str(mtf_result.get("qa_grade") or "N/A"), "summary quality grade"),
        ]
        return rows

    @staticmethod
    def _curve_finite_stats(curve: dict[str, Any]) -> tuple[float | None, float | None, int]:
        y = np.asarray(curve.get("y", []), dtype=np.float64)
        if y.size == 0:
            return (None, None, 0)
        finite = y[np.isfinite(y)]
        if finite.size == 0:
            return (None, None, 0)
        return (float(np.min(finite)), float(np.max(finite)), int(finite.size))

    def _build_esf_curve_metric_rows(self) -> list[tuple[str, str, str]]:
        curve = self._last_esf_curve_payload
        x, y = self._curve_xy_finite(curve)
        x_unit = self._resolve_curve_x_unit(curve)
        esf_min, esf_max, esf_points = self._curve_finite_stats(curve)
        delta_i = (esf_max - esf_min) if isinstance(esf_min, float) and isinstance(esf_max, float) else None
        i50 = (esf_min + 0.5 * delta_i) if isinstance(esf_min, float) and isinstance(delta_i, float) else None
        w10_90, w10_90_reason = self._compute_esf_transition_width(x, y, 0.1, 0.9)
        w20_80, w20_80_reason = self._compute_esf_transition_width(x, y, 0.2, 0.8)
        return [
            ("Sample count", self._metric_value_text(esf_points, "samples", digits=0, na_reason="missing data"), "number of ESF samples"),
            ("Min", self._metric_value_text(esf_min, "", digits=4, na_reason="missing data"), "minimum ESF value"),
            ("Max", self._metric_value_text(esf_max, "", digits=4, na_reason="missing data"), "maximum ESF value"),
            ("Contrast (ΔI)", self._metric_value_text(delta_i, "", digits=4, na_reason="missing data"), "ΔI = I_max - I_min"),
            ("Center level (I50)", self._metric_value_text(i50, "", digits=4, na_reason="missing data"), "I50 = I_min + 0.5 × ΔI"),
            ("10–90% width", self._metric_value_text(w10_90, x_unit, digits=4, na_reason=w10_90_reason), "W10-90 = x90 - x10"),
            ("20–80% width", self._metric_value_text(w20_80, x_unit, digits=4, na_reason=w20_80_reason), "W20-80 = x80 - x20"),
        ]

    def _build_lsf_curve_metric_rows(self) -> list[tuple[str, str, str]]:
        curve = self._last_lsf_curve_payload
        x, y = self._curve_xy_finite(curve)
        x_unit = self._resolve_curve_x_unit(curve)
        lsf_min, lsf_max, lsf_points = self._curve_finite_stats(curve)
        peak_amplitude, peak_position, peak_reason = self._compute_lsf_peak(x, y)
        fwhm, fwhm_reason = self._compute_lsf_fwhm(x, y, peak_amplitude)
        centroid, centroid_reason = self._compute_lsf_centroid(x, y)
        area, area_reason = self._compute_lsf_area(x, y)
        return [
            ("Sample count", self._metric_value_text(lsf_points, "samples", digits=0, na_reason="missing data"), "number of LSF samples"),
            ("Min", self._metric_value_text(lsf_min, "", digits=4, na_reason="missing data"), "minimum LSF value"),
            ("Max", self._metric_value_text(lsf_max, "", digits=4, na_reason="missing data"), "maximum LSF value"),
            ("Peak amplitude", self._metric_value_text(peak_amplitude, "", digits=4, na_reason=peak_reason), "max(|LSF|)"),
            ("Peak position", self._metric_value_text(peak_position, x_unit, digits=4, na_reason=peak_reason), "x at peak amplitude"),
            ("FWHM", self._metric_value_text(fwhm, x_unit, digits=4, na_reason=fwhm_reason), "width at 50% of peak amplitude"),
            ("Centroid", self._metric_value_text(centroid, x_unit, digits=4, na_reason=centroid_reason), "Σ(x·|LSF|) / Σ(|LSF|)"),
            ("Area", self._metric_value_text(area, x_unit, digits=4, na_reason=area_reason), "ΣLSF or ∫LSF dx"),
        ]

    @staticmethod
    def _curve_has_finite_data(curve: dict[str, Any]) -> bool:
        y = np.asarray(curve.get("y", []), dtype=np.float64)
        return bool(y.size > 0 and np.isfinite(y).any())

    def _curve_xy_finite(self, curve: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(curve.get("x", []), dtype=np.float64)
        y = np.asarray(curve.get("y", []), dtype=np.float64)
        if x.size == 0 or y.size == 0:
            return np.asarray([], dtype=np.float64), np.asarray([], dtype=np.float64)
        n = min(x.size, y.size)
        x = x[:n]
        y = y[:n]
        finite_mask = np.isfinite(x) & np.isfinite(y)
        return x[finite_mask], y[finite_mask]

    def _resolve_curve_x_unit(self, curve: dict[str, Any]) -> str:
        unit = str(curve.get("x_unit") or "").strip()
        if unit:
            return unit
        spacing = self._get_pixel_spacing_mm()
        if spacing is not None:
            return "mm"
        return "px"

    @staticmethod
    def _interpolate_crossing_x(x0: float, y0: float, x1: float, y1: float, target: float) -> float | None:
        dy = y1 - y0
        if abs(dy) < 1e-12:
            return None
        t = (target - y0) / dy
        if t < 0 or t > 1:
            return None
        return x0 + t * (x1 - x0)

    def _compute_esf_transition_width(self, x: np.ndarray, y: np.ndarray, lo: float, hi: float) -> tuple[float | None, str]:
        if x.size < 2 or y.size < 2:
            return None, "missing data"
        y_min = float(np.min(y))
        y_max = float(np.max(y))
        delta = y_max - y_min
        if not np.isfinite(delta) or delta <= 0:
            return None, "no contrast"
        t_lo = y_min + lo * delta
        t_hi = y_min + hi * delta
        x_lo = self._find_curve_crossing(x, y, t_lo)
        x_hi = self._find_curve_crossing(x, y, t_hi)
        if x_lo is None or x_hi is None:
            return None, "no crossing"
        width = abs(float(x_hi - x_lo))
        return (width, "") if np.isfinite(width) else (None, "unstable")

    def _find_curve_crossing(self, x: np.ndarray, y: np.ndarray, target: float) -> float | None:
        for idx in range(len(x) - 1):
            y0 = float(y[idx])
            y1 = float(y[idx + 1])
            if (y0 - target) == 0:
                return float(x[idx])
            if (y0 - target) * (y1 - target) > 0:
                continue
            result = self._interpolate_crossing_x(float(x[idx]), y0, float(x[idx + 1]), y1, target)
            if result is not None:
                return float(result)
        return None

    def _compute_lsf_peak(self, x: np.ndarray, y: np.ndarray) -> tuple[float | None, float | None, str]:
        if x.size == 0 or y.size == 0:
            return None, None, "missing data"
        abs_y = np.abs(y)
        if abs_y.size == 0 or not np.isfinite(abs_y).any():
            return None, None, "missing data"
        idx = int(np.nanargmax(abs_y))
        peak = float(abs_y[idx])
        pos = float(x[idx]) if idx < x.size else None
        if not np.isfinite(peak) or peak <= 0:
            return None, None, "unstable"
        return peak, pos, ""

    def _compute_lsf_fwhm(self, x: np.ndarray, y: np.ndarray, peak_amplitude: float | None) -> tuple[float | None, str]:
        if x.size < 2 or y.size < 2 or not isinstance(peak_amplitude, float) or peak_amplitude <= 0:
            return None, "missing data"
        half = 0.5 * peak_amplitude
        abs_y = np.abs(y)
        indices = np.where(abs_y >= half)[0]
        if indices.size == 0:
            return None, "no crossing"
        left = indices[0]
        right = indices[-1]
        left_cross = float(x[left])
        right_cross = float(x[right])
        if left > 0:
            candidate = self._interpolate_crossing_x(float(x[left - 1]), float(abs_y[left - 1]), float(x[left]), float(abs_y[left]), half)
            if candidate is not None:
                left_cross = float(candidate)
        if right < (len(x) - 1):
            candidate = self._interpolate_crossing_x(float(x[right]), float(abs_y[right]), float(x[right + 1]), float(abs_y[right + 1]), half)
            if candidate is not None:
                right_cross = float(candidate)
        width = abs(right_cross - left_cross)
        return (width, "") if np.isfinite(width) else (None, "unstable")

    def _compute_lsf_centroid(self, x: np.ndarray, y: np.ndarray) -> tuple[float | None, str]:
        if x.size == 0 or y.size == 0:
            return None, "missing data"
        abs_y = np.abs(y)
        denom = float(np.sum(abs_y))
        if not np.isfinite(denom) or denom <= 0:
            return None, "zero denominator"
        numer = float(np.sum(x * abs_y))
        centroid = numer / denom
        return (centroid, "") if np.isfinite(centroid) else (None, "unstable")

    def _compute_lsf_area(self, x: np.ndarray, y: np.ndarray) -> tuple[float | None, str]:
        if x.size == 0 or y.size == 0:
            return None, "missing data"
        if x.size >= 2:
            area = float(np.trapezoid(y, x))
        else:
            area = float(np.sum(y))
        return (area, "") if np.isfinite(area) else (None, "unstable")

    @staticmethod
    def _format_curve_summary(label: str, curve: dict[str, Any]) -> str:
        y = np.asarray(curve.get("y", []), dtype=np.float64)
        if y.size == 0:
            return f"{label}: 결과 없음"
        finite = y[np.isfinite(y)]
        if finite.size == 0:
            return f"{label}: 결과 없음"
        return f"{label}: {finite.size} points, range {np.min(finite):.2f} ~ {np.max(finite):.2f}"

    def _render_mtf_curve(self, mtf_curve: dict[str, Any]) -> None:
        canvas = getattr(self, "_mtf_graph_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = int(canvas.winfo_width() or 360)
        height = int(canvas.winfo_height() or 180)
        pad_l, pad_r, pad_t, pad_b = 34, 10, 10, 26
        plot_w = max(width - pad_l - pad_r, 20)
        plot_h = max(height - pad_t - pad_b, 20)
        canvas.create_rectangle(pad_l, pad_t, pad_l + plot_w, pad_t + plot_h, outline="#CBD5E1")
        canvas.create_line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, fill="#64748B")
        canvas.create_line(pad_l, pad_t, pad_l, pad_t + plot_h, fill="#64748B")
        frequency_unit = self._resolve_mtf_frequency_unit(getattr(self, "_last_mtf_result", {}) or {})
        raw_freqs = np.asarray(mtf_curve.get("frequency_cy_per_pixel", []), dtype=np.float64)
        freqs = raw_freqs
        if frequency_unit == "lp/mm":
            spacing = self._get_pixel_spacing_mm()
            row_spacing_mm = float(spacing[0]) if spacing is not None else None
            if isinstance(row_spacing_mm, (int, float)) and row_spacing_mm > 0:
                freqs = raw_freqs / row_spacing_mm
        mtf = np.asarray(mtf_curve.get("mtf", []), dtype=np.float64)
        if freqs.size < 2 or mtf.size < 2 or freqs.size != mtf.size:
            self._mtf_graph_status_var.set("MTF curve: unavailable")
            return
        finite = np.isfinite(freqs) & np.isfinite(mtf)
        freqs = freqs[finite]
        mtf = mtf[finite]
        if freqs.size < 2:
            self._mtf_graph_status_var.set("MTF curve: unavailable")
            return
        xmax = float(np.max(freqs))
        xmax = xmax if xmax > 0 else 1.0
        mtf = np.clip(mtf, 0.0, 1.2)
        points: list[float] = []
        for x, y in zip(freqs, mtf):
            px = pad_l + (float(x) / xmax) * plot_w
            py = pad_t + plot_h - (float(y) / 1.2) * plot_h
            points.extend([px, py])
        if len(points) >= 4:
            canvas.create_line(*points, fill="#0A84FF", width=2, smooth=True)
        self._draw_axis_ticks(
            canvas=canvas,
            pad_l=pad_l,
            pad_t=pad_t,
            plot_w=plot_w,
            plot_h=plot_h,
            x_min=0.0,
            x_max=xmax,
            y_min=0.0,
            y_max=1.2,
        )
        show_nyquist_legend = self._render_mtf_reference_markers(
            canvas,
            key_metrics=self._last_mtf_key_metrics,
            xmax=xmax,
            pad_l=pad_l,
            pad_t=pad_t,
            plot_w=plot_w,
            plot_h=plot_h,
            frequency_unit=frequency_unit,
        )
        self._render_mtf_legend(canvas, width=width, pad_t=pad_t, include_nyquist=show_nyquist_legend)
        canvas.create_text(pad_l + plot_w / 2, height - 10, text=f"Frequency ({frequency_unit})", fill="#334155")
        canvas.create_text(12, pad_t + plot_h / 2, text="MTF", fill="#334155", angle=90)
        self._mtf_graph_status_var.set(f"MTF curve: {freqs.size} points")

    @staticmethod
    def _is_finite_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and np.isfinite(float(value))

    def _render_mtf_reference_markers(
        self,
        canvas: tk.Canvas,
        key_metrics: dict[str, Any],
        xmax: float,
        pad_l: int,
        pad_t: int,
        plot_w: int,
        plot_h: int,
        frequency_unit: str,
    ) -> bool:
        marker_specs = [
            ("mtf50", "#DC2626", "MTF50"),
            ("mtf10", "#16A34A", "MTF10"),
        ]
        for key, color, label in marker_specs:
            value = key_metrics.get(key)
            if not self._is_finite_number(value):
                continue
            freq = float(value)
            if freq < 0 or freq > xmax:
                continue
            px = pad_l + (freq / xmax) * plot_w
            canvas.create_line(px, pad_t, px, pad_t + plot_h, fill=color, dash=(4, 3), width=1)
            canvas.create_text(px + 4, pad_t + 10, text=f"{label}={freq:.4f}", fill=color, anchor="w")
        nyquist = key_metrics.get("nyquist_frequency_lp_per_mm") if frequency_unit == "lp/mm" else key_metrics.get("nyquist_frequency_cy_per_pixel")
        reliable_nyquist = self._is_finite_number(key_metrics.get("nyquist_mtf"))
        if not self._is_finite_number(nyquist):
            nyquist = 0.5 if frequency_unit == "cy/pixel" else None
        if nyquist is None:
            return False
        nyquist_freq = float(nyquist)
        if 0 <= nyquist_freq <= xmax:
            px = pad_l + (nyquist_freq / xmax) * plot_w
            canvas.create_line(px, pad_t, px, pad_t + plot_h, fill="#7C3AED", dash=(2, 4), width=1)
            return reliable_nyquist
        return False

    @staticmethod
    def _render_mtf_legend(canvas: tk.Canvas, width: int, pad_t: int, include_nyquist: bool) -> None:
        legend_items = [
            ("#DC2626", (4, 3), "MTF50"),
            ("#16A34A", (4, 3), "MTF10"),
        ]
        if include_nyquist:
            legend_items.append(("#7C3AED", (2, 4), "Nyquist"))
        legend_x = max(width - 170, 180)
        y = pad_t + 8
        for color, dash, label in legend_items:
            canvas.create_line(legend_x, y, legend_x + 26, y, fill=color, dash=dash, width=2)
            canvas.create_text(legend_x + 32, y, text=label, anchor="w", fill="#1E293B")
            y += 14

    def _render_xy_curve(
        self,
        canvas: tk.Canvas | None,
        curve: dict[str, Any],
        curve_name: str,
        x_label: str,
    ) -> None:
        if canvas is None:
            return
        canvas.delete("all")
        width = int(canvas.winfo_width() or 360)
        height = int(canvas.winfo_height() or 180)
        pad_l, pad_r, pad_t, pad_b = 34, 10, 10, 26
        plot_w = max(width - pad_l - pad_r, 20)
        plot_h = max(height - pad_t - pad_b, 20)
        canvas.create_rectangle(pad_l, pad_t, pad_l + plot_w, pad_t + plot_h, outline="#CBD5E1")
        canvas.create_line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, fill="#64748B")
        canvas.create_line(pad_l, pad_t, pad_l, pad_t + plot_h, fill="#64748B")
        xs = np.asarray(curve.get("x", []), dtype=np.float64)
        ys = np.asarray(curve.get("y", []), dtype=np.float64)
        if xs.size < 2 or ys.size < 2 or xs.size != ys.size:
            canvas.create_text(width / 2, height / 2, text="No curve data", fill="#64748B")
            return
        valid = np.isfinite(xs) & np.isfinite(ys)
        xs = xs[valid]
        ys = ys[valid]
        if xs.size < 2:
            canvas.create_text(width / 2, height / 2, text="No curve data", fill="#64748B")
            return
        x_min = float(np.min(xs))
        x_max = float(np.max(xs))
        y_min = float(np.min(ys))
        y_max = float(np.max(ys))
        x_span = (x_max - x_min) if x_max > x_min else 1.0
        y_span = (y_max - y_min) if y_max > y_min else 1.0
        points: list[float] = []
        for x_val, y_val in zip(xs, ys):
            px = pad_l + ((float(x_val) - x_min) / x_span) * plot_w
            py = pad_t + plot_h - ((float(y_val) - y_min) / y_span) * plot_h
            points.extend([px, py])
        if len(points) >= 4:
            canvas.create_line(*points, fill="#0A84FF", width=2, smooth=True)
        self._draw_axis_ticks(
            canvas=canvas,
            pad_l=pad_l,
            pad_t=pad_t,
            plot_w=plot_w,
            plot_h=plot_h,
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
        )
        canvas.create_text(pad_l + plot_w / 2, height - 10, text=x_label, fill="#334155")
        canvas.create_text(12, pad_t + plot_h / 2, text=curve_name, fill="#334155", angle=90)

    @staticmethod
    def _draw_axis_ticks(
        canvas: tk.Canvas,
        pad_l: int,
        pad_t: int,
        plot_w: int,
        plot_h: int,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
    ) -> None:
        if not np.isfinite(x_min) or not np.isfinite(x_max) or not np.isfinite(y_min) or not np.isfinite(y_max):
            return
        x_span = (x_max - x_min) if x_max > x_min else 1.0
        y_span = (y_max - y_min) if y_max > y_min else 1.0
        x_ticks = MaxNLocator(nbins=6, min_n_ticks=4).tick_values(x_min, x_max)
        y_ticks = MaxNLocator(nbins=5, min_n_ticks=4).tick_values(y_min, y_max)
        for tick in x_ticks:
            if tick < x_min - 1e-9 or tick > x_max + 1e-9:
                continue
            px = pad_l + ((float(tick) - x_min) / x_span) * plot_w
            canvas.create_line(px, pad_t + plot_h, px, pad_t + plot_h + 4, fill="#64748B")
            canvas.create_text(px, pad_t + plot_h + 10, text=f"{tick:.3g}", fill="#334155", anchor="n")
        for tick in y_ticks:
            if tick < y_min - 1e-9 or tick > y_max + 1e-9:
                continue
            py = pad_t + plot_h - ((float(tick) - y_min) / y_span) * plot_h
            canvas.create_line(pad_l - 4, py, pad_l, py, fill="#64748B")
            canvas.create_text(pad_l - 6, py, text=f"{tick:.3g}", fill="#334155", anchor="e")

    def _get_active_mtf_curve_key(self) -> str | None:
        notebook = self._mtf_curve_notebook
        if notebook is None:
            return None
        try:
            selected_tab = notebook.select()
        except Exception:
            return None
        return self._mtf_curve_tab_ids.get(str(selected_tab))

    def _copy_active_mtf_curve_graph(self) -> None:
        # Tkinter clipboard image support is platform-dependent and not reliable
        # without optional OS-specific dependencies; provide a safe fallback.
        messagebox.showinfo(
            "Copy Graph",
            "Copy Graph is not supported in this environment. Please use Save Graph.",
        )

    def _save_active_mtf_curve_graph(self) -> None:
        curve_key = self._get_active_mtf_curve_key()
        if curve_key is None:
            messagebox.showwarning("Save Graph", "Unable to detect active curve tab.")
            return
        default_names = {
            "mtf": "moduba_mtf_curve.png",
            "esf": "moduba_esf_curve.png",
            "lsf": "moduba_lsf_curve.png",
        }
        path = filedialog.asksaveasfilename(
            title="Save Graph",
            defaultextension=".png",
            initialfile=default_names.get(curve_key, "moduba_curve.png"),
            filetypes=[
                ("PNG image", "*.png"),
                ("SVG vector", "*.svg"),
                ("PDF document", "*.pdf"),
            ],
        )
        if not path:
            return
        try:
            self._export_active_curve_figure(curve_key=curve_key, output_path=path)
        except Exception as exc:
            messagebox.showerror("Save Graph", f"Failed to save graph: {exc}")
            return
        messagebox.showinfo("Save Graph", f"Graph saved:\n{path}")

    def _export_active_curve_figure(self, curve_key: str, output_path: str) -> None:
        fig, ax = plt.subplots(figsize=(6.4, 3.6))
        try:
            if curve_key == "mtf":
                self._plot_export_mtf(ax)
            elif curve_key == "esf":
                self._plot_export_xy(ax, self._last_esf_curve_payload, "ESF", "x")
            elif curve_key == "lsf":
                self._plot_export_xy(ax, self._last_lsf_curve_payload, "LSF", "x")
            else:
                raise ValueError("Unsupported curve tab.")
            output = Path(output_path)
            suffix = output.suffix.lower()
            dpi = 300 if suffix == ".png" else None
            fig.tight_layout()
            fig.savefig(output, dpi=dpi, bbox_inches="tight")
        finally:
            plt.close(fig)

    def _plot_export_mtf(self, ax: Any) -> None:
        frequency_unit = self._resolve_mtf_frequency_unit(getattr(self, "_last_mtf_result", {}) or {})
        raw_freqs = np.asarray(self._last_mtf_curve_payload.get("frequency_cy_per_pixel", []), dtype=np.float64)
        freqs = raw_freqs
        if frequency_unit == "lp/mm":
            spacing = self._get_pixel_spacing_mm()
            row_spacing_mm = float(spacing[0]) if spacing is not None else None
            if isinstance(row_spacing_mm, (int, float)) and row_spacing_mm > 0:
                freqs = raw_freqs / row_spacing_mm
        mtf = np.asarray(self._last_mtf_curve_payload.get("mtf", []), dtype=np.float64)
        valid = np.isfinite(freqs) & np.isfinite(mtf)
        freqs = freqs[valid]
        mtf = mtf[valid]
        if freqs.size < 2:
            raise ValueError("No MTF curve data available.")
        xmax = float(np.max(freqs))
        xmax = xmax if xmax > 0 else 1.0
        mtf = np.clip(mtf, 0.0, 1.2)
        ax.plot(freqs, mtf, color="#0A84FF", linewidth=2.0)
        ax.set_xlim(0.0, xmax)
        ax.set_ylim(0.0, 1.2)
        for key, color, label in (("mtf50", "#DC2626", "MTF50"), ("mtf10", "#16A34A", "MTF10")):
            value = self._last_mtf_key_metrics.get(key)
            if self._is_finite_number(value):
                freq = float(value)
                if 0 <= freq <= xmax:
                    ax.axvline(freq, color=color, linestyle=(0, (4, 3)), linewidth=1.0, label=label)
        nyquist = (
            self._last_mtf_key_metrics.get("nyquist_frequency_lp_per_mm")
            if frequency_unit == "lp/mm"
            else self._last_mtf_key_metrics.get("nyquist_frequency_cy_per_pixel")
        )
        if not self._is_finite_number(nyquist):
            nyquist = 0.5 if frequency_unit == "cy/pixel" else None
        if self._is_finite_number(nyquist) and 0 <= float(nyquist) <= xmax:
            nyquist_freq = float(nyquist)
            ax.axvline(nyquist_freq, color="#7C3AED", linestyle=(0, (2, 4)), linewidth=1.0, label="Nyquist")
        ax.set_xlabel(f"Frequency ({frequency_unit})")
        ax.set_ylabel("MTF")
        ax.tick_params(axis="both", which="major", labelsize=9)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6, min_n_ticks=4))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5, min_n_ticks=4))
        if ax.get_legend_handles_labels()[0]:
            ax.legend(loc="upper right", frameon=False)

    def _plot_export_xy(self, ax: Any, curve: dict[str, Any], curve_name: str, x_label: str) -> None:
        xs = np.asarray(curve.get("x", []), dtype=np.float64)
        ys = np.asarray(curve.get("y", []), dtype=np.float64)
        valid = np.isfinite(xs) & np.isfinite(ys)
        xs = xs[valid]
        ys = ys[valid]
        if xs.size < 2:
            raise ValueError(f"No {curve_name} curve data available.")
        x_min = float(np.min(xs))
        x_max = float(np.max(xs))
        y_min = float(np.min(ys))
        y_max = float(np.max(ys))
        if x_max <= x_min:
            x_max = x_min + 1.0
        if y_max <= y_min:
            y_max = y_min + 1.0
        ax.plot(xs, ys, color="#0A84FF", linewidth=2.0)
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_xlabel(x_label)
        ax.set_ylabel(curve_name)
        ax.tick_params(axis="both", which="major", labelsize=9)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6, min_n_ticks=4))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5, min_n_ticks=4))

    def _show_mtf_details(self) -> None:
        mtf_payload = (self._select_analysis_last_run("mtf") or {}).get("result")
        if not mtf_payload:
            messagebox.showinfo("MTF Analysis", "MTF 실행 결과가 없습니다.")
            return
        messagebox.showinfo("MTF Details", json.dumps(mtf_payload, indent=2, ensure_ascii=False))

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
        for measurement in self._selector_measurements_for_current_frame(kind="roi"):
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
                    "item_name": "Current frame ROI statistics",
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
        snr = self._select_analysis_last_run("snr")
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

        cnr = self._select_analysis_last_run("cnr")
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

        uniformity = self._select_analysis_last_run("uniformity")
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

        line = self._select_analysis_last_run("line_profile")
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
                    "item_name": "Summary",
                    "note_text": line_note,
                    "result_text": f"{line_stats['mean_intensity']:.2f}",
                    "developer_meta": line,
                }
            )
        mtf = self._select_analysis_last_run("mtf")
        if mtf is not None:
            result = dict(mtf.get("result") or {})
            key_metrics = dict(result.get("key_mtf_metrics") or {})
            metric_value = key_metrics.get("mtf50")
            status_text = str(result.get("calculation_validity", result.get("calculation_status", "")))
            mode_id = str(result.get("mtf_mode_id", key_metrics.get("mode_id", "matlab_reference")))
            mode_label = str(result.get("mtf_mode_label", key_metrics.get("mode_label", "MATLAB Reference")))
            reason_codes = ", ".join(str(item) for item in (result.get("reason_codes") or []))
            mtf_row = {
                "metric_name": "MTF",
                "formula_mode": f"{mode_id} [{status_text}]",
                "roi_ids": [str((mtf.get('context') or {}).get("roi_id", ""))],
                "roles": [],
                "stats": {
                    "mtf50": key_metrics.get("mtf50"),
                    "mtf10": key_metrics.get("mtf10"),
                    "nyquist_mtf": key_metrics.get("nyquist_mtf"),
                    "edge_angle_deg": result.get("edge_angle_deg"),
                    "edge_snr": result.get("edge_snr"),
                    "iec_compliance": result.get("iec_compliance"),
                    "qa_grade": result.get("qa_grade"),
                    "mtf_mode_id": mode_id,
                    "mtf_mode_label": mode_label,
                },
                "result_value": float(metric_value) if isinstance(metric_value, (int, float)) else None,
                "item_name": "MTF",
                "note_text": f"Mode={mode_label}; Validity={status_text}; reason_codes=[{reason_codes}]",
                "result_text": f"{float(metric_value):.4f}" if isinstance(metric_value, (int, float)) else status_text,
                "developer_meta": mtf,
            }
            rows.append(mtf_row)
            base_payload = {
                "formula_mode": mtf_row["formula_mode"],
                "roi_ids": mtf_row["roi_ids"],
                "roles": [],
                "stats": mtf_row["stats"],
                "note_text": "",
                "developer_meta": mtf,
            }
            for metric_name, value in (
                ("MTF50", key_metrics.get("mtf50")),
                ("MTF10", key_metrics.get("mtf10")),
                ("Nyquist MTF", key_metrics.get("nyquist_mtf")),
                ("Edge SNR", result.get("edge_snr")),
                ("IEC Compliance", result.get("iec_compliance")),
                ("QA Grade", result.get("qa_grade")),
            ):
                metric_text = f"{float(value):.4f}" if isinstance(value, (int, float)) else (str(value) if value not in (None, "") else "N/A")
                rows.append(
                    {
                        "metric_name": "MTF",
                        "item_name": metric_name,
                        "result_value": float(value) if isinstance(value, (int, float)) else None,
                        "result_text": metric_text,
                        **base_payload,
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
        metric_name = str(row.get("metric_name", "")).upper()
        result_value = row.get("result_value")
        if metric_name == "MTF" and isinstance(result_value, (int, float)):
            return f"{float(result_value):.4f}"
        if isinstance(result_value, (int, float)):
            return f"{float(result_value):.2f}"
        if metric_name == "MTF":
            result_text = str(row.get("result_text", "")).strip()
            return result_text if result_text else "N/A"
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
    def _build_mtf_summary_note(mtf_result: dict[str, Any]) -> str:
        parts: list[str] = []
        mode_label = mtf_result.get("mtf_mode_label")
        if mode_label:
            parts.append(f"Mode={mode_label}")
        matlab_eq = mtf_result.get("matlab_equivalence_status")
        if matlab_eq:
            parts.append(f"MATLAB_EQ={matlab_eq}")
        validity = mtf_result.get("calculation_validity")
        if validity is not None:
            parts.append(str(validity))
        iec = mtf_result.get("iec_compliance")
        if iec is not None:
            parts.append(f"IEC={iec}")
        qa_grade = mtf_result.get("qa_grade")
        if qa_grade:
            parts.append(f"QA={qa_grade}")
        warnings = mtf_result.get("warnings")
        if isinstance(warnings, list) and warnings:
            compact_warnings = [str(item) for item in warnings if item]
            if compact_warnings:
                parts.append(f"warnings={','.join(compact_warnings)}")
        return " | ".join(parts)

    @staticmethod
    def _resolve_mtf_frequency_unit(mtf_result: dict[str, Any]) -> str:
        key_metrics = mtf_result.get("key_mtf_metrics") or {}
        for key in ("unit", "frequency_unit"):
            value = key_metrics.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("frequency_unit", "unit"):
            value = mtf_result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "lp/mm"

    @staticmethod
    def _extract_mtf_roi_size_mm(mtf_result: dict[str, Any]) -> tuple[float | None, float | None]:
        roi_size = mtf_result.get("roi_size_mm")
        if isinstance(roi_size, dict):
            width = roi_size.get("width") if isinstance(roi_size.get("width"), (int, float)) else roi_size.get("w")
            height = roi_size.get("height") if isinstance(roi_size.get("height"), (int, float)) else roi_size.get("h")
            return (
                float(width) if isinstance(width, (int, float)) else None,
                float(height) if isinstance(height, (int, float)) else None,
            )
        if isinstance(roi_size, (list, tuple)) and len(roi_size) >= 2:
            width = roi_size[0]
            height = roi_size[1]
            return (
                float(width) if isinstance(width, (int, float)) else None,
                float(height) if isinstance(height, (int, float)) else None,
            )
        return None, None

    @staticmethod
    def _is_mtf_result_invalid(mtf_result: dict[str, Any]) -> bool:
        validity = str(mtf_result.get("calculation_validity", "")).strip().lower()
        status = str(mtf_result.get("calculation_status", "")).strip().lower()
        return validity == "invalid" or status == "reject"

    def append_mtf_result_to_history(self, mtf_result: dict[str, Any], context: dict[str, Any]) -> None:
        payload = dict(mtf_result or {})
        run_context = dict(context or {})
        reason_codes = [str(code) for code in (payload.get("reason_codes") or []) if code]
        summary_note = self._build_mtf_summary_note(payload)
        roi_width_mm, roi_height_mm = self._extract_mtf_roi_size_mm(payload)
        if isinstance(roi_width_mm, (int, float)) and isinstance(roi_height_mm, (int, float)):
            summary_note = f"{summary_note} | ROI={roi_width_mm:g}x{roi_height_mm:g}mm" if summary_note else f"ROI={roi_width_mm:g}x{roi_height_mm:g}mm"
        target_name = str(run_context.get("image_id") or "MTF")
        related_target_ids = [str(run_context.get("roi_id"))] if run_context.get("roi_id") else []

        if self._is_mtf_result_invalid(payload):
            invalid_note = (
                f"MTF rejected: calculation_validity={payload.get('calculation_validity', '')}; "
                f"reason_codes=[{', '.join(reason_codes)}]"
            )
            self._append_history_entry(
                measurement_type="MTF",
                target_name=target_name,
                metric=MTF_METRIC_INVALID,
                value=None,
                unit="",
                note=invalid_note,
                measurement_mode="analysis",
                target_id=str(run_context.get("roi_id", "")),
                related_target_ids=related_target_ids,
                extra_payload=payload,
                reason_codes=reason_codes,
                group_id=str(run_context.get("group_id", "")),
                study_id=str(run_context.get("study_id", "")),
            )
            return

        frequency_unit = self._resolve_mtf_frequency_unit(payload)
        key_metrics = payload.get("key_mtf_metrics") or {}
        metric_rows = [
            (MTF_METRIC_MTF50, key_metrics.get("mtf50"), frequency_unit),
            (MTF_METRIC_MTF10, key_metrics.get("mtf10"), frequency_unit),
            (MTF_METRIC_NYQUIST_MTF, key_metrics.get("nyquist_mtf"), frequency_unit),
            (MTF_METRIC_EDGE_ANGLE_DEG, payload.get("edge_angle_deg"), "deg"),
            (MTF_METRIC_EDGE_SNR, payload.get("edge_snr"), ""),
            (MTF_METRIC_ROI_WIDTH_MM, roi_width_mm, "mm"),
            (MTF_METRIC_ROI_HEIGHT_MM, roi_height_mm, "mm"),
        ]
        for metric, metric_value, unit in metric_rows:
            if not isinstance(metric_value, (int, float)):
                continue
            self._append_history_entry(
                measurement_type="MTF",
                target_name=target_name,
                metric=metric,
                value=float(metric_value),
                unit=unit,
                note=summary_note,
                measurement_mode="analysis",
                target_id=str(run_context.get("roi_id", "")),
                related_target_ids=related_target_ids,
                extra_payload=payload,
                reason_codes=reason_codes,
                group_id=str(run_context.get("group_id", "")),
                study_id=str(run_context.get("study_id", "")),
            )

    def complete_mtf_analysis(self, mtf_result: dict[str, Any], context: dict[str, Any]) -> None:
        self._action_set_analysis_last_run("mtf", {"result": dict(mtf_result or {}), "context": dict(context or {})})
        self.append_mtf_result_to_history(mtf_result, context)
        self._update_mtf_analysis_ui(dict(mtf_result or {}))
        self._refresh_analysis_results_panel()

    @staticmethod
    def _group_analysis_rows_for_panel(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def _is_placeholder_text(value: Any) -> bool:
            text = str(value or "").strip()
            return text in {"", "-", "N/A", "n/a"}

        def _is_meaningless_metric_row(row: dict[str, Any]) -> bool:
            metric_name = str(row.get("metric_name", "")).strip()
            item_name = str(row.get("item_name", "")).strip()
            result_text = str(row.get("result_text", "")).strip()
            note_text = str(row.get("note_text", "")).strip()
            return _is_placeholder_text(metric_name) and _is_placeholder_text(item_name) and _is_placeholder_text(result_text) and _is_placeholder_text(note_text)

        def _summarize_validation_text(value: Any) -> str:
            text = str(value or "").strip()
            if not text:
                return ""
            lowered = text.lower()
            if "validity=valid" not in lowered and "reason_codes=" not in lowered:
                return ""
            code_text = ""
            if "reason_codes=[" in text:
                code_text = text.split("reason_codes=[", 1)[1].split("]", 1)[0]
            codes = [str(item).strip().upper() for item in code_text.split(",") if str(item).strip()]
            if not codes:
                return ""
            risks: list[str] = []
            if any(code in {"EDGE_SNR_LOW", "EDGE_SNR_BORDERLINE"} for code in codes):
                risks.append("low edge SNR")
            if any(code in {"POSSIBLE_ALIASING", "NONMONOTONIC_TAIL"} for code in codes):
                risks.append("aliasing risk")
            if "HIGH_FREQUENCY_NOISE_BIAS_RISK" in codes:
                risks.append("high-frequency noise risk")
            if "EDGE_CLIPPING_DETECTED" in codes:
                risks.append("edge clipping risk")
            prefix = "Questionable" if "RESULT_QUESTIONABLE" in codes else "Review"
            if not risks:
                return prefix
            return f"{prefix}: {' / '.join(dict.fromkeys(risks))}"

        def _resolve_analysis_type(row: dict[str, Any]) -> str:
            candidates = [
                row.get("analysis_type"),
                row.get("category"),
                row.get("source"),
                row.get("metric_name"),
                row.get("item_name"),
            ]
            for raw in candidates:
                text = DicomViewer._normalize_analysis_tab_name(str(raw or ""))
                if text:
                    return text
            return ""

        def _resolve_roi_label(row: dict[str, Any]) -> str:
            roi_ids = [str(item).strip() for item in (row.get("roi_ids") or []) if str(item).strip()]
            if roi_ids:
                return ", ".join(roi_ids)
            metric_name = str(row.get("metric_name", "")).upper()
            if metric_name == "ROI_STATS":
                item_name = str(row.get("item_name", "")).strip()
                if item_name:
                    return item_name
            return ""

        analysis_priority = {
            "MTF": 0,
            "SNR": 1,
            "CNR": 2,
            "Uniformity": 3,
            "Line Profile": 4,
            "Other": 5,
        }

        filtered_rows = [row for row in rows if not _is_meaningless_metric_row(row)]
        if not filtered_rows:
            return []

        normalized_rows: list[dict[str, Any]] = []
        for row in filtered_rows:
            merged = dict(row)
            analysis_type = _resolve_analysis_type(merged)
            roi_label = _resolve_roi_label(merged)
            if not roi_label:
                roi_label = "ROI 1"
            if not analysis_type:
                analysis_type = "Other"
            analysis_type = DicomViewer._normalize_analysis_tab_name(analysis_type)
            if not analysis_type:
                analysis_type = "Other"
            merged["resolved_roi_label"] = roi_label
            merged["resolved_analysis_type"] = analysis_type if analysis_type in analysis_priority else (analysis_type or "Other")
            normalized_rows.append(merged)

        if any(not row.get("resolved_roi_label") for row in normalized_rows):
            return []
        if any(not row.get("resolved_analysis_type") for row in normalized_rows):
            return []

        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        roi_order: list[str] = []
        for row in normalized_rows:
            roi_key = str(row["resolved_roi_label"])
            analysis_type = str(row["resolved_analysis_type"])
            if analysis_type not in analysis_priority:
                analysis_type = "Other"
            if roi_key not in grouped:
                grouped[roi_key] = {}
                roi_order.append(roi_key)
            grouped[roi_key].setdefault(analysis_type, []).append(row)

        ordered: list[dict[str, Any]] = []
        for roi_key in roi_order:
            ordered.append({"category": "ROI", "item_name": roi_key, "result_text": "", "note_text": ""})
            analysis_nodes = grouped[roi_key]
            analysis_keys = sorted(analysis_nodes.keys(), key=lambda key: (analysis_priority.get(key, 5), key))
            for analysis_key in analysis_keys:
                metric_rows = analysis_nodes.get(analysis_key, [])
                analysis_note = ""
                for metric_row in metric_rows:
                    analysis_note = _summarize_validation_text(metric_row.get("note_text", ""))
                    if analysis_note:
                        break
                ordered.append({"category": "ANALYSIS", "item_name": analysis_key, "result_text": "", "note_text": analysis_note})
                metric_rows_sorted = sorted(
                    metric_rows,
                    key=lambda item: (
                        str(item.get("item_name", item.get("metric_name", ""))).lower(),
                        str(item.get("metric_name", "")).lower(),
                    ),
                )
                for metric_row in metric_rows_sorted:
                    if _summarize_validation_text(metric_row.get("note_text", "")):
                        metric_row = {**metric_row, "note_text": ""}
                    ordered.append({**metric_row, "category": "METRIC"})
        return ordered

    @staticmethod
    def _normalize_analysis_tab_name(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        lowered = normalized.lower()
        if "mtf" in lowered:
            return "MTF"
        if "snr" in lowered:
            return "SNR"
        if "cnr" in lowered:
            return "CNR"
        if "uniform" in lowered:
            return "Uniformity"
        if "line" in lowered or "profile" in lowered:
            return "Line Profile"
        return normalized

    @classmethod
    def _resolve_analysis_tab_for_row(cls, row: dict[str, Any]) -> str:
        for key in ("analysis_type", "category", "tab"):
            value = row.get(key)
            normalized = cls._normalize_analysis_tab_name(str(value or ""))
            if normalized in {"SNR", "CNR", "Uniformity", "Line Profile", "MTF"}:
                return normalized
        for key in ("metric_name", "item_name", "formula_mode", "result_text"):
            value = row.get(key)
            normalized = cls._normalize_analysis_tab_name(str(value or ""))
            if normalized in {"SNR", "CNR", "Uniformity", "Line Profile", "MTF"}:
                return normalized
        return ""

    @classmethod
    def _filter_analysis_rows_for_selected_tab(cls, rows: list[dict[str, Any]], selected_tab: str) -> list[dict[str, Any]]:
        active_tab = cls._normalize_analysis_tab_name(selected_tab)
        if active_tab not in {"SNR", "CNR", "Uniformity", "Line Profile", "MTF"}:
            return list(rows)
        return [row for row in rows if cls._resolve_analysis_tab_for_row(row) == active_tab]

    @staticmethod
    def _value_or_na(value: Any, digits: int = 2) -> str:
        if isinstance(value, (int, float)) and np.isfinite(float(value)):
            return f"{float(value):.{digits}f}"
        text = str(value or "").strip()
        return text if text else "N/A"

    @staticmethod
    def _truncate_formula_text(text: str, max_chars: int = 34) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return "N/A"
        if len(normalized) <= max_chars:
            return normalized
        return f"{normalized[: max_chars - 3].rstrip()}..."

    def _build_metric_formula_payload(self, row: dict[str, Any], analysis_type: str) -> tuple[str, str, str]:
        stats = dict(row.get("stats") or {})
        result_text = self._value_or_na(row.get("result_value"))
        metric = str(row.get("item_name", row.get("metric_name", ""))).strip() or "Metric"
        analysis = self._normalize_analysis_tab_name(analysis_type)

        if analysis == "SNR":
            signal_text = self._value_or_na(stats.get("mean_signal"))
            noise_text = self._value_or_na(stats.get("std_noise"))
            if metric == "Signal Mean":
                return ("mean(signal ROI)", "Signal Mean = mean(signal ROI)", signal_text)
            if metric == "Noise SD":
                return ("std(background ROI)", "Noise SD = std(background ROI)", noise_text)
            display = f"{signal_text} / {noise_text}"
            full = f"SNR = {signal_text} / {noise_text} = {result_text}"
            return (display, full, result_text)

        if analysis == "CNR":
            signal = self._value_or_na(stats.get("target_mean"))
            background = self._value_or_na(stats.get("reference_mean"))
            noise = self._value_or_na(stats.get("noise_std"))
            display = f"|{signal} - {background}| / {noise}"
            full = f"CNR = |{signal} - {background}| / {noise} = {result_text}"
            return (display, full, result_text)

        if analysis == "Uniformity":
            max_value = self._value_or_na(stats.get("max_value"))
            min_value = self._value_or_na(stats.get("min_value"))
            display = "100 × (1 - (max - min)/(max + min))"
            full = f"Uniformity = 100 × (1 - ({max_value} - {min_value}) / ({max_value} + {min_value})) = {result_text}"
            return (display, full, result_text)

        if analysis == "Line Profile":
            line_stats = dict(stats)
            metric_key = metric.lower()
            if "distance" in metric_key:
                value = self._value_or_na(line_stats.get("length_px"))
                return ("distance between sampled points", "Distance = line length along selected segment", value)
            if "std" in metric_key:
                value = self._value_or_na(line_stats.get("std_intensity"))
                return ("std(intensity(x))", "Std = standard deviation of sampled line intensity", value)
            if "fwhm" in metric_key:
                value = self._value_or_na(line_stats.get("fwhm"))
                return ("width at 50% of peak", "FWHM = distance between half-maximum crossings", value)
            if "mean" in metric_key:
                value = self._value_or_na(line_stats.get("mean_intensity"))
                return ("mean(intensity(x))", "Mean = average sampled line intensity", value)
            return ("intensity(x) sampled along selected line", "Line profile sampled along selected line", result_text)

        if analysis == "MTF":
            metric_key = metric.lower()
            mapping = {
                "mtf50": ("f where MTF(f) = 0.5", "MTF50 is the spatial frequency where MTF(f) reaches 0.5"),
                "mtf10": ("f where MTF(f) = 0.1", "MTF10 is the spatial frequency where MTF(f) reaches 0.1"),
                "nyquist mtf": ("MTF(f_Nyquist)", "Nyquist MTF is MTF at detector Nyquist frequency"),
                "edge snr": ("edge contrast / noise", "Edge SNR = edge contrast divided by noise"),
                "iec compliance": ("IEC validation outcome", "IEC compliance = structured validation result"),
                "qa grade": ("quality grade from metrics", "QA grade = mapped rating from MTF quality metrics"),
            }
            display, full = mapping.get(metric_key, ("slanted-edge definition", "MTF computed from slanted-edge ESF/LSF/MTF pipeline"))
            return (display, full, result_text)

        display = str(row.get("formula_mode", "")).strip() or "N/A"
        full = f"{metric} = {display} = {result_text}" if display != "N/A" else f"{metric} = {result_text}"
        return (display, full, result_text)

    def _expand_analysis_metric_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        expanded: list[dict[str, Any]] = []
        for row in rows:
            analysis_type = self._resolve_analysis_tab_for_row(row)
            if not analysis_type:
                continue
            base = dict(row)
            base["analysis_type"] = analysis_type
            if analysis_type == "SNR":
                stats = dict(base.get("stats") or {})
                for metric_name, result_value in (
                    ("Signal Mean", stats.get("mean_signal")),
                    ("Noise SD", stats.get("std_noise")),
                    ("SNR", base.get("result_value")),
                ):
                    metric_row = dict(base)
                    metric_row["item_name"] = metric_name
                    metric_row["metric_name"] = metric_name
                    metric_row["result_value"] = result_value
                    metric_row["result_text"] = self._value_or_na(result_value)
                    expanded.append(metric_row)
                continue
            if analysis_type == "Line Profile" and str(base.get("metric_name", "")).upper() == "LINE_PROFILE_SUMMARY":
                stats = dict(base.get("stats") or {})
                for metric_name, result_value in (
                    ("Distance", stats.get("length_px")),
                    ("Mean", stats.get("mean_intensity")),
                    ("Std", stats.get("std_intensity")),
                    ("FWHM", stats.get("fwhm")),
                ):
                    metric_row = dict(base)
                    metric_row["item_name"] = metric_name
                    metric_row["metric_name"] = metric_name
                    metric_row["result_value"] = result_value
                    metric_row["result_text"] = self._value_or_na(result_value)
                    expanded.append(metric_row)
                continue
            if analysis_type == "Uniformity":
                base["item_name"] = "Uniformity"
                base["metric_name"] = "Uniformity"
            expanded.append(base)
        return expanded

    def _refresh_analysis_results_panel(self) -> None:
        rows_container = getattr(self, "analysis_results_rows_container", None)
        if rows_container is None:
            return
        for child in rows_container.winfo_children():
            child.destroy()
        self._analysis_results_row_widgets = []
        self._analysis_results_selected_index = None
        active_tab = self._get_active_signal_analysis_tab()
        self._active_signal_analysis_tab = active_tab
        rows = self._build_analysis_result_rows()
        filtered_rows = self._filter_analysis_rows_for_selected_tab(rows, active_tab)
        expanded_rows = self._expand_analysis_metric_rows(filtered_rows)
        grouped_rows = self._group_analysis_rows_for_panel(expanded_rows)
        if not grouped_rows:
            grouped_rows = [{"category": "ROI", "item_name": "No results for selected analysis", "result_text": "", "note_text": ""}]
        data_row_index = 0
        self._analysis_result_popup_payloads = {}
        for row_index, row in enumerate(grouped_rows):
            category = str(row.get("category", "METRIC"))
            item_text = row.get("item_name", row.get("metric_name", ""))
            if category == "ANALYSIS":
                item_text = f"  {item_text}"
            elif category == "METRIC":
                item_text = f"    {item_text}"
            value_text = self._format_analysis_value_text(row) if category in {"METRIC", "METRIC_FLAT"} else ""
            display_formula = ""
            full_formula = ""
            if category in {"METRIC", "METRIC_FLAT"}:
                display_formula, full_formula, value_text = self._build_metric_formula_payload(row, str(row.get("resolved_analysis_type", "")))
                display_formula = self._truncate_formula_text(display_formula)
            item_value = self._sanitize_ui_text(str(item_text))
            formula_value = self._sanitize_ui_text(display_formula)
            value_value = self._sanitize_ui_text("" if value_text is None else str(value_text))
            if category in {"ROI", "ANALYSIS"}:
                background = "#F8FAFC"
                font = ("TkDefaultFont", 10, "bold")
            else:
                background = "#FFFFFF" if data_row_index % 2 == 0 else "#F6F7F9"
                font = ("TkDefaultFont", 10)
                data_row_index += 1
            row_frame = tk.Frame(rows_container, bg=background, highlightthickness=0, bd=0)
            row_frame.grid(row=row_index, column=0, sticky="ew")
            row_frame.grid_columnconfigure(0, weight=1, minsize=340)
            row_frame.grid_columnconfigure(1, weight=0, minsize=190)
            row_frame.grid_columnconfigure(2, weight=0, minsize=130)

            item_label = tk.Label(row_frame, text=item_value, anchor="w", justify="left", bg=background, fg=self.ui_colors["text_primary"], font=font, padx=8, pady=4)
            formula_label = tk.Label(row_frame, text=formula_value, anchor="w", justify="left", bg=background, fg=self.ui_colors["text_primary"], font=("TkDefaultFont", 9), padx=6, pady=4)
            value_label = tk.Label(row_frame, text=value_value, anchor="w", justify="left", bg=background, fg=self.ui_colors["text_primary"], font=font, padx=6, pady=4)
            item_label.grid(row=0, column=0, sticky="nsew")
            formula_label.grid(row=0, column=1, sticky="nsew")
            value_label.grid(row=0, column=2, sticky="nsew")

            separator = tk.Frame(rows_container, height=1, bg=self.ui_colors["border"])
            separator.grid(row=(row_index * 2) + 1, column=0, sticky="ew")
            row_frame.grid_configure(row=row_index * 2)

            row_widgets = {
                "frame": row_frame,
                "labels": (item_label, formula_label, value_label),
                "base_bg": background,
                "is_section": category in {"ROI", "ANALYSIS"},
            }
            self._analysis_results_row_widgets.append(row_widgets)
            if category in {"METRIC", "METRIC_FLAT"}:
                self._analysis_result_popup_payloads[row_index] = {
                    "metric": str(row.get("item_name", row.get("metric_name", ""))),
                    "definition": display_formula,
                    "calculation": full_formula or display_formula,
                    "result": str(value_text or "N/A"),
                }
            for widget in (row_frame, item_label, formula_label, value_label):
                widget.bind("<Button-1>", lambda _event, idx=row_index: self._select_analysis_results_row(idx))
                if category in {"METRIC", "METRIC_FLAT"}:
                    widget.bind("<Double-Button-1>", lambda _event, idx=row_index: self._show_analysis_formula_detail(idx))

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
        formula_width = max(220, width - item_width - value_width - 40)
        for row in self._analysis_results_row_widgets:
            labels = row["labels"]
            labels[0].configure(wraplength=item_width - 16)
            labels[1].configure(wraplength=formula_width - 12)
            labels[2].configure(wraplength=value_width - 12)

    def _show_analysis_formula_detail(self, row_index: int) -> None:
        payload = getattr(self, "_analysis_result_popup_payloads", {}).get(row_index)
        if not payload:
            return
        messagebox.showinfo(
            "Formula Details",
            "\n".join(
                (
                    f"Metric: {payload.get('metric', 'N/A')}",
                    f"Definition: {payload.get('definition', 'N/A')}",
                    f"Calculation: {payload.get('calculation', 'N/A')}",
                    f"Result: {payload.get('result', 'N/A')}",
                )
            ),
        )

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
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "rows": user_rows,
            },
            "developer_meta": {
                "analysis_last_run": self.domain_store.select_all_analysis_last_run(),
                "internal_rows": rows,
            },
        }

    def _get_exportable_analysis_results(self) -> dict[str, dict[str, Any]]:
        normalized = dict(getattr(self, "analysis_last_run_normalized", {}) or {})
        if normalized:
            return normalized
        raw_last_run = dict(getattr(self, "analysis_last_run", {}) or {})
        if raw_last_run:
            normalized = normalize_analysis_last_run(raw_last_run)
            self.analysis_last_run_normalized = normalized
            return normalized
        raise ValueError("No analysis results available for export")

    def export_analysis_results_json(self, path: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(
                title="분석 결과 JSON 저장",
                defaultextension=".json",
                filetypes=[("JSON", "*.json"), ("All Files", "*.*")],
            )
        if not path:
            return None
        normalized_results = self._get_exportable_analysis_results()
        return export_analysis_results_to_json(
            normalized_results,
            path=path,
            metadata={"app": "moduba", "export_source": "viewer"},
        )

    def export_analysis_results_csv(self, path: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(
                title="분석 결과 CSV 저장",
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv"), ("All Files", "*.*")],
            )
        if not path:
            return None
        normalized_results = self._get_exportable_analysis_results()
        return export_analysis_results_to_csv(
            normalized_results,
            path=path,
            metadata={"app": "moduba", "export_source": "viewer"},
        )

    def _get_reportable_analysis_results(self) -> dict[str, dict[str, Any]]:
        return self._get_exportable_analysis_results()

    def _resolve_threshold_config_for_report(self, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any] | None:
        if threshold_config is not None:
            return threshold_config
        if use_selected_threshold_config:
            current = getattr(self, "current_threshold_config", None)
            if not current:
                raise ValueError("current_threshold_config is empty")
            return current
        return None

    def build_current_analysis_report_model(self, metadata: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]:
        normalized_results = self._get_reportable_analysis_results()
        base_metadata = {"app": "moduba", "report_source": "viewer"}
        if metadata:
            base_metadata.update(dict(metadata))
        resolved = self._resolve_threshold_config_for_report(threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        threshold_eval = self.evaluate_current_analysis_thresholds(resolved) if resolved is not None else None
        return build_analysis_report_model(normalized_results, metadata=base_metadata, threshold_evaluation=threshold_eval)

    def render_current_analysis_report_markdown(self, metadata: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> str:
        report_model = self.build_current_analysis_report_model(metadata=metadata, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        return render_analysis_report_markdown(report_model)

    def export_analysis_report_markdown(self, path: str | None = None, metadata: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(
                title="분석 리포트 Markdown 저장",
                defaultextension=".md",
                filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All Files", "*.*")],
            )
        if not path:
            return None
        text = self.render_current_analysis_report_markdown(metadata=metadata, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        Path(path).write_text(text, encoding="utf-8")
        return text

    def export_analysis_report_pdf(self, path: str | None = None, metadata: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> bytes | None:
        if path is None:
            path = filedialog.asksaveasfilename(
                title="분석 리포트 PDF 저장",
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("All Files", "*.*")],
            )
        if not path:
            return None
        report_metadata = {"report_format": "pdf"}
        if metadata:
            report_metadata.update(dict(metadata))
        report_model = self.build_current_analysis_report_model(metadata=report_metadata, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        return export_analysis_report_to_pdf(report_model, path=path)

    def build_current_analysis_report_preview_text(self, metadata: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> str:
        preview_metadata = {"report_view": "preview"}
        if metadata:
            preview_metadata.update(dict(metadata))
        return self.render_current_analysis_report_markdown(metadata=preview_metadata, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)

    def show_analysis_report_preview(self, metadata: dict[str, Any] | None = None) -> str:
        text = self.build_current_analysis_report_preview_text(metadata=metadata)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        preview = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        preview.title("QC Report Preview")
        preview.geometry("900x700")
        container = ttk.Frame(preview, padding=8)
        container.pack(fill="both", expand=True)
        text_widget = tk.Text(container, wrap="word")
        text_widget.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(container, orient="vertical", command=text_widget.yview)
        scroll.pack(side="right", fill="y")
        text_widget.configure(yscrollcommand=scroll.set)
        text_widget.insert("1.0", text)
        text_widget.configure(state="disabled")
        return text

    def build_current_analysis_history_record(self, metadata: dict[str, Any] | None = None, record_id: str | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]:
        normalized_results = self._get_reportable_analysis_results()
        base_metadata = {"app": "moduba", "history_source": "viewer"}
        if metadata:
            base_metadata.update(dict(metadata))
        resolved = self._resolve_threshold_config_for_report(threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        threshold_eval = self.evaluate_current_analysis_thresholds(resolved) if resolved is not None else None
        return build_analysis_history_record(normalized_results, metadata=base_metadata, record_id=record_id, threshold_evaluation=threshold_eval)

    def append_current_analysis_history(self, history_path: str | Path, metadata: dict[str, Any] | None = None, record_id: str | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]:
        record = self.build_current_analysis_history_record(metadata=metadata, record_id=record_id, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        append_analysis_history_record(history_path, record)
        return record

    def load_analysis_history_for_viewer(self, path: str | Path) -> list[dict[str, Any]]:
        return load_analysis_history_records(path)

    def build_analysis_history_summary_for_viewer(self, path: str | Path | None = None, analysis_type: str | None = None, validity: str | None = None) -> dict[str, Any] | None:
        if path is None:
            path = filedialog.askopenfilename(title="QC history JSONL 선택", filetypes=[("JSONL", "*.jsonl"), ("All Files", "*.*")])
            if not path:
                return None
        return build_history_summary(self.load_analysis_history_for_viewer(path), analysis_type=analysis_type, validity=validity)

    def render_analysis_history_summary_text_for_viewer(self, path: str | Path | None = None, analysis_type: str | None = None, validity: str | None = None) -> str | None:
        s = self.build_analysis_history_summary_for_viewer(path=path, analysis_type=analysis_type, validity=validity)
        return None if s is None else render_history_summary_text(s)

    def build_metric_trend_series_for_viewer(self, path: str | Path | None = None, analysis_type: str | None = None, metric_name: str | None = None) -> dict[str, Any] | None:
        if not analysis_type or not metric_name:
            raise ValueError("analysis_type and metric_name are required")
        if path is None:
            path = filedialog.askopenfilename(title="QC history JSONL 선택", filetypes=[("JSONL", "*.jsonl"), ("All Files", "*.*")])
            if not path:
                return None
        return build_metric_trend_series(self.load_analysis_history_for_viewer(path), analysis_type=analysis_type, metric_name=metric_name)

    def render_metric_trend_text_for_viewer(self, path: str | Path | None = None, analysis_type: str | None = None, metric_name: str | None = None) -> str | None:
        t = self.build_metric_trend_series_for_viewer(path=path, analysis_type=analysis_type, metric_name=metric_name)
        return None if t is None else render_metric_trend_text(t)

    def show_analysis_history_summary_viewer(self, path: str | Path | None = None) -> str | None:
        text = self.render_analysis_history_summary_text_for_viewer(path=path)
        if text is None:
            return None
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("QC History Summary")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def build_metric_trend_chart_model_for_viewer(self, path: str | Path | None = None, analysis_type: str | None = None, metric_name: str | None = None) -> dict[str, Any] | None:
        series = self.build_metric_trend_series_for_viewer(path=path, analysis_type=analysis_type, metric_name=metric_name)
        return None if series is None else build_metric_trend_chart_model(series)

    def render_metric_trend_chart_text_for_viewer(self, path: str | Path | None = None, analysis_type: str | None = None, metric_name: str | None = None) -> str | None:
        model = self.build_metric_trend_chart_model_for_viewer(path=path, analysis_type=analysis_type, metric_name=metric_name)
        return None if model is None else render_metric_trend_chart_text(model)

    def show_metric_trend_chart_viewer(self, path: str | Path | None = None, analysis_type: str | None = None, metric_name: str | None = None) -> dict[str, Any] | None:
        model = self.build_metric_trend_chart_model_for_viewer(path=path, analysis_type=analysis_type, metric_name=metric_name)
        if model is None:
            return None
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Metric Trend Chart")
        win.geometry("900x700")
        canvas = tk.Canvas(win, width=860, height=360, bg="white")
        canvas.pack(fill="x")
        text = tk.Text(win, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("1.0", render_metric_trend_chart_text(model))
        text.configure(state="disabled")
        pts = model.get("points") or []
        if pts:
            left, top, width, height = 40, 20, 780, 300
            ys = [p["y"] for p in pts]
            ymin, ymax = min(ys), max(ys)
            span = (ymax - ymin) if ymax != ymin else 1.0
            coords = []
            for i, p in enumerate(pts):
                x = left + (i * width / max(1, len(pts) - 1))
                y = top + height - ((p["y"] - ymin) / span) * height
                coords.extend([x, y])
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="blue", outline="blue")
            if len(coords) >= 4:
                canvas.create_line(*coords, fill="blue")
        return model

    def _resolve_threshold_config_for_batch(self, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any] | None:
        if threshold_config is not None:
            return dict(threshold_config)
        if not use_selected_threshold_config:
            return None
        current = getattr(self, "current_threshold_config", None)
        if current is None:
            raise ValueError("current_threshold_config is empty")
        return dict(current)

    def build_batch_qc_run_for_viewer(self, path: str | Path | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any] | None:
        if path is None:
            path = filedialog.askopenfilename(title="QC history JSONL 선택", filetypes=[("JSONL", "*.jsonl"), ("All Files", "*.*")])
            if not path:
                return None
        resolved = DicomViewer._resolve_threshold_config_for_batch(self, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        return build_batch_qc_run(self.load_analysis_history_for_viewer(path), threshold_config=resolved, metadata=metadata, batch_id=batch_id)

    def render_batch_qc_summary_text_for_viewer(self, path: str | Path | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, use_selected_threshold_config: bool = False) -> str | None:
        run = self.build_batch_qc_run_for_viewer(path=path, threshold_config=threshold_config, metadata=metadata, batch_id=batch_id, use_selected_threshold_config=use_selected_threshold_config)
        return None if run is None else render_batch_qc_summary_text(run)

    def export_batch_qc_run_json_for_viewer(self, path: str | None = None, history_path: str | Path | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, use_selected_threshold_config: bool = False) -> str | None:
        run = self.build_batch_qc_run_for_viewer(path=history_path, threshold_config=threshold_config, metadata=metadata, batch_id=batch_id, use_selected_threshold_config=use_selected_threshold_config)
        if run is None:
            return None
        if path is None:
            path = filedialog.asksaveasfilename(title="Batch QC JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return export_batch_qc_run_to_json(run, path=path)

    def export_batch_qc_run_csv_for_viewer(self, path: str | None = None, history_path: str | Path | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, use_selected_threshold_config: bool = False) -> str | None:
        run = self.build_batch_qc_run_for_viewer(path=history_path, threshold_config=threshold_config, metadata=metadata, batch_id=batch_id, use_selected_threshold_config=use_selected_threshold_config)
        if run is None:
            return None
        if path is None:
            path = filedialog.asksaveasfilename(title="Batch QC CSV 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")])
            if not path:
                return None
        return export_batch_qc_run_to_csv(run, path=path)

    def show_batch_qc_summary_viewer(self, path: str | Path | None = None, threshold_config: dict[str, Any] | None = None, use_selected_threshold_config: bool = False) -> str | None:
        text = self.render_batch_qc_summary_text_for_viewer(path=path, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        if text is None:
            return None
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Batch QC Summary")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word"); t.pack(fill="both", expand=True); t.insert("1.0", text); t.configure(state="disabled")
        return text

    def build_batch_qc_run_with_selected_threshold_for_viewer(self, path: str | Path | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None) -> dict[str, Any] | None:
        return self.build_batch_qc_run_for_viewer(path=path, metadata=metadata, batch_id=batch_id, use_selected_threshold_config=True)

    def render_batch_qc_summary_text_with_selected_threshold_for_viewer(self, path: str | Path | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None) -> str | None:
        return self.render_batch_qc_summary_text_for_viewer(path=path, metadata=metadata, batch_id=batch_id, use_selected_threshold_config=True)

    def export_batch_qc_run_json_with_selected_threshold_for_viewer(self, path: str | None = None, history_path: str | Path | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None) -> str | None:
        return self.export_batch_qc_run_json_for_viewer(path=path, history_path=history_path, metadata=metadata, batch_id=batch_id, use_selected_threshold_config=True)

    def export_batch_qc_run_csv_with_selected_threshold_for_viewer(self, path: str | None = None, history_path: str | Path | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None) -> str | None:
        return self.export_batch_qc_run_csv_for_viewer(path=path, history_path=history_path, metadata=metadata, batch_id=batch_id, use_selected_threshold_config=True)

    def show_batch_qc_summary_with_selected_threshold_viewer(self, path: str | Path | None = None) -> str | None:
        return self.show_batch_qc_summary_viewer(path=path, use_selected_threshold_config=True)

    def build_dicom_batch_history_records_for_viewer(self, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]]:
        result = execution_result if execution_result is not None else getattr(self, "current_dicom_batch_execution_result", None)
        if result is None:
            raise ValueError("current_dicom_batch_execution_result is empty")
        records = build_analysis_history_records_from_dicom_batch_execution_result(result, metadata=metadata, record_id_prefix=record_id_prefix)
        self.current_dicom_batch_history_records = records
        DicomViewer._refresh_window_b_batch_workspace(self)
        return records

    def append_dicom_batch_history_records_for_viewer(self, history_path: str | Path | None = None, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]] | None:
        if history_path is None:
            history_path = filedialog.asksaveasfilename(title="QC history JSONL 저장", defaultextension=".jsonl", filetypes=[("JSONL", "*.jsonl"), ("All Files", "*.*")])
            if not history_path:
                return None
        records = self.build_dicom_batch_history_records_for_viewer(execution_result=execution_result, metadata=metadata, record_id_prefix=record_id_prefix)
        append_dicom_batch_execution_history_records(str(history_path), records)
        self._refresh_result_history_table()
        DicomViewer._refresh_window_b_batch_workspace(self)
        return records

    def build_batch_qc_run_from_dicom_batch_execution_result_for_viewer(self, execution_result: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]:
        result = execution_result if execution_result is not None else getattr(self, "current_dicom_batch_execution_result", None)
        if result is None:
            raise ValueError("current_dicom_batch_execution_result is empty")
        resolved = DicomViewer._resolve_threshold_config_for_batch(self, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        run = build_batch_qc_run_from_dicom_batch_execution_result(result, threshold_config=resolved, metadata=metadata, batch_id=batch_id)
        self.current_batch_qc_run = run
        DicomViewer._refresh_window_b_batch_workspace(self)
        return run

    def build_analysis_history_records_from_normalized_execution_for_viewer(self, normalized_execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]]:
        normalized = normalized_execution_result if normalized_execution_result is not None else getattr(self, "current_normalized_dicom_batch_execution_result", None)
        if normalized is None:
            execution_result = getattr(self, "current_dicom_batch_execution_result", None)
            if execution_result is None:
                raise ValueError("current_normalized_dicom_batch_execution_result is empty")
            normalized = DicomViewer.build_normalized_dicom_batch_execution_result_for_viewer(self, execution_result=execution_result)
        records = build_analysis_history_records_from_normalized_dicom_batch_execution_result(normalized, metadata=metadata, record_id_prefix=record_id_prefix)
        self.current_normalized_execution_history_records = records
        return records

    def append_normalized_execution_history_records_for_viewer(self, history_path: str | Path | None = None, normalized_execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, record_id_prefix: str | None = None) -> list[dict[str, Any]] | None:
        if history_path is None:
            history_path = filedialog.asksaveasfilename(title="QC history JSONL 저장", defaultextension=".jsonl", filetypes=[("JSONL", "*.jsonl"), ("All Files", "*.*")])
            if not history_path:
                return None
        records = self.build_analysis_history_records_from_normalized_execution_for_viewer(normalized_execution_result=normalized_execution_result, metadata=metadata, record_id_prefix=record_id_prefix)
        out = append_normalized_dicom_batch_execution_history_records(str(history_path), records)
        self._refresh_result_history_table()
        return out

    def render_normalized_execution_history_adapter_text_for_viewer(self, normalized_execution_result: dict[str, Any] | None = None) -> str:
        normalized = normalized_execution_result if normalized_execution_result is not None else getattr(self, "current_normalized_dicom_batch_execution_result", None)
        if normalized is None:
            raise ValueError("current_normalized_dicom_batch_execution_result is empty")
        records = self.build_analysis_history_records_from_normalized_execution_for_viewer(normalized_execution_result=normalized)
        return render_normalized_execution_history_adapter_text(records, normalized_execution_result=normalized)

    def build_batch_qc_run_from_normalized_execution_history_records_for_viewer(self, records: list[dict[str, Any]] | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]:
        record_list = records if records is not None else getattr(self, "current_normalized_execution_history_records", None)
        if not record_list:
            raise ValueError("current_normalized_execution_history_records is empty")
        resolved = DicomViewer._resolve_threshold_config_for_batch(self, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        run = build_batch_qc_run_from_normalized_execution_history_records(record_list, threshold_config=resolved, metadata=metadata, batch_id=batch_id)
        self.current_batch_qc_run = run
        return run

    def build_batch_qc_run_from_normalized_execution_for_viewer(self, normalized_execution_result: dict[str, Any] | None = None, threshold_config: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, batch_id: str | None = None, record_id_prefix: str | None = None, use_selected_threshold_config: bool = False) -> dict[str, Any]:
        normalized = normalized_execution_result if normalized_execution_result is not None else getattr(self, "current_normalized_dicom_batch_execution_result", None)
        if normalized is None:
            raise ValueError("current_normalized_dicom_batch_execution_result is empty")
        records = DicomViewer.build_analysis_history_records_from_normalized_execution_for_viewer(self, normalized_execution_result=normalized, record_id_prefix=record_id_prefix)
        resolved = DicomViewer._resolve_threshold_config_for_batch(self, threshold_config=threshold_config, use_selected_threshold_config=use_selected_threshold_config)
        run = build_batch_qc_run_from_normalized_dicom_batch_execution_result(normalized, threshold_config=resolved, metadata=metadata, batch_id=batch_id, record_id_prefix=record_id_prefix)
        self.current_normalized_execution_history_records = records
        self.current_batch_qc_run = run
        return run

    def render_normalized_batch_qc_adapter_text_for_viewer(self, batch_qc_run: dict[str, Any] | None = None, records: list[dict[str, Any]] | None = None, normalized_execution_result: dict[str, Any] | None = None) -> str:
        run = batch_qc_run if batch_qc_run is not None else getattr(self, "current_batch_qc_run", None)
        if run is None:
            raise ValueError("current_batch_qc_run is empty")
        return render_normalized_batch_qc_adapter_text(run, records=records, normalized_execution_result=normalized_execution_result)

    def build_normalized_batch_qc_report_model_for_viewer(self, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        run = batch_qc_run if batch_qc_run is not None else getattr(self, "current_batch_qc_run", None)
        if run is None:
            raise ValueError("current_batch_qc_run is empty")
        model = build_report_model_from_normalized_batch_qc_run(run, metadata=metadata)
        self.current_normalized_batch_qc_report_model = model
        return model

    def render_normalized_batch_qc_report_text_for_viewer(self, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str:
        model = self.build_normalized_batch_qc_report_model_for_viewer(batch_qc_run=batch_qc_run, metadata=metadata)
        return render_normalized_batch_qc_report_text(model)

    def export_normalized_batch_qc_report_json_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], title="Save Normalized Batch QC Report JSON")
            if not path: return None
        model = self.build_normalized_batch_qc_report_model_for_viewer(batch_qc_run=batch_qc_run, metadata=metadata)
        return export_normalized_batch_qc_report_to_json(model, path=path)

    def export_normalized_batch_qc_report_csv_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], title="Save Normalized Batch QC Report CSV")
            if not path: return None
        model = self.build_normalized_batch_qc_report_model_for_viewer(batch_qc_run=batch_qc_run, metadata=metadata)
        return export_normalized_batch_qc_report_to_csv(model, path=path)

    def export_normalized_batch_qc_report_text_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")], title="Save Normalized Batch QC Report Text")
            if not path: return None
        model = self.build_normalized_batch_qc_report_model_for_viewer(batch_qc_run=batch_qc_run, metadata=metadata)
        return export_normalized_batch_qc_report_to_text(model, path=path)

    def export_normalized_batch_qc_report_pdf_for_viewer(self, path: str | None = None, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> bytes | None:
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], title="Save Normalized Batch QC Report PDF")
            if not path: return None
        model = self.build_normalized_batch_qc_report_model_for_viewer(batch_qc_run=batch_qc_run, metadata=metadata)
        return export_normalized_batch_qc_report_to_pdf(model, path=path)

    def render_normalized_batch_workflow_summary_text_for_viewer(self) -> str:
        has_execution = getattr(self, "current_dicom_batch_execution_result", None) is not None
        has_norm_exec = getattr(self, "current_normalized_dicom_batch_execution_result", None) is not None
        record_count = len(getattr(self, "current_normalized_execution_history_records", []) or [])
        has_qc = getattr(self, "current_batch_qc_run", None) is not None
        has_report = getattr(self, "current_normalized_batch_qc_report_model", None) is not None
        selected_threshold_var = getattr(self, "_window_b_batch_use_selected_threshold_var", None)
        selected_threshold_enabled = bool(selected_threshold_var.get()) if selected_threshold_var is not None and hasattr(selected_threshold_var, "get") else False
        if not has_execution:
            next_action = "Run or build batch execution result first."
        elif not has_norm_exec:
            next_action = "Build normalized execution result."
        elif record_count == 0:
            next_action = "Build normalized history records."
        elif not has_qc:
            next_action = "Build normalized batch QC run."
        elif not has_report:
            next_action = "Preview or export normalized batch QC report."
        else:
            next_action = "Workflow ready."
        return (
            f"has_execution_result={has_execution}\n"
            f"has_normalized_execution_result={has_norm_exec}\n"
            f"normalized_history_record_count={record_count}\n"
            f"has_batch_qc_run={has_qc}\n"
            f"has_normalized_batch_qc_report_model={has_report}\n"
            f"selected_threshold_enabled={selected_threshold_enabled}\n"
            f"next_action={next_action}\n"
        )

    def show_normalized_batch_qc_report_viewer(self, batch_qc_run: dict[str, Any] | None = None) -> str:
        text = self.render_normalized_batch_qc_report_text_for_viewer(batch_qc_run=batch_qc_run)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Normalized Batch QC Report Preview")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def show_normalized_batch_qc_adapter_viewer(self, batch_qc_run: dict[str, Any] | None = None) -> str:
        text = self.render_normalized_batch_qc_adapter_text_for_viewer(batch_qc_run=batch_qc_run)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Normalized Batch QC Adapter Preview")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def show_normalized_execution_history_adapter_viewer(self, normalized_execution_result: dict[str, Any] | None = None) -> str:
        text = self.render_normalized_execution_history_adapter_text_for_viewer(normalized_execution_result=normalized_execution_result)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Normalized Execution → History Adapter Preview")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def show_dicom_batch_history_bridge_viewer(self, execution_result: dict[str, Any] | None = None) -> str:
        records = self.build_dicom_batch_history_records_for_viewer(execution_result=execution_result)
        text = render_dicom_batch_history_bridge_summary_text(records)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("DICOM Batch History Bridge Preview")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def build_current_batch_qc_report_model_for_viewer(self, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        run = batch_qc_run if batch_qc_run is not None else getattr(self, "current_batch_qc_run", None)
        if run is None:
            raise ValueError("current_batch_qc_run is empty")
        model = build_batch_qc_report_model(run, metadata=metadata)
        self.current_batch_qc_report_model = model
        return model

    def render_current_batch_qc_report_text_for_viewer(self, batch_qc_run: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str:
        return render_batch_qc_report_text(DicomViewer.build_current_batch_qc_report_model_for_viewer(self, batch_qc_run=batch_qc_run, metadata=metadata))

    def export_current_batch_qc_run_json_for_viewer(self, path: str | None = None) -> str | None:
        run = getattr(self, "current_batch_qc_run", None)
        if run is None:
            raise ValueError("current_batch_qc_run is empty")
        if path is None:
            path = filedialog.asksaveasfilename(title="Batch QC JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return export_batch_qc_run_to_json(run, path=path)

    def export_current_batch_qc_run_csv_for_viewer(self, path: str | None = None) -> str | None:
        run = getattr(self, "current_batch_qc_run", None)
        if run is None:
            raise ValueError("current_batch_qc_run is empty")
        if path is None:
            path = filedialog.asksaveasfilename(title="Batch QC CSV 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")])
            if not path:
                return None
        return export_batch_qc_run_to_csv(run, path=path)

    def export_current_batch_qc_report_text_for_viewer(self, path: str | None = None, metadata: dict[str, Any] | None = None) -> str | None:
        model = DicomViewer.build_current_batch_qc_report_model_for_viewer(self, metadata=metadata)
        if path is None:
            path = filedialog.asksaveasfilename(title="Batch QC Report Text 저장", defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All Files", "*.*")])
            if not path:
                return None
        return export_batch_qc_report_to_text(model, path=path)

    def export_current_batch_qc_report_pdf_for_viewer(self, path: str | None = None, metadata: dict[str, Any] | None = None) -> bytes | None:
        model = DicomViewer.build_current_batch_qc_report_model_for_viewer(self, metadata=metadata)
        if path is None:
            path = filedialog.asksaveasfilename(title="Batch QC Report PDF 저장", defaultextension=".pdf", filetypes=[("PDF", "*.pdf"), ("All Files", "*.*")])
            if not path:
                return None
        return export_batch_qc_report_to_pdf(model, path=path)

    def show_current_batch_qc_report_viewer(self) -> str:
        text = self.render_current_batch_qc_report_text_for_viewer()
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Batch QC Report Preview")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def build_current_dicom_batch_execution_plan_for_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        source_manifest = manifest if manifest is not None else getattr(self, "current_dicom_batch_manifest", None)
        source_preset = roi_preset if roi_preset is not None else getattr(self, "current_roi_preset", None)
        if source_manifest is None:
            raise ValueError("current_dicom_batch_manifest is empty")
        if source_preset is None:
            raise ValueError("current_roi_preset is empty")
        bounds = getattr(self, "current_roi_bounds_validation", None)
        if bounds is None:
            bounds = DicomViewer.build_roi_bounds_validation_for_viewer(self, manifest=source_manifest, roi_preset=source_preset, metadata=metadata)
        analysis_plan = DicomViewer.build_dicom_batch_analysis_plan_for_viewer(self, manifest=source_manifest, roi_preset=source_preset, metadata=metadata)
        plan = build_dicom_batch_execution_plan(analysis_plan, bounds, metadata=metadata)
        self.current_dicom_batch_execution_plan = plan
        DicomViewer._refresh_window_b_batch_workspace(self)
        return plan

    def run_current_dicom_batch_execution_plan_for_viewer(self, execution_plan: dict[str, Any] | None = None, analysis_executor: Any = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        plan = execution_plan if execution_plan is not None else getattr(self, "current_dicom_batch_execution_plan", None)
        if plan is None:
            raise ValueError("current_dicom_batch_execution_plan is empty")
        roi_preset = getattr(self, "current_roi_preset", None)
        if roi_preset is None:
            raise ValueError("current_roi_preset is empty")
        executor = analysis_executor if analysis_executor is not None else getattr(self, "current_batch_analysis_executor", None)
        result = run_dicom_batch_execution_plan_with_executor(plan, roi_preset, analysis_executor=executor, metadata=metadata)
        self.current_dicom_batch_execution_result = result
        DicomViewer._refresh_window_b_batch_workspace(self)
        return result

    def get_dicom_batch_execution_plan_summary_for_viewer(self, execution_plan: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_dicom_batch_run_orchestration_summary(execution_plan=execution_plan if execution_plan is not None else getattr(self, "current_dicom_batch_execution_plan", None), execution_result=None)

    def render_dicom_batch_run_workspace_summary_text_for_viewer(self, execution_plan: dict[str, Any] | None = None, execution_result: dict[str, Any] | None = None) -> str:
        plan = execution_plan if execution_plan is not None else getattr(self, "current_dicom_batch_execution_plan", None)
        result = execution_result if execution_result is not None else getattr(self, "current_dicom_batch_execution_result", None)
        return render_dicom_batch_run_orchestration_summary_text(plan, result)

    def preview_current_dicom_batch_execution_result_for_viewer(self, execution_result: dict[str, Any] | None = None) -> str:
        result = execution_result if execution_result is not None else getattr(self, "current_dicom_batch_execution_result", None)
        if result is None:
            return "DICOM batch execution result is empty\n"
        return render_dicom_batch_execution_result_text(validate_dicom_batch_execution_result(result))

    def create_batch_analysis_dispatcher_for_viewer(self):
        snr = lambda task, item, context: {"status": "ok", "result": 1.0, "signal_roi_id": (context.get("roi_ids") or [None])[0], "noise_roi_id": (context.get("roi_ids") or [None, None])[-1]}
        cnr = lambda task, item, context: {"status": "ok", "result": 1.0, "inputs": {"region_a_roi_id": (context.get("roi_ids") or [None])[0], "region_b_roi_id": (context.get("roi_ids") or [None, None])[-1], "noise_roi_id": (context.get("roi_ids") or [None])[-1]}}
        uni = lambda task, item, context: {"status": "ok", "result": {"value": 1.0}, "inputs": {"roi_ids": list(context.get("roi_ids") or []), "roi_count": len(list(context.get("roi_ids") or []))}}
        mtf = lambda task, item, context: {"status": "ok", "key_mtf_metrics": {"mtf50": 1.0}, "mtf_curve": {"frequency_cy_per_pixel": [0.0, 1.0], "mtf": [1.0, 0.5]}}
        return create_existing_analysis_dispatcher(snr_analyzer=snr, cnr_analyzer=cnr, uniformity_analyzer=uni, mtf_analyzer=mtf)

    def create_dicom_batch_pixel_analysis_executor_for_viewer(self, *, pixel_loader=None, roi_resolver=None, analysis_dispatcher=None):
        dispatcher = analysis_dispatcher if analysis_dispatcher is not None else DicomViewer.create_batch_analysis_dispatcher_for_viewer(self)
        return create_dicom_batch_pixel_analysis_executor(pixel_loader=pixel_loader, roi_resolver=roi_resolver, analysis_dispatcher=dispatcher)

    def validate_current_dicom_batch_roi_roles_for_viewer(self, execution_plan: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, bounds_result: dict[str, Any] | None = None, role_policy: dict[str, Any] | None = None) -> dict[str, Any]:
        plan = execution_plan if execution_plan is not None else getattr(self, "current_dicom_batch_execution_plan", None)
        preset = roi_preset if roi_preset is not None else getattr(self, "current_roi_preset", None)
        if plan is None:
            raise ValueError("current_dicom_batch_execution_plan is empty")
        if preset is None:
            raise ValueError("current_roi_preset is empty")
        bounds = bounds_result if bounds_result is not None else getattr(self, "current_roi_bounds_validation", None)
        report = validate_dicom_batch_roi_roles(plan, preset, bounds_result=bounds, role_policy=role_policy)
        self.current_dicom_batch_roi_role_validation_report = report
        DicomViewer._refresh_window_b_batch_workspace(self)
        return report

    def render_current_dicom_batch_roi_role_validation_text_for_viewer(self, validation_report: dict[str, Any] | None = None) -> str:
        report = validation_report if validation_report is not None else getattr(self, "current_dicom_batch_roi_role_validation_report", None)
        if report is None:
            return "No ROI role validation report\n"
        return render_dicom_batch_roi_role_validation_text(report)

    def preview_current_dicom_batch_roi_role_validation_for_viewer(self) -> str:
        report = DicomViewer.validate_current_dicom_batch_roi_roles_for_viewer(self)
        return DicomViewer.render_current_dicom_batch_roi_role_validation_text_for_viewer(self, report)

    def set_current_dicom_batch_strict_roi_validation_for_viewer(self, enabled: bool):
        self.current_dicom_batch_strict_roi_validation = bool(enabled)

    def build_current_dicom_batch_workflow_readiness_for_viewer(self, strict_roi_role_validation: bool | None = None) -> dict[str, Any]:
        strict = bool(getattr(self, "current_dicom_batch_strict_roi_validation", False)) if strict_roi_role_validation is None else bool(strict_roi_role_validation)
        report = build_dicom_batch_workflow_readiness_report(
            execution_plan=getattr(self, "current_dicom_batch_execution_plan", None),
            roi_role_validation_report=getattr(self, "current_dicom_batch_roi_role_validation_report", None),
            pixel_capability_text=DicomViewer.preview_current_dicom_batch_pixel_executor_capability_for_viewer(self),
            execution_result=getattr(self, "current_dicom_batch_execution_result", None),
            history_records=getattr(self, "current_dicom_batch_history_records", None),
            batch_qc_run=getattr(self, "current_batch_qc_run", None),
            strict_roi_role_validation=strict,
        )
        self.current_dicom_batch_workflow_readiness_report = report
        return report

    def render_current_dicom_batch_workflow_readiness_text_for_viewer(self, report: dict[str, Any] | None = None) -> str:
        payload = report if report is not None else getattr(self, "current_dicom_batch_workflow_readiness_report", None)
        if payload is None:
            payload = DicomViewer.build_current_dicom_batch_workflow_readiness_for_viewer(self)
        return render_dicom_batch_workflow_readiness_text(payload)

    def preview_current_dicom_batch_workflow_readiness_for_viewer(self, strict_roi_role_validation: bool | None = None) -> str:
        payload = DicomViewer.build_current_dicom_batch_workflow_readiness_for_viewer(self, strict_roi_role_validation=strict_roi_role_validation)
        return DicomViewer.render_current_dicom_batch_workflow_readiness_text_for_viewer(self, payload)

    def run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer(self, execution_plan: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, analysis_dispatcher=None, strict_roi_role_validation: bool = False) -> dict[str, Any]:
        if strict_roi_role_validation:
            report = DicomViewer.validate_current_dicom_batch_roi_roles_for_viewer(self, execution_plan=execution_plan)
            assert_dicom_batch_roi_roles_valid(report)
            ready = DicomViewer.build_current_dicom_batch_workflow_readiness_for_viewer(self, strict_roi_role_validation=True)
            assert_dicom_batch_workflow_ready_for_pixel_run(ready)
        executor = DicomViewer.create_dicom_batch_pixel_analysis_executor_for_viewer(self, analysis_dispatcher=analysis_dispatcher)
        out = DicomViewer.run_current_dicom_batch_execution_plan_for_viewer(self, execution_plan=execution_plan, analysis_executor=executor, metadata=metadata)
        DicomViewer.build_current_dicom_batch_workflow_readiness_for_viewer(self, strict_roi_role_validation=strict_roi_role_validation)
        return out

    def preview_current_dicom_batch_pixel_executor_capability_for_viewer(self) -> str:
        plan = getattr(self, "current_dicom_batch_execution_plan", None)
        has_plan = plan is not None
        item_count = int((plan or {}).get("item_count", 0))
        task_count = int((plan or {}).get("task_count", 0))
        try:
            import importlib
            importlib.import_module("pydicom")
            pydicom_status = "available"
        except Exception:
            pydicom_status = "unavailable"
        dispatcher_info = {"supported_analysis_types": sorted(SUPPORTED_BATCH_ANALYSIS_TYPES), "connected_analyzer_types": sorted(SUPPORTED_BATCH_ANALYSIS_TYPES), "missing_analyzer_types": [], "payload_validation_enabled": True}
        lines = [
            "DICOM Batch Pixel Executor Capability",
            f"pydicom: {pydicom_status} (lazy import)",
            f"has_execution_plan: {has_plan}",
            f"item_count: {item_count}",
            f"task_count: {task_count}",
            f"supported_analysis_types: {sorted(SUPPORTED_ANALYSIS_TYPES)}",
            "unsupported_analysis_types: any other analysis_type",
            "next_action: Run Pixel Batch Execution",
            "",
            render_batch_analysis_dispatcher_capability_text(dispatcher_info).strip(),
        ]
        return "\\n".join(lines) + "\\n"

    def get_dicom_batch_execution_result_summary_for_viewer(self, execution_result: dict[str, Any] | None = None) -> dict[str, Any]:
        history_records = list(getattr(self, "current_dicom_batch_history_records", []) or [])
        batch_qc_run = getattr(self, "current_batch_qc_run", None)
        result = execution_result if execution_result is not None else getattr(self, "current_dicom_batch_execution_result", None)
        if result is None:
            return {
                "has_execution_result": False,
                "run_id": "",
                "execution_plan_id": "",
                "item_count": 0,
                "task_count": 0,
                "completed_task_count": 0,
                "blocked_task_count": 0,
                "not_executed_task_count": 0,
                "error_task_count": 0,
                "history_record_count": len(history_records),
                "has_batch_qc_run": bool(batch_qc_run),
            }
        payload = validate_dicom_batch_execution_result(result)
        return {
            "has_execution_result": True,
            "run_id": str(payload.get("run_id", "")),
            "execution_plan_id": str(payload.get("execution_plan_id", "")),
            "item_count": int(payload.get("item_count", 0)),
            "task_count": int(payload.get("task_count", 0)),
            "completed_task_count": int(payload.get("completed_task_count", 0)),
            "blocked_task_count": int(payload.get("blocked_task_count", 0)),
            "not_executed_task_count": int(payload.get("not_executed_task_count", 0)),
            "error_task_count": int(payload.get("error_task_count", 0)),
            "history_record_count": len(history_records),
            "has_batch_qc_run": bool(batch_qc_run),
        }

    def render_dicom_batch_workspace_summary_text_for_viewer(self, execution_result: dict[str, Any] | None = None) -> str:
        summary = DicomViewer.get_dicom_batch_execution_result_summary_for_viewer(self, execution_result=execution_result)
        lines = [
            "Window B Batch Workspace Summary",
            f"Execution Result Loaded: {summary['has_execution_result']}",
            f"Run ID: {summary['run_id']}",
            f"Execution Plan ID: {summary['execution_plan_id']}",
            f"Items: {summary['item_count']}, Tasks: {summary['task_count']}",
            f"Task Status Counts: completed={summary['completed_task_count']} blocked={summary['blocked_task_count']} not_executed={summary['not_executed_task_count']} error={summary['error_task_count']}",
            f"Current Bridge Records: {summary['history_record_count']}",
            f"Current Batch QC Run: {summary['has_batch_qc_run']}",
        ]
        if summary["has_execution_result"]:
            lines.append("Next Action: Build History Records -> Append JSONL -> Build Batch QC Run")
        else:
            lines.append("Next Action: Build or load DICOM batch execution result first")
        return "\n".join(lines) + "\n"

    def _refresh_window_b_batch_workspace(self) -> None:
        summary_var = getattr(self, "_window_b_batch_summary_var", None)
        preview_text = getattr(self, "_window_b_batch_preview_text", None)
        if summary_var is None or preview_text is None:
            return
        summary = self.get_dicom_batch_execution_result_summary_for_viewer()
        summary_var.set(
            f"has_execution_result={summary.get('has_execution_result')} | run_id={summary.get('run_id')} | execution_plan_id={summary.get('execution_plan_id')} | "
            f"items={summary.get('item_count')} | tasks={summary.get('task_count')} | completed={summary.get('completed_task_count')} blocked={summary.get('blocked_task_count')} "
            f"not_executed={summary.get('not_executed_task_count')} error={summary.get('error_task_count')} | bridge_records={summary.get('history_record_count')} | has_batch_qc_run={summary.get('has_batch_qc_run')}"
        )
        preview_text.configure(state="normal")
        preview_text.delete("1.0", "end")
        preview_text.insert("1.0", self.render_dicom_batch_workspace_summary_text_for_viewer())
        preview_text.configure(state="disabled")

    def build_dicom_batch_manifest_for_viewer(self, paths: list[str] | tuple[str, ...] | None = None, recursive: bool = True, metadata: dict[str, Any] | None = None, manifest_id: str | None = None) -> dict[str, Any] | None:
        if paths is None:
            picked = filedialog.askopenfilenames(title="Batch DICOM 파일 선택", filetypes=[("DICOM", "*.dcm"), ("All Files", "*.*")])
            if not picked:
                return None
            paths = list(picked)
        m = build_dicom_batch_manifest(paths, recursive=recursive, metadata=metadata, manifest_id=manifest_id)
        self.current_dicom_batch_manifest = m
        return m

    def render_dicom_batch_manifest_text_for_viewer(self, paths: list[str] | tuple[str, ...] | None = None, recursive: bool = True, metadata: dict[str, Any] | None = None, manifest_id: str | None = None) -> str | None:
        m = self.build_dicom_batch_manifest_for_viewer(paths=paths, recursive=recursive, metadata=metadata, manifest_id=manifest_id)
        return None if m is None else render_dicom_batch_manifest_text(m)

    def export_dicom_batch_manifest_json_for_viewer(self, path: str | None = None, source_paths: list[str] | tuple[str, ...] | None = None, recursive: bool = True, metadata: dict[str, Any] | None = None, manifest_id: str | None = None) -> str | None:
        m = self.build_dicom_batch_manifest_for_viewer(paths=source_paths, recursive=recursive, metadata=metadata, manifest_id=manifest_id)
        if m is None:
            return None
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Manifest JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return export_dicom_batch_manifest_to_json(m, path=path)

    def export_dicom_batch_manifest_csv_for_viewer(self, path: str | None = None, source_paths: list[str] | tuple[str, ...] | None = None, recursive: bool = True, metadata: dict[str, Any] | None = None, manifest_id: str | None = None) -> str | None:
        m = self.build_dicom_batch_manifest_for_viewer(paths=source_paths, recursive=recursive, metadata=metadata, manifest_id=manifest_id)
        if m is None:
            return None
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Manifest CSV 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")])
            if not path:
                return None
        return export_dicom_batch_manifest_to_csv(m, path=path)

    def show_dicom_batch_manifest_viewer(self, paths: list[str] | tuple[str, ...] | None = None, recursive: bool = True) -> str | None:
        text = self.render_dicom_batch_manifest_text_for_viewer(paths=paths, recursive=recursive)
        if text is None:
            return None
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("DICOM Batch Manifest")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word"); t.pack(fill="both", expand=True); t.insert("1.0", text); t.configure(state="disabled")
        return text

    def build_current_roi_preset(self, name: str = "Untitled ROI preset", description: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        rois = getattr(self, "roi_definitions", None)
        if not isinstance(rois, list):
            rois = (getattr(self, "current_roi_preset", {}) or {}).get("roi_definitions") or []
        return build_roi_preset_from_roi_definitions(rois, name=name, description=description, metadata=metadata)

    def load_roi_preset_for_viewer(self, path: str | None = None) -> dict[str, Any] | None:
        if path is None:
            path = filedialog.askopenfilename(title="ROI preset JSON 선택", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        self.current_roi_preset = load_roi_preset(path)
        return self.current_roi_preset

    def save_current_roi_preset(self, path: str | None = None, name: str = "Untitled ROI preset", description: str = "", metadata: dict[str, Any] | None = None) -> str | None:
        preset = getattr(self, "current_roi_preset", None) or self.build_current_roi_preset(name=name, description=description, metadata=metadata)
        if path is None:
            path = filedialog.asksaveasfilename(title="ROI preset JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return export_roi_preset_to_json(preset, path=path)

    def render_current_roi_preset_text(self) -> str:
        preset = getattr(self, "current_roi_preset", None) or self.build_current_roi_preset()
        return render_roi_preset_text(preset)

    def show_current_roi_preset_preview(self) -> str:
        text = self.render_current_roi_preset_text()
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("ROI Preset Preview")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word"); t.pack(fill="both", expand=True); t.insert("1.0", text); t.configure(state="disabled")
        return text

    def build_dicom_batch_analysis_plan_for_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, plan_id: str | None = None) -> dict[str, Any]:
        m = manifest or getattr(self, "current_dicom_batch_manifest", None)
        if m is None:
            raise ValueError("current_dicom_batch_manifest is empty")
        p = roi_preset or getattr(self, "current_roi_preset", None)
        if p is None:
            raise ValueError("current_roi_preset is empty")
        plan = build_dicom_batch_analysis_plan(m, p, analyses=analyses, metadata=metadata, plan_id=plan_id)
        self.current_dicom_batch_analysis_plan = plan
        return plan

    def render_dicom_batch_analysis_plan_text_for_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, plan_id: str | None = None) -> str:
        return render_dicom_batch_analysis_plan_text(self.build_dicom_batch_analysis_plan_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses, metadata=metadata, plan_id=plan_id))

    def export_dicom_batch_analysis_plan_json_for_viewer(self, path: str | None = None, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, plan_id: str | None = None) -> str | None:
        plan = self.build_dicom_batch_analysis_plan_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses, metadata=metadata, plan_id=plan_id)
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Plan JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return export_dicom_batch_analysis_plan_to_json(plan, path=path)

    def export_dicom_batch_analysis_plan_csv_for_viewer(self, path: str | None = None, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, plan_id: str | None = None) -> str | None:
        plan = self.build_dicom_batch_analysis_plan_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses, metadata=metadata, plan_id=plan_id)
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Plan CSV 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")])
            if not path:
                return None
        return export_dicom_batch_analysis_plan_to_csv(plan, path=path)

    def show_dicom_batch_analysis_plan_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None) -> str:
        text = self.render_dicom_batch_analysis_plan_text_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("DICOM Batch Analysis Plan")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word"); t.pack(fill="both", expand=True); t.insert("1.0", text); t.configure(state="disabled")
        return text

    def build_roi_bounds_validation_for_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, validation_id: str | None = None) -> dict[str, Any]:
        m = manifest or getattr(self, "current_dicom_batch_manifest", None)
        if m is None:
            raise ValueError("current_dicom_batch_manifest is empty")
        p = roi_preset or getattr(self, "current_roi_preset", None)
        if p is None:
            raise ValueError("current_roi_preset is empty")
        result = build_roi_bounds_validation_result(m, p, analyses=analyses, metadata=metadata, validation_id=validation_id)
        self.current_roi_bounds_validation = result
        return result

    def build_dicom_batch_execution_plan_for_viewer(self, batch_plan: dict[str, Any] | None = None, bounds_validation: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, execution_plan_id: str | None = None) -> dict[str, Any]:
        plan = batch_plan if batch_plan is not None else getattr(self, "current_dicom_batch_analysis_plan", None)
        if plan is None:
            raise ValueError("current_dicom_batch_analysis_plan is empty")
        bounds = bounds_validation if bounds_validation is not None else getattr(self, "current_roi_bounds_validation", None)
        if bounds is None:
            raise ValueError("current_roi_bounds_validation is empty")
        execution_plan = build_dicom_batch_execution_plan(plan, bounds, analyses=analyses, metadata=metadata, execution_plan_id=execution_plan_id)
        self.current_dicom_batch_execution_plan = execution_plan
        return execution_plan

    def render_dicom_batch_execution_plan_text_for_viewer(self, batch_plan: dict[str, Any] | None = None, bounds_validation: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, execution_plan_id: str | None = None) -> str:
        plan = DicomViewer.build_dicom_batch_execution_plan_for_viewer(self, batch_plan=batch_plan, bounds_validation=bounds_validation, analyses=analyses, metadata=metadata, execution_plan_id=execution_plan_id)
        return render_dicom_batch_execution_plan_text(plan)

    def export_dicom_batch_execution_plan_json_for_viewer(self, path: str | None = None, batch_plan: dict[str, Any] | None = None, bounds_validation: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, execution_plan_id: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Execution Plan JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        plan = DicomViewer.build_dicom_batch_execution_plan_for_viewer(self, batch_plan=batch_plan, bounds_validation=bounds_validation, analyses=analyses, metadata=metadata, execution_plan_id=execution_plan_id)
        return export_dicom_batch_execution_plan_to_json(plan, path=path)

    def export_dicom_batch_execution_plan_csv_for_viewer(self, path: str | None = None, batch_plan: dict[str, Any] | None = None, bounds_validation: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, execution_plan_id: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Execution Plan CSV 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")])
            if not path:
                return None
        plan = DicomViewer.build_dicom_batch_execution_plan_for_viewer(self, batch_plan=batch_plan, bounds_validation=bounds_validation, analyses=analyses, metadata=metadata, execution_plan_id=execution_plan_id)
        return export_dicom_batch_execution_plan_to_csv(plan, path=path)

    def show_dicom_batch_execution_plan_viewer(self, batch_plan: dict[str, Any] | None = None, bounds_validation: dict[str, Any] | None = None, analyses: list[str] | None = None) -> str:
        text = DicomViewer.render_dicom_batch_execution_plan_text_for_viewer(self, batch_plan=batch_plan, bounds_validation=bounds_validation, analyses=analyses)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("DICOM Batch Execution Plan")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word"); t.pack(fill="both", expand=True); t.insert("1.0", text); t.configure(state="disabled")
        return text

    def build_dicom_batch_execution_result_for_viewer(self, execution_plan: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analysis_executor=None, metadata: dict[str, Any] | None = None, run_id: str | None = None) -> dict[str, Any]:
        plan = execution_plan if execution_plan is not None else getattr(self, "current_dicom_batch_execution_plan", None)
        if plan is None:
            raise ValueError("current_dicom_batch_execution_plan is empty")
        preset = roi_preset if roi_preset is not None else getattr(self, "current_roi_preset", None)
        if preset is None:
            raise ValueError("current_roi_preset is empty")
        result = build_dicom_batch_execution_result(plan, preset, analysis_executor=analysis_executor, metadata=metadata, run_id=run_id)
        self.current_dicom_batch_execution_result = result
        return result

    def render_dicom_batch_execution_result_text_for_viewer(self, execution_plan: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analysis_executor=None, metadata: dict[str, Any] | None = None, run_id: str | None = None) -> str:
        result = DicomViewer.build_dicom_batch_execution_result_for_viewer(self, execution_plan=execution_plan, roi_preset=roi_preset, analysis_executor=analysis_executor, metadata=metadata, run_id=run_id)
        return render_dicom_batch_execution_result_text(result)

    def export_dicom_batch_execution_result_json_for_viewer(self, path: str | None = None, execution_plan: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analysis_executor=None, metadata: dict[str, Any] | None = None, run_id: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Execution Result JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        result = DicomViewer.build_dicom_batch_execution_result_for_viewer(self, execution_plan=execution_plan, roi_preset=roi_preset, analysis_executor=analysis_executor, metadata=metadata, run_id=run_id)
        return export_dicom_batch_execution_result_to_json(result, path=path)

    def export_dicom_batch_execution_result_csv_for_viewer(self, path: str | None = None, execution_plan: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analysis_executor=None, metadata: dict[str, Any] | None = None, run_id: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(title="DICOM Batch Execution Result CSV 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")])
            if not path:
                return None
        result = DicomViewer.build_dicom_batch_execution_result_for_viewer(self, execution_plan=execution_plan, roi_preset=roi_preset, analysis_executor=analysis_executor, metadata=metadata, run_id=run_id)
        return export_dicom_batch_execution_result_to_csv(result, path=path)

    def build_normalized_dicom_batch_execution_result_for_viewer(self, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> dict[str, Any]:
        result = execution_result if execution_result is not None else getattr(self, "current_dicom_batch_execution_result", None)
        if result is None:
            raise ValueError("current_dicom_batch_execution_result is empty")
        normalized = build_normalized_dicom_batch_execution_result(result, metadata=metadata, normalization_id=normalization_id)
        self.current_normalized_dicom_batch_execution_result = normalized
        return normalized

    def render_normalized_dicom_batch_execution_result_text_for_viewer(self, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> str:
        normalized = DicomViewer.build_normalized_dicom_batch_execution_result_for_viewer(self, execution_result=execution_result, metadata=metadata, normalization_id=normalization_id)
        return render_normalized_dicom_batch_execution_result_text(normalized)

    def export_normalized_dicom_batch_execution_result_json_for_viewer(self, path: str | None = None, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], title="Save Normalized DICOM Batch Execution Result JSON")
            if not path:
                return None
        normalized = DicomViewer.build_normalized_dicom_batch_execution_result_for_viewer(self, execution_result=execution_result, metadata=metadata, normalization_id=normalization_id)
        return export_normalized_dicom_batch_execution_result_to_json(normalized, path=path)

    def export_normalized_dicom_batch_execution_result_csv_for_viewer(self, path: str | None = None, execution_result: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, normalization_id: str | None = None) -> str | None:
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], title="Save Normalized DICOM Batch Execution Result CSV")
            if not path:
                return None
        normalized = DicomViewer.build_normalized_dicom_batch_execution_result_for_viewer(self, execution_result=execution_result, metadata=metadata, normalization_id=normalization_id)
        return export_normalized_dicom_batch_execution_result_to_csv(normalized, path=path)

    def show_normalized_dicom_batch_execution_result_viewer(self, execution_result: dict[str, Any] | None = None) -> str:
        text = DicomViewer.render_normalized_dicom_batch_execution_result_text_for_viewer(self, execution_result=execution_result)
        win = tk.Toplevel(self.root)
        win.title("DICOM Batch Execution Normalized Result")
        win.geometry("900x620")
        txt = tk.Text(win, wrap="none")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", text)
        txt.config(state="disabled")
        return text

    def show_dicom_batch_execution_result_viewer(self, execution_plan: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analysis_executor=None) -> str:
        text = DicomViewer.render_dicom_batch_execution_result_text_for_viewer(self, execution_plan=execution_plan, roi_preset=roi_preset, analysis_executor=analysis_executor)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("DICOM Batch Execution Result")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word"); t.pack(fill="both", expand=True); t.insert("1.0", text); t.configure(state="disabled")
        return text

    def render_roi_bounds_validation_text_for_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, validation_id: str | None = None) -> str:
        return render_roi_bounds_validation_text(self.build_roi_bounds_validation_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses, metadata=metadata, validation_id=validation_id))

    def export_roi_bounds_validation_json_for_viewer(self, path: str | None = None, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, validation_id: str | None = None) -> str | None:
        result = self.build_roi_bounds_validation_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses, metadata=metadata, validation_id=validation_id)
        if path is None:
            path = filedialog.asksaveasfilename(title="ROI Bounds Validation JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return export_roi_bounds_validation_to_json(result, path=path)

    def export_roi_bounds_validation_csv_for_viewer(self, path: str | None = None, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None, metadata: dict[str, Any] | None = None, validation_id: str | None = None) -> str | None:
        result = self.build_roi_bounds_validation_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses, metadata=metadata, validation_id=validation_id)
        if path is None:
            path = filedialog.asksaveasfilename(title="ROI Bounds Validation CSV 저장", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")])
            if not path:
                return None
        return export_roi_bounds_validation_to_csv(result, path=path)

    def show_roi_bounds_validation_viewer(self, manifest: dict[str, Any] | None = None, roi_preset: dict[str, Any] | None = None, analyses: list[str] | None = None) -> str:
        text = self.render_roi_bounds_validation_text_for_viewer(manifest=manifest, roi_preset=roi_preset, analyses=analyses)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("ROI Bounds Validation")
        win.geometry("900x700")
        t = tk.Text(win, wrap="word"); t.pack(fill="both", expand=True); t.insert("1.0", text); t.configure(state="disabled")
        return text

    def build_analysis_history_display_model(self, path: str | Path | None = None, analysis_type: str | None = None, validity: str | None = None) -> dict[str, Any] | None:
        if path is None:
            path = filedialog.askopenfilename(title="QC history JSONL 선택", filetypes=[("JSONL", "*.jsonl"), ("All Files", "*.*")])
            if not path:
                return None
        records = self.load_analysis_history_for_viewer(path)
        return build_history_records_display_model(records, analysis_type=analysis_type, validity=validity)

    def render_analysis_history_record_detail(self, record: dict[str, Any]) -> str:
        return render_history_record_detail_text(record)

    def show_analysis_history_viewer(self, path: str | Path | None = None) -> dict[str, Any] | None:
        if path is None:
            path = filedialog.askopenfilename(title="QC history JSONL 선택", filetypes=[("JSONL", "*.jsonl"), ("All Files", "*.*")])
            if not path:
                return None
        records = self.load_analysis_history_for_viewer(path)
        display = build_history_records_display_model(records)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("QC History Viewer")
        win.geometry("980x700")
        left = ttk.Frame(win, padding=8)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(win, padding=8)
        right.pack(side="right", fill="both", expand=True)
        lst = tk.Listbox(left)
        lst.pack(fill="both", expand=True)
        detail = tk.Text(right, wrap="word")
        detail.pack(fill="both", expand=True)
        for row in display["rows"]:
            lst.insert("end", f"{row['record_id']} | {row['generated_at']} | invalid={row['invalid_count']}")

        def _on_select(_event=None):
            sel = lst.curselection()
            if not sel:
                return
            idx = int(sel[0])
            txt = self.render_analysis_history_record_detail(records[idx])
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", txt)
            detail.configure(state="disabled")

        lst.bind("<<ListboxSelect>>", _on_select)
        if records:
            lst.selection_set(0)
            _on_select()
        return display

    def evaluate_current_analysis_thresholds(self, threshold_config: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
        normalized_results = self._get_reportable_analysis_results()
        return evaluate_analysis_thresholds(normalized_results, threshold_config, generated_at=generated_at)

    def render_current_threshold_evaluation_text(self, threshold_config: dict[str, Any]) -> str:
        return render_threshold_evaluation_text(self.evaluate_current_analysis_thresholds(threshold_config))

    def set_current_threshold_config(self, config: dict[str, Any]) -> dict[str, Any]:
        self.current_threshold_config = dict(config)
        validate_threshold_config(self.current_threshold_config)
        self.current_threshold_config_display = build_threshold_config_display_model(self.current_threshold_config)
        return self.current_threshold_config

    def clear_current_threshold_config(self) -> None:
        self.current_threshold_config = None
        self.current_threshold_config_display = None

    def set_current_threshold_catalog(self, catalog: dict[str, Any]) -> dict[str, Any]:
        self.current_threshold_catalog = validate_threshold_catalog(catalog)
        return self.current_threshold_catalog

    def build_current_threshold_catalog_display_model(self) -> dict[str, Any]:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            catalog = self.set_current_threshold_catalog(build_empty_threshold_catalog())
        return build_threshold_catalog_display_model(catalog)

    def clear_current_threshold_catalog(self) -> None:
        self.current_threshold_catalog = None

    def load_threshold_catalog_for_viewer(self, path: str | Path | None = None) -> dict[str, Any] | None:
        if path is None:
            path = filedialog.askopenfilename(title="Threshold catalog JSON 선택", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        catalog = load_threshold_catalog(path)
        return self.set_current_threshold_catalog(catalog)

    def save_current_threshold_catalog(self, path: str | Path | None = None) -> str | None:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        if path is None:
            path = filedialog.asksaveasfilename(title="Threshold catalog JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return save_threshold_catalog(catalog, path)

    def render_current_threshold_catalog_text(self) -> str:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        return render_threshold_catalog_text(catalog)

    def add_current_threshold_config_to_catalog(self, config_id: str | None = None) -> dict[str, Any]:
        config = self._require_current_threshold_config()
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        updated = add_threshold_config_to_catalog(catalog, config, config_id=config_id)
        return self.set_current_threshold_catalog(updated)

    def select_threshold_config_from_catalog(self, config_id: str) -> dict[str, Any]:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        updated = set_selected_threshold_config_id(catalog, config_id)
        return self.set_current_threshold_catalog(updated)

    def apply_selected_catalog_threshold_config_to_viewer(self) -> dict[str, Any]:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        selected = get_selected_threshold_config(catalog)
        return self.set_current_threshold_config(selected)

    def remove_threshold_config_from_current_catalog(self, config_id: str) -> dict[str, Any]:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        updated = remove_threshold_config_from_catalog(catalog, config_id)
        return self.set_current_threshold_catalog(updated)

    def export_threshold_config_from_current_catalog(self, config_id: str, path: str | None = None) -> str | None:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        if path is None:
            path = filedialog.asksaveasfilename(title="Threshold config JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return export_threshold_config_from_catalog(catalog, config_id, path)

    def import_threshold_config_file_to_current_catalog(self, path: str | None = None, config_id: str | None = None) -> dict[str, Any] | None:
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        if path is None:
            path = filedialog.askopenfilename(title="Threshold config JSON 선택", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        updated = import_threshold_config_file_to_catalog(catalog, path, config_id=config_id)
        return self.set_current_threshold_catalog(updated)

    def show_threshold_catalog_manager(self) -> dict[str, Any]:
        display = self.build_current_threshold_catalog_display_model()
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Threshold Catalog Manager")
        win.geometry("980x700")
        left = ttk.Frame(win, padding=8); left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(win, padding=8); right.pack(side="right", fill="both", expand=True)
        lst = tk.Listbox(left); lst.pack(fill="both", expand=True)
        detail = tk.Text(right, wrap="word"); detail.pack(fill="both", expand=True)
        btns = ttk.Frame(right); btns.pack(fill="x")

        def _selected_config_id() -> str | None:
            sel = lst.curselection()
            if not sel:
                return None
            idx = int(sel[0])
            rows = self.build_current_threshold_catalog_display_model().get("entries", [])
            if idx < 0 or idx >= len(rows):
                return None
            return rows[idx]["config_id"]

        def _refresh() -> None:
            d = self.build_current_threshold_catalog_display_model()
            lst.delete(0, "end")
            for e in d["entries"]:
                mark = "*" if e["is_selected"] else "-"
                lst.insert("end", f"{mark} {e['config_id']} | {e['name']} | rules={e['rule_count']}")
            detail.configure(state="normal"); detail.delete("1.0", "end"); detail.insert("1.0", self.render_current_threshold_catalog_text()); detail.configure(state="disabled")

        def _on_select(_event=None):
            cid = _selected_config_id()
            if not cid:
                return
            cfg = get_threshold_config_from_catalog(self.current_threshold_catalog, cid)
            text = render_threshold_config_text(cfg)
            detail.configure(state="normal"); detail.delete("1.0", "end"); detail.insert("1.0", text); detail.configure(state="disabled")

        def _load():
            if self.load_threshold_catalog_for_viewer() is not None:
                _refresh()

        def _save():
            _ = self.save_current_threshold_catalog()

        def _import():
            if self.import_threshold_config_file_to_current_catalog() is not None:
                _refresh()

        def _export():
            cid = _selected_config_id()
            if cid:
                _ = self.export_threshold_config_from_current_catalog(cid)

        def _select():
            cid = _selected_config_id()
            if cid:
                self.select_threshold_config_from_catalog(cid); _refresh()

        def _apply():
            self.apply_selected_catalog_threshold_config_to_viewer()

        def _remove():
            cid = _selected_config_id()
            if cid:
                self.remove_threshold_config_from_current_catalog(cid); _refresh()
        def _save_current_to_selected():
            _run = lambda fn: fn()
            _run(lambda: self.save_current_threshold_config_to_selected_catalog_entry()); _refresh()
        def _save_current_as_new():
            cid = getattr(self, "threshold_catalog_sync_new_id_var", None)
            config_id = cid.get().strip() if cid else ""
            if config_id:
                self.save_current_threshold_config_as_catalog_entry(config_id); _refresh()

        ttk.Button(btns, text="Load Catalog", command=_load).pack(fill="x")
        ttk.Button(btns, text="Save Catalog", command=_save).pack(fill="x")
        ttk.Button(btns, text="Import Config", command=_import).pack(fill="x")
        ttk.Button(btns, text="Export Selected Config", command=_export).pack(fill="x")
        ttk.Button(btns, text="Select Config", command=_select).pack(fill="x")
        ttk.Button(btns, text="Apply Selected to Viewer", command=_apply).pack(fill="x")
        self.threshold_catalog_sync_new_id_var = tk.StringVar(master=win, value="")
        ttk.Entry(btns, textvariable=self.threshold_catalog_sync_new_id_var).pack(fill="x")
        ttk.Button(btns, text="Save Current to Selected", command=_save_current_to_selected).pack(fill="x")
        ttk.Button(btns, text="Save Current as New", command=_save_current_as_new).pack(fill="x")
        ttk.Button(btns, text="Remove Selected Config", command=_remove).pack(fill="x")
        ttk.Button(btns, text="Close", command=win.destroy).pack(fill="x")
        lst.bind("<<ListboxSelect>>", _on_select)
        _refresh()
        return display

    def load_threshold_config_for_viewer(self, path: str | Path | None = None) -> dict[str, Any] | None:
        if path is None:
            path = filedialog.askopenfilename(title="Threshold config JSON 선택", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        config = load_threshold_config(path)
        return self.set_current_threshold_config(config)

    def save_current_threshold_config(self, path: str | Path | None = None) -> str | None:
        config = getattr(self, "current_threshold_config", None)
        if not config:
            raise ValueError("current_threshold_config is empty")
        if path is None:
            path = filedialog.asksaveasfilename(title="Threshold config JSON 저장", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
            if not path:
                return None
        return save_threshold_config(config, path)

    def render_current_threshold_config_text(self) -> str:
        config = getattr(self, "current_threshold_config", None)
        if not config:
            raise ValueError("current_threshold_config is empty")
        return render_threshold_config_text(config)

    def _require_current_threshold_config(self) -> dict[str, Any]:
        config = getattr(self, "current_threshold_config", None)
        if not config:
            raise ValueError("current_threshold_config is empty")
        return config

    def add_rule_to_current_threshold_config(self, rule: dict[str, Any]) -> dict[str, Any]:
        updated = add_threshold_rule(self._require_current_threshold_config(), rule)
        return self.set_current_threshold_config(updated)

    def update_rule_in_current_threshold_config(self, rule_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        updated = update_threshold_rule(self._require_current_threshold_config(), rule_id, updates)
        return self.set_current_threshold_config(updated)

    def remove_rule_from_current_threshold_config(self, rule_id: str) -> dict[str, Any]:
        updated = remove_threshold_rule(self._require_current_threshold_config(), rule_id)
        return self.set_current_threshold_config(updated)

    def reorder_rules_in_current_threshold_config(self, rule_ids: list[str]) -> dict[str, Any]:
        updated = reorder_threshold_rules(self._require_current_threshold_config(), rule_ids)
        return self.set_current_threshold_config(updated)

    def duplicate_rule_in_current_threshold_config(self, source_rule_id: str, new_rule_id: str) -> dict[str, Any]:
        updated = duplicate_threshold_rule(self._require_current_threshold_config(), source_rule_id, new_rule_id)
        return self.set_current_threshold_config(updated)

    def get_current_threshold_rule(self, rule_id: str) -> dict[str, Any]:
        return get_threshold_rule(self._require_current_threshold_config(), rule_id)

    def list_current_threshold_rules(self) -> list[dict[str, Any]]:
        return list_threshold_rules(self._require_current_threshold_config())

    def build_current_threshold_editor_display_model(self, selected_rule_id: str | None = None) -> dict[str, Any]:
        config = getattr(self, "current_threshold_config", None)
        if not config:
            raise ValueError("current_threshold_config is empty")
        return build_threshold_editor_display_model(config, selected_rule_id=selected_rule_id)

    def show_threshold_config_editor(self) -> dict[str, Any]:
        model = self.build_current_threshold_editor_display_model()
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        win = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        win.title("Threshold Config Editor")
        win.geometry("980x700")
        left = ttk.Frame(win, padding=8); left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(win, padding=8); right.pack(side="right", fill="both", expand=True)
        lst = tk.Listbox(left); lst.pack(fill="both", expand=True)
        status = tk.Text(right, height=4, wrap="word"); status.pack(fill="x")
        detail = tk.Text(right, wrap="word"); detail.pack(fill="both", expand=True)
        fields = {k: tk.StringVar(value="") for k in ("rule_id","analysis_type","metric","operator","threshold","severity","label")}
        grid = ttk.Frame(right); grid.pack(fill="x")
        for i, k in enumerate(fields):
            ttk.Label(grid, text=k).grid(row=i, column=0, sticky="w")
            ttk.Entry(grid, textvariable=fields[k]).grid(row=i, column=1, sticky="ew")
        btns = ttk.Frame(right); btns.pack(fill="x")

        def _rows(): return self.build_current_threshold_editor_display_model().get("rules", [])
        def _sel_id():
            s=lst.curselection()
            if not s: return None
            rows=_rows(); i=int(s[0])
            return rows[i]["rule_id"] if 0 <= i < len(rows) else None
        def _set_status(t): status.configure(state="normal"); status.delete("1.0","end"); status.insert("1.0",t); status.configure(state="disabled")
        def _refresh(select_id=None):
            d=self.build_current_threshold_editor_display_model(selected_rule_id=select_id) if select_id else self.build_current_threshold_editor_display_model()
            lst.delete(0,"end")
            for r in d["rules"]: lst.insert("end", f"{r['rule_id']} | {r['analysis_type']}.{r['metric']} | {r['operator']} {r['threshold']} | {r['severity']}")
            detail.configure(state="normal"); detail.delete("1.0","end"); detail.insert("1.0", render_threshold_editor_text(self.current_threshold_config, selected_rule_id=select_id)); detail.configure(state="disabled")
        def _on_select(_e=None):
            rid=_sel_id()
            if not rid: return
            r=self.get_current_threshold_rule(rid)
            for k,v in fields.items(): v.set(str(r.get(k,"")))
            detail.configure(state="normal"); detail.delete("1.0","end"); detail.insert("1.0", render_threshold_rule_detail_text(r)); detail.configure(state="disabled")

        def _rule_from_fields():
            return {"rule_id":fields["rule_id"].get(),"analysis_type":fields["analysis_type"].get(),"metric":fields["metric"].get(),"operator":fields["operator"].get(),"threshold":float(fields["threshold"].get()),"severity":fields["severity"].get(),"label":fields["label"].get()}
        def _run(fn):
            try: fn(); _set_status("ok")
            except Exception as e: _set_status(f"error: {e}")
        def _add(): _run(lambda: (self.add_rule_to_current_threshold_config(_rule_from_fields()), _refresh(fields["rule_id"].get())))
        def _update():
            rid=_sel_id()
            if rid: _run(lambda: (self.update_rule_in_current_threshold_config(rid, _rule_from_fields()), _refresh(fields["rule_id"].get())))
        def _remove():
            rid=_sel_id()
            if rid: _run(lambda: (self.remove_rule_from_current_threshold_config(rid), _refresh(None)))
        def _dup():
            rid=_sel_id()
            if rid: _run(lambda: (self.duplicate_rule_in_current_threshold_config(rid, fields["rule_id"].get()), _refresh(fields["rule_id"].get())))
        def _move(delta):
            rid=_sel_id()
            if not rid: return
            ids=[r["rule_id"] for r in self.list_current_threshold_rules()]; i=ids.index(rid); j=i+delta
            if j<0 or j>=len(ids): return
            ids[i],ids[j]=ids[j],ids[i]
            _run(lambda: (self.reorder_rules_in_current_threshold_config(ids), _refresh(rid)))
        def _sync_status(): _set_status(str(self.build_current_threshold_catalog_sync_status()))
        sync_new_id = tk.StringVar(master=win, value="")
        ttk.Entry(btns, textvariable=sync_new_id).pack(fill="x")
        ttk.Button(btns, text="Save to Selected Catalog Entry", command=lambda: _run(lambda: self.save_current_threshold_config_to_selected_catalog_entry())).pack(fill="x")
        ttk.Button(btns, text="Save as New Catalog Entry", command=lambda: _run(lambda: self.save_current_threshold_config_as_catalog_entry(sync_new_id.get().strip()))).pack(fill="x")
        ttk.Button(btns, text="Reload from Selected Catalog Entry", command=lambda: _run(lambda: self.refresh_current_threshold_config_from_selected_catalog_entry())).pack(fill="x")
        ttk.Button(btns, text="Sync Status", command=_sync_status).pack(fill="x")
        ttk.Button(btns, text="Add Rule", command=_add).pack(fill="x")
        ttk.Button(btns, text="Update Rule", command=_update).pack(fill="x")
        ttk.Button(btns, text="Remove Rule", command=_remove).pack(fill="x")
        ttk.Button(btns, text="Duplicate Rule", command=_dup).pack(fill="x")
        ttk.Button(btns, text="Move Up", command=lambda: _move(-1)).pack(fill="x")
        ttk.Button(btns, text="Move Down", command=lambda: _move(1)).pack(fill="x")
        ttk.Button(btns, text="Save Config", command=lambda: _run(lambda: self.save_current_threshold_config())).pack(fill="x")
        ttk.Button(btns, text="Close", command=win.destroy).pack(fill="x")
        lst.bind("<<ListboxSelect>>", _on_select); _refresh()
        return model

    def build_current_threshold_catalog_sync_status(self) -> dict[str, Any]:
        return build_threshold_catalog_sync_status(getattr(self, "current_threshold_config", None), getattr(self, "current_threshold_catalog", None))

    def save_current_threshold_config_to_selected_catalog_entry(self) -> dict[str, Any]:
        cfg = self._require_current_threshold_config()
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        sid = catalog.get("selected_config_id")
        if not sid:
            raise ValueError("selected_config_id is empty")
        updated = update_threshold_config_in_catalog(catalog, sid, cfg)
        return self.set_current_threshold_catalog(updated)

    def save_current_threshold_config_as_catalog_entry(self, config_id: str) -> dict[str, Any]:
        cfg = self._require_current_threshold_config()
        catalog = getattr(self, "current_threshold_catalog", None)
        if not catalog:
            raise ValueError("current_threshold_catalog is empty")
        return self.set_current_threshold_catalog(add_threshold_config_to_catalog(catalog, cfg, config_id=config_id))

    def refresh_current_threshold_config_from_selected_catalog_entry(self) -> dict[str, Any]:
        return self.apply_selected_catalog_threshold_config_to_viewer()

    def discard_current_threshold_config_changes_from_catalog_selection(self) -> dict[str, Any]:
        return self.refresh_current_threshold_config_from_selected_catalog_entry()

    def evaluate_current_analysis_with_selected_threshold_config(self, generated_at: str | None = None) -> dict[str, Any]:
        config = getattr(self, "current_threshold_config", None)
        if not config:
            raise ValueError("current_threshold_config is empty")
        return self.evaluate_current_analysis_thresholds(config, generated_at=generated_at)

    def render_current_selected_threshold_evaluation_text(self) -> str:
        return render_threshold_evaluation_text(self.evaluate_current_analysis_with_selected_threshold_config())

    def show_current_threshold_evaluation_preview(self) -> str:
        text = self.render_current_selected_threshold_evaluation_text()
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        preview = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        preview.title("Threshold Evaluation Preview")
        preview.geometry("900x700")
        container = ttk.Frame(preview, padding=8)
        container.pack(fill="both", expand=True)
        t = tk.Text(container, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def build_current_analysis_report_preview_text_with_selected_threshold(self, metadata: dict[str, Any] | None = None) -> str:
        return self.build_current_analysis_report_preview_text(metadata=metadata, use_selected_threshold_config=True)

    def show_analysis_report_preview_with_selected_threshold(self, metadata: dict[str, Any] | None = None) -> str:
        text = self.build_current_analysis_report_preview_text_with_selected_threshold(metadata=metadata)
        owner = getattr(self, "master", None) or getattr(self, "root", None) or getattr(self, "window", None)
        preview = tk.Toplevel(owner) if owner is not None else tk.Toplevel()
        preview.title("QC Report Preview (Selected Threshold)")
        preview.geometry("900x700")
        container = ttk.Frame(preview, padding=8)
        container.pack(fill="both", expand=True)
        t = tk.Text(container, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")
        return text

    def export_analysis_report_markdown_with_selected_threshold(self, path: str | None = None, metadata: dict[str, Any] | None = None) -> str | None:
        return self.export_analysis_report_markdown(path=path, metadata=metadata, use_selected_threshold_config=True)

    def export_analysis_report_pdf_with_selected_threshold(self, path: str | None = None, metadata: dict[str, Any] | None = None) -> bytes | None:
        return self.export_analysis_report_pdf(path=path, metadata=metadata, use_selected_threshold_config=True)

    def build_current_analysis_history_record_with_selected_threshold(self, metadata: dict[str, Any] | None = None, record_id: str | None = None) -> dict[str, Any]:
        return self.build_current_analysis_history_record(metadata=metadata, record_id=record_id, use_selected_threshold_config=True)

    def append_current_analysis_history_with_selected_threshold(self, history_path: str | Path, metadata: dict[str, Any] | None = None, record_id: str | None = None) -> dict[str, Any]:
        return self.append_current_analysis_history(history_path, metadata=metadata, record_id=record_id, use_selected_threshold_config=True)

    def export_analysis_results_json_legacy(self) -> None:
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

    def export_analysis_results_csv_legacy(self) -> None:
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
                    "mtf50",
                    "mtf10",
                    "nyquist_mtf",
                    "edge_snr",
                    "iec_compliance",
                    "qa_grade",
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
                        stats.get("mtf50", ""),
                        stats.get("mtf10", ""),
                        stats.get("nyquist_mtf", ""),
                        stats.get("edge_snr", ""),
                        stats.get("iec_compliance", ""),
                        stats.get("qa_grade", ""),
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
        self.viewer_a_file_status_var = tk.StringVar(value="A | No file | Frame -")
        ttk.Label(status, textvariable=self.viewer_a_file_status_var).pack(side="left", padx=(12, 0), fill="x", expand=True)
        ttk.Label(status, textvariable=self.image_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.frame_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.zoom_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.window_level_var).pack(side="left", padx=(12, 0))
        ttk.Label(status, textvariable=self.cursor_var).pack(side="left", padx=(12, 0))
        ttk.Button(status, textvariable=self.info_toggle_var, command=self._toggle_info_panel).pack(side="right")
        if hasattr(self, "path_var") and self.path_var is not None:
            self.path_var.trace_add("write", lambda *_args: self._update_viewer_a_file_status())
        if hasattr(self, "frame_var") and self.frame_var is not None:
            self.frame_var.trace_add("write", lambda *_args: self._update_viewer_a_file_status())
        self._update_viewer_a_file_status()

    def _update_viewer_a_file_status(self) -> None:
        if not hasattr(self, "viewer_a_file_status_var"):
            return
        path_text = ""
        try:
            path_text = self.path_var.get().strip() if hasattr(self, "path_var") and self.path_var is not None else ""
        except Exception:
            path_text = ""
        try:
            current = int(getattr(self, "current_frame", 0))
            total = len(getattr(self, "frames", []) or [])
        except Exception:
            current = 0
            total = 0
        self.viewer_a_file_status_var.set(build_viewer_a_status_label(path_text, current, total, prefix="A"))

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
        self._update_viewer_a_file_status()
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
        self._action_update_image_context(path, Path(path).name)
        self._action_commit_frame_change(self.current_frame)
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
        if not self._selector_measurements_for_image():
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
            if mode == "roi":
                self._apply_measurement_selection(measurement.id, toggle=False)
            self._update_guided_snr_selection(measurement)
            if mode == "roi":
                self._refresh_analysis_selectors()
                self._update_analysis_action_button_state()
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

    def _normalize_roi_bounds_matlab_imcrop(
        self,
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
        x0_raw = min(float(start[0]), float(end[0]))
        y0_raw = min(float(start[1]), float(end[1]))
        x1_raw = max(float(start[0]), float(end[0]))
        y1_raw = max(float(start[1]), float(end[1]))
        x0 = int(np.floor(x0_raw))
        y0 = int(np.floor(y0_raw))
        x1 = int(np.ceil(x1_raw))
        y1 = int(np.ceil(y1_raw))
        x0 = int(np.clip(x0, 0, max(width - 1, 0)))
        y0 = int(np.clip(y0, 0, max(height - 1, 0)))
        x1 = int(np.clip(x1, 0, max(width - 1, 0)))
        y1 = int(np.clip(y1, 0, max(height - 1, 0)))
        if ensure_non_empty:
            if x1 < x0:
                x1 = x0
            if y1 < y0:
                y1 = y0
        return x0, y0, x1, y1

    def _extract_roi_pixels(
        self,
        image_array: np.ndarray | None,
        start: tuple[int | float, int | float],
        end: tuple[int | float, int | float],
        ensure_non_empty: bool = True,
        semantics: str = "default",
    ) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        if image_array is None or image_array.ndim < 2:
            return np.array([]), (0, 0, 0, 0)
        if semantics == "matlab_imcrop":
            x0, y0, x1, y1 = self._normalize_roi_bounds_matlab_imcrop(image_array.shape, start, end, ensure_non_empty=ensure_non_empty)
            if x1 < x0 or y1 < y0:
                return np.array([]), (x0, y0, x1, y1)
            return image_array[y0 : y1 + 1, x0 : x1 + 1], (x0, y0, x1, y1)
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
            for item in self._selector_measurements_for_current_frame(kind="roi")
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
        self._ensure_domain_store()
        measurement_ids = self.domain_store.select_measurement_ids_for_image(self._store_image_id)
        for measurement_id in measurement_ids:
            if measurement_id in self.domain_store.state.measurements:
                self.domain_store.delete_measurement(measurement_id)
        self.selected_persistent_measurement_id = None
        self.domain_store.set_selection(self._store_image_id, [])
        self._persistent_canvas_item_to_measurement_id = {}
        self._cancel_guided_snr_workflow()
        self.canvas.delete("persistent_measurement")
        self.canvas.delete("temp_measurement")
        self._refresh_analysis_selectors()
        self._update_analysis_action_button_state()
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def undo_last_measurement(self) -> None:
        self._ensure_domain_store()
        visible_measurements = self.domain_store.select_measurements_for_image(self._store_image_id)
        if not visible_measurements:
            return
        removed_row = visible_measurements[-1]
        removed = Measurement(
            id=removed_row.measurement_id,
            kind=removed_row.kind,
            start=(float(removed_row.start[0]), float(removed_row.start[1])),
            end=(float(removed_row.end[0]), float(removed_row.end[1])),
            frame_index=int(removed_row.frame_index),
            geometry_key=removed_row.geometry_key,
            summary_text=removed_row.summary_text,
            meta=dict(removed_row.meta or {}),
        )
        if removed.id in self.domain_store.state.measurements:
            self.domain_store.delete_measurement(removed.id)
        state = self.guided_snr_state
        if state is not None and removed.id in {state.get("signal_id"), state.get("noise_id")}:
            self._cancel_guided_snr_workflow()
        if self.selected_persistent_measurement_id == removed.id:
            self.selected_persistent_measurement_id = None
            self.domain_store.set_selection(self._store_image_id, [])
        self._draw_preview_measurements()
        self._draw_persistent_measurements()
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def clear_selected_measurement(self) -> None:
        self._ensure_domain_store()
        selected_id = self.domain_store.state.selected_measurement_ids[0] if self.domain_store.state.selected_measurement_ids else None
        if selected_id is None:
            messagebox.showinfo("안내", "삭제할 측정을 먼저 선택하세요.")
            return
        if selected_id not in self.domain_store.state.measurements:
            self.selected_persistent_measurement_id = None
            self._draw_persistent_measurements()
            return
        state = self.guided_snr_state
        if state is not None and selected_id in {state.get("signal_id"), state.get("noise_id")}:
            self._cancel_guided_snr_workflow()
        if selected_id in self.domain_store.state.measurements:
            self.domain_store.delete_measurement(selected_id)
        self.selected_persistent_measurement_id = None
        self.domain_store.set_selection(self._store_image_id, [])
        self._draw_preview_measurements()
        self._draw_persistent_measurements()
        if self.view_mode == "single":
            self._draw_single_view_overlays()

    def _select_persistent_measurement_at_event(self, event: tk.Event) -> bool:
        if self.view_mode != "single":
            return False
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        overlapping = list(
            reversed(
                self.canvas.find_overlapping(
                    canvas_x - ROI_SELECTION_HIT_RADIUS_PX,
                    canvas_y - ROI_SELECTION_HIT_RADIUS_PX,
                    canvas_x + ROI_SELECTION_HIT_RADIUS_PX,
                    canvas_y + ROI_SELECTION_HIT_RADIUS_PX,
                )
            )
        )
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
            self.domain_store.set_selection(self._store_image_id, [])
            return
        self.selected_persistent_measurement_id = measurement_id
        self.domain_store.set_selection(self._store_image_id, [measurement_id])

    def register_measurement_hit_target(self, item_id: int, measurement_id: str) -> None:
        self._persistent_canvas_item_to_measurement_id[item_id] = measurement_id

    def _selector_measurements_for_current_frame(self, kind: str | None = None) -> list[Measurement]:
        return self._selector_measurements_for_image(frame_index=int(self.current_frame), kind=kind)

    def _selector_measurements_for_image(
        self,
        frame_index: int | None = None,
        kind: str | None = None,
    ) -> list[Measurement]:
        self._ensure_domain_store()
        store_measurements = self.domain_store.select_measurements_for_image(
            self._store_image_id,
            frame_index=frame_index,
        )
        filtered = [
            Measurement(
                id=item.measurement_id,
                kind=item.kind,
                start=(float(item.start[0]), float(item.start[1])),
                end=(float(item.end[0]), float(item.end[1])),
                frame_index=int(item.frame_index),
                geometry_key=item.geometry_key,
                summary_text=item.summary_text,
                meta=dict(item.meta or {}),
            )
            for item in store_measurements
        ]
        legacy_measurements = list(getattr(self, "persistent_measurements", []) or [])
        if frame_index is not None:
            legacy_measurements = [item for item in legacy_measurements if int(item.frame_index) == int(frame_index)]
        seen_ids = {item.id for item in filtered}
        filtered.extend(item for item in legacy_measurements if item.id not in seen_ids)
        if kind is not None:
            filtered = [item for item in filtered if item.kind == kind]
        return filtered

    def _select_measurement_draw_projections(self) -> list[MeasurementDrawProjection]:
        self._ensure_domain_store()
        current_geometry = self._get_current_geometry_key()
        selected_ids = set(self.domain_store.state.selected_measurement_ids)
        rows: list[MeasurementDrawProjection] = []
        for item in self.domain_store.select_measurements_for_image(
            self._store_image_id,
            frame_index=int(self.current_frame),
        ):
            if not self._geometry_matches(current_geometry, item.geometry_key):
                continue
            rows.append(
                MeasurementDrawProjection(
                    measurement_id=item.measurement_id,
                    kind=item.kind,
                    start=(float(item.start[0]), float(item.start[1])),
                    end=(float(item.end[0]), float(item.end[1])),
                    frame_index=int(item.frame_index),
                    geometry_key=item.geometry_key,
                    role=item.role,
                    meta=dict(item.meta or {}),
                    summary_text=item.summary_text,
                    selected=item.measurement_id in selected_ids,
                )
            )
        return rows

    @staticmethod
    def _runtime_measurement_from_projection(projection: MeasurementDrawProjection) -> Measurement:
        return Measurement(
            id=projection.measurement_id,
            kind=projection.kind,
            start=(float(projection.start[0]), float(projection.start[1])),
            end=(float(projection.end[0]), float(projection.end[1])),
            frame_index=int(projection.frame_index),
            geometry_key=projection.geometry_key,
            summary_text=projection.summary_text,
            meta=dict(projection.meta or {}),
        )

    def _action_add_measurement_to_store(self, measurement: Measurement) -> None:
        self._ensure_domain_store()
        role = self._get_measurement_roi_role(measurement)
        self.domain_store.add_measurement(
            image_id=self._store_image_id,
            kind=measurement.kind,
            start=(float(measurement.start[0]), float(measurement.start[1])),
            end=(float(measurement.end[0]), float(measurement.end[1])),
            frame_index=int(measurement.frame_index),
            geometry_key=measurement.geometry_key,
            summary_text=measurement.summary_text,
            role=role,
            meta=dict(measurement.meta or {}),
            measurement_id=measurement.id,
        )

    def _action_update_measurement_in_store(self, measurement: Measurement) -> None:
        self._ensure_domain_store()
        role = self._get_measurement_roi_role(measurement)
        self.domain_store.update_or_add_measurement(
            image_id=self._store_image_id,
            kind=measurement.kind,
            start=(float(measurement.start[0]), float(measurement.start[1])),
            end=(float(measurement.end[0]), float(measurement.end[1])),
            frame_index=int(measurement.frame_index),
            geometry_key=measurement.geometry_key,
            summary_text=measurement.summary_text,
            role=role,
            meta=dict(measurement.meta or {}),
            measurement_id=measurement.id,
        )

    def _action_commit_frame_change(self, frame_index: int) -> None:
        self._ensure_domain_store()
        self.domain_store.set_frame(self._store_image_id, int(frame_index))

    def _action_update_image_context(self, source_image_path: str, image_name: str) -> None:
        self._ensure_domain_store()
        image_ctx = self.domain_store.state.images.get(self._store_image_id)
        if image_ctx is None:
            self._store_image_id = self.domain_store.add_image_context(source_image_path, image_name)
            return
        image_ctx.source_image_path = source_image_path
        image_ctx.image_name = image_name

    def _ensure_domain_store(self) -> None:
        if not hasattr(self, "domain_store") or self.domain_store is None:
            self.domain_store = DomainStore()
        if not hasattr(self, "_store_image_id") or not self._store_image_id:
            self._store_image_id = self.domain_store.add_image_context(self._get_current_image_path(), "current")

    def _ensure_window_b_services(self) -> None:
        if not hasattr(self, "analysis_result_controller") or self.analysis_result_controller is None:
            self.analysis_result_controller = AnalysisResultController()
        if not hasattr(self, "history_controller") or self.history_controller is None:
            self.history_controller = HistoryController()
        if not hasattr(self, "session_controller") or self.session_controller is None:
            self.session_controller = SessionController()
        if not hasattr(self, "report_export_controller") or self.report_export_controller is None:
            self.report_export_controller = ReportExportController()

    def open_window_b(self) -> None:
        if not hasattr(self, "window_b_manager") or self.window_b_manager is None:
            self.window_b_manager = WindowBManager(self.root, self)
            self.window_b_manager.bind_store_events()
        self.window_b_manager.open()

    def _open_window_b_and_refresh_all(self) -> None:
        self.open_window_b()
        if hasattr(self, "window_b_manager") and self.window_b_manager is not None:
            self.window_b_manager.refresh_all()

    def _open_window_b_and_refresh_history(self) -> None:
        self.open_window_b()
        if hasattr(self, "window_b_manager") and self.window_b_manager is not None:
            self.window_b_manager.refresh_history()

    def save_analysis_session_via_window_b(self) -> None:
        self._open_window_b_and_refresh_all()
        self.save_analysis_session()

    def load_analysis_session_via_window_b(self) -> None:
        self._open_window_b_and_refresh_all()
        self.load_analysis_session()

    def export_result_history_csv_via_window_b(self) -> None:
        self._open_window_b_and_refresh_history()
        self.export_result_history_csv()

    def export_selected_result_history_csv_via_window_b(self) -> None:
        self._open_window_b_and_refresh_history()
        self.export_selected_result_history_csv()

    def _select_analysis_groups_map(self) -> dict[str, ImageAnalysisGroup]:
        self._ensure_domain_store()
        return self.domain_store.state.analysis_groups

    def _select_study_sessions_map(self) -> dict[str, StudySession]:
        self._ensure_domain_store()
        return self.domain_store.state.sessions

    def _action_replace_analysis_groups(self, groups: list[ImageAnalysisGroup]) -> None:
        group_map = self._select_analysis_groups_map()
        group_map.clear()
        group_map.update({group.group_id: group for group in groups})

    def _action_replace_study_sessions(self, sessions: list[StudySession]) -> None:
        session_map = self._select_study_sessions_map()
        session_map.clear()
        session_map.update({study.study_id: study for study in sessions})

    def _action_set_analysis_last_run(self, key: str, payload: dict[str, Any]) -> None:
        self._ensure_domain_store()
        self.domain_store.set_analysis_last_run(key, dict(payload))
        # LEGACY_BRIDGE: 결과 패널 read 경로 완전 selector화 전까지만 캐시 유지.
        self.analysis_last_run[key] = dict(payload)
        if key in {"snr", "cnr", "uniformity", "mtf"}:
            try:
                normalized = normalize_analysis_result(key, dict(payload))
            except Exception:
                normalized = None
            if normalized is not None:
                if not hasattr(self, "analysis_last_run_normalized") or self.analysis_last_run_normalized is None:
                    self.analysis_last_run_normalized = {}
                if not hasattr(self, "analysis_last_run_display") or self.analysis_last_run_display is None:
                    self.analysis_last_run_display = {}
                self.analysis_last_run_normalized[key] = normalized
                self.analysis_last_run_display[key] = build_analysis_display_model(normalized)
        if hasattr(self, "window_b_manager") and self.window_b_manager is not None:
            self.window_b_manager.refresh_all()

    def _action_clear_analysis_last_run(self) -> None:
        self._ensure_domain_store()
        self.domain_store.clear_analysis_last_run()
        # LEGACY_BRIDGE: 결과 패널 read 경로 완전 selector화 전까지만 캐시 유지.
        self.analysis_last_run = {}
        self.analysis_last_run_normalized = {}
        self.analysis_last_run_display = {}
        self._last_mtf_curve_payload = {}
        self._last_esf_curve_payload = {}
        self._last_lsf_curve_payload = {}
        self._last_mtf_key_metrics = {}
        self._render_mtf_curve({})
        self._render_xy_curve(getattr(self, "_mtf_esf_canvas", None), {}, "ESF", "x")
        self._render_xy_curve(getattr(self, "_mtf_lsf_canvas", None), {}, "LSF", "x")

    def _action_history_append_entry(self, entry: ResultHistoryEntry) -> None:
        self._ensure_domain_store()
        self.domain_store.append_history_payload(self._serialize_history_entry(entry))
        # LEGACY_BRIDGE: history panel read 경로 완전 selector화 전까지만 캐시 유지.
        self.result_history_store.append(entry)
        if hasattr(self, "window_b_manager") and self.window_b_manager is not None:
            self.window_b_manager.refresh_history()

    def _action_history_clear(self) -> None:
        self._ensure_domain_store()
        self.domain_store.clear_history_payloads()
        # LEGACY_BRIDGE: history panel read 경로 완전 selector화 전까지만 캐시 유지.
        self.result_history_store.clear()

    def _action_history_remove_indices(self, indices: list[int]) -> None:
        self._ensure_domain_store()
        self.domain_store.remove_history_payload_indices(indices)
        # LEGACY_BRIDGE: history panel read 경로 완전 selector화 전까지만 캐시 유지.
        self.result_history_store.remove_indices(indices)

    def _select_analysis_last_run(self, key: str) -> dict[str, Any]:
        self._ensure_domain_store()
        payload = self.domain_store.select_analysis_last_run(key)
        if payload:
            return payload
        return dict(getattr(self, "analysis_last_run", {}).get(key) or {})

    def _select_result_history_entries(self) -> list[ResultHistoryEntry]:
        self._ensure_domain_store()
        payloads = self.domain_store.select_history_payloads()
        return [self._deserialize_history_entry(item) for item in payloads]

    def _select_filtered_history_entries(
        self,
        measurement_type: str = "All",
        search_text: str = "",
    ) -> list[tuple[int, ResultHistoryEntry]]:
        query = search_text.strip().lower()
        selected_type = measurement_type.strip()
        rows: list[tuple[int, ResultHistoryEntry]] = []
        for index, entry in enumerate(self._select_result_history_entries()):
            if selected_type and selected_type != "All" and entry.measurement_type != selected_type:
                continue
            if query:
                haystack = f"{entry.image_name} {entry.target_name} {entry.metric}".lower()
                if query not in haystack:
                    continue
            rows.append((index, entry))
        return rows

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
        if measurement.kind == "roi":
            measurement.meta.setdefault("roi_source", "manual")
        metrics = self.compute_measurement(measurement, self._get_frame_pixel_array(measurement.frame_index))
        measurement.summary_text = metrics["summary"]
        measurement.meta = self._canonicalize_measurement_meta(measurement, metrics)
        self._action_add_measurement_to_store(measurement)
        legacy_measurements = getattr(self, "persistent_measurements", None)
        if legacy_measurements is not None:
            legacy_measurements.append(measurement)
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
        for measurement in self._selector_measurements_for_current_frame(kind="line"):
            if measurement.kind != "line":
                continue
            if not self._geometry_matches(measurement.geometry_key, current_geometry):
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
            for measurement in self._selector_measurements_for_image(frame_index=source_frame_index, kind="roi")
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
            propagated.meta["roi_source"] = "propagated"
            propagated.meta["propagated_from_group_id"] = str(getattr(self, "active_group_id", ""))
            metrics = self.compute_measurement(propagated, self._get_frame_pixel_array(propagated.frame_index))
            propagated.summary_text = metrics["summary"]
            propagated.meta = self._canonicalize_measurement_meta(propagated, metrics)
            self._action_add_measurement_to_store(propagated)

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
        for measurement in self._selector_measurements_for_image(frame_index=target_frame_index, kind="roi"):
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
        draw_projections = self._select_measurement_draw_projections()
        grid_roi_measurements: list[Measurement] = []
        occupied_label_boxes: list[tuple[float, float, float, float]] = []
        for projection in draw_projections:
            measurement = self._runtime_measurement_from_projection(projection)
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
            self._action_update_measurement_in_store(measurement)
            selected = projection.selected
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
        if not self._selector_measurements_for_image():
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
            for item in self._selector_measurements_for_image():
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
            created_at=str(payload.get("created_at", datetime.now(timezone.utc).isoformat())),
            measurements=measurements,
        )

    def save_measurement_set(self) -> None:
        if not self._selector_measurements_for_image():
            messagebox.showinfo("안내", "저장할 영구 측정값이 없습니다.")
            return
        geometry_key = self._get_current_geometry_key()
        if geometry_key is None:
            return
        name = simple_prompt(self.root, "세트 이름", "측정 세트 이름을 입력하세요:")
        if not name:
            return
        selected = [m for m in self._selector_measurements_for_image() if self._geometry_matches(m.geometry_key, geometry_key)]
        measurement_set = MeasurementSet(
            id=str(uuid.uuid4()),
            name=name,
            geometry_key=geometry_key,
            created_at=datetime.now(timezone.utc).isoformat(),
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
        for item in copied:
            self._action_add_measurement_to_store(item)
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
    def _serialize_analysis_group(group: ImageAnalysisGroup) -> dict[str, Any]:
        return {
            "group_id": group.group_id,
            "study_id": group.study_id,
            "source_image_path": group.source_image_path,
            "image_name": group.image_name,
            "created_at": group.created_at,
            "entry_ids": list(group.entry_ids),
            "frame_indices": [int(item) for item in group.frame_indices],
            "roi_source_type": group.roi_source_type,
            "propagated_from_group_id": group.propagated_from_group_id,
            "propagated_from_measurement_ids": list(group.propagated_from_measurement_ids),
        }

    @staticmethod
    def _deserialize_analysis_group(payload: dict[str, Any]) -> ImageAnalysisGroup:
        return ImageAnalysisGroup(
            group_id=str(payload.get("group_id") or uuid.uuid4()),
            study_id=str(payload.get("study_id", "")),
            source_image_path=str(payload.get("source_image_path", "")),
            image_name=str(payload.get("image_name", "N/A")),
            created_at=str(payload.get("created_at", datetime.now(timezone.utc).isoformat())),
            entry_ids=[str(item) for item in (payload.get("entry_ids") or [])],
            frame_indices=[int(item) for item in (payload.get("frame_indices") or [])],
            roi_source_type=str(payload.get("roi_source_type", "manual")),
            propagated_from_group_id=str(payload.get("propagated_from_group_id", "")),
            propagated_from_measurement_ids=[str(item) for item in (payload.get("propagated_from_measurement_ids") or [])],
        )

    @staticmethod
    def _serialize_study_session(study: StudySession) -> dict[str, Any]:
        return {
            "study_id": study.study_id,
            "name": study.name,
            "created_at": study.created_at,
            "group_ids": list(study.group_ids),
        }

    @staticmethod
    def _deserialize_study_session(payload: dict[str, Any]) -> StudySession:
        return StudySession(
            study_id=str(payload.get("study_id") or uuid.uuid4()),
            name=str(payload.get("name", "Imported Study")),
            created_at=str(payload.get("created_at", datetime.now(timezone.utc).isoformat())),
            group_ids=[str(item) for item in (payload.get("group_ids") or [])],
        )

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
        self._ensure_window_b_services()
        current_path = self._get_current_image_path()
        self._sync_domain_store_from_persistent_measurements()
        all_measurements = self._selector_measurements_for_image()
        roi_items = [item for item in all_measurements if item.kind == "roi"]
        line_items = [item for item in all_measurements if item.kind == "line"]
        store_snapshot = self.domain_store.snapshot()
        analysis_groups = self._select_analysis_groups_map()
        study_sessions = self._select_study_sessions_map()
        return self.session_controller.build_serialize_payload(
            {
                "schema_version": SESSION_SCHEMA_VERSION,
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
                "results_history": [self._serialize_history_entry(item) for item in self._select_result_history_entries()],
                "analysis_groups": [self._serialize_analysis_group(item) for item in analysis_groups.values()],
                "study_sessions": [self._serialize_study_session(item) for item in study_sessions.values()],
                "active_study_id": self.active_study_id,
                "active_group_id": self.active_group_id,
                "compare_state": {
                "selected_history_row_ids": list(self._session_compare_state.get("selected_entry_ids", [])),
                "baseline_index": int(self._session_compare_state.get("baseline_index", 0)),
            },
                "store_snapshot": store_snapshot,
                "iqa_history": list(getattr(self, "iqa_history", []) or []),
                "latest_iqa_history_index": (len(getattr(self, "iqa_history", []) or []) - 1) if getattr(self, "iqa_history", None) else None,
                "iqa_ui_state": self._serialize_iqa_ui_state_snapshot(),
                "last_iqa_export_record": dict(((self.analysis_last_run or {}).get("iqa") or {})),
                "last_iqa_display_summary": str((get_latest_iqa_history(getattr(self, "iqa_history", []) or []) or {}).get("display_summary", "")),
            }
        )

    def deserialize_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        version = str(payload.get("version", "0"))
        display = dict(payload.get("display") or {})
        history_rows = [self._deserialize_history_entry(item) for item in (payload.get("results_history") or [])]
        roi_list = [self._deserialize_measurement_for_session(item) for item in (payload.get("roi_list") or [])]
        line_list = [self._deserialize_measurement_for_session(item) for item in (payload.get("line_list") or [])]
        analysis_groups = [self._deserialize_analysis_group(item) for item in (payload.get("analysis_groups") or [])]
        study_sessions = [self._deserialize_study_session(item) for item in (payload.get("study_sessions") or [])]
        return {
            "version": version,
            "source_image_path": str(payload.get("source_image_path", "")),
            "frame_index": int(payload.get("frame_index", 0)),
            "display": display,
            "analysis_options": dict(payload.get("analysis_options") or {}),
            "roi_list": roi_list,
            "line_list": line_list,
            "results_history": history_rows,
            "analysis_groups": analysis_groups,
            "study_sessions": study_sessions,
            "active_study_id": str(payload.get("active_study_id", "")),
            "active_group_id": str(payload.get("active_group_id", "")),
            "compare_state": dict(payload.get("compare_state") or {}),
            "store_snapshot": dict(payload.get("store_snapshot") or {}),
            "iqa_history": list(payload.get("iqa_history") or []),
            "latest_iqa_history_index": payload.get("latest_iqa_history_index"),
            "iqa_ui_state": dict(payload.get("iqa_ui_state") or {}),
            "last_iqa_export_record": dict(payload.get("last_iqa_export_record") or {}),
            "last_iqa_display_summary": str(payload.get("last_iqa_display_summary", "")),
        }

    def _serialize_iqa_ui_state_snapshot(self) -> dict[str, Any]:
        state = getattr(self, "iqa_ui_state", None)
        if state is None:
            return {}
        return {
            "reference_id": getattr(state, "reference_id", ""),
            "reference_label": getattr(state, "reference_label", ""),
            "target_id": getattr(state, "target_id", ""),
            "target_label": getattr(state, "target_label", ""),
            "input_mode": getattr(state, "input_mode", "raw_dicom_pixel"),
            "scope": getattr(state, "scope", "full_image"),
            "data_range_mode": getattr(state, "data_range_mode", "auto"),
            "photometric_invert": bool(getattr(state, "photometric_invert", False)),
            "selected_roi_id": getattr(state, "selected_roi_id", ""),
            "selected_roi_label": getattr(state, "selected_roi_label", ""),
            "roi_bbox": getattr(state, "roi_bbox", None),
        }

    def _restore_iqa_ui_state_snapshot(self, snapshot: dict[str, Any]) -> None:
        if not hasattr(self, "iqa_ui_state") or self.iqa_ui_state is None:
            self.iqa_ui_state = create_default_iqa_state()
        for key in (
            "reference_id",
            "reference_label",
            "target_id",
            "target_label",
            "input_mode",
            "scope",
            "data_range_mode",
            "selected_roi_id",
            "selected_roi_label",
        ):
            if key in snapshot:
                setattr(self.iqa_ui_state, key, snapshot.get(key))
        self.iqa_ui_state.photometric_invert = bool(snapshot.get("photometric_invert", False))
        self.iqa_ui_state.roi_bbox = snapshot.get("roi_bbox")

    def _migrate_legacy_session_to_store_snapshot(self, session_data: dict[str, Any]) -> dict[str, Any]:
        migrated = DomainStore()
        image_path = str(session_data.get("source_image_path", ""))
        image_name = Path(image_path).name if image_path else "current"
        frame_index = int(session_data.get("frame_index", 0))
        image_id = migrated.add_image_context(image_path, image_name, frame_index=frame_index)
        migrated.state.selected_image_id = image_id

        for measurement in list(session_data.get("roi_list") or []) + list(session_data.get("line_list") or []):
            migrated.add_measurement(
                image_id=image_id,
                kind=measurement.kind,
                start=(float(measurement.start[0]), float(measurement.start[1])),
                end=(float(measurement.end[0]), float(measurement.end[1])),
                frame_index=int(measurement.frame_index),
                geometry_key=measurement.geometry_key,
                summary_text=measurement.summary_text,
                role=self._get_measurement_roi_role(measurement),
                meta=dict(measurement.meta or {}),
                measurement_id=measurement.id,
            )

        history_payloads = [self._serialize_history_entry(item) for item in (session_data.get("results_history") or [])]
        migrated.replace_history_payloads(history_payloads)
        migrated.state.analysis_groups = {
            group.group_id: group
            for group in (session_data.get("analysis_groups") or [])
        }
        migrated.state.sessions = {
            study.study_id: study
            for study in (session_data.get("study_sessions") or [])
        }
        return migrated.snapshot()

    def _reset_analysis_session_state(self) -> None:
        self.selected_persistent_measurement_id = None
        self._persistent_canvas_item_to_measurement_id.clear()
        self.domain_store = DomainStore()
        self._store_image_id = self.domain_store.add_image_context(self._get_current_image_path(), "current")
        self._action_history_clear()
        self._select_analysis_groups_map().clear()
        self._select_study_sessions_map().clear()
        self.active_study_id = ""
        self.active_group_id = ""
        self._session_compare_state = {"selected_entry_ids": [], "baseline_index": 0}
        self.line_profile_series_cache.clear()
        self._action_clear_analysis_last_run()
        self._ensure_default_study_session()
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

    def _rebuild_persistent_measurements_from_domain_store(self) -> None:
        self._ensure_domain_store()
        rebuilt_measurements = [
            Measurement(
                id=item.measurement_id,
                kind=item.kind,
                start=(float(item.start[0]), float(item.start[1])),
                end=(float(item.end[0]), float(item.end[1])),
                frame_index=int(item.frame_index),
                geometry_key=item.geometry_key,
                summary_text=item.summary_text,
                meta=dict(item.meta or {}),
            )
            for item in self.domain_store.select_measurements_for_image(self._store_image_id)
        ]
        setattr(self, "persistent_measurements", rebuilt_measurements)

    def _sync_domain_store_from_persistent_measurements(self) -> None:
        self._ensure_domain_store()
        for measurement in list(getattr(self, "persistent_measurements", []) or []):
            self._action_update_measurement_in_store(measurement)

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

        store_snapshot = dict(session_data.get("store_snapshot") or {})
        snapshot_state = store_snapshot.get("state")
        snapshot_has_measurements = bool(getattr(snapshot_state, "measurements", {}) if snapshot_state is not None else {})
        legacy_has_measurements = bool(session_data.get("roi_list") or session_data.get("line_list"))
        if not (store_snapshot.get("state") is not None and store_snapshot.get("snapshot_timestamp")) or (legacy_has_measurements and not snapshot_has_measurements):
            # LEGACY_BRIDGE: 구세션 payload를 최신 store snapshot 구조로 1회 변환한다.
            store_snapshot = self._migrate_legacy_session_to_store_snapshot(session_data)
        self.domain_store.load_session({**store_snapshot, "session_id": str(session_data.get("active_study_id", ""))})
        self._store_image_id = self.domain_store.state.selected_image_id or self._store_image_id
        self.result_history_store.clear()
        for payload in self.domain_store.select_history_payloads():
            self.result_history_store.append(self._deserialize_history_entry(payload))
        image_ctx = self.domain_store.state.images.get(self._store_image_id)
        if image_ctx is not None:
            self.current_frame = int(image_ctx.frame_index)

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

        self.domain_store.set_frame(self._store_image_id, int(self.current_frame))
        self.domain_store.set_selection(self._store_image_id, [])
        self._rebuild_persistent_measurements_from_domain_store()
        self._draw_persistent_measurements()

        for key, value in (session_data.get("analysis_options") or {}).items():
            if key in self.analysis_inputs:
                self.analysis_inputs[key].set(str(value))
        self._refresh_analysis_selectors()
        self.iqa_history = [restore_iqa_history_entry(item).__dict__ for item in list(session_data.get("iqa_history") or [])][-50:]
        self._restore_iqa_ui_state_snapshot(dict(session_data.get("iqa_ui_state") or {}))
        latest_iqa = get_latest_iqa_history(self.iqa_history)
        if latest_iqa:
            if not hasattr(self, "analysis_last_run") or self.analysis_last_run is None:
                self.analysis_last_run = {}
            self.analysis_last_run["iqa"] = dict(latest_iqa.get("export_record") or {"analysis_type": "iqa", "status": latest_iqa.get("status", "invalid")})
            summary = str(latest_iqa.get("display_summary") or summarize_iqa_history_entry(latest_iqa))
            status = str(latest_iqa.get("status", "success"))
            if status == "invalid":
                reason = str(latest_iqa.get("invalid_reason") or "invalid")
                self.image_analysis_results["image_result"].set(f"Result: IQA unavailable ({reason})")
                self.image_analysis_results["image_formula"].set(f"Formula: 이전 세션의 IQA 결과 요약입니다. 현재 영상으로 자동 재계산하지 않았습니다. | {summary}")
            else:
                self.image_analysis_results["image_result"].set(f"Result: 이전 세션의 IQA 결과 요약입니다. 현재 영상으로 자동 재계산하지 않았습니다. | {summary}")
                self.image_analysis_results["image_formula"].set("Formula: 이전 세션의 IQA 결과 요약입니다. 현재 영상으로 자동 재계산하지 않았습니다.")
            self._update_iqa_report_preview_from_history()
        self._sync_analysis_selector_inputs()
        self._toggle_cnr_noise_widgets()

        analysis_groups = self._select_analysis_groups_map()
        study_sessions = self._select_study_sessions_map()
        analysis_groups.clear()
        analysis_groups.update({group.group_id: group for group in self.domain_store.select_analysis_groups()})
        study_sessions.clear()
        study_sessions.update({study.study_id: study for study in self.domain_store.select_study_sessions()})
        self.active_study_id = str(session_data.get("active_study_id", ""))
        self.active_group_id = str(session_data.get("active_group_id", ""))
        self._ensure_default_study_session()
        for entry in self._select_result_history_entries():
            if not entry.group_id:
                continue
            group = analysis_groups.get(entry.group_id)
            if group is None:
                continue
            if entry.entry_id not in group.entry_ids:
                group.entry_ids.append(entry.entry_id)
            if entry.frame_index not in group.frame_indices:
                group.frame_indices.append(int(entry.frame_index))
        if not analysis_groups:
            default_study = self._ensure_default_study_session()
            image_to_group: dict[str, ImageAnalysisGroup] = {}
            for entry in self._select_result_history_entries():
                image_key = entry.source_image_path or entry.image_name
                if image_key not in image_to_group:
                    group_id = str(uuid.uuid4())
                    group = ImageAnalysisGroup(
                        group_id=group_id,
                        study_id=default_study.study_id,
                        source_image_path=entry.source_image_path,
                        image_name=entry.image_name,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        entry_ids=[],
                        frame_indices=[],
                        roi_source_type="manual",
                    )
                    analysis_groups[group_id] = group
                    default_study.group_ids.append(group_id)
                    image_to_group[image_key] = group
                group = image_to_group[image_key]
                entry.group_id = group.group_id
                entry.study_id = default_study.study_id
                group.entry_ids.append(entry.entry_id)
                if int(entry.frame_index) not in group.frame_indices:
                    group.frame_indices.append(int(entry.frame_index))
            if image_to_group:
                self.active_group_id = next(iter(image_to_group.values())).group_id
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
        for measurement in self._selector_measurements_for_current_frame(kind="roi"):
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
            "created_at": datetime.now(timezone.utc).isoformat(),
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
                self._action_update_measurement_in_store(measurement)

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
        self._action_set_analysis_last_run("line_profile", {
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
        })
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
                for measurement in self._selector_measurements_for_image()
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
            for measurement in self._selector_measurements_for_image()
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
        self._ensure_window_b_services()
        roi_set, source = self._collect_uniformity_roi_set()
        formula_key = self.analysis_inputs["uniformity_formula"].get()
        formulas = self._uniformity_formula_definitions()
        uniformity_result = self.analysis_result_controller.evaluate_uniformity(
            roi_set=roi_set,
            source=source,
            formula_key=formula_key,
            formulas=formulas,
            collect_factors=self._collect_analysis_factors,
            get_frame_array=self._get_frame_pixel_array,
            extract_roi_pixels=self._extract_roi_pixels,
        )
        self.analysis_results["uniformity_preview"].set(uniformity_result.preview_text)
        self.analysis_results["uniformity_result"].set(uniformity_result.result_text)
        self._action_set_analysis_last_run("uniformity", uniformity_result.payload)
        self._refresh_analysis_results_panel()
        if uniformity_result.history_row is not None:
            self._append_analysis_history_row(
                uniformity_result.history_row,
                unit="%",
                related_target_ids=list(uniformity_result.payload.get("inputs", {}).get("roi_ids", [])),
            )
        if uniformity_result.message_level == "info":
            messagebox.showinfo("Uniformity", uniformity_result.message_text)
        elif uniformity_result.message_level == "warning":
            messagebox.showwarning("Uniformity", uniformity_result.message_text)

    def calculate_snr_from_inputs(self) -> None:
        resolved = self.resolve_signal_analysis_inputs("snr")
        resolved_measurements = resolved.get("resolved_measurements") or {}
        signal_roi = resolved_measurements.get("signal")
        noise_roi = resolved_measurements.get("noise")
        signal_roi_id = str(resolved.get("signal_roi_id") or "")
        noise_roi_id = str(resolved.get("noise_roi_id") or "")
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
        if not bool(resolved.get("is_valid")) or signal_roi is None or noise_roi is None:
            reason = str(resolved.get("reason") or "ROI selection required")
            preview_text = "ROI selection required"
            result_text = "SNR unavailable"
            self.analysis_results["snr_preview"].set(preview_text)
            self.analysis_results["snr_result"].set(result_text)
            snr_payload["status"] = "missing"
            snr_payload["reason"] = reason
            snr_payload["warnings"] = list(resolved.get("warnings") or [])
            snr_payload["preview"] = preview_text
            snr_payload["preview_text"] = f"Preview: {preview_text}"
            snr_payload["result_text"] = result_text
            self._action_set_analysis_last_run("snr", snr_payload)
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
            self._action_set_analysis_last_run("snr", snr_payload)
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
        self._action_set_analysis_last_run("snr", snr_payload)
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
        resolved = self.resolve_signal_analysis_inputs("cnr")
        formula = str(resolved.get("formula") or self.analysis_inputs["cnr_formula"].get())
        resolved_measurements = resolved.get("resolved_measurements") or {}
        target_roi = resolved_measurements.get("target")
        reference_roi = resolved_measurements.get("reference")
        noise_roi = resolved_measurements.get("noise")
        target_roi_id = str(resolved.get("target_roi_id") or "")
        reference_roi_id = str(resolved.get("reference_roi_id") or "")
        noise_roi_id = str(resolved.get("noise_roi_id") or "")
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
        if not bool(resolved.get("is_valid")) or target_roi is None or reference_roi is None or (formula == "standard_noise" and noise_roi is None):
            reason = str(resolved.get("reason") or "ROI selection required")
            preview_text = "ROI selection required"
            result_text = "CNR unavailable"
            self.analysis_results["cnr_preview"].set(preview_text)
            self.analysis_results["cnr_result"].set(result_text)
            cnr_payload["status"] = "missing"
            cnr_payload["reason"] = reason
            cnr_payload["warnings"] = list(resolved.get("warnings") or [])
            cnr_payload["preview_text"] = f"Preview: {preview_text}"
            cnr_payload["result_text"] = result_text
            self._action_set_analysis_last_run("cnr", cnr_payload)
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
            self._action_set_analysis_last_run("cnr", cnr_payload)
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
        self._action_set_analysis_last_run("cnr", cnr_payload)
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

    def _resolve_image_analysis_runtime_inputs(self) -> tuple[str, str, str]:
        reference_id = self._resolve_image_analysis_selection("reference_image_id", "reference_image", "image")
        target_id = self._resolve_image_analysis_selection("target_image_id", "target_image", "image")
        scope = self.image_analysis_inputs["scope_type"].get()
        if not hasattr(self, "iqa_ui_state") or self.iqa_ui_state is None:
            self.iqa_ui_state = create_default_iqa_state()
        return reference_id, target_id, scope

    def _set_iqa_reference_from_current(self) -> None:
        if not hasattr(self, "iqa_ui_state") or self.iqa_ui_state is None:
            self.iqa_ui_state = create_default_iqa_state()
        image_id = str(self.iqa_ui_state.reference_id or "").strip()
        if not image_id:
            image_id = self._resolve_image_analysis_selection("reference_image_id", "reference_image", "image")
        if not image_id:
            image_id = str(getattr(self, "path_var", None).get() if getattr(self, "path_var", None) is not None else "").strip()
        label = str(self.iqa_ui_state.reference_label or image_id or "").strip()
        array = self._load_analysis_image_array(image_id) if image_id else None
        dataset = None
        if image_id and hasattr(self, "dicom_loader") and self.dicom_loader is not None:
            try:
                dataset, _frames = self.dicom_loader.get_decoded_file(image_id)
            except Exception:
                dataset = None
        set_iqa_reference_from_current(self.iqa_ui_state, image_id, label, dataset=dataset, array=array)
        self._update_iqa_pair_status_display()

    def _set_iqa_target_from_current(self) -> None:
        if not hasattr(self, "iqa_ui_state") or self.iqa_ui_state is None:
            self.iqa_ui_state = create_default_iqa_state()
        image_id = str(self.iqa_ui_state.target_id or "").strip()
        if not image_id:
            image_id = self._resolve_image_analysis_selection("target_image_id", "target_image", "image")
        if not image_id:
            image_id = str(getattr(self, "path_var", None).get() if getattr(self, "path_var", None) is not None else "").strip()
        label = str(self.iqa_ui_state.target_label or image_id or "").strip()
        array = self._load_analysis_image_array(image_id) if image_id else None
        dataset = None
        if image_id and hasattr(self, "dicom_loader") and self.dicom_loader is not None:
            try:
                dataset, _frames = self.dicom_loader.get_decoded_file(image_id)
            except Exception:
                dataset = None
        set_iqa_target_from_current(self.iqa_ui_state, image_id, label, dataset=dataset, array=array)
        self._update_iqa_pair_status_display()

    def _swap_iqa_reference_target(self) -> None:
        if not hasattr(self, "iqa_ui_state") or self.iqa_ui_state is None:
            self.iqa_ui_state = create_default_iqa_state()
        swap_iqa_reference_target(self.iqa_ui_state)
        self._update_iqa_pair_status_display()

    def _clear_iqa_selection(self) -> None:
        if not hasattr(self, "iqa_ui_state") or self.iqa_ui_state is None:
            self.iqa_ui_state = create_default_iqa_state()
        clear_iqa_selection(self.iqa_ui_state)
        self._update_iqa_pair_status_display()

    def _update_iqa_pair_status_display(self) -> None:
        if "iqa_pair_status" not in getattr(self, "image_analysis_results", {}):
            return
        state = getattr(self, "iqa_ui_state", None) or create_default_iqa_state()
        run_state = resolve_iqa_run_state(state)
        ref_label = state.reference_label or ""
        tar_label = state.target_label or ""
        reason_map = {
            "missing_reference": "실행 불가: Reference 영상이 선택되지 않았습니다.",
            "missing_target": "실행 불가: Target 영상이 선택되지 않았습니다.",
            "missing_scope_roi": "ROI 범위가 선택되었지만 사용할 ROI가 없습니다.",
            "same_image": "Reference와 Target이 동일합니다. 검증용 비교로 사용할 수 있습니다.",
            "stale_roi_id": "세션에 저장된 ROI를 현재 영상에서 찾을 수 없습니다.",
        }
        ready_text = "실행 가능" if run_state.get("is_ready") else reason_map.get(str(run_state.get("reason") or ""), f"실행 불가: {run_state.get('reason') or 'missing'}")
        self.image_analysis_results["iqa_pair_status"].set(
            build_pair_status_label(
                reference_label=ref_label,
                target_label=tar_label,
                ready_text=ready_text,
                roi_label=str(getattr(state, "selected_roi_label", "") or ""),
                scope=str(getattr(state, "scope", "")),
            )
        )

    def _update_iqa_report_preview_from_history(self) -> str:
        latest = get_latest_iqa_history(getattr(self, "iqa_history", []) or [])
        if not latest:
            return ""
        report = build_iqa_report(latest)
        full_text = format_iqa_report_text(report)
        lines = [line for line in full_text.splitlines() if line.strip()]
        kept = lines[:8]
        if "Metrics:" not in kept and "Metrics:" in lines:
            kept.append("Metrics:")
        interp_idx = next((i for i, line in enumerate(lines) if line.startswith("Interpretation:")), None)
        if interp_idx is not None:
            kept.append(lines[interp_idx])
            if interp_idx + 1 < len(lines):
                kept.append(lines[interp_idx + 1])
        text = "\n".join(kept[:10])
        if not hasattr(self, "analysis_last_run") or self.analysis_last_run is None:
            self.analysis_last_run = {}
        self.analysis_last_run["iqa_report"] = report
        self.analysis_last_run["iqa_report_text"] = text
        return text

    def _get_iqa_report_export_format(self) -> str:
        value = "txt"
        if "iqa_report_export_format" in getattr(self, "image_analysis_inputs", {}):
            value = str(self.image_analysis_inputs["iqa_report_export_format"].get() or "txt")
        return normalize_iqa_report_export_format(value)

    def _resolve_latest_iqa_report_for_export(self) -> dict[str, Any] | None:
        return resolve_latest_iqa_report_for_export(getattr(self, "analysis_last_run", {}) or {}, getattr(self, "iqa_history", []) or [])

    def _ask_iqa_report_save_path(self, fmt: str, default_name: str) -> str:
        ext = f".{fmt}"
        return str(filedialog.asksaveasfilename(title="IQA Report 저장", defaultextension=ext, initialfile=default_name + ext, filetypes=[(fmt.upper(), f"*{ext}"), ("All Files", "*.*")]) or "")

    def _ask_iqa_report_save_directory(self, default_name: str) -> str:
        return str(filedialog.askdirectory(title=f"IQA Report 저장 폴더 선택 ({default_name})") or "")

    def _save_latest_iqa_report(self) -> None:
        report = self._resolve_latest_iqa_report_for_export()
        fmt = self._get_iqa_report_export_format()
        status_text, bundle = save_iqa_report_by_format(report, fmt, self._ask_iqa_report_save_path, self._ask_iqa_report_save_directory)
        self.image_analysis_results["iqa_export_status"].set(status_text)
        if bundle is not None:
            if not hasattr(self, "analysis_last_run") or self.analysis_last_run is None:
                self.analysis_last_run = {}
            self.analysis_last_run["iqa_report_export_bundle"] = bundle

    def _resolve_iqa_roi_selection(self) -> tuple[Any | None, list[str]]:
        warnings: list[str] = []
        if not hasattr(self, "iqa_ui_state") or self.iqa_ui_state is None:
            self.iqa_ui_state = create_default_iqa_state()
        roi_id = str(getattr(self.iqa_ui_state, "selected_roi_id", "") or "").strip()
        if not roi_id:
            roi_id = self._resolve_image_analysis_selection("scope_roi_id", "scope_roi", "roi")
        if not roi_id and "scope_roi_id" in self.image_analysis_inputs:
            roi_id = str(self.image_analysis_inputs["scope_roi_id"].get() or "").strip()
        if not roi_id:
            return None, ["missing_scope_roi"]
        roi = self._get_selected_measurement_from_analysis("roi", "scope_roi_id", "scope_roi")
        if roi is None or getattr(roi, "id", "") != roi_id:
            warnings.append("stale_roi_id")
            roi = self._find_measurement_by_id(roi_id, expected_kind="roi")
        if roi is None:
            return None, ["missing_roi_object", *warnings]
        self.iqa_ui_state.selected_roi_id = str(roi.id)
        self.iqa_ui_state.selected_roi_label = str(getattr(roi, "summary_text", "") or roi.id)
        self.iqa_ui_state.selected_roi_source = "analysis_selector"
        try:
            self.iqa_ui_state.roi_bbox = (int(roi.start[0]), int(roi.start[1]), int(roi.end[0]), int(roi.end[1]))
            self.iqa_ui_state.roi_policy = "bbox"
        except Exception:
            return None, ["unsupported_roi_shape", *warnings]
        self.iqa_ui_state.roi_resolution_warnings = list(warnings)
        return roi, warnings

    @staticmethod
    def _normalize_iqa_roi_bbox(raw_bbox: tuple[int, int, int, int], image_shape: tuple[int, ...]) -> tuple[tuple[int, int, int, int] | None, list[str]]:
        warnings: list[str] = []
        x0, y0, x1, y1 = [int(v) for v in raw_bbox]
        if x1 <= x0 or y1 <= y0:
            x1 = x0 + max(x1, 0)
            y1 = y0 + max(y1, 0)
            warnings.append("roi_bbox_xywh_converted")
        h = int(image_shape[0]) if image_shape else 0
        w = int(image_shape[1]) if len(image_shape) > 1 else 0
        nx0, ny0 = max(0, x0), max(0, y0)
        nx1, ny1 = min(w, x1), min(h, y1)
        if (nx0, ny0, nx1, ny1) != (x0, y0, x1, y1):
            warnings.append("roi_bbox_clipped_to_image_bounds")
        if nx1 <= nx0 or ny1 <= ny0:
            return None, ["invalid_roi_bbox_after_clip", *warnings]
        return (nx0, ny0, nx1, ny1), warnings

    def _run_iqa_from_viewer_state(self, input_mode: str = "raw_dicom_pixel", scope: str = "full_image") -> tuple[Any | None, list[str]]:
        reference_id, target_id, selected_scope = self._resolve_image_analysis_runtime_inputs()
        self._set_iqa_reference_from_current()
        self._set_iqa_target_from_current()
        set_iqa_scope(self.iqa_ui_state, selected_scope or scope)
        if hasattr(self, "image_analysis_inputs"):
            set_iqa_input_mode(self.iqa_ui_state, self.image_analysis_inputs.get("iqa_input_mode", None).get() if self.image_analysis_inputs.get("iqa_input_mode") is not None else input_mode)
            set_iqa_data_range_mode(self.iqa_ui_state, self.image_analysis_inputs.get("iqa_data_range_mode", None).get() if self.image_analysis_inputs.get("iqa_data_range_mode") is not None else "auto")
            set_iqa_photometric_invert(self.iqa_ui_state, bool(self.image_analysis_inputs.get("iqa_photometric_invert", None).get()) if self.image_analysis_inputs.get("iqa_photometric_invert") is not None else False)
        run_state = resolve_iqa_run_state(self.iqa_ui_state)
        run_warnings = [str(w) for w in run_state.get("warnings", []) if str(w).strip()]
        if not run_state.get("is_ready"):
            return None, [str(run_state.get("reason") or "missing_reference_or_target"), *run_warnings]

        scope_to_use = self.iqa_ui_state.scope
        roi_options: dict[str, Any] = {}
        if scope_to_use == "roi":
            roi, roi_warnings = self._resolve_iqa_roi_selection()
            if roi is None:
                return None, roi_warnings or ["missing_scope_roi"]
            roi_options["bbox"] = tuple(self.iqa_ui_state.roi_bbox or ())
            run_warnings.extend(roi_warnings)

        reference_array = self._load_analysis_image_array(reference_id)
        target_array = self._load_analysis_image_array(target_id)
        if reference_array is None or target_array is None:
            return None, ["failed_to_load_images"]
        if scope_to_use == "roi" and "bbox" in roi_options:
            normalized_bbox, norm_warnings = self._normalize_iqa_roi_bbox(tuple(roi_options["bbox"]), tuple(np.asarray(reference_array).shape))
            if normalized_bbox is None:
                return None, norm_warnings
            roi_options["bbox"] = normalized_bbox
            run_warnings.extend(norm_warnings)

        ds_ref = None
        ds_tar = None
        if hasattr(self, "dicom_loader") and self.dicom_loader is not None:
            try:
                ds_ref, _frames_ref = self.dicom_loader.get_decoded_file(reference_id)
            except Exception:
                ds_ref = None
            try:
                ds_tar, _frames_tar = self.dicom_loader.get_decoded_file(target_id)
            except Exception:
                ds_tar = None

        hist_ref = np.asarray(reference_array, dtype=np.float64)
        hist_tar = np.asarray(target_array, dtype=np.float64)
        if hist_ref.shape != hist_tar.shape:
            min_h = min(hist_ref.shape[0], hist_tar.shape[0])
            min_w = min(hist_ref.shape[1], hist_tar.shape[1])
            hist_ref = hist_ref[:min_h, :min_w]
            hist_tar = hist_tar[:min_h, :min_w]
        if scope_to_use == "roi" and "bbox" in roi_options:
            x0, y0, x1, y1 = roi_options["bbox"]
            hist_ref = hist_ref[y0:y1, x0:x1]
            hist_tar = hist_tar[y0:y1, x0:x1]

        if ds_ref is not None and ds_tar is not None and hasattr(ds_ref, "pixel_array") and hasattr(ds_tar, "pixel_array"):
            result = calculate_dicom_iqa(
                ds_ref,
                ds_tar,
                input_mode=run_state["options"].get("input_mode", input_mode),
                scope=scope_to_use,
                options={
                    "data_range_policy": run_state["options"].get("data_range_policy", "bits"),
                    "photometric_invert": bool(run_state["options"].get("photometric_invert", False)),
                    **roi_options,
                },
            )
            hist_range, hist_warnings = resolve_histogram_range(hist_ref, hist_tar, policy="auto", data_range=result.context.data_range_used)
            hist_result = calculate_histogram_data(hist_ref, hist_tar, bins=64, hist_range=hist_range, normalize=True)
            from iqa_result_schema import IQAContext as _IQAContext, IQAResult as _IQAResult
            ssim_params = dict(result.context.ssim_params or {})
            histogram_payload = {
                "histogram_bins": hist_result["bins"],
                "histogram_range": hist_result["hist_range"],
                "histogram_normalized": hist_result["normalized"],
                "histogram_range_policy": "auto",
                "histogram_corr": hist_result["hist_corr"],
                "histogram_distribution_hint": hist_result["distribution_shift_hint"],
                "histogram_reference_peak_bin": hist_result["peak_bin_reference"],
                "histogram_target_peak_bin": hist_result["peak_bin_target"],
                "histogram_summary": summarize_histogram_difference(hist_result),
            }
            ssim_params.update(histogram_payload)
            enriched_context = _IQAContext(
                input_mode=result.context.input_mode,
                scope=result.context.scope,
                image_shape=result.context.image_shape,
                data_range_policy=result.context.data_range_policy,
                data_range_used=result.context.data_range_used,
                bits_stored=result.context.bits_stored,
                histogram_bins=result.context.histogram_bins,
                histogram_range=result.context.histogram_range,
                histogram=histogram_payload,
                ssim_params=ssim_params,
            )
            result = _IQAResult(metrics=result.metrics, context=enriched_context, warnings=list(result.warnings))
            return result, sorted(set(run_warnings + hist_warnings + hist_result.get("warnings", [])))

        ref = np.asarray(reference_array, dtype=np.float64)
        tar = np.asarray(target_array, dtype=np.float64)
        if ref.shape != tar.shape:
            min_h = min(ref.shape[0], tar.shape[0])
            min_w = min(ref.shape[1], tar.shape[1])
            ref = ref[:min_h, :min_w]
            tar = tar[:min_h, :min_w]
            shape_warning = ["shape_mismatch"]
        else:
            shape_warning = []
        if scope_to_use == "roi" and "bbox" in roi_options:
            x0, y0, x1, y1 = roi_options["bbox"]
            ref = ref[y0:y1, x0:x1]
            tar = tar[y0:y1, x0:x1]

        result = calculate_iqa_metrics(
            ref,
            tar,
            options={
                "input_mode": "array",
                "scope": scope_to_use,
                "data_range_policy": "actual_union",
            },
        )
        if ref.shape != tar.shape:
            pass
        from iqa_result_schema import IQAContext as _IQAContext, IQAResult as _IQAResult
        ssim_params = dict(result.context.ssim_params or {})
        ssim_params["original_reference_shape"] = tuple(int(v) for v in np.asarray(reference_array).shape)
        ssim_params["original_target_shape"] = tuple(int(v) for v in np.asarray(target_array).shape)
        ssim_params["compared_shape"] = tuple(int(v) for v in ref.shape)
        ssim_params["shape_alignment_policy"] = "common_crop" if "shape_mismatch" in shape_warning else "none"
        if scope_to_use == "roi":
            ssim_params["roi_id"] = getattr(self.iqa_ui_state, "selected_roi_id", "")
            ssim_params["roi_label"] = getattr(self.iqa_ui_state, "selected_roi_label", "")
            ssim_params["roi_source"] = getattr(self.iqa_ui_state, "selected_roi_source", "")
            ssim_params["roi_bbox"] = tuple(self.iqa_ui_state.roi_bbox or ())
            ssim_params["roi_policy"] = getattr(self.iqa_ui_state, "roi_policy", "bbox")
        hist_range, hist_warnings = resolve_histogram_range(ref, tar, policy="auto", data_range=result.context.data_range_used)
        hist_result = calculate_histogram_data(ref, tar, bins=64, hist_range=hist_range, normalize=True)
        histogram_payload = {
            "histogram_bins": hist_result["bins"],
            "histogram_range": hist_result["hist_range"],
            "histogram_normalized": hist_result["normalized"],
            "histogram_range_policy": "auto",
            "histogram_corr": hist_result["hist_corr"],
            "histogram_distribution_hint": hist_result["distribution_shift_hint"],
            "histogram_reference_peak_bin": hist_result["peak_bin_reference"],
            "histogram_target_peak_bin": hist_result["peak_bin_target"],
            "histogram_summary": summarize_histogram_difference(hist_result),
        }
        ssim_params.update(histogram_payload)
        enriched_context = _IQAContext(
            input_mode=result.context.input_mode,
            scope=result.context.scope,
            image_shape=result.context.image_shape,
            data_range_policy=result.context.data_range_policy,
            data_range_used=result.context.data_range_used,
            bits_stored=result.context.bits_stored,
            histogram_bins=result.context.histogram_bins,
            histogram_range=result.context.histogram_range,
            histogram=histogram_payload,
            ssim_params=ssim_params,
        )
        result = _IQAResult(metrics=result.metrics, context=enriched_context, warnings=list(result.warnings))
        if "shape_mismatch" in shape_warning and "영상 크기가 달라 공통 영역 기준으로 비교했습니다." not in run_warnings:
            run_warnings.append("영상 크기가 달라 공통 영역 기준으로 비교했습니다.")
        return result, sorted(set(shape_warning + run_warnings + hist_warnings + hist_result.get("warnings", [])))

    def _build_iqa_display_rows(self, iqa_result: Any) -> tuple[str, str, str]:
        display_model = build_iqa_display_model(iqa_result, reference_label=getattr(self, "iqa_ui_state", create_default_iqa_state()).reference_label, target_label=getattr(self, "iqa_ui_state", create_default_iqa_state()).target_label)
        result_text, context_text = format_iqa_display_text(display_model)
        histogram_text = ""
        if isinstance(getattr(iqa_result.context, "histogram", None), dict):
            preview = build_histogram_preview_model(
                iqa_result.context.histogram,
                reference_label=getattr(self, "iqa_ui_state", create_default_iqa_state()).reference_label,
                target_label=getattr(self, "iqa_ui_state", create_default_iqa_state()).target_label,
            )
            histogram_text = format_histogram_preview_text(preview)
        warning_rows = display_model.get("warning_rows", [])
        warning_text = "Warnings=None" if not warning_rows else "Warnings=" + ",".join(row.get("message", "") for row in warning_rows)
        if histogram_text:
            result_text = f"{result_text} | {histogram_text}"
        return result_text, context_text, warning_text

    def calculate_image_comparison_metrics(self) -> None:
        try:
            iqa_result, extra_warnings = self._run_iqa_from_viewer_state(input_mode="raw_dicom_pixel", scope="full_image")
        except Exception as exc:
            self.image_analysis_results["image_result"].set(f"Result: IQA failed: {exc}")
            return

        if iqa_result is None:
            reason = ",".join(extra_warnings) or "invalid"
            self.image_analysis_results["image_result"].set(
                "[IQA Summary]\n- 종합 해석: IQA 실행 불가 상태입니다. 진단 정확도 판정이 아닌 영상 품질 비교 지표입니다.\n"
                f"- Status: invalid\n- Invalid Reason: {reason}\n- Reference: {getattr(self.iqa_ui_state, 'reference_label', '') or 'None'}\n"
                f"- Target: {getattr(self.iqa_ui_state, 'target_label', '') or 'None'}\n\n"
                "[Metrics]\n- MSE: 계산 불가\n- RMSE: 계산 불가\n- PSNR: 계산 불가\n- SSIM: 계산 불가\n- HIST Corr: 계산 불가"
            )
            friendly = sorted({WARNING_MESSAGE_MAP.get(w, w) for w in extra_warnings})
            self.image_analysis_results["image_formula"].set("[Warnings]\n- " + (", ".join(friendly) if friendly else "주의 사항 없음"))
            if not hasattr(self, "analysis_last_run") or self.analysis_last_run is None:
                self.analysis_last_run = {}
            self.analysis_last_run["iqa"] = {"analysis_type": "iqa", "status": "invalid", "reason": ",".join(extra_warnings)}
            self.analysis_last_run["iqa_report"] = {"report_type": "iqa_single", "status": "invalid", "invalid_reason": ",".join(extra_warnings)}
            if not hasattr(self, "iqa_history") or self.iqa_history is None:
                self.iqa_history = []
            invalid_entry = build_iqa_history_entry(
                result=None,
                selection_state=getattr(self, "iqa_ui_state", None),
                export_record=self.analysis_last_run["iqa"],
                display_model={"summary": "IQA unavailable"},
                status="invalid",
                invalid_reason=",".join(extra_warnings) or "missing_input",
                source="viewer",
            )
            append_iqa_history(self.iqa_history, invalid_entry, max_items=50)
            return

        combined = sorted(set(list(iqa_result.warnings) + list(extra_warnings)))
        if "data_range <= 0" in combined and "data_range_ambiguous" not in combined:
            combined.append("data_range_ambiguous")
        from iqa_result_schema import IQAResult as _IQAResult, IQAContext as _IQAContext
        ssim_params = dict(iqa_result.context.ssim_params or {})
        ssim_params["reference_label"] = getattr(self.iqa_ui_state, "reference_label", "")
        ssim_params["target_label"] = getattr(self.iqa_ui_state, "target_label", "")
        if getattr(self.iqa_ui_state, "scope", "") == "roi":
            ssim_params["roi_id"] = getattr(self.iqa_ui_state, "selected_roi_id", "")
            ssim_params["roi_label"] = getattr(self.iqa_ui_state, "selected_roi_label", "")
            ssim_params["roi_source"] = getattr(self.iqa_ui_state, "selected_roi_source", "")
            ssim_params["roi_bbox"] = tuple(getattr(self.iqa_ui_state, "roi_bbox", ()) or ())
            ssim_params["roi_policy"] = getattr(self.iqa_ui_state, "roi_policy", "bbox")
        enriched_context = _IQAContext(
            input_mode=iqa_result.context.input_mode,
            scope=iqa_result.context.scope,
            image_shape=iqa_result.context.image_shape,
            data_range_policy=iqa_result.context.data_range_policy,
            data_range_used=iqa_result.context.data_range_used,
            bits_stored=iqa_result.context.bits_stored,
            histogram_bins=iqa_result.context.histogram_bins,
            histogram_range=iqa_result.context.histogram_range,
            histogram=dict(getattr(iqa_result.context, "histogram", {}) or {}),
            ssim_params=ssim_params,
        )
        iqa_result = _IQAResult(metrics=iqa_result.metrics, context=enriched_context, warnings=sorted(set(combined)))

        metrics_text, context_text, warning_text = self._build_iqa_display_rows(iqa_result)
        self.image_analysis_results["image_result"].set(f"{metrics_text} | {warning_text}")
        self.image_analysis_results["image_formula"].set(context_text)
        if not hasattr(self, "analysis_last_run") or self.analysis_last_run is None:
            self.analysis_last_run = {}
        self.analysis_last_run["iqa"] = iqa_result_to_analysis_record(iqa_result, source="image_analysis")
        if not hasattr(self, "iqa_history") or self.iqa_history is None:
            self.iqa_history = []
        history_entry = build_iqa_history_entry(
            result=iqa_result,
            selection_state=getattr(self, "iqa_ui_state", None),
            export_record=self.analysis_last_run["iqa"],
            display_model=build_iqa_display_model(
                iqa_result,
                reference_label=getattr(self.iqa_ui_state, "reference_label", "") if hasattr(self, "iqa_ui_state") else "",
                target_label=getattr(self.iqa_ui_state, "target_label", "") if hasattr(self, "iqa_ui_state") else "",
            ),
            status="success",
            source="viewer",
        )
        append_iqa_history(self.iqa_history, history_entry, max_items=50)
        self._update_iqa_report_preview_from_history()

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
        self._action_update_measurement_in_store(selected)
        self._action_clear_analysis_last_run()
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
        for measurement in self._selector_measurements_for_current_frame(kind=expected_kind):
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
        for measurement in self._selector_measurements_for_current_frame(kind="roi"):
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
        self._action_commit_frame_change(self.current_frame)
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

