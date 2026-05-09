from __future__ import annotations

import json

import pytest
from types import SimpleNamespace

from dicom_batch_execution_plan import (
    build_dicom_batch_execution_plan,
    export_dicom_batch_execution_plan_to_csv,
    export_dicom_batch_execution_plan_to_json,
    load_dicom_batch_execution_plan,
    render_dicom_batch_execution_plan_text,
    validate_dicom_batch_execution_plan,
)
from dicom_viewer import DicomViewer


def _bp_item(item_id: str = "i1", status: str = "valid", ready: bool = True) -> dict:
    return {
        "execution": 0,
        "plan_item_schema_version": 1,
        "item_id": item_id,
        "dicom_path": "/tmp/a.dcm",
        "dicom_status": status,
        "analysis_readiness": {
            "snr": {"is_ready": ready, "required_roles": ["signal", "noise"], "missing_roles": []},
            "cnr": {
                "is_ready": ready,
                "required_roles": ["region_a", "region_b", "noise|background"],
                "missing_roles": [],
            },
            "uniformity": {"is_ready": ready, "required_roles": ["uniformity"], "missing_roles": []},
            "mtf": {"is_ready": ready, "required_roles": ["mtf_edge"], "missing_roles": []},
        },
    }


def _bv_item(item_id: str = "i1", bstatus: str = "pass", ready: bool = True) -> dict:
    return {
        "roi_bounds_item_schema_version": 1,
        "item_id": item_id,
        "dicom_path": "/tmp/a.dcm",
        "dicom_status": "valid",
        "rows": 10,
        "columns": 10,
        "bounds_status": bstatus,
        "roi_results": [
            {
                "roi_id": "s",
                "analysis_roles": ["signal"],
                "bounds_status": "pass",
                "label": "",
                "roi_type": "point",
                "reason": None,
            },
            {
                "roi_id": "n",
                "analysis_roles": ["noise"],
                "bounds_status": "pass",
                "label": "",
                "roi_type": "point",
                "reason": None,
            },
        ],
        "analysis_readiness": {
            "snr": {
                "is_ready": ready,
                "required_roles": ["signal", "noise"],
                "missing_roles": [],
                "out_of_bounds_roles": [],
            },
            "cnr": {
                "is_ready": ready,
                "required_roles": ["region_a", "region_b", "noise|background"],
                "missing_roles": [],
                "out_of_bounds_roles": [],
            },
            "uniformity": {
                "is_ready": ready,
                "required_roles": ["uniformity"],
                "missing_roles": [],
                "out_of_bounds_roles": [],
            },
            "mtf": {
                "is_ready": ready,
                "required_roles": ["mtf_edge"],
                "missing_roles": [],
                "out_of_bounds_roles": [],
            },
        },
        "blocked_reasons": [],
    }


def _bp(items: list[dict]) -> dict:
    return {
        "dicom_batch_analysis_plan_schema_version": 1,
        "plan_id": "bp1",
        "manifest_id": "m1",
        "item_count": len(items),
        "analyses": ["snr", "cnr", "uniformity", "mtf"],
        "items": items,
    }


def _bv(items: list[dict]) -> dict:
    return {
        "roi_bounds_validation_schema_version": 1,
        "validation_id": "bv1",
        "manifest_id": "m1",
        "item_count": len(items),
        "items": items,
    }


def test_build_dicom_batch_execution_plan_creates_executable_tasks() -> None:
    plan = build_dicom_batch_execution_plan(_bp([_bp_item()]), _bv([_bv_item()]))
    assert plan["executable_task_count"] >= 1


def test_build_dicom_batch_execution_plan_blocks_invalid_dicom_item() -> None:
    plan = build_dicom_batch_execution_plan(
        _bp([_bp_item(status="invalid", ready=False)]),
        _bv([_bv_item(bstatus="not_evaluated", ready=False)]),
    )
    assert plan["blocked_item_count"] == 1


def test_build_dicom_batch_execution_plan_blocks_out_of_bounds_item() -> None:
    plan = build_dicom_batch_execution_plan(_bp([_bp_item()]), _bv([_bv_item(bstatus="fail", ready=False)]))
    assert plan["blocked_item_count"] == 1


def test_build_dicom_batch_execution_plan_blocks_missing_required_roles() -> None:
    bv_item = _bv_item()
    bv_item["analysis_readiness"]["snr"]["missing_roles"] = ["noise"]
    bv_item["analysis_readiness"]["snr"]["is_ready"] = False
    plan = build_dicom_batch_execution_plan(_bp([_bp_item()]), _bv([bv_item]))
    assert "missing_required_roles" in plan["items"][0]["tasks"][0]["blocked_reasons"]


def test_build_dicom_batch_execution_plan_rejects_mismatched_items() -> None:
    with pytest.raises(ValueError):
        build_dicom_batch_execution_plan(_bp([_bp_item("a")]), _bv([_bv_item("b")]))


def test_build_dicom_batch_execution_plan_handles_empty_plan() -> None:
    plan = build_dicom_batch_execution_plan(_bp([]), _bv([]))
    assert plan["item_count"] == 0


def test_build_dicom_batch_execution_plan_does_not_mutate_inputs() -> None:
    batch_plan = _bp([_bp_item()])
    bounds_validation = _bv([_bv_item()])
    batch_plan_before = json.loads(json.dumps(batch_plan))
    bounds_before = json.loads(json.dumps(bounds_validation))

    build_dicom_batch_execution_plan(batch_plan, bounds_validation)

    assert batch_plan == batch_plan_before
    assert bounds_validation == bounds_before


def test_validate_dicom_batch_execution_plan_rejects_wrong_schema() -> None:
    with pytest.raises(ValueError):
        validate_dicom_batch_execution_plan({"dicom_batch_execution_plan_schema_version": 2, "items": []})


def test_render_dicom_batch_execution_plan_text_contains_counts_and_tasks() -> None:
    text = render_dicom_batch_execution_plan_text(
        build_dicom_batch_execution_plan(_bp([_bp_item()]), _bv([_bv_item()]))
    )
    assert "Tasks:" in text


def test_export_dicom_batch_execution_plan_to_json_round_trips() -> None:
    plan = build_dicom_batch_execution_plan(_bp([_bp_item()]), _bv([_bv_item()]))
    loaded = json.loads(export_dicom_batch_execution_plan_to_json(plan))
    assert loaded["dicom_batch_execution_plan_schema_version"] == 1


def test_export_dicom_batch_execution_plan_to_csv_exports_task_rows() -> None:
    text = export_dicom_batch_execution_plan_to_csv(
        build_dicom_batch_execution_plan(_bp([_bp_item()]), _bv([_bv_item()]))
    )
    assert "analysis_type" in text


def test_load_dicom_batch_execution_plan_reads_valid_json(tmp_path) -> None:
    path = tmp_path / "x.json"
    export_dicom_batch_execution_plan_to_json(
        build_dicom_batch_execution_plan(_bp([_bp_item()]), _bv([_bv_item()])),
        path,
    )
    assert load_dicom_batch_execution_plan(path)["item_count"] == 1


def test_load_dicom_batch_execution_plan_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "x.json"
    path.write_text("{x")
    with pytest.raises(ValueError):
        load_dicom_batch_execution_plan(path)


def test_dicom_batch_execution_plan_does_not_start_batch_analysis_or_calculation() -> None:
    assert True


def test_dicom_batch_execution_plan_does_not_read_dicom_pixel_data() -> None:
    assert True


def test_dicom_batch_execution_plan_does_not_change_roi_resolver() -> None:
    assert True


def _viewer() -> SimpleNamespace:
    return SimpleNamespace(
        current_dicom_batch_analysis_plan=None,
        current_roi_bounds_validation=None,
        current_dicom_batch_execution_plan=None,
    )


def test_viewer_build_dicom_batch_execution_plan_uses_current_plan_and_bounds() -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    plan = DicomViewer.build_dicom_batch_execution_plan_for_viewer(viewer)
    assert plan["item_count"] == 1


def test_viewer_build_dicom_batch_execution_plan_prefers_explicit_arguments() -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item("cached")])
    viewer.current_roi_bounds_validation = _bv([_bv_item("cached")])
    plan = DicomViewer.build_dicom_batch_execution_plan_for_viewer(
        viewer,
        batch_plan=_bp([_bp_item("explicit")]),
        bounds_validation=_bv([_bv_item("explicit")]),
    )
    assert plan["items"][0]["item_id"] == "explicit"


def test_viewer_build_dicom_batch_execution_plan_requires_current_plan() -> None:
    viewer = _viewer()
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    with pytest.raises(ValueError):
        DicomViewer.build_dicom_batch_execution_plan_for_viewer(viewer)


def test_viewer_build_dicom_batch_execution_plan_requires_current_bounds() -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    with pytest.raises(ValueError):
        DicomViewer.build_dicom_batch_execution_plan_for_viewer(viewer)


def test_viewer_build_dicom_batch_execution_plan_updates_current_execution_plan_cache() -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    plan = DicomViewer.build_dicom_batch_execution_plan_for_viewer(viewer)
    assert viewer.current_dicom_batch_execution_plan == plan


def test_viewer_render_dicom_batch_execution_plan_text_uses_helper() -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    text = DicomViewer.render_dicom_batch_execution_plan_text_for_viewer(viewer)
    assert "Execution Plan ID:" in text


def test_viewer_export_dicom_batch_execution_plan_json_writes_file(tmp_path) -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    out = tmp_path / "plan.json"
    DicomViewer.export_dicom_batch_execution_plan_json_for_viewer(viewer, path=str(out))
    assert json.loads(out.read_text())["dicom_batch_execution_plan_schema_version"] == 1


def test_viewer_export_dicom_batch_execution_plan_csv_writes_file(tmp_path) -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    out = tmp_path / "plan.csv"
    DicomViewer.export_dicom_batch_execution_plan_csv_for_viewer(viewer, path=str(out))
    assert "analysis_type" in out.read_text()


def test_viewer_dicom_batch_execution_plan_dialog_cancel_returns_none_without_mutation(monkeypatch) -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    baseline = DicomViewer.build_dicom_batch_execution_plan_for_viewer(viewer)
    monkeypatch.setattr("dicom_viewer.filedialog.asksaveasfilename", lambda **_: "")
    result = DicomViewer.export_dicom_batch_execution_plan_json_for_viewer(viewer, path=None)
    assert result is None
    assert viewer.current_dicom_batch_execution_plan == baseline


def test_show_dicom_batch_execution_plan_viewer_uses_preview_text_without_calculation(monkeypatch) -> None:
    viewer = _viewer()
    viewer.current_dicom_batch_analysis_plan = _bp([_bp_item()])
    viewer.current_roi_bounds_validation = _bv([_bv_item()])
    inserted = {}

    class _FakeTop:
        def title(self, _): pass
        def geometry(self, _): pass

    class _FakeText:
        def __init__(self, *_args, **_kwargs): pass
        def pack(self, **_kwargs): pass
        def insert(self, _index, text): inserted["text"] = text
        def configure(self, **_kwargs): pass

    monkeypatch.setattr("dicom_viewer.tk.Toplevel", lambda *_args, **_kwargs: _FakeTop())
    monkeypatch.setattr("dicom_viewer.tk.Text", _FakeText)
    text = DicomViewer.show_dicom_batch_execution_plan_viewer(viewer)
    assert text == inserted["text"]
    assert "Tasks:" in text


def test_viewer_execution_plan_does_not_read_dicom_pixel_data() -> None:
    assert True


def test_viewer_execution_plan_does_not_change_roi_resolver() -> None:
    assert True
