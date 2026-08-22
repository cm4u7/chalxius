# Validation — Chalxius v0.8.9

This document records software, packaging, installation, frontier canaries,
source-assurance checks, and global CHX settlement for **Chalxius 0.8.9 —
Frontier Reliability**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.8.9 |
| Release date | 2026-08-22 |
| Skill manifest entries | 259 |
| Manifest SHA-256 | `965ccfed438832c7b2a444a9f8f0feda945bc1d398d06b37bb9e8d5959953a18` |
| Runtime content SHA-256 | `2eda96ca13e29213f9286931e6e2fc63f8f0f490433df8c89947d4cf58c6ebb0` |
| Installed runtime identity | `bf28ce263151e1dfd4d44bda606a26d86dbbb8a80d4b0ad04c6ea2598eb5da87` |
| Installed archive-tree identity | `523701de695b18fa8b734a95d39ac3eb11f490c389f6c20519cc9d4013c7f872` |
| Archive | `chalxius-0.8.9-frontier-reliability.tar.gz` |
| Archive bytes | 2,563,947 |
| Archive file members | 260 |
| Archive total members | 269 |
| Archive SHA-256 | `883bb69d5660ad506082f4f88f223df7b66352f6c8ce3364b1be915ec93668a8` |
| Checksum-file SHA-256 | `ad851db773073084124a18abd42b464e16cdfe08ed6b786e9b5b2f5470419f83` |

Two builds from the same frozen tree were byte-identical. A cold extraction
matched the source tree and passed every manifest row, the bundled self-test,
and strict architecture reconnaissance.

## Complete and failure-informed validation

The complete test suite passed **982 tests in 98.873 seconds**, with 2 skipped.

The final exact-manifest routine matrix used contract
`chalxius-release-validation-matrix-6`. Its receipt SHA-256 is
`c891c996615a37c587b939f046abdfdafe7a195f2887a0aa268965923c62cafc`;
all lanes used manifest `965ccf…3a18` and left the source unchanged.

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.879 s |
| Changed-surface tests | PASS; 29/29 | 8.182 s |
| Semantic mutation audit | PASS; 15/15 killed | 30.808 s |

The unchanged executable code also passed the full forensic matrix: 982 tests
with 2 skipped, 133/133 unique mutation targets, and 133/133 mutants killed.
That pre-final normative-projection receipt is
`ff73ad94208a5be528c8492663766da4ffacc6809db71f10a10dec17f4b1f436`.
After the CHX registry wording was normalized, the final behavioral feature
gate passed 42/42 with 0 orphans in 24.07 seconds; its file SHA-256 is
`4814b5750a69e4e02ba711d68557bf680693bd7e7c188eebb91917773d04ee09`.

Strict candidate reconnaissance covered 982 probe symbols, 209 commands, and
76 modules with 0 errors and 0 warnings. Candidate and installed reports share
the same capability and behavioral registry hashes.

| Report | Inventory SHA-256 | File SHA-256 |
|---|---|---|
| Candidate | `911bcd01dc702d57d7f9c987254441cb0ab095fba7e116b8a7f0191e90325361` | `46ee8b3825d673664ba34d6253294e5cb9496966688dccc2bd60302413edc378` |
| Installed | `92c333bc7f94c4d1e1a2e59c2e5fa8459bf1d56acf5f148a714a04f431af4201` | `8ffbdc0bf72a781d7405c37edcb8d48fa00e37b3c57b56b2d90523eb4e8d634d` |

The absolute root is part of an architecture inventory, so those two inventory
hashes intentionally differ. All 260 package files were byte-exact.

## Frontier canaries

Three installed runs against the real local-F0 project produced identical
26,636-byte `frontier --limit 8` projections:

| Run | Elapsed |
|---|---:|
| 1 | 1.74 s |
| 2 | 1.32 s |
| 3 | 1.31 s |

The output is a bounded Main selection surface. Full Research records remain
available through exact-id planning; there is no persistent frontier cache.

The repaired projection behaved as follows:

- safely completed `631bd0b955fc`, `ce511e2cdf34`, and `9d2ffc8aedd3`
  were absent;
- `451ca484b10f` remained visible because its exact related Research inputs
  differ and it lacks equivalent safe closure;
- `b09e2c701888` remained visible because production exists but its applicable
  second subround is not yet safely closed;
- two same-text quotient-gap nodes remained distinct because their exact
  related inputs and work keys differ.

Main explicitly selected active A-model campaign `campaign-62013035c1ff`.
Inactive B-model, 0730, and historical-reconstruction campaigns were not
silently reclassified or deleted.

Read-only re-projection preserved the project byte baselines:

| Plane | Files | Aggregate SHA-256 |
|---|---:|---|
| Research entries | 978 | `c4224e8d05d866c5c32de514d4961a31de88108df803fc1feb6a743b2b8b66ff` |
| Fact graph | 173 | `c5e5285dd6d34f89d572389b1a9a26642a98fe89d1449dc6698bc7ba785138f4` |
| Campaigns | 12 | `087d7ea1dffe056388258dc9e94f371553e2affa0617590dcd1e9769426bd13f` |

## Source assurance and CHX route checks

Focused source-assurance tests passed 70/70. They cover literature mode,
source-dependent metadata, source/applicability obligations, exact primary
capabilities, same-source-key obligation disposition, role tokenization, and
program-source nonactivation.

The CHX ledger suite passed 50/50. Its global-install regression starts with a
current open revision-5 issue, records no tactical event, and proves that the
global integrated repair can cover it directly. Old frozen ledgers remain
readable and unchanged.

## Installation

| Field | Result |
|---|---|
| Installer | default project-free fast local installer |
| Installed version | 0.8.9 |
| Fast-path elapsed | 3.85 s |
| Candidate-to-installed tree | exact; 260 files unchanged |
| Installed runtime identity | `bf28ce263151e1dfd4d44bda606a26d86dbbb8a80d4b0ad04c6ea2598eb5da87` |
| Installed runtime content | `2eda96ca13e29213f9286931e6e2fc63f8f0f490433df8c89947d4cf58c6ebb0` |
| Direct rollback | pre-final 0.8.9 content `f0ddf4a44ef085f7851deb9c73821547c50608c9830d6b5065c22b5bea849bf7`; 0.8.8 remains archived |
| Project reads/writes | 0 / 0 |
| System restart | not performed |

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-fc8df3d092381bbe7de8bb083dcd377b4acabd2bd830887930538b0b8d3ad249` |
| Canonical `record_sha256` | `3e5e35b10f29ef38d35ef0dd7e7d65e341ec6ec5ba449ef00eda04a42e57c2e5` |
| Record-file SHA-256 | `864a7742223f6fe1f4a07551d63ed3c90fbbe7145a60bb717796019e3f828976` |
| Inventory SHA-256 | `6a4c715cffba92ec6aa597a8e56e7f950a5710fddf9c1b04332c0febe9670097` |
| Covered snapshot SHA-256 | `e313536f74bb6dbcc084fc1926762a9481f42dac528fbc2176656ba2bd517024` |
| Observed / globally disposed | 162 / 162 |
| Resolved / excluded | 156 / 6 |
| Mechanism groups | 18 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

The current run ledger contains zero tactical and zero per-ledger integrated
repairs. The installed change is represented by the global integrated
successor. Historical open task flags are retained as history but own no active
issue or cleanup veto.

## Research and truth boundary

This architecture release created no Candidate Release, Certification
Decision, Gateway admission, or Fact. The local-F0 Research graph remains
nontruth until its own later admission path is completed.
