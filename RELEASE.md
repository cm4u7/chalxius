# Chalxius v1.0.17 — Literal Input Continuity

Chalxius 1.0.17 makes long-running Research planning more reliable when one
round depends on exact historical mathematical bytes. It also includes the
scope-owned source continuity and explicit repair/head handoff introduced in
1.0.15 and 1.0.16. These changes affect coordination only; Research and Fact
authority are unchanged.

## What changed

- Before Main freezes work that consumes one exact historical formula,
  definition, convention, or theorem statement, it opens the selected artifact
  and binds a byte object that actually contains the input. A symbol mention,
  locator, or downstream coefficient is not silently promoted to capability.
- Source authority belongs to the exact source-owned assignment. Proof and
  integration siblings do not inherit a source gate merely by sharing a round,
  and unrelated historical source reviews remain provenance rather than live
  capability.
- Explicit head replacement transfers the named old head's context without
  guessing a successor. Repeating the same `plan-repair-round` request returns
  the canonical existing non-aborted round instead of duplicating work.
- Campaign context storage has no numeric quota, and Fact admission is off by
  default until the user explicitly requests a bounded Fact window.

These are coordination changes only. Chalxius does not infer mathematical
completion, select a research direction, dispatch work, rewrite Research, or
change package, verifier, Gateway, or Fact authority.

## Preserved boundaries

- The v1.0.5 split opt-in rule remains active: routine supervision and Fact
  packaging ignore splitting, while a new low-level split requires explicit
  current authorization.
- Campaign and frontier remain nontruth working memory.
- Installation remains the software-correctness boundary; publication reuses
  the exact installed bytes and checks only archive identity, checksum, file
  set, and absence of sensitive local data.

## Graph Browser status

Graph Browser and graphical graph generation remain temporarily unavailable
as supported release capabilities. Textual Research, exact search, Campaign,
frontier, supervision, COW, Fact packaging, verification, and certification
remain available.

## Validation

The exact manifest-bound candidate passed complete candidate and installed
self-tests, 83 focused lifecycle/frontier tests, installer regressions, atomic
installation, rollback preparation, and exact candidate-to-installed
comparison across all 271 manifest entries. Real-project canaries read 1,338
rounds and the bounded Campaign frontier without starting maintenance, Fact,
Candidate, verifier, Gateway, or admission work.

Full evidence and exact hashes are recorded in [VALIDATION.md](VALIDATION.md)
and `RELEASE.lock.json`.

## Distribution

Release assets:

- `chalxius-1.0.17-literal-input-continuity.tar.gz`
- `chalxius-1.0.17-literal-input-continuity.tar.gz.sha256`

```sh
shasum -a 256 -c chalxius-1.0.17-literal-input-continuity.tar.gz.sha256
tar -xzf chalxius-1.0.17-literal-input-continuity.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

Publication creates no mathematical Fact.
