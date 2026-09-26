#!/usr/bin/env python3
"""Self-contained strict subset validator for the JSON-Schema keywords used by M8 schemas."""
import argparse, json, re
from pathlib import Path

SUPPORTED={'$schema','format','$id','type','additionalProperties','required','properties','const','enum','pattern','minimum','minLength','minItems','maxItems','uniqueItems','items','contains','minContains','maxContains'}

def typename_ok(v,t):
    return {'object':isinstance(v,dict),'array':isinstance(v,list),'string':isinstance(v,str),'integer':isinstance(v,int) and not isinstance(v,bool),'number':isinstance(v,(int,float)) and not isinstance(v,bool),'boolean':isinstance(v,bool),'null':v is None}.get(t,False)

def validate(v,s,path='$'):
    unknown=set(s)-SUPPORTED
    if unknown: raise ValueError(f'UNSUPPORTED_SCHEMA_KEYWORDS:{path}:{sorted(unknown)}')
    t=s.get('type')
    if t:
        ts=t if isinstance(t,list) else [t]
        if not any(typename_ok(v,x) for x in ts): raise ValueError(f'TYPE:{path}:{ts}')
    if 'const' in s and v!=s['const']: raise ValueError(f'CONST:{path}')
    if 'enum' in s and v not in s['enum']: raise ValueError(f'ENUM:{path}')
    if isinstance(v,str):
        if s.get('format')=='date-time':
            import datetime as _dt
            try:
                x=_dt.datetime.fromisoformat(v.replace('Z','+00:00'))
                if x.tzinfo is None: raise ValueError
            except Exception: raise ValueError(f'FORMAT_DATE_TIME:{path}')
        if 'minLength' in s and len(v)<s['minLength']: raise ValueError(f'MIN_LENGTH:{path}')
        if 'pattern' in s and re.fullmatch(s['pattern'],v) is None: raise ValueError(f'PATTERN:{path}')
    if isinstance(v,int) and not isinstance(v,bool) and 'minimum' in s and v<s['minimum']: raise ValueError(f'MINIMUM:{path}')
    if isinstance(v,dict):
        for k in s.get('required',[]):
            if k not in v: raise ValueError(f'REQUIRED:{path}.{k}')
        props=s.get('properties',{})
        if s.get('additionalProperties') is False:
            extra=set(v)-set(props)
            if extra: raise ValueError(f'ADDITIONAL_PROPERTIES:{path}:{sorted(extra)}')
        for k,sub in props.items():
            if k in v: validate(v[k],sub,f'{path}.{k}')
    if isinstance(v,list):
        if 'minItems' in s and len(v)<s['minItems']: raise ValueError(f'MIN_ITEMS:{path}')
        if 'maxItems' in s and len(v)>s['maxItems']: raise ValueError(f'MAX_ITEMS:{path}')
        if s.get('uniqueItems'):
            seen=set()
            for x in v:
                key=json.dumps(x,sort_keys=True,separators=(',',':'))
                if key in seen: raise ValueError(f'UNIQUE_ITEMS:{path}')
                seen.add(key)
        if 'items' in s:
            for i,x in enumerate(v): validate(x,s['items'],f'{path}[{i}]')
        if 'contains' in s:
            n=0
            for x in v:
                try: validate(x,s['contains'],path+'[*]'); n+=1
                except ValueError: pass
            if n<s.get('minContains',1): raise ValueError(f'MIN_CONTAINS:{path}:{n}')
            if 'maxContains' in s and n>s['maxContains']: raise ValueError(f'MAX_CONTAINS:{path}:{n}')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--schema',required=True); ap.add_argument('--instance',required=True); a=ap.parse_args()
    s=json.load(open(a.schema,encoding='utf-8')); v=json.load(open(a.instance,encoding='utf-8')); validate(v,s); print('SCHEMA_VALID')
if __name__=='__main__': main()
