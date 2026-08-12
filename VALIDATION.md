# Validation — Chalxius v0.7.4

## Frozen release identity

| Field | Exact value |
|---|---|
| Version | `0.7.4` |
| Display name | `Bounded Main Routing` |
| Release date | `2026-08-12` |
| Skill manifest entries | `245` |
| `MANIFEST.sha256` SHA-256 | `80e8b1abc333c32786149b6e4794091aeefc0e8eaa55415b56252b356e205cf7` |
| Runtime content SHA-256 | `d6673f07691c4657d9e35d2ee6d743099960904d73fe44dc9c74a9c5e54ff5c7` |
| Archive | `chalxius-0.7.4-bounded-main-routing.tar.gz` |
| Archive bytes | `2372899` |
| Archive members | `246` |
| Archive SHA-256 | `dbad69ae6cb6ef5b1fff23fefbc73a98d3229b1737833f0bd67ff73ac4ec6d9e` |

The deterministic USTAR archive was built twice from the sorted exact member
set with fixed ownership and time metadata; the two outputs were byte-identical.

## Manifest-bound release matrix

The accepted receipt uses contract `chalxius-release-validation-matrix-4`,
contains all six required lanes, and records `one_manifest_identity=true`,
`source_unchanged=true`, and `lane_unchanged=true` for every lane.

| Phase | Lane | Result | Duration |
|---|---|---|---:|
| 1 | strict architecture reconnaissance | pass; 246 files; 0 errors or warnings; no orphan modules/features | 4.451 s |
| 1 | mutation-registry preflight | `148/148` exact targets | 0.093 s |
| 2 | behavioral feature gate | pass; `30` registered features | 18.233 s |
| 3 | full discovered suite | `846/846` pass | 133.417 s |
| 3 | bundled self-test | pass | 1.630 s |
| 4 | aggressive mutation audit | `148/148` mutants killed; source unchanged | 184.481 s |

| Receipt or inventory | SHA-256 |
|---|---|
| Final matrix receipt | `90ffcd665ab01bc35fcde437b317cef7ac0e59869fa38221d18ce43175ad7da7` |
| Final architecture inventory | `b3564ad4240e55088d2d44486011f527be74ad44ef9ce0dc0de070234b43e853` |
| Final architecture receipt bytes | `4896713078204fe426b3fe2719f0d5c8b353a10a0eb9b25c80297a990e3329cf` |
| Behavioral registry | `4ff43881e6c67a9d43141f0d8607a75e580ef089185b9992f577a743a9695e5c` |
| Capability registry | `2d9dabec4d9d0532e5275c91868058d1c733859e83d501afda052f05bc33a712` |

The final strict scan was rerun with bytecode writes disabled. It verified exact
manifest path equality and detected no generated cache artifacts.

## Focused 0.7.4 evidence

- Fifty-nine focused adverse-routing and two-subround Research tests passed.
- Current route creation and promotion are Main-only; workers return incident
  evidence rather than persistent abstractions.
- Current rules are English, mechanism-level, semantically compressed, and
  bound by per-field and total code-point limits.
- Current projects and newly frozen cards expose at most sixteen active routes;
  legacy cards retain compatibility with their historical contract.
- Compact worker bootstraps require an artifact-or-blocker first-output
  milestone and reuse the existing CHX path for architecture-caused repeats.
- No watcher, timer, new lifecycle state, normal-flow audit, package gate, or
  truth gate was added.
- An isolated English-text predicate benchmark measured approximately
  7.2–7.6 microseconds per call. It is telemetry, not a separate release lane.

## Cold extraction

A fresh extraction of the archive passed:

- `245/245` manifest hashes;
- bundled `scripts/self_test.py`; and
- no `__pycache__`, `.pyc`, or `.pyo` files.

## Protected global installation

The final candidate was installed with `runtime_cutover.py`. Because both the
protected project and lifecycle code had changed, the cutover used the explicit
full-audit path once and retained that result in memory for exact post-swap
validation. It did not run a second semantic audit.

| Field | Exact value |
|---|---|
| Installed runtime identity | `6063cd16304ca1e32fea728c5d9c8e55e790355bd36bad8c007c86cbc2d32fa6` |
| Installed runtime content SHA-256 | `d6673f07691c4657d9e35d2ee6d743099960904d73fe44dc9c74a9c5e54ff5c7` |
| Runtime archive tree SHA-256 | `a29a3ac0c3f9c800506b97402e04240b303f51b6266153f18c4eda191086a06e` |
| Protected project state SHA-256 | `5a70a5fc5d0d9d662cf0d42b302b916a129ff9a1f079ef211b10ff33ab3b4195` |
| Protected Research rounds | `136`, all terminal |
| Full semantic audits during cutover | `1` |
| Duplicate post-swap semantic audits | `0` |
| Rollback runtime | `chalxius-rollback-0.7.3-pre-0.7.4-20260812` |

The installed runtime reports version `0.7.4`, matches the frozen manifest,
passes its bundled self-test, and leaves the protected project
`current_ok=true`.

## CHX and PHX receipts

The public CHX lineage enumerates CHX-001 through CHX-022. The 0.7.4 successor
ledger is `run-20260812T073631884601Z-53f28d3790b8`, SHA-256
`ca3d5634586755ba179a8d5c4001c174ec60e1ec05cae945cfa81800d93c3ec0`;
its architecture report SHA-256 is
`b7d1676a269cf1fe16e1cb9e3b698b479a1decdc981964c930eb7cb1755f66e5`.

The adopted advisory PHX successor is
`run-20260812T073119641576Z-a5cb7d922e7a`, SHA-256
`0db62d4656042f8dfea024f20ba4e13623c4c1f26ac12358f1dbc70c3d044f36`.
Its route adoption remains nontruth and Main-governed.

## Contract hashes

| Contract | SHA-256 |
|---|---|
| `INHERITANCE.lock.json` | `7b8a585e876524c707c88232275f5f99ff6d7aa7081a468a5e54e9e8faab41e9` |
| `KNOWN_LIMITATIONS.md` | `3cd9d312c7a5cbcfdc7986a4f6a62a750cd48475d4a06803c8009acd1355e0cc` |
| `references/adverse_routing_evolution.md` | `0c8802a1bedbdeac7ac1e91538638bf0d8a77d311c38982fb9aa215ae5530e3c` |
| `references/v5_release_traceability.md` | `d8ad147d22122afccf1cb19f4da267becb80cd538d8387a595117a6ce71fca96` |
| `SKILL.md` | `7d00183914c468d65c160c0e3a90b4266452edbe7442f414dd50c9a3a77c0b4f` |
| `scripts/mathgraph/adverse_routing.py` | `5f796ef7f520582c319146afb23f3d044f652d550e9547c52a8041e32c73b480` |
| `scripts/mathgraph/v5_lifecycle.py` | `e84e969e5b973c8266341eed6403946280c124c3933f6b2b4b4ea6117014b270` |

## Claim scope

Hashes establish byte identity. Tests establish only exercised properties.
Mutation scores establish only detection of registered faults. Research
artifacts remain nontruth unless they separately pass Candidate Release,
independent verification, Certification, Gateway, and Fact admission.
