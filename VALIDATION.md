# Validation — Chalxius v1.0.5 Split Opt-In Repair

This report records software, installation, package, real-project canary, and
publication evidence. It does not certify a mathematical claim.

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

The installed runtime passed a read-only canary on a large real project.
Dormant repairs were absent from the live decision surface while their original
history remained readable and unchanged. No project data or truth-authority
record was modified by installation or canary inspection.

The split authorization is one-shot: it is absent from Research, task cards,
receipts, frontier state, and replay arguments. Regular source/proof supervision,
mixed-product diagnosis, and ordinary one-to-one COW remain available.

## Publication scan

Publication uses the already installed bytes. Its gate is limited to exact
archive identity, checksum sidecar, repository file set, and absence of local
paths or sensitive data. The exact final archive and staged public diff were
scanned; no credential, private-key material, local username/path, or private
runtime identifier is included in the published package or release-facing
files. Synthetic fixtures and existing public traceability text were classified
as non-sensitive. Heavy mutation and forensic matrices were not repeated.

## Publication boundary

The `v1.0.5` annotated tag resolves to
`bb9f552180ac740740e3ef328cf64464ec298be9`. GitHub published the release at
`2026-08-30T17:22:54Z`:
<https://github.com/cm4u7/chalxius/releases/tag/v1.0.5>. Both uploaded asset
sizes and GitHub SHA-256 digests exactly match the frozen archive and sidecar.
Installation, validation, and publication create no Research or Fact authority.
