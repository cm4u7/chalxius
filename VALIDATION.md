# Validation — Chalxius v0.6.2

Result: **PASS within the enumerated software and workflow scope**.

This document separates package validation, architecture-regression evidence,
and field-pipeline assurance from research truth. None of the results below
proves a mathematical theorem, establishes a philosophical or empirical claim,
establishes novelty, certifies the private field graph, or Fact-admits a paper.

## Frozen public package

| Property | Value |
|---|---|
| Version | \`0.6.2\` |
| Display name | \`Paper Graph Continuity / Brave Future BF-1–BF-3\` |
| Workflow authority | V5 |
| Truth path | \`Research -> Candidate Release -> Certification Decision -> Fact\` |
| Renderer | \`chalxius-reader-html-20\` |
| Layout | \`deterministic_theme_multicenter_orbit_fields\` |
| Manifest entries | 201 |
| \`MANIFEST.sha256\` SHA-256 | \`6794d0eaec2c7eb02b427b816180375ea1b2cd37788c1158e7b5b63888609158\` |
| Archive | \`chalxius-0.6.2-paper-graph-continuity-brave-future-bf1-bf3.tar.gz\` |
| Archive bytes | 1,985,285 |
| Archive members | 202 regular files |
| Archive SHA-256 | \`389e923d9bd91479693d1ee9659cb78449cccf0f52f439074fd91e897a0addb3\` |

The archive is produced from the manifest allowlist twice and the resulting
bytes are identical. It uses sorted USTAR regular-file members, numeric UID/GID
0, empty owner/group names, fixed member time 0, and gzip time 0. It contains no
directory, symlink, duplicate, absolute, traversal, cache, bytecode, or
unlisted member.

## Automated checks

| Check | Final tree / installed tree | Cold archive |
|---|---:|---:|
| Complete unittest suite | 622/622 PASS (108.587 s) | 622/622 PASS (93.332 s) |
| \`scripts/self_test.py\` | PASS | PASS |
| Manifest exact path/hash set | 201/201 PASS | 201/201 PASS |
| Exact extracted tree comparison | — | PASS |
| Targeted installed CHX/Paper suite | 37/37 PASS | Identical code bound by exact tree |
| Aggressive release mutation audit | 110/110 killed | Identical code bound by exact tree |
| Public Reader packet/schema/privacy validation | 3/3 PASS | Public files are repository assets |
| Transactional runtime-cutover audit | 10/10 rounds before and after cutover | Prior and new archives preserved |

The release mutation audit reports \`candidate_unchanged=true\`. Its 110 killed
mutations include strict research-draft admission, Paper topology and atomic
closure, source/operator transport, evidence receipt recomputation, composable
verification, runtime continuity, BF advisory boundaries, CHX disclosure, and
exact ledger-run namespacing. Three final disclosure mutants specifically
attempted to accept an unresolved issue, bypass explicit public enumeration, or
bypass the ledger namespace; all were killed.

## Field Paper Research Pipeline matrix

The private field run first froze this baseline:

- Pipeline preflight id:
  \`ppr-54d03ca6c5f12c80679f638d4d1e166e58c17e683b54c1d9dcb98aaf4a6bdda5\`
- Baseline receipt SHA-256:
  \`b80012d11ebcd78e68f3a7a4ad3d5b8e31a88bf6f943d0068a6acdfe9769c0d0\`
- Actual inherited Paper Graph: 1,499 nodes and 2,553 edges.
- Ordered frontier: 101 claims and 43 inferences.
- Paper-subject atomic DAG: 101 claims and 144 dependencies.

A later append-only reliability campaign generated 1,200 semantic mutations:
200 each against \`paper_graph\`, \`ordered_frontier\`, \`atomic_dag\`,
\`research_continuity\`, \`evidence_receipt\`, and \`successor_receipt\`.
All 1,200 were killed; there were zero survivors and zero harness errors.

- Matrix id:
  \`prm-1e79c12ef60383199465dce6cd4e984df86973fbd450a674dadc09d6d9aa8b3d\`
- Matrix SHA-256:
  \`6c31aa9dc7bcaae41e0382bc53447802a33ca2249e4acd724e1be7003d1139b2\`

This matrix is later nontruth assurance bound to one frozen private baseline.
Its aggregate and hashes are reported here; the private Paper Graph, receipts,
sources, and ledger are excluded from the public package. The matrix neither
upgrades a historical admission nor changes the immutable status artifact that
recorded which checks had been deferred at admission time.

## CHX disclosure preflight

The public package enumerates CHX-001 through CHX-057 and qualifies them under:

\`run-20260801T233737840117Z-a29d00a787c1/CHX-NNN\`

The private ledger itself contains CHX-018 through CHX-057; CHX-001 through
CHX-017 belong to the same release lineage and are carried forward in the
public registry. All 57 public entries have prospective resolved mechanisms.

The publication-disclosure preflight passed against the exact ledger run,
resolved dispositions, explicit issue list, and required documentation
markers.

- Canonical public issue registry SHA-256:
  \`df8c57533d5319d8df4deeaefdec076744ef3337c8e5db82ea3798cb2479d55d\`
- \`KNOWN_LIMITATIONS.md\` SHA-256:
  \`d2d7f62c9501ecae30c20d8de22b51cba203f617b2b4371aec8f94df89964c5f\`
- \`v5_release_traceability.md\` SHA-256:
  \`0a054cad6a2e16b3f115ed8e77327089652dace597d1c06076c29dfe8668eb71\`

Resolved mechanisms do not establish permanent architecture completeness.
Future field discoveries must open new append-only CHX issues. They do not
authorize weaker Candidate, Certification, or Fact gates.

## Public showcase privacy and determinism

The featured Reader artifact contains 175 nodes, 364 edges, 17 targets, and 7
themes. It was generated read-only from a private research topology with an
ephemeral 256-bit HMAC key discarded after export.

- Packet file SHA-256:
  \`19cb5e0fc9f588305531276241207b1dc60cd2d002946dbfcad90b75e3e7244a\`.
- Canonical packet SHA-256:
  \`75df4f4fa769a30485b45f5198b033a72136d50f61c00a576e85ef1a73fad998\`.
- Deterministic HTML SHA-256:
  \`90207966b1779d8595f0ce8ee9275ff5a2f4abeaa313f0984647d19304cb3ae6\`.
- Screenshot SHA-256:
  \`3e012ee58684de1b4eb0504b34114a9bec9636365ca2cce4dea9a93404ece444\`.

Every content-bearing field and original identifier is replaced by an opaque
hash. Topology and structural enums remain visible by explicit design. All
three public Reader cases have \`truth_effect="none"\`.

## Release contract hashes

| Contract | SHA-256 |
|---|---|
| \`INHERITANCE.lock.json\` | \`f1874e345ada4de3f857bc71e23c49087ea50e0652c3a9752e90a018ccdea710\` |
| \`scripts/mathgraph/contracts.py\` | \`5bd04ce9dc5fea159805e50b921a225875124946ec26e3e119af4236d03d75e1\` |
| \`references/admission_contract.md\` | \`4879da333f75a90062742a4280cd855697e39a5f7f6cb01f53121a337f70a75c\` |
| \`references/reasoning_modes.md\` | \`ee2dc78be7ab0a999d4f4738e4ab31056475c13e2c7680f980d8d2da8a5c8d3a\` |
| \`references/paper_research_pipeline.md\` | \`dac241b91acb45d17fe09be3037d5fdbdbbc4ff1ae31c42c30128db0d0291c49\` |
| \`scripts/mathgraph/paper_research_pipeline.py\` | \`dee168e34923fe274465e8d31f67342f1a526dc5ba729de31558f11d093541a3\` |
| \`scripts/mathgraph/paper_research_reliability.py\` | \`52f546d24cd03ed3e6c8183d121d883e7d4b054b8cdbce170737562cc4da0f4f\` |
| \`scripts/chx_ledger.py\` | \`67a61345c8e5258f1b943df24152ab7e4fc3e1aef7d46f95a74a2bd79ff76b4a\` |
| \`assets/reader_html_app.js\` | \`b949ed26a059d71887ac1ca2e7661e7aa987070abc2d12c1438556a92b440fc7\` |

## Scope boundary

Package hashes prove byte identity; tests establish only the exercised
properties; mutation scores establish only that the enumerated mutations were
detected. Paper Audit, Evidence review, Reader rendering, CHX closure, and
software validation are not interchangeable with fresh verification and Fact
admission.

Publication does not migrate, backfill, reopen, or request redo of any active or
historical project. Installing or replacing a global runtime is a separate,
explicit, transactional operation.
