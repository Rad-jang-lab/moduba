from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IQASelectionState:
    reference_id: str = ""
    reference_label: str = ""
    reference_dataset: Any = None
    reference_array: Any = None
    target_id: str = ""
    target_label: str = ""
    target_dataset: Any = None
    target_array: Any = None
    input_mode: str = "raw_dicom_pixel"
    scope: str = "full_image"
    data_range_mode: str = "auto"
    photometric_invert: bool = False
    selected_roi_id: str = ""
    selected_roi_label: str = ""
    selected_roi_source: str = ""
    roi_bbox: tuple[int, int, int, int] | None = None
    selected_roi_mask: Any = None
    roi_policy: str = "none"
    roi_resolution_warnings: list[str] = field(default_factory=list)
    last_result: Any = None
    warnings: list[str] = field(default_factory=list)


def create_default_iqa_state() -> IQASelectionState:
    return IQASelectionState()


def resolve_iqa_data_range_policy_for_mode(input_mode: str, data_range_mode: str = "auto") -> tuple[str, float | None]:
    if data_range_mode != "auto":
        return data_range_mode, None
    mode = str(input_mode or "raw_dicom_pixel")
    if mode == "raw_dicom_pixel":
        return "bits", None
    if mode == "modality_lut":
        return "actual_union", None
    if mode == "windowed_display":
        return "explicit", 255.0
    return "actual_union", None


def set_iqa_reference_from_current(state: IQASelectionState, image_id: str, label: str, dataset: Any = None, array: Any = None) -> None:
    state.reference_id = str(image_id or "")
    state.reference_label = str(label or image_id or "")
    state.reference_dataset = dataset
    state.reference_array = array


def set_iqa_target_from_current(state: IQASelectionState, image_id: str, label: str, dataset: Any = None, array: Any = None) -> None:
    state.target_id = str(image_id or "")
    state.target_label = str(label or image_id or "")
    state.target_dataset = dataset
    state.target_array = array


def swap_iqa_reference_target(state: IQASelectionState) -> None:
    state.reference_id, state.target_id = state.target_id, state.reference_id
    state.reference_label, state.target_label = state.target_label, state.reference_label
    state.reference_dataset, state.target_dataset = state.target_dataset, state.reference_dataset
    state.reference_array, state.target_array = state.target_array, state.reference_array


def clear_iqa_selection(state: IQASelectionState) -> None:
    state.reference_id = ""
    state.reference_label = ""
    state.reference_dataset = None
    state.reference_array = None
    state.target_id = ""
    state.target_label = ""
    state.target_dataset = None
    state.target_array = None
    state.selected_roi_id = ""
    state.selected_roi_label = ""
    state.selected_roi_source = ""
    state.roi_bbox = None
    state.selected_roi_mask = None
    state.roi_policy = "none"
    state.roi_resolution_warnings = []
    state.warnings = []


def get_iqa_pair_status(state: IQASelectionState) -> dict[str, Any]:
    warnings: list[str] = []
    if not state.reference_id:
        return {"ready": False, "reason": "reference missing", "warnings": warnings}
    if not state.target_id:
        return {"ready": False, "reason": "target missing", "warnings": warnings}
    if state.reference_id == state.target_id:
        warnings.append("reference and target are identical image")
    if state.reference_array is not None and state.target_array is not None:
        if getattr(state.reference_array, "shape", None) != getattr(state.target_array, "shape", None):
            warnings.append("shape mismatch")
    return {"ready": True, "reason": "", "warnings": warnings}


def resolve_iqa_run_state(state: IQASelectionState) -> dict[str, Any]:
    pair = get_iqa_pair_status(state)
    policy, data_range_used = resolve_iqa_data_range_policy_for_mode(state.input_mode, state.data_range_mode)
    return {
        "is_ready": bool(pair["ready"]),
        "reason": pair["reason"],
        "warnings": list(pair["warnings"]),
        "reference_label": state.reference_label,
        "target_label": state.target_label,
        "options": {
            "input_mode": state.input_mode,
            "scope": state.scope,
            "data_range_policy": policy,
            "data_range_used": data_range_used,
            "photometric_invert": state.photometric_invert,
        },
    }


def set_iqa_input_mode(state: IQASelectionState, mode: str) -> None:
    state.input_mode = str(mode or "raw_dicom_pixel")


def set_iqa_scope(state: IQASelectionState, scope: str) -> None:
    state.scope = str(scope or "full_image")


def set_iqa_photometric_invert(state: IQASelectionState, enabled: bool) -> None:
    state.photometric_invert = bool(enabled)


def set_iqa_data_range_mode(state: IQASelectionState, mode: str) -> None:
    state.data_range_mode = str(mode or "auto")
