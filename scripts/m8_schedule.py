#!/usr/bin/env python3
import argparse, datetime as dt, hashlib, json, re, subprocess
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
BASE_ROUND = 1243
BASE_CUTOFF = dt.datetime(2026,9,26,20,0,0,tzinfo=KST)
BASE_DRAW = dt.datetime(2026,9,26,20,35,0,tzinfo=KST)

def parse_iso(s):
    x=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
    if x.tzinfo is None:
        raise ValueError('NAIVE_DATETIME')
    return x

def canonical_cutoff(round_no:int):
    r=int(round_no)
    if r < BASE_ROUND:
        raise ValueError('ROUND_BEFORE_1243')
    return BASE_CUTOFF + dt.timedelta(days=7*(r-BASE_ROUND))

def canonical_draw_time(round_no:int):
    r=int(round_no)
    if r < BASE_ROUND:
        raise ValueError('ROUND_BEFORE_1243')
    return BASE_DRAW + dt.timedelta(days=7*(r-BASE_ROUND))

def canonical_bytes(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _gentime(tsr):
    cp=subprocess.run(['openssl','ts','-reply','-in',str(tsr),'-text'],text=True,capture_output=True,check=True)
    m=re.search(r'Time stamp:\s*(.+)',cp.stdout)
    if not m: raise RuntimeError('GENTIME_NOT_FOUND')
    txt=m.group(1).strip(); fmts=['%b %d %H:%M:%S %Y GMT','%b %d %H:%M:%S.%f %Y GMT']
    for f in fmts:
        try: return dt.datetime.strptime(txt,f).replace(tzinfo=dt.timezone.utc)
        except ValueError: pass
    raise RuntimeError('GENTIME_PARSE_FAIL:'+txt)

def _verify_tsr_data(data_path,tsr_path,ca_file,signer_file):
    try:
        subprocess.run(['openssl','ts','-verify','-data',str(data_path),'-in',str(tsr_path),'-CAfile',str(ca_file),'-untrusted',str(signer_file)],check=True,capture_output=True,text=True)
    except subprocess.CalledProcessError as e:
        detail=(e.stderr or e.stdout or '').strip().replace('\n',' | ')[:500]
        raise RuntimeError('TSR_SIGNATURE_INVALID' + (':' + detail if detail else '')) from None

def resolve_schedule(authority_path, exception_dir='schedule_exceptions', ca_file=None, signer_file=None, trust_policy_sha=None, verify_exception_tsr=True):
    ap=Path(authority_path)
    raw=ap.read_bytes(); auth=json.loads(raw.decode('utf-8-sig'))
    r=int(auth['round'])
    declared_cutoff=parse_iso(auth['schedule']['cutoff_time_kst'])
    declared_draw=parse_iso(auth['schedule']['draw_time_kst'])
    default_cutoff=canonical_cutoff(r)
    default_draw=canonical_draw_time(r)
    exsha=auth['schedule'].get('schedule_exception_sha256')

    # Normal schedule: Authority may only make cutoff earlier, never later, and may not alter draw time.
    if declared_cutoff <= default_cutoff:
        if exsha:
            raise RuntimeError('SCHEDULE_EXCEPTION_NOT_ALLOWED_FOR_NONDELAYED_CUTOFF')
        if declared_draw != default_draw:
            raise RuntimeError('DRAW_TIME_MUST_EQUAL_CANONICAL_WITHOUT_EXCEPTION')
        if declared_cutoff >= declared_draw:
            raise RuntimeError('CUTOFF_NOT_BEFORE_DRAW')
        return {
            'round':r,
            'canonical_cutoff_kst':default_cutoff.isoformat(),
            'canonical_draw_time_kst':default_draw.isoformat(),
            'declared_cutoff_kst':declared_cutoff.isoformat(),
            'declared_draw_time_kst':declared_draw.isoformat(),
            'effective_cutoff_kst':declared_cutoff.isoformat(),
            'effective_draw_time_kst':declared_draw.isoformat(),
            'schedule_exception':None,
        }

    # Delayed cutoff requires a separately pre-default-cutoff RFC3161-sealed schedule exception.
    if not exsha:
        raise RuntimeError('DELAYED_CUTOFF_WITHOUT_SCHEDULE_EXCEPTION')
    ep=Path(exception_dir)/f'SCHEDULE_EXCEPTION_{r}.json'
    if not ep.exists(): raise RuntimeError('SCHEDULE_EXCEPTION_FILE_MISSING')
    eraw=ep.read_bytes(); eobj=json.loads(eraw.decode('utf-8-sig')); ecan=canonical_bytes(eobj)
    if eraw != ecan: raise RuntimeError('SCHEDULE_EXCEPTION_NONCANONICAL')
    if hashlib.sha256(ecan).hexdigest()!=exsha: raise RuntimeError('SCHEDULE_EXCEPTION_SHA_MISMATCH')
    if eobj.get('schema')!='M8_SCHEDULE_EXCEPTION_V1' or int(eobj.get('round',-1))!=r: raise RuntimeError('SCHEDULE_EXCEPTION_IDENTITY_MISMATCH')
    if parse_iso(eobj['default_cutoff_time_kst']) != default_cutoff: raise RuntimeError('SCHEDULE_EXCEPTION_DEFAULT_CUTOFF_MISMATCH')
    if parse_iso(eobj['default_draw_time_kst']) != default_draw: raise RuntimeError('SCHEDULE_EXCEPTION_DEFAULT_DRAW_MISMATCH')
    effective_cutoff=parse_iso(eobj['effective_cutoff_time_kst'])
    effective_draw=parse_iso(eobj['effective_draw_time_kst'])
    if effective_cutoff != declared_cutoff: raise RuntimeError('SCHEDULE_EXCEPTION_EFFECTIVE_CUTOFF_MISMATCH')
    if effective_draw != declared_draw: raise RuntimeError('SCHEDULE_EXCEPTION_EFFECTIVE_DRAW_MISMATCH')
    if effective_cutoff <= default_cutoff: raise RuntimeError('SCHEDULE_EXCEPTION_NOT_DELAYING_CUTOFF')
    if effective_draw <= default_draw: raise RuntimeError('SCHEDULE_EXCEPTION_NOT_DELAYING_DRAW')
    if effective_cutoff >= effective_draw: raise RuntimeError('DELAYED_CUTOFF_NOT_BEFORE_DELAYED_DRAW')

    notice=eobj.get('official_notice') or {}
    url=notice.get('source_url',''); npath=Path(exception_dir)/notice.get('artifact_path','')
    if not (url.startswith('https://') and notice.get('artifact_sha256')): raise RuntimeError('OFFICIAL_NOTICE_BINDING_MISSING')
    if not npath.exists() or sha256_file(npath)!=notice['artifact_sha256']: raise RuntimeError('OFFICIAL_NOTICE_ARTIFACT_MISMATCH')
    tev=eobj.get('timestamp_evidence') or {}
    tsr=Path(exception_dir)/tev.get('tsr_path','')
    if not tsr.exists(): raise RuntimeError('SCHEDULE_EXCEPTION_TSR_MISSING')
    if trust_policy_sha and tev.get('tsa_trust_policy_sha256')!=trust_policy_sha: raise RuntimeError('SCHEDULE_EXCEPTION_TRUST_POLICY_MISMATCH')
    if verify_exception_tsr:
        if not (ca_file and signer_file): raise RuntimeError('SCHEDULE_EXCEPTION_TRUST_FILES_REQUIRED')
        _verify_tsr_data(ep,tsr,ca_file,signer_file)
        gt=_gentime(tsr)
        if gt > default_cutoff.astimezone(dt.timezone.utc): raise RuntimeError('SCHEDULE_EXCEPTION_TIMESTAMP_AFTER_DEFAULT_CUTOFF')
    else:
        gt=None
    return {
        'round':r,
        'canonical_cutoff_kst':default_cutoff.isoformat(),
        'canonical_draw_time_kst':default_draw.isoformat(),
        'declared_cutoff_kst':declared_cutoff.isoformat(),
        'declared_draw_time_kst':declared_draw.isoformat(),
        'effective_cutoff_kst':effective_cutoff.isoformat(),
        'effective_draw_time_kst':effective_draw.isoformat(),
        'schedule_exception':{
            'path':str(ep),'sha256':exsha,'tsr_sha256':sha256_file(tsr),
            'gentime_utc':gt.isoformat() if gt else None,
            'official_notice_url':url,
        },
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--round',type=int)
    ap.add_argument('--authority')
    ap.add_argument('--exception-dir',default='schedule_exceptions')
    ap.add_argument('--ca-file')
    ap.add_argument('--signer-file')
    ap.add_argument('--trust-policy-sha')
    ap.add_argument('--no-verify-exception-tsr',action='store_true')
    ap.add_argument('--show-draw-time',action='store_true')
    a=ap.parse_args()
    if a.authority:
        print(json.dumps(resolve_schedule(a.authority,a.exception_dir,a.ca_file,a.signer_file,a.trust_policy_sha,not a.no_verify_exception_tsr),separators=(',',':')))
    elif a.round is not None:
        print((canonical_draw_time(a.round) if a.show_draw_time else canonical_cutoff(a.round)).isoformat())
    else:
        raise SystemExit('REQUIRE_ROUND_OR_AUTHORITY')
if __name__=='__main__': main()
