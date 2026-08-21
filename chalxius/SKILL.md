---
name: chalxius
description: Operate Chalxius for source-bound mathematical and philosophical research, Paper and Evidence graphs, two-subround Research, verifier-gated Fact admission, computation, architecture repair, Reader export, and explicitly requested academic teaching through Chalxius Learner.
---

# Chalxius 0.8.7 — Main Observation and CHX Snapshot

Chalxius is one research runtime. `fast`, `auto`, and `deep` are execution
profiles; they never change the Fact-admission contract. The historical
`operate-mathgraph-unified` name is schema compatibility only. Cross-version
operation is defined by the MathGraph itself: node and edge identity, content
hashes, dependencies, provenance, workflow stage, and owner boundaries. A
runtime path, installation identity, archive locator, or obsolete receipt is
diagnostic provenance, not a prerequisite for ordinary graph work.

## Forward-upgrade rule

Future releases do not owe runtime or procedural forward compatibility. An
upgrade may replace or remove old adapters, migration ceremonies, runtime
identity checks, and administrative gates when the MathGraph semantic surface
remains operable. The continuity obligation is semantic: an agent must be able
to interpret and operate valid node/edge hashes, dependencies, provenance,
workflow stages, and owner boundaries. Mathematical-safety and Fact-authority
checks stay at their owning boundaries; procedural legality is not a second
truth path.

Worker-ingestion receipts are workflow markers only. They document that a
return passed through ingestion and provide optional replay provenance, but do
not grant a Research capability or mathematical status. A complete hash-bound
Research product with valid assignment provenance can be consumed by later
workflow stages when its derived receipt is absent; missing products,
stage/owner/hash drift, and independent verifier, Certification, Gateway, Fact,
terminal-seal, or final-experiment checks remain blocking at their own owners.

Candidate-level fresh-adverse review is scoped to the explicitly selected
constructive Research heads that themselves carry
`independent_adverse_required=true`. Historical `related_research_ids` may
still establish dependency and provenance, but they do not silently inherit a
remote adverse obligation into a different Candidate. When multiple marked
heads are explicitly selected, only maximal selected heads require separate
fresh reviews; direct Candidate-byte binding, independent actor, disposition,
and verifier exclusion remain exact.

Structured source-evidence capabilities are interpreted by their graph
semantics, not one runtime-era field spelling. Current `artifact_path` and
`artifact_sha256`, compact `path` and `sha256`, and the historical
`card_authorized_path` plus `returned_copy_path` declaration are equivalent
only when every declared concrete path exists inside the project and has the
same declared SHA-256. A locator by itself never grants file capability.

The 0.8.6 repair keeps orchestration explicit. Main names the load-bearing
Research ids, and a planning command creates only immutable assignments and
task cards. Main must still launch each selected worker through the host and
confirm that the worker actually started; a plan or card is not dispatch.
This is an operating instruction, not a new receipt, compatibility layer, or
mathematical gate.

The 0.8.7 repair makes performance observation equally explicit. Main directly
notices the end-to-end elapsed time of commands and work units already visible
through ordinary host interaction. An operation that is unexpectedly slow for
its apparent complexity or compared with a recent comparable operation is a
performance diagnostic signal: inspect it for repeated validation, broad
rescans, or idle work. This is Main's judgment, not a numeric acceptance
threshold or a new monitoring subsystem.

The same repair removes reproduced work rather than monitoring it. One
selective checkpoint shares a command-local inspection across its explicit
targets; an exact supervision retry filters unrelated manifests and returns the
existing round before rebuilding supervisor Research; and an independent
Research append with no Fact dependencies does not open the active-Fact
lineage. Proof-logic, program-math, and integration supervisors receive the
exact production card, selected production outputs, and active Fact premises
without preloading source-only baseline bytes; source-scope supervision alone
projects those exact source capabilities. Historical Research artifacts that
already form exact project-relative path/SHA-256/role capabilities remain
directly operable regardless of their old assurance label. These projections
never persist across commands or mutation
boundaries. Ordinary content-addressed capabilities use their bytes and final
SHA-256 as authority, so harmless mtime/ctime-only localization does not count
as artifact drift while device, inode, type, size, link, containment, and hash
checks remain exact. Current worker examples bind the selected skill root's
executable `scripts/mgraph` shell entry instead of assuming a PATH alias.

Main may author the exact canonical Candidate Fact bytes, including a canonical
Fact file inside a sealed Main-authored Candidate Release. Worker authorship,
container identity, and other provenance metadata remain useful lineage, but
none is a mathematical validity gate. Main calls
`prepare-candidate-adverse-target SELECTED_RESEARCH_ID --candidate-fact PROJECT_RELATIVE_PATH`.
The public command fixes the actor to Main and accepts no `--actor` override.
It consumes those exact canonical Fact bytes and binds every
applicable completed supervision result for the selected Research (possibly
none when no supervision scope applies); it does not infer, rewrite, or
validate the theorem merely from provenance. Fresh adverse work, its
disposition, a fresh verifier, Gateway-owned `certification-record`, and Gateway
Fact admission remain separate mandatory boundaries.

## Start through the smallest applicable contract

Read this complete router first. Then select exactly one startup path:

1. A current task card with `research_cycle.subround="production"` uses
   [references/v5_production_worker_bootstrap.md](references/v5_production_worker_bootstrap.md).
2. A current task card with `research_cycle.subround="supervision"` uses
   [references/v5_supervisor_worker_bootstrap.md](references/v5_supervisor_worker_bootstrap.md).
3. A current whole-Candidate refute card with no `research_cycle` and literal
   `independent_adverse_required=true` uses
   [references/v5_candidate_adverse_worker_bootstrap.md](references/v5_candidate_adverse_worker_bootstrap.md).
4. An explicitly requested, bounded edit of an existing Chalxius Learner
   teaching Markdown uses
   [references/learner_document_edit_bootstrap.md](references/learner_document_edit_bootstrap.md)
   only when every selector condition in that file holds.
5. Every other Main, Operator, legacy, malformed, uncertain, or escalated task
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

## Selective Fact-admission checkpoint

Before expensive Candidate construction, Main explicitly selects the
load-bearing Research targets and may run
`selective-fact-checkpoint --input FILE` over at most sixteen explicitly named
Research targets. The checkpoint fully validates each selected Research record
and its direct readiness requirements, uses structural envelopes only for
unselected graph connectivity, and freezes exact ancestry, downstream reuse,
known blockers, explicit exclusions, and a content-addressed Candidate batch
seed. It performs no automatic ranking or selection.

The default batch partition first closes the explicitly selected dependency
graph. Dependency-connected ready targets remain in one atomic unit, while
independent ready targets remain singleton failure-isolation units. Main may
combine independent units only after reviewing their logical dependency and
failure surfaces. Every resulting Candidate still requires exact canonical
Fact statements or a typed mini-DAG authored or selected by Main, fresh
Candidate adverse review when applicable, verifier coverage, Certification,
and Gateway admission. The checkpoint is nontruth and creates no Candidate,
Decision, admission, or Fact.

For a selected ready Research target and exact project-relative canonical Fact,
Main first runs
`prepare-candidate-adverse-target SELECTED_RESEARCH_ID --candidate-fact PROJECT_RELATIVE_PATH`,
whose actor is fixed to Main, then passes the returned Research id to
`plan-candidate-adverse RESEARCH_ID`.
The canonical bytes may be Main-authored; their author/provenance fields do not
establish mathematical validity. Preparation binds every applicable completed
supervision result, while planning is separate from constructive production and
Research supervision, exact-retry idempotent within one host scope, and creates
only a nontruth refute assignment and card. Main must actually launch and
confirm the adverse worker.
Candidate disposition, fresh verifier review, Gateway-owned Certification, and
Gateway Fact admission remain mandatory.

## CHX and PHX

For runs started after the 0.4.1 activation boundary, start one task-scoped CHX
ledger before substantive project work. Project-bound ledgers live under
`PROJECT/chx-ledgers/`; projectless ledgers use private host task state outside
the skill. Historical runs must not be backfilled.

Record architecture-caused or materially amplified mechanisms, not ordinary
mathematical difficulty. For an ordinary run-local issue, make one bounded
reusable tactical repair first, then coordinate related issues into one
integrated repair. An explicitly requested project-wide historical
revalidation may instead use the cross-ledger global repair path after validating
every ledger and every observed qualified issue against one exact current
candidate; it must not manufacture tactical entries in immutable predecessor
ledgers. Performance issues consult PHX before mechanism selection. Main
directly observes both worker progress and the elapsed duration of commands or
work units through ordinary visible host interaction. Main may reclaim or
redirect a worker that stops producing useful visible progress, and treats an
operation unexpectedly slow for its apparent complexity or a recent comparable
run as a diagnostic signal worth inspecting. This instruction creates no timer,
daemon, watcher, numeric threshold, heartbeat record, persistent performance
state, or lifecycle/admission gate. PHX is advisory and user
adoption remains explicit. A current card-bound worker ledger projects any genuine finding into
the project's small CHX observation inbox when the return is ingested; a pure
mathematical challenge creates no architecture observation. This replaces
reliance on host memory and does not create Blackboard, Pulse, scoring, or truth
authority.

Before a stage-wide repair or any claim that the project's CHX work is closed,
run `chx_ledger.py inventory --project-root PROJECT`. Treat issue identity as
`RUN_ID/CHX-NNN`: numbering is local to one predecessor chain. The read-only
inventory separates active issues, closed orphan issues, resolved successor
chains, and historical report-renderer compatibility drift; it never rewrites
old ledgers or reports. Its default output is bounded; `--full` exposes every
validated ledger and chain only for an explicit forensic need.

For a user-directed full historical settlement, `record-global-repair` binds
the complete qualified issue inventory, exact candidate root, version and
manifest, the revision-3 `covered_issue_snapshot_sha256`, one disposition per
observed issue, disjoint mechanism groups, and reproducible risk/regression
evidence.
Regression evidence must be a digest-bound `project:` receipt; candidate files
are implementation anchors only. `verify-global-repair` and every later
inventory read fail closed after covered-ledger, candidate-manifest, lineage,
or report drift. Exact retries are idempotent. The copy-on-write record lives
under `PROJECT/chx-ledgers/global-repairs/`, has no truth or project authority,
and never edits historical JSONL or architecture reports.
The inventory binds the exact bytes currently visible and may include open
ledgers; an open flag is not proof that a task remains active and is not a
global-repair gate. Independent open or abandoned ledgers remain visible, and
every issue already observed in them must still receive an exact disposition.
Closed parallel successor subtrees remain separate `RUN_ID`-qualified
projections; open parallel subtrees stay represented by their ordinary ledger
and chain snapshot. Malformed predecessor lineage or competing cross-branch
`supersedes` successors still fails closed. Candidate identity means the
complete exact manifest tree.
Anchors and evidence are candidate- or project-relative file references bound
to SHA-256; same-ledger or excluded `supersedes` relations never discharge an
earlier issue. A later valid zero-issue ledger does not stale an existing
repair, and an issue in a newly appended ledger remains uncovered until a
successor global repair covers it. Any later mutation of an open ledger whose
issues were covered naturally stales that exact covered-ledger snapshot; it
does not erase or silently hide the new bytes.

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
3. Main explicitly names the load-bearing Research IDs. Production subround 1
   plans constructive proof, literature, insight, interpretation, or
   computation-design assignments and never plans refute. Explicit Research
   IDs use the exact-ID path and do not rebuild the unrelated global frontier.
   Planning and card creation are not dispatch: Main must launch each worker
   through the host and confirm the actual start.
4. Logical components, not wall-clock barriers, determine supervision. A
   completed component may enter subround 2 while unrelated production
   continues. Use at most three failure-informed supervisors: `proof_logic`,
   `source_scope`, `program_math`, and `integration` only for a genuine
   cross-primary interface.
5. Completing one Research subround is not completing the host task. At that
   boundary validate the exact card, hash-bound Research product, supervision
   state, and affected local projection; treat a worker-ingestion receipt as
   optional provenance rather than a startup capability gate; do not automatically run a whole-
   project audit. Reserve the full audit for an explicit user request,
   Candidate/Fact or final-delivery boundary, shared-runtime change, detected
   drift, or a user-configured cumulative cadence. No fixed round-count
   threshold is implicit.
6. A supervisor challenge opens a later copy-on-write repair round. The repair
   Research stores its original worker mode, so abort/replan under `auto` cannot
   turn compute or literature repair into prove.
7. New V5 Pulse planning is retired. The production/supervision cycle is the only prospective Research collaboration path.
   Existing historical Pulse records retain status, audit, dispatch, close, void, and abort compatibility.
8. Before Candidate packaging, require complete applicable supervision and the
   fresh Candidate-level adverse gate. Recheck live supervisor results under
   the seal lock, then package once. Iterative repair belongs before expensive
   packaging.
9. Generic production planning omits only source Research obligations closed by
   an exact valid, non-aborted production Research product. It retains the worker result,
   history views, and explicit-ID planning. Main `memory-add` reuses identical
   unbound semantics across actor labels only when the current CLI role is Main;
   actor text never grants that authority.

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
The verifier returns review bytes but does not publish Certification.
`certification-record` is Gateway-owned and records one immutable decision;
Gateway separately revalidates and admits accepted Facts. Never weaken a
missing gate because a mode is fast or a result is plausible.

`validate-return` is one bounded read-only snapshot of the canonical return and
its declared artifacts. A transient `ENOENT` or `ESTALE` visibility failure
before that safe snapshot exists may be retried after the same paths stabilize,
without quarantine. An unsafe filesystem object or visible malformed,
hash-drifted, schema-invalid, or semantically invalid bytes remain fail-closed
and retain the ordinary local-quarantine path. Snapshot retry is not a worker
receipt or admission shortcut.

One Candidate command may reuse one ephemeral fully validated inspection
context across its immutable Research, adverse, and historical-runtime
projections. The context never persists across commands or mutation boundaries;
Candidate sealing recomputes live supervision under the final lock. Automatic
selection may form dependency-closed authoring batches, but it never atomizes
claims. Each later Fact must expose exactly one semantic conclusion, and any
multi-Fact batch requires explicit Candidate-DAG closure. A Main-approved batch
merge still requires the exact dependency and failure-surface checks recorded by
the selective checkpoint. New `candidate_fact` worker outputs are canonical-Fact
validated before ingestion; an exact repair specification, when supplied, is
hash-bound into both repair Research and its task card.

Candidate preflight rejects assurance cardinality, internal-edge, and exact
statement-interface mismatches from the submitted Candidate bytes before global
Research replay. This early projection is nonauthoritative: the complete
assurance validator still reruns after Research, source, artifact, predecessor,
and adverse closure. Manual or historical Research does not inventory
supervision rounds unless a selected constructive record actually carries
production-assignment provenance.

Active-Fact reconstruction uses one two-phase command-local projection. A
reentrant task-card check may read only locally hash-validated Release,
admission-marker, and admitted-Fact bytes; the outer frame then performs the
complete Research, runtime, Decision, successor, and lineage replay and rejects
any provisional/final drift. Approved-computation replay propagates the same
inspection context through its design, supervision, receipt, disposition, and
task-card closure. This is a recursion boundary, not an admission shortcut or a
persistent authority cache.

Workers report at most three deduplicated, well-supported concrete failure
families and their success boundaries. They do not author persistent attack
rules. Main may reject a report or synthesize one compact mechanism-level rule
for future work. Current rules use English internal prose, accept at most
sixteen active project rules, and fail closed on an oversized rule until Main
provides semantic compression; they are never truncated. This routing plane has
no truth or admission effect.

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

Runtime identity and archive records may explain where a card or release was
created, but they do not authorize or deny ordinary graph operations. Agents
continue a legacy graph directly when its content hashes, dependencies,
provenance, and workflow owner checks are valid; no adapter, migration copy, or
mode-init ceremony is needed merely to read or append graph work. Release and
rollback tools remain deployment diagnostics and must not become a second truth
path or a graph-operation gate.

Architecture releases use failure-informed validation: changed files, affected
boundaries, manifest/inventory, focused regression, self-test, and only the
broader suite justified by shared-runtime risk. Install the validated candidate
locally before publication. The default host-global path is
`scripts/local_install.py`: it validates one complete candidate tree, runs the
self-test and the two changed-surface regressions, archives the prior runtime,
atomically swaps `/Users/<user>/.codex/skills/chalxius`, and keeps one direct
rollback copy outside skill discovery. It never reads or mutates a project and
does not require a project audit, release matrix, or worker receipt. The older
`scripts/runtime_cutover.py` remains an explicit forensic/protected-project
deployment tool. For this release workflow, an explicit publication request includes merging the corresponding reviewed change into `main` by default; the user may explicitly exclude merge. Installation and publication remain separate authorizations, and publication never authorizes an unreviewed or unrelated change.
