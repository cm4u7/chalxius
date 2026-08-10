# Validation — Chalxius v0.7.0

## Frozen release identity

| Field | Exact value |
|---|---|
| Version | `0.7.0` |
| Display name | `Failure-Informed Efficiency` |
| Release date | `2026-08-10` |
| Skill manifest entries | `242` |
| `MANIFEST.sha256` SHA-256 | `9cb93afb90d90e8f8cdfd7cba59bbce3e3c68f7b4181f9594d561cc878942468` |
| Runtime content SHA-256 | `6078c75b0ae64f17502450d4a6e1b67047f6e5955f45202bbfe56243eeb78950` |
| Archive | `chalxius-0.7.0-failure-informed-efficiency.tar.gz` |
| Archive bytes | `2352031` |
| Archive members | `243` |
| Archive SHA-256 | `94637f21f221761532936c07074a5b98d606cd25f57aca326c754e37d3b2dc38` |

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
| 1 | strict architecture reconnaissance | pass; 0 errors, 0 warnings, 0 orphan modules |
| 1 | mutation-registry preflight | `147/147` exact single targets |
| 2 | behavioral feature gate | pass; `29` registered features |
| 3 | full suite | `838/838` pass |
| 3 | bundled self-test | pass |
| 4 | aggressive mutation audit | `147/147` mutants killed; candidate unchanged |

The snapshot-sensitive mutation audit ran only after baseline phases. Any
architecture or registry-preflight failure would have short-circuited the
expensive lanes.

| Receipt or inventory | SHA-256 |
|---|---|
| Final matrix receipt | `a049f1074938cab779f80fd5257a3a40e15c3a5baebc39a1d9c2646653aefdc1` |
| Final architecture inventory | `6c85ea575ebe97bbfc8a60f34977a9f085c33fc5cdbb83def28f8532342abfe9` |
| Behavioral registry | `f41dd06ed1ea20febd8cea597921d45d73ade7e1932aef38f0810e61ee892a0f` |

## Focused 0.7.0 regression evidence

- Selected-ancestry Paper-continuation lookup completes real target `show` and
  39-Fact closure reads without project-wide Research recursion.
- Typed closure authority expands active admitted predecessors only for the
  exact dual typed request; direct, empty, inactive-root, and inactive-
  predecessor cases are separately checked.
- A current interpretive artifact carrying a frozen proof-boundary signal
  receives proof-logic supervision; ordinary interpretive insight does not.
- Public disclosure accepts one exact later resolved `supersedes` successor and
  rejects unresolved, absent, backward, cyclic, ambiguous, or differently
  related substitutes.
- The mutation registry contains one exact probe for each reproduced regression
  surface and validates all targets before starting the expensive audit.

## Cold extraction

A fresh extraction of the release archive passed:

- `242/242` manifest hashes;
- bundled `scripts/self_test.py`;
- no `__pycache__`, `.pyc`, or `.pyo` files.

## Protected installation

The final candidate was installed through `runtime_cutover.py` after one fresh
deep audit of the protected project. Preflight and postflight both recorded
`audit_current_ok=true`; the postflight reused the same exact snapshot rather
than repeating semantic reconstruction. The installed tree is byte-identical
to the candidate, its self-test passes, and the prior runtime is retained as a
rollback tree.

| Field | Exact value |
|---|---|
| Installed runtime identity | `12df834343960f4e968227f784e243d8de17109f5790706dcde1234b24b8e100` |
| Project state SHA-256 | `670943df121e997ccf624f69f2e6e5d798bdba40196a9f40c751eea7754278ff` |
| Deep audits performed during cutover | `1` |
| Post-swap duplicate semantic audits | `0` |

## Contract hashes

| Contract | SHA-256 |
|---|---|
| `INHERITANCE.lock.json` | `5dd08bcf0e9953854d92fca02f489d42cb4e25c415198781016844afce489145` |
| `KNOWN_LIMITATIONS.md` | `a5f2ae581fdfeb3db4cebb0a2f28c7f7c39f1412cf38aa07616694e6ef2eda6a` |
| `references/v5_release_traceability.md` | `ec70e72e7fc6e22dbe9f4ef035232bb48720d70fe580a650d14040fa77217d2d` |
| `scripts/mathgraph/adverse_routing.py` | `ca664f332edfbc299e16716ea5a4bfdc16c7ed6e012ac68c8e5e67fa4a5cbf4a` |
| `scripts/release_validation.py` | `d132a19e80c823cab9c08a6dd100797d27046489582e9d708194cb6faace282b` |
| `scripts/aggressive_bug_audit.py` | `9e27c708ef03f461635aa511755d7e870264d22571b63cb32878d7766379c393` |
| `scripts/runtime_cutover.py` | `06aa0e4f4bbee4ab10ca9c4ee5b93f463af420a23e7d2871f1df641a57959b8a` |
| `scripts/chx_ledger.py` | `27e25697bf67f4bc6fcbe185e98be79fdf0e99caa464eedd994dde20580c8416` |
| `scripts/mathgraph/paper_continuation.py` | `a8cc713213a49efb67d4f08755421f3a64a2634c7a6ce2f99117c81f203cf0b2` |
| `scripts/mathgraph/v5_lifecycle.py` | `5b1ac7738faff5507eb791883faddda8910bfa7126d4c640f51c9f346e4bd451` |

## CHX disclosure boundary

The release binds the exact append-only field lineage from qualified CHX-001
through CHX-006. The current ledger SHA-256 is
`9419d638cd15549bd0006d4bad2c44174d975ab02aaf7da11e88daa9f2d57b67`;
its generated architecture report SHA-256 is
`cad4c49ae42bc1e734e8cb0222ed958fe9588f0b212a88a0551a50a7504ef7b6`.
Private JSONL and Research bytes are not distributed. Public disclosure passed
the exact owner, predecessor, document, issue enumeration, and ledger-hash
checks.

## Claim scope

Hashes establish byte identity. Tests establish only exercised properties.
Mutation scores establish only detection of enumerated faults. None of these
receipts substitutes for fresh independent verification, Certification, or Fact
admission.
