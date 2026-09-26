#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

def can(o): return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('ledger'); a=ap.parse_args(); p=Path(a.ledger)
    if not p.exists() or not p.read_text(encoding='utf-8').strip(): print('GENESIS'); return
    evs=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
    prev='GENESIS'
    for i,e in enumerate(evs):
        if e.get('prev_event_sha256')!=prev: raise SystemExit(f'BROKEN_CHAIN_AT_{i}')
        prev=hashlib.sha256(can(e)).hexdigest()
    print(prev)
if __name__=='__main__': main()
