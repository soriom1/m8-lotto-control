#!/usr/bin/env python3
import argparse, datetime as dt, json
from pathlib import Path
from m8_schedule import parse_iso, canonical_cutoff

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dir',default='authority'); ap.add_argument('--now-utc',default=''); ap.add_argument('--window-hours',type=float,default=6.0)
    a=ap.parse_args(); now=parse_iso(a.now_utc) if a.now_utc else dt.datetime.now(dt.timezone.utc)
    due=[]
    for p in sorted(Path(a.dir).glob('ROUND_AUTHORITY_*.json')):
        d=json.loads(p.read_text(encoding='utf-8'))
        r=int(d['round']); declared=parse_iso(d['schedule']['cutoff_time_kst']); canonical=canonical_cutoff(r)
        exsha=d['schedule'].get('schedule_exception_sha256')
        if declared>canonical and not exsha:
            raise SystemExit(f'DELAYED_CUTOFF_WITHOUT_SCHEDULE_EXCEPTION:{p}')
        # Auto due-selection never moves later than the canonical schedule. A valid delayed
        # exception is handled by the identical manual workflow after cryptographic exception validation.
        due_cutoff=min(declared,canonical)
        delta=(due_cutoff.astimezone(dt.timezone.utc)-now).total_seconds()/3600
        if 0 <= delta <= a.window_hours: due.append((p,r,delta,canonical,declared))
    if len(due)!=1:
        raise SystemExit(f'DUE_AUTHORITY_COUNT_{len(due)}')
    p,r,h,canonical,declared=due[0]
    print(json.dumps({'path':str(p),'round':r,'hours_to_due_cutoff':h,'canonical_cutoff_kst':canonical.isoformat(),'declared_cutoff_kst':declared.isoformat()},separators=(',',':')))
if __name__=='__main__': main()
