import numpy as np

from iqa_ui_state import (
    clear_iqa_selection,
    create_default_iqa_state,
    get_iqa_pair_status,
    resolve_iqa_data_range_policy_for_mode,
    resolve_iqa_run_state,
    set_iqa_reference_from_current,
    set_iqa_target_from_current,
    swap_iqa_reference_target,
)


def test_default_state_values():
    state = create_default_iqa_state()
    assert state.input_mode == "raw_dicom_pixel"
    assert state.scope == "full_image"
    assert state.data_range_mode == "auto"
    assert state.photometric_invert is False


def test_set_reference_target_and_ready():
    state = create_default_iqa_state()
    arr = np.zeros((4, 4))
    set_iqa_reference_from_current(state, "a", "A", array=arr)
    set_iqa_target_from_current(state, "b", "B", array=arr.copy())
    status = get_iqa_pair_status(state)
    assert status["ready"] is True


def test_missing_target_not_ready():
    state = create_default_iqa_state()
    set_iqa_reference_from_current(state, "a", "A", array=np.zeros((4, 4)))
    status = get_iqa_pair_status(state)
    assert status["ready"] is False
    assert "target" in status["reason"]


def test_swap_and_clear():
    state = create_default_iqa_state()
    set_iqa_reference_from_current(state, "a", "A")
    set_iqa_target_from_current(state, "b", "B")
    swap_iqa_reference_target(state)
    assert state.reference_id == "b" and state.target_id == "a"
    clear_iqa_selection(state)
    assert state.reference_id == "" and state.target_id == ""


def test_auto_data_range_policy():
    assert resolve_iqa_data_range_policy_for_mode("raw_dicom_pixel", "auto")[0] == "bits"
    assert resolve_iqa_data_range_policy_for_mode("modality_lut", "auto")[0] == "actual_union"
    policy, used = resolve_iqa_data_range_policy_for_mode("windowed_display", "auto")
    assert policy == "explicit" and used == 255.0


def test_same_image_warning():
    state = create_default_iqa_state()
    arr = np.zeros((4, 4))
    set_iqa_reference_from_current(state, "same", "S", array=arr)
    set_iqa_target_from_current(state, "same", "S", array=arr.copy())
    status = get_iqa_pair_status(state)
    assert any("identical" in w for w in status["warnings"])


def test_run_state_contains_labels_and_options():
    state = create_default_iqa_state()
    arr = np.zeros((4, 4))
    set_iqa_reference_from_current(state, "a", "A", array=arr)
    set_iqa_target_from_current(state, "b", "B", array=arr.copy())
    run = resolve_iqa_run_state(state)
    assert run["is_ready"] is True
    assert run["reference_label"] == "A"
    assert run["target_label"] == "B"
    assert run["options"]["data_range_policy"] == "bits"
