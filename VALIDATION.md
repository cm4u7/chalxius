# Validation — Chalxius v0.8.0

This document records software, packaging, installation, and CHX evidence for
Chalxius 0.8.0 MathGraph First. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.8.0 |
| Release date | 2026-08-18 |
| Skill manifest entries | 253 |
| Manifest SHA-256 | ba4bb4854e0701e01c186ccea06b7bfb52311a40874799b6636718f61a3c84d7 |
| Runtime content SHA-256 | 7f951b3ef3dfd168ce91b2ed5a424af698a1601325ee0c79346fc054c3a63f84 |
| Installed runtime identity | 943a66bc9d5ec76f5622de5b13cfda800e26c349e8b210fb63d00eae16ba32da |
| Installed archive-tree SHA-256 | a85671c716eabd1249bc49f63238a6e18550b9f8afc517ed70399b423bddbfc9 |
| Archive | chalxius-0.8.0-mathgraph-first.tar.gz |
| Archive bytes | 2496311 |
| Archive members | 254 |
| Archive SHA-256 | 44f5badf9d20d0f871d278f24da2e46da668be8c821f2086c2bdd9538f629fca |
| Checksum-file SHA-256 | d41fdcc2e68afc7dce35ad639deb7ee11f6208b73d2c69665b2efefe9c6dd6b1 |

The archive was generated deterministically from the frozen runtime tree and
verified by a cold extraction.

## Routine release matrix

The receipt is chalxius-release-validation-matrix-6, SHA-256
6d9f8e04968c67888e9b140209c6486d669e93b341a5b1b154d70ea36bc79fda.
It binds the manifest
ba4bb4854e0701e01c186ccea06b7bfb52311a40874799b6636718f61a3c84d7 and
reports ok=true, source_unchanged=true, and one manifest identity.

| Lane | Result |
|---|---|
| Changed-surface tests | PASS; 28/28 |
| Semantic mutation profile | PASS; 15/15 |
| Bundled self-test | PASS |
| Strict architecture reconnaissance | PASS; 0 errors, 0 warnings |
| Graph/runtime lifecycle focus | PASS; 35/35 |
| Cold archive manifest check | PASS; 253/253 |
| Cache and bytecode check | PASS |

The semantic profile covers graph frontier and Fact authority, computation
truncation, source/adverse provenance, worker-return integrity, verifier
signatures, and Research continuity. It is a routine release profile, not a
claim that every historical mutation probe was rerun.

## Protected installation

| Field | Result |
|---|---|
| Cutover status | cutover_complete |
| Installed version | 0.8.0 |
| Installed runtime identity | 943a66bc9d5ec76f5622de5b13cfda800e26c349e8b210fb63d00eae16ba32da |
| Installed runtime content | 7f951b3ef3dfd168ce91b2ed5a424af698a1601325ee0c79346fc054c3a63f84 |
| Candidate-to-installed tree | exact manifest/content identity |
| Prior runtime identity | 82fe34deaf8d7d09899918e9507e1f0743d85fc4b0596c8cff80bdd246ff57de |
| Rollback | preserved as chalxius-prior-0.8.0 |
| System restart | not performed |

Graph smoke tests and the installed self-test passed after cutover. Runtime
identity and archive records are deployment diagnostics; they do not gate
ordinary graph reads or Research continuation.

## CHX disclosure and Research boundary

The canonical public CHX lineage remains CHX-001 through CHX-035. Current
release-run observations are private nontruth operational evidence and are not
distributed as a parallel issue namespace. Two valid unfinished worker returns
were retained as nontruth Research:

- round-20260816T094813Z-079a0e70;
- round-20260817T040553Z-d50b6f19.

No Candidate Release, Certification Decision, Gateway admission, or Fact was
created by this release. Hashes establish byte identity, tests establish
exercised behavior, and CHX/PHX records explain architecture operation only.
