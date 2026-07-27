# Campaigns, Frontier, Audit, and Migration v4

Read this reference before changing campaigns, targets, frontier policy, audit behavior, or
upgrading a v1-v3 project copy.

## Campaign model

A campaign states one research objective, source claims, constraints, stop conditions, and a value
definition. Its targets are typed:

- `headline_proof`;
- `supporting_proof`;
- `communication`.

Only admitted fact ids may be proof targets. Communication targets may point to a fact, source claim,
report, or verification bundle but never enter proof-target closure. Archiving is append-only.
`TARGETS.txt` is a derived projection of active headline/supporting fact targets, not an independent
source of truth.

Every `source_claim_id` must resolve to a valid object in the project claim registry. Campaign
creation verifies this before writing, audit rechecks it as current workflow integrity, and
`plan-round` rechecks it before freezing the campaign snapshot. A dangling or removed source claim
therefore cannot silently enter a new task card.

Campaign creation also validates the actor and every initial target, including duplicate and
collision checks, before publishing anything. Initial proof targets require a caller-supplied
active-admitted-fact predicate. The complete `created` plus `target_added` ledger is staged and
published as one new campaign directory; a failed validation or publication leaves no partial
campaign.

## Actionable frontier

New V4 memory records a four-factor `decision_profile`: impact, information value, tractability,
and burden. Readiness is derived from dependency state and combines with tractability to form
feasibility. The workflow priority score is:

```text
0.35 impact + 0.25 information_value
+ 0.20 feasibility + 0.20 (1 - burden)
```

Legacy eight-metric v4 memory remains readable without rewriting and is deterministically projected
into those four factors. An unscored new item receives a neutral four-factor profile rather than
eight synthesized legacy fields. Do not mix both input forms in a new event. Read
[adoption_policy_v4.md](adoption_policy_v4.md) for the projection and experimental evidence.

The score is an ordering aid, never a mathematical status or novelty certificate. Collapse repair
lineages to active leaves by default, but do not silently close an unresolved literal claim. Use
`--history` for the full lineage and prefer explicit stop conditions over false precision.

Blackboard nodes become actionable only through `blackboard-promote-node`, which creates ordinary
memory with provenance. Promotion does not admit the node as a fact.

## Compatible audit

Audit dispatches validators by recorded evidence/schema version:

- `current_ok` evaluates current v4 state and new evidence;
- `historical_workflow_warnings` records readable legacy policy drift;
- `trust_debt` records evidence that remains usable historically but has not passed current gates;
- `history_clean` is false when warnings or debt remain.

Default audit fails on current graph/workflow errors, not merely on known historical warnings.
`audit --strict-history` additionally requires clean history. Never suppress a genuine new v4
error for compatibility.

## Legacy V3 to unified project inheritance

Treat the legacy V3 project as a read-only ancestor and the unified copy as a
new lineage. The copy becomes eligible for unified work only after its workflow
declaration is migrated to V4 and an explicit `mode-init` activation receipt is
recorded. Chalxius never starts an old V3 or other retired predecessor runtime.
Legacy facts keep their recorded V3 assurance; read-time interfaces
and V4 expert exports must label that assurance as inherited and must never
imply a fresh V4 review.

Classify inherited state before migration:

1. Immutable evidence such as facts, submissions, reviews, rounds, returns, artifacts, and
   acceptance objects remains byte-exact.
2. Shared append-only logs keep their exact V3 byte prefix. Every V4 suffix event receives a
   write-once V4 sidecar anchor; audit rejects prefix edits, unanchored wrong-engine suffixes,
   suffix edits, and suffix truncation while its anchor remains.
3. `TARGETS.txt` and its closure certificate are mutable derived projections. In V4 only active
   campaign proof targets may regenerate them; direct `set-targets` is denied and audit requires
   exact campaign/projection equality.
4. `project.json` is the only inherited declaration rewritten: workflow evidence becomes V4 and
   the V4 policy revision is recorded.
5. Blackboard, claims, conventions, campaigns, experiments, bundles, interfaces, append anchors,
   and migration receipts are additive V4 state. A nonempty pre-migration collision in a reserved
   V4 namespace fails closed.

Checksums and sidecars detect cooperative errors and wrong-engine writes; they are not OS security.
A local actor able to delete both an event and every independent local commitment can erase evidence.
Authenticated or ACL isolation remains outside this release.
The same limit applies in-process: public constructors expose no legacy-writer boolean, but
underscored identity-token fixture/staged-copy seams are cooperative internals, not a defense
against hostile Python reflection.

The Chalxius writer retains `writer_engine: "operate-mathgraph-unified"` in new
append anchors. Audit continues to accept the exact historical
`"mathgraph-chalk-version"` value as schema-lineage compatibility and hashes it
in place, so no historical anchor is relabeled or rewritten.

## Safe project-level copy command

Never make the active research root the destination. Choose a new sibling or otherwise disjoint path
that does not exist:

```bash
"$MGRAPH" --root "$UNIFIED_COPY" --role operator upgrade-project-copy \
  --source "$LEGACY_PROJECT" --dry-run
"$MGRAPH" --root "$UNIFIED_COPY" --role operator upgrade-project-copy \
  --source "$LEGACY_PROJECT" --actor OPERATOR
"$MGRAPH" --root "$UNIFIED_COPY" --role operator mode-init \
  --mode auto --actor OPERATOR --reason "Explicit unified activation"
```

Dry-run is read-only and does not create the destination. Apply:

1. rejects symlinks, special files, nested roots, an existing destination, a non-V3 source, and
   nonempty reserved V4 namespaces;
2. hashes the full legacy source tree;
3. copies into a unique same-parent staging root and requires exact tree equality;
4. runs the low-level workflow migration only in staging;
5. records a content-addressed migration receipt binding the source tree digest, source project
   declaration, assurance policy, immutable inventory, append-only prefixes, and mutable projection
   policy;
6. re-hashes the legacy source, requires it unchanged, and requires the migrated default audit to
   be current-clean;
7. renames staging to the requested destination without overwriting anything.

The result deliberately reports `cutover_status: not_performed`. Inspect default audit,
strict-history audit, every historical warning/trust-debt item, and a representative V4 continuation
before asking the user to select the unified root.

`upgrade-workflow --to 4` is the low-level fixture primitive. Its apply form requires
`--confirm-isolated-copy`. Use it only when a copy has already been created and independently
hash-checked; prefer `upgrade-project-copy` for legacy project inheritance because it records the
copy lineage.

The x-y swap canary copied a 39-file first-round source, preserved its 30-file strict immutable
inventory, bound the source tree in the receipt, continued the inherited JSONL prefix with anchored
V4 events, and finished current-clean with historical trust debt reported separately. This is
evidence for isolated canary use, not permission to switch the active project.

## Cutover and rollback

Cutover is a user decision, never an automatic migration side effect:

- before cutover, discard the unified copy and keep using the untouched legacy project;
- at cutover, freeze the legacy ancestor and explicitly select the unified project root;
- after cutover but before any V4 suffix, returning to the frozen legacy ancestor is lossless;
- after V4-only state exists, rollback means quarantine the unified branch and resume from the frozen
  legacy snapshot. Never down-convert, backport, or merge V4 state into the ancestor automatically.

Do not open the unified root with either legacy standalone writer. The unified
audit detects unanchored legacy-shaped suffix writes. A legacy engine's V4-root
guard is defense in depth only; the primary boundary is that one unified kernel
owns the selected writable root.

Discard pre-dev.2 experimental Chalk copies whose older migration receipt bound an entire JSONL file
as immutable. Do not synthesize a prefix length or rewrite that receipt. Recreate the canary from its
untouched legacy V3 ancestor so the new copy-lineage, prefix, sidecar, and assurance bindings are
honest.
