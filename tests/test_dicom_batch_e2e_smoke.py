from __future__ import annotations

import copy
from analysis_batch_qc import export_batch_qc_run_to_csv
from analysis_batch_qc_report import (
    build_batch_qc_report_model,
    export_batch_qc_report_to_json,
    export_batch_qc_report_to_pdf,
    export_batch_qc_report_to_text,
)
from analysis_history_store import load_analysis_history_records
from dicom_batch_execution import build_dicom_batch_execution_result
from dicom_batch_execution_plan import build_dicom_batch_execution_plan
from dicom_batch_history_adapter import (
    append_dicom_batch_execution_history_records,
    build_analysis_history_records_from_dicom_batch_execution_result,
    build_batch_qc_run_from_dicom_batch_execution_result,
)
from dicom_batch_pixel_executor import create_dicom_batch_pixel_analysis_executor
from tests.test_dicom_batch_execution_plan import _bp, _bp_item, _bv, _bv_item
from tests.test_dicom_batch_execution import _preset
from tests.test_analysis_threshold_integration import _cfg


def _plan():
    bp = _bp([_bp_item("i1", ["snr", "cnr", "uniformity", "mtf"]), _bp_item("i2", ["snr"])])
    bv = _bv([_bv_item("i1", "pass", True), _bv_item("i2", "pass", True)])
    return build_dicom_batch_execution_plan(bp, bv)


def _executor(loader_calls):
    px = create_dicom_batch_pixel_analysis_executor(
        pixel_loader=lambda path: loader_calls.__setitem__(path, loader_calls.get(path, 0) + 1) or {"pixel_array": [[1]], "Rows": 1, "Columns": 1},
        analysis_dispatcher=lambda task, item, ctx: (
            {"status": "ok", "result": 1.0, "signal_roi_id": "r1", "noise_roi_id": "r1"}
            if task.get("analysis_type") == "snr"
            else {"status": "ok", "result": 1.0, "inputs": {"region_a_roi_id": "r1", "region_b_roi_id": "r1", "noise_roi_id": "r1"}}
            if task.get("analysis_type") == "cnr"
            else {"status": "ok", "result": {"value": 1.0}, "inputs": {"roi_ids": ["r1"], "roi_count": 1}}
            if task.get("analysis_type") == "uniformity"
            else {"status": "ok", "key_mtf_metrics": {"mtf50": 1.0}, "mtf_curve": {"frequency_cy_per_pixel": [0.0, 1.0], "mtf": [1.0, 0.5]}}
        ),
    )
    return lambda dpath, atype, roi_defs, task: px(task, {"dicom_path": dpath}, {"dicom_cache": {}})


def test_dicom_batch_e2e_smoke_completed_pipeline(tmp_path):
    calls = {}
    result = build_dicom_batch_execution_result(_plan(), _preset(), analysis_executor=_executor(calls))
    records = build_analysis_history_records_from_dicom_batch_execution_result(result)
    qc = build_batch_qc_run_from_dicom_batch_execution_result(result)
    report = build_batch_qc_report_model(qc)
    assert any(t["status"] in {"completed", "blocked"} for t in result["items"][0]["task_results"])
    assert len(records) > 0 and qc["item_count"] == len(records)
    assert "batch_qc_report_schema_version" in export_batch_qc_report_to_json(report)
    assert "record_id" in export_batch_qc_run_to_csv(qc)
    assert "Batch QC Report" in export_batch_qc_report_to_text(report)
    assert export_batch_qc_report_to_pdf(report).startswith(b"%PDF-")


def test_dicom_batch_e2e_history_jsonl_roundtrip(tmp_path):
    result = build_dicom_batch_execution_result(_plan(), _preset(), analysis_executor=_executor({}))
    recs = build_analysis_history_records_from_dicom_batch_execution_result(result)
    p = tmp_path / "h.jsonl"
    append_dicom_batch_execution_history_records(str(p), recs)
    out = load_analysis_history_records(p)
    assert out[0]["record_id"] == recs[0]["record_id"] and out[0]["metadata"]["dicom_path"]


def test_dicom_batch_e2e_blocked_and_error_tasks_survive_downstream():
    plan = _plan(); plan["items"][0]["tasks"][0]["is_executable"] = False
    bad = lambda d, a, r, t: (_ for _ in ()).throw(RuntimeError("x")) if a == "cnr" else _executor({})(d, a, r, t)
    result = build_dicom_batch_execution_result(plan, _preset(), analysis_executor=bad)
    recs = build_analysis_history_records_from_dicom_batch_execution_result(result)
    qc = build_batch_qc_run_from_dicom_batch_execution_result(result)
    assert any(t["status"] == "blocked" for t in result["items"][0]["task_results"])
    assert any(t["status"] in {"error", "blocked"} for t in result["items"][0]["task_results"])
    assert len(recs) > 0 and qc["item_count"] > 0


def test_dicom_batch_e2e_pixel_loader_cache():
    calls = {}
    _ = build_dicom_batch_execution_result(_plan(), _preset(), analysis_executor=_executor(calls))
    assert all(v >= 1 for v in calls.values())


def test_dicom_batch_e2e_does_not_mutate_inputs():
    p = _plan(); r = _preset(); bp = copy.deepcopy(p); br = copy.deepcopy(r)
    _ = build_dicom_batch_execution_result(p, r, analysis_executor=_executor({}))
    assert p == bp and r == br


def test_dicom_batch_e2e_threshold_policy_default_none():
    result = build_dicom_batch_execution_result(_plan(), _preset(), analysis_executor=_executor({}))
    qc = build_batch_qc_run_from_dicom_batch_execution_result(result, threshold_config=None)
    assert all(i.get("threshold_evaluation") is None for i in qc["items"])


def test_dicom_batch_e2e_threshold_policy_explicit_config():
    result = build_dicom_batch_execution_result(_plan(), _preset(), analysis_executor=_executor({}))
    qc = build_batch_qc_run_from_dicom_batch_execution_result(result, threshold_config=_cfg())
    report = build_batch_qc_report_model(qc)
    assert any(i.get("threshold_evaluation") is not None for i in qc["items"]) and "threshold_status_counts" in report["summary"]
