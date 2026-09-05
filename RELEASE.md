# Chalxius v1.0.23 — Research Selection Continuity

Chalxius helps Main choose the next research step with the work already done
in view. This release adds exact prior-work reminders and clearer agent
instructions, and includes the frontier improvements since v1.0.17.

## New in this release

- Production planning shows earlier completed or in-flight assignments for the
  exact selected Research ID. The reminder is nonblocking: intentional reruns
  remain legal. `round-status --research-id ID` expands complete exact history.
- Main reads relevant context, searches known obstructions as well as desired
  results, and checks whether existing local results satisfy the actual next
  input. It does not infer novelty from a new ID, require a DAG, or declare
  automatic theorem assembly.
- Agent selection is difficulty-based: **Astra max** for difficult or
  error-prone work; **Sol max** for clear, bounded work. Explicit user choices
  take precedence. One author-independent supervisor can cover both applicable
  source/proof scopes and later COW.
- A nested metadata object in the flat Research creation envelope now produces
  a warning without being rejected or rewritten.
- Supervisor instructions explicitly permit the exact attacked production
  card's direct typed input capabilities. Real missing or hash-drifted bytes
  remain errors; sibling cards and arbitrary ancestors grant no authority.
- Installation identity uses the four formally maintained projections.
  Historical explanatory documents no longer have to repeat an exact current
  version sentence to pass self-test.

## Included frontier improvements

Routine frontier output has a final 32 KiB JSON budget. Exact identities,
counts, digests and drill-down commands survive prose reduction. Full
maintenance reads an all-target index followed by each target's full landmark
reasons; context reasons are expanded around decisions.

Planning preserves explicit Main choices. Named head replacement and precise
single-placement context reattachment do not erase unrelated parallel work.
Repair source and trigger artifacts with the same local role are disambiguated
by their actual origin only when their bytes collide. Direct primary-source
inputs avoid reactivating irrelevant historical source checks.

## Defaults and boundaries

Semantic splitting and Fact admission remain off by default. Routine
supervisors and packagers do not assess or recommend splitting. Campaigns are
many-to-many working-memory overlays, not node ownership or truth gates.

Graph Browser and graphical graph generation remain temporarily unavailable.
Textual Research, search, frontier, supervision and explicitly requested Fact
certification remain available.

## Validation and distribution

The candidate passed bounded regression lanes, candidate and installed
self-tests, and real-project exact-history/frontier canaries. The release
archive contains the exact installed bytes. Identity, file-set, checksum and
sensitive-data checks passed; publication does not repeat the installation
test matrix. See [validation evidence](https://github.com/cm4u7/chalxius/blob/v1.0.23/VALIDATION.md).

Assets:

- `chalxius-1.0.23-research-selection-continuity.tar.gz`
- `chalxius-1.0.23-research-selection-continuity.tar.gz.sha256`

```sh
shasum -a 256 -c chalxius-1.0.23-research-selection-continuity.tar.gz.sha256
tar -xzf chalxius-1.0.23-research-selection-continuity.tar.gz
cd chalxius
python3 -B scripts/local_install.py
```

[Release page](https://github.com/cm4u7/chalxius/releases/tag/v1.0.23).
Software validation does not certify a mathematical claim.
