# Chalxius v0.8.7 — Main Observation and CHX Snapshot

Chalxius 0.8.7 completes the PHX cleanup begun in 0.8.6. Main now observes
ordinary visible progress and end-to-end elapsed time, while the runtime removes
the repeated validation and procedural gates reproduced during continued
local-F0 research. No timer, daemon, watcher, persistent cache, compatibility
layer, scheduler, new lifecycle state, or truth gate was added.

The mathematical authority path remains:

**Research → Candidate Release → Certification Decision → Fact**

This release is cumulative from public 0.8.0 and includes all 0.8.1 through
0.8.7 changes.

## What changed

- Main directly notices command and work-unit elapsed time already visible from
  the host. Unexpected duration is a diagnostic signal, not an automatic
  timeout or acceptance threshold.
- A global CHX repair binds an exact current inventory even when historical
  task ledgers remain open. Open status is not treated as liveness or veto
  authority; later mutation of a covered ledger stales the snapshot.
- Independent Research with no Fact dependencies no longer reconstructs the
  unrelated active-Fact closure.
- Selective checkpoints share one ephemeral command-local inspection across
  explicitly selected targets.
- Exact supervision retry prefilters unrelated manifests and returns an
  existing source/component round before rebuilding planner Research.
- Proof-logic, program-math, and integration supervision project the production
  card, selected outputs, and active Fact premises without preloading
  source-only baseline bytes. Source-scope supervision retains the exact source
  closure.
- Exact project-relative path/SHA-256/role artifacts remain Research
  capabilities independently of a historical assurance label. No migration or
  compatibility successor is required.
- APFS/FileProvider mtime or ctime localization no longer overrides unchanged
  bytes and final SHA-256; containment, file identity, type, size, link policy,
  and hash checks remain exact.
- Worker contracts invoke the selected installation's executable
  `scripts/mgraph` shell entry instead of a guessed PATH alias or Python file.

## PHX boundary

The cleanup removes administrative expansion at the owner where it occurred.
It does not weaken source-byte validation, selected dependency closure,
Candidate adversity, verifier review, Gateway-owned Certification, Fact
admission, or mathematical correctness checks. Runtime/archive identities and
worker receipts remain useful diagnostic provenance, but are not graph
capabilities.

## Main-visible performance evidence

All timings below are local diagnostic observations, never thresholds or
cross-machine guarantees.

| Operation | Earlier observation | 0.8.7 observation |
|---|---:|---:|
| Five-target selective checkpoint | 82.9 s | 3.01 s |
| Exact supervision retry | 10–17 s | 1.63 s |
| Historical partial-supervisor replay | previously blocked | 2.40 s |
| Exact legacy source Research planning | previously rejected late | 1.22 s |

The earlier 0.8.6 local-F0 canaries also remain relevant: Candidate Release
12.80 s from about 91.7 s, verifier capsule 6.35 s from about 134 s, and host
materialization 6.72 s from about 210 s, with semantic ids unchanged.

## Validation

The frozen 256-entry manifest and 257-member archive passed:

- 162 affected-surface regressions in 9.300 s;
- release matrix contract `chalxius-release-validation-matrix-6`:
  self-test, 29 changed-surface tests, and 15 semantic mutants;
- strict architecture reconnaissance over 257 files with 0 errors and 0
  warnings;
- exact candidate-to-installed comparison with 257 unchanged files;
- deterministic double archive build, cold 256/256 manifest verification,
  cold self-test, and cold strict architecture reconnaissance.

The release-matrix receipt SHA-256 is
`db7179a16bf47144777c06fd471739d97cc4599da5201d0145f46c1a4a7e8f98`.
Software checks establish exercised behavior only; they do not certify a
mathematical claim.

## Installation

The exact validated tree is installed globally as 0.8.7 through the
project-free local installer.

| Item | SHA-256 or value |
|---|---|
| Manifest | `455628742109d5e7f7adb2a1a33ca8058cce0f47fe683dc7e68ce0ebf34c7b7f` |
| Runtime content | `adf87ef71e785a1a9188a6848c5bedf15e880f1dd15f985d2cff591ec56d73cf` |
| Installed runtime identity | `420ab20e1d633afe091154f7bb2a489b7746e52e8a43cccae82584e4aebaa755` |
| Installed archive-tree identity | `f4659ae08540bd4a98de7e58284a856f6caf94b1d16dd052464e87d6d395d69a` |
| Direct rollback | installation-before-final 0.8.7, identity `46317a46d0d1bdf6d18fdffbe7435a1ea90bd4fe214c969027bdd393e92f0e0c` |
| Preserved 0.8.6 archive | identity `dbf07dbaef568f50e473f0081d22a743382bc75a5e2d2c71b8790a10cf354ec8` |

Installation read and wrote no research project and required no restart.

## CHX settlement

After final installation, one copy-on-write global repair superseded the stale
0.7.16 settlement and covered all 156 observed qualified CHX issues:

- 150 `resolved`;
- 6 `excluded_nonarchitectural` because they were deployment diagnostics,
  optional consultation features, or host-orchestration preferences rather
  than graph-correctness defects;
- 0 unresolved and 0 uncovered;
- 0 lineage errors and 0 report drift.

The current record is
`global-repair-edddb03262efce8afadbeef701652c818f52eb2ea9c714b50c919ac6d64b45be`,
with canonical `record_sha256`
`dcaba853ee3206733b2bf671d1da2ba23c475d74d57433b1daf7fb7ed76b6b74`
and complete-file SHA-256
`b38b89f4eacf2fa11522cad02f0f5e8ba3c595cadcc24fc30921faf5d3033235`.
Twenty-one historical ledgers retain their old open task flag, but own no
current unresolved issue and have no cleanup veto. Historical ledger bytes were
not rewritten.

## Public distribution

Release assets:

- `chalxius-0.8.7-main-observation-chx-snapshot.tar.gz`
- `chalxius-0.8.7-main-observation-chx-snapshot.tar.gz.sha256`

The deterministic archive has 257 members, 2,536,984 bytes, and SHA-256
`f749903fa86e0af558b44fd15b5fa7df6633f4a7859e6d61e97a521a97f5f65f`.

To verify:

```sh
shasum -a 256 -c chalxius-0.8.7-main-observation-chx-snapshot.tar.gz.sha256
tar -xzf chalxius-0.8.7-main-observation-chx-snapshot.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/self_test.py
```

This architecture release created no Candidate Release, Certification Decision,
Gateway admission, or Fact.
