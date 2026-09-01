# Chalxius v1.0.14 — Durable Campaign Memory

Chalxius 1.0.14 makes long-running Campaign memory more durable under head
replacement, landmark maintenance, source-review reuse, and continuous Main
turns. These changes affect coordination only; Research and Fact authority are
unchanged.

## What changed

- The same Research may be an active head and a historical landmark in one
  target. Its use in another Campaign remains independent and many-to-many.
- `promote_active_head` transfers the replaced head's contexts atomically to
  the explicitly named successor. Concrete attachments absorb obsolete null
  copies without deleting genuinely distinct reasons.
- A replaceable per-Campaign maintenance clock records the last full review and
  the next 50-minute deadline. Main commands surface an overdue, nonblocking
  advisory; the clock does not dispatch work or interrupt running agents.
- A completed source review can remain provenance for a proof or internal task
  without recursively making its old source bytes a new planning capability.
  New source claims and source-scope supervision retain exact source checks.

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

The exact manifest-bound candidate passed 183 changed-surface tests, two
focused lanes of 66 and 58 tests, complete self-test, installer regressions,
atomic installation, rollback preparation, and exact candidate-to-installed
comparison across all 271 manifest entries. A real-project canary read live
generation 372 and preserved three active-head/landmark overlaps without
changing heads or contexts.

Full evidence and exact hashes are recorded in [VALIDATION.md](VALIDATION.md)
and `RELEASE.lock.json`.

## Distribution

Release assets:

- `chalxius-1.0.14-durable-campaign-memory.tar.gz`
- `chalxius-1.0.14-durable-campaign-memory.tar.gz.sha256`

```sh
shasum -a 256 -c chalxius-1.0.14-durable-campaign-memory.tar.gz.sha256
tar -xzf chalxius-1.0.14-durable-campaign-memory.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

Publication creates no mathematical Fact.
