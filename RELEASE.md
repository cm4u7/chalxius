# Chalxius v1.0.7 — Campaign Attention Continuity

Chalxius 1.0.7 repairs Campaign working-memory continuity on large, branched
Research projects. Main can advance one route without silently losing an
unrelated attention centre or the exact context attached to it.

## What changed

- A target-local `plan-round` retires only the active head that its selected
  exact Research route actually replaces.
- Unrelated parallel heads remain active even when their own current workflow
  is complete. Main may still remove or reorder them explicitly.
- Context and its reason follow a unique replaced head to its successor.
  Genuine multi-successor ambiguity remains visible and unattached.
- The same exact Research may be used by several Campaigns or targets as a
  member, head, context, or landmark. Its creation Campaign is provenance,
  not ownership or an eligibility gate.
- Attaching a context absorbs only an otherwise identical unattached copy, so
  distinct reasons and real ambiguity are preserved.

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

The exact manifest-bound candidate passed 63 focused Campaign/frontier tests,
installer self-test and focused regressions, atomic installation, rollback
preparation, and exact candidate-to-installed comparison across all 269
manifest entries. A real-project canary successfully reused Research across
targets without replacing the current route.

Full evidence and exact hashes are recorded in [VALIDATION.md](VALIDATION.md)
and `RELEASE.lock.json`.

## Distribution

Release assets:

- `chalxius-1.0.7-campaign-attention-continuity.tar.gz`
- `chalxius-1.0.7-campaign-attention-continuity.tar.gz.sha256`

```sh
shasum -a 256 -c chalxius-1.0.7-campaign-attention-continuity.tar.gz.sha256
tar -xzf chalxius-1.0.7-campaign-attention-continuity.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

Publication creates no mathematical Fact.
