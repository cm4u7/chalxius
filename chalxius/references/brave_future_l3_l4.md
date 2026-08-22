# Brave Future BF-1 through BF-3: cautious L3/L4 recovery

This is the executable boundary for the optional Brave Future sidecar introduced
in Chalxius 0.6.0 and retained without authority expansion through 0.6.5. The
runtime-continuity and Paper Graph continuity repairs do not add a planning,
dispatch, Campaign, Research, or truth seam. The
sidecar still implements only the safe first slice of the L3/L4 design:

- L4 projects strict typed repair lineage over the existing V5 frontier;
- L3 validates a real blockage and returns a bounded route reassessment;
- the result remains advice until a later ordinary, explicit planning action.

It does not implement `plan_one`, `execute_one`, a background loop, or a
`plan-round --reassessment` connector. Those authority-bearing seams remain
closed pending a separate review. Campaign, Pulse, Paper, Evidence, Reader,
Learner, Candidate, Certification, Gateway, and Fact behavior is unchanged when
Brave Future is absent or disabled. The ordinary frontier itself follows the
shared 0.8.9 projection below.

## 0.8.9 shared frontier projection

Brave Future no longer constructs a second actionable completion semantics.
One command-local projection supplies both the ordinary and Brave Future
actionable views. It groups exact work semantics across incidental record
identity, timestamps, and explicitly non-material provenance, selects one
deterministic representative, and removes a group closed by valid production
plus applicable completed supervision. Workgroup identity remains exact across
Campaign, work kind, content/source, relation, dependencies, related Research
inputs, obligations, source dependence, artifact path/SHA/role capabilities,
profiles, stop conditions, and conventions; it performs no fuzzy theorem
matching. Because `related_research_ids` feed task-card dossiers, artifact
authority, and supervision ancestry, different related-input sets never share
a workgroup. The history view retains every original Research record and
provenance edge.

Prospective writers emit `chalxius-bf-frontier-projection-3`. Frozen
`chalxius-bf-frontier-projection-1` and `-2` objects retain exact read
validation but are never rewritten or emitted by the current writer. This is a
frozen-record read contract, not a migration or runtime compatibility adapter.

The requested `limit` bounds serialized entries and the corresponding member
window. The complete eligible-set identity is represented by count and digest,
while detailed inventories and explanation closure are restricted to returned
entries. A planning request with zero active proof targets stops before Fact
inventory. All of this state dies with the command: there is no persistent
frontier cache or index, timer, watcher, migration, compatibility adapter, new
truth path, or rewrite of a frozen Research/card.

## Authority boundary

Every Brave Future record has:

```text
autonomy_level=advisory
plan_effect=none
dispatch_effect=none
campaign_close_effect=none
truth_effect=none
fact_admission_effect=none
```

The module has no call seam to round creation, repair-round creation, Pulse or
Host dispatch, Candidate Release, Certification, Gateway admission, Fact
admission, or `CampaignStore.active()`. It cannot create Research. A malformed
sidecar fails `brave-future-audit` but is excluded from stable Fact authority
and does not change `fact_evidence_audit()`.

The sidecar is stored under `PROJECT/governance/brave-future/`. It contains no
`ACTIVE`, queue, dispatch, Candidate Release, Certification, or Fact store.

## Exact activation

Activation is prospective, explicit, and Campaign-specific. The policy input
must equal this object except for the exact Campaign id:

```json
{
  "revision": "chalxius-brave-future-policy-1",
  "campaign_id": "campaign-...",
  "autonomy_level": "advisory",
  "max_reassessments_per_signature": 1,
  "max_reassessments_per_epoch": 3,
  "shortlist_limit": 5,
  "local_graph_depth": 2,
  "local_graph_node_limit": 64,
  "max_new_research_nodes": 0,
  "max_auto_workers": 0,
  "max_consecutive_auto_rounds": 0,
  "allow_active_campaign_pointer": false,
  "allow_chx_as_route_input": false,
  "truth_effect": "none",
  "fact_admission_effect": "none"
}
```

Run:

```bash
mgraph --root PROJECT --role operator brave-future-enable \
  --campaign CAMPAIGN_ID --input policy.json --actor USER
mgraph --root PROJECT --role main brave-future-status \
  --campaign CAMPAIGN_ID
mgraph --root PROJECT --role main frontier \
  --campaign CAMPAIGN_ID --brave-future --view actionable
```

Brave Future always requires the exact `--campaign`. It never consumes the
legacy informational `ACTIVE` pointer, a task-card hint, or a natural-language
Campaign name. A policy change creates a new epoch; it does not rewrite old
transactions.

## L4 strict repair-lineage projection

Only new current-assurance Research carrying
`metadata.brave_future_repair` with revision
`chalxius-bf-repair-contract-1` can close a repair lineage. A valid repair must
bind:

- a typed relation and strategy;
- exact same-Campaign predecessor Research;
- complete obligation coverage with `preserved`, `resolved`, or `rehome`;
- supporting or successor Research for resolved or rehomed obligations;
- every inherited or explicitly disposed invalidator;
- exact source-capability hashes;
- an acyclic, non-self, same-Campaign lineage.

Legacy repair metadata remains readable but cannot collapse its parent. For an
otherwise actionable repair lineage, a strict successor hides its root only
when the union of visible successors completely covers its obligations and
every live invalidator is inherited or validly disposed. Otherwise the root
remains visible with a machine-readable residual surface.
Conflicting repairs, cycles, stale sources, blocked or failed repairs, and
unresolved program-math or Paper obligations fail closed to visibility.

The projection reuses the existing V5 four-factor ordering. It has
`scheduler=v5_main_four_factor_frontier` and `score_writeback=false`; there is
no second scheduler or persistent priority queue. Views are `actionable`,
`all-active`, and `history`. `--history` and `--all-active` are compatibility
aliases only under `--brave-future`; conflicting view switches reject.

## Shared read-only planning snapshot

Each projection is computed from one deterministic read-only snapshot binding:

- exact Campaign bytes and event count;
- every same-Campaign Research record, disposition, invalidator, and typed
  repair edge;
- current active Fact/interface/admission/revocation authority projection;
- a pure Blackboard preview with the same id and hash as later publication;
- current Paper Logic/Audit/continuation and Evidence heads;
- reasoning-mode and Fact-admission contract heads;
- adverse-routing and program-math Research projections;
- project background and workflow heads.

The preview publishes nothing. Persisted reassessments revalidate all bound
heads under the ordinary V5 mutation lock and publish the complete transaction
by one same-volume atomic directory rename.

## L3 blockage and reassessment

`campaign-reassess` accepts either a fresh exact blockage object or an already
stored blockage id. A fresh object uses revision `chalxius-bf-blockage-1` and
must bind one exact Campaign, planning snapshot, target, blocked routes,
blocker class, method-family hash, remaining obligation keys, and at least one
real V5 attempt. Every attempt must identify an existing round, assignment,
task-card hash, final ingestion receipt, and resulting Research record. Runtime
or host failures and CHX findings are not mathematical blockage inputs.

The closed blocker classes are:

```text
missing_prerequisite
surviving_counterexample
scope_or_quantifier_mismatch
source_or_applicability_gap
representation_mismatch
program_math_failure
method_exhaustion
dependency_conflict
resource_bound_requiring_reformulation
```

Use dry-run first:

```bash
mgraph --root PROJECT --role main campaign-reassess \
  --campaign CAMPAIGN_ID --blockage-input blockage.json --dry-run
```

Dry-run is byte-for-byte zero-write. Persistent advisory mode stores exactly
one transaction containing the validated blockage, planning snapshot, L4
projection, candidate manifest, and reassessment:

```bash
mgraph --root PROJECT --role main campaign-reassess \
  --campaign CAMPAIGN_ID --blockage-input blockage.json
```

The shortlist is bounded and deterministic. Repeating the same stable blockage
signature in an epoch returns `park_and_escalate` and writes nothing. The
signature excludes time, prose, actor, and attempt order, so cosmetic changes
cannot reset the cooldown.

An Operator may record only an advisory disposition:

```bash
mgraph --root PROJECT --role operator campaign-reassess-decide \
  REASSESSMENT_ID --input decision.json --actor USER
```

The decision does not plan or dispatch a round. If the user wants to act on it,
Main must make a separate ordinary `plan-round` choice through the existing
Campaign, L1, L2/`auto`, assurance, Host, and Pulse boundaries.

## Roles and coordination

- Main: status, audit, Brave Future frontier, dry or persistent advisory
  reassessment.
- Operator: every Main read/advisory capability plus enable, disable, and
  decision.
- Host, Worker, Paper Auditor, Verifier, and Gateway: no Brave Future command.

`auto` continues to control only the ordinary future work unit's bounded
reasoning budget. It does not enlarge the Brave Future policy, compress a Paper
Graph, bypass a verifier shard, select `plan_one`, or change the Fact gate.

Run `brave-future-audit` before relying on any persisted proposal and after any
unexpected interruption:

```bash
mgraph --root PROJECT --role main brave-future-audit
```

Disablement is an Operator action and affects only future use:

```bash
mgraph --root PROJECT --role operator brave-future-disable \
  --campaign CAMPAIGN_ID --actor USER --reason "Return to stable planning."
```

Historical sidecar objects remain immutable and nontruth. No old task, Paper
snapshot, Research entry, Candidate Release, decision, admission, or Fact is
rewritten or invalidated by activation or disablement.

## Goal-driven `auto` and `deep` intake

Version 0.6.5 retains the prospective Operator intake compiler and closes its
Research handoff. The user does not need to know or say the internal word `Campaign`.
If a user states a
research objective while the project uses `reasoning_mode=auto` or
`reasoning_mode=deep`, the host
freezes those exact words in this minimal input:

```json
{
  "revision": "chalxius-bf-goal-intake-2",
  "objective": "The user's exact research objective."
}
```

Then run:

```bash
mgraph --root PROJECT --role operator research-goal-intake \
  --input goal.json --actor USER
```

The compiler performs Unicode-NFC and whitespace normalization only. It reuses
one lexically exact objective match or creates one new Campaign; it never
fuzzy-matches, selects through `ACTIVE`, or retags existing Research. The
returned internal `campaign_id` and intake token are host capabilities. The
public command creates or reuses exactly one prospective root Research that
binds both, so planning has durable lineage. A duplicate exact objective is
ambiguous and fails before writes. A prior explicit BF disablement also blocks
implicit re-enable until the user makes a new re-enable decision.

The BF transaction enables only the fixed advisory policy and computes BF-1;
BF-1 through BF-3 themselves create no Research. The public wrapper's separate
root-Research write creates no round, Pulse, dispatch, decision, or Fact. BF-2
and BF-3 remain ineligible until the existing blockage validator can
bind at least one exact ingested attempt. Once that evidence exists, the host
may use the returned internal Campaign id to run dry and persistent
`campaign-reassess` without asking the user to repeat Campaign jargon. The
ordinary blockage, cooldown, audit, and zero-authority gates remain unchanged.

## 0.6.5 finite-recovery acceptance boundary

The coordinated recovery is accepted only when the inherited Brave Future and
Campaign regressions pass together with the full V5 suite and the Paper
Research Pipeline and goal-intake matrices. The Paper pipeline may hand an ordered nontruth Paper
frontier to the existing scheduler, but Brave Future still cannot consume that
frontier without an exact goal/Campaign binding, create a round, dispatch an agent, write Research, close a
Campaign, or affect Candidate, Certification, Gateway, or Fact state. BF-4 and
all autonomous planning/execution remain deliberately absent.
