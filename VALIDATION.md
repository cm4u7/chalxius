# Validation — Chalxius v0.8.12

This document records software, packaging, installation, semantic-recovery
behavior, and global CHX settlement for **Chalxius 0.8.12 — Semantic
Recovery**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.8.12 |
| Release date | 2026-08-24 |
| Skill manifest entries | 262 |
| Package files, including manifest | 263 |
| Manifest SHA-256 | `e47bdaeac15cfa1381264b04c9854fb99905a0dd2b863c6bb038f01841c82e77` |
| Runtime content SHA-256 | `ffb00b70da8035ff7939aef3a8050dbcd41492249398ac7a2fc3f4f6de233c03` |
| Installed runtime identity | `c0cdc2075fb6ac5a1b2d6c92da20a47dfdd37e806d47ec05b65d28ef968ca379` |
| Installed archive-tree identity | `d1250a57b007308853574ef6f7d5f1c91435754d4e31f1cf3ca68d092e9a675e` |
| Archive | `chalxius-0.8.12-semantic-recovery.tar.gz` |
| Archive bytes | 2,581,988 |
| Archive regular-file members | 263 |
| Archive directory members | 0 |
| Archive SHA-256 | `8e93c0d6fb165c6c8e38a3925a17b6051dd0d05be9842307bf77db2a9773142a` |
| Checksum-file SHA-256 | `2156f3c15ee596c13be438df98e623881a5dfe2b42515c20e4e57b82a8369f3f` |

Two builds from the same frozen tree were byte-identical. A cold extraction
matched the source tree and passed every manifest row, the bundled self-test,
and strict architecture reconnaissance.

## Complete and failure-informed validation

The complete suite passed **995 tests in 78.691 seconds**, with 2 skipped.

The forensic matrix receipt is
`/private/tmp/chalxius-0812-release.Cequm5/release-validation-forensic.json`
with file SHA-256
`db0b7029f149f697dea0b223d29837b1d214f25939363856b0ba685c6af27ff4`.

| Forensic lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.989 s |
| Full suite | PASS; 995 tests, 2 skipped | 94.002 s |
| Mutant registry preflight | PASS; 139/139 | 0.118 s |
| Full mutation audit | PASS; 139/139 killed | 183.840 s |
| Behavioral feature gate | PASS; 42 features, 0 orphans | 21.558 s |
| Strict architecture scan | PASS; 0 errors, 0 warnings | 5.437 s |

The final routine matrix receipt is
`/private/tmp/chalxius-0812-release.Cequm5/release-validation-routine-final.json`
with file SHA-256
`1db6e2628c2b60dfd9ebea368a73c5305a6268b23680f8cf95a73e06c9576882`.

| Routine lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.985 s |
| Changed-surface tests | PASS; 36/36 | 8.897 s |
| Semantic mutation audit | PASS; 21/21 killed | 38.924 s |

Every lane used manifest
`e47bdaeac15cfa1381264b04c9854fb99905a0dd2b863c6bb038f01841c82e77`
and reported an unchanged candidate source tree.

## Architecture reconnaissance

Strict reconnaissance found 263 files, 90 test files, and 76 Python modules,
with 0 errors, 0 warnings, and 0 orphans. The absolute root participates in the
inventory identity, so candidate, installed, and cold-extraction hashes
intentionally differ.

| Report | Inventory SHA-256 | File SHA-256 |
|---|---|---|
| Candidate | `5d4d62ad05a04a8f0cea904a0112a6af85191dbb44d078c2983e17b33a5c3bbd` | `0be1165d8de678b61a0aaecabbbd292ec0ff1e0acc618e02b248041267394c9a` |
| Installed | `2b99d999e00ae6e73dcd55606ead355909346feb9f6a3e0b138bf42b6767c48c` | `b2a4311c0503c28bded98b623e03f431216f70c36c43e30fdbdd00a3ffcf281a` |
| Cold archive | `bc76d4b7970516b77325d840034b7c74f64a38dd8fe6e84fdb7c80ddbbd84718` | `0c0b48bb23a14d5155df6b256bcd8465bfa3a6a8d67b25690ef2190874da290e` |

All 263 candidate and installed package files were byte-exact.

## Semantic-recovery regressions

The 0.8.12 tests establish the following fail-closed behavior:

- a unique, exact, multi-hop COW repair lineage can project completion back to
  the original Research identity;
- an unsafe terminal product or incomplete frozen obligations reopen the work;
- malformed lineage, multiple child repairs, or a cycle remains pending;
- a second active invalidator not covered by the repair prevents closure;
- the repair objective, relations, source product, and obligations must match
  the hash-bound normalized repair specification;
- distinct non-aborted products for one Research are ambiguous, while an
  identical retry publication of the same product is accepted;
- Main's authoritative documents independently preserve semantic selection,
  useful-slot, bounded-scout, and client-reconnect rules.

The mutation audit covers branch-ambiguity bypass, invalidator-exhaustion
weakening, repair-continuity bypass, original-identity projection bypass, and
prior-terminal-staleness bypass. All 21 semantic mutants were killed.

## Main and reconnect boundary

- Main owns cross-round/COW search, completion projection, duplicate exclusion,
  and final target selection.
- Workers may gather bounded evidence; they do not own final dispatch authority.
- Free slots are used for real independent work when it exists, never to satisfy
  a quota or create filler.
- Client reconnect is transport-only. Main inspects agent status, canonical
  return bytes, ingestion, and round state before resuming, and does not reclaim
  or duplicate live work solely from a reconnect banner.

No monitor, timer, scheduler, receipt requirement, reconnect gate,
compatibility layer, lifecycle state, or truth gate was added.

## Installation

| Field | Result |
|---|---|
| Installer | default project-free local installer |
| Installed version | 0.8.12 |
| Candidate-to-installed tree | exact; 263 files unchanged |
| Installed runtime identity | `c0cdc2075fb6ac5a1b2d6c92da20a47dfdd37e806d47ec05b65d28ef968ca379` |
| Installed runtime content | `ffb00b70da8035ff7939aef3a8050dbcd41492249398ac7a2fc3f4f6de233c03` |
| Installed archive-tree identity | `d1250a57b007308853574ef6f7d5f1c91435754d4e31f1cf3ca68d092e9a675e` |
| Candidate runtime identity | `025bfc65ce4826a8c5ffaae5c6adf7ca75855171c7fd6491940aa432a334e1df` |
| Cold runtime identity | `184357fa260a391fa2fea5cf141470cb10fde93b924f6b8896d8a1449fcb46d5` |
| Direct rollback | 0.8.11 content `de1d4a03ef94c0e47ed994b75493cc74504664fc4054a1d8c6809a0e2a4ebba9` |
| Project reads/writes | 0 / 0 |
| System restart | not performed |

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-c82951c65fad6ec03d324b330345ee770787ca504413dd3855ed49f4a99d02ed` |
| Canonical `record_sha256` | `d2ba32cb5d0d977f2cfdadee2ebe2d7363cf6544ab313d536d6d8409abc02e0b` |
| Record-file SHA-256 | `b81f0a80d344fa4266245ef0ad7fc95260813d4a98532129e8f6915932b0ed69` |
| Inventory SHA-256 | `d3c113fac745f35371f46b8ccbfb4f8d4fec31be4c24db50630b479b3f30d17f` |
| Covered snapshot SHA-256 | `381d12e827f01d2dab6ea69d258e60cc1a3a3f3aaff266295ba165f7a41770bf` |
| Observed / globally disposed | 170 / 170 |
| Resolved / excluded | 164 / 6 |
| Current mechanism groups | 3 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

The current task ledger is closed with SHA-256
`e2c1f43a965e89dfb6640395bd094df77837ced22f0198373269c72ff860e5c8`.
Its architecture-report SHA-256 is
`ca0e19ad3b60e2a0f9923a5b8767999298468e7a357dcfca6d35d00811dfc80e`.
It contains zero tactical and zero per-ledger integrated repairs. Historical
ledgers remain append-only and own no active issue.

## Research and truth boundary

The A-model Research campaign was paused after the final VQ proof-logic
supervision returned `challenge`: one artifact was not standalone because key
symbols were undefined, while the mathematical withdrawal was otherwise
correct. No third COW was started.

This architecture release created no Candidate Release, Certification
Decision, Gateway admission, or Fact. Installation and publication did not
mutate Research graph bytes.
