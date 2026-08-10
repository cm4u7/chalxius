# MathGraph Agent Protocol v4

> **V5 adaptation.** The three-plane capability boundary survives in Chalxius.
> Historical V4 cards retain their frozen `execution_profile` and
> `profile_obligations`. Current V5 cards instead bind the mode event and a
> prospective assurance contract; the legacy execution profile is not attached
> automatically. Every mode uses the same V5 Candidate Release, Certification
> Decision, and Fact gateway.

Read this reference before planning, executing, validating, or ingesting a
workflow-evidence v4 round.

## Status and boundary

Protocol v4 originated in the pre-Chalxius `mathgraph-chalk-version` package and
supplies the retained communication and task-card protocol embedded by this
package. V5 changes the durable truth lifecycle without weakening those
coordination boundaries:

- admitted fact statement interfaces are the only reusable proof premises;
- memory, blackboard objects, worker returns, computations, and votes remain exploration;
- a Research entry or compatibility submission is only nontruth input until it
  is sealed into one exact V5 Candidate Release; and
- only a fresh verifier's immutable Certification Decision followed by exact
  gateway admission creates a V5 Fact.

Before that fresh dispatch, the host should run
`scripts/prepare_verifier_capsule.py`. For V4 it materializes the exact frozen
bundle. For V5 it recomputes the release/capsule, copies only authorized bytes,
and, for prospectively marked releases, supplies a complete decision template,
standalone preflight validator, and copied host submission program. Give the
verifier only the returned input paths and `review_draft_path`; retain the host
capability receipt and run `host/submit_review.py` after the draft is returned.
Only `formally_returned` bytes may go to the gateway. Historical unmarked V5
capsules retain their direct `review_return_path`. A reported access outside the
allowlist invalidates the run. This is a cooperative audit boundary, not OS
sandbox enforcement.

Installing the skill does not authorize migration or cutover of an active
project. This package starts neither the legacy `$mathgraph-chalk-version` nor
`$run-multi-agent-mathgraph`; their old writer-exclusivity rule applies only
when using those standalone rollback packages. Unified work has one active
kernel and one writable project root.

## Three planes

Keep these channels distinct:

1. The control plane is the compact worker prompt, strict JSON task card, bounded host follow-ups,
   and the exact worker-final handoff.
2. The mathematical-state plane is one frozen, bounded blackboard snapshot shared by every worker
   in the round.
3. The narrative plane is the worker's bounded rationale, narrative summary, and intuition.

The prompt must not duplicate the policy or the graph. It names only the task card, this reference,
the `mgraph` wrapper, the truth reminder, and the final handoff format. A follow-up is exactly one
JSON object with `type="control"`, the assignment ID, one action from `clarify`, `stop`, `finalize`,
or `report-blocker`, and an object-valued `payload` whose canonical JSON is at most 8 KiB. Proofs,
formula repairs, computations, and other truth-bearing content must be written to the designated
return, artifact, or blackboard delta rather than existing only in a follow-up.

## Parallel exploration and communication

Read the task card's
`execution_profile.exploration_features.parallel_clean_context_panel`. If its
status is `required`, use every callable clean-context slot for which a
genuinely distinct eligible direction exists, all launched from the same frozen
snapshot. If it is `available`, panel use is opt-in; if `not_applicable`, do not
create a ceremonial panel. Whenever a panel runs, its first-wave returns add
typed exploration nodes and no worker may cite or pretend to have read a
same-round draft.

If `execution_profile.exploration_features.barriered_blackboard_pulse.status`
is `required`, communication is one durable two-wave pulse:

1. persist a pulse plan binding every first-wave commitment before any bound canonical return or
   ingestion exists;
2. validate and ingest every committed first-wave return;
3. freeze a fresh snapshot and create the cross-review assignments from it;
4. derive an immutable barrier that binds those existing assignments to actual first-wave
   ingestion receipts, then after each native spawn record trusted host dispatch before that
   assignment has a canonical return or ingestion; and
5. ingest every committed cross-review and derive a closure containing a registered relation such
   as `challenges`, `refines`, `duplicates`, or `supports_candidate` before synthesis. Its payload
   names the peer node, the independently
   repeated check, and the concrete correction or explicit no-correction boundary.

A mutable draft may fail `preflight-return` without changing the pulse. After
main supplies the matching worker-final hash, each complete return is handled
independently: a valid return enters cumulative Research and a malformed or
semantically invalid peer receives an immutable local quarantine receipt. It
does not erase or invalidate earlier valid contributions. A whole-pulse abort
(`pulse-abort`) is an explicit operation that stops future dispatch and writes
while retaining all existing Research and receipts. Pulse closure reports
collaboration repair status only; it never certifies or admits a Fact.

The host supplies one explicit cooperative configuration through `--host-config` or
`PROJECT/host_adapter.json`; `pulse-plan` freezes its trusted issuers. After a real native Wave-2
spawn, the dedicated `host` role records `pulse-dispatch` with the commitment, prompt hash,
host-task scope, unique context ID, native agent identity, and exact `fresh-context-v1` contract.
No other role may write that receipt. Read `multi_agent_adapter.md` for the schema and commands.
This is machine-checked host attestation, not cryptographic identity. Plans and dispatches cannot
be backfilled: canonical return/receipt state and the immutable blackboard transaction ledger both
fail closed, including when someone later removes the canonical result files.

Host messages are control-plane notifications only. If an objection or refinement affects the
mathematical conclusion, the responsible worker must encode it in its return delta so recovery and
audit do not depend on chat history. For a profile-required pulse, absence of a
second-wave cross-edge must be reported as an incomplete collaboration
obligation, not described as blackboard communication.
A ceremonial or content-free cross-edge also leaves that gate incomplete.

For a profile-required panel, use every callable clean-context slot while
genuinely distinct eligible directions remain. For an available panel, explicit
opt-in may choose a bounded subset. Estimated duration, cost, budget, or burden
may order starts and load within the selected panel, but never weakens a
required profile feature, adoption gate, or Fact-admission gate. Hard
artifact, graph, event, checkpoint, governance-ledger, and pulse-control caps remain safety and
integrity boundaries. Only the host-observed union of active task intervals can trigger a duration
notice: exactly 1200 seconds does not trigger; the first observation strictly greater than 1200
seconds produces one immutable notice while managed work remains runnable. No acknowledgement is
required, and the engine never sends SIGKILL or another process signal. A later explicit host/user
stop may forbid subsequent managed writes without terminating an operating-system process.
The task card's hashed `host_task_scope_id`, not the campaign, defines that durable clock. Interval
coordinates share a task-relative host timeline; overlaps count once even across source
`clock_epoch` labels. Supply the scope explicitly or through `MATHGRAPH_HOST_TASK_SCOPE_ID` or
`CODEX_THREAD_ID`; planning fails before writing a round when no stable source exists. Campaign and
memory IDs remain event provenance, so one host task can cross campaign boundaries without
splitting or double-counting its clock.
V5 uses the same normalizer with one prospective fallback: when neither an explicit value nor
either environment channel exists, `plan-round` deterministically allocates a non-null local scope
from the exact project and planning request before any round write, returns that scope, and freezes
it into the round, every assignment, and every card. Reuse the returned scope explicitly for later
rounds that belong to the same host task. Historical V5 cards with a null scope remain readable but
cannot be silently attributed to a new attack report.
Never use a worker vote to resolve a truth-bearing dispute. A surviving load-bearing challenge
requires an orthogonal specialist or an explicit open/blocked boundary. Stop panel expansion after
two consecutive barriered cross-review waves add no new typed information.

## Historical V4 round profile repair advice

Every new workflow-evidence-v4 round manifest freezes `profile_obligations` as a reproducible
feature-by-assignment plan. Once governed assignments have canonical outcomes,
main may inspect `profile-closure-status` and may append one exact
`profile-closure-record` to cumulative Research. The record binds the manifest,
reasoning-mode event, execution profiles, task cards, exact returns, ingestion
or quarantine receipts, and outcome/effect subjects so its advice can be
replayed.

Evidence must cover exactly the required features and exact required
assignments. Pulse commitments from another round or unrelated assignments do
not satisfy the matrix. Specialist artifacts stay inside the exact assignment
return or artifact directory and need genuinely distinct hashes. Campaign
entries partition covered assignments by their task-card campaign and bind
concrete expansion event IDs plus distinct before/after scope artifacts.
Novelty and campaign events must be recorded no earlier than the governed
round. Paper Logic and Audit evidence can reuse a reviewed earlier snapshot only
while it is current and non-superseded; Audit also requires a current Logic
base. A Blackboard Paper mirror must project the selected assignment snapshot.

Expert synthesis binds a native passing expert or interpretation lint receipt,
exact draft/card bytes, and a separate assignment-scope artifact containing the
current task-card, return, ingestion, outcome, and effect hashes. The lint is
machine-verified; the semantic assignment linkage is a procedural host
attestation, so the composite level is
`mixed_procedural_and_machine_verified`.

If no feature is required, status is recomputably `not_required`. If
`profile_obligations` is absent from an old round, retain that history rather
than manufacturing evidence. Missing, incomplete, or drifted profile advice
never blocks a V5 verifier capsule, Candidate Release, Certification Decision,
or Fact admission. It has `truth_effect="none"`; the exact V5 transition gates
remain authoritative.

## Task card

For workflow evidence v4, treat the generated task card as immutable capability
data. It binds:

- project, round, assignment, worker, campaign, host-task scope, memory, work mode, and assigned
  relation;
- exact predecessor fact clauses and required hypothesis witnesses;
- claim and convention identifiers;
- obligations and stop conditions;
- verification mode and authorized artifact roles;
- the deterministic workload profile, compact adoption binding, required feature statuses, and
  replan triggers;
- artifact, work, and return locations;
- object/file budgets;
- fixed release-profile hard safety and integrity caps;
- the frozen blackboard snapshot hash and read/write spaces.

A current V5 card preserves the three planes, exact paths, snapshot, Research,
predecessor interfaces, mode event, and capabilities, but does not contain the
V4 execution-profile fields. It adds the prospective assurance contract with
typed obligations, computation-stage count, risk signals, and related-artifact
roles. A frozen card with
`task_context_revision="chalxius-v5-task-context-0.4.3-2"` contains the
complete immutable source Research dossier and a task-referenced current V5
authority snapshot. The latter, not nontruth project-background prose,
determines current Fact, Release, Decision, and admission status. An explicitly
named attack target grants only its exact path/hash-bound Release, Decision,
optional admission marker, admitted Facts, and sealed artifacts. Use the
generated card rather than merging the schemas by hand.

For prospective public production, `workers` counts only constructive primary
assignments. Explicit or automatically selected `refute` work is rejected and
no paired adverse assignment is appended. The exact boolean
`independent_adverse_required=true` remains a marker for the later
exact-Candidate adverse-readiness gate, not a production dispatch predicate.
Historical direct-allocation cards and their paired worker/context bindings
remain byte-exact readable; their returns remain nontruth Research and do not
replace Candidate adverse closure or disposition.

A newly planned 0.4.4 card uses
`task_context_revision="chalxius-v5-task-context-0.4.4-1"` and adds one exact
Main-planner context-selection receipt plus an exact candidate-root/version
runtime binding. In 0.6.3, a newly generated schema-2 binding also freezes a
path-independent content identity and the canonical object locator under the
host-managed archive root outside skill discovery. The locator is cross-checked
against current host configuration; task-card text never chooses the trust root.
Legacy schema-1 cards remain byte-exact and use an immutable identity-registry
mapping to the same kind of verified content object.

Start the worker CHX ledger with that candidate's script and `--task-card CARD`;
a mismatched older global runtime fails before creating the ledger. Historical
archive resolution is available only after a valid abort or complete validation
of every return, receipt, Research record, and conditionally required adverse or
program-math side record. It is read/status/audit-only, rehashes the complete
archive and registry on every bounded phase, and never imports or executes the
archive. Active cards, worker startup, return preflight/validation/ingestion,
experiments, Pulse, and all writes remain exact-current-runtime operations.
Within one bounded round phase, identical runtime identities may share one
successful scan; that in-memory deduplication is discarded before the next
phase and never caches authority. An origin-bound promoted Blackboard
query may seed only one task and retains its node/snapshot/query/hash lineage.
Exact enum mode hints are advisory and may apply automatically only when the
recorded cross-component signature is unchanged; explicit user mode wins. The
technical Host remains the trusted dispatch adapter and gains no planner or
background capability.

When Main explicitly plans V5 with `--campaign ID`, the round manifest and each
card also bind one `chalxius-v5-campaign-scope-1` envelope and its exact frozen
snapshot path/hash. Read its objective, active typed targets, constraints,
value definition, stop conditions, and history as nontruth planning context.
It never replaces the source Research dossier, chooses the work mode, closes
the assignment, grants an undeclared filesystem capability, or changes Fact
admission. Cards planned without the flag—including older cards that merely
carry a passive `campaign_id`—remain valid without this field or any redo.
Use `campaign-status ID --task-card CARD` to read the frozen V5 status; it must
never fall through to the current live Campaign.

`PROJECT_BACKGROUND.md` is still generated or refreshed only after explicit
user instruction. A new card freezes its complete exact-byte index and one
round-local immutable copy, not its body in active context. A worker must use
`project-background-read CHUNK_ID --task-card CARD`, and after compaction must
reread the frozen card/index and retrieve the exact chunks again. Every chunk
remains retrievable, the background has no truth effect, and historical cards
keep their original full-body binding.

A frozen V5 card without `task_context_revision` keeps its original contract.
Do not add the field, copy new state into it, warn that it is noncompliant, or
ask its worker to repeat completed work. Authority drift after a new current
card was planned is handled by planning a future successor card; the frozen
card bytes remain unchanged.

Source-dependent Research added for a new card must use
`memory-add --current-assurance` and exact project-relative path/SHA-256/role
artifacts. A legacy entry containing only an absolute source path remains
historical nontruth, but future planning fails until a current-assurance
successor supplies the capability. Source mutation after card freeze is a
visible drift error; it never rewrites the card.

When and only when an operator has enabled adverse-routing evolution for the
project, a new card additionally binds the fixed baseline attack vocabulary,
the exact matching user-approved future-only rules, their hashes, and the
counterexample learning contract. Approval or disablement after planning never
changes the frozen card. The general baseline includes hidden-conjunct
splitting. The ordinary-language, burden/charity/independent-failure-surface,
and quantifier-modal-scope-exception attacks require an exact frozen
`philosophy` or `mixed` domain profile; prompt wording cannot activate them. A
legacy card without this field keeps its original return schema even if later
commands enable the extension.

Unknown fields fail. A worker must not infer extra capability from filesystem visibility.
For lane-separated collaboration, a V4 memory entry may bind
`blackboard_write_space_ids` and `blackboard_cross_space_endpoint_node_ids`. Planning validates
them against the current graph and copies only those exact capabilities into that assignment's
task card; omitting `blackboard_write_space_ids` retains the project-wide compatibility default.
`assets/task_card.v4.example.json` is illustrative; use the generated task card for a real round.
Experiment start, event, resume, status, and finalize additionally compare the supplied card with
the exact on-disk card and SHA-256 named by `round.json`; a schema-valid edited copy grants no
capability.
Read [adoption_policy_v4.md](adoption_policy_v4.md) before changing the binding. The three planes
are always required; experiment, replay, atomic bundle, and expert-export gates become mandatory
only when their recorded trigger is true.
An exact historical estimate-gated binding is archival-only and remains audit-readable, but it is
not an active capability:
every execution path rejects it and requires a newly planned current-policy round.

## Worker return

For a workflow-evidence-v4 card, return exactly one strict schema-v4 JSON
object. Supported outcomes are:

- `fact_submission`: an atomic candidate statement and proof;
- `counterexample`: a checked construction that challenges a claim;
- `evidence`: bounded evidence that does not itself enter truth;
- `dead_end`: a reproducible failed route and what remains open.

Every return binds the task-card hash and frozen snapshot hash. It includes an obligation ledger,
one typed blackboard delta, a bounded narrative summary, and only declared artifacts. The
outcome-specific fields are exact: do not add commentary keys.

For a current V5 assurance-bound card, the return contains exact
`obligation_dispositions`, `computation_manifest`, and `research_assurance`
fields. The complete exact-key contract, status enums, evidence-binding rules,
and a no-adverse template are in
[v5_worker_return_contract.md](v5_worker_return_contract.md) and
`assets/worker_return.v5.assurance-no-adverse.template.json`; a worker must not
infer these shapes from private implementation code. For an
adverse-routing-bound V5 card it additionally contains exactly
one `attack_learning` field. A current counterexample requires schema-2
`result_kind=surviving_counterexample`; `evidence`, `insight`, or `challenge`
may use `result_kind=productive_challenge` only with a concrete load-bearing
before/after/evidence value effect. Otherwise the field is `null`.
A completed `refute` assignment remains adverse provenance even when its
outcome is `evidence` or `insight`: ingestion records the exact card, worker,
mode, and assignment independently of Research kind. A later Candidate Release
must bind and dispose it and exclude that worker from verification, while the
null learning field creates no attack case or route proposal.
A reportable attack supplies a typed result and family, target pattern, failure mechanism,
premise and conclusion-failure witnesses, reproduction steps, exact success
boundary, value effects, and one proposed route with trigger, instruction, false-positive
guards, and scope. Ingestion may record the case and proposal, but only a later
operator decision can affect future routing. See
`adverse_routing_evolution.md` for the exact schema and attack-report procedure.

The delta may add only content-addressed nodes and edges allowed by the task card. Validation must
finish before merge. A validation error has zero ingestion effect.

## Prospective Research production and supervision

`plan-round` creates constructive production subround 1. It rejects explicit or
automatically selected `refute` work and never appends a paired adverse worker.
Proof, literature, insight, interpretation, and computation-design returns are
independently ingested and later eligible for supervision. A worker may record a
boundary, obstruction, or counterexample discovered while doing its assigned
constructive work, but formal Research attack is not a production assignment.

The production manifest freezes logical components from selected Research
ancestry before dispatch. As soon as one exact component is fully ingested,
Main may run:

```bash
"$MGRAPH" --root "$PROJECT" --role main \
  plan-supervision-round SOURCE_ROUND_ID --component-id COMPONENT_ID
```

Omit `--component-id` only when the source round has one component. The command
binds the exact source manifest, immutable component id/hash, and complete
component receipt-set hash, and creates one to three scoped `refute`
supervisors selected from a static reproduced-failure registry. Workers in
unrelated components may continue concurrently. `program_math` applies to
computation design/output, `proof_logic` to proof-bearing work, and
`source_scope` to literature or exact source use. `integration` applies only
when one completed component crosses at least two of those primary scopes;
same-scope multiple outputs remain with their primary supervisor. Explicit
`--scope` may select only applicable distinct values. Supervisors
return one `research_supervision_report`; defects become later copy-on-write Research
repair. Supervisors attack the new production returns and declared artifacts;
admitted Fact dependencies are frozen premises unless exact new contradiction
evidence is escalated for separate authority-governed reopening. Validation
rejects timing-derived subsets, unknown or tampered components, and overlapping
scope coverage while keeping an identical retry idempotent. Historical
component-free rounds retain conservative whole-round completion semantics.
Validation shares one ephemeral command-local inspection context. Only a reentrant check
of the same supervision binding stops after local schema and hash validation;
the outer check still reconstructs the complete source-round authority. If an
interruption occurs after content-addressed supervisor Research is written but
before the round, an identical retry reuses that Research and creates at most
one round. The required cycle never starts Pulse or gives supervisors a mutable
same-wave blackboard.

Each newly generated 0.7.0 supervisor also binds the exact static registry
revision, hash, and family id. Pre-0.7.0 revision-2 supervision records without
that additional nontruth provenance remain readable without backfill and retain
their original exact supervision validation.

For prospective 0.7.0 planning, the default Blackboard capability freezes only
one root-space node and grants zero write spaces. Larger reads require a promoted
query, and writes require an explicit space capability. Historical wide
snapshots remain valid. Public V5 `pulse-plan` is retired; operations needed to
inspect or finish already-created Pulse records remain available, and V4 keeps
its historical contract.

Candidate preflight derives the exact applicable scopes for every selected
constructive production result and requires one live completed ingested result
per scope before expensive work. Review task/return records remain review-only
and are attached automatically rather than selected as constructive anchors.
Immediately before artifact sealing, the Candidate mutation lock protects a
second derivation of the exact live result set; an intervening abort or set
change fails without writing a release.

Main routes a concrete defect back with:

```bash
"$MGRAPH" --root "$PROJECT" --role main \
  plan-repair-round PRODUCTION_RESULT_ID \
  --trigger-memory-id SUPERVISOR_RESULT_ID
```

The repair preserves the source assignment's work mode when available, so a
computation-design defect produces another design-only compute card rather
than silently falling into a generic proof task.

A production computer first returns exactly `computation_source`,
`computation_design`, and `computation_dependencies`, with
`computation_manifest=null` and no execution output. After the program-math
supervisor result is explicitly disposed as `resolved_no_obstruction` or
`resolved_by_evidence` and while its supervision round remains live, Main may
run:

```bash
"$MGRAPH" --root "$PROJECT" --role main \
  plan-computation-execution SOURCE_ROUND_ID ASSIGNMENT_ID
```

An aborted supervision round is not a match and cannot make a live successor
ambiguous. The new card binds the design return, supervisor return,
disposition, and exact source/dependency hashes. The selected execution
Research, complete approval binding, and latest supervision disposition are
revalidated under the round-write mutation lock before any round bytes are
created. Preflight rejects changed bytes. The ingested actual output does not
enter the legacy automatic review queue; Main sends its whole execution round
through `plan-supervision-round` for the explicit second subround.

## Round procedure

1. Add or select actionable memory and inspect the active campaign.
2. Run `plan-round`; all assignments in that round receive the same frozen snapshot.
3. Give each context-free worker only its generated prompt and paths.
4. The worker writes artifacts only in its artifact directory and a mutable return draft below its
   work directory. Before the canonical return exists, run:

   ```bash
   "$MGRAPH" --root "$PROJECT" --role worker preflight-return ROUND_ID ASSIGNMENT_ID \
     --input WORK_DRAFT.json
   ```

   This read-only command and `validate-return` share ingestion's exact prompt/task-card/binding,
   mode semantics, artifact, blackboard-delta, and pulse-review validator. Success and failure have
   zero project write effect. Only a passing draft may be copied byte-for-byte, without
   reserialization, to the designated canonical return path.
5. Run `validate-return` on those canonical bytes.
6. After the worker stops editing, obtain exactly:

   ```json
   {
     "assignment_id": "a01-0123456789ab-compute",
     "return_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
     "status": "final"
   }
   ```

7. Run `ingest-return` with that exact hash. An identical successful retry is idempotent; changed
   bytes fail. A matching-hash core validation failure is also replay-safe terminal evidence:
   retry observes the same aborted pulse and cannot create a second failure/abort pair. A wrong
   caller-supplied hash does not authenticate canonical final bytes and creates no failure evidence.
8. Inspect the receipt, blackboard transaction, memory status, round status, frontier, and `audit`.

Never treat `draft_present`, a plausible return, or an unauthenticated file as final.

## Verification capability

`closed_packet` authorizes statement interfaces and no computation bytes. `artifact_replay`
authorizes only the exact roles listed in the task card and bundle manifest. A verifier receives no
project CLI, project root, memory, unrelated fact proof, checkpoint, or undeclared artifact.

Adding evidence can resolve an evidence-access finding. It cannot erase a mathematical, typing,
scope, source-mismatch, or prior-rejection finding without a new submission and fresh review.

## Release boundary

The verification-bundle/review/admission path, shared submission/blackboard visibility marker,
current/history projection, hard caps, and pulse plan/barrier/closure/abort
lifecycle originated in the pre-Chalxius codebase and were regression-tested
there. Real fresh-context workers exposed and drove repairs for envelope-only
graph validation, ceremonial cross-edges, and vocabulary drift before release.
Exact inheritance-lock verification and project audit still govern
every use. Installing the unified candidate does not activate either legacy
runtime, migrate an active project, or authorize cutover.
Cross-project, cross-machine, and multi-root federation is deliberately disabled.
These state transitions govern cooperative CLI calls only. Direct OS filesystem access can rewrite
or delete canonical returns and pulse records; audit can detect inconsistent surviving evidence but
cannot prevent that bypass or reconstruct a fully erased trail.
