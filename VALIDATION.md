# Validation - Chalxius v0.7.15

This document records software, packaging, CHX/PHX, and protected-installation
evidence for Chalxius 0.7.15 **Research Obligation Closure**. It does not certify
any mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | `0.7.15` |
| Release date | `2026-08-14` |
| Skill manifest entries | `251` |
| `MANIFEST.sha256` SHA-256 | `84b9521218079357f4a325ef1561adb70b2663259068d0c18cee6f4d820a6e62` |
| Runtime content SHA-256 | `dacdd1112bd0b9e63f0da46d439acc57b11eb62e7703cc7c9d54b3ccdcc3ccca` |
| Installed runtime identity | `e1ec1d9a49715506c9018ec4fda46f8be688d2bec0517ad8cab34f6fd39fdfe4` |
| Archive | `chalxius-0.7.15-research-obligation-closure.tar.gz` |
| Archive bytes | `2438226` |
| Archive members | `252` |
| Archive SHA-256 | `66cb6bfc0ed2b3ee654d53d15eec352bbfcc57b7b8ea56d7608e2ea721c7b05e` |
| Checksum-file SHA-256 | `ff00d4cf64b77b360ca2e46913cf2c94b68952ecd16526b7d4ca92fa1ea0cb47` |

The deterministic USTAR archive was built twice from the sorted exact manifest
and the two byte streams were identical.

## Release matrix

The final manifest-bound receipt is
`release-validation-0.7.15-final2.json`, SHA-256
`d8d35f1bf296895a1d59689d1bc05b57bec914b2e50add37223c2db5da4f028c`.
It records `ok=true`, `complete_lane_set=true`,
`one_manifest_identity=true`, and `source_unchanged=true`.

| Lane | Result |
|---|---|
| Mutation-registry preflight | PASS; `148/148` exact targets |
| Architecture reconnaissance | PASS |
| Behavioral feature gate | PASS |
| Full discovered suite | PASS; `889/889` tests |
| Bundled self-test | PASS |
| Aggressive bug audit | PASS; `148/148` registered mutants killed |

All six isolated lane copies retained the exact approved manifest and reported
`lane_unchanged=true`.

The focused Research-obligation regression file contains eight tests covering:

- Main-only semantic reuse across actor labels;
- retained actor identity for ordinary and task-bound writes;
- caller authority instead of display text;
- valid receipt closure of source obligations only;
- assignment-local closure;
- pending, quarantined, invalid, and aborted exclusions;
- exact-ID planning without generic frontier reconstruction; and
- fresh lock-held obligation revalidation.

## CHX disclosure

The public lineage is continuous through CHX-035. The final closed ledger and
deterministic report are:

| Evidence | SHA-256 |
|---|---|
| `run-20260814T004319766703Z-fdfc7f3fd6e2.jsonl` | `4eb2660eee4bc089d0bd50fd7f871ad48a2141ce1c0d587fb3e50625eebbf8af` |
| `run-20260814T004319766703Z-fdfc7f3fd6e2.architecture-report.md` | `36b515222031f191f79607ccbc09f60927c90279cc3d7daf544b51646fce198e` |

Public-disclosure verification passed. The private ledgers and reports are not
included in the public package and have no truth effect.

## PHX evaluation and adoption

PHX-002 was evaluated only after protected installation and post-installation
identity checks.

| Field | Value |
|---|---|
| PHX run | `run-20260809T131409541618Z-e6ec115394d1` |
| Ledger SHA-256 after adoption | `7aa5e1d5a5b18dc405faad665591a297f4c3ae66322a79795defd9d303188a27` |
| Consultation | `consultation-62a703ac5ffb398ee39b5b66b90d003775812ce0fa951a42e42dd659641af303` |
| Measurement | `measurement-5d00c8098221212fe654735adce4b72dd304bdc8ab98b0f4ca9f3867654efe96` |
| Adoption | `adoption-7758607e23b0b6526f67e33932713240c1be68ef6e7fa0ccbd02d745c35afdec` |
| Outcome | `supported` |
| Authority | advisory, nontruth, premise-ineligible |

The adoption covers only explicitly Main-originated unbound Research identity
and validated generic production-obligation closure. It does not authorize a
Candidate, verifier shortcut, Certification, Gateway action, or Fact.

## Protected runtime cutover

The approved project-validation receipt SHA-256 is
`d8ed812c0391671f40950974d3db33ff00e8a9e6eaed6de10247d0dc7b06c928`.
It binds the exact candidate manifest, prior 0.7.14 runtime identity, complete
15-path runtime diff, final release matrix, protected project inventory, and
one fresh candidate-runtime deep audit.

The installation receipt SHA-256 is
`2ba4f815611849f4eb3e98a77ed1b8081b0ea65788c01b5da464d7bead863172`.

| Field | Result |
|---|---|
| Cutover status | `cutover_complete` |
| Deep project audits | `1` |
| Duplicate post-swap semantic audits | `0` |
| Protected terminal rounds | `201` |
| Preflight audit | `current_ok=true` |
| Postflight project snapshot | unchanged |
| Project-state SHA-256 | `e49f11893069389999ff154916e093ad1a59395314736629ce5f75e7f2c89b15` |
| Installed self-test | PASS |
| Candidate-to-installed tree diff | no differences |
| Rollback runtime | `0.7.14` preserved |
| Installed archive-tree SHA-256 | `cbaa950f8c91a0b534d0630c7646cfe65a04566d26d85f23a6561ebad0a6208f` |

## Cold archive check

A fresh extraction of the public archive passed:

- `251/251` manifest hashes;
- the bundled self-test; and
- absence of `__pycache__` directories and `.pyc` files.

## Research and truth boundary

The A-model workload is closed as nontruth Research for this release. No
Candidate Release, Certification Decision, Gateway admission, or Fact was
created. Hashes establish byte identity, tests establish exercised behavior,
and mutation results establish detection of registered faults; none proves a
mathematical theorem.
