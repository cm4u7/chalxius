# Campaigns, Frontier, Audit, and Migration v4

> **V5 boundary.** Campaign and target mechanics remain available in a V5
> project, but the V3-to-V4 migration procedure preserved later in this file is
> rollback history only. V5 never upgrades or inherits authority from a V1-V4
> root. Keep historical roots read-only and start V5 in a separate root with an
> empty Fact Graph. Generate `PROJECT_BACKGROUND.md` only on explicit user
> instruction; once present, read it by default as nontruth context. In current
> V5, Campaign frontier use is likewise explicit: never infer it from `ACTIVE`.
> A Campaign is selected only by exact id. Main may create it explicitly and
> bind a new Research root atomically with `memory-add --campaign`; no hidden
> intake compiler or `ACTIVE` inference selects it. That immutable
> `metadata.campaign_id` is creation provenance only; Campaign membership is a
> separate many-to-many nontruth overlay.

Read this reference before changing campaigns, targets, frontier policy, audit behavior, or
upgrading a v1-v3 project copy.

## Campaign model

A campaign states one research objective, source claims, constraints, stop conditions, and a value
definition. Its targets are typed:

- `headline_proof`;
- `supporting_proof`;
- `research_goal`;
- `communication`.

`campaign-create --input` accepts exactly `name`, `objective`,
`source_claim_ids`, `targets`, `constraints`, `stop_conditions`, and
`value_definition`. `campaign-update --input` accepts exactly `type` and an
object `payload`; `type` is one of `constraint_added`,
`stop_condition_disposition`, `value_definition_updated`, or `note`. The CLI
also exposes these fields in the corresponding `--help` text.

Only admitted fact ids may be proof targets. A `research_goal` is added only
after Campaign creation and names one exact Research root in the same project.
That target makes the root a member of this Campaign even if it was created
unbound or with another Campaign as provenance. It is durable nontruth
direction: it never enters proof-target
closure, schedules a round, closes itself, or affects Candidate/Fact state.
Communication targets may point to a fact, source claim, report, or verification
bundle but never enter proof-target closure. Archiving is append-only.
`TARGETS.txt` is a derived projection of active headline/supporting fact targets, not an independent
source of truth. Its certificate loads only those exact proof targets and their
transitive Fact predecessors; a Campaign containing only `research_goal` or
communication targets reads zero Facts during synchronization.

Every `source_claim_id` must resolve to a valid object in the project claim registry. Campaign
creation verifies this before writing, audit rechecks it as current workflow integrity, and
`plan-round` rechecks it before freezing the campaign snapshot. A dangling or removed source claim
therefore cannot silently enter a new task card.

Campaign creation also validates the actor and every initial target, including duplicate and
collision checks, before publishing anything. Initial proof targets require a caller-supplied
active-admitted-fact predicate. The complete `created` plus `target_added` ledger is staged and
published as one new campaign directory; a failed validation or publication leaves no partial
campaign.

## Explicit V5 Campaign envelope

Main may name an existing Campaign id. A new root may record creation
provenance atomically with
`memory-add --campaign CAMPAIGN_ID --input RESEARCH.json`; the command validates
the Campaign before semantic identity is fixed and revalidates it under the
write lock before publication. A payload/flag mismatch fails before any
immutable Research byte is written. The user need not use Campaign vocabulary:
Main may translate the stated objective into an explicit Campaign choice, but
the program never fuzzy-matches or consults `ACTIVE` for selection. The stored
creation Campaign is provenance only, not membership, ownership, or a later
planning predicate.

Use `frontier --campaign CAMPAIGN_ID` or `plan-round --campaign CAMPAIGN_ID`
only when Main deliberately chooses that durable objective. Explicit
`plan-round --campaign ... --memory-id ...` accepts any exact Research in the
current project and records an ordinary Campaign member link in the existing
Campaign event log plus the frozen round receipt. Target, active-head, context,
landmark, and recent-history roles are Campaign-local member roles. The same
Research may be an ordinary member or carry different roles in several
Campaigns, with no Research rewrite or truth effect. Generic scoped selection
does not scan this membership set: it stays inside the Campaign's explicit
active `research_goal` roots and current active-head successor corridors, in
ordinary four-factor order with no score cutoff.

The ordinary Main-facing `frontier` decision surface separates
`goal_coverage` from the bounded `workflow_queue`. Exact Research workgroup,
COW, round, return, supervision, repair, and disposition bytes derive what has
already been covered and the next action for each active `research_goal`.
Missing same-project roots are shown as `orphaned`; a different creation
Campaign is valid and remains visible. Orphans do not disappear or block
unrelated work. When no explicit Campaign filter is supplied,
the current `ACTIVE` Campaign may be shown as an `active_hint` only. That hint
does not filter the global queue, select Research, dispatch work, or authorize a
scoped plan. Main compares the goal view with the queue and chooses explicitly.
The same read compares every checkpoint active head with exact immutable
workflow successors. A stale head exposes its productive terminal route and
clean terminal review evidence separately, while `checkpoint_refresh` advises
Main to exact-search and reconcile dynamic working state after semantic
judgment. A manual checkpoint is optional; its local sequence is not the live
frontier generation and never makes a current working frontier stale. Refresh
advice is based only on live state and exact semantic-successor mismatch, not
checkpoint presence or generation arithmetic.
After context compaction or handoff, Main rereads the live frontier, in-flight
rounds, historical landmarks, and material old Research, then steps back to
review the route. An active integrated repair or installation delays this
Research-recovery pass until Research resumes. Before the next cut, bounded
exact search assigns each material match `reference_only`, `attach_context`,
`promote_landmark`, or `promote_active_head`. This is an advisory capability,
not a timer or gate.
Historical COW Research is recognized by its exact kind, relation, source,
product, and supervision-trigger edge even when it predates the optional
hash-bound repair-spec projection. No checkpoint updates itself.
For each valid attained checkpoint, the same read projects only exact recorded
production, supervision, and canonical COW successor shapes. It displays
bounded routes whose terminal Research has not already been named by the
checkpoint, while retaining full counts and digests. These summaries have
`selection_effect=none`: Main decides whether they are relevant, whether a
checkpoint should later change, and what work—if any—should follow.

When Main selects Research for a new round, an exact existing 12-hex Research
id literally present in its claim, content, rationale, or source is frozen as
direct predecessor context together with exact path/SHA-256/role artifacts.
This lexical convenience makes named graph nodes operable if the structured
relation was omitted; it ignores nonexistent checksum-like tokens and performs
no fuzzy or mathematical relevance inference. Existing frozen cards are not
rewritten.

Before writing a scoped round, planning revalidates the Campaign, exact
same-project Research selection, registered
source claims, and active proof targets. It then freezes one bounded snapshot
below the round and puts a compact `chalxius-v5-campaign-scope-3` binding in the
manifest and cards: objective,
active typed targets, constraints, value definition, stop conditions, and an
exact ordered event-prefix commitment with its count, terminal event id, and
digest. It does not copy historical update bodies. Scope 1 remains readable
only for immutable existing rounds, and scope 2 remains readable historical
compatibility. Later tail events do not mutate a card;
snapshot damage, frozen-prefix rewrite/reorder/truncation, mixed Campaign ids,
or a missing Campaign fails closed. The snapshot size cap guards anomalous
current state and is not a project-age or event-count limit.
A bound V5 worker may retrieve only that frozen status with
`campaign-status CAMPAIGN_ID --task-card CARD`; a passive unscoped association
does not authorize a live Campaign read.

Main `campaign-status` is deliberately one compact current view, not a paging
protocol. It returns current Campaign semantics, the newest minimal
frontier-head checkpoint, and the eight most recent event summaries. Exact older
event bytes remain append-only in `campaigns/CAMPAIGN_ID/events.jsonl` for
targeted event/Research forensics. New frontier checkpoints persist only the
routing fields the reader consumes: generation/supersedes, target id, bounded
active and attained Research ids, optional recovery root, and concise Main
disposition. Canonical Research, product, review, and reason bodies are not
copied into each generation; old verbose checkpoints remain untouched.

Main's ordinary `frontier` goal rows keep decision-complete routing: exact
active/attained ids, head-to-workflow-root mappings, current route and terminal
ids, actionable Research/round, replay argv, freshness, and concise semantic
disposition. Repeated per-successor hashes, counts, and full diagnostic trees
are emitted only by explicit `frontier --diagnostic`. This changes neither the
underlying exact search nor Main's authority to choose a different route.

Omitting an exact Campaign id preserves the global V5 frontier and the earlier passive
behavior: a selected Research item may still copy its `campaign_id` into a card,
but no Campaign envelope or implicit active-Campaign filter is attached. The
Campaign is nontruth context, never a scheduler, expansion loop, task closure,
certification gate, or Fact premise. V4 keeps its recorded active-Campaign
behavior and is not reinterpreted by this V5 option.

`plan-repair-round` copies the repaired Research's exact `campaign_id` into
both the immutable repair Research and its production round scope. If the
source Research is unbound, the repair remains unbound even when `ACTIVE`
names another Campaign. No late manual binding or active-Campaign inference is
used.

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

## Historical V3-to-V4 inheritance procedure (not a V5 path)

The remainder of this section documents the retired V4 workflow so old
artifacts can be interpreted. Do not execute it to initialize, migrate, or
authorize a V5 project; `mode-init`, copy-upgrade, import, and cutover receipts
from this section grant no V5 authority.

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
