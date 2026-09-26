#!/usr/bin/env python3
import argparse, subprocess
from pathlib import Path

def run(args,cwd):
    cp=subprocess.run(args,cwd=cwd,text=True,capture_output=True)
    if cp.returncode: raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    return cp.stdout

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--branch',default='anchor'); ap.add_argument('--path',default='anchor_ledger.jsonl'); a=ap.parse_args()
    commits=[x for x in run(['git','rev-list','--reverse',a.branch,'--',a.path],a.repo).splitlines() if x]
    prev=b''
    for c in commits:
        cp=subprocess.run(['git','show',f'{c}:{a.path}'],cwd=a.repo,capture_output=True)
        if cp.returncode: raise SystemExit('ANCHOR_HISTORY_FILE_MISSING:'+c)
        cur=cp.stdout
        if not cur.startswith(prev): raise SystemExit('ANCHOR_HISTORY_NOT_APPEND_ONLY:'+c)
        prev=cur
    print('PASS_PUBLIC_ANCHOR_GIT_HISTORY_APPEND_ONLY')
if __name__=='__main__': main()
