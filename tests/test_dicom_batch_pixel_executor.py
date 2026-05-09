from __future__ import annotations

import copy
import sys

import pytest

from dicom_batch_pixel_executor import *
from dicom_batch_run_orchestrator import run_dicom_batch_execution_plan_with_executor
from tests.test_dicom_batch_execution import _plan, _preset


def test_pixel_executor_uses_injected_pixel_loader():
    c={"n":0}
    loader=lambda p: c.__setitem__("n",c["n"]+1) or {"pixel_array":[[1]],"Rows":1,"Columns":1}
    _=load_dicom_pixel_data_for_batch("/tmp/a.dcm", pixel_loader=loader)
    assert c["n"]==1

def test_pixel_executor_uses_injected_analysis_dispatcher():
    ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:{"pixel_array":[[1]]}, analysis_dispatcher=lambda t,i,c:{"x":1})
    assert ex({"analysis_type":"snr","roi_ids":["r1"]},{"dicom_path":"/tmp/a.dcm"},{})=={"x":1}

def test_pixel_executor_caches_pixel_data_per_item_context():
    c={"n":0}; ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:c.__setitem__("n",c["n"]+1) or {"pixel_array":[[1]]}, analysis_dispatcher=lambda t,i,c:{"x":1})
    ctx={}; item={"dicom_path":"/tmp/a.dcm"}; task={"analysis_type":"snr","roi_ids":["r1"]}
    ex(task,item,ctx); ex(task,item,ctx)
    assert c["n"]==1

def test_pixel_executor_missing_dicom_path_raises_value_error():
    ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:{"pixel_array":[[1]]}, analysis_dispatcher=lambda t,i,c:{"x":1})
    with pytest.raises(ValueError): ex({"analysis_type":"snr","roi_ids":["r1"]},{}, {})

def test_pixel_executor_unsupported_analysis_type_raises_value_error():
    ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:{"pixel_array":[[1]]}, analysis_dispatcher=lambda t,i,c:{"x":1})
    with pytest.raises(ValueError): ex({"analysis_type":"abc","roi_ids":["r1"]},{"dicom_path":"/tmp/a.dcm"}, {})

def test_pixel_executor_analysis_dispatcher_error_propagates_to_orchestrator_task_error():
    ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:{"pixel_array":[[1]]}, analysis_dispatcher=lambda *_: (_ for _ in ()).throw(RuntimeError("x")))
    r=run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=ex)
    assert any(t["status"]=="error" for t in r["items"][0]["task_results"])

def test_pixel_executor_with_orchestrator_completes_task_with_fake_dispatcher():
    ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:{"pixel_array":[[1]]}, analysis_dispatcher=lambda *_:{"result":1.0,"status":"ok"})
    r=run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=ex)
    assert any(t["status"]=="completed" for t in r["items"][0]["task_results"])

def test_pixel_executor_with_orchestrator_preserves_blocked_task():
    ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:(_ for _ in ()).throw(RuntimeError("should not")), analysis_dispatcher=lambda *_:{"result":1.0})
    r=run_dicom_batch_execution_plan_with_executor(_plan(), _preset(), analysis_executor=ex)
    assert any(t["status"]=="blocked" for t in r["items"][0]["task_results"])

def test_pixel_executor_does_not_mutate_task_item_context_inputs():
    ex=create_dicom_batch_pixel_analysis_executor(pixel_loader=lambda p:{"pixel_array":[[1]]}, analysis_dispatcher=lambda *_:{"x":1})
    task={"analysis_type":"snr","roi_ids":["r1"]}; item={"dicom_path":"/tmp/a.dcm"}; ctx={}
    bt,bi=copy.deepcopy(task),copy.deepcopy(item)
    ex(task,item,ctx)
    assert task==bt and item==bi

def test_pixel_executor_module_does_not_import_tkinter_or_messagebox():
    src=open("dicom_batch_pixel_executor.py",encoding="utf-8").read()
    assert "import tkinter" not in src and "messagebox" not in src

def test_pixel_executor_module_does_not_import_pydicom_at_module_import_time():
    src=open("dicom_batch_pixel_executor.py",encoding="utf-8").read()
    assert "import pydicom" not in src

def test_load_dicom_pixel_data_lazy_import_failure_is_clear(monkeypatch):
    monkeypatch.setattr("importlib.import_module", lambda name: (_ for _ in ()).throw(ImportError("x")))
    with pytest.raises(RuntimeError): load_dicom_pixel_data_for_batch("/tmp/a.dcm")
