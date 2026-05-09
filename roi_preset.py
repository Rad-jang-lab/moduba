from __future__ import annotations
import json, math
from pathlib import Path
from typing import Any

ROI_TYPES={"rectangle","ellipse","polygon","point","line"}
ROLES={"signal","noise","background","region_a","region_b","uniformity","mtf_edge"}
REQ={"snr":["signal","noise"],"cnr":["region_a","region_b"],"uniformity":["uniformity"],"mtf":["mtf_edge"]}

def _is_fin(v): return isinstance(v,(int,float)) and math.isfinite(float(v))

def build_empty_roi_preset(name="Untitled ROI preset", description=""):
    return {"roi_preset_schema_version":1,"name":str(name),"description":str(description),"metadata":{},"roi_definitions":[]}

def _validate_coords(rt,c):
    if not isinstance(c,dict): raise ValueError('coordinates must be dict')
    if rt in {"rectangle","ellipse"}:
        for k in ["x","y","width","height"]:
            if not _is_fin(c.get(k)): raise ValueError('invalid rect/ellipse coordinate')
    elif rt=="point":
        if not _is_fin(c.get('x')) or not _is_fin(c.get('y')): raise ValueError('invalid point coordinate')
    elif rt in {"polygon","line"}:
        pts=c.get('points')
        if not isinstance(pts,list): raise ValueError('points must be list')
        min_n=3 if rt=='polygon' else 2
        if len(pts)<min_n: raise ValueError('too few points')
        for p in pts:
            if not isinstance(p,dict) or not _is_fin(p.get('x')) or not _is_fin(p.get('y')): raise ValueError('invalid point')

def validate_roi_preset(preset):
    p=dict(preset)
    if p.get('roi_preset_schema_version')!=1: raise ValueError('unsupported schema')
    rois=p.get('roi_definitions')
    if not isinstance(rois,list): raise ValueError('roi_definitions must be list')
    ids=set(); out=[]
    for r in rois:
        if not isinstance(r,dict): raise ValueError('malformed roi')
        rid=str(r.get('roi_id','')).strip()
        if not rid or rid in ids: raise ValueError('invalid roi_id')
        ids.add(rid)
        rt=str(r.get('roi_type',''))
        if rt not in ROI_TYPES: raise ValueError('unsupported roi_type')
        roles=r.get('analysis_roles')
        if not isinstance(roles,list) or any((not isinstance(x,str) or x not in ROLES) for x in roles): raise ValueError('unsupported role')
        _validate_coords(rt,r.get('coordinates'))
        out.append({"roi_id":rid,"label":str(r.get('label','')),"roi_type":rt,"coordinates":json.loads(json.dumps(r.get('coordinates'))),"analysis_roles":[str(x) for x in roles],"notes":str(r.get('notes',''))})
    p['name']=str(p.get('name','Untitled ROI preset')); p['description']=str(p.get('description','')); p['metadata']=dict(p.get('metadata') or {}); p['roi_definitions']=out
    return p

def build_roi_preset_from_roi_definitions(roi_definitions,name="Untitled ROI preset",description="",metadata=None):
    return validate_roi_preset({"roi_preset_schema_version":1,"name":name,"description":description,"metadata":dict(metadata or {}),"roi_definitions":json.loads(json.dumps(list(roi_definitions or [])))})

def extract_roi_definitions_from_preset(preset):
    return json.loads(json.dumps(validate_roi_preset(preset).get('roi_definitions',[])))

def render_roi_preset_text(preset):
    p=validate_roi_preset(preset)
    lines=[f"ROI Preset: {p['name']}",f"Description: {p['description']}",f"ROI Count: {len(p['roi_definitions'])}"]
    for i,r in enumerate(p['roi_definitions']): lines.append(f"- [{i}] {r['roi_id']} | {r['roi_type']} | roles={r['analysis_roles']}")
    return "\n".join(lines)+"\n"

def export_roi_preset_to_json(preset,path=None):
    text=json.dumps(validate_roi_preset(preset),ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)
    if path is not None: Path(path).write_text(text,encoding='utf-8')
    return text

def load_roi_preset(path):
    try: p=json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as e: raise ValueError('failed to load roi preset') from e
    return validate_roi_preset(p)

def check_roi_preset_analysis_readiness(preset,analysis_type):
    p=validate_roi_preset(preset); a=str(analysis_type)
    if a not in REQ: raise ValueError('unsupported analysis_type')
    roles={role for r in p['roi_definitions'] for role in r['analysis_roles']}
    req=list(REQ[a]);
    if a=='cnr' and ('noise' in roles or 'background' in roles):
        miss=[x for x in ['region_a','region_b'] if x not in roles]
    else:
        miss=[x for x in req if x not in roles]
    if a=='cnr' and not ('noise' in roles or 'background' in roles): miss.append('noise|background')
    return {"analysis_type":a,"is_ready":len(miss)==0,"required_roles":req+["noise|background"] if a=='cnr' else req,"missing_roles":miss}
