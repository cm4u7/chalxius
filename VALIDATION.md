# Validation — Chalxius v0.5.0

Result: **PASS**.

## Frozen public package

| Property | Value |
|---|---|
| Version | `0.5.0` |
| Display name | `Back to the Future / Paper Continuation` |
| Workflow authority | V5 |
| Truth path | `Research -> Candidate Release -> Certification Decision -> Fact` |
| Renderer | `chalxius-reader-html-20` |
| Layout | `deterministic_theme_multicenter_orbit_fields` |
| Manifest entries | 177 |
| `MANIFEST.sha256` SHA-256 | `479b35c0c841d737a5806a3c472d8ffd965be6127e525c5d511708a88c43df8d` |
| Archive | `chalxius-0.5.0-back-to-the-future-paper-continuation.tar.gz` |
| Archive bytes | 1,791,856 |
| Archive members | 178 regular files |
| Archive SHA-256 | `5f5d71401fa7c6e2f132c5fa36bc8fde74d285ada27da891ace2b4bf2da2a3a4` |

The archive is built twice from the manifest allowlist and the resulting bytes
must be identical. It uses sorted USTAR regular-file members, numeric UID/GID 0,
empty owner/group names, fixed member time 0, and gzip time 0. It contains no
directory, symlink, duplicate, absolute, traversal, cache, bytecode, or unlisted
member.

## Automated checks

| Check | Final tree | Cold archive |
|---|---:|---:|
| Complete unittest suite | 537/537 PASS | 537/537 PASS |
| Native Paper/Evidence focused suite | 15/15 PASS | Included in complete suite |
| `scripts/self_test.py` | PASS | PASS |
| Official Skill Creator validator | PASS | PASS |
| Manifest exact path/hash set | 177/177 PASS | 177/177 PASS |
| Exact tree comparison | — | PASS |
| Release-only aggressive mutation audit | 51/51 killed | Bound by identical tree |
| Git whitespace check | PASS | — |
| Public Reader packet/schema validation | 3/3 PASS | — |

The 51 killed mutations cover Campaign exact scoping and frozen envelopes,
hidden-conjunct and philosophy-domain attack gating, Paper/worker public schema
reachability, Paper ancestry and revised-writing authority, verifier-visible
closure evidence, program–mathematics truncation, background hashes, L1/L2 mode
equivalence, source capabilities, adverse provenance, legacy premises, runtime
identity, two-phase admission recovery, completed/aborted round projection,
Reader math projection, multi-center forces, orbit-off pinned-card repulsion, and
critical exact-set/off-by-one guards.

## Public showcase privacy and determinism

The featured Reader artifact contains 175 nodes, 364 edges, 17 targets, and 7
themes. It was generated read-only from a private research topology with an
ephemeral 256-bit HMAC key that was discarded after export.

- Packet file SHA-256:
  `19cb5e0fc9f588305531276241207b1dc60cd2d002946dbfcad90b75e3e7244a`.
- Canonical packet SHA-256:
  `75df4f4fa769a30485b45f5198b033a72136d50f61c00a576e85ef1a73fad998`.
- Deterministic HTML SHA-256:
  `90207966b1779d8595f0ce8ee9275ff5a2f4abeaa313f0984647d19304cb3ae6`.
- Screenshot SHA-256:
  `3e012ee58684de1b4eb0504b34114a9bec9636365ca2cce4dea9a93404ece444`.

Every node ID, title, summary, intuition, importance, reasoning field, formal
field, provenance object/locator/snapshot field, and every edge ID/relation is a
64-character lowercase hash. The generator additionally rejects source strings,
source identifiers, user-supplied forbidden markers, and output paths inside the
private source project. The committed packet and generated HTML pass an
independent public-marker scan. Topology and structural enums remain visible by
the user's explicit design.

## Release contract hashes

| Contract | SHA-256 |
|---|---|
| `scripts/mathgraph/contracts.py` | `5bd04ce9dc5fea159805e50b921a225875124946ec26e3e119af4236d03d75e1` |
| `references/admission_contract.md` | `4879da333f75a90062742a4280cd855697e39a5f7f6cb01f53121a337f70a75c` |
| `references/reasoning_modes.md` | `ee2dc78be7ab0a999d4f4738e4ab31056475c13e2c7680f980d8d2da8a5c8d3a` |
| `INHERITANCE.lock.json` | `cf9f4d32b6fcd5fc4c078bb0ee4c7c15dfe05a5560446fe750fbfcdfb4547265` |
| `references/evidence_plane.md` | `27378cf3c32bf3c680313a0adc432f708b38136b0fc3138c30610c0243a4055a` |
| `references/paper_continuation_contract.md` | `6b27d559d2cbc7afd487bf35248579765725dc73e838e5067792a0c43f2aaa4e` |
| `assets/reader_html_app.js` | `b949ed26a059d71887ac1ca2e7661e7aa987070abc2d12c1438556a92b440fc7` |

## Scope boundary

These checks establish software, packaging, deterministic presentation, and the
stated workflow properties. They do not prove a mathematical theorem, establish
novelty, certify a private source graph, or Fact-admit any research claim. The
public showcase has `truth_effect="none"`.

Publishing this release does not replace the globally installed runtime and does
not migrate, backfill, reopen, or request redo of any active project.
