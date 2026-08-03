# Validation — Chalxius v0.6.4

This record covers the exact public asset, the single final high-cost matrix, a
cold-archive smoke check, and the installed runtime. Software validation
establishes exercised workflow, identity, and nonmutation properties only; it
does not certify research claims or admit Facts.

## Release identity

| Field | Exact value |
|---|---|
| Version | `0.6.4` |
| Display name | `Goal-Driven Advisory Recovery` |
| Release date | `2026-08-03` |
| Archive | `chalxius-0.6.4-goal-driven-advisory-recovery.tar.gz` |
| Archive bytes | `2,034,377` |
| Archive members | `208` |
| Archive SHA-256 | `50f9c680a312d772314c3a797b288151b0d3399697705f72659761b1ad06ca8e` |
| Manifest entries | `207` |
| `MANIFEST.sha256` SHA-256 | `353387b7f0a0d6b176201a16ff14de7486139ede8a9403d5dc4e7058cf4b7db5` |
| Deterministic double build | PASS |
| Symlinks / bytecode / cache in asset | `0 / 0 / 0` |

The archive builder produced two byte-identical gzip/tar streams, normalized
member order, ownership, mode, and timestamp, and verified the exact
manifest-listed regular-file set. A fresh extraction then passed all 207
manifest hashes and the bundled self-test.

## Necessary-validation strategy

Release 0.6.4 uses one final manifest-bound high-cost matrix. The deterministic
archive and installed tree were proved to contain the same bytes, so their
acceptance used manifest, self-test, identity, and targeted smoke checks instead
of repeating the complete suite and mutation audit.

This is evidence reuse, not a weaker truth gate:

- a changed manifest invalidates the matrix;
- a stale or inapplicable mutation plan fails before its baseline starts;
- any source or lane drift invalidates the aggregate receipt;
- a changed protected-project digest invalidates the cutover receipt; and
- a runtime delta that affects deep project interpretation requires one fresh
  project audit.

## Final coordinated matrix

Contract revision:
`chalxius-release-validation-matrix-1`.

| Lane | Result | Duration | Nonmutation |
|---|---:|---:|---:|
| Self-test | PASS | `1.332 s` | lane PASS |
| Complete suite | `646/646` PASS | `97.358 s` | lane PASS |
| Aggressive mutation audit | `138/138` killed | `159.889 s` | lane PASS |

Aggregate properties:

- `complete_lane_set=true`;
- `one_manifest_identity=true`;
- `isolated_lane_roots=true`;
- `snapshot_sensitive_audit_exclusive_after_baseline=true`;
- `source_unchanged=true`; and
- `lane_unchanged=true` for every lane.

Receipt SHA-256:
`1ddbf0855ecd092a971f888522a58c92889da03b2ffab8d48e0b23c04e68c6a6`.

A preceding diagnostic matrix is not release evidence. Its ordinary 645-test
and self-test lanes passed, but its mutation lane rejected an obsolete
zero-occurrence target after 130.247 seconds. CHX-068 added a complete
read-only registry preflight before any baseline subprocess; the final
138-mutant plan passed that preflight and the full lane.

## Receipt-first protected cutover

Cutover contract revision:
`chalxius-runtime-cutover-2`.

| Field | Exact result |
|---|---|
| Dry-run | PASS in `2.410 s` |
| Real same-parent cutover | PASS in `4.684 s` |
| Project-validation request SHA-256 | `a6697dcdcb78f308de3130da65608aaedbf2fb82aa6b7414e76ff23c21cbe3f6` |
| Project-validation receipt SHA-256 | `a7ed3517357361300dddbfb6c140d0be3ae2fba2be005321a1386e7111fe4b1c` |
| Deep project audit required | `false` |
| Full project audits during receipt/cutover | `0` |
| Audit-relevant project files | `8,536` |
| Audit-relevant project bytes | `71,194,078` |
| Project state SHA-256 before/after | `4540e676ccd775970e2b2e35d491bbb11abc675ed2402d8e375849cf5ac4e85e` |
| Terminal frozen rounds | `10/10 completed` |
| Historical runtime bindings | `2/2 resolved` |
| Automatic rollback | armed; not needed |

The request classified the exact 21-path candidate-versus-installed delta as
prospective goal intake, advisory routing, host-only cutover/release validation,
tests, and documentation. It did not change lifecycle storage, task-card or
round interpretation, audit semantics, Paper/Research/Candidate/Certification/
Gateway/Fact authority, or historical project schemas. The receipt reused the
prior exact current audit only while the complete project digest remained
unchanged.

The request, receipt, and installation receipt are operator-local validation
artifacts and are not part of the public skill archive.

## Installed runtime

| Identity | SHA-256 |
|---|---|
| Candidate path-bound runtime identity | `855fe06ecf2a8179e754b2a3018bffcd18c1318562f6e565ceb75bc74c329304` |
| Prior installed runtime identity | `7aba89d8e21b25691c52c9aedccd4365c9087ee5ae174dfcdd0d2d12791ef4cd` |
| Final installed path-bound runtime identity | `3acf349ba7728d142dbc76c8d33587a09a624d5c7b0312dedd393b20df8ee678` |
| Final runtime content | `074f3f0ac858fe142248081b9e076a1b42a3c171435d6f2584627c2978c4e67f` |
| Final archive tree | `52d8570b4ce9411a1b9bf298734311020bb8a7369a2785f08a3dc3ea4f0e728c` |
| Prior rollback runtime content | `53faafcf0593c556bdc100f00134e816801c355aedd1967d3deacd07983a7bc3` |

The candidate and installed directories passed a recursive byte-for-byte diff,
the installed exact-manifest validator reported 207 entries, and the installed
self-test passed. The prior tree remains available under the dedicated
`.chalxius-pre-0.6.4-bounded-cutover-20260803` rollback directory and in the
content-addressed archive.

The complete matrix was not rerun after installation: byte identity, installed
self-test, and the following fresh behavioral smoke were the necessary checks.

## Installed `deep` goal-intake smoke

A fresh V5 project was initialized in `deep` and received only:

```json
{
  "revision": "chalxius-bf-goal-intake-2",
  "objective": "Regenerate the philosophy paper from its inherited Paper Graph in deep mode while preserving its argumentative position and addressing expert feedback."
}
```

No Campaign id or Campaign terminology was supplied. The installed output:

- created `campaign-fc6ec2c4d1fb` from the exact goal;
- returned `trigger="explicit_user_research_goal_under_deep"`;
- projected advisory BF-1;
- left BF-2/BF-3 at
  `awaiting_existing_exact_blockage_evidence_gate`;
- reported `active_campaign_pointer_used=false` and
  `fuzzy_objective_matching=false`;
- bound future Research without retagging existing Research;
- reported `automatic_plan=false` and `automatic_dispatch=false`; and
- preserved `fact_admission_effect="none"` and `truth_effect="none"`.

## CHX public-disclosure preflight

The package enumerates CHX-001 through CHX-068 across eleven ordered,
digest-bound ledgers. The qualified public head is
`run-20260803T094645700515Z-355e835f8fef/CHX-068`.

The final six mechanisms are:

- CHX-063 — exact user-goal intake without Campaign jargon;
- CHX-064 — intrinsically nonmutating aggressive release audit;
- CHX-065 — manifest-bound isolated validation lanes;
- CHX-066 — the same goal trigger under `deep`;
- CHX-067 — receipt-first cutover with at most one necessary project audit; and
- CHX-068 — complete mutation-plan preflight before expensive baselines.

Public-disclosure validation passed exact issue enumeration, resolved
dispositions, predecessor ownership, ledger digests, qualified namespaces, and
document markers.

| Artifact | SHA-256 |
|---|---|
| Public CHX registry semantic | `10945fb37ed43c7aef5fdf495f6c97cbc8952a66f003bd64aa5b01c030445216` |
| Latest ledger file | `7c3ae2734d20cf21536a36409b9696c2d1a1a3cfa7573dc755d1d2e2b5c80d4f` |
| Latest architecture report | `5fd853a37d7a38db96d85a50da7f5eeca8cd07c4394ad262f27b3dc6082059bf` |
| `KNOWN_LIMITATIONS.md` | `943c4bb00f36bc330a0a81fc424fd72ac6f998378da4d3f0d31a1fcfc02382ea` |
| `v5_release_traceability.md` | `5e2b54f7df82cdd8e9340ac647f791530648bec964ea3bd3a03bcd5f5cb2d410` |

Private ledgers and field research are not shipped. Resolved mechanisms do not
establish permanent architectural completeness; new findings enter a new
append-only ledger.

## Preserved Paper Research assurance

The 0.6.2 field assurance remains bound to its frozen private baseline: 1,499
Paper nodes, 2,553 edges, 101 atomic claims, 144 dependencies, and 1,200/1,200
domain-neutral semantic mutations killed with zero harness errors. That later
nontruth assurance does not upgrade any historical admission.

## Runtime compatibility closure

| Field | Exact value |
|---|---|
| Baseline | `chalxius-0.4.3` |
| Protected files | `88` |
| Protected-tree SHA-256 | `6c36904804bf7d0fba03d018aefbc62fa78ed1e020d3a1325f044944622b3faa` |
| Changed protected paths | `40` |
| Changed-path inventory SHA-256 | `bcba05a61267cc03764003fea15e35c998ac37fe2de5e85888c575002dd69a58` |
| Fact-admission contract changed | `false` |

## Contract hashes

| Contract | SHA-256 |
|---|---|
| `INHERITANCE.lock.json` | `694adc5b8643bd557782f3901f5e050c05db52d414f23b9d8c2b45759c43bf09` |
| `scripts/release_validation.py` | `fcbe628b04f67e0f826350ce3f25d19c30137e96089de2df786e23da61ae96db` |
| `scripts/aggressive_bug_audit.py` | `0f33cd5b2f62275fff368aea27d6dc2bd9d5e89ecc29b5bc84bb31269fa83037` |
| `scripts/runtime_cutover.py` | `a781a6417c82ec5f6e37697a82c3dc9baea4a7c42f1945d7d45d9818028f335c` |
| `scripts/runtime_cutover_project_validation.py` | `24a418298edb5a9b1d4d0edeb2100d694b53009ebc0bbba800a061fb799095ab` |
| `scripts/mathgraph/runtime_cutover.py` | `589a9d42f3a21cd2c278a055b0372a5af02b9234d0e7e8495224a5c68aaefab6` |
| `scripts/chx_ledger.py` | `eb17f987b35b81a4e48cd8130981c99749f6ec8261ec9f0b5583a65d192cfc94` |

## Scope boundary

Hashes establish byte identity. Tests establish only exercised properties.
Mutation scores establish only detection of enumerated faults. Goal intake,
Brave Future projections, Paper Audit, Evidence, Reader rendering, CHX closure,
status projection, software validation, and cutover receipts do not substitute
for fresh independent verification, Certification, and Fact admission.

