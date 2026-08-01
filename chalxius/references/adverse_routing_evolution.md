# Adverse routing evolution and attack reports

## Contents

1. [Purpose and authority boundary](#purpose-and-authority-boundary)
2. [Prospective activation](#prospective-activation)
3. [Case-to-rule lifecycle](#case-to-rule-lifecycle)
4. [Worker return contract](#worker-return-contract)
5. [Attack report and user decision](#attack-report-and-user-decision)
6. [Future task-card routing](#future-task-card-routing)
7. [Compatibility and recovery](#compatibility-and-recovery)

## Purpose and authority boundary

The adverse-routing extension lets an adverse worker retain either a surviving
counterexample or a productive challenge and propose a reusable attack rule. A
productive challenge is one that does not refute the repaired theorem but
forces a load-bearing hypothesis, scope, definition, proof route, source,
computation, or boundary change. It does not let a worker rewrite its own
prompt, activate a route, certify a counterexample, or write a Fact.

The persistent lifecycle is:

```text
surviving counterexample or productive challenge
  -> immutable attack case
  -> immutable route proposal
  -> operator decision
  -> future-only active route rule
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

## Prospective activation

Default adverse reporting is enabled for V5. Every host task produces a
separate attack report, including an explicit zero report. A newly frozen V5
`refute` card receives the baseline and already user-approved future rules. The
first such card lazily materializes only
`PROJECT/governance/adverse-routing/`; merely loading newer bytes or reading
status does not write project state. The compatibility command below may still
materialize the same state explicitly:

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-enable \
  --actor USER --reason "Enable user-governed adverse routing evolution."
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

## Case-to-rule lifecycle

For a current adverse-bound task card, a `counterexample` return must include a
schema-2 `attack_learning` object with
`result_kind="surviving_counterexample"`. An `evidence`, `insight`, or
`challenge` return may include the same object with
`result_kind="productive_challenge"` only when the attack forced one or more
explicit value effects. Ingestion first creates the ordinary cumulative
Research entry, then records:

1. an exact attack case binding the round, assignment, task-card hash, return
   hash, target Research, attack Research, result kind, host-task scope,
   witnesses, reproduction steps, value effects, and exact success boundary;
2. one proposed route rule containing a deterministic trigger, attack
   instruction, false-positive guards, and scope note.

The case is labeled `worker_reported_counterexample_nontruth` or
`worker_reported_productive_challenge_nontruth`. Schema and hash checks
establish provenance and reproducibility of the report, not the mathematical
truth of the refutation or of the claimed value.

Proposal creation has no routing effect. Exactly one immutable user decision
may later approve it unchanged, approve a modified rule, or reject it. Only an
approved rule is eligible for future task cards. A rule may subsequently be
disabled; both approval and disablement apply only to work units frozen later.

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
    "schema_version": 2,
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
    ],
    "route_rule": {
      "attack_family": "quantifier_witness",
      "trigger": {
        "research_kinds": ["challenge"],
        "claim_terms_any": ["uniform"],
        "metadata_signals_any": ["quantifier_sensitive"],
        "universal_refute": false
      },
      "instruction": "Attack silent witness replacement.",
      "false_positive_guards": ["Do not demand one witness for a literal pointwise claim."],
      "scope_note": "Use when witness identity or uniformity is load-bearing."
    }
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
a complete schema-2 object with `result_kind="productive_challenge"`. Its
`value_effects` must identify at least one exact before/after/evidence triple
using one of `hypothesis_added`, `scope_narrowed`, `definition_repaired`,
`proof_route_replaced`, `source_defect_isolated`, `computation_corrected`, or
`boundary_made_explicit`. A `proof` or `dead_end` uses `null`. A legacy frozen
card retains its old learning schema or lacks the field entirely; never add or
rewrite it retroactively.

Triggers combine their nonempty axes conjunctively. Terms are
case-insensitive substrings of the Research claim; metadata signals come only
from the explicit `logic_signals` list in Research metadata. A universal rule
must set `universal_refute=true` and leave every filter list empty. Workers may
propose universal rules, but they never activate them.

## Attack report and user decision

At host-task completion, query the exact task scope and present the result to
the user even when it contains zero attacks:

```bash
"$MGRAPH" --root "$PROJECT" --role main attack-report \
  --host-task-scope-id HOST_TASK_SCOPE_ID
```

Report separately:

- each case id, result kind, family, target, mechanism, witnesses,
  reproduction steps, exact success boundary, and concrete value effects;
- the proposed trigger, instruction, guards, and scope;
- its status: pending, approved, modified-and-approved, rejected, or disabled;
- the explicit evidence boundary that the case is worker-reported nontruth;
- whether a user decision is pending.

The user chooses one of three exact actions. `approve` copies the proposal and
requires `rule=null`. `approve_modified` supplies a complete replacement rule.
`reject` requires `rule=null`.

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-decide PROPOSAL_ID \
  --input DECISION.json --actor USER
```

Example approval input:

```json
{
  "action": "approve",
  "reason": "The trigger and false-positive guard are reusable.",
  "rule": null
}
```

Disable an approved rule prospectively with:

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-disable RULE_ID \
  --actor USER --reason "The route was too broad."
```

Only the `operator` role may enable, decide, or disable. `main` may read status
and produce the attack report but cannot alter routing.

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
- at most 24 active user-approved rules whose triggers match the frozen
  Research entry;
- exact hashes for both lists;
- the requirement that a counterexample supplies schema-2 learning, while a
  non-refuting attack creates a proposal only when it supplies a structured
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
review of a successfully ingested computation-bearing Research return. The
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
24 matching approved rules fails planning visibly so the user can narrow or
disable routes instead of silently truncating them.

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
