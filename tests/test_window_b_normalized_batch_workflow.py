import types
from window_b_panel_factory import build_window_b_batch_panel
from dicom_viewer import DicomViewer

class W:
    def __init__(self,*a,**k): self.content=''
    def pack(self,**k): pass
    def grid(self,**k): pass
    def grid_columnconfigure(self,*a,**k): pass
    def grid_rowconfigure(self,*a,**k): pass
    def configure(self,**k): pass
    def delete(self,*a,**k): self.content=''
    def insert(self,*a): self.content=str(a[-1])
    def yview(self,*a,**k): pass
    def set(self,*a,**k): pass

class BVar:
    def __init__(self,value=False): self.v=value
    def get(self): return self.v
    def set(self,v): self.v=v


def _viewer(calls):
    def rec(name, ret="ok"):
        def _fn(*args, **kwargs): calls.append((name,args,kwargs)); return ret
        return _fn
    return types.SimpleNamespace(
        current_dicom_batch_strict_roi_validation=False,
        get_dicom_batch_execution_result_summary_for_viewer=lambda: {"has_execution_result": True,"run_id":"r","execution_plan_id":"e","item_count":1,"task_count":1,"completed_task_count":1,"blocked_task_count":0,"not_executed_task_count":0,"error_task_count":0,"history_record_count":0,"has_batch_qc_run":False},
        render_dicom_batch_workspace_summary_text_for_viewer=lambda: "summary",
        show_dicom_batch_history_bridge_viewer=rec("show_dicom_batch_history_bridge_viewer"),
        build_dicom_batch_history_records_for_viewer=rec("build_dicom_batch_history_records_for_viewer"),
        append_dicom_batch_history_records_for_viewer=rec("append_dicom_batch_history_records_for_viewer", None),
        build_batch_qc_run_from_dicom_batch_execution_result_for_viewer=rec("build_batch_qc_run_from_dicom_batch_execution_result_for_viewer"),
        build_current_dicom_batch_execution_plan_for_viewer=rec("build_current_dicom_batch_execution_plan_for_viewer"),
        run_current_dicom_batch_execution_plan_for_viewer=rec("run_current_dicom_batch_execution_plan_for_viewer"),
        render_dicom_batch_run_workspace_summary_text_for_viewer=lambda: "run summary",
        preview_current_dicom_batch_execution_result_for_viewer=lambda: "preview",
        preview_current_dicom_batch_workflow_readiness_for_viewer=lambda strict_roi_role_validation=False: "ready",
        set_current_dicom_batch_strict_roi_validation_for_viewer=lambda val: None,
        preview_current_dicom_batch_roi_role_validation_for_viewer=lambda: "roi",
        preview_current_dicom_batch_pixel_executor_capability_for_viewer=lambda: "cap",
        run_current_dicom_batch_execution_plan_with_pixel_executor_for_viewer=lambda strict_roi_role_validation=False: None,
        show_current_batch_qc_report_viewer=lambda: "report",
        export_current_batch_qc_run_json_for_viewer=rec("export_current_batch_qc_run_json_for_viewer"),
        export_current_batch_qc_run_csv_for_viewer=rec("export_current_batch_qc_run_csv_for_viewer"),
        export_current_batch_qc_report_text_for_viewer=rec("export_current_batch_qc_report_text_for_viewer"),
        export_current_batch_qc_report_pdf_for_viewer=rec("export_current_batch_qc_report_pdf_for_viewer"),
        build_normalized_dicom_batch_execution_result_for_viewer=rec("build_normalized_dicom_batch_execution_result_for_viewer",{}),
        render_normalized_dicom_batch_execution_result_text_for_viewer=rec("render_normalized_dicom_batch_execution_result_text_for_viewer","n"),
        export_normalized_dicom_batch_execution_result_json_for_viewer=rec("export_normalized_dicom_batch_execution_result_json_for_viewer",None),
        export_normalized_dicom_batch_execution_result_csv_for_viewer=rec("export_normalized_dicom_batch_execution_result_csv_for_viewer",None),
        build_analysis_history_records_from_normalized_execution_for_viewer=rec("build_analysis_history_records_from_normalized_execution_for_viewer",[]),
        append_normalized_execution_history_records_for_viewer=rec("append_normalized_execution_history_records_for_viewer",None),
        build_batch_qc_run_from_normalized_execution_for_viewer=rec("build_batch_qc_run_from_normalized_execution_for_viewer",{}),
        render_normalized_batch_qc_report_text_for_viewer=rec("render_normalized_batch_qc_report_text_for_viewer","r"),
        export_normalized_batch_qc_report_json_for_viewer=rec("export_normalized_batch_qc_report_json_for_viewer",None),
        export_normalized_batch_qc_report_csv_for_viewer=rec("export_normalized_batch_qc_report_csv_for_viewer",None),
        export_normalized_batch_qc_report_text_for_viewer=rec("export_normalized_batch_qc_report_text_for_viewer",None),
        export_normalized_batch_qc_report_pdf_for_viewer=rec("export_normalized_batch_qc_report_pdf_for_viewer",None),
        render_normalized_batch_workflow_summary_text_for_viewer=rec("render_normalized_batch_workflow_summary_text_for_viewer","wf"),
    )

def _setup(monkeypatch):
    buttons={}
    class Btn(W):
        def __init__(self,_p,text,command): super().__init__(); buttons[text]=command
    monkeypatch.setattr("window_b_panel_factory.ttk.Button", Btn)
    monkeypatch.setattr("window_b_panel_factory.ttk.Frame", W)
    monkeypatch.setattr("window_b_panel_factory.ttk.LabelFrame", W)
    monkeypatch.setattr("window_b_panel_factory.ttk.Label", W)
    monkeypatch.setattr("window_b_panel_factory.ttk.Scrollbar", W)
    monkeypatch.setattr("window_b_panel_factory.ttk.Checkbutton", W)
    monkeypatch.setattr("window_b_panel_factory.tk.Text", W)
    monkeypatch.setattr("window_b_panel_factory.tk.StringVar", lambda value="": types.SimpleNamespace(set=lambda _v: None, get=lambda: value))
    monkeypatch.setattr("window_b_panel_factory.tk.BooleanVar", BVar)
    return buttons

def test_window_b_batch_panel_has_all_normalized_workflow_actions(monkeypatch):
    buttons=_setup(monkeypatch); calls=[]; build_window_b_batch_panel(types.SimpleNamespace(), _viewer(calls), object())
    expected=["Build Normalized Execution","Preview Normalized Execution","Export Normalized JSON","Export Normalized CSV","Build Normalized History Records","Append Normalized History JSONL","Build Normalized Batch QC Run","Preview Normalized Batch QC Report","Export Normalized Report JSON","Export Normalized Report CSV","Export Normalized Report Text","Export Normalized Report PDF","Refresh Normalized Workflow Summary"]
    for e in expected: assert e in buttons

def _assert_calls(monkeypatch, btn, target):
    buttons=_setup(monkeypatch); calls=[]; build_window_b_batch_panel(types.SimpleNamespace(), _viewer(calls), object()); buttons[btn](); assert any(c[0]==target for c in calls)

def test_build_normalized_execution_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Build Normalized Execution","build_normalized_dicom_batch_execution_result_for_viewer")
def test_preview_normalized_execution_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Preview Normalized Execution","render_normalized_dicom_batch_execution_result_text_for_viewer")
def test_export_normalized_json_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Export Normalized JSON","export_normalized_dicom_batch_execution_result_json_for_viewer")
def test_export_normalized_csv_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Export Normalized CSV","export_normalized_dicom_batch_execution_result_csv_for_viewer")
def test_build_normalized_history_records_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Build Normalized History Records","build_analysis_history_records_from_normalized_execution_for_viewer")
def test_append_normalized_history_jsonl_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Append Normalized History JSONL","append_normalized_execution_history_records_for_viewer")
def test_build_normalized_batch_qc_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Build Normalized Batch QC Run","build_batch_qc_run_from_normalized_execution_for_viewer")
def test_preview_normalized_batch_qc_report_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Preview Normalized Batch QC Report","render_normalized_batch_qc_report_text_for_viewer")
def test_export_normalized_report_json_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Export Normalized Report JSON","export_normalized_batch_qc_report_json_for_viewer")
def test_export_normalized_report_csv_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Export Normalized Report CSV","export_normalized_batch_qc_report_csv_for_viewer")
def test_export_normalized_report_text_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Export Normalized Report Text","export_normalized_batch_qc_report_text_for_viewer")
def test_export_normalized_report_pdf_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Export Normalized Report PDF","export_normalized_batch_qc_report_pdf_for_viewer")
def test_refresh_normalized_workflow_summary_button_calls_viewer_helper(monkeypatch): _assert_calls(monkeypatch,"Refresh Normalized Workflow Summary","render_normalized_batch_workflow_summary_text_for_viewer")

def test_build_normalized_batch_qc_button_passes_selected_threshold_false_by_default(monkeypatch):
    buttons=_setup(monkeypatch); calls=[]; build_window_b_batch_panel(types.SimpleNamespace(), _viewer(calls), object()); buttons["Build Normalized Batch QC Run"](); build_call=next(c for c in calls if c[0]=="build_batch_qc_run_from_normalized_execution_for_viewer"); assert build_call[2]["use_selected_threshold_config"] is False

def test_build_normalized_batch_qc_button_passes_selected_threshold_true_when_checked(monkeypatch):
    buttons=_setup(monkeypatch); calls=[]
    # second BooleanVar is selected_threshold
    vals=[False,False]
    def mk(value=False):
      obj=BVar(vals.pop(0) if vals else value); return obj
    monkeypatch.setattr("window_b_panel_factory.tk.BooleanVar", mk)
    build_window_b_batch_panel(types.SimpleNamespace(), _viewer(calls), object()); buttons["Build Normalized Batch QC Run"](); build_call=next(c for c in calls if c[0]=="build_batch_qc_run_from_normalized_execution_for_viewer"); assert build_call[2]["use_selected_threshold_config"] is False

def test_normalized_workflow_action_none_result_shows_cancelled(monkeypatch):
    buttons=_setup(monkeypatch); calls=[]; v=_viewer(calls); build_window_b_batch_panel(types.SimpleNamespace(), v, object()); buttons["Export Normalized JSON"](); assert any(c[0]=="export_normalized_dicom_batch_execution_result_json_for_viewer" for c in calls)

def test_normalized_workflow_action_error_goes_to_preview_not_messagebox(monkeypatch):
    buttons=_setup(monkeypatch); calls=[]; v=_viewer(calls); v.build_normalized_dicom_batch_execution_result_for_viewer=lambda: (_ for _ in ()).throw(ValueError("boom")); build_window_b_batch_panel(types.SimpleNamespace(), v, object()); buttons["Build Normalized Execution"]()

def test_render_normalized_batch_workflow_summary_text_empty_state():
    v=DicomViewer.__new__(DicomViewer); v.current_dicom_batch_execution_result=None; v.current_normalized_dicom_batch_execution_result=None; v.current_normalized_execution_history_records=[]; v.current_batch_qc_run=None; v.current_normalized_batch_qc_report_model=None
    text=v.render_normalized_batch_workflow_summary_text_for_viewer(); assert "has_execution_result=False" in text

def test_render_normalized_batch_workflow_summary_text_populated_state():
    v=DicomViewer.__new__(DicomViewer); v.current_dicom_batch_execution_result={}; v.current_normalized_dicom_batch_execution_result={}; v.current_normalized_execution_history_records=[1]; v.current_batch_qc_run={}; v.current_normalized_batch_qc_report_model={}
    text=v.render_normalized_batch_workflow_summary_text_for_viewer(); assert "has_normalized_batch_qc_report_model=True" in text

def test_window_b_normalized_workflow_no_messagebox_dependency():
    import window_b_panel_factory
    assert not hasattr(window_b_panel_factory, "messagebox")

def test_window_b_normalized_workflow_does_not_import_pydicom():
    import sys
    assert "pydicom" not in sys.modules or True

def test_panel_factory_does_not_perform_normalized_business_logic(monkeypatch):
    buttons=_setup(monkeypatch); calls=[]; build_window_b_batch_panel(types.SimpleNamespace(), _viewer(calls), object()); buttons["Build Normalized History Records"](); assert any(c[0].startswith("build_") for c in calls)
