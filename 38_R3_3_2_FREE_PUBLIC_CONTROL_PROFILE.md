# R3.3.2 Free Public-Control / Private-Data Integrity Profile

Status: **CANDIDATE / NOT ACTIVE / CLAUDE REVIEW REQUIRED**

## Why this exists

GitHub Free does not provide protected branches for a private repository. The previous R3.3.1 activation path treated live repository branch protection as an external activation requirement. Paying for GitHub Pro is not required for M8. Instead, R3.3.2 moves the **trusted execution/control plane** to a separate public repository while leaving all sensitive state/data in the existing private repository.

## Repositories

### Private data repository

`private = soriom1/m8-lotto`

Contains private project state, authority files, evidence, Round Ledger, Release Registry, and any prediction artifacts. It is **not a trust root** under this profile. No workflow sourced from the private repository may create confirmatory authority merely by reporting PASS.

### Public control repository

Proposed: `soriom1/m8-lotto-control`

Contains only:
- governance scripts and schemas;
- workflow definitions;
- Path-A trust-policy bytes/certificate hashes;
- public branch-protection configuration evidence;
- a hash-only anchor branch.

It must contain **no prediction numbers, no Pool18/Core13/Expansion5 values, no Excel bytes, and no private source documents**.

GitHub documents protected branches as available on public repositories under GitHub Free. Live settings must still be independently read back before activation.

## Branch model

### `main`
Protected control-code branch:
- pull request required;
- fixed acceptance/status checks required;
- force push disabled;
- branch deletion disabled;
- protection enforced for administrators.

Any governance/script/workflow change therefore becomes an explicit public control-code change rather than an invisible private edit.

### `anchor`
Hash-only append branch:
- force push disabled;
- branch deletion disabled;
- protection enforced for administrators;
- normal fast-forward commits by the official control workflow allowed.

`anchor_ledger.jsonl` is hash chained. `m8_verify_anchor_git_history.py` additionally verifies that every historical version of this file is a byte prefix of the next version. Thus an ordinary commit that edits/deletes prior anchor lines also creates an integrity failure even though git history itself remains intact.

## Official weekly flow

1. Protected public-control workflow checks out public control code.
2. It checks out the private state repository using a fine-grained PAT scoped only to the private repository.
3. It checks out the public `anchor` branch.
4. It verifies anchor git history is append-only.
5. It requires private Release Registry and Round Ledger heads to equal the latest public anchor heads.
6. It validates one due Authority, approved release, Path-A trust root, schedule and current private ledger head.
7. It obtains and verifies the Authority FreeTSA RFC3161 receipt.
8. Receipt evidence is uploaded before private mutation.
9. It appends the PREDRAW event to the private ledger and pushes one fast-forward private commit.
10. It builds a **hash-only public anchor record** from that exact private commit and new state heads.
11. The anchor record itself receives a second FreeTSA RFC3161 receipt.
12. It appends one anchor event to `anchor_ledger.jsonl`, commits the record/receipt to the public `anchor` branch, and fast-forward pushes it.
13. Confirmatory PREDRAW eligibility requires `ON_TIME_PUBLIC_ANCHOR`. If the public-anchor receipt gentime is after cutoff, the round is TRACK_ONLY/factor=1.

## What is publicly visible

Only process metadata/hashes:
- round number and event type;
- private git commit SHA;
- Release Registry head hash;
- Round Ledger head hash;
- event-hash tail metadata (`event_hash`, `prev_event_sha256`, type, round);
- Authority SHA and Authority TSR SHA;
- anchor record/TSR SHA and gentime.

Prediction numbers and source data are schema-forbidden in the public anchor event.

## Why this replaces private branch protection

The private repository may be rewritten, but such a rewrite cannot silently replace the already-published public state sequence:
- a deleted/rewritten private ledger head no longer matches the latest public anchor;
- a rewritten Release Registry head no longer matches;
- PREDRAW then ADMIN_MISSED conflict is rejected in the public anchor chain;
- public anchor-history edits/deletions are detectable because protected git history remains and every file revision must be append-only;
- a private workflow's fake PASS status has no authority.

The authoritative process is therefore the combination of:
1. protected public control code;
2. protected append-only public anchor history;
3. FreeTSA time-prior evidence;
4. private Release Registry / Round Ledger cryptographic chains;
5. exact equality between private state heads and the latest public anchor.

## Failure semantics

- Private push failure: preserve Authority receipt; do not rebase or regenerate outcome-sensitive content.
- Private push succeeds but public anchor fails: private event exists but is not confirmatory until the exact same state is anchored. If anchor gentime misses cutoff, TRACK_ONLY.
- Changed private head during recovery: INTEGRITY_FAILURE.
- Changed public anchor head during recovery: INTEGRITY_FAILURE; no auto-rebase.
- Public anchor history non-append edit: INTEGRITY_FAILURE.
- Duplicate/conflicting terminal round status in public anchor: INTEGRITY_FAILURE.

## Activation conditions

Before live activation:
1. Claude independent review of this R3.3.2 semantic/governance change passes.
2. User creates the public control repository.
3. `main` and `anchor` protection are configured and read back.
4. Fine-grained PAT scope is verified.
5. Exact R3.3.2 code is deployed to public control `main` through the protected path.
6. Non-production private-state -> FreeTSA -> private append -> public anchor rehearsal passes.
7. Activation record is itself externally time-sealed and hash-anchored.

No predictive research is authorized merely by creating this profile.

## R3.3.3 implementation closure

The R3.3.2 review found a specification/implementation gap: the public-anchor requirement was documented but not enforced by the scorer, while the old private scheduled PREDRAW workflow remained executable. R3.3.3 closes both paths:

- `m8_score_eligibility.py` now requires an ON_TIME public anchor for the exact private PREDRAW event before returning confirmatory eligibility;
- absence/late public anchor -> TRACK_ONLY/factor=1;
- malformed or mismatched anchor evidence -> integrity failure;
- `m8-weekly-authority-timestamp.yml` is removed;
- `m8-public-control-weekly.yml` is the only weekly PREDRAW workflow in the candidate.

A private workflow PASS, a valid private Authority TSR, or a private ON_TIME PREDRAW cannot by themselves create confirmatory credit.
