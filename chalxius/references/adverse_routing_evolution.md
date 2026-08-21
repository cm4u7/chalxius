# Adverse routing evolution and attack reports

## Contents

1. [Purpose and authority boundary](#purpose-and-authority-boundary)
2. [Three Research attack roles](#three-research-attack-roles)
3. [Prospective activation](#prospective-activation)
4. [Failure-report-to-route lifecycle](#failure-report-to-route-lifecycle)
5. [Worker return contract](#worker-return-contract)
6. [Independent paired allocation](#independent-paired-allocation)
7. [Attack report and Main synthesis](#attack-report-and-main-synthesis)
8. [Future task-card routing](#future-task-card-routing)
9. [Compatibility and recovery](#compatibility-and-recovery)

## Purpose and authority boundary

The adverse-routing extension lets an adverse worker retain either a surviving
counterexample or a productive challenge as a concrete failure report. A
productive challenge is one that does not refute the repaired theorem but
forces a load-bearing hypothesis, scope, definition, proof route, source,
computation, or boundary change. It does not let a worker rewrite its own
prompt, activate a route, certify a counterexample, or write a Fact.

The persistent lifecycle is:

```text
surviving counterexample or productive challenge
  -> immutable concrete failure report
  -> Main comparison and abstraction
  -> bounded Main decision
  -> future-only active route rule, if warranted
```

Attack cases, proposals, decisions, reports, and rules have
`truth_effect="none"`. Both result kinds remain worker-reported Research until
independently assessed through the normal research and certification
boundaries. Approving a routing heuristic says only that it is useful guidance
for future adverse exploration.

The attack report is separate from the CHX runtime architecture report:

- the attack report describes mathematical or logical attacks found by workers
  and candidate routing improvements;
- the CHX report describes only problems caused or materially amplified by the
  Chalxius architecture.

Never copy one report into the other or treat either as Fact evidence.

For current load-bearing work, Main explicitly selects the constructive
Research ids and the canonical Candidate Fact bytes to be attacked. Those Fact
bytes may be authored by Main. Author labels and other provenance metadata
preserve lineage but do not establish mathematical validity, require worker
authorship, or replace any later review boundary.

## Three Research attack roles

Keep three layers distinct:

1. A production worker is a constructive peer researcher. It may record a
   boundary, obstruction, or counterexample found while proving, computing,
   interpreting, or searching sources, but prospective public production does
   not dispatch a `refute` worker.
2. A second-subround `refute` supervisor attacks exact first-subround returns. Its scope
   is proof logic, program-math/code, source/scope, or integration. It can
   induce a later copy-on-write Research repair, but it does not activate
   attack routes or use Pulse for live peer editing. Its default target is new
   Research, not an admitted Fact premise.
3. Candidate fresh-adverse review attacks the whole frozen Candidate Fact
   content selected by Main and its dispositions before expensive sealing. It
   is the formal engineering acceptance attack; a fresh verifier and
   Gateway-owned Certification still follow it.

Only a `refute` return carrying the current adverse-routing contract and an
explicit qualifying `attack_learning` object supplies a failure report.
Supervisor or Candidate findings may justify Research repair, but workers do
not turn them into reusable rules. The default attack report remains a sparse
Main-facing queue of at most three concrete failure families and emits no
filler. Main may synthesize, compress, merge, or reject them.

## Prospective activation

Default adverse reporting is enabled for V5. Every host task produces a
separate attack report, including an explicit zero report. A newly frozen V5
`refute` card receives the baseline and already Main-synthesized future rules. The
first such card lazily materializes only
`PROJECT/governance/adverse-routing/`; merely loading newer bytes or reading
status does not write project state. The compatibility command below may still
materialize the same state explicitly:

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-enable \
  --actor OPERATOR --reason "Materialize prospective adverse reporting."
```

Existing rounds, task cards, returns, and V1-V4 work units never acquire the
extension merely because they load newer bytes. A round frozen before this
prospective default retains its original task-card and return schema and never
receives a retroactive attack-learning obligation, warning, downgrade, or redo
request.

Query the state with:

```bash
"$MGRAPH" --root "$PROJECT" --role main attack-route-status
```

Default reporting does not change `fast`, `auto`, or `deep`, and it does not
change the invariant V5 Fact-admission contract. L2 may select `refute` because
the adverse capability is already user-authorized prospectively; the separate
program-math review and assurance-equivalence guards remain enforced.

## Failure-report-to-route lifecycle

For a current adverse-bound task card, a `counterexample` return must include a
schema-3 `attack_learning` failure report with
`result_kind="surviving_counterexample"`. An `evidence`, `insight`, or
`challenge` return may include the same report with
`result_kind="productive_challenge"` only when the attack forced one or more
explicit value effects. Ingestion first creates the ordinary cumulative
Research entry, then records an exact attack case binding the round,
assignment, task-card hash, return hash, target Research, attack Research,
result kind, host-task scope, witnesses, reproduction steps, value effects,
and exact success boundary.

The worker report contains no trigger, instruction, scope note, or proposed
route rule. The case is labeled `worker_reported_counterexample_nontruth` or
`worker_reported_productive_challenge_nontruth`. Schema and hash checks
establish provenance and reproducibility of the report, not the mathematical
truth of the refutation or of the claimed value.

Current worker failure reports, Main decision reasons, persistent route rules,
CHX/PHX architecture records, and protocol artifacts use English internal
prose. Mathematical notation, exact user claims, source quotations, and frozen
historical bytes are preserved in their original language and are not rewritten
by this policy.

Main compares one or more concrete reports, deduplicates failure families, and
may synthesize a persistent rule only at the mechanism level. Main may also
reject the report as too specific or redundant. A synthesized rule has a hard
720-Unicode-code-point total budget, smaller per-field budgets, at most two
false-positive guards, at most eight trigger items, and a sixteen-active-rule
project cap. Oversize rules must be semantically compressed; truncation is
forbidden. Decisions and disablements affect only task cards frozen later;
already frozen future task cards are never rewritten.

## Worker return contract

Use the following complete V5 top-level return template. Replace every
`COPY_EXACT_*` value from the frozen task card or assignment, keep the field
set exact, and write it to the task card's `return_relpath`.
Do not start from a schema-v4 example. A prospective 0.4.3 task card already
requires `obligation_dispositions`, `computation_manifest`, and
`research_assurance`; the extension adds exactly one further top-level field,
`attack_learning`:

```json
{
  "schema_version": 5,
  "project_id": "COPY_EXACT_PROJECT_ID_FROM_TASK_CARD",
  "round_id": "COPY_EXACT_ROUND_ID_FROM_TASK_CARD",
  "assignment_id": "COPY_EXACT_ASSIGNMENT_ID_FROM_TASK_CARD",
  "worker_id": "COPY_EXACT_WORKER_ID_FROM_TASK_CARD",
  "task_card_sha256": "COPY_EXACT_TASK_CARD_SHA256_FROM_ASSIGNMENT",
  "blackboard_snapshot_sha256": "COPY_EXACT_BLACKBOARD_SNAPSHOT_SHA256_FROM_ASSIGNMENT",
  "outcome": "counterexample",
  "claim": "State the exact challenged conclusion that fails.",
  "content": "Give the checked counterexample and its bounded derivation.",
  "narrative": {
    "rationale": "Explain why this attack targets the assigned claim.",
    "summary": "Summarize the successful attack.",
    "intuition": "Give bounded intuition without changing the claim.",
    "limitations": "State what the counterexample does not refute."
  },
  "artifacts": [],
  "obligation_dispositions": [],
  "computation_manifest": null,
  "research_assurance": {
    "source_uses": [],
    "route_invalidations": [],
    "extremal_cases": [],
    "claim_strength": [],
    "contour_substitutions": [],
    "claimed_structures": [],
    "program_math_alignments": []
  },
  "attack_learning": {
    "schema_version": 3,
    "result_kind": "surviving_counterexample",
    "attack_family": "quantifier_witness",
    "target_pattern": "A pointwise witness is treated as canonical and uniform.",
    "failure_mechanism": "The proof silently reuses one witness outside its scope.",
    "premise_witnesses": ["Each parameter has a locally valid witness."],
    "conclusion_failure_witness": "Two parameters require incompatible witnesses.",
    "reproduction_steps": ["Choose the parameters.", "Check the premises.", "Show no common witness exists."],
    "success_boundary": "Refutes uniformity, not pointwise existence.",
    "value_effects": [
      {
        "effect_kind": "claim_refuted",
        "before": "The route asserts one uniform witness.",
        "after": "Only pointwise existence remains viable.",
        "evidence": "The two-parameter witness construction is reproduced above."
      }
    ]
  }
}
```

The exact top-level keys are therefore `schema_version`, `project_id`,
`round_id`, `assignment_id`, `worker_id`, `task_card_sha256`,
`blackboard_snapshot_sha256`, `outcome`, `claim`, `content`, `narrative`,
`artifacts`, `obligation_dispositions`, `computation_manifest`,
`research_assurance`, and `attack_learning`. Artifact entries and assurance
objects must match the exact frozen card revision; the empty values above are
valid only when the card has no corresponding obligation or computation stage.

For `evidence`, `insight`, or `challenge`, `attack_learning` is either `null` or
a complete schema-3 failure report with `result_kind="productive_challenge"`. Its
`value_effects` must identify at least one exact before/after/evidence triple
using one of `hypothesis_added`, `scope_narrowed`, `definition_repaired`,
`proof_route_replaced`, `source_defect_isolated`, `computation_corrected`, or
`boundary_made_explicit`. A `proof` or `dead_end` uses `null`. A legacy frozen
card retains its old learning schema or lacks the field entirely; never add or
rewrite it retroactively.

Workers never supply triggers. For a Main-synthesized rule, trigger axes combine
conjunctively. Terms are case-insensitive substrings of the Research claim;
metadata signals come only from the explicit `logic_signals` list in Research
metadata. A universal rule must set `universal_refute=true` and leave every
filter list empty.

## Historical paired allocation and prospective replacement

Historical direct-allocation contracts may contain paired adverse assignments
and remain byte-exact readable. New public production rounds freeze
`chalxius-v5-logical-component-production-allocation-2`: `workers` counts only
constructive primaries, `refute` is rejected, and no pair is appended. The exact
boolean metadata predicate `independent_adverse_required` remains meaningful,
but only as a later exact-Candidate adverse-readiness marker. Claim text and
domain labels cannot infer it. The earlier
`chalxius-v5-supervision-only-refute-allocation-1` remains readable for frozen
production rounds.

Second-subround supervision supplies the Research attack pass. The normal
Candidate adverse closure/disposition remains the later whole-candidate release
gate, and route activation still requires a Main decision. Neither stage
creates a second Fact authority.

Before Candidate artifact normalization, source audit, capsule construction,
or sealing, the prospective fresh-adverse readiness gate inspects only
content-hashed Research headers, canonical Candidate Fact bytes, and the exact
refute assignment/card/return/Research-product lineage. For each maximal selected
constructive branch with `independent_adverse_required=true`, one later
independent refute must directly target that branch head, freeze every exact
Candidate Fact hash in its task-card capabilities, be non-aborted and have a
hash-valid Research product,
appear in `adverse_actor_ids`, and have a Candidate disposition. A paired
adverse assignment or a separately planned primary `refute` can satisfy the
gate. Missing or inherited actor labels cannot. Failure is
`fresh_adverse_missing` and occurs before high-cost release work.

For a prospectively prepared Candidate-Fact target, Main uses the public,
Main-only command:

```bash
"$MGRAPH" --root "$PROJECT" --role main \
  plan-candidate-adverse RESEARCH_ID \
  --host-task-scope-id HOST_TASK_SCOPE_ID
```

The target must be active, non-stale, bind exactly one current
`candidate_fact` artifact, and explicitly require independent adverse review.
An exact retry in the same host scope returns the existing live or completed
round; a scope drift, stale target, missing byte binding, ordinary production
claim, or duplicate live exact retry fails closed. This command does not change
the constructive-only first Research subround or the supervision lane.

For one exact Research target and canonical Candidate Fact path selected by
Main, Main first runs
`prepare-candidate-adverse-target SELECTED_RESEARCH_ID --candidate-fact PROJECT_RELATIVE_PATH`.
The command canonical-validates and consumes the exact project-contained bytes,
binds every applicable completed supervision result (possibly none when no
scope applies), and creates or reuses one nontruth synthesis target. The bytes
may be Main-authored; producer/container/author provenance does not certify
them. Neither this preparation nor `plan-candidate-adverse` launches a worker.
Main must actually launch the exact refute worker through the host and confirm
that it started. This creates no new dispatch receipt or mathematical gate.

The sealed readiness receipt instructs the fresh verifier to adjudicate every
bound adverse disposition. It does not ask the verifier to rerun packaging and
does not make the adverse return true. A mathematical verifier finding may
still require a copy-on-write repair; the gate eliminates late mechanical,
freshness, scope, and candidate-byte failures rather than promising that
substantive mathematical review can never disagree.
The verifier returns review bytes only; Gateway owns `certification-record` and
the later Fact-admission revalidation.

## Attack report and Main synthesis

At host-task completion, Main queries the exact task scope, including an
explicit zero queue:

```bash
"$MGRAPH" --root "$PROJECT" --role main attack-report \
  --host-task-scope-id HOST_TASK_SCOPE_ID
```

The default report is intentionally selective:

- at most three pending failure families;
- one item per family, even when several concrete reports share it;
- one concrete reported failure and its success boundary;
- one reviewed ordinary-language family description and support kind/count;
- no worker-authored trigger, instruction, scope note, or persistent rule.

The ordinary-language sentence comes from a reviewed family vocabulary, never
from worker-authored route instructions. A new or unknown family remains in
`--full` and is omitted from the default report until that vocabulary is
reviewed; the report never invents filler merely to reach its quota.

If no proposal survives this filter, recommend nothing. Do not fill a quota.
The full coverage/case audit remains available for internal diagnosis:

```bash
"$MGRAPH" --root "$PROJECT" --role main attack-report \
  --host-task-scope-id HOST_TASK_SCOPE_ID --full
```

That full form retains every validated scope round, assignment, task card,
return/Research-product state (with any receipt as optional provenance), paired adverse coverage record, case, technical witness,
proposal status, and the explicit worker-reported nontruth boundary. It is not
the normal user-facing report.

An empty `attacks` array is never self-interpreting. It establishes a completed
zero only with `coverage_status=dispatched-no-surviving-attack` and complete
paired return coverage, or records that no independent pair was required.
A plan or assignment/card alone is not actual dispatch. Main must separately
launch and confirm the worker before treating the planned attack as under way;
pending or quarantined returns remain explicitly incomplete. The historical
coverage labels in the report are workflow projections, not proof of a native
process launch. A mixed or missing current scope, pair mismatch, or
card/manifest/return drift fails closed. Historical null-scope cards stay
readable and are not assigned to a newer scope.

Main compares the concrete reports with active routes. It either rejects a
report or supplies a newly written mechanism-level rule. Copying worker text is
not an action. The decision records that Main excluded concrete case detail and
whether semantic compression was needed.

```bash
"$MGRAPH" --root "$PROJECT" --role main attack-route-decide PROPOSAL_ID \
  --input DECISION.json --actor main
```

Example approval input:

```json
{
  "action": "approve_modified",
  "reason": "Several reports share one mechanism-level failure family.",
  "rule": {
    "attack_family": "quantifier_witness",
    "trigger": {
      "research_kinds": ["challenge"],
      "claim_terms_any": ["uniform"],
      "metadata_signals_any": ["quantifier_sensitive"],
      "universal_refute": false
    },
    "instruction": "Attack changes in quantifier order or witness dependency.",
    "false_positive_guards": ["Accept explicitly pointwise conclusions."],
    "scope_note": "Use when witness dependency is load-bearing."
  },
  "governance": {
    "abstraction_level": "mechanism",
    "concrete_evidence_excluded": true,
    "compression": "compressed"
  }
}
```

Disable an approved rule prospectively with:

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-disable RULE_ID \
  --actor USER --reason "The route was too broad."
```

Only Main may decide. The Operator may materialize reporting state or disable a
rule prospectively, but cannot approve worker reports.

## Future task-card routing

Every newly frozen V5 refutation task card carries:

- the fixed low-cost baseline families for exact target, implication
  direction, missing premise, type/domain, quantifier/witness,
  scope/transport, cases/boundaries, circularity, and hidden-conjunct
  splitting;
- for an exact `adverse_domain_profile` of `philosophy` or `mixed`, or a
  validated Paper-continuation binding with that domain, three additional
  philosophy-only families: faithful ordinary-language substitution;
  burden-of-proof plus strongest charitable objection plus independent failure
  surfaces; and quantifier/modal/scope/exception equivalence;
- at most sixteen active Main-synthesized rules whose triggers match the frozen
  Research entry;
- exact hashes for both lists;
- the requirement that a counterexample supplies a schema-3 concrete failure
  report, while a non-refuting attack is recorded only with a structured
  productive-challenge value witness.

Every new ordinary refutation card carries the original eight families plus
`baseline_hidden_conjunct_split`. The split requires distinct truth conditions
or a separating case and must not manufacture claims from grammatical
coordination or one explicitly defined construction. The three philosophy
families are selected only from the exact frozen domain binding. Claim text,
titles, terminology, and substring matching cannot activate them. A generic
philosophy task may declare:

```json
{
  "kind": "challenge",
  "claim": "Challenge the stated argument.",
  "adverse_domain_profile": "philosophy"
}
```

`mathematics` leaves the philosophy set inactive; `mixed` activates it because
the bounded task explicitly contains a philosophy component. The
ordinary-language attack holds stipulated definitions fixed, replaces
load-bearing terms faithfully, and identifies a hidden premise, equivocation,
or unsupported step only when the inference changes. The combined dialectical
attack keeps burdens atomic, uses the strongest good-faith objection supported
by the source, and prevents one local repair from silently closing independent
failure surfaces. The equivalence attack seeks a separating scenario when
quantifier, modality, negation/operator scope, or exception conditions drift.

One further fixed family,
`baseline_program_math_semantic_alignment`, is appended only to the generated
review of a computation-bearing Research product that passed its worker stage. The
scope check requires an actual positive computation-stage count, the generated
`program_math_review` metadata, and exact capability-bound
`computation_source` and `computation_output` artifacts. A claim that merely
mentions code cannot activate it.

The program-math instruction attacks formula-to-code anchors, signs and
conventions, loop/index domains and boundary cases, mathematical-object
representations and multiplicity, truncation order or precision, output
interpretation, and supposedly independent checks that replay the same bug.
It is queued as future Research after producer ingestion; it does not interrupt
the producer, mutate the source return, or certify a flaw. CHX architecture
issues are forbidden inputs to this route.

The task card remains the immutable capability boundary. A later approval,
modification, rejection, or disablement cannot mutate a frozen card. More than
sixteen matching current rules fails planning visibly so Main can consolidate
or disable routes instead of silently truncating them. Historical schema-3/4
cards retain their original twenty-four-rule compatibility bound.

This revision is prospective. Schema-1/2 cards retain the original legacy
learning contract; schema-3 cards retain the earlier eight-rule baseline plus
its computation scope. They are validated under their frozen bytes and never
receive the hidden-conjunct or philosophy families by backfill.

Baseline families and approved routes are attack guidance, not a universal
exploration-completion checklist and not a second adverse certification gate.
Candidate Release continues to bind the actual challenge/counterexample
Research already linked to its branch.

## Compatibility and recovery

- Do not materialize or backfill governance state merely to modernize an old
  project; default status and explicit zero reports are read-only.
- Do not backfill attack cases from old returns or describe their absence as a
  warning, blocker, lower standard, or reason to redo work.
- Mixed 0.4.0 and later bytes do not change a frozen old task card.
- A malformed case, proposal, decision, rule, disablement, lineage, or hash
  fails route selection and status/report generation.
- An approved decision whose rule materialization was interrupted can be
  retried idempotently; it never authorizes a different decision for the same
  proposal.
- Disabling a rule preserves every historical case, proposal, decision, rule,
  report reconstruction, and frozen task card.
