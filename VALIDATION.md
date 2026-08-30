# Validation — Chalxius v1.0.5 Split Opt-In Repair

This report records software, installation, package, live-project, CHX/PHX,
and publication evidence. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 1.0.5 |
| Release date | 2026-08-31 |
| Manifest entries | 269 |
| Package files, including manifest | 270 |
| Manifest SHA-256 | `f8f7cd04201b4f3761d16619b089a832e8f32348430f7882bcd26b07398a7508` |
| Archive | `chalxius-1.0.5-split-opt-in-repair.tar.gz` |
| Archive bytes | 2,794,846 |
| Archive regular-file members | 270 |
| Archive SHA-256 | `921c273825388199725d10ea0bbfc7bfb1186138de3e2b9b32fa7f42f5b71335` |
| Checksum-file SHA-256 | `5771e5bb04d14e4a88d8d930d13cc8fbb267b183d2e74125c1ffdd89ae7a58cd` |

Two independent archive builds were byte-identical. The archive contains only
the 270 sorted regular package files and no directory, cache, or bytecode
member.

## Correctness validation and installation

Correctness validation was completed before publication:

- full suite: 1,104 tests passed, 19 skipped;
- routine changed-surface lane: 164 tests passed;
- semantic mutation diagnostic: 32/32 selected mutations killed;
- installer dry run, installer self-test, focused split/frontier regressions,
  atomic swap, and rollback preparation: PASS;
- candidate-to-installed identity: exact at all 269 manifest entries; and
- project reads/writes performed by installation: 0/0.

The exact installed manifest is
`f8f7cd04201b4f3761d16619b089a832e8f32348430f7882bcd26b07398a7508`.
The archived 1.0.4 runtime remains available for direct rollback.

A separate forensic diagnostic also passed architecture, behavior, full-suite,
self-test, and 144/144 preflight checks. One historical mutation-harness
self-test mutation survived inside the diagnostic harness; it did not alter the
candidate, installed identity, changed surface, or release decision. This lane
is intentionally diagnostic, not a publication gate.

## Live-project canary

The installed runtime read and reconciled the local-$\mathbb F_0$ project.
Campaign generation 194 reports both targets current and no stale head. The
three paused split ids are absent from target decision surfaces and the workflow
queue. Their original rounds and existing returns remain readable, unvalidated,
uningested, and unmodified. A completed negative branch was removed from active
work, while its Research history remains intact.

The split authorization is one-shot: it is absent from Research, task cards,
receipts, frontier state, and replay arguments. Regular source/proof supervision,
mixed-product diagnosis, and ordinary one-to-one COW remain available.

## Publication scan

Publication uses the already installed bytes. Its gate is limited to exact
archive identity, checksum sidecar, repository file set, and absence of local
paths or sensitive data. The exact final archive and staged public diff were
scanned; no credential, private-key material, local username/path, private
Campaign id, or current ledger id is included in the published package or
release-facing files. Three classified matches remain: two visibly synthetic
fixture ids and one historical project label already present in public release
traceability. None contains a secret or local path. Heavy mutation and forensic
matrices were not repeated.

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-15192f1156b72b5563a45c2f58d3b439fec41c8c6bf46c5b13d5d1ef9353d447` |
| Canonical `record_sha256` | `cd6520c035467a77d7e48ab82197661e9c56acba7870fd5ad4f33a36fc7449ef` |
| Record-file SHA-256 | `955a7ab9a51732475616d4e24af77e9df7681a760721506ddf7f6401b899597f` |
| Inventory SHA-256 | `64b78dd78fbec944fb16e0f7bc384841ae05e7bdc4c2fc77918b21f68721d655` |
| Covered snapshot SHA-256 | `01235b486fb3134ff4636544d1a29bd6172c00b068c9f6a999b7717379ad16dd` |
| Observed / covered | 258 / 258 |
| Revalidated prior / newly fixed | 257 / 1 |
| Uncovered | 0 |

Historical ledger bytes were not rewritten. The current exact installed
manifest covers every qualified observation in the terminal inventory.

## PHX adoption

The explicit split opt-in route is adopted as
`adoption-01787a30b6bc8dacd56fcd78eb7647bd3f6845ea5926453f3f262f32333e01ff`
from supported measurement
`measurement-e957a3effa813e5b846b35c6c8294b4d657ad1886b93ef9f04b3cfb6351728ab`.
It introduces no scheduler, inferred authorization, compatibility layer,
second lifecycle, project effect, or truth effect.

## Publication boundary

The prepared annotated tag is `v1.0.5`; the release endpoint is
<https://github.com/cm4u7/chalxius/releases/tag/v1.0.5>. The exact remote commit,
time, and asset confirmation are recorded on `main` after publication.
Installation, validation, CHX/PHX settlement, and publication create no Research
or Fact authority.
