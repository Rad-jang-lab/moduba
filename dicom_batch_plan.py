from __future__ import annotations
import csv, io, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from dicom_batch_manifest import validate_dicom_batch_manifest
from roi_preset import validate_roi_preset, check_roi_preset_analysis_readiness

DEFAULT=["snr","cnr","uniformity","mtf"]

def build_dicom_batch_analysis_plan(manifest, roi_preset, analyses=None, metadata=None, generated_at=None, plan_id=None):
    m=validate_dicom_batch_manifest(manifest); p=validate_roi_preset(roi_preset); a=list(analyses or DEFAULT)
    items=[]; ready=0; blocked=0
    for it in m.get('items',[]):
        rid={k:check_roi_preset_analysis_readiness(p,k) for k in a}
        dstatus=it.get('status','invalid'); reasons=[]
        if dstatus!='valid': reasons.append(it.get('reason') or 'dicom_invalid')
        any_ready=(dstatus=='valid') and any(x.get('is_ready') for x in rid.values())
        if any_ready: ready+=1
        else: blocked+=1
        items.append({"plan_item_schema_version":1,"item_id":it.get('item_id'),"dicom_path":it.get('path'),"dicom_status":dstatus,"analysis_readiness":rid,"is_ready_for_any_analysis":any_ready,"blocked_reasons":reasons})
    return validate_dicom_batch_analysis_plan({"dicom_batch_analysis_plan_schema_version":1,"plan_id":plan_id or f"plan_{uuid.uuid4().hex}","generated_at":generated_at or datetime.now(timezone.utc).isoformat(),"metadata":dict(metadata or {}),"manifest_id":m.get('manifest_id'),"roi_preset_name":p.get('name'),"analyses":a,"item_count":len(items),"ready_item_count":ready,"blocked_item_count":blocked,"items":items})

def validate_dicom_batch_analysis_plan(plan):
    x=dict(plan)
    if x.get('dicom_batch_analysis_plan_schema_version')!=1: raise ValueError('unsupported plan schema')
    if not isinstance(x.get('items'),list): raise ValueError('items must be list')
    for it in x['items']:
        if not isinstance(it,dict) or it.get('plan_item_schema_version')!=1: raise ValueError('malformed plan item')
    return x

def render_dicom_batch_analysis_plan_text(plan):
    p=validate_dicom_batch_analysis_plan(plan); lines=[f"Plan ID: {p['plan_id']}",f"Item Count: {p['item_count']}",f"Ready: {p['ready_item_count']}, Blocked: {p['blocked_item_count']}"]
    for i,it in enumerate(p['items']):
        r=[k for k,v in it['analysis_readiness'].items() if v.get('is_ready')]
        lines.append(f"- [{i}] {it['item_id']} | {it['dicom_status']} | any_ready={it['is_ready_for_any_analysis']} | ready={r} | blocked={it['blocked_reasons']}")
    return '\n'.join(lines)+'\n'

def export_dicom_batch_analysis_plan_to_json(plan,path=None):
    t=json.dumps(validate_dicom_batch_analysis_plan(plan),ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)
    if path is not None: Path(path).write_text(t,encoding='utf-8')
    return t

def export_dicom_batch_analysis_plan_to_csv(plan,path=None):
    p=validate_dicom_batch_analysis_plan(plan); f=["dicom_batch_analysis_plan_schema_version","plan_id","generated_at","item_index","item_id","dicom_path","dicom_status","is_ready_for_any_analysis","ready_analyses_json","blocked_reasons_json","analysis_readiness_json"]
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=f,lineterminator='\n'); w.writeheader()
    for i,it in enumerate(p['items']):
        ready=[k for k,v in it['analysis_readiness'].items() if v.get('is_ready')]
        w.writerow({"dicom_batch_analysis_plan_schema_version":1,"plan_id":p['plan_id'],"generated_at":p['generated_at'],"item_index":i,"item_id":it['item_id'],"dicom_path":it['dicom_path'],"dicom_status":it['dicom_status'],"is_ready_for_any_analysis":it['is_ready_for_any_analysis'],"ready_analyses_json":json.dumps(ready,ensure_ascii=False,sort_keys=True),"blocked_reasons_json":json.dumps(it['blocked_reasons'],ensure_ascii=False,sort_keys=True),"analysis_readiness_json":json.dumps(it['analysis_readiness'],ensure_ascii=False,sort_keys=True)})
    t=b.getvalue();
    if path is not None: Path(path).write_text(t,encoding='utf-8')
    return t

def load_dicom_batch_analysis_plan(path):
    try: x=json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as e: raise ValueError('failed to load plan') from e
    return validate_dicom_batch_analysis_plan(x)
