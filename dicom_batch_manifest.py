from __future__ import annotations
import csv, io, json, math, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pydicom
from pydicom.errors import InvalidDicomError

META_KEYS = ["PatientID","StudyInstanceUID","SeriesInstanceUID","SOPInstanceUID","Modality","StudyDate","SeriesDescription","Rows","Columns","PixelSpacing"]

def _sanitize(v: Any) -> Any:
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, list):
        return [_sanitize(x) for x in v]
    if isinstance(v, dict):
        return {k:_sanitize(x) for k,x in v.items()}
    return v

def discover_dicom_files(paths, recursive=True):
    files=[]
    for raw in list(paths or []):
        p=Path(raw)
        if p.is_file():
            files.append(str(p))
        elif p.is_dir():
            it = p.rglob('*') if recursive else p.glob('*')
            files.extend(str(x) for x in it if x.is_file())
    seen=set(); out=[]
    for p in sorted(files):
        if p not in seen:
            seen.add(p); out.append(p)
    return out

def build_dicom_batch_item(path, item_id=None):
    p=Path(path)
    item={"batch_item_schema_version":1,"item_id":item_id or f"item_{uuid.uuid4().hex}","path":str(p),"status":"invalid","reason":None,"dicom_metadata":{k:None for k in META_KEYS}}
    if not p.exists() or not p.is_file():
        item["reason"]="file_not_found"; return item
    try:
        ds=pydicom.dcmread(str(p), stop_before_pixels=True, force=False)
    except InvalidDicomError:
        item["reason"]="not_dicom"; return item
    except Exception:
        item["reason"]="read_error"; return item
    meta={}
    for k in META_KEYS:
        v=getattr(ds,k,None)
        if k=="PixelSpacing" and v is not None:
            v=[float(x) for x in v]
        elif k in ("Rows","Columns") and v is not None:
            v=int(v)
        elif v is not None:
            v=str(v)
        meta[k]=v
    item["status"]="valid"; item["dicom_metadata"]=meta
    return item

def build_dicom_batch_manifest(paths, recursive=True, metadata=None, generated_at=None, manifest_id=None):
    source=list(paths or [])
    files=discover_dicom_files(source, recursive=recursive)
    items=[build_dicom_batch_item(p, item_id=f"item_{i:04d}") for i,p in enumerate(files)]
    valid=sum(1 for i in items if i["status"]=="valid")
    invalid=len(items)-valid
    m={"dicom_batch_manifest_schema_version":1,"manifest_id":manifest_id or f"manifest_{uuid.uuid4().hex}","generated_at":generated_at or datetime.now(timezone.utc).isoformat(),"metadata":dict(metadata or {}),"source_paths":source,"recursive":bool(recursive),"item_count":len(items),"valid_item_count":valid,"invalid_item_count":invalid,"items":items}
    return validate_dicom_batch_manifest(m)

def validate_dicom_batch_manifest(manifest):
    m=dict(manifest)
    if m.get("dicom_batch_manifest_schema_version")!=1: raise ValueError("unsupported manifest schema")
    items=m.get("items")
    if not isinstance(items,list): raise ValueError("items must be list")
    for it in items:
        if not isinstance(it,dict) or it.get("batch_item_schema_version")!=1: raise ValueError("malformed item")
        if it.get("status") not in {"valid","invalid"}: raise ValueError("invalid status")
    return m

def render_dicom_batch_manifest_text(manifest):
    m=validate_dicom_batch_manifest(manifest)
    lines=[f"Manifest ID: {m.get('manifest_id')}",f"Generated At: {m.get('generated_at')}",f"Item Count: {m.get('item_count')}",f"Valid: {m.get('valid_item_count')}, Invalid: {m.get('invalid_item_count')}"]
    for i,it in enumerate(m.get('items') or []):
        lines.append(f"- [{i}] {it.get('item_id')} | {it.get('path')} | {it.get('status')} | reason={it.get('reason')}")
    return "\n".join(lines)+"\n"

def export_dicom_batch_manifest_to_json(manifest, path=None):
    text=json.dumps(_sanitize(validate_dicom_batch_manifest(manifest)),ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)
    if path is not None: Path(path).write_text(text,encoding='utf-8')
    return text

def export_dicom_batch_manifest_to_csv(manifest, path=None):
    m=validate_dicom_batch_manifest(manifest)
    f=["dicom_batch_manifest_schema_version","manifest_id","generated_at","item_index","item_id","path","status","reason","PatientID","StudyInstanceUID","SeriesInstanceUID","SOPInstanceUID","Modality","StudyDate","SeriesDescription","Rows","Columns","PixelSpacing_json"]
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=f,lineterminator='\n'); w.writeheader()
    for idx,it in enumerate(m.get('items') or []):
        md=it.get('dicom_metadata') or {}
        w.writerow({"dicom_batch_manifest_schema_version":1,"manifest_id":m.get('manifest_id'),"generated_at":m.get('generated_at'),"item_index":idx,"item_id":it.get('item_id'),"path":it.get('path'),"status":it.get('status'),"reason":it.get('reason'),"PatientID":md.get('PatientID'),"StudyInstanceUID":md.get('StudyInstanceUID'),"SeriesInstanceUID":md.get('SeriesInstanceUID'),"SOPInstanceUID":md.get('SOPInstanceUID'),"Modality":md.get('Modality'),"StudyDate":md.get('StudyDate'),"SeriesDescription":md.get('SeriesDescription'),"Rows":md.get('Rows'),"Columns":md.get('Columns'),"PixelSpacing_json":json.dumps(md.get('PixelSpacing'),ensure_ascii=False,sort_keys=True)})
    text=b.getvalue();
    if path is not None: Path(path).write_text(text,encoding='utf-8')
    return text

def load_dicom_batch_manifest(path):
    try:
        m=json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as e:
        raise ValueError("failed to load manifest") from e
    return validate_dicom_batch_manifest(m)
