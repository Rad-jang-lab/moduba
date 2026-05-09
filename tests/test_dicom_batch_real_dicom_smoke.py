from __future__ import annotations

import copy
import importlib
from pathlib import Path

import numpy as np
import pytest

from analysis_batch_qc import export_batch_qc_run_to_csv
from analysis_batch_qc_report import build_batch_qc_report_model, export_batch_qc_report_to_json, export_batch_qc_report_to_pdf
from dicom_batch_execution import build_dicom_batch_execution_result
from dicom_batch_execution_plan import build_dicom_batch_execution_plan
from dicom_batch_history_adapter import build_analysis_history_records_from_dicom_batch_execution_result, build_batch_qc_run_from_dicom_batch_execution_result
from dicom_batch_pixel_executor import create_dicom_batch_pixel_analysis_executor, load_dicom_pixel_data_for_batch
from tests.test_analysis_threshold_integration import _cfg
from tests.test_dicom_batch_execution import _preset
from tests.test_dicom_batch_execution_plan import _bp, _bp_item, _bv, _bv_item


def _create_minimal_test_dicom(path: Path, pixel_array: np.ndarray, *, slope=None, intercept=None, include_pixel_data=True):
    pydicom = pytest.importorskip("pydicom")
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.Rows = int(pixel_array.shape[0])
    ds.Columns = int(pixel_array.shape[1])
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    if slope is not None:
        ds.RescaleSlope = float(slope)
    if intercept is not None:
        ds.RescaleIntercept = float(intercept)
    if include_pixel_data:
        ds.PixelData = pixel_array.astype(np.uint16).tobytes()
    pydicom.filewriter.dcmwrite(str(path), ds, enforce_file_format=True)
    return path


def _plan_for_path(path: str):
    bp = _bp([_bp_item("i1")])
    bp["items"][0]["dicom_path"] = path
    bv = _bv([_bv_item("i1", "pass", True)])
    return build_dicom_batch_execution_plan(bp, bv)


def _dispatcher(task, item, context):
    px = context["pixel_array"]
    assert tuple(px.shape) == (2, 2)
    return {"status": "ok", "result": float(px.sum()), "signal_roi_id": "r1", "noise_roi_id": "r1"}


def test_load_dicom_pixel_data_for_batch_reads_real_pydicom_fixture(tmp_path):
    path = _create_minimal_test_dicom(tmp_path / "a.dcm", np.array([[1, 2], [3, 4]], dtype=np.uint16))
    out = load_dicom_pixel_data_for_batch(str(path))
    assert out["pixel_array"].shape == (2, 2)
    assert int(out["pixel_array"][1, 1]) == 4
    assert out["metadata"]["dicom_path"] == str(path)
    assert out["metadata"]["rows"] == 2 and out["metadata"]["columns"] == 2


def test_load_dicom_pixel_data_for_batch_rescale_metadata_is_exposed(tmp_path):
    path = _create_minimal_test_dicom(tmp_path / "b.dcm", np.array([[5, 6], [7, 8]], dtype=np.uint16), slope=2, intercept=10)
    out = load_dicom_pixel_data_for_batch(str(path))
    assert int(out["pixel_array"][0, 0]) == 5
    assert out["metadata"]["rescale_slope"] == 2.0 and out["metadata"]["rescale_intercept"] == 10.0


def test_load_dicom_pixel_data_for_batch_unreadable_file_error_is_clear(tmp_path):
    bad = tmp_path / "bad.dcm"
    bad.write_text("not dicom")
    with pytest.raises(Exception, match="DICOM|pixel_array|pydicom"):
        load_dicom_pixel_data_for_batch(str(bad))


def test_load_dicom_pixel_data_for_batch_missing_pixel_data_error_is_clear(tmp_path):
    path = _create_minimal_test_dicom(tmp_path / "missing_pixel.dcm", np.array([[1, 2], [3, 4]], dtype=np.uint16), include_pixel_data=False)
    with pytest.raises(RuntimeError, match="pixel_array"):
        load_dicom_pixel_data_for_batch(str(path))


def test_load_dicom_pixel_data_without_pydicom_reports_clear_error(monkeypatch):
    real = importlib.import_module

    def _fake(name, *a, **k):
        if name == "pydicom":
            raise ImportError("missing")
        return real(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", _fake)
    with pytest.raises(RuntimeError, match="pydicom"):
        load_dicom_pixel_data_for_batch("x.dcm")


def test_real_dicom_e2e_to_history_qc_report(tmp_path):
    path = _create_minimal_test_dicom(tmp_path / "e2e.dcm", np.array([[1, 2], [3, 4]], dtype=np.uint16))
    plan = _plan_for_path(str(path))
    result = build_dicom_batch_execution_result(plan, _preset(), analysis_executor=lambda d, a, r, t: create_dicom_batch_pixel_analysis_executor(analysis_dispatcher=_dispatcher)(t, {"dicom_path": d, "item_id": "i1"}, {"dicom_cache": {}}))
    recs = build_analysis_history_records_from_dicom_batch_execution_result(result)
    qc = build_batch_qc_run_from_dicom_batch_execution_result(result, threshold_config=_cfg())
    report = build_batch_qc_report_model(qc)
    assert recs and qc["item_count"] >= 1
    assert export_batch_qc_report_to_pdf(report).startswith(b"%PDF-")
    assert "batch_qc_report_schema_version" in export_batch_qc_report_to_json(report)
    assert "record_id" in export_batch_qc_run_to_csv(qc)


def test_real_dicom_smoke_does_not_mutate_execution_plan(tmp_path):
    path = _create_minimal_test_dicom(tmp_path / "m.dcm", np.array([[1, 1], [1, 1]], dtype=np.uint16))
    p = _plan_for_path(str(path)); bp = copy.deepcopy(p)
    _ = build_dicom_batch_execution_result(p, _preset(), analysis_executor=lambda d, a, r, t: create_dicom_batch_pixel_analysis_executor(analysis_dispatcher=_dispatcher)(t, {"dicom_path": d, "item_id": "i1"}, {"dicom_cache": {}}))
    assert p == bp


def test_pixel_executor_still_does_not_import_pydicom_at_module_import_time():
    src = Path("dicom_batch_pixel_executor.py").read_text(encoding="utf-8")
    assert "import pydicom" not in src
