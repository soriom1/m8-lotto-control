from __future__ import annotations
import json, hashlib, pathlib, sys

ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('private')
PREREG_SHA = 'ad5760eebebbede978d2a4aa14415fee6fb30fd2c44e106699dba9223c9b1db7'
CODE_SHA = '2f332acb4037ddeb5e6a8254b0db36ed9582522942eb4a6ea75997c47536eae8'
BASELINE_SHA = 'bfee66330de2645801c5fffbee885ec79a0d39980dc8d81d79f68a1bf3dd819b'
VALIDATION_SHA = '919c4a56d0ce5553460fc279de80021b80dfaf7b9ee02c93e2683a5fd8cd252e'
SELECTION_SHA = 'f9806dc1b44b4c71eecc222909a9017bf2fe77b251894861dae8a3427c911599'
PRE_HEAD = '893f8065eeb470c78232625415e91a5c9e2665b3cc6aa6a0427f6675896b53b3'
DIAG_HEAD = 'cf611a2e5c7c62376786b79fa176c8059e5d54699cb9d8bcb6bdfebaee2ccfd0'

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def canonical_hash(o):
    d = dict(o); d.pop('event_sha256', None)
    b = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(b).hexdigest()

assert sha(ROOT/'research/rq005/RQ005_FAMILY2_PREREG_FINAL_APPROVED.md') == PREREG_SHA
assert sha(ROOT/'research/rq005/rq005_longterm_quota.py') == CODE_SHA
assert sha(ROOT/'research/rq005/GTB_LEDGER_FULL_CHAIN_VALIDATION_20260928.json') == VALIDATION_SHA
assert sha(ROOT/'research/rq005/RQ005_FAMILY2_CANDIDATE_SELECTION_RECORD.md') == SELECTION_SHA
identity = json.loads((ROOT/'baseline/R4_DOC_RESEAL_20260927_APPROVED_IDENTITY.json').read_text(encoding='utf-8'))
assert identity['per_file_sha256']['select_v2.py'] == BASELINE_SHA
assert identity['whole19_sha256'] == 'fe5cf6ef00bc38d80adab7a42948d3572b49452b57deaca45b9244a9eb14f2d3'
assert identity['method_repro_sha256'] == '30502b98a6aec332ff3ccfbbd203467e9f25afd3fe61e2c5e0b3f014fedf4803'

ledger = ROOT/'research/testing_budget_ledger.jsonl'
lines = [x for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
rows = [json.loads(x) for x in lines]
for i, o in enumerate(rows):
    if i == 0:
        assert o['previous_event_sha256'] == 'GENESIS'
    else:
        assert o['previous_event_sha256'] == rows[i-1]['event_sha256'], (i, 'prev_link')

bad = []
for i, (line, o) in enumerate(zip(lines, rows)):
    recomputed = canonical_hash(o)
    if recomputed != o['event_sha256']:
        bad.append((i, o['event_sha256'], recomputed, hashlib.sha256(line.encode()).hexdigest()))
expected = {
    '8ff7fcd297e699892472eed63ad6dde36f9c1354b515e36c1860d6d9e91ee2b6',
    '6fdde6b0ad4f2f726ffb64d13af53dd011fc5098111dc86c963f9ccfce4c1255'}
assert {x[1] for x in bad} == expected, bad
corr = next(o for o in rows if o.get('event_type') == 'INTEGRITY_CORRECTION')
amap = {x['claimed_event_sha256']: x for x in corr['affected_events']}
for _, claimed, recomputed, raw in bad:
    assert amap[claimed]['recomputed_event_sha256'] == recomputed
    assert amap[claimed]['raw_line_sha256'] == raw

head = rows[-1]['event_sha256']
if head == DIAG_HEAD:
    print('GTB_CHAIN_PASS; RQ005_CARRYFORWARD_ALREADY_PRESENT')
    raise SystemExit(0)
assert head == PRE_HEAD, head

o = {
    'schema':'M8_GLOBAL_TESTING_BUDGET_LEDGER_EVENT_V1',
    'event_type':'DIAGNOSTIC',
    'epoch':'M8_GTB_EPOCH_20260927',
    'diagnostic_id':'PREEXISTING_11W_OUTCOME_EXPOSURE_BOUND_10',
    'status':'RETROSPECTIVE_BOUND_RECORDED_BEFORE_RQ005_SEAL',
    'previous_event_sha256':head,
    'hash_preimage_rule':'SHA256_UTF8_CANONICAL_JSON_SORT_KEYS_NO_SPACES_EXCLUDING_event_sha256',
    'advancement_allowed':'NO',
    'historical_confirmatory_credit':0,
    'm_diag':10,
    'm_diag_bound_type':'CLAUDE_PREAPPROVED_CONSERVATIVE_BOUND',
    'hypotheses_exposed':[
        'game-layer 11w+ 1~2 deviation approx 30.69%',
        '11w+ same-week pair co-placement WATCH',
        '11~13w Expansion cap=1 test',
        'exact-W bin chi-square test',
        'winners >=5 from 1~10w distribution check',
        'residual-bucket next-round rate 11~15w',
        'residual-bucket next-round rate 16~20w',
        'residual-bucket next-round rate 21~30w',
        'residual-bucket next-round rate 31~45w',
        'residual-bucket next-round rate 46+w'],
    'rq005_carryforward_rule':'Holm over 13 hypotheses: 3 RQ005 primary comparisons plus 10 carry-forward hypotheses each assigned p=1, at exact family alpha 1/120.',
    'family_index_consumed':False,
    'alpha_consumed':'0/1',
    'next_family_index':2,
    'next_family_alpha':'1/120',
    'recorded_at_kst':'2026-09-28T08:22:00+09:00'}
o['event_sha256'] = canonical_hash(o)
assert o['event_sha256'] == DIAG_HEAD
with ledger.open('a', encoding='utf-8') as f:
    f.write(json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
print('GTB_CHAIN_PASS; APPENDED_RQ005_CARRYFORWARD=' + o['event_sha256'])
