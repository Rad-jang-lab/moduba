from __future__ import annotations

import copy

import pytest

from dicom_batch_roi_role_validation import (
    assert_dicom_batch_roi_roles_valid,
    render_dicom_batch_roi_role_validation_text,
    validate_dicom_batch_roi_roles,
)


def _preset():
    return {"rois": [{"id": "r1"}, {"id": "r2"}]}


def _plan(atype="snr", roi_ids=None):
    return {"execution_plan_id": "ep1", "items": [{"item_id": "i1", "dicom_path": "/tmp/a.dcm", "tasks": [{"task_id": "t1", "analysis_type": atype, "roi_ids": roi_ids if roi_ids is not None else ["r1", "r2"]}]}]}


def test_validate_roi_roles_valid_and_unknown_and_missing():
    assert validate_dicom_batch_roi_roles(_plan("snr", ["r1", "r2"]), _preset())["valid"] is True
    bad = validate_dicom_batch_roi_roles(_plan("snr", ["r1", "x"]), _preset())
    assert bad["valid"] is False and bad["summary"]["unknown_roi_count"] >= 1
    miss = validate_dicom_batch_roi_roles(_plan("snr", []), _preset())
    assert miss["valid"] is False


def test_validate_roi_roles_duplicate_unsupported_order_and_no_mutation():
    p = _plan("weird", ["r1", "r1"]); rp = _preset(); bp = copy.deepcopy(p); br = copy.deepcopy(rp)
    out = validate_dicom_batch_roi_roles(p, rp)
    reasons = out["items"][0]["task_validations"][0]["reason_codes"]
    assert "UNSUPPORTED_ANALYSIS_TYPE" in reasons and "DUPLICATE_ROI_ID" in reasons
    assert out["items"][0]["item_id"] == "i1" and out["items"][0]["task_validations"][0]["task_id"] == "t1"
    assert p == bp and rp == br


def test_validate_roi_roles_bounds_render_assert_and_guardrails():
    out = validate_dicom_batch_roi_roles(_plan(), _preset(), bounds_result={"items": [{"item_id": "i1", "bounds_status": "warn"}]})
    assert "ROI_BOUNDS_WARNING" in out["items"][0]["task_validations"][0]["reason_codes"]
    txt = render_dicom_batch_roi_role_validation_text(out)
    assert "DICOM Batch ROI Role Validation" in txt and "tasks:" in txt
    assert_dicom_batch_roi_roles_valid(validate_dicom_batch_roi_roles(_plan(), _preset()))
    with pytest.raises(ValueError):
        assert_dicom_batch_roi_roles_valid(validate_dicom_batch_roi_roles(_plan("snr", []), _preset()))
    src = open("dicom_batch_roi_role_validation.py", encoding="utf-8").read()
    assert "tkinter" not in src and "messagebox" not in src and "pydicom" not in src
