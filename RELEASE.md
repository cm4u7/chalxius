# Chalxius v0.7.0 — Failure-Informed Efficiency

Chalxius 0.7.0 reduces routine Research coordination and validation cost while
preserving the V5 truth path and its independent release gates. The release
targets failures reproduced in real runs instead of adding broad speculative
checks to every operation.

## Research workflow

Prospective Research uses two logical subrounds:

1. Production creates proof attempts, literature and source analysis,
   interpretation, insight, and computation designs. It rejects dedicated
   `refute` assignments. A computation design freezes reviewable core code,
   mathematical design, and dependencies before execution.
2. Supervision assigns at most three scoped `refute` workers over exact frozen
   production returns. Scope selection comes from a small static registry of
   reproduced failures: program–math projection, proof boundary and scope,
   source locator and applicability, and cross-output integration.

The subrounds are logical, not global time barriers. A completed logical
component may enter supervision while unrelated production workers continue;
dependency-related work remains in one component. Findings create a later
copy-on-write Research repair round. Admitted Fact dependencies are frozen
premises rather than default counterexample targets.

Formal computation starts only after a safe program–math disposition. The
execution round revalidates the exact live supervisor result and latest
disposition under its write lock, reuses the reviewed source and dependency
hashes, and returns actual logs and output for another supervision round.

## Failure-informed efficiency

- Plain interpretive insight receives no blanket proof review. Frozen
  proof-boundary signals selectively activate proof-logic supervision when an
  interpretive artifact is load-bearing.
- Integration review is used only when one logical component crosses at least
  two primary supervision scopes.
- New production cards receive one Blackboard root node and no write space by
  default. Explicit promoted queries and write capabilities remain available.
- New V5 Pulse planning is retired. Historical V5 and V4 Pulse records remain
  readable and completable under their original contracts.
- Candidate supervision and fresh-adverse readiness fail before expensive
  artifact normalization, source audit, fingerprinting, and sealing. The
  Candidate seal lock rechecks the live supervisor-result set once immediately
  before writing.

## Field-integrated repairs

The final candidate also repairs four defects found while using A-model
Research as a nontruth stability workload:

- Paper-continuation applicability traverses only selected Research ancestry
  instead of scanning all project Research during a Fact read.
- The exact active admitted Fact closure is projected to a worker only for the
  dual typed `fact_closure_reconstruction` request; inactive roots or
  predecessors fail before dispatch.
- Frozen proof-boundary signals reach the selective supervisor planner without
  changing immutable receipt hashes.
- Public CHX disclosure can recognize one strictly later, resolved,
  explicitly `supersedes` successor without rewriting an immutable predecessor.

Five focused release-only mutation probes protect these reproduced failures.
They add no new normal-runtime gate.

## Authority boundary

The sole truth path remains:

`Research → Candidate Release → Certification Decision → Fact`

Research, supervisor reports, attack-route suggestions, CHX and PHX records,
software tests, release receipts, and package hashes all have
`truth_effect=none`. Whole-Candidate adverse review, the fresh Verifier,
Certification, Gateway, and Fact admission remain distinct later stages.

## Validation

The exact 242-entry manifest passed one final manifest-bound six-lane matrix:

- strict architecture reconnaissance with no errors, warnings, or orphan
  modules;
- mutation-registry preflight with 147 exact single targets;
- the behavioral feature gate over 29 registered features;
- all 838 unit and integration tests;
- bundled self-test; and
- 147/147 mutation kills with the source and every isolated lane unchanged.

The deterministic archive contains 243 members including
`MANIFEST.sha256`. A fresh extraction passed all 242 manifest hashes, bundled
self-test, and cache/bytecode absence checks. The validated candidate was also
installed through the protected atomic cutover path after one project deep
audit; the same exact project snapshot was reused after the swap and the prior
runtime remains available for rollback.

Exact receipts and hashes are recorded in [VALIDATION.md](VALIDATION.md) and
[RELEASE.lock.json](RELEASE.lock.json).

## Install

Download adjacent assets:

- `chalxius-0.7.0-failure-informed-efficiency.tar.gz`
- `chalxius-0.7.0-failure-informed-efficiency.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.7.0-failure-informed-efficiency.tar.gz.sha256
tar -xzf chalxius-0.7.0-failure-informed-efficiency.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 scripts/self_test.py
```

Replacing an active global runtime is a separate protected cutover operation;
do not copy files over a runtime that already owns frozen task cards.

## Scope

Software validation establishes exercised workflow and byte-identity
properties. It does not prove a theorem, certify a manuscript, validate an
empirical result, or admit a Fact.
