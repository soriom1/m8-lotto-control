from __future__ import annotations
import json, hashlib, pathlib, datetime, sys

ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('private')
SEAL_HEAD = '1f67ccf9255b0b36dc9a70d053c454cbd028692fb55bdbd7d500161e6fb99525'
SUMMARY_SHA = '040e7be7f8709086add72771992e2a114da61293f4d2f4cb503d1953993cf6f4'
RAW_SHA = '23afc689bac7ac51d155b181024d56311cbe51fccf7fc5ad90be407f11b1c36b'

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def canonical_hash(o):
    d=dict(o); d.pop('event_sha256',None)
    return hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

summary_path=ROOT/'research_results/RQ005_FINAL_RESULT_V1.json'
assert sha(summary_path)==SUMMARY_SHA, sha(summary_path)
s=json.loads(summary_path.read_text(encoding='utf-8'))
assert s['verdict']=='RQ005_CLOSED_NO_ADVANCEMENT'
assert s['raw_sha256']==RAW_SHA
assert s['passing_variants']==[]
assert s['rounds']==943 and s['rows']==3772
assert s['family_index']==2 and s['family_alpha']=='1/120'
assert s['holm_hypotheses_total']==13 and s['carryforward_hypotheses']==10
assert s['production_changed'] is False and s['historical_confirmatory_credit']==0

ledger=ROOT/'research/testing_budget_ledger.jsonl'
rows=[json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
assert rows[-1]['event_sha256']==SEAL_HEAD, rows[-1]['event_sha256']
assert rows[-1]['event_type']=='FAMILY_PREREGISTRATION_SEAL' and rows[-1]['family_index']==2
assert not any(o.get('event_type')=='FAMILY_RESULT' and o.get('family_index')==2 for o in rows)

event={
 'schema':'M8_GLOBAL_TESTING_BUDGET_LEDGER_EVENT_V1',
 'event_type':'FAMILY_RESULT',
 'epoch':'M8_GTB_EPOCH_20260927',
 'sequence':2,
 'family_index':2,
 'research_id':'RQ005_CORE11W_QUOTA_FACTORIAL_V1_20260928',
 'status':'CLOSED_NO_ADVANCEMENT',
 'family_verdict':'RQ005_CLOSED_NO_ADVANCEMENT',
 'previous_event_sha256':SEAL_HEAD,
 'hash_preimage_rule':'SHA256_UTF8_CANONICAL_JSON_SORT_KEYS_NO_SPACES_EXCLUDING_event_sha256',
 'alpha_j':'1/120','alpha_state':'SPENT_PVALUE',
 'allocated_alpha_total':'1/30','remaining_alpha_bound':'1/60',
 'next_family_index':3,'next_family_alpha':'1/240',
 'primary_comparisons':3,'carryforward_hypotheses':10,'holm_hypotheses_total':13,
 'rounds':943,'rows':3772,
 'raw_sha256':RAW_SHA,'result_summary_sha256':SUMMARY_SHA,
 'execution_engine':'HYBRID_EXACT_FRACTION_BRANCH_AND_BOUND_WITH_EXACT_DP_FALLBACK',
 'bb_regression_sha256':s['bb_regression_sha256'],'dp_regression_sha256':s['dp_regression_sha256'],
 'historical_confirmatory_credit':0,'production_changed':False,
 'variant_verdicts':{
   v:{'sum_diff':x['sum_diff'],'early_sum_diff':x['early_sum_diff'],'late_sum_diff':x['late_sum_diff'],'raw_p':x['raw_p_fraction'],'holm_p':x['holm_p_fraction'],'pass':x['pass']}
   for v,x in s['variants'].items()},
 'recorded_at_kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(microsecond=0).isoformat()
}
event['event_sha256']=canonical_hash(event)
with ledger.open('a',encoding='utf-8') as f:
    f.write(json.dumps(event,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')

queue=ROOT/'research/research_queue_v1.jsonl'
qrows=[json.loads(x) for x in queue.read_text(encoding='utf-8').splitlines() if x.strip()]
idx=[i for i,x in enumerate(qrows) if x.get('queue_id')=='RQ-005']
assert len(idx)==1
old=qrows[idx[0]]
assert old['status']=='SEALED_EXECUTION_AUTHORIZED', old['status']
qrows[idx[0]]={
 'queue_id':'RQ-005','family':'CORE11W_QUOTA_FACTORIAL_V1','status':'CLOSED_NO_ADVANCEMENT',
 'gtb_epoch':'M8_GTB_EPOCH_20260927','family_index':2,'alpha':'1/120',
 'variants':['L00','L01','L02','L03'],'holm_hypotheses_total':13,'carryforward_hypotheses':10,
 'primary_window':'300-1242','execution':'COMPLETED_943_ROUNDS_3772_ROWS',
 'verdict':'RQ005_CLOSED_NO_ADVANCEMENT',
 'variant_sum_diffs':{v:s['variants'][v]['sum_diff'] for v in ('L01','L02','L03')},
 'holm_adjusted_p':{v:s['variants'][v]['holm_p_fraction'] for v in ('L01','L02','L03')},
 'result_summary_sha256':SUMMARY_SHA,'raw_sha256':RAW_SHA,
 'seal_event_sha256':SEAL_HEAD,'result_event_sha256':event['event_sha256'],
 'production_changed':False,'confirmatory_credit':0}
queue.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in qrows)+'\n',encoding='utf-8')

state={
 'schema':'M8_CURRENT_STATE_RQ005_CLOSED_V1','status':'AUTHORITATIVE_CURRENT_STATE',
 'production_predictive_semantics':'M7_UNIFIED10_V4_PARETO_ACTIVE',
 'method_repro':'30502b98a6aec332ff3ccfbbd203467e9f25afd3fe61e2c5e0b3f014fedf4803',
 'static19_whole19':'fe5cf6ef00bc38d80adab7a42948d3572b49452b57deaca45b9244a9eb14f2d3',
 'l0':'CLOSED','error_first_open_blockers':[],
 'gtb':{
   'policy_status':'ACTIVE','epoch':'M8_GTB_EPOCH_20260927','ledger_head_sha256':event['event_sha256'],
   'family_1_status':'RQ004_CLOSED_NO_ADVANCEMENT',
   'family_2':{
     'research_id':'RQ005_CORE11W_QUOTA_FACTORIAL_V1_20260928','status':'CLOSED_NO_ADVANCEMENT','alpha_j':'1/120',
     'holm_hypotheses_total':13,'carryforward_hypotheses':10,'rounds':943,'rows':3772,
     'raw_sha256':RAW_SHA,'result_summary_sha256':SUMMARY_SHA,
     'variant_results':{v:{'sum_diff':s['variants'][v]['sum_diff'],'early':s['variants'][v]['early_sum_diff'],'late':s['variants'][v]['late_sum_diff'],'raw_p':s['variants'][v]['raw_p_fraction'],'holm_p':s['variants'][v]['holm_p_fraction'],'pass':False} for v in ('L01','L02','L03')},
     'verdict':'RQ005_CLOSED_NO_ADVANCEMENT'},
   'allocated_alpha_total':'1/30','remaining_alpha_bound':'1/60','next_family_index':3,'next_family_alpha':'1/240'},
 'historical_confirmatory_credit':0,'production_changed':False,
 'automation_policy':{'scheduled_predictive_research':'FORBIDDEN','scheduled_allowed_scope':'READ_ONLY_RESULT_WATCH_AND_INTEGRITY_WATCH'},
 'next_gate':'NO_ACTIVE_PREDICTIVE_CANDIDATE; ANY NEW FAMILY 3 RESEARCH REQUIRES USER EXPLICIT INSTRUCTION, NOVELTY CHECK, EXACT PREREGISTRATION, APPLICABLE_CLAUDE_AUDIT, AND EXTERNAL_SEAL'}
state_dir=ROOT/'current_state'; state_dir.mkdir(exist_ok=True)
(state_dir/'M8_CURRENT_STATE_RQ005_CLOSED_V1.json').write_text(json.dumps(state,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
print('RQ005_RESULT_EVENT_SHA256='+event['event_sha256'])
