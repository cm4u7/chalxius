# Chalxius v0.7.4 — Bounded Main Routing

Chalxius 0.7.4 makes attack-route evolution a bounded Main responsibility and
adds a work-elimination checkpoint to compact Research workers. It preserves
the V5 truth path, frozen-card compatibility, and the two-subround Research
architecture introduced by earlier releases.

## Main-governed attack routes

- Attack and supervision workers return concrete failure evidence, affected
  boundaries, and surviving boundaries. They do not author persistent attack
  rules.
- Main alone decides whether repeated evidence justifies a reusable route,
  writes the mechanism-level abstraction, and records its provenance.
- Current route text is English and mechanism-level. Case-specific phrases are
  rejected as persistent rules when they cannot transfer beyond the incident.
- A current route is capped at 720 code points in total, including at most 280
  for its instruction, 180 for scope, and two 180-code-point guards. Oversized
  material must be semantically compressed; blind truncation is forbidden.
- A project and each newly frozen task card may expose at most sixteen active
  current routes. Main's default promotion queue remains at most three concrete
  failure families per decision pass.
- Legacy route contracts remain readable for frozen historical cards.

## Worker work elimination

The compact production and supervision bootstraps now require the first
post-startup milestone to be either one durable artifact or one explicit
blocker. Repeated status-only drafting while the artifact directory is empty
may be reclaimed by Main and recorded under the existing worker-CHX mechanism.
This is a protocol checkpoint, not a watcher, timer, lifecycle state, package
gate, audit, or truth gate.

The English-only check for current internal governance text is intentionally
small. An isolated local microbenchmark measured approximately 7.2–7.6
microseconds per validation call. The high-cost target remains repeated broad
protocol loading and avoidable repair/replay work, not this text predicate.

## CHX and PHX integration

The public CHX lineage now covers CHX-001 through CHX-022. CHX-021 records the
worker-authored, oversized, case-specific route problem; CHX-022 records
status-only startup delay before the first substantive artifact. Both are
closed by reusable 0.7.4 behavior and public architecture documentation.

PHX remains advisory. The adopted route is
`route.main_governed_abstract_attack_rules.adopted`: workers supply incident
evidence, Main performs abstraction and promotion, and route size is bounded.
No PHX entry admits a Fact or silently changes the truth path.

## A-model Research boundary

The release cycle also produced nontruth Research for the local
\(K_{\mathbb P^2}\) program:

- a finite-heart, unique-vanishing-simple, non-spherical mass-gap mechanism;
- a reusable finite-quiver quotient majorant;
- a common-domain analytic factorization criterion with controlled word and
  operator growth, including one parameter derivative via a buffer-domain
  Cauchy estimate; and
- a non-Dynkin formal control class from cyclic quivers with potential.

The formal-to-analytic, degeneration-family, endpoint, and A-model geometry
bridges for that non-Dynkin class remain open. These results are Research only:
no Candidate Release, Certification Decision, Gateway admission, or Fact was
created.

## Validation and installation

The exact 245-entry manifest passed the six-lane release matrix:

- strict architecture reconnaissance: 246 release files, 0 errors, 0
  warnings, and no orphan module or feature;
- mutation-registry preflight: 148 exact single targets;
- behavioral feature gate: 30 registered features;
- full discovered suite: 846 tests;
- bundled self-test; and
- aggressive audit: 148/148 registered mutants killed.

Every isolated lane and the candidate source remained unchanged. A fresh
archive extraction passed all 245 manifest hashes, the bundled self-test, and
the no-cache check. The deterministic archive contains 246 members and was
reproduced byte-for-byte in a second build.

The exact candidate was globally installed through the protected cutover. One
full pre-swap project audit was reused after the exact swap; no duplicate
post-swap semantic audit ran. All 136 protected Research rounds were terminal,
and the project remained `current_ok=true`. The previous 0.7.3 runtime is
retained for rollback.

Exact receipts and hashes are recorded in [VALIDATION.md](VALIDATION.md) and
[RELEASE.lock.json](RELEASE.lock.json).

## Install

Download adjacent release assets:

- `chalxius-0.7.4-bounded-main-routing.tar.gz`
- `chalxius-0.7.4-bounded-main-routing.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.7.4-bounded-main-routing.tar.gz.sha256
tar -xzf chalxius-0.7.4-bounded-main-routing.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 scripts/self_test.py
```

Replacing an active global runtime is a protected cutover operation. Do not
copy files over a runtime that owns frozen task cards.

## Claim scope

Hashes establish byte identity. Tests establish exercised software behavior.
Mutation results establish detection of enumerated faults. None of these
receipts proves a mathematical theorem or substitutes for fresh independent
verification, Certification, or Fact admission.
