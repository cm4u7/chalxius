# Validation — Chalxius v0.6.5

This record covers the exact public asset, the final manifest-bound reliability
matrix, the protected-project receipt, global cutover, PHX/CHX disclosure, and
a cold-archive check. It establishes software properties only; it does not
certify research claims or admit Facts.

## Release identity

| Field | Exact value |
|---|---|
| Version | `0.6.5` |
| Display name | `Integrated Research Continuity` |
| Release date | `2026-08-05` |
| Archive | `chalxius-0.6.5-integrated-research-continuity.tar.gz` |
| Archive bytes | `2,291,346` |
| Archive members | `241` |
| Archive SHA-256 | `9e2945f057ac38a1e41e7dea2d54bd39a68216fa903f1f72f9e1b22532578468` |
| Manifest entries | `240` |
| `MANIFEST.sha256` SHA-256 | `5c8bf3c39b2269d819acbc6d4fbb5835dcb728fd02f8a132e101e6bb4af77e15` |
| Deterministic double build | PASS |
| Symlinks / bytecode / cache in asset | `0 / 0 / 0` |

The archive builder independently produced two byte-identical gzip/tar streams
with normalized member order, ownership, mode, and timestamp. A fresh extraction
passed all 240 manifest hashes, exact manifest identity, and the bundled
self-test.

## Necessary-validation strategy

One final manifest-bound high-cost matrix was run after the candidate metadata
and public-disclosure contract were frozen. The deterministic archive and the
installed tree then reused that evidence only after proving exact manifest and
content identity.

The following invalidate reuse:

- any candidate or manifest byte change;
- missing or stale mutation targets;
- architecture errors, unclassified behavioral orphans, or unreachable public
  state writers;
- source or lane mutation;
- release-receipt or request drift;
- project-state, terminal-round, historical-runtime, or runtime-content drift;
  and
- any change in the semantics that the protected-project classification marks
  as deep-audit affecting.

## Final coordinated matrix

Contract revision:
`chalxius-release-validation-matrix-4`.

| Lane | Result | Duration | Nonmutation |
|---|---:|---:|---:|
| Architecture reconnaissance | PASS | `4.594 s` | lane PASS |
| Mutation-registry preflight | `142/142` exact targets | `0.084 s` | lane PASS |
| Behavioral feature gate | PASS | `8.155 s` | lane PASS |
| Self-test | PASS | `1.533 s` | lane PASS |
| Complete suite | `787/787` PASS | `84.261 s` | lane PASS |
| Aggressive mutation audit | `142/142` killed | `161.960 s` | lane PASS |

Aggregate properties:

- `complete_lane_set=true`;
- `one_manifest_identity=true`;
- `isolated_lane_roots=true`;
- `architecture_gate_before_baseline=true`;
- `behavioral_gate_after_architecture_before_baseline=true`;
- `mutant_registry_preflight_before_baseline=true`;
- `snapshot_sensitive_audit_exclusive_after_baseline=true`;
- `source_unchanged=true`; and
- `lane_unchanged=true` for every lane.

Matrix receipt SHA-256:
`c300d37676921f32779faf46390e1b790654d0a67d92ee2c3e0d94bc3b298323`.

## Full architecture reconnaissance

The final source-tree scan completed in `4.343 s` under strict mode.

| Field | Result |
|---|---:|
| Files including manifest | `241` |
| Python modules | `75` |
| MathGraph modules | `57` |
| Tests | `73` |
| Exact duplicate file groups | `0` |
| Behavioral orphan features | `0` |
| Generated artifacts | `0` |
| Errors | `0` |
| Warnings | `0` |

Inventory SHA-256:
`e022527d476ac2f55fb8ae0dc365932304f56e00b28d5c109b37c7d29f692e30`.

Report SHA-256:
`325cb99367aeb780f9d668578464120fc90132bc073b2f20915ae1218e04c809`.

This is a topology and reachability gate, not a truth validator. The complete
matrix and mutation audit remain independently required.

## Protected-project receipt and cutover

| Field | Exact result |
|---|---|
| Cutover contract | `chalxius-runtime-cutover-2` |
| Project receipt contract | `chalxius-cutover-project-validation-receipt-2` |
| Project-validation request SHA-256 | `46ac15e7e751c2f70223355b2b6c72a1e115ac69bdf091289f4a6bfc297d91ef` |
| Project-validation receipt SHA-256 | `990161bfc9975924807eee0e50c402448d9579bc75b4c7d97894f421847e90e9` |
| Deep audit required | `true` |
| Candidate subprocesses during receipt build | `1` |
| Deep audit duration | `2.855 s` |
| Deep audits repeated during cutover | `0` |
| Audit current | `true` |
| Audit-relevant project files | `20,826` |
| Audit-relevant project bytes | `134,698,238` |
| Project state SHA-256 | `9f1dc9b44c5273dcc023e0377374cd20ce888abf171f2759acd87d2aa2282d1d` |
| Terminal frozen rounds | `11/11 completed` |
| Automatic rollback | armed; not needed |

The exact 102-path candidate-versus-installed delta affected aggregate audit,
Paper continuation, optional Experiment validation, PHX, Evidence, Research,
Candidate, adverse routing, Fact-admission support code, and cutover behavior.
The request therefore required one fresh deep audit. The receipt bound the
final release matrix, prior runtime, historical runtimes, project snapshot, and
terminal rounds. The real cutover reused the exact receipt after the swap and
did not repeat the semantic audit.

The request, receipt, and cutover output are operator-local validation artifacts
and are not included in the public skill archive.

## Installed runtime

| Identity | SHA-256 |
|---|---|
| Candidate path-bound runtime identity | `9c3ca71af057478879fe08f73fd2d1bf8d0a13d6985093a536d5d3b6585ea6be` |
| Prior installed runtime identity | `3acf349ba7728d142dbc76c8d33587a09a624d5c7b0312dedd393b20df8ee678` |
| Installed path-bound runtime identity | `1cff764e03d7e33998c040c6cafbcd0857564d3b84028f3d3167780755f69e4c` |
| Installed runtime content | `167ca09c89f414ef44f81a5c15c3ebd92e2dc6dcae8abb94a62b13d345d3a88d` |
| Installed archive tree | `6f367b6336aae9b89793422607dfc6b31f2c566c1b8dc493f1126d14062ca477` |

The installed manifest is byte-identical to the validated candidate manifest,
all 240 installed hashes passed, and the installed self-test passed. The prior
0.6.4 runtime remains available at
`rollback-before-chalxius-0.6.4-20260805-final` and in the content-addressed
runtime archive.

The complete matrix was not repeated after installation because the cutover
proved exact candidate content and revalidated the protected-project snapshot.
The installed manifest and self-test were run fresh.

## CHX public disclosure

The package explicitly enumerates CHX-001 through CHX-109 across 18 ordered,
digest-bound ledgers. The current qualified public head is
`run-20260804T161234526251Z-380819388733/CHX-109`.

| Artifact | SHA-256 |
|---|---|
| Public CHX registry semantic | `53f16e85551c76d37e9392e05b6769a9c79ce3c3e93af2f3d614f8fded2f8f72` |
| Latest ledger file | `d25e2cf700d838aeee2df9dd21684de49c486e0f679a32af599f62115dc6f939` |
| Latest architecture report | `7d7f0c2523fc4d23e31cd1b2caf489ff0ac991b7bb75203f6c193451f1b5db1b` |
| `KNOWN_LIMITATIONS.md` | `3091fb50f7b339faf19c568797c464f515f8446c3adfbe452b16f438a2097046` |
| `v5_release_traceability.md` | `b61b8b6822be49941ceee2d58c92a9bf3ad0bd3c3125177fa10ba1cfbb60ad42` |

All eight issues in the latest ledger are resolved under one superseding
integrated repair. Public-disclosure validation passed exact enumeration,
dispositions, predecessor ownership, ledger digests, qualified namespaces, and
document markers. Private ledgers and field research are not shipped.

## PHX global route guide

The first PHX ledger is global, project-independent, nontruth, and closed.

| Field | Exact result |
|---|---:|
| Routes | `18` |
| Measurements | `8` |
| Consultations | `0` |
| Adoptions | `0` |
| Ledger SHA-256 | `395d0bd0fa4fc226f1428f172bcb236bd4e87884150039c578d253799151ed07` |
| Report SHA-256 | `c48c4befb0ca3d10ed9b72c99ce7514f96ebbef836bbb68c16418a574225e2bc` |
| Performance search receipt SHA-256 | `64608f860ccc4e833fe9381afbc0fdd319ea5e7f0a60e67fda4469d955ba2ae1` |

The report verifies exactly. Routes are advisory: no route was retroactively
declared adopted, and an active-architecture change still requires an informed
user consultation.

## Runtime compatibility closure

| Field | Exact value |
|---|---|
| Baseline | `chalxius-0.4.3` |
| Protected files | `92` |
| Protected-tree SHA-256 | `0eadb4e2f31d81bdebe6d6469afe17c94962f8bef6bd26688252e9d02c6b6424` |
| Changed protected paths | `44` |
| Changed-path inventory SHA-256 | `91c2e13cc9f70e219cd5a364b2d12ab58478841db2ebd4824d93133edb61d736` |
| Fact-admission contract changed | `false` |

## Contract hashes

| Contract | SHA-256 |
|---|---|
| `INHERITANCE.lock.json` | `f1f303c36b030000a624e5dabef6f59b1059efaea2bdd3231c1ed12d7ca3349c` |
| `scripts/release_validation.py` | `d132a19e80c823cab9c08a6dd100797d27046489582e9d708194cb6faace282b` |
| `scripts/aggressive_bug_audit.py` | `fa1dcc47e24b0125a69395911cc2c55911193c7166e64bedb73b6983cf1e2d31` |
| `scripts/architecture_reconnaissance.py` | `106b0061abe0df4d859e1e9e23d6d21965905135e22cb8aa0a639dec82c3fb99` |
| `scripts/behavioral_feature_gate.py` | `d106a6ba10f2ca2ed71b2eec5084db03ac26222fb7dd4c1b941b72dd814b2a92` |
| `scripts/runtime_cutover.py` | `06aa0e4f4bbee4ab10ca9c4ee5b93f463af420a23e7d2871f1df641a57959b8a` |
| `scripts/runtime_cutover_project_validation.py` | `21caf44365b987501e2bd6dda0237eb9c75d2c507f57015ff82723c6de41d93e` |
| `scripts/mathgraph/runtime_cutover.py` | `057cc4e6a92fb3c40476a62a377040634ba7a1206f2f82216139f307996899a2` |
| `scripts/chx_ledger.py` | `1e8da18f6541b7609cfcf50b6867f24c8731ca51b759394c1708a1730710c33e` |
| `scripts/phx_ledger.py` | `a555dfef5a1c693d53d8a5963243728aed879bb8e704b07f064fbe263c9e7906` |
| `scripts/self_test.py` | `eb3200c7614b5eab2861c61e4771b9b8cfa817749009df428e121aee1db4fbe2` |

## Scope boundary

Hashes establish byte identity. Tests establish exercised properties. Mutation
scores establish detection of enumerated faults. Goal intake, Brave Future,
Paper Audit, Evidence, Reader rendering, CHX, PHX, status projection, software
validation, and cutover receipts never substitute for fresh independent
verification, Certification, and Fact admission.
