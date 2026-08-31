# Validation — Chalxius v1.0.9 Working Memory Maintenance

This report records software, installation, package, CHX-settlement, and
publication evidence. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 1.0.9 |
| Release date | 2026-08-31 |
| Manifest entries | 270 |
| Package files, including manifest | 271 |
| Manifest SHA-256 | `0685603076b1852df69ea2195e95067016c243b10ed88d73b6efd7bb9120e262` |
| Archive | `chalxius-1.0.9-working-memory-maintenance.tar.gz` |
| Archive bytes | 2,821,670 |
| Archive regular-file members | 271 |
| Archive SHA-256 | `1974d0b44eaa34df547cc9aff9715cd3bd76392b2bd5ca5acc9e28ecbca587d7` |
| Checksum-file SHA-256 | `446f5b759966d33795b428a5bb9f2142cd77a8edd7cb4140db30818dd6823b6a` |

Two independent archive builds were byte-identical. The archive contains only
the 271 sorted regular package files and no directory, symlink, cache, or
bytecode member.

## Correctness validation and installation

- focused working-memory, frontier, round, Campaign, Blackboard, release-
  identity, and adjacent regression lane: 150 passed;
- two supplementary lanes: 30 passed and 82 passed;
- installer self-test and focused regressions: PASS;
- manifest-bound archive, atomic swap, and rollback preparation: PASS;
- candidate-to-installed identity: exact at all 270 manifest entries; and
- project reads/writes performed by installation: 0/0.

The installed version is `1.0.9` with manifest
`0685603076b1852df69ea2195e95067016c243b10ed88d73b6efd7bb9120e262`.
The previous runtime remains available through the installer-managed rollback
archive.

## Behavioral coverage

The focused validation covers:

- bounded zero-argument round recovery with explicit full-history diagnostics;
- compact ordinary frontier projections with exact count/digest bindings and
  complete drill-down;
- additive head creation, exact disposition-bearing retirement, preservation
  of omitted co-heads, and detached-context recovery;
- Campaign maintenance-heartbeat phase skips and the absence of Fact,
  liveness, cancellation, or truth authority;
- ordinary V5 round creation without a default Blackboard snapshot, together
  with explicit Blackboard binding and historical replay; and
- deterministic, idempotent release-identity updating that fails before writes
  on invalid anchors or a dirty candidate tree.

## CHX integrated repair

After installation, the current global CHX record
`global-repair-20de5c2069446864a30ef0ce3270361ca435ae8ac12e571deb79dabcf523ef83`
verified as current. It covers all 266 observed issue identities, reports zero
uncovered issues and zero lineage/report drift, and has explicit `project_effect`
and `truth_effect` values of `none`.

## Publication scan

Publication reuses the already installed bytes. Its gate is limited to archive
identity, checksum sidecar, intended file set, and absence of credentials,
private keys, actual local usernames/paths, private runtime identifiers,
symlinks, caches, and bytecode. No mutation or forensic matrix is repeated as a
publication ceremony.

## Publication boundary

The annotated `v1.0.9` tag and GitHub release identify the archive above.
Installation, validation, Campaign coordination, CHX settlement, and
publication create no Research or Fact authority.
