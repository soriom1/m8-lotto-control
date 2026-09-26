#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, datetime as dt
from pathlib import Path
from m8_public_anchor import can, h, sha_file, latest_private_heads, private_head, tail_after

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--anchor-ledger',required=True); ap.add_argument('--private-registry',required=True); ap.add_argument('--private-ledger',required=True)
    ap.add_argument('--private-repo',required=True); ap.add_argument('--private-branch',required=True); ap.add_argument('--private-commit-sha',required=True)
    ap.add_argument('--event-type',required=True); ap.add_argument('--round',type=int); ap.add_argument('--authority'); ap.add_argument('--authority-tsr'); ap.add_argument('--out',required=True)
    a=ap.parse_args(); prev_reg,prev_led,prev_anchor,prev_seq=latest_private_heads(a.anchor_ledger)
    reg_head=private_head(a.private_registry,False); led_head=private_head(a.private_ledger,True)
    reg_tail=tail_after(a.private_registry,prev_reg,False); led_tail=tail_after(a.private_ledger,prev_led,True)
    if a.event_type!='ACTIVATION' and not (reg_tail or led_tail): raise SystemExit('NO_PRIVATE_STATE_ADVANCE_TO_ANCHOR')
    obj={'schema':'M8_PUBLIC_ANCHOR_RECORD_V1','sequence':prev_seq+1,'event_type':a.event_type,'round':a.round,
         'prev_anchor_event_sha256':prev_anchor,'private_repo':a.private_repo,'private_branch':a.private_branch,'private_commit_sha':a.private_commit_sha,
         'previous_release_registry_head_sha256':prev_reg,'previous_round_ledger_head_sha256':prev_led,
         'release_registry_head_sha256':reg_head,'round_ledger_head_sha256':led_head,'release_registry_tail':reg_tail,'round_ledger_tail':led_tail,
         'authority_sha256':sha_file(a.authority) if a.authority else None,'authority_tsr_sha256':sha_file(a.authority_tsr) if a.authority_tsr else None}
    Path(a.out).write_bytes(can(obj)+b'\n'); print(sha_file(a.out))
if __name__=='__main__': main()
