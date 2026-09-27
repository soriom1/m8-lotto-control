from __future__ import annotations
import json, hashlib, pathlib, os, re, datetime, shutil, sys

ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('private')
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path('rq005-seal-output')
DIAG_HEAD = 'cf611a2e5c7c62376786b79fa176c8059e5d54699cb9d8bcb6bdfebaee2ccfd0'
MASTER_SHA = '98700ac05e7e6052901454d12b49f1128fbe4d419ee3d4e6ba577d47ebca192b'
TSQ_SHA = 'b411b0f76811574b58e840ff4f1986fb1ae3739d3bcb2a332c16f26392cdf3bf'
PREREG_SHA = 'ad5760eebebbede978d2a4aa14415fee6fb30fd2c44e106699dba9223c9b1db7'
CODE_SHA = '2f332acb4037ddeb5e6a8254b0db36ed9582522942eb4a6ea75997c47536eae8'
BASELINE_SHA = 'bfee66330de2645801c5fffbee885ec79a0d39980dc8d81d79f68a1bf3dd819b'
VALIDATION_SHA = '919c4a56d0ce5553460fc279de80021b80dfaf7b9ee02c93e2683a5fd8cd252e'

def canonical_hash(o):
    d = dict(o); d.pop('event_sha256', None)
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

ledger = ROOT/'research/testing_budget_ledger.jsonl'
rows = [json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
if any(o.get('event_type') == 'FAMILY_PREREGISTRATION_SEAL' and o.get('family_index') == 2 for o in rows):
    raise SystemExit('Family2 seal already exists; refusing duplicate')
assert rows[-1]['event_sha256'] == DIAG_HEAD

tsr = OUT/'M8_RQ005_FAMILY2_PREREG_SEAL_MASTER_V1.tsr'
tsr_sha = hashlib.sha256(tsr.read_bytes()).hexdigest()
reply = pathlib.Path('/tmp/reply.txt').read_text(encoding='utf-8')
m = re.search(r'^Time stamp:\s*(.+?)\s*$', reply, re.M)
assert m, 'missing gentime'
dt = datetime.datetime.strptime(m.group(1), '%b %d %H:%M:%S %Y GMT').replace(tzinfo=datetime.timezone.utc)
gentime = dt.isoformat().replace('+00:00', 'Z')
digest = os.environ['ARTIFACT_DIGEST']
if digest.startswith('sha256:'):
    digest = digest.split(':', 1)[1]

o = {
    'schema':'M8_GLOBAL_TESTING_BUDGET_LEDGER_EVENT_V1',
    'event_type':'FAMILY_PREREGISTRATION_SEAL',
    'epoch':'M8_GTB_EPOCH_20260927',
    'sequence':2,
    'family_index':2,
    'research_id':'RQ005_CORE11W_QUOTA_FACTORIAL_V1_20260928',
    'status':'SEALED_EXECUTION_AUTHORIZED',
    'previous_event_sha256':DIAG_HEAD,
    'hash_preimage_rule':'SHA256_UTF8_CANONICAL_JSON_SORT_KEYS_NO_SPACES_EXCLUDING_event_sha256',
    'alpha_global':'1/20',
    'alpha_j':'1/120',
    'alpha_state':'SPENT_PVALUE',
    'allocated_alpha_total':'1/30',
    'remaining_alpha_bound':'1/60',
    'next_family_index':3,
    'next_family_alpha':'1/240',
    'primary_comparisons':3,
    'carryforward_hypotheses':10,
    'holm_hypotheses_total':13,
    'carryforward_assigned_p':'1',
    'raw_p_smallest_step_threshold':'1/1560',
    'prereg_sha256':PREREG_SHA,
    'research_code_sha256':CODE_SHA,
    'production_baseline_sha256':BASELINE_SHA,
    'gtb_full_chain_validation_sha256':VALIDATION_SHA,
    'seal_master_sha256':MASTER_SHA,
    'seal_tsq_sha256':TSQ_SHA,
    'seal_tsr_sha256':tsr_sha,
    'seal_gentime_utc':gentime,
    'seal_artifact_id':int(os.environ['ARTIFACT_ID']),
    'seal_artifact_digest_sha256':digest,
    'seal_workflow_run_id':int(os.environ['GITHUB_RUN_ID']),
    'claude_execution_after_seal':'YES',
    'historical_confirmatory_credit':0,
    'production_promotion':'NOT_GRANTED',
    'recorded_at_kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(microsecond=0).isoformat()}
o['event_sha256'] = canonical_hash(o)
with ledger.open('a', encoding='utf-8') as f:
    f.write(json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')

evdir = ROOT/'research/rq005/seal'
evdir.mkdir(parents=True, exist_ok=True)
shutil.copy2('helper/rq005-seal-input/M8_RQ005_FAMILY2_PREREG_SEAL_MASTER_V1.json', evdir/'M8_RQ005_FAMILY2_PREREG_SEAL_MASTER_V1.json')
shutil.copy2('/tmp/rq005.tsq', evdir/'M8_RQ005_FAMILY2_PREREG_SEAL_MASTER_V1.tsq')
shutil.copy2(tsr, evdir/'M8_RQ005_FAMILY2_PREREG_SEAL_MASTER_V1.tsr')
(evdir/'RQ005_FAMILY2_SEAL_LEDGER_EVENT.json').write_text(json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')

queue = ROOT/'research/research_queue_v1.jsonl'
qrows = [json.loads(x) for x in queue.read_text(encoding='utf-8').splitlines() if x.strip()]
matches = [i for i, x in enumerate(qrows) if x.get('queue_id') == 'RQ-005']
assert len(matches) == 1, matches
idx = matches[0]
assert qrows[idx].get('status') == 'PROPOSED_AWAITING_CLAUDE_AUDIT_NOT_SEALED_NOT_EXECUTED'
qrows[idx] = {
    'queue_id':'RQ-005','family':'CORE11W_QUOTA_FACTORIAL_V1','status':'SEALED_EXECUTION_AUTHORIZED',
    'gtb_epoch':'M8_GTB_EPOCH_20260927','family_index':2,'alpha':'1/120',
    'variants':['L00','L01','L02','L03'],'holm_hypotheses_total':13,'carryforward_hypotheses':10,
    'primary_window':'300-1242','execution':'AUTHORIZED_AFTER_EXTERNAL_SEAL',
    'seal_event_sha256':o['event_sha256'],'seal_master_sha256':MASTER_SHA,'seal_tsr_sha256':tsr_sha,
    'production_changed':False,'confirmatory_credit':0}
queue.write_text('\n'.join(json.dumps(x, ensure_ascii=False, separators=(',', ':')) for x in qrows) + '\n', encoding='utf-8')

state = {
    'schema':'M8_CURRENT_STATE_RQ005_SEALED_EXECUTION_AUTHORIZED_V1',
    'status':'AUTHORITATIVE_CURRENT_STATE',
    'production_predictive_semantics':'M7_UNIFIED10_V4_PARETO_ACTIVE',
    'method_repro':'30502b98a6aec332ff3ccfbbd203467e9f25afd3fe61e2c5e0b3f014fedf4803',
    'static19_whole19':'fe5cf6ef00bc38d80adab7a42948d3572b49452b57deaca45b9244a9eb14f2d3',
    'l0':'CLOSED','error_first_open_blockers':[],
    'gtb':{
        'policy_status':'ACTIVE','epoch':'M8_GTB_EPOCH_20260927','ledger_head_sha256':o['event_sha256'],
        'family_1_status':'RQ004_CLOSED_NO_ADVANCEMENT',
        'family_2':{
            'research_id':'RQ005_CORE11W_QUOTA_FACTORIAL_V1_20260928',
            'status':'SEALED_EXECUTION_AUTHORIZED','alpha_j':'1/120','holm_hypotheses_total':13,
            'carryforward_hypotheses':10,'seal_master_sha256':MASTER_SHA,'seal_tsr_sha256':tsr_sha,
            'seal_gentime_utc':gentime}},
    'historical_confirmatory_credit':0,'production_changed':False,
    'next_gate':'EXECUTE_RQ005_SEALED_943_ROUND_WF'}
state_dir = ROOT/'current_state'; state_dir.mkdir(exist_ok=True)
(state_dir/'M8_CURRENT_STATE_RQ005_SEALED_EXECUTION_AUTHORIZED_V1.json').write_text(
    json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
print('SEAL_EVENT_SHA256=' + o['event_sha256'])
print('TSR_SHA256=' + tsr_sha)
print('GENTIME=' + gentime)
