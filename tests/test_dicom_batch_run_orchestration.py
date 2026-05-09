from __future__ import annotations

import copy

from dicom_batch_run_orchestrator import *
from tests.test_dicom_batch_execution import _plan, _preset


def _exec_task(plan, executable=True):
    p = copy.deepcopy(plan)
    p["items"][0]["tasks"][0]["is_executable"] = executable
    return p


def test_run_execution_plan_with_fake_executor_completes_tasks():
    r = run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=lambda t, i, c: {"ok": True})
    assert any(t["status"] == "completed" for t in r["items"][0]["task_results"])

def test_run_execution_plan_without_executor_creates_not_executed_tasks():
    r = run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=None)
    assert any(t["status"] == "not_executed" for t in r["items"][0]["task_results"])

def test_run_execution_plan_executor_error_becomes_task_error():
    r = run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=lambda *_: (_ for _ in ()).throw(RuntimeError("x")))
    assert any(t["status"] == "error" for t in r["items"][0]["task_results"])

def test_run_execution_plan_preserves_blocked_tasks():
    r = run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=lambda *_: {"ok": True})
    assert any(t["status"] == "blocked" for t in r["items"][0]["task_results"])

def test_run_execution_plan_does_not_mutate_plan():
    p = _plan(); b = copy.deepcopy(p)
    _ = run_dicom_batch_execution_plan_with_executor(p, _preset(), analysis_executor=None)
    assert p == b

def test_run_orchestration_summary_empty_state():
    s = build_dicom_batch_run_orchestration_summary()
    assert s["has_execution_plan"] is False and s["has_execution_result"] is False

def test_run_orchestration_summary_counts_statuses():
    r = run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=None)
    s = build_dicom_batch_run_orchestration_summary(_plan(), r)
    assert s["task_count"] >= 1 and s["not_executed_task_count"] >= 1

def test_run_orchestration_module_does_not_import_tkinter_or_pydicom():
    src = open("dicom_batch_run_orchestrator.py", encoding="utf-8").read()
    assert "import tkinter" not in src and "import pydicom" not in src
