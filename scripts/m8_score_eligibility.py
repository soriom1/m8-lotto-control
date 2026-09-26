#!/usr/bin/env python3
import argparse, datetime as dt, hashlib, json
from pathlib import Path
from m8_schedule import canonical_bytes, resolve_schedule, _verify_tsr_data, _gentime, canonical_draw_time
from m8_release_registry import approved_release_payload
from m8_trust_root import verify_runtime_material, ROOT_TRUST_POLICY_SHA256
from m8_public_anchor import verify_round_predraw_public_anchor

def can(o): return canonical_bytes(o)
def h(o): return hashlib.sha256(can(o)).hexdigest()
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_events(path):
    p=Path(path); return [] if not p.exists() else [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def verify_chain(evs):
    prev='GENESIS'
    for i,e in enumerate(evs):
        if e.get('prev_event_sha256')!=prev: raise SystemExit(f'BROKEN_CHAIN_AT_{i}')
        prev=h(e)
    return prev

def append_issue_once(ledger, evs, round_no, issue_code, details):
    if any(e.get('event_type')=='ISSUE_OPENED' and int(e.get('payload',{}).get('round',-1))==round_no and e.get('payload',{}).get('issue_code')==issue_code for e in evs):
        return
    head=verify_chain(evs)
    e={'schema':'M8_ROUND_LEDGER_EVENT_V1','event_type':'ISSUE_OPENED','event_id':f'issue-{round_no}-{issue_code.lower()}',
       'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'prev_event_sha256':head,
       'payload':{'round':round_no,'issue_code':issue_code,'severity':'P1_SCORING_INTEGRITY','details':details}}
    with open(ledger,'a',encoding='utf-8',newline='\n') as f: f.write(can(e).decode()+'\n')

def verify_trust(policy_path, ca_file, signer_file, expected_sha):
    if expected_sha!=ROOT_TRUST_POLICY_SHA256: raise SystemExit('NON_ROOT_TSA_TRUST_POLICY')
    try:
        actual=verify_runtime_material(policy_path,ca_file,signer_file)
    except RuntimeError as e:
        raise SystemExit(str(e))
    if actual!=expected_sha: raise SystemExit('TRUST_POLICY_SHA_MISMATCH')
    return actual

def load_outcome_record(path, source_root):
    p=Path(path); raw=p.read_bytes(); o=json.loads(raw.decode('utf-8-sig'))
    if raw!=can(o): raise SystemExit('OUTCOME_RECORD_NONCANONICAL')
    src=o.get('official_source') or {}; sp=Path(source_root)/src.get('artifact_path','')
    if not sp.exists() or sha_file(sp)!=src.get('artifact_sha256'): raise SystemExit('OUTCOME_SOURCE_ARTIFACT_MISMATCH')
    return o, hashlib.sha256(raw).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ledger',required=True); ap.add_argument('--round',type=int,required=True)
    ap.add_argument('--anchor-ledger',help='Protected public anchor_ledger.jsonl; absent/missing anchor forces TRACK_ONLY')
    ap.add_argument('--release-registry',required=True)
    ap.add_argument('--authority-dir',default='authority'); ap.add_argument('--evidence-dir',default='evidence')
    ap.add_argument('--exception-dir',default='schedule_exceptions'); ap.add_argument('--trust-policy-file',required=True)
    ap.add_argument('--ca-file',required=True); ap.add_argument('--signer-file',required=True)
    ap.add_argument('--outcome-record',required=True); ap.add_argument('--outcome-source-root',default='.')
    a=ap.parse_args(); evs=read_events(a.ledger); verify_chain(evs)
    same=[e for e in evs if int(e.get('payload',{}).get('round',-1))==a.round]
    pred=[e for e in same if e.get('event_type')=='PREDRAW_REGISTERED']; missed=[e for e in same if e.get('event_type')=='ADMIN_MISSED']
    if pred and missed: raise SystemExit('INTEGRITY_FAILURE_ADMIN_MISSED_AND_PREDRAW_CONFLICT')
    if len(pred)>1 or len(missed)>1: raise SystemExit('INTEGRITY_FAILURE_DUPLICATE_ROUND_STATUS')
    outcome_events=[e for e in same if e.get('event_type')=='OUTCOME_AUTHENTICATED']
    if len(outcome_events)!=1: raise SystemExit('EXACTLY_ONE_AUTHENTICATED_OUTCOME_REQUIRED')
    outcome, outcome_sha=load_outcome_record(a.outcome_record,a.outcome_source_root)
    if int(outcome.get('round',-1))!=a.round: raise SystemExit('OUTCOME_ROUND_MISMATCH')
    if outcome_events[0].get('payload',{}).get('outcome_record_sha256')!=outcome_sha: raise SystemExit('OUTCOME_LEDGER_SHA_MISMATCH')

    if missed:
        print(json.dumps({'round':a.round,'confirmatory_factor':1,'eligibility':'ADMIN_MISSED_FACTOR_ONE'},separators=(',',':'))); return
    if not pred: raise SystemExit('ROUND_STATUS_MISSING')
    p=pred[0]; pp=p.get('payload',{})
    if pp.get('timestamp_status')=='TRACK_ONLY':
        print(json.dumps({'round':a.round,'confirmatory_factor':1,'eligibility':'TRACK_ONLY_FACTOR_ONE'},separators=(',',':'))); return
    if pp.get('timestamp_status')!='ON_TIME': raise SystemExit('UNKNOWN_TIMESTAMP_STATUS')

    auth=Path(a.authority_dir)/f'ROUND_AUTHORITY_{a.round}.json'
    if not auth.exists(): raise SystemExit('AUTHORITY_EVIDENCE_MISSING')
    raw=auth.read_bytes(); obj=json.loads(raw.decode('utf-8-sig'))
    if raw!=can(obj): raise SystemExit('AUTHORITY_NONCANONICAL')
    if hashlib.sha256(raw).hexdigest()!=pp.get('authority_sha256'): raise SystemExit('AUTHORITY_SHA_MISMATCH')
    approved=approved_release_payload(a.release_registry, obj['release']['release_id'])
    for k in ('whole19','method_repro','selector_anchor'):
        if approved.get(k)!=obj['release'].get(k): raise SystemExit(f'RELEASE_IDENTITY_MISMATCH:{k}')
    approved_trust_sha=approved['tsa_trust_policy_sha256']
    if approved_trust_sha!=ROOT_TRUST_POLICY_SHA256: raise SystemExit('NON_ROOT_TSA_TRUST_POLICY')
    if pp.get('tsa_trust_policy_sha256')!=approved_trust_sha: raise SystemExit('LEDGER_TSA_TRUST_POLICY_NOT_APPROVED')
    trust_sha=verify_trust(a.trust_policy_file,a.ca_file,a.signer_file,approved_trust_sha)
    tsr=Path(a.evidence_dir)/f'round_{a.round}'/'authority.tsr'
    if not tsr.exists() or sha_file(tsr)!=pp.get('tsr_sha256'): raise SystemExit('TSR_SHA_MISMATCH')
    sched=resolve_schedule(auth,a.exception_dir,a.ca_file,a.signer_file,trust_sha,True)
    _verify_tsr_data(auth,tsr,a.ca_file,a.signer_file)
    gt=_gentime(tsr)
    if gt.isoformat()!=pp.get('gentime_utc'): raise SystemExit('LEDGER_GENTIME_MISMATCH')
    cutoff=dt.datetime.fromisoformat(sched['effective_cutoff_kst']).astimezone(dt.timezone.utc)
    if gt>cutoff: raise SystemExit('TSR_AFTER_EFFECTIVE_CUTOFF')

    official_draw=dt.datetime.fromisoformat(str(outcome['official_draw_time_kst']).replace('Z','+00:00'))
    effective_draw=dt.datetime.fromisoformat(sched['effective_draw_time_kst'])
    if sched['schedule_exception'] is not None and official_draw != effective_draw:
        append_issue_once(a.ledger,evs,a.round,'SCHEDULE_EXCEPTION_NOT_CONFIRMED_BY_AUTHENTICATED_OUTCOME',{
            'effective_draw_time_kst':sched['effective_draw_time_kst'],
            'authenticated_official_draw_time_kst':outcome['official_draw_time_kst'],
            'action':'TRACK_ONLY_FACTOR_ONE'
        })
        print(json.dumps({'round':a.round,'confirmatory_factor':1,'eligibility':'TRACK_ONLY_SCHEDULE_EXCEPTION_NOT_CONFIRMED','issue_opened':True},separators=(',',':'))); return
    if official_draw <= dt.datetime.fromisoformat(sched['effective_cutoff_kst']): raise SystemExit('OFFICIAL_DRAW_NOT_AFTER_EFFECTIVE_CUTOFF')
    if sched['schedule_exception'] is None and official_draw != canonical_draw_time(a.round): raise SystemExit('OFFICIAL_DRAW_NOT_CANONICAL_WITHOUT_EXCEPTION')

    # R3.3.3: private ON_TIME evidence is necessary but never sufficient for confirmatory scoring.
    if not a.anchor_ledger:
        print(json.dumps({'round':a.round,'confirmatory_factor':1,'eligibility':'TRACK_ONLY_PUBLIC_ANCHOR_REQUIRED','anchor_reason':'ANCHOR_LEDGER_ARGUMENT_MISSING'},separators=(',',':'))); return
    try:
        anchor_check=verify_round_predraw_public_anchor(a.anchor_ledger,a.ledger,a.round,pp['authority_sha256'],pp['tsr_sha256'])
    except RuntimeError as e:
        raise SystemExit('PUBLIC_ANCHOR_INTEGRITY_FAILURE:'+str(e))
    if not anchor_check.get('confirmatory'):
        print(json.dumps({'round':a.round,'confirmatory_factor':1,'eligibility':'TRACK_ONLY_PUBLIC_ANCHOR_REQUIRED','anchor_reason':anchor_check.get('reason'),'confirmatory_anchor_status':anchor_check.get('confirmatory_anchor_status')},separators=(',',':'))); return

    print(json.dumps({'round':a.round,'confirmatory_factor_source':'SCORING_POLICY','eligibility':'ON_TIME_EVIDENCE_REVERIFIED','confirmatory_anchor_status':'ON_TIME_PUBLIC_ANCHOR','public_anchor_event_sha256':anchor_check['anchor_event_sha256'],'authority_sha256':pp['authority_sha256'],'tsr_sha256':pp['tsr_sha256'],'official_draw_time_kst':outcome['official_draw_time_kst']},separators=(',',':')))
if __name__=='__main__': main()
