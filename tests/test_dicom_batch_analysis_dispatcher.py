from __future__ import annotations

import copy
import pytest

from dicom_batch_analysis_dispatcher import *


def _task(t="snr", rois=None):
    return {"analysis_type": t, "roi_ids": rois or ["r1", "r2"]}


def test_create_existing_analysis_dispatcher_routes_snr():
    c={"v":0}; d=create_existing_analysis_dispatcher(snr_analyzer=lambda *_: c.__setitem__("v",1) or {"status":"ok","result":1.0,"signal_roi_id":"r1","noise_roi_id":"r2"})
    assert d(_task("snr"), {}, {"pixel_array":[[1]]})["result"]==1.0 and c["v"]==1

def test_create_existing_analysis_dispatcher_routes_cnr():
    d=create_existing_analysis_dispatcher(cnr_analyzer=lambda *_:{"status":"ok","result":1.0,"inputs":{"region_a_roi_id":"r1","region_b_roi_id":"r2","noise_roi_id":"r2"}})
    assert d(_task("cnr"), {}, {"pixel_array":[[1]]})["result"]==1.0

def test_create_existing_analysis_dispatcher_routes_uniformity():
    d=create_existing_analysis_dispatcher(uniformity_analyzer=lambda *_:{"status":"ok","result":{"value":1.0},"inputs":{"roi_ids":["r1"],"roi_count":1}})
    assert d(_task("uniformity", ["r1"]), {}, {"pixel_array":[[1]]})["result"]["value"]==1.0

def test_create_existing_analysis_dispatcher_routes_mtf():
    d=create_existing_analysis_dispatcher(mtf_analyzer=lambda *_:{"status":"ok","key_mtf_metrics":{"mtf50":1.0},"mtf_curve":{"frequency_cy_per_pixel":[0,1],"mtf":[1,0.5]}})
    assert "key_mtf_metrics" in d(_task("mtf"), {}, {"pixel_array":[[1]]})

def test_dispatcher_missing_analyzer_raises_value_error():
    d=create_existing_analysis_dispatcher()
    with pytest.raises(ValueError): d(_task("snr"), {}, {"pixel_array":[[1]]})

def test_dispatcher_unsupported_analysis_type_raises_value_error():
    d=create_existing_analysis_dispatcher(snr_analyzer=lambda *_:{})
    with pytest.raises(ValueError): d(_task("unknown"), {}, {"pixel_array":[[1]]})

def test_dispatcher_missing_roi_ids_raises_value_error():
    d=create_existing_analysis_dispatcher(snr_analyzer=lambda *_:{})
    with pytest.raises(ValueError): d({"analysis_type":"snr","roi_ids":[]}, {}, {"pixel_array":[[1]]})

def test_dispatcher_missing_pixel_array_raises_value_error():
    d=create_existing_analysis_dispatcher(snr_analyzer=lambda *_:{})
    with pytest.raises(ValueError): d(_task("snr"), {}, {})

def test_dispatcher_analyzer_return_must_be_dict():
    d=create_existing_analysis_dispatcher(snr_analyzer=lambda *_:None)
    with pytest.raises(ValueError): d(_task("snr"), {}, {"pixel_array":[[1]]})

def test_validate_batch_analysis_payload_calls_normalizer():
    assert validate_batch_analysis_payload("snr", {"status":"ok","result":1.0,"signal_roi_id":"r1","noise_roi_id":"r2"})["result"]==1.0

def test_dispatcher_does_not_mutate_task_item_context():
    d=create_existing_analysis_dispatcher(snr_analyzer=lambda *_:{"status":"ok","result":1.0,"signal_roi_id":"r1","noise_roi_id":"r2"})
    task=_task("snr"); item={"x":1}; ctx={"pixel_array":[[1]]}
    bt,bi,bc=copy.deepcopy(task),copy.deepcopy(item),copy.deepcopy(ctx)
    _=d(task,item,ctx)
    assert task==bt and item==bi and ctx==bc

def test_dispatcher_module_does_not_import_tkinter_messagebox_pydicom():
    src=open("dicom_batch_analysis_dispatcher.py",encoding="utf-8").read()
    assert "import tkinter" not in src and "messagebox" not in src and "import pydicom" not in src
