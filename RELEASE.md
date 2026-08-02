# Chalxius v0.6.3 — Bounded Paper Status / Ledger Lineage

Chalxius 0.6.3 permanently fixes two release-blocking architecture defects
found while continuing a large research draft from its Paper Graph. It keeps
the 0.6.2 paper-led research model, domain-indexed target continuity,
composable verification, and cautious BF-1–BF-3 recovery intact.

No Paper snapshot, Research claim, Candidate, Certification Decision, Fact,
Evidence object, or historical CHX ledger is rewritten by this release.

## Bounded Paper-continuation status (CHX-061)

Routine status used to return a compact projection only after reconstructing
the complete Paper, Research, disposition, and revised-writing closure. That
made the output small but left the computational cost unbounded.

The permanent mechanism is a content-addressed status index:

- immutable per-plan states and receipts;
- one atomic project HEAD with directory-generation fingerprints;
- synchronous advancement or invalidation at plan, materialization, Research,
  disposition, writing, and Paper-snapshot mutation boundaries;
- exactly bounded routine reads, with no summary-to-full fallback;
- fail-closed stale detection; and
- an explicit `paper-continuation-status-index-rebuild` command that commits
  only after indexed counts, adequacy, and receipts equal a full forensic
  reconstruction.

`paper-continuation-status --full` remains available when complete topology is
actually required. `auto` may control research cost, but it still cannot
compress Paper topology, provenance, atomic claims, or target closure.

## Exact-runtime entrypoint nonmutation (CHX-062)

The final cutover rehearsal exposed a second defect: the default Python host
entrypoints could create `__pycache__` before validating the exact runtime file
set. The entrypoints now disable bytecode before any local import:

- `scripts/runtime_cutover.py`;
- `scripts/archive_runtime.py`; and
- `scripts/chx_ledger.py`.

Regression tests clear both `PYTHONDONTWRITEBYTECODE` and
`PYTHONPYCACHEPREFIX`, invoke every entrypoint with ordinary `python3`, and
require a byte-for-byte unchanged runtime tree.

## Ordered CHX ledger inheritance

Public disclosure now covers CHX-001 through CHX-062 across five immutable
ledger runs. Each run binds its exact predecessor, ledger digest, contract
revision, and included issue ids. The current public head is:

`run-20260802T214123599238Z-d206bd85e676/CHX-062`

A short `CHX-NNN` is never treated as globally unique. Disclosure validation
compares the complete ordered lineage, explicit issue enumeration, resolved
dispositions, and required documentation markers. Private ledgers are not
distributed.

## Research continuity remains domain-indexed

| Domain | Frozen continuity object | Valid outcomes |
|---|---|---|
| Philosophy | Argumentative direction, headline thesis, required and forbidden claims | `preserved` or `strengthened`, unless an exact major revision is authorized |
| Mathematics | Problem/conjecture, hypotheses, domains, quantifiers, and target ids | `proved`, `disproved`, or `unresolved_with_obstruction` |
| Empirical | Question, estimand, population, intervention/exposure, outcome, and scope | supported, disconfirmed, or inconclusive |
| Mixed | Explicit component adapters and shared target ids | composed adapter outcomes |

For a research draft, the draft is frozen and decomposed into a
proposition-total Paper DAG, then admitted or strengthened node by node. A
finished external paper remains Evidence and gains no Fact authority from its
reputation, DOI, PDF, or citations.

## Brave Future remains bounded

BF-1 through BF-3 still provide only read-only repair-lineage projection,
zero-write reassessment, and—after exact opt-in—one bounded nontruth advisory
receipt. They cannot select an active Campaign implicitly, plan rounds,
dispatch agents, write Research, change scores, or affect Candidate,
Certification, Gateway, or Fact.

## Validation summary

- Final candidate: 628/628 tests PASS; 119/119 release mutants killed with
  `candidate_unchanged=true`; self-test PASS.
- Cold extracted archive: 628/628 PASS; 119/119 killed; self-test and all
  204 manifest entries PASS.
- Installed global tree: 628/628 PASS; 119/119 killed; self-test PASS; no
  bytecode or cache files; exact tree equals the candidate.
- Deterministic archive: 205 regular files, 2,004,366 bytes; two independent
  builds are byte-identical.
- Transactional cutover: all ten protected rounds and project audit were
  current before and after replacement; exact rollback remains available.
- Real inherited Paper-continuation migration: generation 1, two plans,
  54 targets, 123 Research-lineage records, and content-addressed HEAD
  `8e7302ee2502cf5c41cdd2af6ca02626d4e41a753440ed4e0400e39d305d9302`.
  Routine all-plan status measured 0.34 s and current-plan status 0.29 s after
  the one explicit full rebuild.

These checks establish bounded software and workflow properties only. They do
not establish philosophical, mathematical, or empirical truth; certify a
private graph; establish novelty; or admit a Fact. See
[`VALIDATION.md`](VALIDATION.md).

## Install

Download the adjacent archive and checksum assets, then run:

```sh
shasum -a 256 -c chalxius-0.6.3-bounded-paper-status-ledger-lineage.tar.gz.sha256
tar -xzf chalxius-0.6.3-bounded-paper-status-ledger-lineage.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
```

Replacing an installed skill remains an explicit transactional cutover. A
project created before the status index should use the explicit rebuild command
once; routine status then reads only the validated index. Historical work keeps
its exact runtime identity and authority boundaries.
