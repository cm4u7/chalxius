# MathGraph Agent Protocol v4

> **Unified supersession.** This protocol runs only inside
> `chalxius`'s Chalk V4 kernel. The legacy standalone Danus and
> Chalk packages are lineage/import sources, not active routers. Truth and
> adoption gates are invariant; panel and pulse requirements come from the
> frozen `execution_profile` bound to each task card.

Read this reference before planning, executing, validating, or ingesting a
workflow-evidence v4 round.

## Status and boundary

Protocol v4 originated in MathGraph Chalk and is the workflow-evidence protocol
embedded by this unified package. It
strengthens round coordination without changing the truth boundary:

- admitted fact statement interfaces are the only reusable proof premises;
- memory, blackboard objects, worker returns, computations, and votes remain exploration;
- a fact submission is only a candidate until a separate verification and admission path accepts
  it;
- a V4 single fact reaches truth only through a content-addressed verification bundle, a structured
  clean review by a different fresh verifier, and explicit gateway admission.

Before that fresh dispatch, the host should run `scripts/prepare_verifier_capsule.py`. It
revalidates the exact bundle file set and copies only those bytes to a neutral path outside project
and skill discovery. Give the verifier only the returned input paths and review output path; retain
the capsule's host capability receipt separately. A reported access outside the allowlist
invalidates the run. This is a cooperative audit boundary, not OS sandbox enforcement.

Installing the skill does not authorize migration or cutover of an active
project. This package starts neither `$mathgraph-chalk-version` nor
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

A mutable draft may fail `preflight-return` without changing the pulse. After main supplies the
matching worker-final hash to ingest a canonical core return, any complete return, graph, or
pulse-semantic validation failure writes immutable evidence binding the commitment, assignment,
return SHA-256, worker-final SHA-256, error class, and original error text; the same transaction
writes a `pulse-abort` receipt bound to that evidence. Core commitments can never be reclassified
as optional voids, while an optional failure does not abort the whole pulse. Aborted pulses reject
later ingest, barrier, dispatch, closure, and void operations. Barrier and closure also reject a
canonical core return with no ingestion receipt and require ingest or abort. A locally complete closure reports
`procedural_ready`; `machine_verified_ready` additionally requires trusted host clean-context
dispatch receipts. Missing host receipts remain explicit blockers.

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
Never use a worker vote to resolve a truth-bearing dispute. A surviving load-bearing challenge
requires an orthogonal specialist or an explicit open/blocked boundary. Stop panel expansion after
two consecutive barriered cross-review waves add no new typed information.

## Round profile closure

Every new unified round manifest freezes `profile_obligations`. Treat it as the
authoritative feature-by-assignment matrix; never infer a weaker set at the end
of the round. Once all governed assignments have exactly one canonical
ingestion receipt, main inspects `profile-closure-status`. If required features
remain, main submits one exact `profile-closure-record` input. The resulting
write-once receipt binds the manifest, reasoning-mode event, execution profiles,
each task card, each exact return and ingestion receipt, and each assignment's
outcome/effect subject.

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

If no feature is required, status is recomputably `not_required` and no closure
receipt may be manufactured. If `profile_obligations` is absent from an old
unified round, replan. Verifier-task creation and admission require closure when
the matrix is nonempty; accepted-idempotent retries and audit revalidate the
same evidence. This is a `workflow_readiness_only` gate outside the invariant
Fact-admission contract and never changes its hash.

## Task card

Treat the generated task card as immutable capability data. It binds:

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

Return exactly one strict schema-v4 JSON object. Supported outcomes are:

- `fact_submission`: an atomic candidate statement and proof;
- `counterexample`: a checked construction that challenges a claim;
- `evidence`: bounded evidence that does not itself enter truth;
- `dead_end`: a reproducible failed route and what remains open.

Every return binds the task-card hash and frozen snapshot hash. It includes an obligation ledger,
one typed blackboard delta, a bounded narrative summary, and only declared artifacts. The
outcome-specific fields are exact: do not add commentary keys.

The delta may add only content-addressed nodes and edges allowed by the task card. Validation must
finish before merge. A validation error has zero ingestion effect.

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
current/history projection, hard caps, and pulse plan/barrier/closure/abort lifecycle are
originated and were regression-tested in Chalk. Real fresh-context workers exposed and drove
repairs for envelope-only graph validation, ceremonial cross-edges, and vocabulary drift before
release. Exact inheritance-lock verification and project audit still govern
every use. Installing the unified candidate does not activate either legacy
runtime, migrate an active project, or authorize cutover.
Cross-project, cross-machine, and multi-root federation is deliberately disabled.
These state transitions govern cooperative CLI calls only. Direct OS filesystem access can rewrite
or delete canonical returns and pulse records; audit can detect inconsistent surviving evidence but
cannot prevent that bypass or reconstruct a fully erased trail.
