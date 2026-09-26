#!/usr/bin/env python3
import argparse, datetime as dt, hashlib, json
from pathlib import Path
from m8_schedule import canonical_bytes

def can(o): return canonical_bytes(o)
def h(o): return hashlib.sha256(can(o)).hexdigest()
def read_events(path):
    p=Path(path); return [] if not p.exists() else [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def verify_chain(evs):
    prev='GENESIS'
    for i,e in enumerate(evs):
        if e.get('prev_event_sha256')!=prev: raise SystemExit(f'BROKEN_CHAIN_AT_{i}')
        prev=h(e)
    return prev

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--ledger',required=True); ap.add_argument('--outcome-record',required=True); ap.add_argument('--source-root',default='.')
    a=ap.parse_args(); p=Path(a.outcome_record); raw=p.read_bytes(); obj=json.loads(raw.decode('utf-8-sig'))
    if raw!=can(obj): raise SystemExit('OUTCOME_RECORD_NONCANONICAL')
    nums=obj.get('winning_numbers') or []
    if len(nums)!=6 or len(set(nums))!=6 or any(not isinstance(n,int) or n<1 or n>45 for n in nums): raise SystemExit('OUTCOME_NUMBERS_INVALID')
    if obj.get('bonus_number') in nums: raise SystemExit('BONUS_DUPLICATES_MAIN')
    src=obj.get('official_source') or {}; sp=Path(a.source_root)/src.get('artifact_path','')
    if not sp.exists(): raise SystemExit('OFFICIAL_SOURCE_ARTIFACT_MISSING')
    if hashlib.sha256(sp.read_bytes()).hexdigest()!=src.get('artifact_sha256'): raise SystemExit('OFFICIAL_SOURCE_ARTIFACT_SHA_MISMATCH')
    if not str(src.get('source_url','')).startswith('https://'): raise SystemExit('OFFICIAL_SOURCE_URL_REQUIRED')
    evs=read_events(a.ledger); head=verify_chain(evs); r=int(obj['round'])
    if any(e.get('event_type')=='OUTCOME_AUTHENTICATED' and int(e.get('payload',{}).get('round',-1))==r for e in evs): raise SystemExit('DUPLICATE_OUTCOME')
    rec_sha=hashlib.sha256(raw).hexdigest()
    e={'schema':'M8_ROUND_LEDGER_EVENT_V1','event_type':'OUTCOME_AUTHENTICATED','event_id':f'outcome-{r}-{rec_sha[:16]}','created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'prev_event_sha256':head,'payload':{'round':r,'outcome_record_sha256':rec_sha,'official_draw_time_kst':obj['official_draw_time_kst'],'official_source_artifact_sha256':src['artifact_sha256']}}
    with open(a.ledger,'a',encoding='utf-8',newline='\n') as f: f.write(can(e).decode()+'\n')
    print(h(e))
if __name__=='__main__': main()
