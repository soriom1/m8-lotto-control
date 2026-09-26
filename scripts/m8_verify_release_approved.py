#!/usr/bin/env python3
import argparse, json
from m8_release_registry import approved_release_payload

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--registry',required=True)
    ap.add_argument('--authority',required=True)
    ap.add_argument('--print-trust-sha',action='store_true')
    a=ap.parse_args()
    auth=json.load(open(a.authority,encoding='utf-8'))
    want=auth['release']
    p=approved_release_payload(a.registry,want['release_id'])
    for k in ('whole19','method_repro','selector_anchor'):
        if p.get(k)!=want.get(k): raise SystemExit(f'RELEASE_IDENTITY_MISMATCH:{k}')
    if a.print_trust_sha:
        print(p['tsa_trust_policy_sha256'])
    else:
        print('RELEASE_APPROVED_AND_MATCHED')
if __name__=='__main__': main()
