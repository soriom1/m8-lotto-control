#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def can(o): return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def h(o): return hashlib.sha256(can(o)).hexdigest()
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read_jsonl_events(path, missing_ok=False):
    p=Path(path)
    if not p.exists():
        if missing_ok: return []
        raise RuntimeError('JSONL_MISSING:'+str(path))
    out=[]
    for i,line in enumerate(p.read_text(encoding='utf-8').splitlines()):
        if not line.strip(): continue
        obj=json.loads(line)
        if line.encode('utf-8') != can(obj):
            raise RuntimeError(f'NONCANONICAL_JSONL_LINE:{path}:{i}')
        out.append(obj)
    return out

def chain_with_hashes(path, missing_ok=False):
    evs=read_jsonl_events(path,missing_ok); prev='GENESIS'; out=[]
    for i,e in enumerate(evs):
        if e.get('prev_event_sha256') != prev:
            raise RuntimeError(f'BROKEN_PRIVATE_CHAIN_AT:{path}:{i}')
        eh=h(e); out.append((e,eh)); prev=eh
    return out

def private_head(path, missing_ok=False):
    c=chain_with_hashes(path,missing_ok); return c[-1][1] if c else 'GENESIS'

def tail_after(path, previous_head, missing_ok=False):
    c=chain_with_hashes(path,missing_ok)
    if previous_head=='GENESIS': start=0
    else:
        hits=[i for i,(_,eh) in enumerate(c) if eh==previous_head]
        if len(hits)!=1: raise RuntimeError('PREVIOUS_PRIVATE_HEAD_NOT_FOUND:'+previous_head)
        start=hits[0]+1
    tail=[]
    for e,eh in c[start:]:
        payload=e.get('payload') or {}
        tail.append({'event_hash':eh,'prev_event_sha256':e.get('prev_event_sha256'),
                     'event_type':e.get('event_type','UNKNOWN'),'round':payload.get('round')})
    return tail

def read_anchor_events(path, missing_ok=True):
    p=Path(path)
    if not p.exists(): return [] if missing_ok else (_ for _ in ()).throw(RuntimeError('ANCHOR_LEDGER_MISSING'))
    evs=[]; prev='GENESIS'; seq=1
    for i,line in enumerate(p.read_text(encoding='utf-8').splitlines()):
        if not line.strip(): continue
        e=json.loads(line)
        if line.encode('utf-8') != can(e): raise RuntimeError(f'ANCHOR_NONCANONICAL_AT:{i}')
        if e.get('schema')!='M8_PUBLIC_ANCHOR_EVENT_V1': raise RuntimeError(f'ANCHOR_SCHEMA_AT:{i}')
        if e.get('sequence')!=seq: raise RuntimeError(f'ANCHOR_SEQUENCE_AT:{i}')
        if e.get('prev_anchor_event_sha256')!=prev: raise RuntimeError(f'ANCHOR_CHAIN_AT:{i}')
        if any(k in e for k in ('prediction','prediction_artifacts','numbers','pool18','core13','expansion5')):
            raise RuntimeError('PUBLIC_ANCHOR_PREDICTIVE_DATA_FORBIDDEN')
        prev=h(e); seq+=1; evs.append(e)
    return evs

def anchor_head(path):
    evs=read_anchor_events(path); return h(evs[-1]) if evs else 'GENESIS'

def latest_private_heads(anchor_path):
    evs=read_anchor_events(anchor_path)
    if not evs: return ('GENESIS','GENESIS','GENESIS',0)
    e=evs[-1]; return (e['release_registry_head_sha256'],e['round_ledger_head_sha256'],h(e),e['sequence'])

def validate_round_status_conflict(anchor_path, round_no, new_event_type):
    terminal={'PREDRAW_REGISTERED','ADMIN_MISSED'}
    if new_event_type not in terminal: return
    existing=[e['event_type'] for e in read_anchor_events(anchor_path) if e.get('round')==round_no and e['event_type'] in terminal]
    if existing and (new_event_type not in existing or len(existing)>=1):
        raise RuntimeError('PUBLIC_ANCHOR_ROUND_STATUS_CONFLICT')

def build_event(anchor_ledger, private_registry, private_ledger, private_repo, private_branch, private_commit_sha,
                event_type, round_no, anchor_record, anchor_tsr, anchor_gentime_utc, confirmatory_anchor_status,
                authority=None, authority_tsr=None):
    prev_reg,prev_led,prev_anchor,prev_seq=latest_private_heads(anchor_ledger)
    validate_round_status_conflict(anchor_ledger,round_no,event_type)
    reg_head=private_head(private_registry,False); led_head=private_head(private_ledger,True)
    reg_tail=tail_after(private_registry,prev_reg,False); led_tail=tail_after(private_ledger,prev_led,True)
    if event_type!='ACTIVATION' and not (reg_tail or led_tail): raise RuntimeError('NO_PRIVATE_STATE_ADVANCE_TO_ANCHOR')
    return {
      'schema':'M8_PUBLIC_ANCHOR_EVENT_V1','sequence':prev_seq+1,'event_type':event_type,'round':round_no,
      'prev_anchor_event_sha256':prev_anchor,'private_repo':private_repo,'private_branch':private_branch,
      'private_commit_sha':private_commit_sha,'release_registry_head_sha256':reg_head,'round_ledger_head_sha256':led_head,
      'round_ledger_tail':led_tail,'release_registry_tail':reg_tail,
      'authority_sha256':sha_file(authority) if authority else None,
      'authority_tsr_sha256':sha_file(authority_tsr) if authority_tsr else None,
      'anchor_record_sha256':sha_file(anchor_record),'anchor_tsr_sha256':sha_file(anchor_tsr),
      'anchor_gentime_utc':anchor_gentime_utc,'confirmatory_anchor_status':confirmatory_anchor_status,
    }

def verify_private_matches_latest(anchor_ledger, private_registry, private_ledger):
    evs=read_anchor_events(anchor_ledger)
    if not evs: raise RuntimeError('PUBLIC_ANCHOR_NOT_ACTIVATED')
    e=evs[-1]
    reg=private_head(private_registry,False); led=private_head(private_ledger,True)
    if reg!=e['release_registry_head_sha256']: raise RuntimeError('PRIVATE_RELEASE_HEAD_NOT_PUBLICLY_ANCHORED')
    if led!=e['round_ledger_head_sha256']: raise RuntimeError('PRIVATE_LEDGER_HEAD_NOT_PUBLICLY_ANCHORED')
    return {'anchor_sequence':e['sequence'],'anchor_event_sha256':h(e),'release_registry_head_sha256':reg,'round_ledger_head_sha256':led}


def verify_round_predraw_public_anchor(anchor_ledger, private_ledger, round_no, expected_authority_sha256=None, expected_authority_tsr_sha256=None):
    """Verify that the exact private PREDRAW event for round_no was covered by an ON_TIME public anchor.

    Missing/late anchors return confirmatory=False (TRACK_ONLY at scoring).
    Malformed chains, duplicate status, or mismatched bound hashes raise RuntimeError.
    """
    private_chain=chain_with_hashes(private_ledger,False)
    preds=[(e,eh) for e,eh in private_chain if e.get('event_type')=='PREDRAW_REGISTERED' and int((e.get('payload') or {}).get('round',-1))==int(round_no)]
    if len(preds)!=1:
        raise RuntimeError('PRIVATE_PREDRAW_COUNT_INVALID')
    pred,pred_hash=preds[0]
    pp=pred.get('payload') or {}
    if expected_authority_sha256 is not None and pp.get('authority_sha256')!=expected_authority_sha256:
        raise RuntimeError('PRIVATE_PREDRAW_AUTHORITY_SHA_MISMATCH')
    if expected_authority_tsr_sha256 is not None and pp.get('tsr_sha256')!=expected_authority_tsr_sha256:
        raise RuntimeError('PRIVATE_PREDRAW_TSR_SHA_MISMATCH')

    ap=Path(anchor_ledger)
    if not ap.exists():
        return {'confirmatory':False,'reason':'PUBLIC_ANCHOR_LEDGER_MISSING','predraw_event_sha256':pred_hash}
    anchors=read_anchor_events(ap,False)
    matches=[(i,e) for i,e in enumerate(anchors) if e.get('event_type')=='PREDRAW_REGISTERED' and e.get('round')==int(round_no)]
    if not matches:
        return {'confirmatory':False,'reason':'PUBLIC_PREDRAW_ANCHOR_MISSING','predraw_event_sha256':pred_hash}
    if len(matches)!=1:
        raise RuntimeError('PUBLIC_PREDRAW_ANCHOR_DUPLICATE')
    idx,e=matches[0]

    # The hash-only tail must itself prove an append-only extension from the prior public anchor.
    prior_head='GENESIS' if idx==0 else anchors[idx-1]['round_ledger_head_sha256']
    tail=e.get('round_ledger_tail') or []
    cursor=prior_head
    tail_hashes=[]
    for j,item in enumerate(tail):
        if item.get('prev_event_sha256')!=cursor:
            raise RuntimeError(f'PUBLIC_ANCHOR_ROUND_TAIL_CHAIN_AT:{idx}:{j}')
        eh=item.get('event_hash')
        if not isinstance(eh,str) or len(eh)!=64:
            raise RuntimeError(f'PUBLIC_ANCHOR_ROUND_TAIL_HASH_AT:{idx}:{j}')
        cursor=eh; tail_hashes.append(eh)
    if cursor!=e.get('round_ledger_head_sha256'):
        raise RuntimeError('PUBLIC_ANCHOR_ROUND_TAIL_HEAD_MISMATCH')

    if pred_hash not in tail_hashes and e.get('round_ledger_head_sha256')!=pred_hash:
        raise RuntimeError('PRIVATE_PREDRAW_EVENT_NOT_COVERED_BY_PUBLIC_ANCHOR')
    if expected_authority_sha256 is not None and e.get('authority_sha256')!=expected_authority_sha256:
        raise RuntimeError('PUBLIC_ANCHOR_AUTHORITY_SHA_MISMATCH')
    if expected_authority_tsr_sha256 is not None and e.get('authority_tsr_sha256')!=expected_authority_tsr_sha256:
        raise RuntimeError('PUBLIC_ANCHOR_AUTHORITY_TSR_SHA_MISMATCH')

    status=e.get('confirmatory_anchor_status')
    if status!='ON_TIME_PUBLIC_ANCHOR':
        return {'confirmatory':False,'reason':'PUBLIC_PREDRAW_ANCHOR_NOT_ON_TIME','confirmatory_anchor_status':status,'predraw_event_sha256':pred_hash,'anchor_event_sha256':h(e),'anchor_sequence':e.get('sequence')}
    return {'confirmatory':True,'reason':'ON_TIME_PUBLIC_ANCHOR','confirmatory_anchor_status':status,'predraw_event_sha256':pred_hash,'anchor_event_sha256':h(e),'anchor_sequence':e.get('sequence')}

def append_event(path,event):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    read_anchor_events(p,True)
    with p.open('ab') as f: f.write(can(event)+b'\n')
    read_anchor_events(p,False)
    return h(event)

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    v=sub.add_parser('verify-private'); v.add_argument('--anchor-ledger',required=True); v.add_argument('--private-registry',required=True); v.add_argument('--private-ledger',required=True)
    a=sub.add_parser('append');
    for x in ('anchor-ledger','private-registry','private-ledger','private-repo','private-branch','private-commit-sha','event-type','anchor-record','anchor-tsr','anchor-gentime-utc','confirmatory-anchor-status'): a.add_argument('--'+x,required=True)
    a.add_argument('--round',type=int); a.add_argument('--authority'); a.add_argument('--authority-tsr')
    ns=ap.parse_args()
    if ns.cmd=='verify-private': print(json.dumps(verify_private_matches_latest(ns.anchor_ledger,ns.private_registry,ns.private_ledger),sort_keys=True)); return
    e=build_event(ns.anchor_ledger,ns.private_registry,ns.private_ledger,ns.private_repo,ns.private_branch,ns.private_commit_sha,ns.event_type,ns.round,ns.anchor_record,ns.anchor_tsr,ns.anchor_gentime_utc,ns.confirmatory_anchor_status,ns.authority,ns.authority_tsr)
    print(append_event(ns.anchor_ledger,e))
if __name__=='__main__': main()
