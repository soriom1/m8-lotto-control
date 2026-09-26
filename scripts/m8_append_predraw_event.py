#!/usr/bin/env python3
import argparse, datetime as dt, hashlib, json
from pathlib import Path
from m8_schedule import canonical_bytes, resolve_schedule, _verify_tsr_data, _gentime
from m8_release_registry import approved_release_payload
from m8_trust_root import verify_runtime_material, ROOT_TRUST_POLICY_SHA256

def can(o): return canonical_bytes(o)
def h(o): return hashlib.sha256(can(o)).hexdigest()
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_events(path):
    p=Path(path)
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def verify_chain(evs):
    prev='GENESIS'
    for i,e in enumerate(evs):
        if e.get('prev_event_sha256')!=prev: raise SystemExit(f'BROKEN_CHAIN_AT_{i}')
        prev=h(e)
    return prev

def verify_trust_material(policy_path, ca_file, signer_file):
    return verify_runtime_material(policy_path,ca_file,signer_file)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ledger',required=True)
    ap.add_argument('--release-registry',required=True)
    ap.add_argument('--authority',required=True)
    ap.add_argument('--tsr',required=True)
    ap.add_argument('--trust-policy-file',required=True)
    ap.add_argument('--ca-file',required=True)
    ap.add_argument('--signer-file',required=True)
    ap.add_argument('--exception-dir',default='schedule_exceptions')
    a=ap.parse_args()

    auth_path=Path(a.authority); raw=auth_path.read_bytes(); auth=json.loads(raw.decode('utf-8-sig'))
    if raw!=can(auth): raise SystemExit('AUTHORITY_NONCANONICAL')
    round_no=int(auth['round'])
    evs=read_events(a.ledger); head=verify_chain(evs)
    if auth.get('prev_round_ledger_head_sha256')!=head: raise SystemExit('LEDGER_HEAD_MISMATCH')
    round_events=[e for e in evs if int(e.get('payload',{}).get('round',-1))==round_no]
    if any(e.get('event_type')=='PREDRAW_REGISTERED' for e in round_events): raise SystemExit('DUPLICATE_PREDRAW')
    if any(e.get('event_type')=='ADMIN_MISSED' for e in round_events): raise SystemExit('ADMIN_MISSED_ALREADY_FINAL')

    approved=approved_release_payload(a.release_registry, auth['release']['release_id'])
    for k in ('whole19','method_repro','selector_anchor'):
        if approved.get(k)!=auth['release'].get(k): raise SystemExit(f'RELEASE_IDENTITY_MISMATCH:{k}')
    approved_trust_sha=approved['tsa_trust_policy_sha256']
    if approved_trust_sha!=ROOT_TRUST_POLICY_SHA256: raise SystemExit('NON_ROOT_TSA_TRUST_POLICY')
    trust_sha=verify_trust_material(a.trust_policy_file,a.ca_file,a.signer_file)
    if trust_sha!=approved_trust_sha: raise SystemExit('NON_APPROVED_TSA_TRUST_POLICY')
    sched=resolve_schedule(auth_path,a.exception_dir,a.ca_file,a.signer_file,approved_trust_sha,True)
    _verify_tsr_data(auth_path,a.tsr,a.ca_file,a.signer_file)
    gt=_gentime(a.tsr)
    cutoff=dt.datetime.fromisoformat(sched['effective_cutoff_kst']).astimezone(dt.timezone.utc)
    if gt>cutoff: raise SystemExit('GENTIME_AFTER_EFFECTIVE_CUTOFF')
    tsr_sha=sha_file(a.tsr); auth_sha=hashlib.sha256(raw).hexdigest()
    payload={
        'round':round_no,'authority_sha256':auth_sha,'timestamp_status':'ON_TIME',
        'tsr_sha256':tsr_sha,'tsa_trust_policy_sha256':trust_sha,'gentime_utc':gt.isoformat()
    }
    e={'schema':'M8_ROUND_LEDGER_EVENT_V1','event_type':'PREDRAW_REGISTERED','event_id':f'predraw-{round_no}-on-time-{auth_sha[:16]}','created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'prev_event_sha256':head,'payload':payload}
    with open(a.ledger,'a',encoding='utf-8',newline='\n') as f: f.write(can(e).decode()+'\n')
    print(h(e))
if __name__=='__main__': main()
