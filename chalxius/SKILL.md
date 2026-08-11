---
name: chalxius
description: Operate Chalxius for source-bound mathematical and philosophical research, Paper and Evidence graphs, two-subround Research, verifier-gated Fact admission, computation, architecture repair, Reader export, and explicitly requested academic teaching through Chalxius Learner.
---

# Chalxius 0.7.3 — Selective Startup

Chalxius is one research runtime. `fast`, `auto`, and `deep` are execution
profiles; they never change the Fact-admission contract. The historical
`operate-mathgraph-unified` name is schema compatibility only.

## Start through the smallest applicable contract

Read this complete router first. Then select exactly one startup path:

1. A current task card with `research_cycle.subround="production"` uses
   [references/v5_production_worker_bootstrap.md](references/v5_production_worker_bootstrap.md).
2. A current task card with `research_cycle.subround="supervision"` uses
   [references/v5_supervisor_worker_bootstrap.md](references/v5_supervisor_worker_bootstrap.md).
3. An explicitly requested, bounded edit of an existing Chalxius Learner
   teaching Markdown uses
   [references/learner_document_edit_bootstrap.md](references/learner_document_edit_bootstrap.md)
   only when every selector condition in that file holds.
4. Every other Main, Operator, legacy, malformed, uncertain, or escalated task
   uses the ordinary path: read
   [references/unified_architecture.md](references/unified_architecture.md),
   [references/reasoning_modes.md](references/reasoning_modes.md),
   [references/admission_contract.md](references/admission_contract.md), and
   [references/chx_runtime_ledger.md](references/chx_runtime_ledger.md), then
   only the directly applicable references below.

Compact paths are complete contracts, not summaries. They load a broader
protocol only at an explicit fail-closed branch. Never preload release,
admission, Paper, Blackboard, Learner, PHX, or attack protocols merely because
they exist.

### Direct reference router

- Round creation, legacy worker execution, return validation, or ingestion:
  [references/agent_protocol_v4.md](references/agent_protocol_v4.md).
- Paper reconstruction, inherited drafts, Paper Logic/Audit, Evidence, or
  continuation:
  [references/paper_logic_graph_v1.md](references/paper_logic_graph_v1.md),
  [references/paper_input_contracts.md](references/paper_input_contracts.md),
  [references/evidence_plane.md](references/evidence_plane.md), and
  [references/paper_research_pipeline.md](references/paper_research_pipeline.md).
- External theorems and sources:
  [references/external_theorem_applicability.md](references/external_theorem_applicability.md)
  and [references/external_source_reliability.md](references/external_source_reliability.md).
- Computation or replay:
  [references/computational_verification_v4.md](references/computational_verification_v4.md).
- Candidate/adverse routing:
  [references/adverse_routing_evolution.md](references/adverse_routing_evolution.md).
- Campaigns, historical migration, and optional advisory planning:
  [references/campaigns_and_migration_v4.md](references/campaigns_and_migration_v4.md)
  and [references/brave_future_l3_l4.md](references/brave_future_l3_l4.md).
- Blackboard or historical Pulse compatibility:
  [references/blackboard_graph_v4.md](references/blackboard_graph_v4.md).
- Explicit academic teaching/testing:
  [references/unified_learning_plane.md](references/unified_learning_plane.md)
  and [references/fact-graph-grilling.md](references/fact-graph-grilling.md).
- Reader export: [references/reader_html_export.md](references/reader_html_export.md).
- Architecture, release, installation, or performance repair:
  [references/capability_difference_audit.md](references/capability_difference_audit.md),
  [references/v5_release_traceability.md](references/v5_release_traceability.md),
  [references/phx_architecture_routes.md](references/phx_architecture_routes.md),
  and [references/administrative_cost_playbook.md](references/administrative_cost_playbook.md).

## Immutable authority boundary

The only truth path is:

`Research -> Candidate Release -> Certification Decision -> Fact`

Research, Evidence, Paper/Audit, Blackboard, Reader, Learner, CHX, PHX, and
attack proposals are nontruth. They never become premises by credibility,
repetition, ingestion, lint, audit, or presentation. V5 Facts are the only
premise store.

Every worker task card retains three communication planes: compact control, one
frozen mathematical-state view, and bounded narrative. The card is the
immutable capability boundary. Current task-referenced authority overrides
conflicting background prose. Historical artifacts remain readable and are
repaired copy-on-write, never rewritten.

## CHX and PHX

For runs started after the 0.4.1 activation boundary, start one task-scoped CHX
ledger before substantive project work. Project-bound ledgers live under
`PROJECT/chx-ledgers/`; projectless ledgers use private host task state outside
the skill. Historical runs must not be backfilled.

Record architecture-caused or materially amplified mechanisms, not ordinary
mathematical difficulty. Make one bounded reusable tactical repair first, then
coordinate related issues into one integrated repair. Performance issues consult
PHX before mechanism selection. PHX is advisory and user adoption remains
explicit. A current card-bound worker ledger projects any genuine finding into
the project's small CHX observation inbox when the return is ingested; a pure
mathematical challenge creates no architecture observation. This replaces
reliance on host memory and does not create Blackboard, Pulse, scoring, or truth
authority.

If `report_required=false`, do not surface CHX bookkeeping to the user. CHX is
never an audit warning, certification blocker, or reason to redo otherwise
valid work.

## Modes and project setup

Default to `auto` unless the user explicitly selects fast or deep. Modes affect
future exploration only. Missing source, replay, convention, quantifier,
atomic-DAG, adverse-disposition, or fresh-verifier evidence remains an explicit
Candidate or Certification blocker in every mode.

Initialize a writable project outside the skill tree:

```bash
SKILL_ROOT=/absolute/path/to/chalxius
MGRAPH="$SKILL_ROOT/scripts/mgraph"
PROJECT=/absolute/path/to/project
python3 -B "$SKILL_ROOT/scripts/self_test.py"
"$MGRAPH" --root "$PROJECT" --role operator init \
  --project-id PROBLEM_ID --title "TITLE" --reasoning-mode auto
"$MGRAPH" --root "$PROJECT" --role main audit
```

Mode switches append future-facing events. Abort an unfinished work unit only
through `work-unit-abort`; completed rounds remain historical. Read APIs never
repair caches implicitly.

## V5 Research cycle

1. Add cumulative Research with exact dependencies, sources, and artifact
   path/SHA/role capabilities. Finished external work enters Evidence, not Fact.
2. For a research draft, freeze the artifact, reconstruct the complete
   load-bearing target DAG, preserve its domain and quantifiers, and expose any
   weaker theorem as a typed gap rather than a solution to the original target.
3. Production subround 1 dispatches constructive proof, literature, insight,
   interpretation, or computation-design workers. It never dispatches refute.
   Explicit Research IDs use the exact-ID planning path and do not rebuild the
   unrelated global frontier.
4. Logical components, not wall-clock barriers, determine supervision. A
   completed component may enter subround 2 while unrelated production
   continues. Use at most three failure-informed supervisors: `proof_logic`,
   `source_scope`, `program_math`, and `integration` only for a genuine
   cross-primary interface.
5. A supervisor challenge opens a later copy-on-write repair round. The repair
   Research stores its original worker mode, so abort/replan under `auto` cannot
   turn compute or literature repair into prove.
6. New V5 Pulse planning is retired. The production/supervision cycle is the only prospective Research collaboration path.
   Existing historical Pulse records retain status, audit, dispatch, close, void, and abort compatibility.
7. Before Candidate packaging, require complete applicable supervision and the
   fresh Candidate-level adverse gate. Recheck live supervisor results under
   the seal lock, then package once. Iterative repair belongs before expensive
   packaging.

Admitted Fact dependencies are frozen premises, not default counterexample
targets. Exact contradiction evidence is routed separately for governed
reopening.

## Computation

Prospective computation is code-before-execution. Subround 1 returns exactly
`computation_source`, `computation_design`, and `computation_dependencies`.
Program-math supervision reviews those bytes before execution. A missing or
blocking disposition is checked before expensive artifact reconstruction, and
the exact authority is checked again under the final write lock.

For one bounded run, the default hard surface is one production validation path
plus the smallest independent mathematical check. Additional controls are
diagnostics unless a recorded failure family selects them. Every load-bearing
stage still binds formula, code anchor, domains, representation, truncation,
output interpretation, and replay. Multi-stage or resumable jobs use the
experiment layer; a one-stage exact script need not.

Before allocating code, name the open target node or explicit architecture
smoke-test purpose. A computation that merely reproduces an already available
derivation is advisory-eliminated, not sent through another gate stack.

## Sources

Load-bearing theorem/formula use requires exact source bytes, locator,
hypotheses, conventions, and applicability. Current erratum/retraction status is
optional metadata in ordinary Research: retain a negative status claim only
with an exact frozen response receipt. Otherwise mark it `not_assessed` or
`unresolved`; this alone does not trigger a repair cycle. Candidate and Fact
work may demand stricter current-status evidence when it is load-bearing.

## Candidate, verifier, and Fact

Candidate preflight binds exact statements, proofs, active predecessor closure,
sources, computation evidence, internal mini-DAGs, supervision, adverse work,
and dispositions. Send only the frozen verifier capsule to a fresh verifier.
Certification records one immutable decision; Gateway alone admits accepted
Facts. Never weaken a missing gate because a mode is fast or a result is
plausible.

Adverse reports present at most three deduplicated, well-supported attack types
in ordinary language. Technical details remain in the full report. Nothing is
activated until the user explicitly approves a proposal.

## Paper, Evidence, and Reader

Paper mirrors and Audit Graphs preserve exact source identity and immutable
correction lineage. Evidence import transfers source availability, never Fact
authority. Project background is optional nontruth context and must return to
exact sources for load-bearing use.

Generate Reader HTML only on explicit request. It is a deterministic,
presentation-only projection with visible native status; it writes nothing back
and has no truth effect.

## Chalxius Learner

Activate Chalxius Learner only when the user explicitly asks to be taught,
questioned, tested, guided through a paper, trained for an exam, or tracked for
mastery/review. Ordinary research, audit, or system testing does not activate
it. Frozen Fact, Paper/Audit, or Blackboard snapshots may be mounted read-only;
persistent learning evidence needs separate authorization and remains nontruth.

An already active read-only oral follow-up uses the bounded oral fast path in
[references/unified_learning_plane.md](references/unified_learning_plane.md).
An existing teaching Markdown edit may use the bounded document-edit bootstrap
only under its complete selector. Source conflict, fresh verification,
Research, truth-state mutation, persistent learning mutation, architecture,
publication, or nonlocal editing immediately restores the ordinary path.

The separate `$grill-me` companion is Grill Me Code and is code-only. It has no
Paper, Fact, Audit, Blackboard, or Learning Graph authority.

## Runtime, release, and installation

Active cards bind the complete current manifest and runtime identity. Historical
terminal cards may resolve only through the immutable external runtime archive.
Install or roll back only through the protected runtime cutover with the
required project inventory and validation receipt. Do not mutate the installed
runtime in place.

Architecture releases use failure-informed validation: changed files, affected
boundaries, manifest/inventory, focused regression, self-test, and only the
broader suite justified by shared-runtime risk. Install the validated candidate
locally before publication. Publication does not imply merging a pull request;
merge requires explicit user authorization.
