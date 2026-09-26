#!/usr/bin/env python3
import argparse, datetime as dt, hashlib, json
from pathlib import Path
from m8_schedule import canonical_cutoff

def can(o): return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--old',required=True); ap.add_argument('--new',required=True); ap.add_argument('--ledger',required=True); ap.add_argument('--now-utc',required=True); a=ap.parse_args()
    old=json.load(open(a.old,encoding='utf-8')); new=json.load(open(a.new,encoding='utf-8')); r=int(old['round'])
    if int(new['round'])!=r: raise SystemExit('REISSUE_ROUND_MISMATCH')
    oldsha=hashlib.sha256(can(old)).hexdigest()
    if new.get('supersedes_unsealed_authority_sha256')!=oldsha: raise SystemExit('REISSUE_SUPERSEDES_SHA_MISMATCH')
    now=dt.datetime.fromisoformat(a.now_utc.replace('Z','+00:00'))
    if now>=canonical_cutoff(r).astimezone(dt.timezone.utc): raise SystemExit('REISSUE_NOT_BEFORE_CANONICAL_CUTOFF')
    evs=[] if not Path(a.ledger).exists() else [json.loads(x) for x in Path(a.ledger).read_text(encoding='utf-8').splitlines() if x.strip()]
    if any(e.get('event_type')=='PREDRAW_REGISTERED' and int(e.get('payload',{}).get('round',-1))==r for e in evs): raise SystemExit('REISSUE_AFTER_PREDRAW_FORBIDDEN')
    for k in ('release','prediction_artifacts','scoring_policy_sha256'):
        if new.get(k)!=old.get(k): raise SystemExit('REISSUE_PREDICTIVE_OR_SCORING_CHANGE:'+k)
    print('REISSUE_VALID')
if __name__=='__main__': main()
