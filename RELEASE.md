# Chalxius v0.7.3 — Selective Startup

Chalxius 0.7.3 removes repeated administrative work from Research workers and
architecture repair while retaining the verifier-gated V5 truth path. The
release is based on reproduced costs and defects observed in A-model Research
and a separate Chalxius Learner document-editing run.

## Selective startup

- The root `SKILL.md` is a compact router. Current Research production,
  Research supervision, and Learner document editing each load one
  manifest-bound role bootstrap; broader protocols load only when the frozen
  task card or a newly observed event requires them.
- Exact Research objectives project their own frontier directly. They no
  longer construct a full historical frontier and discard unrelated work.
- Logical subrounds remain dependency order, not global time barriers:
  completed components may enter supervision while unrelated production
  continues.
- Repair work mode is immutable across abort and replan. A rejected or aborted
  consumer cannot silently restore ordinary production behavior.

## Failure-informed work elimination

- Latest supervisor dispositions are checked before expensive design
  reconstruction and are revalidated under the final write lock.
- One-off computation is judged first by information value. If the requested
  quantity is already available by an authoritative route, the system records
  the elimination instead of building a redundant execution pipeline.
- Negative source-status claims without frozen response evidence are removed or
  marked unresolved; a new online-query subsystem is not introduced merely to
  preserve a negative statement.
- Worker CHX observations are projected from the task card. Empty or explicitly
  excluded observations remain silent; qualifying architecture costs stay
  append-only and reusable.
- macOS temporary paths are canonicalized before audit containment checks, so
  `/var/...` and `/private/var/...` do not create false mutation findings.

## CHX and PHX integration

The public nontruth lineage now covers CHX-001 through CHX-020 across four
immutable ledgers. CHX-012 through CHX-019 are the integrated 0.7.3 successors
for startup, exact-frontier, repair-mode, source-status, observation,
disposition-order, information-value, and temporary-path findings. CHX-020
repairs public ownership of an explicitly excluded nonarchitectural issue.

PHX remains advisory. It supplied existing failure-informed selective-assurance,
work-elimination, source-status, and robust-practical-repair routes; no PHX
suggestion was silently activated as a new truth gate.

## Research and truth boundary

The A-model workload produced reusable nontruth Research about a finite
bound-quiver quotient majorant. It did not create a Candidate Release or Fact.
For local P2 the finite-heart geometry supplies a three-lift combinatorial
constant, but a family-uniform exponential DT/BPS coefficient bound after the
spherical factor is removed remains open.

The sole truth path is unchanged:

`Research → Candidate Release → Certification Decision → Fact`

CHX, PHX, software tests, release receipts, Research artifacts, and package
hashes all have `truth_effect=none`.

## Validation

The exact 245-entry manifest passed one manifest-bound six-lane matrix:

- architecture reconnaissance: 246 files, 0 errors, 0 warnings, 0 orphan
  modules or features;
- mutation-registry preflight: 148 exact single targets;
- behavioral feature gate: 30 registered features;
- full suite: 844 tests;
- bundled self-test; and
- aggressive audit: 148/148 mutants killed, with every isolated lane and the
  candidate source unchanged.

One protected-project deep audit validated all 125 historical Research rounds
as terminal and `current_ok=true`. The immutable receipt was reused for dry-run
and installation, so the semantic audit was not repeated after the exact swap.
The prior 0.7.2 runtime remains available for rollback.

The deterministic archive contains 246 members including `MANIFEST.sha256`.
A fresh extraction passed all 245 manifest hashes, the bundled self-test, and
the cache/bytecode absence check.

Exact receipts and hashes are recorded in [VALIDATION.md](VALIDATION.md) and
[RELEASE.lock.json](RELEASE.lock.json).

## Install

Download adjacent assets:

- `chalxius-0.7.3-selective-startup.tar.gz`
- `chalxius-0.7.3-selective-startup.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.7.3-selective-startup.tar.gz.sha256
tar -xzf chalxius-0.7.3-selective-startup.tar.gz
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
