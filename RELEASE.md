# Chalxius v0.7.15 - Research Obligation Closure

Chalxius 0.7.15 closes two sources of duplicate Research work and publishes the
validated successor line accumulated after v0.7.4. It preserves the V5 truth
path, historical runtime compatibility, worker provenance, and the logical
two-subround Research architecture.

## Research obligation closure

- A valid ingestion receipt in a live, non-aborted production round closes
  only its source Research obligation for the default generic frontier.
- Pending, quarantined, invalid, missing, aborted, or differently bound work
  closes nothing. The worker-result Research remains visible, while history
  and explicit-ID continuation are unchanged.
- Generic planning repeats the selected-obligation check from fresh bytes
  under the final mutation lock, preventing a newly completed receipt from
  producing a duplicate public round.
- Main-role `memory-add` reuses an existing unbound Research record only when
  every normalized semantic field except actor is identical. Ordinary,
  Operator, task-bound, assignment-bound, historical, and semantically
  distinct writes remain actor-sensitive.
- Actor display text grants no Main authority. The mechanism is selected by
  the explicit caller role and adds no persistent cache, scheduler, watcher,
  lifecycle state, automatic successor, or truth shortcut.

## Integrated successor line

The release also publishes the previously local 0.7.5 through 0.7.14
successors as one validated runtime:

- compact manifest-bound startup contracts for Research production,
  supervision, Candidate adverse work, and bounded Chalxius Learner document
  editing;
- selective Fact-readiness checkpoints that form dependency-closed authoring
  batches without automatically atomizing claims or creating Candidates;
- early Candidate preflight rejection of non-atomic statements, canonical
  `candidate_fact` return validation, and hash-bound repair specifications;
- command-local inspection reuse and bounded status/frontier projections,
  without persistent authority caches or weakened final-lock checks;
- a protected runtime cutover receipt that binds the candidate, prior runtime,
  release matrix, exact runtime diff, project snapshot, and one necessary deep
  audit; and
- compact Main preparation for Candidate adverse review while preserving the
  fresh verifier, Certification, Gateway, and Fact gates.

## CHX and PHX closure

The continuous public CHX lineage covers CHX-001 through CHX-035. For this
release, CHX-032 closes validated production-obligation handling and CHX-033
closes explicit Main unbound-Research reuse. CHX-034 and CHX-035 strengthen
mutation witnesses for the existing release preflight and exact include-history
frontier branch; they add no production mechanism.

PHX remains advisory and nontruth. PHX-002 records a supported, digest-bound
measurement and adopts only the installed Research-obligation mechanism under
the user's exact constraints. It establishes no Research validity, Candidate
readiness, or mathematical premise.

## A-model Research boundary

The A-model cycle that supplied the field workload is closed for this release.
Its artifacts remain nontruth Research. Version 0.7.15 creates no Candidate
Release, Certification Decision, Gateway admission, or Fact from that work.

## Validation and installation

The exact 251-entry manifest passed the six-lane release matrix:

- strict architecture reconnaissance;
- mutation-registry preflight with 148 exact single targets;
- the behavioral feature gate;
- the full discovered suite with 889 passing tests;
- the bundled self-test; and
- aggressive audit with 148/148 registered mutants killed.

Every lane and the candidate source retained one manifest identity. The final
matrix receipt SHA-256 is
`d8d35f1bf296895a1d59689d1bc05b57bec914b2e50add37223c2db5da4f028c`.

The deterministic USTAR archive contains 252 members and was reproduced
byte-for-byte in a second build. A fresh extraction passed all 251 manifest
hashes, the bundled self-test, and the no-cache check.

The exact candidate was globally installed through the protected cutover. One
fresh candidate-runtime project audit was reused through the exact swap; no
duplicate post-swap semantic audit ran. All 201 protected Research rounds were
terminal, the project remained `current_ok=true`, and its protected snapshot
remained
`e49f11893069389999ff154916e093ad1a59395314736629ce5f75e7f2c89b15`.
The previous 0.7.14 runtime remains available for rollback.

Exact receipts and hashes are recorded in [VALIDATION.md](VALIDATION.md) and
[RELEASE.lock.json](RELEASE.lock.json).

## Install

Download adjacent release assets:

- `chalxius-0.7.15-research-obligation-closure.tar.gz`
- `chalxius-0.7.15-research-obligation-closure.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.7.15-research-obligation-closure.tar.gz.sha256
tar -xzf chalxius-0.7.15-research-obligation-closure.tar.gz
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
verification, Certification, Gateway admission, or Fact admission.
