# Validation — Chalxius v0.9.10

This report records software, package, installation, live-project performance,
sensitive-information, and CHX-settlement evidence for **Chalxius 0.9.10 —
Terminal Seal Hygiene**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.9.10 |
| Release date | 2026-08-27 |
| Manifest entries | 265 |
| Package files, including manifest | 266 |
| Manifest SHA-256 | `3ceea6139f013908fa8cb2889bcb428fd49e25c3556f8758f05c11e09655a801` |
| Archive | `chalxius-0.9.10-terminal-seal-hygiene.tar.gz` |
| Archive bytes | 2,625,388 |
| Archive regular-file members | 266 |
| Archive SHA-256 | `6c2b33b413e715166af477ab58c34e10ab5227158cf6a33b0af4fc3363863798` |
| Checksum-file SHA-256 | `0bb89daed26d2a8f4a69e108e104788f0b41b17a20180335849e7cfc9e07a260` |

Two archive builds from the frozen tree were byte-identical. The archive
contains only sorted regular files rooted at `chalxius/`; it contains no
directory, link, device, or synthetic member. A cold extraction verified all
265 manifest rows and passed the bundled self-test.

## Routine release matrix

One routine profile was selected for the exact final manifest.

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.947 s |
| Changed-surface tests | 94 tests, PASS | 10.406 s |
| Semantic mutation audit | 32/32 killed | 50.475 s |

The matrix took 61.209 wall seconds. Each lane ran in an isolated manifest-only
copy and reported an unchanged source tree. The receipt file SHA-256 is
`c7af39b1fa4a69d1d386fc0c69e35a78c819cf1a194f4e8b8cdcdff99ce4af0c`.

The complete suite, full historical mutation registry, behavioral registry,
and whole-tree reconnaissance remain an opt-in forensic profile. They are not
an ordinary release gate.

## Focused regression surface

The release regressions establish that:

- production and repair planning update the selected Campaign target without a
  second checkpoint write;
- exact positive successors, overlapping supervision, and compatible
  multi-branch in-flight work preserve one coherent frontier;
- ordinary search/show cover immutable Research without treating Research as
  admitted Fact;
- structured exact source artifacts retain typed primary-source capability;
- supervisor review remains whole-product review across copy-on-write;
- two exact Finder metadata locations are non-authority while terminal tree and
  sealed-byte checks otherwise remain strict;
- one command reuses one exact-snapshot COW/repair and completion inspection,
  then invalidates it at Research and round publication.

No regression grants Candidate, Certification, Gateway, or Fact authority.

## Installed live-project canary

The global installation and candidate match exactly across all 266 package
files. Installed self-test passed. A read-only audit of the local-F0 project
reported:

| Signal | Result |
|---|---|
| Research entries | 1,778 |
| `current_ok` | true |
| `history_clean` | true |
| Graph errors | 0 |
| Workflow errors | 0 |

Three installed frontier runs for `campaign-62013035c1ff --limit 8` emitted the
same 42,528-byte output and SHA-256
`fbdcdfece328916ea3635f604b7f6530b4a4ed418e884690ace3c6da295baa89`.
Elapsed times were 1.90, 1.75, and 1.73 seconds.

The earlier six-run alternating canary measured a 2.4116-second installed
baseline median and a 1.8115-second candidate median. The profile reduced
repair-continuity checks from 8,758 to 151 and ingestion-receipt validations
from 327 to 60. Output identity was unchanged.

## Sensitive-information scan

The packaged tree was scanned for the local username and absolute user path,
private-key headers, common cloud access keys, GitHub/OpenAI/Slack token forms,
literal API-key/password assignments, and common personal-email forms. No true
positive was found. Two matches were benign identifiers in an example task card
and a contract revision string.

This bounded scan is release evidence, not a general secret-detection
guarantee. The exact package remains inspectable through `MANIFEST.sha256`.

## Installation and rollback

| Field | Result |
|---|---|
| Installer | `scripts/local_install.py` |
| Installed version | 0.9.10 |
| Candidate-to-installed tree | exact; 266/266 files unchanged |
| Installed manifest SHA-256 | `3ceea6139f013908fa8cb2889bcb428fd49e25c3556f8758f05c11e09655a801` |
| Previous runtime archived | yes |
| Direct rollback available | yes |
| Project reads / writes by installation | 0 / 0 |
| System restart | not performed |

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-22003bdd9fbe6523bbc7ed95e7a114ce22e0706be69b6af6753a4d82eb65fe15` |
| Canonical `record_sha256` | `a3fbced619132cc31b5440b3547e5ac62da0fd30b706c81bed5c46b0bb9a75af` |
| Record-file SHA-256 | `7a86be3a388cd967515065fa23e9527e302582a65b4592273938a8749c80e146` |
| Inventory SHA-256 | `2b0157058e3ddabf7970d5e51966f74652d505ff73b9d459b533b051c5f46f94` |
| Covered snapshot SHA-256 | `cfb7608e609d776783c6c47145979f9766d17e538b8eb130d34184e15c2d904b` |
| Observed / globally resolved | 217 / 217 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

Historical ledger bytes were not rewritten. Raw historical active flags may
remain as provenance, but none retains an unresolved issue under the current
global settlement.

## Research and truth boundary

Installation wrote no project byte. The live canary performed read-only audit
and frontier operations. This release created no Candidate Release,
Certification Decision, Gateway admission, or Fact. Software validation is not
a theorem proof.
