# Validation — Chalxius v0.8.7

This document records software, packaging, installation, performance, and
global CHX-settlement evidence for **Chalxius 0.8.7 — Main Observation and CHX
Snapshot**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.8.7 |
| Release date | 2026-08-21 |
| Skill manifest entries | 256 |
| Manifest SHA-256 | `455628742109d5e7f7adb2a1a33ca8058cce0f47fe683dc7e68ce0ebf34c7b7f` |
| Runtime content SHA-256 | `adf87ef71e785a1a9188a6848c5bedf15e880f1dd15f985d2cff591ec56d73cf` |
| Installed runtime identity | `420ab20e1d633afe091154f7bb2a489b7746e52e8a43cccae82584e4aebaa755` |
| Installed archive-tree identity | `f4659ae08540bd4a98de7e58284a856f6caf94b1d16dd052464e87d6d395d69a` |
| Archive | `chalxius-0.8.7-main-observation-chx-snapshot.tar.gz` |
| Archive bytes | 2,536,984 |
| Archive members | 257 |
| Archive SHA-256 | `f749903fa86e0af558b44fd15b5fa7df6633f4a7859e6d61e97a521a97f5f65f` |
| Checksum-file SHA-256 | `4a45fbd9d06f8273658d38dcc09754b4641d171abf431dd629d4d4e22268557a` |

The archive was built twice from the exact frozen tree; the byte streams were
identical. A cold extraction passed all 256 manifest rows, the bundled
self-test, and strict architecture reconnaissance.

## Failure-informed release validation

The affected regression suite passed **162 tests in 9.300 s**. The isolated
release matrix used contract **chalxius-release-validation-matrix-6** and
receipt SHA-256
`db7179a16bf47144777c06fd471739d97cc4599da5201d0145f46c1a4a7e8f98`.
Every matrix lane used the same source tree and left it unchanged.

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.926 s |
| Changed-surface tests | PASS; 29/29 | 8.417 s |
| Semantic mutation profile | PASS; 15/15 | 33.593 s |
| Strict architecture reconnaissance | PASS; 257 files, 0 errors, 0 warnings | — |
| Candidate-to-installed comparison | PASS; 257/257 unchanged | — |
| Cold archive | PASS; manifest, self-test, reconnaissance | — |

The architecture inventory SHA-256 is
`f66134f39caed3fff6b9b4f2a1b009fd04d9aabafd721faaa0e8c4350c23712a`.
The candidate and installed reconnaissance receipt SHA-256 values are,
respectively,
`97e7bd2850a2c85662605ffa42a3db8ee35ca00a162ba6376598453ef9f49fa5`
and
`df33cda7a770b1ee3402c7308f0b4f32f4c5be2f3e1b05f329bf6e8aa677ffcf`.

Software checks establish exercised behavior only; they do not admit Research,
certify a Candidate, or establish a mathematical Fact.

## Main-visible performance evidence

All timings are local observations, not automatic timeouts, thresholds, or
cross-machine guarantees.

| Operation | Earlier observation | 0.8.7 observation |
|---|---:|---:|
| Five-target selective checkpoint | 82.9 s | 3.01 s |
| Exact supervision retry | 10–17 s | 1.63 s |
| Historical partial-supervisor replay | previously blocked | 2.40 s |
| Exact legacy source Research planning | previously rejected late | 1.22 s |

The earlier 0.8.6 local-F0 canaries remain relevant: Candidate Release 12.80 s
from about 91.7 s, verifier capsule 6.35 s from about 134 s, and host
materialization 6.72 s from about 210 s, with semantic ids unchanged.

Main is instructed to notice elapsed time already exposed by host command and
work-unit results. No timer, daemon, watcher, polling loop, scheduler,
persistent cache, performance index, receipt gate, or lifecycle state was
added.

## Installation

| Field | Result |
|---|---|
| Installer | default project-free local installer |
| Installed version | 0.8.7 |
| Candidate-to-installed tree | exact; 257/257 unchanged |
| Install receipt SHA-256 | `21a52d21b3222314cbd97ea2459648cc5be93213248135bb2e31d12b4dc3d11b` |
| Project reads/writes | 0 / 0 |
| Direct rollback | installation-before-final 0.8.7, identity `46317a46d0d1bdf6d18fdffbe7435a1ea90bd4fe214c969027bdd393e92f0e0c` |
| Preserved 0.8.6 archive | identity `dbf07dbaef568f50e473f0081d22a743382bc75a5e2d2c71b8790a10cf354ec8` |
| System restart | not performed |

Runtime identity and archives are deployment evidence only; they are not
graph-operation or Fact-authority gates.

## Global CHX settlement

After final installation, an owner-authorized copy-on-write global repair
superseded the stale settlement and bound the exact current inventory:

| Field | Result |
|---|---|
| Global repair | `global-repair-edddb03262efce8afadbeef701652c818f52eb2ea9c714b50c919ac6d64b45be` |
| Contract | `chalxius-chx-global-integrated-repair-3` |
| Canonical `record_sha256` | `dcaba853ee3206733b2bf671d1da2ba23c475d74d57433b1daf7fb7ed76b6b74` |
| Record-file bytes SHA-256 | `b38b89f4eacf2fa11522cad02f0f5e8ba3c595cadcc24fc30921faf5d3033235` |
| Settlement evidence receipt SHA-256 | `0ab8acc393e9f568cd299efe46ee0af23d4162a1e3d5eb00c432cd1373ce6235` |
| Inventory SHA-256 | `3c883ec1a9dcb43f70a1e939ed2f62972ece67912e960c84642bb22a1d88d265` |
| Covered snapshot SHA-256 | `7ffbe9ede34d7e5cc6261ad6f8cc8ac4211638551a3e42d8703ee9e6b69ef59b` |
| Observed / globally disposed | 156 / 156 |
| Resolved | 150 |
| Excluded nonarchitectural | 6 |
| Unresolved / uncovered | 0 / 0 |
| Lineage errors / report drift | 0 / 0 |

The six exclusions are deployment diagnostics, optional consultation features,
or host-orchestration preferences rather than graph-correctness defects.
Twenty-one historical ledgers retain an old open task flag, but
`active_open_issues` is zero; those flags are historical metadata, not liveness
or cleanup vetoes. The 601 historical ledger files were not rewritten.

Later mutation of any covered ledger makes this exact snapshot stale. That
fact-preserving rule is sufficient; no compatibility layer or additional
closure ritual was introduced.

## Research and truth boundary

The local-F0 research artifacts used for real replays remained read-only
fixtures. This architecture release created no Candidate Release,
Certification Decision, Gateway admission, or Fact.
