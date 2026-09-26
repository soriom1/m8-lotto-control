#!/usr/bin/env python3
import hashlib, json
from pathlib import Path

ROOT_TRUST_POLICY_SHA256 = "93b1ef5e10156e86e4d93d42f77f509cd271a2683a9ee52a78152a69304b6c6f"
LEGACY_SCHEMA = "M8_TIMESTAMP_TRUST_POLICY_V1"
CURRENT_SCHEMA = "M8_TSA_TRUST_POLICY_V1"

def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def assert_root_trust_sha(value):
    if value != ROOT_TRUST_POLICY_SHA256:
        raise RuntimeError("NON_ROOT_TSA_TRUST_POLICY")
    return value

def load_policy(path):
    raw=Path(path).read_bytes(); actual=hashlib.sha256(raw).hexdigest()
    assert_root_trust_sha(actual)
    d=json.loads(raw.decode("utf-8-sig"))
    schema=d.get("schema")
    if schema==LEGACY_SCHEMA:
        ca=d.get("freetsa_ca_sha256"); signer=d.get("freetsa_tsa_cert_sha256"); tsa_url_sha=None
    elif schema==CURRENT_SCHEMA:
        ca=d.get("ca_pem_sha256"); signer=d.get("signer_pem_sha256"); tsa_url_sha=d.get("tsa_url_sha256")
    else:
        raise RuntimeError("TRUST_POLICY_SCHEMA")
    for label,v in (("CA",ca),("SIGNER",signer)):
        if not isinstance(v,str) or len(v)!=64:
            raise RuntimeError("TRUST_POLICY_"+label+"_SHA_INVALID")
    return {"raw_sha256":actual,"schema":schema,"ca_sha256":ca,"signer_sha256":signer,"tsa_url_sha256":tsa_url_sha,"raw":d}

def verify_runtime_material(policy_path, ca_file, signer_file, tsa_url=None):
    p=load_policy(policy_path)
    if sha_file(ca_file)!=p["ca_sha256"]: raise RuntimeError("TRUST_POLICY_CA_MISMATCH")
    if sha_file(signer_file)!=p["signer_sha256"]: raise RuntimeError("TRUST_POLICY_SIGNER_MISMATCH")
    # Endpoint is operational routing, not the trust anchor for the legacy Path-A policy.
    if p["tsa_url_sha256"] is not None and tsa_url is not None:
        got=hashlib.sha256(tsa_url.encode()).hexdigest()
        if got!=p["tsa_url_sha256"]: raise RuntimeError("TRUST_POLICY_MISMATCH:tsa_url_sha256")
    return p["raw_sha256"]
