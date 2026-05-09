from __future__ import annotations

import copy

import pytest

from dicom_batch_workflow_readiness import build_dicom_batch_workflow_readiness_report, render_dicom_batch_workflow_readiness_text, assert_dicom_batch_workflow_ready_for_pixel_run


def test_readiness_policies_and_no_mutation():
    plan={"items": []}; roi={"valid": False}; hist=[]; qc=None
    bp=copy.deepcopy(plan); br=copy.deepcopy(roi)
    r=build_dicom_batch_workflow_readiness_report(execution_plan=plan, roi_role_validation_report=roi, strict_roi_role_validation=False, history_records=hist, batch_qc_run=qc)
    assert r["overall_status"] == "warning"
    r2=build_dicom_batch_workflow_readiness_report(execution_plan=plan, roi_role_validation_report=roi, strict_roi_role_validation=True)
    assert r2["overall_status"] == "blocked"
    assert "STRICT_ROI_VALIDATION_BLOCK" in str(r2["checks"])
    assert plan==bp and roi==br


def test_readiness_missing_plan_blocked_render_assert_guardrails():
    r=build_dicom_batch_workflow_readiness_report(execution_plan=None)
    assert r["overall_status"] == "blocked"
    t=render_dicom_batch_workflow_readiness_text(r)
    assert "DICOM Batch Workflow Readiness" in t and "next_actions" in t
    with pytest.raises(ValueError):
        assert_dicom_batch_workflow_ready_for_pixel_run(r)
    src=open("dicom_batch_workflow_readiness.py",encoding="utf-8").read()
    assert "tkinter" not in src and "messagebox" not in src and "pydicom" not in src
