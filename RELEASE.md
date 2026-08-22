# Chalxius v0.8.8 — Direct Graph Operations

Chalxius 0.8.8 removes two remaining procedural detours from ordinary
Research. Exact graph capabilities can now be used directly: a bounded
Research operation validates the admitted Fact premises it actually names, and
a worker may bind an exact primary source already frozen in its task card
without returning a second copy of the same bytes.

The mathematical authority path is unchanged:

**Research → Candidate Release → Certification Decision → Fact**

## What changed

### Exact Fact premises are local operations

Ordinary Research and ordinary task-authority snapshots now resolve each
explicitly referenced admitted Fact directly. They no longer replay every
active-Fact admission and historical Research round merely to validate a small
premise set.

Broad reconstruction remains available where it is semantically requested:
explicit Fact-closure reconstruction and exact attack targets still receive
their complete authority checks.

### Primary sources no longer require duplicate return bytes

A source-use binding is valid when its SHA-256 identifies either:

- a source artifact returned by the worker; or
- an exact primary source frozen in the task card.

This is one semantic source-capability rule, not a version branch or
compatibility adapter. Existing returned-source bindings remain valid.
Toy-check outputs, computation bridges, and other derived artifacts remain
bound to their own returned bytes.

### The public README is a product page again

The repository README was rebuilt around the first-time reader: value,
one-prompt start, live graph, authority model, installation, and a short
documentation map. The previous 609-line mixture of command encyclopedia,
version history, and internal architecture notes was reduced to 226 lines;
detailed contracts remain in their owning documents.

## PHX boundary

The repair removes work that was caused by procedure rather than mathematical
meaning. It adds no compatibility layer, persistent cache, migration ceremony,
timer, monitor, scheduler, receipt gate, or lifecycle state.

Source-byte identity, explicit Fact-closure reconstruction, Candidate
adversity, fresh verification, Certification, Gateway admission, revocation,
and mathematical correctness checks remain at the boundaries that own them.

## Validation

The frozen 257-entry manifest passed:

- the complete suite: 972 tests in 83.446 seconds, with 2 skipped;
- the isolated release matrix:
  - self-test PASS in 0.920 seconds;
  - changed-surface tests 29/29 PASS in 8.459 seconds;
  - semantic mutants 15/15 detected in 33.265 seconds;
- strict candidate and installed architecture reconnaissance with 0 errors and
  0 warnings;
- exact candidate-to-installed comparison;
- a real historical canonical worker return under the new source rule;
- a direct task-card primary-source return with no duplicate source artifact;
- a two-Fact Research authority projection in 0.002910 seconds, containing
  exactly the two requested Fact ids and no broad active projection;
- deterministic double archive construction and cold manifest, self-test,
  architecture, and source-tree verification.

These are software and workflow checks. They do not certify a mathematical
claim.

## Installation

The validated tree is installed globally as 0.8.8.

| Item | SHA-256 or value |
|---|---|
| Manifest | `938373dda29ca5c151cc469be8c7fe2a7b1d1d45bcd879533b8c89f20d15c917` |
| Runtime content | `635a2a9c0ef96c5f247e313a85b240a9f418162f0b04458795a6ad1016360b9f` |
| Installed runtime identity | `ebd626682653fad4c425a8386b214ec6f1baff8d04b016c9dc0b5545a573639c` |
| Installed archive-tree identity | `6ee68f87f728ea7426424575662915a276f0f74859ec04addea529bb2c01dc61` |
| Direct rollback | prior 0.8.7 identity `420ab20e1d633afe091154f7bb2a489b7746e52e8a43cccae82584e4aebaa755` |

Installation read and wrote no research project and required no restart.

## Global CHX settlement

After installation, a copy-on-write successor record covered all 159 observed
qualified CHX issues:

- 153 resolved;
- 6 excluded as nonarchitectural;
- 0 unresolved;
- 0 uncovered;
- 0 active open issues;
- 0 lineage errors or report drift.

The current record is
`global-repair-24cdfcf98bf77b60e93e699ae5adfbab6c02ea71471768e4009be0d7d2645b7c`.
Its canonical `record_sha256` is
`65834de2ede12abdfe3705492a4ef675fa9260c773268f6e2cac7609b156c19f`,
and the complete record file SHA-256 is
`71d26443d41c63e0241f807f1d6fbb5b9480f19726ff61547844f57ed7d2f995`.

Twenty-three historical task ledgers retain an old open flag but own no active
issue. Those flags are historical metadata, not liveness or cleanup vetoes.
No historical ledger bytes were rewritten.

## Public distribution

Release assets:

- `chalxius-0.8.8-direct-graph-operations.tar.gz`
- `chalxius-0.8.8-direct-graph-operations.tar.gz.sha256`

The archive contains 258 files plus directory entries, is 2,561,374 bytes, and
has SHA-256
`e253142d934af49fa7e7cf8b8de7c0cb4c1b6f5359248591a617911e1c001561`.

Verify it with:

```sh
shasum -a 256 -c chalxius-0.8.8-direct-graph-operations.tar.gz.sha256
tar -xzf chalxius-0.8.8-direct-graph-operations.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/self_test.py
```

This architecture release created no Candidate Release, Certification
Decision, Gateway admission, or Fact.
