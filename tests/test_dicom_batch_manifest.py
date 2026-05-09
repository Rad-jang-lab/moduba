from __future__ import annotations
import json
import pytest
from pathlib import Path
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from dicom_batch_manifest import *
from dicom_viewer import DicomViewer
from tests.test_analysis_result_model import _viewer_for_export


def _mk_dicom(path: Path):
    fm=FileMetaDataset(); fm.MediaStorageSOPClassUID=generate_uid(); fm.MediaStorageSOPInstanceUID=generate_uid(); fm.TransferSyntaxUID=ExplicitVRLittleEndian
    ds=FileDataset(str(path),{},file_meta=fm,preamble=b"\0"*128)
    ds.PatientID="P1"; ds.StudyInstanceUID=generate_uid(); ds.SeriesInstanceUID=generate_uid(); ds.SOPInstanceUID=generate_uid(); ds.Modality="CT"; ds.StudyDate="20260101"; ds.SeriesDescription="S"; ds.Rows=16; ds.Columns=16; ds.PixelSpacing=[1.0,1.0]
    ds.save_as(str(path))

def test_discover_dicom_files_accepts_file_paths(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p)
    assert discover_dicom_files([str(p)])==[str(p)]

def test_discover_dicom_files_recurses_directories(tmp_path):
    d=tmp_path/'d'; d.mkdir(); p=d/'a.dcm'; _mk_dicom(p)
    assert str(p) in discover_dicom_files([str(tmp_path)], recursive=True)

def test_discover_dicom_files_deduplicates_and_sorts(tmp_path):
    a=tmp_path/'b.dcm'; b=tmp_path/'a.dcm'; _mk_dicom(a); _mk_dicom(b)
    out=discover_dicom_files([str(a),str(b),str(a)])
    assert out==sorted([str(a),str(b)])

def test_build_dicom_batch_item_valid_dicom_metadata(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); it=build_dicom_batch_item(str(p), item_id='x')
    assert it['status']=='valid' and it['item_id']=='x' and it['dicom_metadata']['PatientID']=='P1'

def test_build_dicom_batch_item_invalid_missing_file():
    assert build_dicom_batch_item('/nope.dcm')['status']=='invalid'

def test_build_dicom_batch_item_invalid_non_dicom_file(tmp_path):
    p=tmp_path/'a.txt'; p.write_text('x')
    assert build_dicom_batch_item(str(p))['reason']=='not_dicom'

def test_build_dicom_batch_manifest_counts_valid_invalid_items(tmp_path):
    d=tmp_path/'d'; d.mkdir(); good=d/'a.dcm'; bad=d/'b.txt'; _mk_dicom(good); bad.write_text('x')
    m=build_dicom_batch_manifest([str(d)])
    assert m['valid_item_count']==1 and m['invalid_item_count']==1

def test_build_dicom_batch_manifest_handles_empty_paths():
    assert build_dicom_batch_manifest([])['item_count']==0

def test_build_dicom_batch_manifest_does_not_mutate_input_paths(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); src=[str(p)]; base=list(src); build_dicom_batch_manifest(src); assert src==base

def test_validate_dicom_batch_manifest_rejects_wrong_schema():
    with pytest.raises(ValueError): validate_dicom_batch_manifest({'dicom_batch_manifest_schema_version':9,'items':[]})

def test_render_dicom_batch_manifest_text_contains_counts_and_items(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); t=render_dicom_batch_manifest_text(build_dicom_batch_manifest([str(p)])); assert 'Item Count' in t and 'valid' in t

def test_export_dicom_batch_manifest_to_json_round_trips(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); m=build_dicom_batch_manifest([str(p)]); assert json.loads(export_dicom_batch_manifest_to_json(m))['item_count']==1

def test_export_dicom_batch_manifest_to_csv_exports_item_rows(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); txt=export_dicom_batch_manifest_to_csv(build_dicom_batch_manifest([str(p)])); assert 'item_id' in txt

def test_load_dicom_batch_manifest_reads_valid_json(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); m=build_dicom_batch_manifest([str(p)]); out=tmp_path/'m.json'; export_dicom_batch_manifest_to_json(m,out); assert load_dicom_batch_manifest(out)['item_count']==1

def test_load_dicom_batch_manifest_rejects_malformed_json(tmp_path):
    p=tmp_path/'m.json'; p.write_text('{x')
    with pytest.raises(ValueError): load_dicom_batch_manifest(p)

def test_viewer_build_dicom_batch_manifest_for_viewer_uses_paths(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); v=_viewer_for_export(); assert DicomViewer.build_dicom_batch_manifest_for_viewer(v, paths=[str(p)])['item_count']==1

def test_viewer_export_dicom_batch_manifest_json_writes_file(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); out=tmp_path/'m.json'; v=_viewer_for_export(); DicomViewer.export_dicom_batch_manifest_json_for_viewer(v,path=str(out),source_paths=[str(p)]); assert out.exists()

def test_viewer_export_dicom_batch_manifest_csv_writes_file(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); out=tmp_path/'m.csv'; v=_viewer_for_export(); DicomViewer.export_dicom_batch_manifest_csv_for_viewer(v,path=str(out),source_paths=[str(p)]); assert out.exists()

def test_viewer_dicom_batch_manifest_dialog_cancel_returns_none_without_mutation(monkeypatch):
    v=_viewer_for_export(); baseline=getattr(v,'current_threshold_config',None); monkeypatch.setattr('dicom_viewer.filedialog.askopenfilenames', lambda **_: ()); assert DicomViewer.build_dicom_batch_manifest_for_viewer(v) is None; assert getattr(v,'current_threshold_config',None)==baseline

def test_dicom_batch_manifest_does_not_start_batch_analysis(tmp_path):
    p=tmp_path/'a.dcm'; _mk_dicom(p); v=_viewer_for_export(); _=DicomViewer.build_dicom_batch_manifest_for_viewer(v, paths=[str(p)]); assert not hasattr(v,'dicom_batch_execution_state')
