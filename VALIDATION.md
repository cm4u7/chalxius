# Validation - Chalxius v0.7.16

This document records software, packaging, CHX, and protected-installation
evidence for Chalxius 0.7.16 **Bounded Capability Hygiene**. It does not certify
any mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | `0.7.16` |
| Release date | `2026-08-16` |
| Skill manifest entries | `253` |
| `MANIFEST.sha256` SHA-256 | `830d0af9b893ba2c1ee2f5fc3e881d59d273375350676292f0882a6d21316693` |
| Runtime content SHA-256 | `ab6a31b541e6d2e85d6c4471f857ccbb5662aaf49030a320be3229faad3c2f1d` |
| Installed runtime identity | `fa48d02e07f878d81a3be985310269d5d5419a42a10decf82a65f5305e52dd8b` |
| Installed archive-tree SHA-256 | `110794a476d6cc9ec8be057b984f1cc56c4d3f8bcd4ead617279d01c07db5221` |
| Archive | `chalxius-0.7.16-bounded-capability-hygiene.tar.gz` |
| Archive bytes | `2488196` |
| Archive members | `254` |
| Archive SHA-256 | `e1091efb2601738879515af860c3bf8dc331626cac5805b4247eaaaf906eab6c` |
| Checksum-file SHA-256 | `1c40697dfa3bdfea32b4f5dcd1676533c05349f0046c7876e797d9f5fcc6d4a8` |

Two independent archive builds from the sorted exact manifest produced the
same byte stream.

## Release matrix

The publication-final manifest-bound receipt is
`release-validation-final-20260816.json`, SHA-256
`372e9b0baadd0b0b1e775951de72986ca05f5c4ee88b89e91d5fcaac1d89ca82`.
It records `ok=true`, `complete_lane_set=true`,
`one_manifest_identity=true`, and `source_unchanged=true`.

| Lane | Result |
|---|---|
| Mutation-registry preflight | PASS; `145/145` exact targets |
| Architecture reconnaissance | PASS; strict mode |
| Behavioral feature gate | PASS |
| Full discovered suite | PASS; `942/942` tests |
| Bundled self-test | PASS |
| Aggressive bug audit | PASS; `145/145` registered mutants killed |

All six isolated lane copies retained the approved manifest and reported
`lane_unchanged=true`.

The protected installation was authorized by an earlier successful run over
the same manifest. Its receipt SHA-256 is
`481ad4431c274d93741dca209cace3cb113092d1749778d6f15de2edb3a004a1`.
The later publication-final rerun is additional same-identity evidence; it does
not rewrite the installation-time receipt.

The standard skill quick validator also passed after confirming PyYAML 6.0.3
in the invoking Python environment.

## CHX disclosure and complete project settlement

The canonical public lineage remains continuous through CHX-035. The final
public ledger and deterministic report remain:

| Evidence | SHA-256 |
|---|---|
| `run-20260814T004319766703Z-fdfc7f3fd6e2.jsonl` | `4eb2660eee4bc089d0bd50fd7f871ad48a2141ce1c0d587fb3e50625eebbf8af` |
| `run-20260814T004319766703Z-fdfc7f3fd6e2.architecture-report.md` | `36b515222031f191f79607ccbc09f60927c90279cc3d7daf544b51646fce198e` |

Later project-local CHX identifiers are RUN_ID-qualified private evidence and
do not extend the public numbering. Their bodies are not included in the
archive.

The user-directed cross-ledger settlement was refreshed against the final
manifest after all task ledgers closed:

| Field | Value |
|---|---|
| Global repair id | `global-repair-75b0125022b0e2697accb8eb401922b2e3ad27564f28e96c38cb71d9e6290043` |
| Record SHA-256 | `541b20c2905559ceba04c69059c22c83a503e9a859bf5428afbabba34c02a2bc` |
| Inventory SHA-256 | `61b52a27ff4c3e44c030a444fc5b729d01c60498e38de43bfee6a627b85807c3` |
| Covered-issue snapshot SHA-256 | `d166166a651d3eee2414744a7c6097add958e61bda034b7c65e6d575c8fa2d77` |
| Observed qualified issues | `122` |
| Covered qualified issues | `122` |
| Uncovered issues | `0` |
| Active ledgers at settlement | `0` |
| Lineage/report drift | `0` |

This record is copy-on-write, nontruth, premise-ineligible project evidence.
It is reported here only to distinguish complete local settlement from the
smaller public disclosure lineage.

## Protected runtime cutover

The approved project-validation receipt SHA-256 is
`13ad9267e86f9b41bd348055ed166834dd66f8c48d0b0d1e03ef307078599e9c`.
It binds the exact candidate manifest, prior 0.7.15 runtime identity, complete
runtime diff, installation-time release matrix, protected project snapshot,
and one necessary deep audit.

| Field | Result |
|---|---|
| Cutover status | `cutover_complete` |
| Validation mode | `single_deep_audit` |
| Protected projects | `1` |
| Protected rounds | `225` terminal: `211` completed, `14` aborted |
| Project audit | `current_ok=true` at cutover validation |
| Cutover project-state SHA-256 | `73e856d9ee79c9ae396921674ec384039e115bc0ff1460bd0b4934ff6cf96057` |
| Candidate-to-installed tree | exact manifest/content identity |
| Current installed version | `0.7.16` |
| Current installed runtime identity | `fa48d02e07f878d81a3be985310269d5d5419a42a10decf82a65f5305e52dd8b` |
| Rollback version | `0.7.15` preserved |
| System restart | not performed |

The present installed binding and its sealed archive were independently
resolved after cutover. Closing the later zero-issue release ledger and writing
the final global CHX settlement changed only nontruth project bookkeeping; it
does not retroactively alter the cutover snapshot.

## Cold archive check

A fresh extraction of the public archive passed:

- `253/253` manifest hashes;
- the bundled self-test;
- the standard skill quick validator;
- PyYAML `6.0.3` availability; and
- absence of `__pycache__` directories and `.pyc` files.

## Research and truth boundary

The A-model artifacts remain nontruth Research. Version 0.7.16 creates no
Candidate Release, Certification Decision, Gateway admission, or Fact. Hashes
establish byte identity, tests establish exercised behavior, and mutation
results establish detection of registered faults; none proves a mathematical
theorem.
