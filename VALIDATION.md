# Validation — Chalxius v1.0.23 Research Selection Continuity

This report records software and distribution checks, not mathematical
certification.

## Frozen payload

| Field | Value |
| --- | --- |
| Version | 1.0.23 |
| Release date | 2026-09-05 |
| Manifest entries | 274 |
| Package files, including manifest | 275 |
| Manifest SHA-256 | `78b474b4c28c92f17b98f95829303a2a13e930ed6a17c96a2c8ba550d04deae3` |
| Archive | `chalxius-1.0.23-research-selection-continuity.tar.gz` |
| Archive bytes | 2887849 |
| Archive SHA-256 | `eae7f71af089c0b5c8e72e0282203292eebcbaa1d089e40eea34d0833d1c77ab` |
| Checksum-file SHA-256 | `91d98d38ae86cfc93935a99f2d5e85f289ec6b87d7a1c4cd664df78e5808ce93` |

The deterministic double build was byte-identical. Candidate, installation and
archive match at every file, including the manifest. The archive has only
regular files and no symlink, directory, cache or bytecode member.

## Installation-owned verification

- Exact selection and adjacent round-recovery lane: 84 tests, 5.100 seconds.
- Main's selection, proof-input, lifecycle, Campaign, installer and identity
  lane: 83 tests, 6.510 seconds.
- Final installer/identity lane: 13 tests, 1.257 seconds, including a complete
  copied candidate bumped to a different version without rewriting historical
  release prose.
- Candidate and installed self-tests: passed.
- Atomic installation and rollback preparation: passed.
- Project reads/writes by the installer: 0/0.

The test lanes overlap; their counts are not a count of unique tests. The
first installation attempt exposed a redundant version-prose check and stopped
before replacing the old runtime. That check was repaired and tested before the
successful final installation. No functional, manifest or formal-identity
check was bypassed.

## Installed real-project canaries

Exact selected-work history returned the expected previously ingested product
and later aborted duplicate, with no unreadable entries: 1309
output bytes in 5.466 seconds. Earlier isolated measurements
ranged from 2.207 to 3.389 seconds.

The Campaign frontier returned all four targets in 28816 bytes,
below its 32 KiB budget, in 5.675 seconds. No new mathematical
work, Fact work or maintenance completion was triggered. Timing is observed
evidence, not a constant-time guarantee.

## Distribution boundary

The final source/package scan covered 325 files and the
byte-identical archive. No current local-home, private-project, credential or
private-key matches remained. An already-public historical project label was
removed from the new payload; existing Git history was not rewritten.

Publication reuses installed bytes and checks archive identity, checksum,
file set and sensitive information. The optional mutation/forensic matrix
was not rerun merely to authorize publication.

The tagged payload is identified by
[v1.0.23](https://github.com/cm4u7/chalxius/releases/tag/v1.0.23).
GitHub's release asset metadata and accompanying checksum provide the public
distribution identity; no source commit hash is embedded into its own commit.
