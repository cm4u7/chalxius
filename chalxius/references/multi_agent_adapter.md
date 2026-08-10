# Multi-agent adapter

> **Unified supersession.** Live allocation follows the frozen task-card
> `execution_profile`. The adapter supplies mechanics; it does not independently
> require a panel or pulse. Deep requires all applicable features, auto follows
> deterministic triggers, and fast leaves applicable high-cost features opt-in.

The Python engine owns durable state; the active host session owns live agent processes. Map the host
to spawn-worker, follow-up, wait/list, and fresh-verifier operations. In Codex these are the native
multi-agent tools. Prefer `fork_turns="none"` when the generated file is self-contained.

## Contents

1. Prospective Research production and supervisors
2. Execution-profile panel and exchange barrier
3. Launch workers
4. Launch a verifier
5. Recovery and states
6. Diversity

## Prospective Research production and supervisors

For new V5 public Research, launch subround-1 assignments from `plan-round` and
ingest each exact return independently. Do not share mutable peer context. The
production manifest freezes logical components from selected Research ancestry.
When one component is complete, run
`plan-supervision-round SOURCE_ROUND --component-id COMPONENT` and launch its
one to three scoped `refute` assignments in fresh contexts even if unrelated
components still have live workers. Omit the flag only for a one-component
round. Related assignments stay in one component, `integration` waits for that
whole component, and no component is derived from return timing. These
supervisors attack the frozen receipts; they do not negotiate live repairs. Any
defect creates a later copy-on-write production cycle.

This required Research sequencing does not call Pulse. The optional
execution-profile Pulse below remains a separate compatibility mechanism for a
task that independently requires snapshot-mediated peer exchange; it cannot
substitute for exact receipt-bound supervisors. A first-wave computation worker
must finish core code/design/dependencies before its program-math supervisor;
only a safely disposed result from a still-live, non-aborted supervision round
permits `plan-computation-execution`. The execution-round lock revalidates that
authority and the latest disposition immediately before writing the card, and
the actual output then gets another supervision round.

## Execution-profile panel and exchange barrier

When `parallel_clean_context_panel.status` is `required`, boldly dispatch
genuinely distinct live subagents and use all currently callable clean-context
worker slots, up to the number of eligible distinct channels. Normally include
constructive and adversarial channels, then every distinct literature,
interpretation, computation, convention, geometry, or protocol channel that
fits. When status is `available`, a panel is opt-in; when `not_applicable`, skip
it. Never create paraphrase workers merely to occupy surplus slots.

The four-factor score has `score_role="priority_ordering_only"`. When channels outnumber slots it
orders starts/load and leaves every lower-ranked channel actionable; it has no eligibility or stop
cutoff. Estimated budget, duration, cost, and burden may affect only that priority/load ordering.
They do not choose algorithms or weaken a profile-required launch, panel width,
refill, expansion, notification, continuation, or stopping obligation.

Parallel agents do not communicate merely because they share a round: every task card binds the
same frozen snapshot. When `barriered_blackboard_pulse.status` is `required`, use a durable
two-wave pulse; when it is `available`, the same mechanism is opt-in:

```bash
HOST_CONFIG=/absolute/host-owned/mathgraph-host-adapter.json

# wave 1: plan before any bound canonical return, then run independent typed deltas
"$MGRAPH" --root "$PROJECT" --role main plan-round --workers N
"$MGRAPH" --root "$PROJECT" --host-config "$HOST_CONFIG" --role main \
  pulse-plan --input PULSE_PLAN.json

# validate and ingest each committed worker-final handoff, then plan wave 2
# from a fresh snapshot so its assignment ids already exist
"$MGRAPH" --root "$PROJECT" --role main plan-round --workers N \
  --memory-id CROSS_REVIEW_MEMORY_ID_1 [...]

# bind those assignments and the fresh snapshot to the ingestion-derived barrier
"$MGRAPH" --root "$PROJECT" --host-config "$HOST_CONFIG" --role main \
  pulse-barrier PULSE_ID --after-snapshot-id SNAPSHOT_ID \
  --input REVIEW_COMMITMENTS.json

# genuinely spawn each wave-2 clean context, then attest before its canonical return exists
"$MGRAPH" --root "$PROJECT" --host-config "$HOST_CONFIG" --role host \
  pulse-dispatch PULSE_ID REVIEW_COMMITMENT_ID \
  --issuer HOST_ISSUER --host-context-id UNIQUE_HOST_CONTEXT_ID \
  --agent-identity NATIVE_AGENT_ID --fresh-context-contract fresh-context-v1

# after exact wave-2 ingestion
"$MGRAPH" --root "$PROJECT" --host-config "$HOST_CONFIG" --role main \
  pulse-close PULSE_ID
```

The host-owned configuration is one exact JSON object:

```json
{
  "schema_version": 1,
  "policy_revision": "mathgraph-0.3.0",
  "project_id": "PROJECT_ID",
  "adapter_mode": "cooperative",
  "trusted_host_issuers": ["HOST_ISSUER"]
}
```

Use the same explicit `--host-config` for plan, barrier, dispatch, status/audit, and closure. If that
option is omitted, `PROJECT/host_adapter.json` is used when present; absence freezes an empty issuer
list and intentionally makes machine readiness unreachable for that pulse. `pulse-plan` freezes the
issuer set, so changing the active configuration later cannot widen an existing pulse.
`pulse-plan` rejects any bound Wave-1 canonical return, receipt, or ingestion transaction.
`pulse-dispatch` likewise rejects a Wave-2 canonical return, receipt, or ingestion transaction.
These are ordering gates, not file-presence conventions: the transaction ledger prevents a deleted
or tampered result marker from enabling retrospective attestation.

The second-wave task must require inspection of at least one peer node and a registered relation
such as `challenges`, `refines`, `duplicates`, or `supports_candidate`. The relation payload must
name the peer node, the independently repeated check, and the resulting correction or explicit
no-correction boundary; an empty edge does not count. A host follow-up message
only announces the new prompt path; it is not the durable mathematical exchange. Main synthesis
for a profile-required pulse must name the cross-edge receipt or explicitly
report that the collaboration obligation is incomplete.
`check.kind` is exactly one of `independent_reproduction`, `scope_audit`,
`counterexample_search`, or `deduplication`. Disposition compatibility is
`challenges -> correction|conflict`, `refines -> correction|no_correction`,
`duplicates -> duplicate`, and `supports_candidate -> no_correction`. `validate-return` applies
these same closure semantics before ingestion, so vocabulary drift has zero graph or receipt
effect instead of producing a late closed failure.
If a core final return fails graph preflight or ingestion, preserve its bytes and use
`pulse-abort PULSE_ID --failure-phase PHASE --reason REASON`; never void a core commitment.
`procedural_ready` describes complete durable local receipts. `machine_verified_ready` additionally
requires one `host`-role receipt after each real native Wave-2 spawn, binding its prompt,
commitment, host-task scope, unique context, agent identity, and exact clean-context contract.
Main, operator, worker, gateway, and verifier roles cannot write it. This is cooperative
host-attested evidence, not cryptographic identity or an OS sandbox; policy strings alone cannot
satisfy it.
Status-only, deterministic-audit, and tiny mechanical tasks normally bind the
panel as `not_applicable` and may skip it.
Use fresh cross-review contexts when the host can provide them. Never settle a load-bearing
disagreement by majority vote; dispatch an orthogonal specialist or preserve the open boundary.
After two consecutive barriered waves add no new typed information, stop expanding the panel.

Only host-observed task time can trigger the duration notice. Maintain the cumulative union of
active intervals across workers, resumes, experiments, and expansion; overlapping intervals count
once and pauses are excluded. Exactly 1200 seconds does not trigger. At the first observation
strictly greater than 1200 seconds, issue one immutable notice and continue managed work. The notice
names the experimental nature, actual elapsed time and
observed resources, completed/current progress and latest checkpoint, mathematical importance and
continuation value, and the exact impact of stopping. Worker telemetry and heartbeats never drive
or reset this gate. The engine does not pause, cancel, terminate, or signal a process. A host/user
response is optional; only an explicit recorded stop forbids later managed writes.
Keep one `MATHGRAPH_HOST_TASK_SCOPE_ID` (or pass one `--host-task-scope-id`) across every round in
the same host task. Codex uses `CODEX_THREAD_ID` automatically. A reused campaign in a later task
must receive a new host-task scope. All interval coordinates use the host's shared task-relative
timeline, so overlapping spans with different source `clock_epoch` labels still count once.

## Launch workers

```bash
"$MGRAPH" --root "$PROJECT" --role main frontier
"$MGRAPH" --root "$PROJECT" --role main plan-round --workers N
```

The returned host payload contains `mgraph_path`, `round_id`, and each assignment's `prompt_path`,
`return_path`, `artifact_dir_path`, and `assignment_id`. Spawn exactly one worker per prompt. Give it
the prompt path and `mgraph_path`; it can derive `PROJECT_ROOT` as four directory levels above the
assignment file. Do not give it the orchestrator's expected answer. In a v4 round it must use only
the admitted statement interfaces and immutable bounded snapshot in the task card; project-wide
`show/search/context/frontier` commands are denied. V3 compatibility rounds retain their bounded
read/search commands.

V4 workers may read their bound task card and write only their designated return plus files below
their designated artifact and work directories. Every frozen artifact must be declared in the return as a project-relative
`{"path": "...", "sha256": "..."}` object. They must not edit facts, manifests, packets, reviews, or
receipts; review their own work; or cite another draft. Undeclared files, a path outside that
assignment's artifact directory, a symlink, or a mismatched artifact hash make the return invalid.
When workers occupy distinct blackboard lanes, put exact existing space IDs in each memory entry's
`blackboard_write_space_ids` and only frozen cross-lane endpoints in
`blackboard_cross_space_endpoint_node_ids`. Every assignment still receives the same snapshot, but
its write capability is independently sealed; a prompt-only lane restriction is insufficient.
The validator also caps an assignment at 256 files, 16 MiB per file, and 64 MiB total. Assignment,
graph, artifact, and checkpoint caps are hard safety and integrity limits, not price budgets,
priority fields, or reasons to shrink the live panel.
Graph type names are exact. Core worker node types are `space`, `conjecture`, `formula`,
`definition`, `obligation`, `obstacle`, `experiment`, `computation_result`, `source_locator`,
`intuition`, `note`, `conflict`, `mechanism`, `prediction`, `fact_interface_mirror`, and
`type_registry`. Core edge types are `placed_in`, `subspace_of`, `overlaps_with`,
`suggests_proof`, `suggests_refutation`, `supports_candidate`, `challenges`, `refines`,
`generalizes`, `specializes`, `analogous_to`, `depends_on_experiment`, `motivates`, `blocks`,
`resolves`, `convention_variant_of`, `source_for`, `derived_from`, `duplicates`, `supersedes`,
`closes`, `retracts_placement`, `explains_candidate`, `predicts`, and `fails_on`. Do not invent a
near-synonym such as `supports`: an unregistered core-like type must fail worker validation before
handoff. The blackboard reference governs any operator-registered namespaced custom type. A
syntactically legal unregistered namespaced type remains opaque history and does not participate in
semantic traversal until registration. Federation is disabled, so every pulse peer belongs to the
same project and physical root.

Before occupying the canonical return path, each worker writes a mutable draft below its designated
work directory and runs the engine's read-only exact preflight:

```bash
"$MGRAPH" --root "$PROJECT" --role worker preflight-return ROUND_ID ASSIGNMENT_ID \
  --input WORK_DRAFT.json
```

`preflight-return`, canonical `validate-return`, and ingestion use one validation core for prompt
and task-card binding, complete mode semantics, artifacts, blackboard delta, and pulse-review
vocabulary. Both passing and failing preflight leave project bytes unchanged. After it passes, copy
the exact draft bytes without reserialization to the canonical return, then run:

```bash
"$MGRAPH" --root "$PROJECT" --role worker validate-return ROUND_ID ASSIGNMENT_ID
```

It reports the returned `return_sha256` in its explicit final handoff, never editing the return or
artifacts afterward. Do not substitute generic JSON parsing for this command, and do not treat file
appearance or a `draft_present` status as a final handoff.

When a worker uses an external result, it must read
[external_theorem_applicability.md](external_theorem_applicability.md), use a primary source, and
return the complete certificate. Every certificate anchor must appear exactly once beside its
mathematical witness in the proof. A title/arXiv/DOI plus a prose assurance that “the hypotheses
hold” is not a valid return. Use a separate certificate key for each distinct labeled source item and
delta conclusion, even when several items come from the same paper.

It must also read [external_source_reliability.md](external_source_reliability.md) and return tiered
external-source evidence v3. Hash the exact versioned primary artifact and exact result
transcription; run the three baseline sanity checks for every item. Run the three source-status
searches once per exact artifact, hash the canonical `source_audit`, and reuse it for other items from
the same bytes for at most 30 days. Use strict profile and add boundary/toy-case plus
statement/proof-consistency checks for formulas, bridge/transport or degeneration, target-critical
results, corrections, conflicts, suspicious source behavior, or failed cheap checks. Bind the
overall judgment and every correction with unique `[CRIT:...]` anchors. Do not silently repair a
cited theorem. Only an unchanged statement, a uniquely forced non-semantic typo correction, or an
exact official erratum may proceed to submission; put every ambiguous, material-unofficial,
contradicted, retracted, unresolved, or misclassified source route in exploration memory.

When a worker invokes a non-attributed fixed/local textbook result without proving it, it must read
[elementary_result_exemption.md](elementary_result_exemption.md) and return the exact
`elementary_uses` ledger. Every `[ELM:KEY]` anchor occurs once in the proof. The verifier rejects
entries outside the closed whitelist or any hidden family/global/transport/formula conclusion.

When the external use is formula-level, the worker must also return `source_fidelity`: hash the exact
primary artifact, identify source TeX or rendered-primary inspection, list every load-bearing token,
state the glyph-level finding, and add a unique `[SRC:SOURCE_KEY:LABEL]` proof anchor. Plain extracted
text alone is not sufficient for signs, subscripts, superscripts, differentials, indices, or
bracketing.
The same hash must appear in the declared artifact list, and the artifact bytes must live below the
assignment's designated artifact directory. Formula-bearing facts must use a bound round, not direct
`submit`.

Collect by manifest identity:

```bash
"$MGRAPH" --root "$PROJECT" --role main ingest-return ROUND_ID ASSIGNMENT_ID \
  --worker-final-sha256 WORKER_FINAL_SHA256
```

Never ingest an arbitrary path or a hash inferred by the main agent before an explicit worker-final
handoff. Ingestion reruns the same validator, compares the handed-off hash with the current bytes,
records the artifact hashes, and makes the return and declared artifacts read-only. Exact replay is
idempotent; a modified replay fails. If a worker
returns prose or malformed JSON, ask once for repair at the same designated path, but only before an
ingest receipt exists. After receipt creation, the assignment prompt, worker return, and receipt form
one immutable provenance record together with its declared artifacts. Do not edit or reformat any of
them. A later correction or stronger proof must be dispatched as a new memory item and assignment,
producing a new submission and review.

## Launch a verifier

After an ingest receipt reports `submission_id`:

```bash
"$MGRAPH" --root "$PROJECT" --role main make-verifier-task FACT_ID

python3 -B "$SKILL_ROOT/scripts/prepare_verifier_capsule.py" \
  --project-root "$PROJECT" --bundle-sha256 BUNDLE_SHA256 \
  --capsule-root /absolute/host-owned/fresh-review-capsule
```

The host-side capsule command revalidates the bundle's exact authorized file set and atomically
copies only those bytes to a neutral path outside project and skill discovery. Spawn a different
context-free agent with a generic mathematical-review prompt. Give it only the command's
`allowed_read_paths`, semantic binding fields, and `review_return_path`; retain
`host/capability.json` on the host side. Do not give it the project root, skill root, search/show
commands, exploration memory, worker conversation, or another instruction bundle. Require the
verifier to report every path it actually accessed. Any extra access invalidates that run even when
its verdict is correct; preserve it as incident evidence and retry in a new neutral capsule. This is
auditable cooperative containment, not an OS sandbox.

The verifier role intentionally has zero project CLI commands. It must decide whether the submitted
fact really proves, refutes, strengthens, weakens, or replaces that exact assigned claim; unrelated
mathematics cannot close the assignment. If the packet contains an external-source
certificate, the verifier may additionally open the exact primary-source locator recorded in
that certificate and the exact source-reliability locators. It may repeat narrowly targeted searches
using the exact identifier/title for version history, errata, retractions, and counterexamples. It
may not perform broad replacement-theorem search, use a secondary summary to establish a correction,
or replace the failed citation with a different theorem. If that exact source/version is
unavailable or its hash differs, it rejects with a source-access gap.

The verifier checks quantifiers, hypotheses, every inference/calculation, conventions, exact direct
dependencies, and cited-source scope. Before choosing a verdict it makes a private witness ledger:
each load-bearing word such as `all`, `only`, `exact`, `cold`, `at the node`, `uniform`, or
`single-valued` must be paired with an independently checked calculation or argument. In a
degeneration, convergence seen only after a moving or rescaled coordinate change does not establish
convergence to a claimed point of the original compactified family. The verifier must substitute the
section into original homogeneous coordinates (or an invariant chart), compute its limiting point,
and compare it with the stated node/divisor. If the packet does not permit that check, the verdict is
`reject` with a gap. The only permitted verdict strings are `correct` and `reject`; synonyms such as
`incorrect` and `incomplete` are schema errors. It writes the exact review schema to
For a V4 capsule it writes `review_return_path` and nothing else. For a
prospectively marked V5 capsule it writes only `review_draft_path`; the host then runs the returned
`review_submission_path` (or `scripts/submit_neutral_review.py --capsule-root
CAPSULE`). The host program preserves the draft, runs the copied strict
preflight, quarantines any failure with JSON-pointer and allowed-enum
diagnostics, and publishes `review_return_path` only together with a validated
`formally_returned` receipt. The gateway must not consume a mere draft or a
`preflight_passed` receipt.
An historical unmarked V5 capability continues to name its direct
`review_return_path`; its frozen return protocol is not rewritten.

For a family over a punctured base, require a monodromy witness for every claim that a marking,
cycle, polarization, or free energy is both flat and single-valued. Compute or cite the relevant
Picard--Lefschetz action, and distinguish a full symplectic marking from a monodromy-invariant
Lagrangian and from a marking that exists only on a cover. Equivariance under a finite scaling-cover
deck group is not automatically equivariance under homological monodromy. Also check construction
domains: a lift of a base vector field exists on the relative smooth locus, not at a critical point
of the total projection, unless a separate extension theorem is supplied for the resulting tensor.

Treat shared regime words as predicates. In particular, `cold`, `hot`, `neck`, `exterior`, `local`,
and `global` must be explicitly defined in the fact statement or in a shared glossary copied into the
frozen packet. Check the definition itself and then check every labelled object against it. Do not
accept a label merely because the worker writes “this proves it is cold/hot.” If a load-bearing term
is undefined, changes meaning between dependencies and the submitted fact, or fails for even one
labelled object, return `reject` and name that semantic gap.

Treat admitted predecessor statements as the only compositional theorem interface. A worker may read
the predecessor proof for provenance, but may not import a stronger coefficient, estimate, hidden
lemma, or side condition that is absent from the predecessor statement. For every predecessor use,
the verifier must point to an entailing statement clause; a proof-only dependency requires rejection
unless the submitted fact proves that step independently. If the stronger result is meant to be
reused, first expose it in a separately stated, independently reviewed fact.

Applicability is still required after the clause is found. Inventory every scope restriction and
hypothesis stated by that predecessor and bind it to a current witness. A change of ambient category
such as fixed-to-family, connected-to-componentwise, global-meromorphic-to-logarithmic-atlas,
smooth-to-degenerate, or cover-local-to-descended is an explicit transport obligation. Reject a bare
application based only on shared terminology, notation, or a claimed “same setting.”

Track quantifier polarity and chosen witnesses as part of the private ledger. A statement saying
there exists a finite exceptional set, coordinate, marking, orientation, or neighborhood exports an
existential witness, not a canonical one. Do not infer membership or nonmembership in that witness
from the theorem's conclusion, and do not silently replace the witness. A replacement is admissible
only when the submitted proof shows that it retains every literal guarantee; for example, removing
one explicitly good framing from an overinclusive exceptional set requires checking all exceptional
conclusions at that framing. Also reject unproved transports from irreducibility to nonseparating
topology, from a branch count to genus, from genus to a complete A-system, or from an informal
counterclockwise label to the exact model coordinate used for coefficient calibration.

For each external-source certificate, independently locate the exact labeled result and its governing
definitions in the cited primary-source version. Reconstruct the complete source hypothesis list
rather than trusting the worker's list. First inventory all external attributions in the proof and
reject any logical source use without a certificate. Check every target witness, convention conversion, nearby
exclusion, conclusion-strength comparison, and operation between the source and target conclusion.
Treat `standard`, `classical`, and `well known` as prompts to identify a premise, not as evidence.
The result must be locally proved, admitted as a predecessor, certified, or validly declared in the
closed elementary ledger. Independently reconstruct every ledger entry and reject Weierstrass
preparation, moving/degenerating-family claims, plumbing/topology/monodromy, global
Riemann-surface normalization, topological recursion, or source-specific formulas/signs/coefficients
in that lane.
In particular, do not silently pass from a fixed smooth object to a degeneration, from `n >= 1` to an
integrated `n = 0` quantity, from a leading term to a pole-exclusion statement, or from a special
model to an arbitrary curve. Any such step needs the certificate's explicit proved bridge.
Reproduce every statement hash, compare the transcription with source TeX or the rendered primary
page, and rerun the three baseline sanity checks per item. Group exact artifacts by
`source_audit.audit_sha256`, reproduce each source and audit hash once, inspect its three stored
status locators, and check its reuse window. Repeat one unpredictable current status query for a
baseline-only group; if any grouped item is strict, repeat all three searches and the two additional
theorem checks for each strict item. Do not trust the worker's profile, `as_stated`, or correction
label. Escalate or reject a baseline item with an omitted risk. Accept a typo correction only when it
is uniquely forced, non-semantic, and non-strengthening; verify an official erratum by exact locator
and artifact hash. Reject an undisclosed, ambiguous, material-unofficial, contradicted, retracted,
unresolved, stale, or misclassified source claim.
For formula-level attributions, also compare the recorded load-bearing tokens against source TeX or
the rendered primary artifact. A text-extraction rendering that drops a differential, subscript,
minus sign, or bracket is not evidence that the source contains the worker's formula.

```bash
"$MGRAPH" --root "$PROJECT" --role gateway record-review --input REVIEW_RETURN.json
"$MGRAPH" --root "$PROJECT" --role gateway admit FACT_ID --review-id REVIEW_ID
```

The first command returns the immutable `review_id`. Reject if any error or gap remains. String-name
inequality is a procedural independence check, not authenticated identity; the host must genuinely use
a fresh agent/session.

The CLI is a cooperative evidence layer, not authenticated user identity or a host process
supervisor. It may preserve a notice and optional response, but it cannot prove who responded and
never pauses, terminates, or sends a process signal. Host/OS enforcement is a separate boundary.

## Recovery and states

`round-status ROUND_ID` derives assignment states `ready`, `draft_present`, `ingesting`, and `ingested`;
the overall state is `ready`, `in_progress`, or `complete`. Manifests, prompts, returns, and receipts
are durable and hash-bound; after ingestion they are immutable evidence, not editable working files.
A replacement main agent can resume by reading `round.json`, checking `round-status`, and ingesting
only designated returns.

After recovery or any mutation, run `audit`. `graph_errors` concern mathematical DAG integrity;
`workflow_errors` concern submission/packet/review/event/round/receipt provenance. Either makes
`ok=false`.

A counterexample is a discovery event, not the end of the workflow. Once the refuted memory item has
been recorded, ask the engine for the standard two-branch repair round:

```bash
"$MGRAPH" --root "$PROJECT" --role main plan-repair-round MEMORY_ID
```

The generated workers independently pursue a minimal-hypothesis repair and the strongest defensible
replacement. Submit either only after the ordinary verifier gate. Record each novelty query and
corpus with `novelty-record`; inspect the resulting subject ledger with `novelty-status`. A search may
support `no_exact_match_found`, never an unqualified global novelty claim.

## Diversity

At any panel width, cover genuinely different modes: constructive proof, adversarial
counterexample/missing hypotheses, exact symbolic computation, controlled numerical evidence,
primary-literature scope, or a different proof architecture. Use all available clean-context slots
only while distinct eligible channels remain. Agreement among workers is not admission.
