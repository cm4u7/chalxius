# Validation — Chalxius v1.0.14 Durable Campaign Memory

This report records software, installation, package, real-project canary, and
publication evidence. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 1.0.14 |
| Release date | 2026-09-01 |
| Manifest entries | 271 |
| Package files, including manifest | 272 |
| Manifest SHA-256 | `a06ab417befa9d4236ee54f7f84fac99f54fcdeb6d5cfa6599b37ae09073acd4` |
| Archive | `chalxius-1.0.14-durable-campaign-memory.tar.gz` |
| Archive bytes | 2,836,880 |
| Archive regular-file members | 272 |
| Archive SHA-256 | `61155cacbad7372400eaa0dd5323c2f89960c82fe72018bfe7208ba63edc5e14` |
| Checksum-file SHA-256 | `0aa72a8fbeea0b72fea7a76d7c24a3531f30f4d7776ff4f45e8c7e7185baa8bc` |

Two independent archive builds were byte-identical. The archive contains only
the 272 sorted regular package files and no directory, symlink, cache, or
bytecode member.

## Correctness validation and installation

- changed-surface regression lane: 183 passed;
- two focused Campaign/frontier and lifecycle lanes: 66 passed and 58 passed;
- complete self-test and installer-focused regressions: PASS;
- manifest-bound atomic installation and rollback preparation: PASS;
- candidate-to-installed identity: exact at all 271 manifest entries; and
- project reads/writes performed by installation: 0/0.

The installed version is `1.0.14` with manifest
`a06ab417befa9d4236ee54f7f84fac99f54fcdeb6d5cfa6599b37ae09073acd4`.
The previous runtime remains available through the installer-managed rollback
archive.

## Real-project canary

The installed runtime read Campaign `campaign-62013035c1ff` at live frontier
generation 372 with 237 members. Three targets retained an exact Research as
both active head and historical landmark:

- `0c33384e6392`;
- `09a4a95ed69a`; and
- `1d8a1522c717`.

The canary changed no head, context, Research, verification, or Fact state. It
also reset the Campaign's nonblocking 50-minute maintenance clock through an
ordinary note update.

## Publication scan

Publication reuses the installed bytes. The candidate and archive were checked
for exact file-set identity, checksum consistency, symlinks, caches, bytecode,
private-key headers, common credential-token forms, actual local usernames and
absolute home paths, and private runtime identifiers. The only path matches
were documented placeholders (`/Users/<user>` and `/Users/example`); true
positive sensitive findings were zero.

The optional mutation/forensic matrix is not a publication gate and was not
repeated. Publication creates no Research or mathematical Fact.
