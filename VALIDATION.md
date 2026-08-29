# Validation — Chalxius v1.0.0 Fact Alpha

This report records software, package, installation, live-project performance,
sensitive-information, and CHX-settlement evidence. It does not certify a
mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 1.0.0 |
| Release date | 2026-08-30 |
| Manifest entries | 268 |
| Package files, including manifest | 269 |
| Manifest SHA-256 | `35ad8484d021035e62a5dcb9efacbf1224f900abd4c61acbc8efcafecc693fcf` |
| Archive | `chalxius-1.0.0-fact-alpha.tar.gz` |
| Archive bytes | 2,705,200 |
| Archive regular-file members | 269 |
| Archive SHA-256 | `815fa9f6eaa910fafb653825cbe3e2c4e231d40938fea5c8bf3accb67841d850` |
| Checksum-file SHA-256 | `d280c67857f74b8cc88bdff4cb47f7e2afb69ac09326cfef80bb926cbc172125` |

Two independent archive builds were byte-identical. The archive contains only
sorted regular package files and no cache or bytecode member.

## Whole-tree architecture and behavioral gates

Strict reconnaissance covered 269 files, 77 Python modules, 57 MathGraph
modules, and 96 test modules. All 24 duplicate function-body groups had an
explicit adjudication. It reported zero orphan modules, behavioral orphan
features, errors, and warnings. The inventory receipt SHA-256 is
`82fcbb04519f696703b5453aaa00849e9e88937a1c4ae1b7e4e9173f9516efdb`.

The final behavioral gate exercised 53 registered features with 141 executable
probes. All passed and the source tree remained unchanged. The receipt-file
SHA-256 is
`42f7bb5cda9aacc07e214c30b76023b018de60bd669c9815dbc3c2855a9c6edd`.

The complete suite passed 1,068 tests, skipped 2, and failed 0 in 75.047
seconds.

## Routine release matrix

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.954 s |
| Changed-surface tests | 132 tests, PASS | 11.153 s |
| Semantic mutation audit | 32/32 killed | 45.900 s |

The matrix completed in 57.426 wall seconds. Every isolated lane reported an
unchanged source tree. Its receipt-file SHA-256 is
`cb141dfa1cfd382a218971d9ab4dd65f5fdc60f7df0dce8247a40a0c912764d7`.

The regressions cover the complete Fact Alpha command surface, exact package
binding, component-isolated verifier decisions, minor and fundamental repair
routes, descendant re-verification propagation, exact certified Research
dependencies, legacy authority isolation, installation reachability, and
current target-bound Campaign round precedence.

## Installation and live-project canary

| Field | Result |
|---|---|
| Installed version | 1.0.0 |
| Candidate-to-installed tree | exact; 269/269 files unchanged |
| Installed manifest SHA-256 | `35ad8484d021035e62a5dcb9efacbf1224f900abd4c61acbc8efcafecc693fcf` |
| Previous runtime archived | 0.9.18 |
| Direct rollback available | yes |
| Project reads / writes by installation | 0 / 0 |

The installed local-$\mathbb F_0$ canary scanned 2,247 Research envelopes.
`fact-frontier --limit 8` completed in 0.942 wall seconds (673.717 ms internal)
and correctly reported zero Fact Alpha marks, grants, and batch opportunities
for the untouched project. Legacy Fact authority was reported as
`read_only_unmapped`.

The full read-only audit completed in 14.789 seconds and reported:

| Signal | Result |
|---|---|
| `current_ok` | true |
| `history_clean` | true |
| Graph errors | 0 |
| Workflow errors | 0 |
| Research entries | 2,368 |
| Legacy Fact entries | 82 |

The project metadata snapshot SHA-256 was
`54ecede31f19dc4ef1feb876ba8e2997edfcff93f9f67f57fd325cec2e21d108`
both before and after the canary.

## Sensitive-information scan

The package was scanned for the local username and absolute user path,
private-key headers, common cloud access keys, GitHub/OpenAI/Slack token forms,
and common secret assignments. No true positive was found. The three reviewed
matches were a generic `/Users/<user>/...` documentation path, a synthetic
host-task identifier, and an `/Users/example/...` fixture.

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-f66daf8fa1046e7c4f8dfda1437cd76de7d781bceb4b3ea6f41e0468a88fac80` |
| Canonical `record_sha256` | `ce4b7f2fa8f790dd41f4b29e8672f2ef16976236578e0247a7f28d0c82bb3c26` |
| Record-file SHA-256 | `ae1c531980e8cf2f88ee874461be980b0d44875daeaf519d37f568e6ad3c5b75` |
| Inventory SHA-256 | `f98c1efd08d3b4f11ffbdbb2333637bb5706c70e30fb0c0aab54449a38828f93` |
| Covered snapshot SHA-256 | `4c636dd928f23faec90df447052e1524097e4bec4e552fe280712e420c87db60` |
| Observed / globally resolved | 239 / 239 |
| Revalidated prior / newly fixed | 236 / 3 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

Historical ledger bytes were not rewritten. Thirty-seven raw historical
ledgers retain old open-state provenance, including nine abandoned open
ledgers, but all observed issues are covered by the current global settlement.

## Research and truth boundary

Installation wrote no project byte. The live canary was read-only. CHX
settlement is administrative. Fact Alpha only grants certification after a
future exact package, independent verifier decision, and `fact-certify`
operation; this release itself created no certification grant or mathematical
Fact.
