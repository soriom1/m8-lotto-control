#!/usr/bin/env python3
import argparse, datetime as dt, hashlib, json, subprocess
from pathlib import Path
from m8_schedule import canonical_cutoff, resolve_schedule, canonical_bytes

def can(o): return canonical_bytes(o)
def h(o): return hashlib.sha256(can(o)).hexdigest()
def events(path):
    p=Path(path); return [] if not p.exists() else [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def append(path,e):
    with open(path,'a',encoding='utf-8',newline='\n') as f: f.write(can(e).decode()+'\n')
def verify_chain(evs):
    prev='GENESIS'
    for i,e in enumerate(evs):
        if e.get('prev_event_sha256')!=prev: raise RuntimeError(f'BROKEN_CHAIN_AT_{i}')
        prev=h(e)
    return prev

def authority_ever_committed(repo_root, authority_path):
    root=Path(repo_root).resolve(); ap=Path(authority_path).resolve()
    try: rel=ap.relative_to(root)
    except ValueError: raise RuntimeError('AUTHORITY_NOT_UNDER_REPO_ROOT')
    cp=subprocess.run(['git','-C',str(root),'log','--all','--format=%H','--',str(rel)],text=True,capture_output=True)
    if cp.returncode!=0: raise RuntimeError('GIT_HISTORY_UNAVAILABLE')
    return bool(cp.stdout.strip())

def build_final_event(ledger, authority_dir, round_no, now_utc, exception_dir='schedule_exceptions', ca_file=None, signer_file=None, trust_policy_sha=None, repo_root='.'):
    now=now_utc.astimezone(dt.timezone.utc)
    ev=events(ledger); head=verify_chain(ev)
    same=[x for x in ev if int(x.get('payload',{}).get('round',-1))==round_no]
    if any(x.get('event_type') in ('PREDRAW_REGISTERED','ADMIN_MISSED') for x in same): raise RuntimeError('ROUND_STATUS_ALREADY_FINALIZED')
    auth=Path(authority_dir)/f'ROUND_AUTHORITY_{round_no}.json'
    if auth.exists():
        try:
            s=resolve_schedule(auth,exception_dir,ca_file,signer_file,trust_policy_sha,True)
            cutoff=dt.datetime.fromisoformat(s['effective_cutoff_kst']).astimezone(dt.timezone.utc); reason='NO_QUALIFYING_TIMESTAMP_BEFORE_CUTOFF'
        except Exception as ex:
            cutoff=canonical_cutoff(round_no).astimezone(dt.timezone.utc); reason='INVALID_OR_UNVERIFIED_SCHEDULE:'+type(ex).__name__
        if now<=cutoff: raise RuntimeError('CUTOFF_NOT_PASSED')
        raw=auth.read_bytes(); obj=json.loads(raw.decode('utf-8-sig'))
        if raw!=can(obj): raise RuntimeError('AUTHORITY_NONCANONICAL')
        sha=hashlib.sha256(raw).hexdigest()
        return {'schema':'M8_ROUND_LEDGER_EVENT_V1','event_type':'PREDRAW_REGISTERED','event_id':f'predraw-{round_no}-track-only-{sha[:16]}','created_at_utc':now.isoformat(),'prev_event_sha256':head,'payload':{'round':round_no,'authority_sha256':sha,'timestamp_status':'TRACK_ONLY','track_only_reason':reason,'confirmatory_factor':1}}
    cutoff=canonical_cutoff(round_no).astimezone(dt.timezone.utc)
    if now<=cutoff: raise RuntimeError('CUTOFF_NOT_PASSED')
    if authority_ever_committed(repo_root,auth): raise RuntimeError('AUTHORITY_DELETION_INTEGRITY_FAILURE')
    return {'schema':'M8_ROUND_LEDGER_EVENT_V1','event_type':'ADMIN_MISSED','event_id':f'admin-missed-{round_no}','created_at_utc':now.isoformat(),'prev_event_sha256':head,'payload':{'round':round_no,'confirmatory_factor':1,'reason':'NO_AUTHORITY_FILE_PRESENT_AND_NEVER_COMMITTED'}}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ledger',required=True); ap.add_argument('--authority-dir',default='authority'); ap.add_argument('--round',type=int,required=True)
    ap.add_argument('--exception-dir',default='schedule_exceptions'); ap.add_argument('--ca-file'); ap.add_argument('--signer-file'); ap.add_argument('--trust-policy-sha'); ap.add_argument('--repo-root',default='.')
    a=ap.parse_args()
    # Production CLI always uses the system clock. Synthetic clocks are available only by importing build_final_event in tests.
    now=dt.datetime.now(dt.timezone.utc)
    try: e=build_final_event(a.ledger,a.authority_dir,a.round,now,a.exception_dir,a.ca_file,a.signer_file,a.trust_policy_sha,a.repo_root)
    except Exception as ex: raise SystemExit(str(ex))
    append(a.ledger,e); print(h(e))
if __name__=='__main__': main()
