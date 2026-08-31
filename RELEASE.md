# Chalxius v1.0.9 — Working Memory Maintenance

Chalxius 1.0.9 makes Campaign/frontier state a compact and dependable working
memory on projects with long Research and round histories. It preserves exact
mathematical content while reducing routine recovery cost and accidental loss
of parallel attention.

## What changed

- `round-status` without an id cheaply enumerates every round identity and
  deeply validates only unresolved candidates. `round-status --all` remains
  the explicit complete-history diagnostic.
- The ordinary frontier retains every active head but bounds nested context,
  recent attainment, landmark, and workflow previews. Counts and digests bind
  the full state, and exact/diagnostic reads remain available.
- `add_head` and disposition-bearing `retire_active_head` are the prospective
  attention operations. Omitted co-heads survive ordinary full-list input;
  retirement detaches rather than deletes context.
- A roughly 50-minute task heartbeat gives Main a visible opportunity to review
  every target, complete sparse-landmark identity, bounded in-flight work, and
  exact Research searches. It skips repair/publication phases, starts no Fact
  packaging, and never interrupts work already running.
- Ordinary prospective V5 rounds no longer create a default one-node
  Blackboard snapshot. Exact promoted queries or explicit write-space work
  still bind Blackboard, and historical snapshots remain readable.
- Release identity authoring is now one deterministic, idempotent repository
  operation; the existing manifest-bound consistency check remains.

These are coordination changes only. Chalxius does not infer mathematical
completion, select a research direction, dispatch work, rewrite Research, or
change package, verifier, Gateway, or Fact authority.

## Preserved boundaries

- The v1.0.5 split opt-in rule remains active: routine supervision and Fact
  packaging ignore splitting, while a new low-level split requires explicit
  current authorization.
- Campaign and frontier remain nontruth working memory.
- Installation remains the software-correctness boundary; publication reuses
  the exact installed bytes and checks only archive identity, checksum, file
  set, and absence of sensitive local data.

## Graph Browser status

Graph Browser and graphical graph generation remain temporarily unavailable
as supported release capabilities. Textual Research, exact search, Campaign,
frontier, supervision, COW, Fact packaging, verification, and certification
remain available.

## Validation

The exact manifest-bound candidate passed 150 focused tests and 112 tests in
two supplementary lanes, followed by installer self-test and focused
regressions, atomic installation, rollback preparation, and exact
candidate-to-installed comparison across all 270 manifest entries. The current
CHX inventory verifies all 266 observed issues as disposed by the installed
integrated-repair lineage, with no Research or truth effect.

Full evidence and exact hashes are recorded in [VALIDATION.md](VALIDATION.md)
and `RELEASE.lock.json`.

## Distribution

Release assets:

- `chalxius-1.0.9-working-memory-maintenance.tar.gz`
- `chalxius-1.0.9-working-memory-maintenance.tar.gz.sha256`

```sh
shasum -a 256 -c chalxius-1.0.9-working-memory-maintenance.tar.gz.sha256
tar -xzf chalxius-1.0.9-working-memory-maintenance.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

Publication creates no mathematical Fact.
