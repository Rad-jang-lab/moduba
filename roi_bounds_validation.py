from __future__ import annotations
import csv, io, json, math, uuid
from datetime import datetime, timezone
from pathlib import Path
from dicom_batch_manifest import validate_dicom_batch_manifest
from roi_preset import validate_roi_preset, check_roi_preset_analysis_readiness

DEFAULT_ANALYSES=["snr","cnr","uniformity","mtf"]

def _to_dim(v):
    return int(v) if isinstance(v,(int,float)) and math.isfinite(v) and int(v)>0 else None

def _pt_in(x,y,rows,cols): return 0<=x<cols and 0<=y<rows

def validate_roi_definition_bounds(roi_definition, rows, columns):
    r=_to_dim(rows); c=_to_dim(columns)
    if r is None or c is None: raise ValueError("invalid_image_dimensions")
    d=dict(roi_definition or {})
    t=d.get("roi_type"); co=d.get("coordinates") or {}
    try:
        if t in {"rectangle","ellipse"}:
            x=float(co["x"]); y=float(co["y"]); w=float(co["width"]); h=float(co["height"])
            ok=all(math.isfinite(v) for v in [x,y,w,h]) and x>=0 and y>=0 and w>0 and h>0 and x+w<=c and y+h<=r
        elif t=="point":
            x=float(co["x"]); y=float(co["y"])
            ok=math.isfinite(x) and math.isfinite(y) and _pt_in(x,y,r,c)
        elif t in {"polygon","line"}:
            pts=co.get("points") or []; min_n=3 if t=="polygon" else 2
            ok=len(pts)>=min_n and all(_pt_in(float(p["x"]),float(p["y"]),r,c) for p in pts)
        else:
            ok=False
    except Exception:
        ok=False
    return {"bounds_status":"pass" if ok else "fail","reason":None if ok else "out_of_bounds_or_malformed"}

def build_roi_bounds_validation_result(manifest, roi_preset, analyses=None, metadata=None, generated_at=None, validation_id=None):
    m=validate_dicom_batch_manifest(manifest); p=validate_roi_preset(roi_preset); a=list(analyses or DEFAULT_ANALYSES)
    items=[]; valid=invalid=pass_n=fail_n=0
    for item in m.get("items") or []:
        status=item.get("status","invalid"); md=item.get("dicom_metadata") or {}; rows=_to_dim(md.get("Rows")); cols=_to_dim(md.get("Columns")); blocked=[]; roi_results=[]
        if status!="valid":
            invalid+=1; bstatus="not_evaluated"; blocked.append(item.get("reason") or "dicom_invalid")
            for roi in p.get("roi_definitions") or []:
                roi_results.append({"roi_id":roi.get("roi_id"),"label":roi.get("label",""),"roi_type":roi.get("roi_type"),"analysis_roles":list(roi.get("analysis_roles") or []),"bounds_status":"not_evaluated","reason":"dicom_invalid"})
        elif rows is None or cols is None:
            valid+=1; bstatus="not_evaluated"; blocked.append("missing_image_dimensions")
            for roi in p.get("roi_definitions") or []:
                roi_results.append({"roi_id":roi.get("roi_id"),"label":roi.get("label",""),"roi_type":roi.get("roi_type"),"analysis_roles":list(roi.get("analysis_roles") or []),"bounds_status":"not_evaluated","reason":"missing_image_dimensions"})
        else:
            valid+=1
            for roi in p.get("roi_definitions") or []:
                b=validate_roi_definition_bounds(roi, rows, cols)
                roi_results.append({"roi_id":roi.get("roi_id"),"label":roi.get("label",""),"roi_type":roi.get("roi_type"),"analysis_roles":list(roi.get("analysis_roles") or []),"bounds_status":b["bounds_status"],"reason":b["reason"]})
            bstatus="pass" if all(x["bounds_status"]=="pass" for x in roi_results) else "fail"
            pass_n += int(bstatus=="pass"); fail_n += int(bstatus=="fail")
        readiness={}
        for an in a:
            base=check_roi_preset_analysis_readiness(p, an)
            out=[]
            roles=set(sum([rr["analysis_roles"] for rr in roi_results],[]))
            for role in roles:
                rel=[rr for rr in roi_results if role in rr["analysis_roles"]]
                if rel and all(rr["bounds_status"]!="pass" for rr in rel): out.append(role)
            is_ready=base["is_ready"] and bstatus=="pass" and len(out)==0
            readiness[an]={"is_ready":is_ready,"required_roles":base["required_roles"],"missing_roles":base["missing_roles"],"out_of_bounds_roles":sorted(set(out))}
        items.append({"roi_bounds_item_schema_version":1,"item_id":item.get("item_id"),"dicom_path":item.get("path"),"dicom_status":status,"rows":rows,"columns":cols,"bounds_status":bstatus,"roi_results":roi_results,"analysis_readiness":readiness,"blocked_reasons":blocked})
    return validate_roi_bounds_validation_result({"roi_bounds_validation_schema_version":1,"validation_id":validation_id or f"rbv_{uuid.uuid4().hex}","generated_at":generated_at or datetime.now(timezone.utc).isoformat(),"metadata":dict(metadata or {}),"manifest_id":m.get("manifest_id"),"roi_preset_name":p.get("name"),"analyses":a,"item_count":len(items),"valid_item_count":valid,"invalid_item_count":invalid,"bounds_pass_item_count":pass_n,"bounds_fail_item_count":fail_n,"items":items})

def validate_roi_bounds_validation_result(result):
    r=dict(result)
    if r.get("roi_bounds_validation_schema_version")!=1: raise ValueError("unsupported schema")
    if not isinstance(r.get("items"),list): raise ValueError("items must be list")
    return r

def render_roi_bounds_validation_text(result):
    r=validate_roi_bounds_validation_result(result)
    lines=[f"Validation ID: {r['validation_id']}",f"Item Count: {r['item_count']}",f"Pass: {r['bounds_pass_item_count']}, Fail: {r['bounds_fail_item_count']}"]
    for i,it in enumerate(r["items"]): lines.append(f"- [{i}] {it['item_id']} | {it['bounds_status']} | blocked={it['blocked_reasons']}")
    return "\n".join(lines)+"\n"

def export_roi_bounds_validation_to_json(result,path=None):
    t=json.dumps(validate_roi_bounds_validation_result(result),ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)
    if path is not None: Path(path).write_text(t,encoding="utf-8")
    return t

def export_roi_bounds_validation_to_csv(result,path=None):
    r=validate_roi_bounds_validation_result(result)
    fields=["roi_bounds_validation_schema_version","validation_id","generated_at","item_index","item_id","dicom_path","dicom_status","rows","columns","item_bounds_status","roi_index","roi_id","roi_label","roi_type","analysis_roles_json","roi_bounds_status","reason","blocked_reasons_json"]
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=fields,lineterminator="\n"); w.writeheader()
    for i,it in enumerate(r["items"]):
        for j,roi in enumerate(it["roi_results"]):
            w.writerow({"roi_bounds_validation_schema_version":1,"validation_id":r["validation_id"],"generated_at":r["generated_at"],"item_index":i,"item_id":it["item_id"],"dicom_path":it["dicom_path"],"dicom_status":it["dicom_status"],"rows":it["rows"],"columns":it["columns"],"item_bounds_status":it["bounds_status"],"roi_index":j,"roi_id":roi["roi_id"],"roi_label":roi["label"],"roi_type":roi["roi_type"],"analysis_roles_json":json.dumps(roi["analysis_roles"],ensure_ascii=False,sort_keys=True),"roi_bounds_status":roi["bounds_status"],"reason":roi["reason"],"blocked_reasons_json":json.dumps(it["blocked_reasons"],ensure_ascii=False,sort_keys=True)})
    t=b.getvalue();
    if path is not None: Path(path).write_text(t,encoding="utf-8")
    return t

def load_roi_bounds_validation(path):
    try: x=json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e: raise ValueError("failed to load") from e
    return validate_roi_bounds_validation_result(x)
