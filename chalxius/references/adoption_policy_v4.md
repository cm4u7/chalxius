# V4 Adoption Policy and Preflight

> **V5 adaptation.** This reference preserves the V4 task-profile vocabulary
> used by `chalxius`. The historical `operate-mathgraph-unified` string remains
> only an artifact compatibility id. In V5, the hash-bound
> `execution_profile` plans exploration: deep requests every applicable
> feature, auto follows deterministic workload triggers, and fast leaves
> applicable high-cost work available. Profile completion and adoption advice
> have no Fact-admission authority. Every mode uses the same V5 Candidate
> Release, Certification Decision, and Fact gateway.

Read this reference before creating v4 memory, planning a round, deciding whether to use an
experiment/checkpoint, preparing several candidate facts, or producing external expert
communication.

## Full V4 versus conditional activation

Adopt the V4 trust model in full. The following communication protocol is always required:

1. a compact non-truth control plane;
2. a typed mathematical-state plane with an explicit truth boundary;
3. a non-truth narrative plane;
4. frozen-snapshot-only visibility between workers in the same round.

“Layered adoption” does not mean falling back to V3 or omitting part of that protocol. It means
activating additional workload-shape mechanisms only when their semantic trigger is true. Once a
trigger is true, the mechanism is mandatory and cannot be disabled by a worker.

## Execution-profile live-agent allocation

Read `execution_profile.exploration_features.parallel_clean_context_panel`.
When its status is `required` and the host exposes callable subagents, fill all
currently callable clean-context slots for which a genuinely distinct eligible
direction exists. Constructive and adversarial exploration are the minimum
coverage classes, not a width ceiling; add every distinct literature,
interpretation, computation, convention, geometry, or protocol direction
allowed by current host capacity. When status is `available`, the panel is
opt-in; when `not_applicable`, do not manufacture one.

Read `execution_profile.exploration_features.barriered_blackboard_pulse`.
When it is `required`, the panel must communicate through the mathematical-state
plane, not only transient host messages. Persist a pulse plan before first-wave
dispatch. After committed returns are validated and ingested, freeze a
second-wave snapshot and create its review assignments. Derive a barrier that
binds those existing assignments to the real ingestion receipts, record trusted
host dispatch, then require at least one worker to challenge, refine,
deduplicate, or otherwise connect to a peer's typed node. The cross-edge payload
must name the inspected peer node, the independently repeated check, and the
resulting correction or explicit no-correction boundary. A content-free edge is
not communication. Only committed cross-reviews contribute to Pulse closure
advice. Each valid return enters cumulative Research independently. A failed or
malformed peer is quarantined locally and does not destroy already valid
contributions; a whole-pulse abort is reserved for an explicit stop of future
dispatch. When pulse status is `available`, this mechanism is opt-in; when
`not_applicable`, frozen-snapshot separation still applies but a pulse is not
required.

For a required panel, launch every eligible, genuinely distinct channel up to
currently callable host capacity. For an available panel, explicit opt-in may
choose a bounded set. Within either selected panel, estimated or actual duration,
monetary or invocation cost, experiment budget estimates or burn, and score
magnitude may order starts/load only; they never weaken a required profile
feature or truth gate. Status reports, deterministic audits, and tiny mechanical
changes normally have panel status `not_applicable`. Fresh verification is
always separate from exploratory exchange.
This is priority/load ordering only, never eligibility.

Estimates never trigger notification or a continuation decision. Only host-observed cumulative
active task time strictly greater than 1200 seconds triggers one required disclosure while work
continues. It does not require an acknowledgement, pause work, or send a process signal. A host or
user may later record an explicit stop, which only forbids subsequent managed writes. Hard safety limits,
artifact integrity, checkpoint compatibility, and actual resource ceilings remain orthogonal
controls; none grants estimates authority over research-agent allocation.
New task cards bind a hashed `host_task_scope_id`: all rounds and workers in one host task share its
clock, but another task does not inherit elapsed time merely because it reuses the same campaign.
The source must be an explicit `--host-task-scope-id`, `MATHGRAPH_HOST_TASK_SCOPE_ID`, or
`CODEX_THREAD_ID`; if none exists, `plan-round` fails before creating a round. A PID/time fallback
is forbidden because it would silently split one task across CLI invocations. In the shared
schema-2 governance ledger, campaign and memory IDs are provenance only; the project and host-task
scope are the clock identity.

## Run preflight

Create a workload profile from `assets/workload_profile.v4.example.json`, then run:

```bash
"$MGRAPH" --root "$PROJECT" --role main adoption-plan --input WORKLOAD.json
```

The profile records activity, audience, computation role, advisory duration estimate, stage/resume
shape, candidate-fact shape, and source/ambiguity/convention/quantifier/terminology sensitivity. The
result is deterministic and hash-bound. `source_ambiguity` is optional for frozen-profile
compatibility: absence routes exactly as `false` without materializing a new field or changing any
legacy hash; explicit `true` requires `source_claim=true`. The estimate remains audit metadata but
never changes feature activation. `plan-round` stores a compact binding in every task card;
changing a feature-bearing workload property requires replanning rather than silently bypassing a
newly required feature.

`plan-round` also freezes `profile_obligations`, recomputed from every
assignment's bound execution profile. It lists the exact assignments suggested
for each exploration feature and a canonical obligation hash. It is repair
guidance, not an operator completion checklist or a truth gate.

After governed returns are canonically ingested,
`profile-closure-status ROUND_ID` may report incomplete planned work.
`profile-closure-record ROUND_ID --input ... --actor ...` may append exact
evidence-bound advice to cumulative Research. Missing or drifted profile
closure never blocks a V5 verifier capsule, Candidate Release, Certification
Decision, or Fact admission. Those transitions enforce their own exact source,
replay, adverse-disposition, atomic-DAG, and fresh-verifier gates.

Profile closure remains `workflow_readiness_only` and outside the invariant
Fact-admission contract. Do not call host claims machine-verified: callable
panel width, specialist identity, campaign scope, and synthesis subject linkage
are procedural host attestations. Native validation combined with such a scope
is `mixed_procedural_and_machine_verified`.

The trigger boundary is deliberate. `source_claim=true` always requires the unchanged
`source_claim_gate`; ambiguity can never satisfy or relax that gate. For Auto paper-led literature,
an unambiguous source claim requires Paper Logic but leaves Paper Audit, full mirroring, and broad
sensitive exploration available. Explicit ambiguity additionally requires Paper Audit and a
full-fidelity mirror, and counts as a sensitive signal for panel, pulse, and specialist routing.
Interpretation still requires Paper Audit and a mirror even when ambiguity is absent; refutation
still requires Paper Audit. Convention, quantifier, and terminology flags independently remain
sensitive exploration signals.

## Trigger table

| Feature | Required when |
|---|---|
| `experiment_checkpoint` | computation is multi-stage or `resume_required` |
| `artifact_replay` | computation is load-bearing in a proof |
| `atomic_fact_bundle` | candidate facts have internal dependencies or explicitly require all-or-none visibility |
| `terminology_export_lint` | audience is expert/advisor/publication, activity is export, or terminology is sensitive |
| `source_claim_gate` | a versioned source claim is bound |
| `convention_gate` | the statement is convention-sensitive |
| `quantifier_gate` | quantifier or witness dependency is load-bearing |

A single-stage non-resumable computation may use ordinary frozen assignment artifacts regardless
of whether its duration estimate is small, huge, or unknown. Several independent candidate facts
may use separate ordinary admissions. Internal notes do not require expert-export lint. These are
workflow-shape controls, not estimate, price, or score gates and not weakened truth semantics.

If an experiment is required, return validation requires at least one valid finalized experiment
receipt whose selected outputs are present in the declared artifact manifest. A mutable checkpoint
or unfinalized workspace never satisfies this requirement.

An exact pre-revision adoption binding whose experiment requirement was activated by an estimate
is archival-only evidence. Audit and historical display may parse it, but start, event, resume,
finalize, observe, optional decision, worker-return validation, ingestion, and current receipt gates reject
it with a replan requirement. Do not reinterpret or rewrite its frozen bytes; create a new round
under the current estimate-advisory policy.

When `terminology_export_lint` is required, route admitted facts through
`lint-expert-document` and `reports/expert-lint-receipts/`, but route exploration mechanisms through
`lint-interpret-document` and `reports/interpret-lint-receipts/`. The applicable readiness consumer
rechecks the exact draft and exact card bytes; missing, failed, stale, or cross-schema evidence
fails closed. Either receipt certifies communication hygiene only and has no mathematical truth
effect.

If an atomic fact bundle is required, a normal single `fact_submission` return is rejected. The
dedicated mini-DAG remains candidate-only until one clean bundle review and one all-or-none
acceptance marker succeed. After acceptance, ordinary `show/search/context/closure`, campaign
targets, statement interfaces, and cascade revoke see the bundle facts as admitted state. Any
pre-marker failure exposes zero facts.

## Compact frontier model

The compact four-factor model is an explicit user-authorized revision of the original guide's
eight-raw-metric proposal. New V4 memory uses four factors as the controlling priority interface;
the eight-dimensional form below survives only as a read-time compatibility projection for
historical records.

New v4 memory should provide four operator-facing factors:

```json
{
  "decision_profile": {
    "impact": 0.8,
    "information_value": 0.7,
    "tractability": 0.9,
    "burden": 0.2
  }
}
```

Engine readiness remains derived. The score components are:

```text
feasibility = 0.5 * tractability + 0.5 * readiness
score =
  0.35 * impact
+ 0.25 * information_value
+ 0.20 * feasibility
+ 0.20 * (1 - burden)
```

Legacy eight-metric v4 memory is read without rewriting and projected as:

```text
impact            = 0.5 priority + 0.5 target_relevance
information_value = 0.4 decisiveness + 0.4 information_gain + 0.2 novelty
tractability      = testability
burden            = 0.6 estimated_cost + 0.4 risk
```

Do not mix the four-factor profile with legacy raw metrics in one new memory event. If a new v4
memory is not scored yet, the engine stores a neutral four-factor profile (`0.5` on every factor);
it does not synthesize eight legacy fields. The score orders work; it never proves novelty, truth,
target closure, eligibility, launch, panel scale, notification, or stopping. Every V4 `frontier`
entry exposes the machine-readable marker:

```json
{"score_role": "priority_ordering_only"}
```

There is no score cutoff. Explicitly selected low-score memory remains schedulable, and automatic
capacity truncation leaves lower-ranked active entries in actionable backlog. `estimated_cost` and
the compact `burden` factor may change this ordering only. Duration estimates may inform an
operator's explicit burden/load-order assessment, but never activate an adoption feature or any
agent-control transition. Stop conditions and admitted facts remain authoritative.

The historical model experiment retained 9 of the guide score's real-fixture Top 10, had pairwise
rank agreement about 0.90, and increased the matched high-versus-low-cost separation from 0.08 to
0.096. This is calibration evidence for ordering only; it grants no cutoff or control authority.
