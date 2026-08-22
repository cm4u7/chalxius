# Validation — Chalxius v0.8.8

This document records software, packaging, installation, direct-operation
canaries, and global CHX-settlement evidence for **Chalxius 0.8.8 — Direct
Graph Operations**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.8.8 |
| Release date | 2026-08-22 |
| Skill manifest entries | 257 |
| Manifest SHA-256 | `938373dda29ca5c151cc469be8c7fe2a7b1d1d45bcd879533b8c89f20d15c917` |
| Runtime content SHA-256 | `635a2a9c0ef96c5f247e313a85b240a9f418162f0b04458795a6ad1016360b9f` |
| Installed runtime identity | `ebd626682653fad4c425a8386b214ec6f1baff8d04b016c9dc0b5545a573639c` |
| Installed archive-tree identity | `6ee68f87f728ea7426424575662915a276f0f74859ec04addea529bb2c01dc61` |
| Archive | `chalxius-0.8.8-direct-graph-operations.tar.gz` |
| Archive bytes | 2,561,374 |
| Archive file members | 258 |
| Archive total members | 267 |
| Archive SHA-256 | `e253142d934af49fa7e7cf8b8de7c0cb4c1b6f5359248591a617911e1c001561` |
| Checksum-file SHA-256 | `35355e6ae2c0601be0abe14a196ce9aefbf903fca8301dfd4dc2387b1d16cd64` |

The archive was built twice from the same frozen tree and the byte streams
were identical. A cold extraction matched the source tree and passed every
manifest row, the bundled self-test, and strict architecture reconnaissance.

## Complete and failure-informed validation

The complete test suite passed **972 tests in 83.446 seconds**, with 2 skipped.

The isolated release matrix used contract
`chalxius-release-validation-matrix-6` and receipt SHA-256
`5170e248e20b4f9cdbd8c51849990ed424ccf3ff3cb72af0328c825cb0d1281b`.
Every lane used the same source tree and left it unchanged.

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.920 s |
| Changed-surface tests | PASS; 29/29 | 8.459 s |
| Semantic mutation profile | PASS; 15/15 | 33.265 s |

Strict candidate reconnaissance covered 972 probe symbols, 209 commands, and
76 modules with 0 errors and 0 warnings. Its inventory and receipt SHA-256
values are:

- candidate inventory:
  `bf808d520cfb401c5971ad22711a4e489da7954a8119ee9ffcc241736f9c83ee`;
- candidate receipt:
  `e788dd6be4ca2de084c9a465c8ab9f70810d83c5540a46f0a4a414445a9d11e3`;
- installed inventory:
  `380ad3d73f25b5a0d0ddb824c639bb5f37ee24b7043d1df68ca0fe6667ab5be3`;
- installed receipt:
  `a70a77d42c53aab130804f239852fbfc75e3a9c2f211a84a988d8051b708ec0c`.

Candidate and installed inventories intentionally have different inventory
hashes because the absolute root is part of the report. Their 258 package files
were byte-exact.

## Direct-operation canaries

### Exact admitted-Fact projection

An existing Research node with two admitted Fact premises was inspected under
the installed 0.8.8 runtime.

| Field | Result |
|---|---|
| Research id | `5389dfa5dd2a` |
| Exact Fact ids | `8e96f0645e11f3c7`, `e95f6372df0906ec` |
| Elapsed | 0.002910 s |
| Broad active projection | false |
| Unrelated Fact or historical Research replay | none |

The elapsed time is a local diagnostic observation, not a threshold or
cross-machine guarantee.

### Source-capability union

The historical canonical return from
`round-20260821T175508Z-099b5554`,
assignment `a01-68a23dd34f7a-literature`, still validates. Its return SHA-256
is
`55f86564961233a9256519051689806d79c428c29369b02bd927e8e9823e3cd0`.

The same frozen task card also validated when its source-use binding named the
primary TeX SHA-256
`df1900c5a0d944a7e9f00eafaa72fe7df340fd7c271c44ccc28103672c99d548`
directly and no duplicate primary-source artifact was returned.

These two canaries jointly protect the intended union: old returned-source
bindings and direct frozen-primary bindings are both capabilities. Derived
toy-check and bridge bytes do not inherit this exception.

## Installation

| Field | Result |
|---|---|
| Installer | default project-free local installer |
| Installed version | 0.8.8 |
| Candidate-to-installed tree | exact; 258 files unchanged |
| Candidate runtime identity | `9628e481c136ee4bad6595b7268009f1b5ca76b5a5b3c866a7e9b445fdeefaca` |
| Installed runtime identity | `ebd626682653fad4c425a8386b214ec6f1baff8d04b016c9dc0b5545a573639c` |
| Runtime archive registry SHA-256 | `ddcbb9c4625fb6b5a73e1f53c7b8ad289ed47583a4fffb6caf7005d10bcd8ad6` |
| Project reads/writes | 0 / 0 |
| Direct rollback | prior 0.8.7 identity `420ab20e1d633afe091154f7bb2a489b7746e52e8a43cccae82584e4aebaa755` |
| System restart | not performed |

Runtime identity and archives are deployment evidence only. They are not
graph-operation or Fact-authority gates.

## Global CHX settlement

After final installation, one owner-authorized copy-on-write successor bound
the exact complete inventory:

| Field | Result |
|---|---|
| Global repair | `global-repair-24cdfcf98bf77b60e93e699ae5adfbab6c02ea71471768e4009be0d7d2645b7c` |
| Canonical `record_sha256` | `65834de2ede12abdfe3705492a4ef675fa9260c773268f6e2cac7609b156c19f` |
| Record-file SHA-256 | `71d26443d41c63e0241f807f1d6fbb5b9480f19726ff61547844f57ed7d2f995` |
| Settlement evidence SHA-256 | `cc441cdffebf67c0ef399cb54884eb88f00ef1150f282cb00b6f795a5bf6eb8d` |
| Inventory SHA-256 | `d6dc30f469fc67a84b76795ae85b073b6e0795f9f11622fed23c3c22ba320d1d` |
| Covered snapshot SHA-256 | `e1f998012a76469ffce10e28439e26ba44cc47a68507928b1f2a977af1519db7` |
| Observed / globally disposed | 159 / 159 |
| Resolved | 153 |
| Excluded nonarchitectural | 6 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

The six exclusions remain deployment diagnostics, optional consultation
features, or host-orchestration preferences rather than graph-correctness
defects. Twenty-three historical ledgers retain an old open task flag but own
no active issue; those flags are not liveness or cleanup vetoes.

The 159 issues were assigned exactly once across 18 mechanism groups. The three
issues added since 0.8.7 are covered by the direct exact-Fact projection and
source-capability-union repairs. No historical ledger bytes were rewritten.

## Research and truth boundary

The local-F0 artifacts used for the canaries remained read-only fixtures. This
architecture release created no Candidate Release, Certification Decision,
Gateway admission, or Fact.
