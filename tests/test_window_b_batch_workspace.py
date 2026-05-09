from __future__ import annotations

import copy
import os
from types import SimpleNamespace

import tkinter as tk
from tkinter import ttk

from dicom_viewer import DicomViewer
from window_b_manager import WindowBManager
from window_b_panel_factory import build_window_b_batch_panel


def _execution_result():
    return {"dicom_batch_execution_result_schema_version":1,"run_id":"run1","generated_at":"2026-01-01T00:00:00+00:00","metadata":{},"execution_plan_id":"ep1","item_count":1,"task_count":1,"completed_task_count":1,"blocked_task_count":0,"not_executed_task_count":0,"error_task_count":0,"items":[{"batch_item_execution_result_schema_version":1,"item_id":"i1","dicom_path":"/tmp/a.dcm","dicom_status":"valid","bounds_status":"pass","is_executable_for_any_analysis":True,"task_results":[{"batch_task_execution_result_schema_version":1,"analysis_type":"snr","status":"completed","dicom_path":"/tmp/a.dcm","roi_ids":["r1"],"blocked_reasons":[],"raw_result_payload":{"result":1.0,"status":"ok"},"error":None}]}]}


def _viewer_stub():
    calls = {"preview":0,"build_records":0,"append":0,"build_qc":[]}
    v = SimpleNamespace(
        current_threshold_config=None,
        current_dicom_batch_execution_result=None,
        current_dicom_batch_history_records=[],
        current_batch_qc_run=None,
        get_dicom_batch_execution_result_summary_for_viewer=lambda execution_result=None: {"has_execution_result":False,"run_id":"","execution_plan_id":"","item_count":0,"task_count":0,"completed_task_count":0,"blocked_task_count":0,"not_executed_task_count":0,"error_task_count":0,"history_record_count":0,"has_batch_qc_run":False},
        render_dicom_batch_workspace_summary_text_for_viewer=lambda execution_result=None: "summary",
        show_dicom_batch_history_bridge_viewer=lambda execution_result=None: calls.__setitem__("preview", calls["preview"]+1) or "bridge",
        build_dicom_batch_history_records_for_viewer=lambda **kwargs: calls.__setitem__("build_records", calls["build_records"]+1) or [],
        append_dicom_batch_history_records_for_viewer=lambda **kwargs: calls.__setitem__("append", calls["append"]+1) or [],
        build_batch_qc_run_from_dicom_batch_execution_result_for_viewer=lambda **kwargs: calls["build_qc"].append(kwargs.get("use_selected_threshold_config")) or {"item_count":0},
        show_current_batch_qc_report_viewer=lambda: calls.__setitem__("report_preview", calls.get("report_preview", 0)+1) or "report",
        export_current_batch_qc_run_json_for_viewer=lambda: calls.__setitem__("report_json", calls.get("report_json", 0)+1) or "ok",
        export_current_batch_qc_run_csv_for_viewer=lambda: calls.__setitem__("report_csv", calls.get("report_csv", 0)+1) or "ok",
        export_current_batch_qc_report_text_for_viewer=lambda: calls.__setitem__("report_text", calls.get("report_text", 0)+1) or "ok",
        export_current_batch_qc_report_pdf_for_viewer=lambda: calls.__setitem__("report_pdf", calls.get("report_pdf", 0)+1) or b"%PDF-1.4",
        preview_current_dicom_batch_roi_role_validation_for_viewer=lambda: calls.__setitem__("validate_roi", calls.get("validate_roi",0)+1) or "roi",
        preview_current_dicom_batch_workflow_readiness_for_viewer=lambda **k: calls.__setitem__("workflow", calls.get("workflow",0)+1) or "wf",
        set_current_dicom_batch_strict_roi_validation_for_viewer=lambda enabled: calls.__setitem__("strict", bool(enabled)),
        current_dicom_batch_strict_roi_validation=False,
    )
    return v, calls


def test_window_b_batch_panel_has_expected_actions():
    if not os.environ.get("DISPLAY"):
        return
    root = tk.Tk(); root.withdraw()
    parent = ttk.Frame(root)
    v, _ = _viewer_stub()
    build_window_b_batch_panel(parent, v, store=None)
    texts = [w.cget("text") for w in parent.winfo_children()[0].winfo_children()[1].winfo_children() if hasattr(w, "cget") and "text" in w.keys()]
    assert "Refresh Batch Summary" in texts and "Build Batch QC Run" in texts and "Use selected threshold config" in texts
    root.destroy()


def test_batch_panel_buttons_call_viewer_helpers():
    if not os.environ.get("DISPLAY"):
        return
    root = tk.Tk(); root.withdraw()
    parent = ttk.Frame(root)
    v, calls = _viewer_stub()
    panel = build_window_b_batch_panel(parent, v, store=None)
    actions = panel.winfo_children()[1]
    btns = [w for w in actions.winfo_children() if isinstance(w, ttk.Button)]
    btns[1].invoke(); btns[2].invoke(); btns[3].invoke(); btns[4].invoke()
    assert calls["preview"] == 1 and calls["build_records"] == 1 and calls["append"] == 1 and calls["build_qc"] == [False]
    root.destroy()


def test_batch_panel_build_qc_uses_selected_threshold_only_when_checked():
    if not os.environ.get("DISPLAY"):
        return
    root = tk.Tk(); root.withdraw()
    parent = ttk.Frame(root)
    v, calls = _viewer_stub()
    panel = build_window_b_batch_panel(parent, v, store=None)
    actions = panel.winfo_children()[1]
    check = [w for w in actions.winfo_children() if isinstance(w, ttk.Checkbutton)][0]
    btn = [w for w in actions.winfo_children() if isinstance(w, ttk.Button)][4]
    btn.invoke(); check.invoke(); btn.invoke()
    assert calls["build_qc"] == [False, True]
    root.destroy()


def test_get_dicom_batch_execution_result_summary_empty_state():
    v = SimpleNamespace(current_dicom_batch_execution_result=None, current_dicom_batch_history_records=[], current_batch_qc_run=None)
    s = DicomViewer.get_dicom_batch_execution_result_summary_for_viewer(v)
    assert s["has_execution_result"] is False and s["item_count"] == 0


def test_get_dicom_batch_execution_result_summary_with_result_and_no_mutation():
    v = SimpleNamespace(current_dicom_batch_execution_result=_execution_result(), current_dicom_batch_history_records=[], current_batch_qc_run=None)
    base = copy.deepcopy(v.current_dicom_batch_execution_result)
    s = DicomViewer.get_dicom_batch_execution_result_summary_for_viewer(v)
    assert s["run_id"] == "run1" and s["task_count"] == 1 and v.current_dicom_batch_execution_result == base


def test_render_dicom_batch_workspace_summary_text_empty_state():
    v = SimpleNamespace(current_dicom_batch_execution_result=None, current_dicom_batch_history_records=[], current_batch_qc_run=None)
    t = DicomViewer.render_dicom_batch_workspace_summary_text_for_viewer(v)
    assert "Execution Result Loaded" in t


def test_refresh_window_b_batch_workspace_no_widgets_noop():
    v = SimpleNamespace(current_dicom_batch_execution_result=None, current_dicom_batch_history_records=[], current_batch_qc_run=None)
    DicomViewer._refresh_window_b_batch_workspace(v)


def test_refresh_all_calls_batch_workspace_refresh_when_open():
    manager = WindowBManager.__new__(WindowBManager)
    calls = {"analysis":0, "history":0, "batch":0}
    manager.viewer = SimpleNamespace(
        _refresh_analysis_results_panel=lambda: calls.__setitem__("analysis", calls["analysis"]+1),
        _refresh_result_history_table=lambda: calls.__setitem__("history", calls["history"]+1),
        _refresh_window_b_batch_workspace=lambda: calls.__setitem__("batch", calls["batch"]+1),
    )
    manager.is_open = lambda: True
    manager.mark_dirty = lambda: None
    WindowBManager.refresh_all(manager)
    assert calls == {"analysis":1, "history":1, "batch":1}


def test_window_b_batch_workspace_no_messagebox_dependency_and_no_pydicom_import():
    src_pf = open("window_b_panel_factory.py", encoding="utf-8").read()
    src_mgr = open("window_b_manager.py", encoding="utf-8").read()
    assert "messagebox" not in src_pf and "messagebox" not in src_mgr and "pydicom" not in src_pf and "pydicom" not in src_mgr


def test_batch_panel_has_report_export_actions():
    src = open("window_b_panel_factory.py", encoding="utf-8").read()
    for label in ["Preview Batch QC Report", "Export Batch QC JSON", "Export Batch QC CSV", "Export Batch QC Text", "Export Batch QC PDF"]:
        assert label in src


def test_batch_panel_has_execution_plan_run_actions():
    src = open("window_b_panel_factory.py", encoding="utf-8").read()
    for label in ["Build Execution Plan", "Run Batch Execution", "Preview Execution Result", "Validate ROI Roles", "Refresh Workflow Readiness", "Require valid ROI roles before pixel run"]:
        assert label in src


def test_batch_panel_has_pixel_executor_actions():
    src = open("window_b_panel_factory.py", encoding="utf-8").read()
    for label in ["Check Pixel Executor", "Run Pixel Batch Execution", "Validate ROI Roles"]:
        assert label in src
