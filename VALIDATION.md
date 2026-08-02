# Validation — Chalxius v0.6.3

Result: **PASS within the enumerated software and workflow scope**.

Package validation, architecture-regression evidence, field acceptance, and
research truth remain separate. Nothing below proves a theorem, establishes a
philosophical or empirical claim, certifies the private Paper Graph, or admits a
Fact.

## Frozen public package

| Property | Value |
|---|---|
| Version | `0.6.3` |
| Display name | `Bounded Paper Status / Ledger Lineage` |
| Workflow authority | V5 |
| Truth path | `Research -> Candidate Release -> Certification Decision -> Fact` |
| Renderer | `chalxius-reader-html-20` |
| Manifest entries | 204 |
| `MANIFEST.sha256` SHA-256 | `5d69ab621e4c07559a253409e0a9f4c79183716b176a9c84b812edac156db886` |
| Archive | `chalxius-0.6.3-bounded-paper-status-ledger-lineage.tar.gz` |
| Archive bytes | 2,004,366 |
| Archive members | 205 regular files |
| Archive SHA-256 | `b573d3b9859e9162f3522dd1ad921a8e5ee3a103c24adbbb35207472047342c8` |

Two independent archive builds were byte-identical. Members are sorted,
regular, manifest-allowlisted files with numeric UID/GID 0, empty owner/group
names, fixed member time 0, cleared PAX headers, and gzip time 0. Absolute,
traversal, duplicate, symlink, cache, bytecode, and unlisted members are
rejected.

## Automated checks

| Check | Final candidate | Cold archive | Installed global tree |
|---|---:|---:|---:|
| Complete unittest suite | 628/628 PASS (97.835 s) | 628/628 PASS (92.405 s) | 628/628 PASS (92.877 s) |
| `scripts/self_test.py` | PASS | PASS | PASS |
| Manifest exact path/hash set | 204/204 PASS | 204/204 PASS | 204/204 PASS |
| Aggressive release mutation audit | 119/119 killed | 119/119 killed | 119/119 killed |
| Candidate/tree unchanged | PASS | PASS | PASS |
| Cache and bytecode absence | PASS | PASS | PASS |

The nine mutations added since 0.6.2 cover content-addressed Paper status,
stale-HEAD rejection, prevention of summary-to-full reconstruction, top-level
bounded status, and the three exact-runtime host entrypoints. Every mutation
was killed and each audit reported `candidate_unchanged=true`.

## Real Paper-continuation acceptance

An inherited research-draft project was rebuilt once through the explicit
full-validation command. The committed index reported:

| Property | Value |
|---|---|
| Index revision | `chalxius-v5-paper-continuation-status-index-1` |
| Generation | 1 |
| Plans | 2 |
| Targets | 54 |
| Research-lineage records | 123 |
| HEAD SHA-256 | `8e7302ee2502cf5c41cdd2af6ca02626d4e41a753440ed4e0400e39d305d9302` |
| All-plan default status | 0.34 s |
| Current-plan default status | 0.29 s |

The current 33-target plan is complete with zero unresolved targets and
adequacy receipt
`ed9a9a4b2af41af8902693c3fd6e3c311b0f891ed31b939eb922c3c317dde0a7`.
The historical 21-target plan remains explicitly stale because its source
snapshot is not current; it is not silently merged into the current plan.
Routine reads validate HEAD and immutable receipt state and do not reconstruct
the full closure. Directory-generation drift fails closed until an explicit
rebuild.

This migration has `truth_effect="none"`: it writes only a status projection
and does not alter Paper, Research, Candidate, Certification, Fact, Evidence,
or manuscript authority.

## Transactional installed-runtime acceptance

The default `python3 scripts/runtime_cutover.py` path passed without `-B` or a
bytecode environment workaround. Preflight and postflight both found all ten
protected rounds completed and the project audit current.

| Identity | SHA-256 |
|---|---|
| Approved candidate runtime | `c483b4da269f3e8aa8255fb8189d6c4a9439774e91b2de1dd53a08993fed8761` |
| Prior installed runtime | `6c55676f428a641e2e834adcc3ac77d01e511816518a6aa8a76aed62f3fa8e0f` |
| New installed runtime | `84c2cbf2b3a4c94e96120fc70af30bd1db92c0b5fc53833277622d6d2dd05f6f` |

The installed tree equals the approved candidate, its manifest passes, and an
exact rollback tree is retained. The installed 628/119 matrix ran with inherited
bytecode suppression and left no `__pycache__` or `.pyc` files.

## CHX disclosure preflight

The package enumerates CHX-001 through CHX-062 across this exact ordered
lineage:

1. `run-20260801T072127934348Z-16d73c1b37d5` — CHX-001..017
2. `run-20260801T233737840117Z-a29d00a787c1` — CHX-018..057
3. `run-20260802T190108619281Z-6b046e728879` — CHX-058..060
4. `run-20260802T203525083918Z-e81514efe3c7` — CHX-061
5. `run-20260802T214123599238Z-d206bd85e676` — CHX-062

The latest qualified identity is
`run-20260802T214123599238Z-d206bd85e676/CHX-062`. Publication disclosure
passed exact issue enumeration, resolved-disposition, predecessor-chain,
ledger-digest, and documentation-marker validation.

- Canonical public registry SHA-256:
  `75cb5ed3f4d40bb32d89216f8c7c3e9f572c692f053ea8fc7c7361639c3457d8`.
- `KNOWN_LIMITATIONS.md` SHA-256:
  `1da16c401093675a33950b3631ba7a0d3230e769d55883f3cc5809fd9a09a56a`.
- `v5_release_traceability.md` SHA-256:
  `729864d75dda604c943686523b2e21221e877f43619c163b783e4e1e281dc3e8`.

Private ledgers and field sources are excluded from the public package.
Resolved mechanisms do not establish permanent architecture completeness; a
new finding must open a new append-only issue.

## Preserved field Paper Research matrix

The 0.6.2 Paper Research Pipeline assurance remains bound to its frozen private
baseline: 1,499 Paper nodes, 2,553 edges, an ordered frontier of 101 claims and
43 inferences, and a Paper-subject atomic DAG of 101 claims and 144
dependencies. Its 1,200 semantic mutations were all killed with zero harness
errors. This later nontruth assurance neither upgrades historical admission nor
changes the draft or its Facts.

## Release contract hashes

| Contract | SHA-256 |
|---|---|
| `INHERITANCE.lock.json` | `47e98c87843539cc4043796d553fd2221ec3e7c171a95f7ee2bac4d43cc43185` |
| `scripts/mathgraph/contracts.py` | `5bd04ce9dc5fea159805e50b921a225875124946ec26e3e119af4236d03d75e1` |
| `references/admission_contract.md` | `4879da333f75a90062742a4280cd855697e39a5f7f6cb01f53121a337f70a75c` |
| `references/reasoning_modes.md` | `ee2dc78be7ab0a999d4f4738e4ab31056475c13e2c7680f980d8d2da8a5c8d3a` |
| `references/paper_research_pipeline.md` | `d67f8bfd02bc3bfd55000233b8d63b93d7221c5eff09f4845b9317e31acccdbc` |
| `scripts/mathgraph/paper_continuation_status.py` | `4907260087b20dc6b18f18bd8a8e0c2ad6a63f121e725d1fd7fa0360e7ae01a9` |
| `scripts/runtime_cutover.py` | `5d1c6202a0c68a3fa2240b63755ef21c3f4e88effc0fd702ec7e7f003141fa89` |
| `scripts/archive_runtime.py` | `66537b4091262b4273ff0eb55e443e501946a3f861615a79f998ea50257c2f3b` |
| `scripts/chx_ledger.py` | `eb17f987b35b81a4e48cd8130981c99749f6ec8261ec9f0b5583a65d192cfc94` |
| `assets/reader_html_app.js` | `b949ed26a059d71887ac1ca2e7661e7aa987070abc2d12c1438556a92b440fc7` |

## Scope boundary

Hashes establish byte identity; tests establish only exercised properties;
mutation scores establish only detection of enumerated faults. Paper Audit,
Evidence review, Reader rendering, CHX closure, status projection, and software
validation are not substitutes for fresh verification and Fact admission.
