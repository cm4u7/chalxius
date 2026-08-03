# Chalxius v0.6.4 — Goal-Driven Advisory Recovery

Chalxius 0.6.4 makes the cautious BF-1–BF-3 recovery slice reachable from an
ordinary research request without asking the user to know or say “Campaign.” It
also closes release-validation and runtime-cutover defects exposed while
validating that change.
The Paper-first research model, domain-indexed target continuity, independent
verification, and sole Fact-admission path remain unchanged.

## User-visible outcome

Under the default `auto` mode or an explicitly selected `deep` mode, a user may
state an explicit research objective in ordinary Chinese or English.
Operator-only `research-goal-intake` then:

1. normalizes Unicode NFC and whitespace without semantic or fuzzy matching;
2. reuses exactly one lexically identical objective or creates one prospective
   internal Campaign scope;
3. ignores the `ACTIVE` pointer and never retags existing Research;
4. honors explicit Brave Future disablement; and
5. projects advisory BF-1 for that exact scope.

The user does not need to mention Campaign or invoke a Campaign command. The
returned internal id is available to bind future Research and, only after real
blockage evidence exists, the inherited BF-2/BF-3 reassessment path.

## Authority boundary remains narrow

Goal intake does not:

- plan a round or choose a worker;
- dispatch an agent or Pulse;
- create or rewrite Research;
- close or continuously advance a Campaign;
- manufacture blockage evidence;
- activate BF-2/BF-3 merely because a goal exists; or
- affect Paper, Candidate Release, Certification, Gateway, Fact, Reader, or
  Learner authority.

`fast` and `deep` remain explicit mode choices. Goal intake is available in
`auto` and `deep`; `fast` retains explicit low-level Campaign administration.
BF-4, `plan_one`, `execute_one`, and `plan-round --reassessment` remain rejected.

## CHX-063: natural-language goal activation

The prior interface exposed only id-bearing Campaign operations. A complete
research objective could therefore enter ordinary research while advisory BF-1
stayed dormant. CHX-063 adds exact, idempotent goal compilation without reviving
fuzzy routing, `ACTIVE`, a second scheduler, or background autonomy.

Qualified owner:
`run-20260803T050224999419Z-b61fe8ef982a/CHX-063`.

## CHX-064: audit nonmutation must be measured

The aggressive mutation audit formerly relied on caller-provided bytecode
suppression and reported `candidate_unchanged=true` without measuring unexpected
paths. It now disables bytecode intrinsically, propagates that policy to every
child, snapshots the complete path/kind/mode/content-or-link identity, and makes
any drift fail the audit. `--help` is now a true zero-audit path.

Qualified owner:
`run-20260803T061517579316Z-67d1a8c570ed/CHX-064`.

## CHX-065: parallel validation needs compatibility phases

The repaired audit correctly caught a full-suite process writing bytecode into
the same cold tree during a concurrent run. Chalxius now ships a reusable
release-validation coordinator that:

- binds every lane to one approved `MANIFEST.sha256` identity;
- creates canonical, no-symlink, manifest-only `lane/chalxius` copies;
- isolates lane temporary and runtime-archive state;
- permits compatible baseline checks to run in parallel;
- places the snapshot-sensitive mutation audit behind a phase barrier;
- snapshots the source and every lane; and
- emits one aggregate fail-closed receipt.

Missing or duplicate lanes, mixed identities, shared mutable roots, nonzero
results, timeouts, source drift, lane drift, or phase-barrier removal all reject
the matrix. The mechanism is domain-neutral and can validate Chalxius research
infrastructure used for philosophy, mathematics, empirical, or mixed projects.

Qualified owner:
`run-20260803T063745640293Z-1ebe1ce2cc97/CHX-065`.

## CHX-066: deep must include applicable goal intake

The first goal-intake implementation hard-coded `auto` as the only eligible
profile, even though `deep` requests every applicable expensive research
feature. Goal-intake revision 2 now accepts exactly `auto` and `deep`, returns a
mode-specific trigger, and continues to reject `fast` before writes. The
exact-match, no-`ACTIVE`, future-only binding, explicit-disablement,
evidence-gated BF-2/BF-3, and zero-authority boundaries are unchanged.

Qualified owner:
`run-20260803T080711145538Z-d486dce92032/CHX-066`.

## CHX-067: protected cutover must not repeat a whole-project audit

The earlier cutover gate reconstructed a protected project before the swap and
again after installing byte-identical candidate bytes. The replacement gate is
receipt-first. One hash-approved request binds the exact runtime delta, complete
release matrix, prior current audit, terminal rounds, historical runtime
bindings, and the audit-relevant project digest. An affecting delta pays for one
deep audit while building the receipt; an unchanged non-affecting delta reuses
the prior audit. Cutover checks the same receipt and project digest after the
swap, with automatic rollback on drift. It never runs a second semantic audit.

Qualified owner:
`run-20260803T090357863328Z-315775267e7b/CHX-067`.

## CHX-068: stale mutation plans must fail before the expensive baseline

Mutation targets were formerly checked only when each mutant was reached. A
refactor could therefore leave a late textual target stale after the full
baseline and many earlier mutants had already run. The audit now resolves the
entire registry before any baseline subprocess, requires each target to be one
contained regular file, and requires exactly one occurrence of every attack
fragment. Mutation uses the same resolver, and a self-mutant protects the
preflight ordering. This reduces wasted validation without weakening release
acceptance.

Qualified owner:
`run-20260803T094645700515Z-355e835f8fef/CHX-068`.

## Preserved 0.6.3 and earlier behavior

The release retains:

- bounded content-addressed Paper-continuation status with explicit forensic
  full reconstruction;
- ordered digest-bound CHX ledger lineage and public disclosure;
- complete draft-to-DAG, Paper Research Pipeline, and atomic Paper-subject Fact
  preflight;
- philosophy stance continuity, mathematical proof/disproof target continuity,
  empirical estimand continuity, and explicit mixed adapters;
- composable independent verification with the ordinary Candidate →
  Certification → Gateway → Fact boundary;
- read-only historical runtime archives and transactional global cutover; and
- the BF-1–BF-3 advisory-only L3/L4 recovery boundary.

No existing Paper, Research, Campaign, Candidate Release, Decision, Fact,
Evidence object, task card, CHX ledger, or frozen runtime is rewritten or
backfilled. No Fact authority is inherited or migrated.

## Validation

The release asset is manifest-complete, deterministic, symlink-free, and
bytecode-free. One final manifest-bound matrix passed self-test, all 646 tests,
all 138 mutants, exact lane isolation, and exact nonmutation. The deterministic
archive then passed manifest and cold self-test checks. The installed tree was
proved byte-identical to that candidate and received only the lightweight
identity, self-test, and `deep` goal-intake smoke checks; the complete matrix was
not repeated. Exact identities, timings, CHX hashes, rollback paths, and the
project-validation receipt are recorded in [VALIDATION.md](VALIDATION.md) and
[RELEASE.lock.json](RELEASE.lock.json).

## Install

Download adjacent assets:

- `chalxius-0.6.4-goal-driven-advisory-recovery.tar.gz`
- `chalxius-0.6.4-goal-driven-advisory-recovery.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.6.4-goal-driven-advisory-recovery.tar.gz.sha256
tar -xzf chalxius-0.6.4-goal-driven-advisory-recovery.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
```

Installing over a global runtime is a separate explicit cutover decision. Use
the bundled project-validation receipt builder and transactional cutover gate,
and name every protected project. A valid unchanged receipt avoids duplicate
whole-project audits; missing, stale, or semantically affected evidence fails
closed or requires the one necessary full audit.

## Scope

Software validation establishes exercised workflow and byte-identity
properties. It does not verify a philosophical claim, prove a theorem, validate
an empirical result, certify a manuscript, or admit a Fact. The sole truth path
remains `Research → Candidate Release → Certification Decision → Fact`.
