# Validation — Chalxius v0.8.11

This document records software, packaging, installation, agent-judgment
semantics, public disclosure, and global CHX settlement for **Chalxius 0.8.11
— Agent Judgment Integrity**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.8.11 |
| Release date | 2026-08-23 |
| Skill manifest entries | 261 |
| Package files, including manifest | 262 |
| Manifest SHA-256 | `114555be38fa461c68cc3b699bf7e63bb26857ebcf7317bbf881114d768546d0` |
| Runtime content SHA-256 | `de1d4a03ef94c0e47ed994b75493cc74504664fc4054a1d8c6809a0e2a4ebba9` |
| Installed runtime identity | `27ec3fa853fda91393a471e4920aed1f57a52987989927111e8954e00980b694` |
| Installed archive-tree identity | `c2c9e3e9febcf3de50621181311f34138057147220ad3951a14bee92d347cde5` |
| Archive | `chalxius-0.8.11-agent-judgment-integrity.tar.gz` |
| Archive bytes | 2,572,660 |
| Archive regular-file members | 262 |
| Archive directory members | 0 |
| Archive SHA-256 | `b81fcbd25823a15d61a0653eae666da342fd76d28158d1d3a0fdf0f51813774c` |
| Checksum-file SHA-256 | `6dd16301e14e0690784c399d5bd301c8c7d9b3677e8a6d251e14e3e6cd27e191` |

Two builds from the same frozen tree were byte-identical. A cold extraction
matched the source tree and passed every manifest row, the bundled self-test,
and strict architecture reconnaissance.

## Complete and failure-informed validation

The complete test suite passed **987 tests in 78.480 seconds**, with 2 skipped.
The full mutation preflight found 134/134 unique targets in 0.093 seconds, and
the full audit killed 134/134 mutants in 153.312 seconds.

The forensic matrix used contract `chalxius-release-validation-matrix-6` and
has file SHA-256
`0e1853da6836a24142b30c26445b3225dac574a70d552935d32da55f6b543284`.

| Forensic lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.837 s |
| Full suite | PASS; 987 tests, 2 skipped | 78.480 s |
| Mutant registry preflight | PASS; 134/134 | 0.093 s |
| Full mutation audit | PASS; 134/134 killed | 153.312 s |
| Behavioral feature gate | PASS; 42/42, 0 orphans | 16.605 s |
| Strict architecture scan | PASS; 0 errors, 0 warnings | 4.764 s |

The final routine matrix used the same contract and exact manifest. Its receipt
file SHA-256 is
`458c3575b00f99b5eeba6eeb002c624aa5c236e068029d9f11bb2115ef11b8fb`.

| Routine lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.953 s |
| Changed-surface tests | PASS; 29/29 | 8.695 s |
| Semantic mutation audit | PASS; 16/16 killed | 34.454 s |

Every lane used manifest
`114555be38fa461c68cc3b699bf7e63bb26857ebcf7317bbf881114d768546d0`
and reported `source_unchanged=true`.

## Architecture reconnaissance

Strict reconnaissance found 262 files, 89 test files, and 76 Python modules,
with 0 errors and 0 warnings. The absolute root participates in the inventory
identity, so candidate, installed, and cold-extraction hashes intentionally
differ.

| Report | Inventory SHA-256 | File SHA-256 |
|---|---|---|
| Candidate | `ee397c88f15e205873c2cf9d23d7de0f8ebe41f021421bd7f9a54f344d5b301b` | `126bb6df8171d4d033946e8ad53cb5c9cd8eeb7206595c4e77a4cfa185fe01fe` |
| Installed | `06cbe1f1dc2a4a5959573b5d2e2e229113be80a475214c2561ef7816f5727577` | `d82f13779d32c0f1ba23115bbbc8b9b2de3980bfb3df74aef97a0e83cf9fb947` |
| Cold archive | `4264b8c7464a62515c4202c85325c582b046c7215b68f1720aa8ef4742a72e93` | `a7e844ee0e2b9e2f3f247a8d93eee4088e230ef49262f6a64180821389d71f1f` |

All 262 candidate and installed package files were byte-exact.

## Agent-judgment regressions

The 0.8.11 regressions exercise generated worker prompts and dossiers, not only
static wording. They establish these semantic boundaries:

- Main must actively select a named Campaign, object, or proposition and check
  exact Research completion before freezing work.
- Artifact silence, a single quiet wait, elapsed time, context compaction,
  bounded startup reading, and deep reasoning do not establish worker loss.
- Fresh host-visible status, messages, explicit errors, and round bytes are the
  relevant evidence. Repeated lack of useful output can justify reclaiming a
  live but unproductive worker; loss requires explicit or corroborated failure.
- Every copy-on-write successor receives a fresh full review within the assigned
  scope. Prior defects are mandatory but non-exhaustive attack seeds.
- PHX removes procedural fragility without limiting proof, source, program, or
  integration scrutiny.

Mutation coverage includes restoration of the forbidden COW defect-allowlist
behavior and confirms that the regression suite kills it.

## Public disclosure and package boundary

The public-disclosure contract
`chalxius-chx-public-disclosure-2` passed against the exact closed historical
ledger chain through CHX-035:

| Field | Value |
|---|---|
| Disclosure status | PASS |
| Historical ledger file SHA-256 | `4eb2660eee4bc089d0bd50fd7f871ad48a2141ce1c0d587fb3e50625eebbf8af` |
| Ledger event-head SHA-256 | `6d057a16436c697bced5de09c7a6cc57fa59d6c5b90b1a111ed0973313446582` |
| Public disclosure registry SHA-256 | `e6187e0b210cf89d32a85569ee047ff1f96a7f5c2b3a5fdcc8c112124aaaa210` |
| Private ledger included | false |
| Truth effect | none |

The archive has 262 regular-file members and no synthetic directory entries.
All cache and bytecode artifacts are absent.

## Installation

| Field | Result |
|---|---|
| Installer | default project-free local installer |
| Installed version | 0.8.11 |
| Elapsed | 3.4 s |
| Candidate-to-installed tree | exact; 262 files unchanged |
| Installed runtime identity | `27ec3fa853fda91393a471e4920aed1f57a52987989927111e8954e00980b694` |
| Installed runtime content | `de1d4a03ef94c0e47ed994b75493cc74504664fc4054a1d8c6809a0e2a4ebba9` |
| Installed archive-tree identity | `c2c9e3e9febcf3de50621181311f34138057147220ad3951a14bee92d347cde5` |
| Direct rollback | 0.8.10 content `50ff63f2ba0c7bc5760337dd70b22ffab2591ae45ee44670c73b282a846bed2c` |
| Archived prior public release | 0.8.9 content `2eda96ca13e29213f9286931e6e2fc63f8f0f490433df8c89947d4cf58c6ebb0` |
| Project reads/writes | 0 / 0 |
| System restart | not performed |

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-adc53add43febe72e78cae0f88c3b728b0992b93e25a2852fe7d3aba42a75a4f` |
| Canonical `record_sha256` | `2b2c1b52a1503846c2044dafd858683556548956094f4971a36ee7f8a5cdb68c` |
| Record-file SHA-256 | `cb6806351a6a99b09ed7bf718aa999d78b338208575fce8f1fd38a2d1465865f` |
| Inventory SHA-256 | `0c9f8b414b6c6c16acb27e4d7259cbe599661e6df6bc3cf4b439b73b1e8fb10b` |
| Covered snapshot SHA-256 | `ba8712968f9c20765b2884815bd92ddd6c31128a71de0dc022f634817d512989` |
| Observed / globally disposed | 166 / 166 |
| Resolved / excluded | 160 / 6 |
| Current mechanism groups | 4 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

The current task ledger is closed with SHA-256
`0085a4cae1a9a59e6f796cff8a8a6ffbfe5ed929f4d18397fac83ebd6461865b`.
It contains zero tactical and zero per-ledger integrated repairs. The globally
installed change is represented directly by the global integrated successor.
Historical ledgers remain append-only and own no active issue.

## Research and truth boundary

This architecture release created no Candidate Release, Certification
Decision, Gateway admission, or Fact. Existing Research and Fact graph bytes
were not part of installation or publication.
