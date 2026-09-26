#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
from m8_trust_root import assert_root_trust_sha

def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def event_hash(event):
    return hashlib.sha256(canonical_bytes(event)).hexdigest()

def read_events(path):
    p=Path(path)
    if not p.exists():
        raise RuntimeError('RELEASE_REGISTRY_MISSING')
    events=[json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
    prev='GENESIS'
    for i,e in enumerate(events):
        if e.get('prev_event_sha256') != prev:
            raise RuntimeError(f'BROKEN_RELEASE_CHAIN_AT_{i}')
        prev=event_hash(e)
    return events

def approved_release_payload(path, release_id):
    state=None
    for e in read_events(path):
        p=e.get('payload') or {}
        if p.get('release_id') != release_id:
            continue
        if e.get('event_type') == 'RELEASE_APPROVED':
            state=('APPROVED', p)
        elif e.get('event_type') == 'RELEASE_REVOKED':
            state=('REVOKED', p)
    if state is None or state[0] != 'APPROVED':
        raise RuntimeError('UNAPPROVED_RELEASE')
    p=state[1]
    trust=p.get('tsa_trust_policy_sha256')
    if not isinstance(trust,str) or len(trust)!=64 or any(c not in '0123456789abcdef' for c in trust):
        raise RuntimeError('APPROVED_RELEASE_MISSING_TSA_TRUST_POLICY_SHA256')
    assert_root_trust_sha(trust)
    return p
