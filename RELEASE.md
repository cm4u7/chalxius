# Chalxius v0.8.0 — MathGraph First

Chalxius 0.8.0 makes the MathGraph the forward-compatibility surface. A
valid graph can be read and extended across runtime upgrades from its node and
edge hashes, dependencies, provenance, workflow stages, and owner boundaries.
Runtime locations, archives, migration ceremonies, and ordinary
worker-ingestion receipts remain diagnostic or process provenance; they are not
prerequisites for ordinary graph work or mathematical status.

## What changed

- Legacy and current graph records are operated directly when their semantic
  hashes, dependencies, provenance, stage, and owner checks are valid.
- The retired runtime-compatibility closure and its adapter/migration gate are
  removed from ordinary graph operations.
- A missing derived worker-ingestion receipt no longer blocks a complete
  hash-bound Research product with valid assignment provenance. Missing
  products, wrong-stage artifacts, owner/hash drift, verifier failures,
  Certification, Gateway, and Fact-authority violations still fail at their
  owning boundaries.
- Sealed writable directories remain readable as directory metadata; writable
  sealed regular files remain rejected. The preserved campaigns/inputs
  directory is accepted only as the declared non-Campaign input surface.
- Historical metadata and unfinished valid worker returns remain readable
  without rewriting mathematical Research or creating a second data plane.

The truth path is unchanged:

Research → Candidate Release → Certification Decision → Fact

## Validation

The frozen 253-entry manifest and 254-file runtime tree passed:

- strict architecture reconnaissance with zero errors and zero warnings;
- bundled self-test;
- changed-surface tests: 28/28;
- semantic mutation profile: 15/15;
- graph/runtime lifecycle focus: 35/35;
- deterministic archive generation and cold extraction;
- manifest, cache, and bytecode checks.

The routine matrix receipt uses
chalxius-release-validation-matrix-6 and has SHA-256
6d9f8e04968c67888e9b140209c6486d669e93b341a5b1b154d70ea36bc79fda.
Two valid unfinished worker returns were ingested as nontruth Research:
round-20260816T094813Z-079a0e70 and
round-20260817T040553Z-d50b6f19.

## Installation

The validated 0.8.0 tree is installed globally as version 0.8.0.

| Item | SHA-256 or value |
|---|---|
| Installed runtime identity | 943a66bc9d5ec76f5622de5b13cfda800e26c349e8b210fb63d00eae16ba32da |
| Installed runtime content | 7f951b3ef3dfd168ce91b2ed5a424af698a1601325ee0c79346fc054c3a63f84 |
| Installed archive-tree identity | a85671c716eabd1249bc49f63238a6e18550b9f8afc517ed70399b423bddbfc9 |
| Prior runtime identity | 82fe34deaf8d7d09899918e9507e1f0743d85fc4b0596c8cff80bdd246ff57de |
| Rollback | preserved as chalxius-prior-0.8.0 |

The installed tree matches the validated candidate exactly. No system restart
was performed.

## Public distribution

The release archive is:

- chalxius-0.8.0-mathgraph-first.tar.gz
- chalxius-0.8.0-mathgraph-first.tar.gz.sha256

The deterministic archive has 254 members, 2,496,311 bytes, and SHA-256
44f5badf9d20d0f871d278f24da2e46da668be8c821f2086c2bdd9538f629fca.
The checksum file has SHA-256
d41fdcc2e68afc7dce35ad639deb7ee11f6208b73d2c69665b2efefe9c6dd6b1.

To verify a downloaded archive:

```sh
shasum -a 256 -c chalxius-0.8.0-mathgraph-first.tar.gz.sha256
tar -xzf chalxius-0.8.0-mathgraph-first.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/self_test.py
```

Replacing an active global runtime is a protected cutover operation. Do not
replace a runtime that owns frozen task cards without an explicit, validated
cutover.

## CHX and truth boundary

The public CHX disclosure remains the continuous CHX-001 through CHX-035
lineage. Current release bookkeeping is nontruth operational evidence and is
not included as a second public issue namespace. No Candidate Release,
Certification Decision, Gateway admission, or Fact was created by this
architecture release. Hashes establish byte identity; tests establish only
the exercised software behavior.
