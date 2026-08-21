# Chalxius v0.8.6 — Bounded PHX Repair

Chalxius 0.8.6 removes several procedural and provenance couplings while
keeping mathematical correctness and Fact authority at their existing owners.
Main selects the load-bearing Research and exact canonical Candidate Fact;
planning creates cards but does not pretend to dispatch workers. Provenance
remains lineage rather than a capability gate.

This public release is cumulative from the prior public 0.8.0 release and
contains the 0.8.1 through 0.8.6 runtime changes.

## What changed

- **prepare-candidate-adverse-target** now takes a Main-selected Research id
  and exact project-relative canonical Fact. The Fact may be Main-authored.
  Every applicable completed supervision result is derived and bound; author,
  container, and worker provenance do not establish mathematical validity.
- Main must explicitly launch and confirm workers after planning. This is a
  visible operating instruction, not a scheduler, receipt, timer, watcher, or
  new lifecycle gate.
- A transient canonical-return ENOENT or ESTALE during one snapshot is
  retryable without false quarantine. Symlinks, unsafe objects, malformed
  bytes, schema errors, and hash drift still fail closed.
- Candidate and verifier commands reuse one command-local immutable inspection
  context. It never persists across commands or crosses the final mutation
  lock. Candidate collection first applies exact local identity projections,
  then fully validates only records that can affect the selected branch.
- Role-aware help exposes only the relevant command projection while runtime
  authorization remains unchanged. Verifiers return review bytes; Gateway
  exclusively owns **certification-record** and Fact admission.
- The semantic mutation registry was rebound to the current local projection.
  A refute assignment that returns an evidence outcome remains adverse and
  cannot disappear from a Candidate.

The truth path is unchanged:

**Research → Candidate Release → Certification Decision → Fact**

## Cumulative 0.8.x surface

- 0.8.1 scopes fresh Candidate adversity to explicitly selected constructive
  heads.
- 0.8.2 makes route invalidation exact and introduces the project-free local
  installer.
- 0.8.3 derives worker/Main handoff hashes from canonical return bytes.
- 0.8.4 interprets graph/source capability by semantic content rather than one
  historical field spelling.
- 0.8.5 terminalizes worker returns through immutable copy-on-write bundles.
- 0.8.6 applies the bounded PHX repair described above.

## Main-visible performance

The same local-F0 Candidate Release and verifier capsule were used before and
after the repair. Semantic ids remained unchanged.

| Operation | Prior | 0.8.6 |
|---|---:|---:|
| Candidate Release successful path | ~91.7 s | 12.80 s |
| Public verifier capsule | ~134 s | 6.35 s |
| Host capsule materialization | ~210 s | 6.72 s |

These are machine- and project-specific measurements, not fixed thresholds.
Chalxius adds no performance daemon or persistent timing state; Main observes
ordinary elapsed time and treats unexpectedly slow simple operations as a
diagnostic signal.

## Validation

The frozen 256-entry manifest and 257-member archive passed:

- routine release matrix: self-test, 29 changed-surface tests, and 15 semantic
  mutants;
- 175 repair-focused regressions;
- behavioral feature gate: 40 features and 102 probes;
- strict architecture reconnaissance: zero errors and zero warnings, with the
  candidate and installed trees identical;
- deterministic double archive build, cold 256/256 manifest verification, and
  cold self-test;
- cache and bytecode hygiene.

The routine matrix receipt SHA-256 is
**fa27cfa0f3d244ecd407f55dfd6ee446940ac20fc25389de8a6926864001df18**.
The software checks establish exercised runtime behavior; they do not certify
any mathematical claim.

## Installation

The exact validated tree is installed globally as version 0.8.6 through the
project-free local installer.

| Item | SHA-256 or value |
|---|---|
| Manifest | 0afb65d4259b80cf6ab59596a4e95bc417335053d4d96e014ac786efd4f92088 |
| Runtime content | 8e30d9bc55f6524ddc48212aa04c639fde213d44173087121d734239af6e649d |
| Installed runtime identity | 1cafa6ae3a68fcc10fbc0b7e43a4435e936371be1ce18ff1d896f1ed8fed480c |
| Installed archive-tree identity | 5b565098279eb5f6bd7731624e271fc3a45076acc43070b55b3fd1d68fd6c85b |
| 0.8.5 archive | preserved in the content-addressed runtime archive |

No project was read or written by installation, and no system restart was
performed.

## Public distribution

The release assets are:

- **chalxius-0.8.6-bounded-phx-repair.tar.gz**
- **chalxius-0.8.6-bounded-phx-repair.tar.gz.sha256**

The deterministic archive has 257 members, 2,527,296 bytes, and SHA-256
**a8507d2b8b7c1293e9ee37a7b35530359bf9d1644ed491e3e0fc2d7430ce6c56**.

To verify a downloaded archive:

    shasum -a 256 -c chalxius-0.8.6-bounded-phx-repair.tar.gz.sha256
    tar -xzf chalxius-0.8.6-bounded-phx-repair.tar.gz
    cd chalxius
    shasum -a 256 -c MANIFEST.sha256
    PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/self_test.py

## CHX and truth boundary

The published historical CHX disclosure remains CHX-001 through CHX-035.
Current project-scoped ledgers are not embedded in this software release, and a
new global historical-repair record is not claimed while foreign task ledgers
remain open. No Candidate Release, Certification Decision, Gateway admission,
or Fact was created by this architecture release.
