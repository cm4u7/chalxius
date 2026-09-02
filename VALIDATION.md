# Validation — Chalxius v1.0.17 Literal Input Continuity

This report records software, installation, package, real-project canary, and
publication evidence. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 1.0.17 |
| Release date | 2026-09-02 |
| Manifest entries | 271 |
| Package files, including manifest | 272 |
| Manifest SHA-256 | `d61410710ae9e2932f0d68a51bdbf03a399a465349bcccb68997af345ccd3db9` |
| Archive | `chalxius-1.0.17-literal-input-continuity.tar.gz` |
| Archive bytes | 2,843,995 |
| Archive regular-file members | 272 |
| Archive SHA-256 | `64c190e30d3f097cb93014e1f3b0d53257a23a528e67fd0aab5a35679bc907dd` |
| Checksum-file SHA-256 | `29a38338c4c8c755a9a64a32eff5ee83cd67a96dad0cf18cf264b930ef60bc4c` |

Two independent archive builds were byte-identical. The archive contains only
the 272 sorted regular package files and no directory, symlink, cache, or
bytecode member.

## Correctness validation and installation

- focused Campaign/frontier and lifecycle lane: 83 passed in 6.827 seconds;
- complete candidate and installed self-tests: PASS;
- installer-focused regressions and fast installation: PASS;
- manifest-bound atomic installation and rollback preparation: PASS;
- candidate-to-installed identity: exact at all 271 manifest entries; and
- project reads/writes performed by installation: 0/0.

The installed version is `1.0.17` with manifest
`d61410710ae9e2932f0d68a51bdbf03a399a465349bcccb68997af345ccd3db9`.
The previous runtime remains available through the installer-managed rollback
archive.

## Real-project canary

The installed zero-argument `round-status` read 1,338 rounds, reported zero
active and zero unreadable rounds, and deeply inspected five unresolved
candidates. A bounded `frontier --limit 1` retained all four Campaign targets
while expanding one goal-coverage row. The due maintenance advisory remained
visible and nonblocking. The canaries started no maintenance, Research, Fact,
Candidate, verifier, Gateway, or admission work.

## Publication scan

Publication reuses the installed bytes. The candidate and archive were checked
for exact file-set identity, checksum consistency, symlinks, caches, bytecode,
private-key headers, common credential-token forms, actual local usernames and
absolute home paths, and private runtime identifiers. The only path matches
were documented placeholders (`/Users/<user>` and `/Users/example`); true
positive sensitive findings were zero.

The optional mutation/forensic matrix is not a publication gate and was not
repeated. Publication creates no Research or mathematical Fact.
