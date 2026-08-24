# Validation — Chalxius v0.9.0

This report records software, packaging, installation, live large-project
behavior, performance, and CHX settlement for **Chalxius 0.9.0 — Frontier
Active Fix**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.9.0 |
| Release date | 2026-08-24 |
| Skill manifest entries | 264 |
| Package files, including manifest | 265 |
| Manifest SHA-256 | `ad7e4a1b5ce81a35e62ac4d78cdc845a9289e226e866f0987d3d02258ff91d51` |
| Runtime content SHA-256 | `fe51aa8d051fc7bfae730cf3f17b4cc56a62b8c80aa1cbdcd08c66e6adf80fed` |
| Installed runtime identity | `164fded34389f5f491ed080eafc99a20c09fc5de2fd3e76345bbea029a8ef630` |
| Installed archive-tree identity | `349612debe0ce1685f1d5b0efa3ea84d923696d81aee06547f5d9199a7b11dce` |
| Archive | `chalxius-0.9.0-frontier-active-fix.tar.gz` |
| Archive bytes | 2,601,441 |
| Archive regular-file members | 265 |
| Archive directory members | 0 |
| Archive SHA-256 | `30e6d08ff6546a454e4273efa42e561b57f67f8c3cf9e8c2337baef3fcc8519a` |
| Checksum-file SHA-256 | `710a00e432b5b575b76ac30a260fc70fddd2a696798af2bccc099348f96e413c` |

Two builds from the frozen tree were byte-identical. A cold extraction matched
the source tree and passed every manifest row, the bundled self-test, and
strict architecture reconnaissance.

## Forensic release matrix

One forensic profile was selected for the exact final manifest. It explicitly
subsumes the routine profile while bytes remain unchanged, so the routine
matrix was not repeated.

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.954 s |
| Full suite | PASS; 1,006 tests discovered | 90.930 s |
| Mutant registry preflight | PASS; 145/145 unique targets | 0.122 s |
| Full mutation audit | PASS; 145/145 killed | 173.444 s |
| Behavioral feature gate | PASS; 43 features, 0 orphans | 21.323 s |
| Strict architecture scan | PASS; 0 errors, 0 warnings | 5.421 s |

The matrix recorded 291.871 wall seconds and 292.194 aggregate lane-seconds.
The full mutation audit was the slowest lane. Every lane used manifest
`ad7e4a1b5ce81a35e62ac4d78cdc845a9289e226e866f0987d3d02258ff91d51`
and reported an unchanged candidate tree.

The final matrix receipt has file SHA-256
`a1b118438c42dd534b2a2828cb4d9716885cb27c460dcc72fa5ba4941d75fc09`.

## Architecture reconnaissance

Strict reconnaissance found:

- 265 files and 11,689,577 bytes;
- 91 test files;
- 77 Python modules, including 58 MathGraph modules;
- 0 orphan modules;
- 0 exact duplicate-file groups;
- 25 duplicate-function-body groups, all 25 explicitly adjudicated;
- 0 generated artifacts, errors, warnings, or behavioral orphans.

The candidate architecture inventory SHA-256 is
`38a6a528a4aa619b3c18e47b4af53a22ea3750e3eaf4c2d5224f5ca9d879c7f1`.

## Frontier Active Fix regressions

Focused and mutation tests establish these properties:

- the compact frontier distinguishes production, return waiting, ingestion,
  supervision, repair, Main reconciliation, and no-action states;
- the actionable id follows the current validated lifecycle object instead of
  mechanically redispatching the original Research root;
- exact canonical COW completion remains a fast path;
- ambiguous, duplicate, historical, malformed, or branching evidence stays
  visible for Main judgment rather than being auto-closed;
- a Campaign `research_goal` names one exact existing Research root in the same
  Campaign and carries no dispatch or truth effect;
- explicit Campaign selection scopes the goal projection, while the ordinary
  active Campaign remains only a hint;
- goal coverage, progress, queue, orphan, and Main-choice signals are derived
  from existing bytes and are not persistent frontier state;
- default output is compact and `--diagnostic` remains bounded;
- no automatic admission, scheduler, watcher, cache, compatibility layer, or
  new lifecycle gate exists.

The semantic mutation profile killed 27/27 mutants. The full release profile
killed 145/145.

## Live large-project exercise

The final installed runtime was exercised on the active local-F0 A-model
project with 1,288 Research entries at the performance measurement point.

Three exact Campaign goals were added without duplicate events:

1. the physical-heart corridor;
2. the exact marked physical light period;
3. the split-light Hall/log factor.

The explicit-Campaign frontier derived:

| Signal | Result |
|---|---|
| Goals covered | 2 |
| Workflow pending | 1 |
| In flight / research open | 0 / 0 |
| Orphaned / needs Main choice | 0 / 0 |
| Selected root | `1a0f4f0fbceb` |
| Actionable Research | `2050c5322ddd` |
| Next action | `repair` |
| Reason | `production_product_invalidated` |

The explicit projection took 2.263 seconds and emitted 13,533 bytes. An
unscoped projection treated the active Campaign only as `active_hint`, took
2.754 seconds, and did not silently filter the queue.

## Target-certificate performance repair

Before the final fix, synchronizing a research-only Campaign target loaded and
validated the whole admitted Fact graph before emitting an empty 250-byte
certificate:

| Measurement | Before fix | Candidate fix | Final installed |
|---|---:|---:|---:|
| Target synchronization / replay | ~294.5 s | 3.02 s first add; 2.39 s retry | 3.23 s retry |
| Approximate sampled physical footprint | ~544 MiB | not retained as a release claim | not retained as a release claim |
| Approximate sampled peak | 1.0 GiB | not retained as a release claim | not retained as a release claim |
| Campaign events after idempotent retry | 7 | 7 | 7 |

The measured candidate wall-time reduction was 98.97%. The repaired
certificate traverses only selected proof targets and their exact transitive
predecessors. A research-only target has an empty proof closure and reads zero
Facts. Deterministic topological order, exact hashes, and existing audit errors
remain in force.

The bound performance evidence has SHA-256
`ab454c54a2c3e91f351ada0592b2e0391b163005aa61e354ca9002ce21ca8582`.

## Installation and rollback

| Field | Result |
|---|---|
| Installer | `scripts/local_install.py` |
| Installed version | 0.9.0 |
| Candidate-to-installed tree | exact; 265 files unchanged |
| Candidate runtime identity | `9343d1ff0905b3b78bf93599add08cd99701488423ec082f4fd46be3719010af` |
| Installed runtime identity | `164fded34389f5f491ed080eafc99a20c09fc5de2fd3e76345bbea029a8ef630` |
| Installed runtime content | `fe51aa8d051fc7bfae730cf3f17b4cc56a62b8c80aa1cbdcd08c66e6adf80fed` |
| Installed archive-tree identity | `349612debe0ce1685f1d5b0efa3ea84d923696d81aee06547f5d9199a7b11dce` |
| Direct rollback | 0.8.12 content `ffb00b70da8035ff7939aef3a8050dbcd41492249398ac7a2fc3f4f6de233c03` |
| Project reads / writes | 0 / 0 |
| System restart | not performed |

The final installation evidence file has SHA-256
`fd13ee61c1193bdaf8a7d214217647941e2ae8fadbcb2fe66430d6e790ccc669`.

## Repository metadata and archive

The existing release validator's metadata-only projection checks the candidate
version, release display name, archive name and bytes, manifest identity,
checksum sidecar, the unique SHA256SUMS row, and the required identity markers
in README, RELEASE, and VALIDATION. Public prose is not generated or approved
by this check.

The archive contains only the 265 regular package files and no synthetic
directory or other members. The checksum sidecar contains exactly:

```text
30e6d08ff6546a454e4273efa42e561b57f67f8c3cf9e8c2337baef3fcc8519a  chalxius-0.9.0-frontier-active-fix.tar.gz
```

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-0b4d0d15520bc41f8273a3f6d962dc0129511b2a18440056fabbd2c9694e698a` |
| Canonical `record_sha256` | `14307aba1bc1af4791dff5e97f068d4df828a22e824af7bbed346cbb9302f7a2` |
| Record-file SHA-256 | `40720e2137716e1229e97f8920779ef88ecc68cb7e879c499dc9512bf2bd3bd0` |
| Inventory SHA-256 | `1c734bb26f242996213213b7e863fe0ddaba24537b78eea88dc10e1b190cd208` |
| Covered snapshot SHA-256 | `7cd60c497e6bbf7daee2aba8cd166e3031955e0742b852362921e7a327440592` |
| Observed / globally disposed | 177 / 177 |
| Resolved / excluded | 171 / 6 |
| Current mechanism groups | 6 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

The current task ledger is closed with SHA-256
`1ecba772b28e08f89d448110ef88508339857a364fb05687c8fe37e5136c7e68`.
Its architecture-report SHA-256 is
`5df04db4c51e3c2d8a995ae3d5dbcae079b9747fedca835cbc492d2df000de5c`.
It contains seven issues, all resolved by the global integrated repair, and
zero tactical or per-ledger integrated repairs. Twenty-four historical ledgers
retain their original active flag, but none owns an open issue; no historical
bytes were rewritten.

## Research and truth boundary

The live exercise changed only nontruth Campaign targets and read-only
frontier projections. It created no Candidate Release, Certification Decision,
Gateway admission, or Fact. Installation read and wrote no Research graph
bytes. The selected A-model repair remains Research work, not an admitted
mathematical result.
