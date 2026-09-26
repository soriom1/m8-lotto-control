#!/usr/bin/env python3
import argparse, datetime as dt, re, subprocess, json
from m8_schedule import canonical_cutoff, resolve_schedule

def parse_gentime(tsr):
    cp=subprocess.run(['openssl','ts','-reply','-in',tsr,'-text'],text=True,capture_output=True,check=True)
    m=re.search(r'Time stamp:\s*(.+)',cp.stdout)
    if not m: raise SystemExit('GENTIME_NOT_FOUND')
    txt=m.group(1).strip(); fmts=['%b %d %H:%M:%S %Y GMT','%b %d %H:%M:%S.%f %Y GMT']
    for f in fmts:
        try: return dt.datetime.strptime(txt,f).replace(tzinfo=dt.timezone.utc)
        except ValueError: pass
    raise SystemExit('GENTIME_PARSE_FAIL:'+txt)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tsr',required=True); ap.add_argument('--round',type=int,required=True); ap.add_argument('--authority'); ap.add_argument('--purpose',choices=['authority','schedule-exception'],default='authority'); ap.add_argument('--exception-dir',default='schedule_exceptions'); ap.add_argument('--ca-file'); ap.add_argument('--signer-file'); ap.add_argument('--trust-policy-sha')
    a=ap.parse_args(); gt=parse_gentime(a.tsr)
    if a.purpose=='schedule-exception':
        cutoff=canonical_cutoff(a.round).astimezone(dt.timezone.utc)
    else:
        if not a.authority: raise SystemExit('AUTHORITY_REQUIRED')
        s=resolve_schedule(a.authority,a.exception_dir,a.ca_file,a.signer_file,a.trust_policy_sha,True)
        cutoff=dt.datetime.fromisoformat(s['effective_cutoff_kst']).astimezone(dt.timezone.utc)
    if gt>cutoff: raise SystemExit('GENTIME_AFTER_EFFECTIVE_CUTOFF')
    print(json.dumps({'round':a.round,'purpose':a.purpose,'gentime_utc':gt.isoformat(),'effective_cutoff_utc':cutoff.isoformat(),'on_time':True},separators=(',',':')))
if __name__=='__main__': main()
