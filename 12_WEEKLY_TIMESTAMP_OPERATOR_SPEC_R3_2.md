# Weekly Authority Timestamp Operator R3.2 — CANDIDATE

## Operator
GitHub Actions workflow `github/workflows/m8-weekly-authority-timestamp.yml` is the default 1244+ external timestamp executor. GPT/ChatGPT runtime is not the executor.

## Cadence
Scheduled Saturday 09:00 UTC (=18:00 KST) plus `workflow_dispatch` fallback. GitHub scheduled jobs can be delayed, so an operational alert/fallback must occur before the sealed cutoff; schedule execution time itself is not evidence.

## Preconditions
- exactly one due canonical `ROUND_AUTHORITY_*.json` within the configured due window;
- authority's `prev_round_ledger_head_sha256` equals current ledger head;
- referenced release is approved;
- authority has not already been PREDRAW_REGISTERED;
- repository has approved pinned TSA configuration (`TSA_URL`, TSA signer certificate, CA chain, pinned certificate hashes/policy id).
- Path-A production routing endpoint for the existing FreeTSA service is `https://freetsa.org/tsr` (stored as the `M8_TSA_URL` secret). This URL is an operational routing value, **not** the trust root; acceptance is determined by the fixed Path-A policy SHA and pinned CA/TSA certificate bytes.

Missing trust config is fatal. R2 deliberately does not invent TSA values; the activated workflow must import the already-approved trust configuration or undergo trust-policy review.

## Actions
1. canonical-byte validation and SHA256;
2. RFC3161 TSQ generation;
3. send to pinned TSA;
4. cryptographic verification against pinned trust chain;
5. parse genTime and require genTime <= authority cutoff;
6. save `.tsq`, `.tsr`, verification JSON as evidence;
7. append exactly one `PREDRAW_REGISTERED` event with authority SHA, TSR SHA, trust-policy hash, genTime and prior ledger head;
8. commit/persist only append-only evidence + ledger event.

## Failure semantics
No receipt / invalid receipt / late genTime / duplicate registration / ledger-head mismatch => no confirmatory timestamp credit. If cutoff passes without qualifying registration, round becomes TRACK_ONLY or ADMIN_MISSED only under the active round rules; it must not create a permanent process blocker.


## R3 cutoff source of truth
The Authority record is not the source of truth for a later cutoff. `canonical_cutoff(round)` is computed in code from round 1243 = 2026-09-26 20:00 KST, +7 days per round. An Authority may choose an earlier cutoff. A later cutoff is valid only via a separately RFC3161-sealed schedule-exception record timestamped no later than the default cutoff and bound to an archived official postponement notice.

## R3 workflow gates before TSA request
1. Authority JSON schema validation.
2. Exactly one `PRODUCTION` artifact.
3. Referenced Release Registry event is currently APPROVED and whole19/METHOD_REPRO/selector anchor match.
4. Canonical schedule / exception validation.
5. Previous Round Ledger head binding.

## R3 failure semantics
- Authority exists but no qualifying timestamp by applicable cutoff => append `PREDRAW_REGISTERED` with `timestamp_status=TRACK_ONLY`, factor=1.
- No Authority file exists after applicable cutoff => `ADMIN_MISSED`, factor=1.
- An existing Authority can never be converted to ADMIN_MISSED.

## Durability
Upload TSQ/TSR/verification evidence as workflow artifact before git commit/push. A push conflict must not be auto-rebased across a changed ledger head; preserve receipt and revalidate/reissue before retry.

## R3.1 append verification
The ledger append command receives raw Authority/TSR/trust-policy/certificate paths, not precomputed operator-supplied evidence fields. It re-verifies the evidence before creating ON_TIME.

## R3.1 scoring handoff
Registration is necessary but not sufficient for confirmatory credit. The scoring gate independently re-verifies the same raw evidence plus the authenticated official outcome record. Schedule-exception mismatch yields factor=1/TRACK_ONLY scoring treatment with ISSUE_OPENED, without mutating the PREDRAW event.

## Repository controls
Under R3.3.2 Free-Anchor, the private repository itself is not protected and is not authoritative. Actual protection of the public control `main` branch and public hash-only `anchor` branch must be verified before first confirmatory scoring. The official workflow must execute from protected public control code, write private state with a narrowly scoped token, then publish a FreeTSA-sealed hash-only anchor. Push-failure recovery follows the superseding R3.3.2 rules in `21_GITHUB_BRANCH_PROTECTION_AND_PUSH_RECOVERY.md`.


## R3.2 Release-Registry trust anchor
- Before TSA request, resolve the Authority release in `release_registry.jsonl` and obtain `RELEASE_APPROVED.payload.tsa_trust_policy_sha256`.
- The checked-in trust-policy file SHA and runtime TSA certificates must match that approved value/material. A repository variable is not a substitute for this check.
- `m8_append_predraw_event.py` receives `--release-registry` and repeats this check before writing ON_TIME.
- `m8_score_eligibility.py` also receives `--release-registry`, verifies the same approved trust SHA against both raw trust material and the Round Ledger field, and rejects any self-authorized/non-approved TSA.

## R3.3.3 confirmatory scoring gate

Scoring receives the protected public `anchor_ledger.jsonl` via `--anchor-ledger`. After all pre-existing Release Registry, Path-A TSA, Authority, TSR, schedule, and outcome checks pass, the scorer independently verifies the exact round PREDRAW event against the public anchor. No anchor argument, no matching round anchor, or a late public anchor returns `TRACK_ONLY_PUBLIC_ANCHOR_REQUIRED` with factor=1. Broken anchor chains, mismatched Authority/TSR hashes, or a PREDRAW event not covered by the anchor tail fail closed as `PUBLIC_ANCHOR_INTEGRITY_FAILURE`.

The old private weekly workflow is removed and must not be deployed or manually re-enabled.
