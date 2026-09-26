#!/usr/bin/env python3
import argparse, datetime as dt, hashlib, json
from pathlib import Path
from m8_schedule import canonical_bytes

def can(o): return canonical_bytes(o)
def h(o): return hashlib.sha256(can(o)).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--ledger',required=True); ap.add_argument('--superseded-event-sha',required=True); ap.add_argument('--round',type=int,required=True); ap.add_argument('--reason',required=True); ap.add_argument('--correction-json',required=True); a=ap.parse_args()
    p=Path(a.ledger); evs=[] if not p.exists() else [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
    prev='GENESIS'; by_hash={}
    for i,e in enumerate(evs):
        if e.get('prev_event_sha256')!=prev: raise SystemExit(f'BROKEN_CHAIN_AT_{i}')
        prev=h(e); by_hash[prev]=e
    target=by_hash.get(a.superseded_event_sha)
    if target is None: raise SystemExit('SUPERSEDED_EVENT_HASH_NOT_FOUND')
    if target.get('event_type') not in ('OUTCOME_AUTHENTICATED','SCORE_APPENDED'): raise SystemExit('EVENT_TYPE_NOT_CORRECTABLE')
    if int(target.get('payload',{}).get('round',-1))!=a.round: raise SystemExit('CORRECTION_ROUND_MISMATCH')
    corr=json.load(open(a.correction_json,encoding='utf-8')); corr_sha=hashlib.sha256(can(corr)).hexdigest()
    e={'schema':'M8_ROUND_LEDGER_EVENT_V1','event_type':'CORRECTION_APPENDED','event_id':f'correction-{a.round}-{corr_sha[:16]}','created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'prev_event_sha256':prev,'payload':{'round':a.round,'superseded_event_sha256':a.superseded_event_sha,'superseded_event_type':target['event_type'],'correction_payload_sha256':corr_sha,'reason':a.reason,'correction':corr}}
    with open(p,'a',encoding='utf-8',newline='\n') as f: f.write(can(e).decode()+'\n')
    print(h(e))
if __name__=='__main__': main()
