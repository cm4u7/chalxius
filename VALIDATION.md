# Validation — Chalxius v0.8.6

This document records software, packaging, installation, and performance
evidence for Chalxius 0.8.6 Bounded PHX Repair. It does not certify a
mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.8.6 |
| Release date | 2026-08-21 |
| Skill manifest entries | 256 |
| Manifest SHA-256 | 0afb65d4259b80cf6ab59596a4e95bc417335053d4d96e014ac786efd4f92088 |
| Runtime content SHA-256 | 8e30d9bc55f6524ddc48212aa04c639fde213d44173087121d734239af6e649d |
| Installed runtime identity | 1cafa6ae3a68fcc10fbc0b7e43a4435e936371be1ce18ff1d896f1ed8fed480c |
| Installed archive-tree SHA-256 | 5b565098279eb5f6bd7731624e271fc3a45076acc43070b55b3fd1d68fd6c85b |
| Archive | chalxius-0.8.6-bounded-phx-repair.tar.gz |
| Archive bytes | 2527296 |
| Archive members | 257 |
| Archive SHA-256 | a8507d2b8b7c1293e9ee37a7b35530359bf9d1644ed491e3e0fc2d7430ce6c56 |
| Checksum-file SHA-256 | 9cbfbc39185e318e6171a9cfdb235912dc77a94942e994576f34eb0865248723 |

The archive was built twice from the exact frozen tree; the byte streams were
identical. A cold extraction passed all 256 manifest rows and the bundled
self-test.

## Failure-informed release validation

The routine matrix used contract
**chalxius-release-validation-matrix-6** and receipt SHA-256
**fa27cfa0f3d244ecd407f55dfd6ee446940ac20fc25389de8a6926864001df18**.
Every lane used the same manifest and left its isolated tree unchanged.

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.953 s |
| Changed-surface tests | PASS; 29/29 | 8.478 s |
| Semantic mutation profile | PASS; 15/15 | 31.595 s |
| Repair-focused regressions | PASS; 175/175 | 18.906 s |
| Behavioral feature gate | PASS; 40 features, 102 probes | bounded |
| Strict architecture reconnaissance | PASS; 0 errors, 0 warnings | bounded |

The behavior-gate receipt SHA-256 is
**dab8f056c3d3b129d8ce3d442461ebfd7bceba63f26ff5c56e406a025061d962**.
The architecture inventory SHA-256 is
**dadbbe8fe1eb7dc19923f8f67124cea40b516d9c14e560cc675a09685d10356c**.
The reconnaissance compared the candidate and installed tree as 257 unchanged
entries.

The full historical mutation registry was not rerun. The PHX-selected routine
surface covered the changed Candidate, return-ingest, CLI, capsule,
installation, and mutation-registry mechanisms without turning a forensic
profile into a routine gate.

## Main-visible performance evidence

The same frozen local-F0 release was used for all measurements:

- release: release-fcb3aba2ab09835d8109a45352f956865e694e9f3f49d92bb50fa808d8acd052
- capsule: capsule-00e44d13be18de1cf103b9379992df3fe178209551c8dddc907e3819fbd89725

| Operation | Prior observation | 0.8.6 observation |
|---|---:|---:|
| Successful Candidate Release path | ~91.7 s | 12.80 s |
| Public verifier capsule | ~134 s | 6.35 s |
| Host capsule materialization | ~210 s | 6.72 s |

The ids remained identical. These timings are diagnostic observations on one
machine and project, not acceptance thresholds. No timer, daemon, heartbeat,
watcher, cache authority, or persistent performance index was added.

## Installation

| Field | Result |
|---|---|
| Installer | default project-free local installer |
| Installed version | 0.8.6 |
| Candidate-to-installed tree | exact |
| Project reads/writes | 0 / 0 |
| 0.8.5 runtime | preserved in the content-addressed archive |
| Direct rollback | available |
| System restart | not performed |

The installed self-test and 175 focused regressions passed after cutover.
Runtime identity and archives are deployment evidence only; they are not graph
operation or Fact-authority gates.

## CHX and Research boundary

The public historical CHX lineage remains CHX-001 through CHX-035. Current
project-scoped ledgers were not copied into the package. A global historical
repair record is not claimed because foreign task ledgers are still open and
must be closed by their owners.

The existing local-F0 Candidate and capsule were read only as performance
fixtures. This architecture release created no Candidate Release,
Certification Decision, Gateway admission, or Fact.
