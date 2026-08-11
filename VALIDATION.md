# Validation — Chalxius v0.7.3

## Frozen release identity

| Field | Exact value |
|---|---|
| Version | `0.7.3` |
| Display name | `Selective Startup` |
| Release date | `2026-08-12` |
| Skill manifest entries | `245` |
| `MANIFEST.sha256` SHA-256 | `191f1880b01c2f7bed75bdc3a246f66e59cd9475fb12d02a708e08c08305e11c` |
| Runtime content SHA-256 | `7ecc27da8c6407ccf6171a1d4a19c2c38484bd2e899a65d1628c79c22802e78d` |
| Archive | `chalxius-0.7.3-selective-startup.tar.gz` |
| Archive bytes | `2366343` |
| Archive members | `246` |
| Archive SHA-256 | `0ad47e0cbb4339ccbd17e8b8011aa939db0d7b47da89a1ee8735aaeee5d8c69e` |

The archive builder independently produced the archive twice and required
byte-for-byte equality. It also required the archive member set to equal the
sorted manifest plus `MANIFEST.sha256`, with fixed ownership, modes, and mtime.

## Final manifest-bound matrix

The accepted receipt uses contract
`chalxius-release-validation-matrix-4`, contains all six required lanes, and
records `one_manifest_identity=true`, `source_unchanged=true`, and
`lane_unchanged=true` for every lane.

| Phase | Lane | Result |
|---|---|---|
| 1 | strict architecture reconnaissance | pass; 246 files; 0 errors, warnings, or orphan modules/features |
| 1 | mutation-registry preflight | `148/148` exact single targets |
| 2 | behavioral feature gate | pass; `30` registered features |
| 3 | full suite | `844/844` pass |
| 3 | bundled self-test | pass |
| 4 | aggressive mutation audit | `148/148` mutants killed; candidate unchanged |

The snapshot-sensitive mutation audit ran only after baseline phases. Any
architecture or registry-preflight failure would have short-circuited the
expensive lanes.

| Receipt or inventory | SHA-256 |
|---|---|
| Final matrix receipt | `6ce9a0d63345363807790d7d8e4b9c7a9aae26805f69eaacad05f9fc79e922ea` |
| Final architecture inventory | `eea2500513027ca37e5c6933455786fb3b81d5be2c3a5c08786ffb668acb766c` |
| Architecture receipt bytes | `15f7542e42c55cc71b945beb0bbf2a2aa53843f35244b3017a7f63f822b77f80` |
| Behavioral registry | `54a52af2ba33c070b9cda787faf47c38d3d89e240a6026c12fa90ab0149b455d` |

## Focused 0.7.3 regression evidence

- The compact root router is 242 lines and current Research roles load one
  card-selected bootstrap instead of the broad historical protocol stack.
- An exact Research projection completed in 1.67 seconds in the reproduced
  workload; the historical full-frontier route exceeded 154 seconds before it
  was stopped.
- A document-editing Chalxius Learner task uses the dedicated bounded bootstrap
  and does not preload Research, Candidate, verifier, CHX-repair, or PHX
  protocols unless a later event requires them.
- Repair mode survives abort and replan; stale dispositions fail before
  expensive design reconstruction and are checked again under the final write
  lock.
- One-off computations and unsupported negative source-status claims can be
  eliminated before high-cost pipeline construction while preserving the
  mathematical and source-reliability boundaries.
- CHX public disclosure includes every issue from CHX-001 through CHX-020,
  including explicit ownership of `excluded_nonarchitectural` CHX-010.

## Cold extraction

A fresh extraction of the release archive passed:

- `245/245` manifest hashes;
- bundled `scripts/self_test.py`;
- no `__pycache__`, `.pyc`, or `.pyo` files.

## Protected installation

The final candidate was installed through `runtime_cutover.py` using an exact
project-validation receipt. One fresh deep audit of the protected project ran
under the candidate before cutover. Dry-run and post-swap checks reused that
immutable snapshot rather than repeating semantic reconstruction.

| Field | Exact value |
|---|---|
| Project validation receipt | `833c6a1de7c35086abfaa61403b8ddef2ddfa3c1d75e33c0e6292ec1c5b0f9bb` |
| Installed runtime identity | `32689d62b09bc1fc12f5006c9c658252abd82d0fb790400444df8e363389f8fe` |
| Project state SHA-256 | `e3eb579b62dc1cb0d087c1e5da8fca1139bfde3f7f9b6794505a2bb8c2b1e436` |
| Historical Research rounds | `125`, all terminal |
| Deep audits performed for cutover | `1` |
| Duplicate post-swap semantic audits | `0` |

The installed tree reports version `0.7.3`, exact manifest SHA-256
`191f1880...e11c`, passes its bundled self-test, and returns
`current_ok=true` on the protected project. The prior 0.7.2 runtime is retained
at `chalxius-rollback-0.7.2-pre-0.7.3-20260812`.

## Contract hashes

| Contract | SHA-256 |
|---|---|
| `INHERITANCE.lock.json` | `2dd254b2aa8cf5274f0774a385eeb69e62d0aa91e94007b85c3551c46d38aee1` |
| `KNOWN_LIMITATIONS.md` | `3db7bd72fc5d868097376565849d291c49f42bdfd30ff16eee73ba4940c29fcd` |
| `references/v5_release_traceability.md` | `870125deb04ef2da3a6769791f9df658ef8557bbfdbe0bc39a9369672987b20b` |
| `SKILL.md` | `3542efa1baf0af7f40ed85a9fd4620a1f3bcfa0b8aa9f0f7a56f508a160f16b7` |
| `scripts/aggressive_bug_audit.py` | `6738ef4812967dad44a78938706a11e9009f125a942993bb945743ef4fe0c4ce` |
| `scripts/chx_ledger.py` | `32bcf8572688e6af0fa1bf6437583dcb2d2bb1137f544726711bbe3d0ff8eb6c` |
| `scripts/mathgraph/v5_lifecycle.py` | `4eef06ddb6fe71e1f5af890e0c6a2f6f7adb8324aed08a9c9eb7d663aa9aaf53` |

## CHX disclosure boundary

The release binds four immutable ledgers and explicitly enumerates CHX-001
through CHX-020. The latest ledger SHA-256 is
`04eb473a6360c49fcf806de6b737c529f47ab91d63c7e1aa8adfb966bdc1acd4`;
its generated architecture report SHA-256 is
`0821ffbdc7bc2a5548fa6a9ba6628ad8f0d6c8509ac57c3453b4536231671e7b`.
Private JSONL and Research bytes are not distributed. Public disclosure passed
the exact owner, predecessor, document, issue-enumeration, exclusion-status,
and ledger-hash checks.

## Claim scope

Hashes establish byte identity. Tests establish only exercised properties.
Mutation scores establish only detection of enumerated faults. None of these
receipts substitutes for fresh independent verification, Certification, or
Fact admission.
