# Chalxius v1.0.5 — Split Opt-In Repair

Chalxius 1.0.5 makes semantic splitting an explicit exception. Every new
Research-side or Fact-side split requires the current user-authorized planning
choice. Diagnosis, supervision, and ordinary one-to-one repair remain routine;
historical split bytes remain readable. Nothing in this release changes the
mathematical authority boundary.

## Graph Browser status

**Graph Browser and graphical graph generation are temporarily unavailable.**
They are not supported release capabilities in v1.0.5. Historical or
experimental Reader code, assets, and command entries may remain in the source
tree, but their presence is not a compatibility promise and they should not be
used as a production interface until the browser is redesigned.

This withdrawal affects presentation only. Research storage, exact search,
Campaign and frontier operations, textual graph inspection, supervision, COW,
Fact packaging, verification, and certification remain in scope.

## Split opt-in boundary

- `needs_split` is an advisory diagnosis, not an authority grant.
- A new schema-v3 split production plan requires exact member selection plus
  the one-shot `--user-authorized-split` flag.
- The flag is not persisted into Research, cards, receipts, frontier state, or
  replay arguments; later split work therefore requires a fresh user choice.
- Supplying the flag for a generic frontier or an all-ordinary batch is rejected
  as an ambiguous or unnecessary use.
- Existing split cards, returns, ingestion paths, and recovery remain readable.
- Ordinary source/proof supervision, mixed-product diagnosis, and one-to-one
  COW remain available without this authorization.

## Dormant repair and frontier projection

An explicit inactive disposition on a productless repair keeps that repair as
searchable history but removes it from live COW and frontier routing. Published
repair products still project normally. This is a read-time working-memory
projection, not a new lifecycle state or compatibility layer.

The current local-$\mathbb F_0$ Campaign was reconciled at generation 194. It
contains four targets: two research-open targets with current heads, and two
targets that legitimately remain `needs_main_choice`. For the two targets
touched by this repair:

- both repaired targets have current active heads and no stale head;
- three paused split ids are absent from target decision surfaces and the
  workflow queue;
- one completed negative branch no longer appears as active work; and
- immutable Research, rounds, returns, Candidate, Fact, and graph bytes were
  not rewritten.

## Validation, installation, and publication

Installation is the correctness boundary. The exact candidate passed the full
suite, focused split/frontier regressions, installer self-test, atomic swap, and
candidate-to-installed manifest comparison. Publication does not repeat those
tests. It checks the intended archive, checksum sidecar, repository file set,
and absence of local paths or secrets. Mutation and forensic matrices are
diagnostic tools, not publication gates.

## Intentional boundaries

- Fact packaging remains asynchronous and may be deferred while Research grows.
- Main remains responsible for mathematical direction and any future split
  authorization.
- Legacy 0.x authority remains readable and is not silently migrated.
- No automatic scheduler, inferred authorization, compatibility layer, second
  lifecycle, or truth effect was introduced.
- Graph Browser and graphical graph generation remain outside the supported
  v1.0.5 capability surface.

## Distribution

The final manifest, installed-tree identity, sensitive-information scan, CHX
settlement, PHX adoption, and deterministic archive identity are recorded in
[VALIDATION.md](VALIDATION.md) and `RELEASE.lock.json`.

Release assets:

- `chalxius-1.0.5-split-opt-in-repair.tar.gz`
- `chalxius-1.0.5-split-opt-in-repair.tar.gz.sha256`

```sh
shasum -a 256 -c chalxius-1.0.5-split-opt-in-repair.tar.gz.sha256
tar -xzf chalxius-1.0.5-split-opt-in-repair.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

Version 1.0.5 was published on 2026-08-31 at
<https://github.com/cm4u7/chalxius/releases/tag/v1.0.5>. The annotated tag
resolves to release commit `bb9f552180ac740740e3ef328cf64464ec298be9`.
Publication creates no mathematical Fact.
