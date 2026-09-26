#!/usr/bin/env python3
import argparse
from m8_trust_root import verify_runtime_material

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--policy',required=True); ap.add_argument('--tsa-url'); ap.add_argument('--ca-file',required=True); ap.add_argument('--signer-file',required=True); a=ap.parse_args()
    print(verify_runtime_material(a.policy,a.ca_file,a.signer_file,a.tsa_url))
if __name__=='__main__': main()
