# Validation — Chalxius v0.6.7

## Frozen release identity

| Field | Exact value |
|---|---|
| Version | `0.6.7` |
| Display name | `Plain-Language Attack Recommendations` |
| Release date | `2026-08-05` |
| Skill manifest entries | `241` |
| `MANIFEST.sha256` SHA-256 | `b7231474bf67018c58205735337fc997f54195bdb4162260745977b132f10c9d` |
| Archive | `chalxius-0.6.7-plain-language-attack-recommendations.tar.gz` |
| Archive bytes | `2330636` |
| Archive members | `242` |
| Archive SHA-256 | `ef99948624d849070642cb9826780a0ef4167d26c0211d6e982a455cfd13b9c5` |
| Candidate runtime identity | `6feac856ca949045d155c2470ca15cb50a7e4e5ed27e80e08301788269ec2cec` |

The archive builder independently produced the archive twice and required
byte-for-byte equality. It also required the archive member set to equal the
sorted manifest plus `MANIFEST.sha256`, with fixed ownership, modes, and mtime.

## Final manifest-bound matrix

The accepted receipt uses contract
`chalxius-release-validation-matrix-4`, contains all six required lanes, and
records `one_manifest_identity=true`, `source_unchanged=true`, and
`lane_unchanged=true` for every lane.

| Phase | Lane | Result |
|---|---|---|
| 1 | strict architecture reconnaissance | pass |
| 1 | mutation-registry preflight | `142/142` exact single targets |
| 2 | behavioral feature gate | `59/59` probes; `25` features |
| 3 | full suite | `801/801` pass |
| 3 | bundled self-test | pass |
| 4 | aggressive mutation audit | `142/142` mutants killed; candidate unchanged |

The snapshot-sensitive mutation audit ran only after baseline phases. Any
architecture or registry-preflight failure would have short-circuited the
expensive lanes.

| Receipt | SHA-256 |
|---|---|
| Final matrix receipt | `3244d7ba431cf9ba6a3914ecbac6e2cba9cac947d436f7bad312997d9a21e078` |
| Behavioral gate receipt | `fc1f449c1a7472b9df6581da19725804ae937cc82555eac024eef4cb38c5df24` |
| Behavioral registry | `dc82f18e92966a942fc3b81a402bb73c898e112f35fb8ab259e324269835e57a` |

## Focused 0.6.7 regression evidence

The adverse recommendation contract is
`chalxius-attack-route-recommendations-2`.

- The positive regression requires the exact reviewed `what_it_checks`
  sentence for each concise recommendation.
- A tampered explanation is rejected.
- An unknown family is omitted from the default report, and its worker-authored
  technical instruction does not leak.
- Technical detail remains available through `--full`; concise recommendations
  remain inert until explicit user approval.

## Cold extraction

A fresh extraction of the release archive passed:

- `241/241` manifest hashes;
- bundled `scripts/self_test.py`;
- no `__pycache__`, `.pyc`, or `.pyo` files.

Skill Creator validation also returned `Skill is valid!`.

## Contract hashes

| Contract | SHA-256 |
|---|---|
| `INHERITANCE.lock.json` | `b057eb65f2db6276d38e2404eb079bf48d10d1a1ab67ef5c11136be352211155` |
| `KNOWN_LIMITATIONS.md` | `c53ec4e3d7d9618e35073f40368705c5f206a6df42434c5891d873cecb016bc5` |
| `references/v5_release_traceability.md` | `aeeda68089f0bf45c6278da4ecf142348a024dac4941f8ed18e843e8b9484a9b` |
| `scripts/mathgraph/adverse_routing.py` | `ca664f332edfbc299e16716ea5a4bfdc16c7ed6e012ac68c8e5e67fa4a5cbf4a` |
| `scripts/release_validation.py` | `d132a19e80c823cab9c08a6dd100797d27046489582e9d708194cb6faace282b` |
| `scripts/aggressive_bug_audit.py` | `fa1dcc47e24b0125a69395911cc2c55911193c7166e64bedb73b6983cf1e2d31` |
| `scripts/runtime_cutover.py` | `06aa0e4f4bbee4ab10ca9c4ee5b93f463af420a23e7d2871f1df641a57959b8a` |
| `scripts/chx_ledger.py` | `1e8da18f6541b7609cfcf50b6867f24c8731ca51b759394c1708a1730710c33e` |

## CHX disclosure boundary

The bundled canonical public CHX registry and self-test pass through the shipped
public lineage ending at qualified CHX-109. The 0.6.7 plain-language report
repair is additionally identified by its project-bound qualified owner
`run-20260805T135745960462Z-8b9e3b4057f3/CHX-005`; its private ledger bytes are
not distributed and no canonical-public-lineage preflight is claimed for that
private field chain.

## Installation boundary

The candidate passed protected-cutover dry-run validation, but no global runtime
replacement was performed. Publication of the validated archive and replacing a
maintainer's active installation are intentionally separate decisions.

## Claim scope

Hashes establish byte identity. Tests establish only exercised properties.
Mutation scores establish only detection of enumerated faults. None of these
receipts substitutes for fresh independent verification, Certification, or Fact
admission.
