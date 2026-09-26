#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('path'); ap.add_argument('--check', action='store_true')
    a=ap.parse_args(); p=Path(a.path)
    raw=p.read_bytes(); obj=json.loads(raw.decode('utf-8-sig')); can=canonical_bytes(obj)
    if a.check and raw != can:
        raise SystemExit('NON_CANONICAL_JSON_BYTES')
    print(hashlib.sha256(can).hexdigest())
if __name__=='__main__': main()
