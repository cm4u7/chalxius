# Chalxius v0.7.16 - Bounded Capability Hygiene

Chalxius 0.7.16 hardens the runtime boundaries exercised by long-running
Research, installation, and project-wide CHX repair. It keeps the V5 truth
path, two-subround Research model, historical runtime compatibility, and
public CHX disclosure contract unchanged.

## Bounded capability handling

- Schema-v2 Repair metadata and task-card capability lineage use one shared
  exact validator. One command-local, digest-keyed snapshot may reuse immutable
  bytes within a read phase, subject to a 64 MiB aggregate cap.
- Every mutation boundary discards that snapshot. Publication and other
  authority-changing writes repeat fresh no-follow identity checks under the
  existing lock; no persistent authority cache is introduced.
- A validated terminal worker bundle is the sole post-ingest authority.
  Mutable source paths become diagnostic after sealing, and exact retries do
  not create a second worker state machine.
- Prospective textual worker artifacts reject unsafe C0 control bytes. Binary
  roles and already frozen 0.7.15 cards retain their existing interpretation.
- Public Python entrypoints suppress bytecode before local imports. Read-only
  Fact search and CHX inventory do not create writable locks or runtime cache
  files.

## Efficient read and lifecycle projections

- Fact search validates one fresh active-Fact authority projection and reuses
  it across hits in the same read-only command instead of replaying the full
  lineage once per result.
- Project CHX inventory represents fully closed parallel successor subtrees as
  separate RUN_ID-qualified chains. Active, missing, drifted, cyclic, unsafe,
  or competing-supersedes branches remain fail-closed.
- The user-directed project-wide global repair covers all 122 observed
  qualified issues against the exact 0.7.16 manifest, with zero uncovered
  issues at freeze time. The record is private project evidence and is not
  included in the public archive.
- The canonical public disclosure remains CHX-001 through CHX-035. Private
  run-local numbering after that boundary does not extend or renumber the
  public lineage.

These changes add no scheduler, watcher, persistent validation cache, new
Candidate gate, verifier substitution, Certification shortcut, Gateway route,
or Fact authority.

## Validation and installation

The exact 253-entry manifest passed the six-lane release matrix:

- strict architecture reconnaissance;
- mutation-registry preflight with 145 exact single targets;
- the behavioral feature gate;
- the full discovered suite with 942 passing tests;
- the bundled self-test; and
- aggressive audit with 145/145 registered mutants killed.

The protected cutover used an earlier successful same-manifest matrix receipt,
SHA-256
`481ad4431c274d93741dca209cace3cb113092d1749778d6f15de2edb3a004a1`.
The later publication-final rerun used the same manifest and produced receipt
SHA-256
`372e9b0baadd0b0b1e775951de72986ca05f5c4ee88b89e91d5fcaac1d89ca82`.
This distinction preserves the exact evidence used for installation while
identifying the newest validation run.

The deterministic USTAR archive contains 254 members, was reproduced
byte-for-byte, and has SHA-256
`e1091efb2601738879515af860c3bf8dc331626cac5805b4247eaaaf906eab6c`.
A fresh extraction passed all 253 manifest hashes, self-test, the standard
skill quick validator, and the no-`__pycache__`/`.pyc` check. PyYAML 6.0.3 was
available to the quick validator.

The exact candidate is globally installed as version 0.7.16 with runtime
content SHA-256
`ab6a31b541e6d2e85d6c4471f857ccbb5662aaf49030a320be3229faad3c2f1d`
and installed runtime identity
`fa48d02e07f878d81a3be985310269d5d5419a42a10decf82a65f5305e52dd8b`.
The 0.7.15 runtime remains available for rollback. No system restart was
performed.

Exact receipts and hashes are recorded in [VALIDATION.md](VALIDATION.md) and
[RELEASE.lock.json](RELEASE.lock.json).

## Install

Download adjacent release assets:

- `chalxius-0.7.16-bounded-capability-hygiene.tar.gz`
- `chalxius-0.7.16-bounded-capability-hygiene.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.7.16-bounded-capability-hygiene.tar.gz.sha256
tar -xzf chalxius-0.7.16-bounded-capability-hygiene.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/self_test.py
```

Replacing an active global runtime is a protected cutover operation. Do not
copy files over a runtime that owns frozen task cards.

## Claim scope

Hashes establish byte identity. Tests establish exercised software behavior.
Mutation results establish detection of enumerated faults. CHX and PHX records
remain nontruth operational evidence. None of these receipts proves a
mathematical theorem or substitutes for fresh independent verification,
Certification, Gateway admission, or Fact admission.
