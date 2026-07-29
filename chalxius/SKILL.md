---
name: chalxius
description: Operate Chalxius, the integrated system for mathematical, philosophical, paper-led, computational, and academic teaching work. Use it to choose or switch fast, auto, and deep reasoning profiles; build source-bound Paper Logic and Audit Graphs; run cumulative Research and replayable verification; govern adverse-worker attack reports and user-approved route evolution; certify V5 Facts through one invariant gate; use a user-generated project background or export an offline knowledge map; or, when academic teaching or testing is explicitly requested, activate Chalxius Learner over frozen Fact, Paper, and Blackboard snapshots.
---

# Chalxius 0.4.4 — Back to the Future

Use the bundled Chalxius research engine as the only research runtime. Fast,
auto, and deep are execution profiles of that one engine. The Fact Graph
admission contract is identical in every profile.

`chalxius` is the public skill name. The earlier
`operate-mathgraph-unified` label survives only as an archived candidate name
and a compatibility protocol identifier in already-defined artifact schemas;
it is not a second runtime or user-facing route.

## Read the governing references

Before substantive work or any project write, read [references/unified_architecture.md](references/unified_architecture.md), [references/reasoning_modes.md](references/reasoning_modes.md), [references/admission_contract.md](references/admission_contract.md), and the mandatory nontruth runtime [references/chx_runtime_ledger.md](references/chx_runtime_ledger.md).

Read the directly applicable Chalxius reference before acting:

- Paper reconstruction, audit, correction, mirroring, or paper-led planning: [references/paper_logic_graph_v1.md](references/paper_logic_graph_v1.md).
- V5 Research, lifecycle, retained capabilities, or release work: [references/v5_capability_matrix.md](references/v5_capability_matrix.md).
- Historical V4 memory, routing, or adoption behavior: [references/adoption_policy_v4.md](references/adoption_policy_v4.md).
- Round creation, worker execution, return validation, or ingestion: [references/agent_protocol_v4.md](references/agent_protocol_v4.md).
- Adverse-worker counterexample learning, attack reports, or route decisions: [references/adverse_routing_evolution.md](references/adverse_routing_evolution.md).
- Blackboard graph types, query, snapshots, merge, or pulses: [references/blackboard_graph_v4.md](references/blackboard_graph_v4.md).
- Computation, checkpoints, artifact replay, or numerical evidence: [references/computational_verification_v4.md](references/computational_verification_v4.md).
- Campaigns, targets, historical projects, and migration: [references/campaigns_and_migration_v4.md](references/campaigns_and_migration_v4.md).
- External theorems or sources: [references/external_theorem_applicability.md](references/external_theorem_applicability.md) and [references/external_source_reliability.md](references/external_source_reliability.md).
- Explicitly requested academic teaching or testing over graph snapshots: [references/unified_learning_plane.md](references/unified_learning_plane.md) and [references/fact-graph-grilling.md](references/fact-graph-grilling.md).
- Explicitly requested human-readable single-file graph visualization: [references/reader_html_export.md](references/reader_html_export.md).
- Engine or release changes: [references/capability_difference_audit.md](references/capability_difference_audit.md), [references/v5_capability_matrix.md](references/v5_capability_matrix.md), and [references/v5_release_traceability.md](references/v5_release_traceability.md).

## Preserve authority and communication boundaries

The V5 truth path is exactly `Research -> Candidate Release -> Certification
Decision -> Fact`. Research is cumulative nontruth; Certification records
evidence; the V5 Fact Graph is the only premise store. Paper/Audit and
Blackboard remain separate nontruth/source subsystems, and the Reader is only a
derived presentation.

Every worker task card retains three communication planes: compact control, one frozen
mathematical-state view, and bounded narrative. The card is the immutable capability boundary. A
new current-contract card also binds the complete source Research dossier and a task-referenced V5
authority snapshot. Its current status overrides conflicting nontruth project-background prose;
never replace the card with prompt prose or infer filesystem capabilities.

A full-fidelity Paper mirror on the Blackboard remains an exploration
projection with an exact receipt. If an Audit Graph is wrong, append a
challenge, disposition, replacement object, and new snapshot; never rewrite
historical audit bytes.

For every Chalxius run started after the 0.4.1 activation boundary, start one
task-scoped CHX runtime ledger before substantive analysis or tool execution.
Project-bound runs store their ledger at `PROJECT/chx-ledgers/`. Projectless
runs use private host task state outside the skill. The directory is an
operational container only: `truth_effect=none` and `project_effect=none` mean
that its bytes never enter project audit, Research, Certification, or Fact
admission. Record only problems that the Chalxius architecture caused or
materially amplified, with an exact causal mechanism and audit anchors. Runs
already underway under 0.4.0 must not be backfilled, reclassified, or reopened,
and their missing ledger is never an audit warning, certification blocker, or
reason to redo work. Mixed 0.4.0 and 0.4.1-or-later bytes do not alter an older run's
original status.

## Choose a reasoning mode

Use one of the following project-level profiles:

- `fast`: low-orchestration Chalxius research. High-cost exploration is opt-in. All hashes, snapshots, source checks, verifier separation, review binding, audit, and admission gates remain active.
- `auto`: deterministic workload routing. Paper, explicit source ambiguity, computation, multi-candidate, novelty, and external-output signals activate only the applicable expensive features. `source_ambiguity=true` requires `source_claim=true`; its absence is legacy-compatible `false` and never weakens the independent source-claim admission gate.
- `deep`: every applicable expensive research feature is required. A genuinely irrelevant feature is recorded `not_applicable`; it is never faked merely to fill a checklist.

If the user does not choose, use `auto`. Project `reasoning_mode` is separate
from assignment `plan-round --mode auto|prove|refute|...`.

Modes allocate future exploration only. They do not create a universal
checklist or a closure gate. In V5, `profile-closure-status` emits repair advice
and `profile-closure-record` appends that advice to Research; neither has
admission authority. Missing source, replay, convention, quantifier,
atomic-DAG, adverse-disposition, or fresh-verifier evidence remains an explicit
Candidate Release or Certification blocker in every mode.

## Initialize a new V5 project

Set explicit, nonnested paths. The writable project must not be inside this skill directory.

```bash
SKILL_ROOT=/absolute/path/to/chalxius
MGRAPH="$SKILL_ROOT/scripts/mgraph"
PROJECT=/absolute/path/to/research-project

python3 -B "$SKILL_ROOT/scripts/self_test.py"
"$MGRAPH" --root "$PROJECT" --role operator init \
  --project-id PROBLEM_ID --title "TITLE" --reasoning-mode auto
"$MGRAPH" --root "$PROJECT" --role main mode-status
"$MGRAPH" --root "$PROJECT" --role main audit
```

`init` defaults to workflow-evidence V5. A V5 root starts with an empty Fact
Graph and does not inherit V4 or Danus authority. Keep every historical root
unchanged and readable; do not perform an in-place V4-to-V5 migration.

Read-like APIs never repair caches implicitly. Statement-interface
materialization, Blackboard `reindex(apply=True)`, and all other writes remain
explicit and guarded.

## Switch modes without rewriting history

```bash
"$MGRAPH" --root "$PROJECT" --role main mode-switch \
  --to deep --actor main --reason "Paper ambiguity requires full audit."
```

Every switch appends a content-addressed event. It applies to future work units
only. A frozen V5 round retains its original mode event, assurance contract,
and admission-contract hash until completion. Historical V4 cards retain their
original execution profiles without backfill. To discontinue a work unit
explicitly:

```bash
"$MGRAPH" --root "$PROJECT" --role main work-unit-abort ROUND_ID \
  --actor main --reason "Superseded by a newly planned deep round."
```

The abort blocks future managed returns, experiment writes, and new Pulse
commitments or dispatch for that round. It preserves existing Research,
receipts, and read-only audit. `round-status` projects unfinished assignments as
`frozen_aborted` with no live awaiting count, and audit checks that projection
against the exact abort id. Use whole-pulse abort only to stop future Pulse
dispatch while retaining accumulated contributions.

## Run research work

1. Add or select cumulative Research. Challenges, counterexamples, obstacles, insights, repairs, and dispositions remain separate immutable entries. Source-dependent work uses `memory-add --current-assurance` with exact project-relative path/hash/role artifacts; path-only prose cannot be planned.
2. For paper-led work, freeze exact Paper Logic and Audit snapshots with their
   independent reviews.
3. Plan a round. The card binds the candidate skill root/version, mode, Blackboard snapshot, complete source Research record, predecessor interfaces, related Research, task-referenced authority, and all three planes. An explicitly named target receives only exact Release/Decision/admission/Fact/artifact capabilities. Main compiles context; Operator governs; the dedicated Host role remains dispatch-only. Bind the task/thread through `host_task_scope_id` when available; worker CHX startup passes the exact task card and fails on runtime drift.
4. Execute only from the frozen card. Preflight a repairable draft, then ingest
   only the exact worker-final hash. A malformed peer is quarantined locally.
5. For collaborative work, use optional two-wave Pulse. Each valid Wave-1 and
   Wave-2 contribution enters Research independently; Pulse closure is advice,
   not certification.
6. Use experiments, novelty, campaigns, claims/conventions, and Blackboard
   promotion only when useful to the bounded task. They do not form a universal
   closure checklist.
7. Seal one explicit Candidate Release. It automatically includes linked
   adverse Research and requires dispositions for every bound attack.
8. Send only the frozen verifier capsule to a fresh verifier, record one
   immutable decision, then let the gateway admit an accepted release.

The automatic V5 frontier uses the compact four-factor ordering: impact,
information value, feasibility, and burden/economy. Historical eight-metric
Research is projected at read time without rewriting. This score orders active
work only: it has no cutoff, no truth effect, and never makes a low-scored
Research id ineligible for explicit scheduling. Frozen task cards never change
when the frontier is rescored.

For new 0.4.4 cards, one promoted Blackboard Research item may seed its exact
bounded query and lineage. Exact enum mode suggestions apply only when their
cross-component assurance/adverse signature equals the kind-derived default;
an explicit user `--mode` wins. Neither mechanism changes Fact admission.

The source-dossier/authority contract is prospective. A frozen card without `task_context_revision` remains
valid without backfill or repeated work. Do not refresh `PROJECT_BACKGROUND.md`; plan a new future card.

If adverse routing was explicitly enabled for the project, an ingested
`counterexample` also creates one immutable nontruth attack case and one route
proposal. The worker may abstract a proposed rule but cannot activate it.
Only the user, through the `operator` role, may approve, modify-and-approve,
reject, or later disable the rule. Every decision affects future task cards
only; frozen cards and old returns remain unchanged.

When an enabled V5 Research return contains one or more actual computation
stages with exact source and output artifacts, successful ingestion also queues
one typed future `refute` Research review of the formula-domain-
representation-approximation-output chain. That review receives the scoped
program-math baseline attack in addition to the ordinary eight rules. Mere
prose about code, an ordinary challenge, or a task with no executable stage
must not activate this route. The queued review is nontruth, does not interrupt
the producer, and never imports a CHX issue into attack routing.

```bash
"$MGRAPH" --root "$PROJECT" --role main profile-closure-status ROUND_ID
"$MGRAPH" --root "$PROJECT" --role main profile-closure-record ROUND_ID \
  --input PROFILE_CLOSURE.json --actor main
```

`profile-closure-status` may still be used for local repair suggestions, but a
recorded suggestion never marks the work complete. Paper evidence may reuse an
earlier reviewed snapshot only while it remains current and nonsuperseded.

Enable and inspect this project-local extension only on explicit request:

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-enable \
  --actor USER --reason "Enable user-governed adverse routing evolution."
"$MGRAPH" --root "$PROJECT" --role main attack-route-status
```

A host-wide explicit user authorization may be consumed prospectively at the
start of each future V5 work unit by issuing the same operator enable command
for its exact project. Global installation alone never activates or writes a
project. Do not consume that authorization in the middle of an already-frozen
unit, on a V1-V4 root, or as a reason to backfill, reclassify, invalidate, or
redo earlier work.

At task completion, if enabled, run `attack-report --host-task-scope-id ID`
and report it separately from CHX even when it contains zero attacks. Present
every pending proposal and let the user choose `approve`, `approve_modified`,
or `reject`; never infer approval from silence or from a successful return.
Attack reporting and route approval have no Fact authority.

For every actual V5 computation stage, bind the displayed formula to one exact
code anchor, mathematical and iteration domains, object representations and
multiplicity, approximation or truncation budget, output interpretation, and
independent checks. A truncated computation must derive the required order and
show `implemented_order >= required_order`; matching two depths alone is not a
proof. A load-bearing stage needs at least two distinct checks, including an
independent implementation, symbolic oracle, or metamorphic relation.

Prepare a neutral frozen verifier capability with
`scripts/prepare_verifier_capsule.py`. It accepts one V5 release id, capsule id,
or exact capsule JSON, copies only authorized bytes outside both the project
field-level preflight validator. The verifier writes and preflights only the
review; the gateway remains the sole recorder/admitter.

## Admit V5 facts through one contract

No mode directly writes truth. Only Facts exposed by exact V5 admission markers
are premises. Every release must pass the same contract hash and gates:

- content-addressed statement, proof, direct predecessors, source evidence, and candidate bytes;
- active statement-only predecessor closure;
- exact source and applicability fidelity, including notation, hypotheses, witnesses, conventions, formula glyphs, quantifiers, and transports;
- independent replay for load-bearing computation;
- an atomic internal mini-DAG bundle when candidate facts depend on one another;
- automatic binding and explicit disposition of linked adverse Research;
- a different fresh verifier using the frozen capsule capability;
- exact Certification Decision, gateway acceptance, admission, and stored Fact;
- cascade revocation and a clean current audit.

Fact communication uses claim cards and expert lint receipts. Exploration communication uses interpretation cards and `interpret-lint-receipts`; neither is admission. If any gate is missing, report candidate status and the exact blocker instead of downgrading the gate because the project is in fast mode.

## Generate historical project background only on explicit request

V5 does not accept V4 or Danus Facts as authority. Preserve historical roots unchanged and readable. Before reducing a prior V5 project to prose, Operator may explicitly run `fact-graph-inventory --source-root OLD`; `fact-graph-append-target --source-root OLD --expected-project-id ID` selects that exact old project for future commands without importing Facts, federation, or current-project writes. When the user explicitly asks to generate or refresh a project background, read the relevant project files broadly and write exactly one `PROJECT_BACKGROUND.md` summary. Do not generate, refresh, or incrementally update it from mere file presence.

Once the summary exists, V5 Reader keeps its historical projection, while a
new task card freezes a complete exact-byte index plus a round-local source
snapshot instead of consuming the full body in active context:

```bash
"$MGRAPH" --root "$PROJECT" --role main project-background-index
"$MGRAPH" --root "$PROJECT" --role main plan-round --workers 1 \
  --memory-id RESEARCH_ID --background-chunk-id BGC_ID
```

If the file is absent, Chalxius proceeds without background and does not create
one. Main/Operator may inspect current chunks; a worker must supply its frozen
task card and reread the index/chunks after compaction. Treat the summary as
nontruth context and return to exact cited sources for load-bearing use.
Retired predecessor packages remain rollback lineage only.

## Activate Chalxius Learner only on demand

`Chalxius Learner` is the canonical name of the internal nontruth academic
learning surface (historically described as the internal Grill learner). It owns
the academic functions formerly exposed by Grill Me: one-question mathematical
and philosophical teaching/testing,
paper-reading modes, qualifying-exam drilling, graph-aware coverage and mastery,
and the lightweight graph algorithm. It does not invoke a Grill Me runtime. It
may mount exact frozen Fact Graphs, `pls-*` Paper snapshots, and `bbs-*`
Blackboard snapshots. Mounting preserves authority labels and hashes but
inherits no truth beyond an already admitted Fact artifact.

Start Chalxius Learner only when the user explicitly asks to be taught,
questioned, grilled, tested, quizzed, guided through a paper, trained for an
exam, or tracked for mastery or spaced review. Do not start it merely because
Chalxius is active, a Paper/Fact/Blackboard graph exists, the user asks for
research or audit, or the user tests Chalxius itself. Mount a graph only when it
materially helps the requested learning task. Persistent learning-graph writes
require separate user authorization; otherwise keep only in-session learning
state.

Reasoning profile and interaction surface are orthogonal. `deep` never starts
Chalxius Learner merely because it enables costly research features; activating
Learner never switches `fast`, `auto`, or `deep`, never starts a research round,
and never changes the Fact admission contract. A suspected source defect remains
a nontruth concern until the user asks for a separate research work unit.

The standalone `$grill-me` companion, called `Grill Me Code`, is deliberately
code-only. It is globally available to the router, including from explicit
natural-language intent without a literal skill token, but semantic activation
still requires a user request for Socratic programming assistance, a
programming challenge, or code-oriented grilling for requirements,
implementation decisions, debugging, testing, or rollout.
Ordinary coding work does not activate it. It has no research or
academic-learning graph access.

Use `scripts/learn` or `scripts/learning_graph.py` only when the user separately
requests persistent learning evidence:

```bash
"$SKILL_ROOT/scripts/learn" init \
  --source-root "$PROJECT" --output /absolute/path/to/learning-graph.json
"$SKILL_ROOT/scripts/learn" mount-paper \
  --source-root "$PROJECT" --snapshot-id pls-FULL_64_HEX \
  --graph /absolute/path/to/learning-graph.json --current-audit-only
"$SKILL_ROOT/scripts/learn" mount-blackboard \
  --source-root "$PROJECT" --snapshot-id bbs-FULL_64_HEX \
  --graph /absolute/path/to/learning-graph.json
"$SKILL_ROOT/scripts/learn" verify \
  --graph /absolute/path/to/learning-graph.json
```

Teaching nodes, mastery scores, objections, and source concerns do not enter
Chalxius research audit and can never be submitted as facts. A blocking source
concern pauses teaching from that anchor but does not mutate its source.
Escalate a suspected mathematical or philosophical defect into a separate
research work unit if the user wants it audited.

## Export a reader HTML only on request

When the user explicitly asks for the single-file knowledge-map view, complete
Reader Finalize as the strengthened validation stage of the existing export
gate, not as a second command, graph, or store. Prepare a strict reader packet
in the requested source language from read-only frozen sources, preserving
native plane/status, exact mathematical text, source hashes, and explicit
theme, target, and prerequisite order. Every included node, including material
hidden by default layer switches, must have nonempty `summary`, `intuition`,
`importance`, and `reasoning` fields before export. The renderer provides one
switchable Chinese/English interface, defaulting to Chinese; controls,
navigation, role labels, and provenance labels change together. Packet titles
and body text are never machine-translated. Presentation-only explanations remain
`reader_note` or Learning material with no truth effect. Then run:

```bash
"$MGRAPH" --root "$PROJECT" --role main export-reader-html \
  --packet /absolute/path/to/reader-packet.json
```

For a V5 project with at least one admitted Fact, use `--v5-projection` instead
of `--packet` to project current Fact, Research, Certification, Paper/Audit,
Blackboard, and default-if-present project-background views into packet v1.
The adapter gives each node a bounded content-free title (object kind plus the
first six object-hash digits); full claims and TeX stay in readable/formal
fields. Non-Fact planes remain visibly nontruth, and oversized projections fail.

Successful Reader Finalize deterministically binds the frozen source snapshot,
canonical packet SHA-256, node count, and complete-sidebar count into
`reader_finalize` metadata. The same metadata is embedded in the page build
metadata and returned in command stdout with
`scope="presentation_readiness_only"` and `truth_effect="none"`; it creates no
receipt file or new authority object.

The deterministic renderer overwrites only `PROJECT/visualizations/knowledge-map.html`.
It embeds all graph, interaction, and math-rendering code, makes no network or
model call, and writes nothing back. Reload uses same-document navigation and
resets runtime UI state; it is not a watcher, poller, fetch loop, or hot reload.
Every eligible node and edge remains on one canvas; minimization changes only
visual size, never topology or eligibility. The initial `All targets`
size action leaves eligible targets full-size and minimizes eligible non-target
cards. `All cards` maximizes every eligible real card. These are reversible
sizing actions, not navigation modes, and they preserve selection, viewport,
graph ordering, and direct card dragging. Every changed card first receives the
derived model-position compensation needed to keep its size-control pivot fixed
on both rendered axes. After the new silhouette is applied, the renderer runs
exactly fourteen deterministic spacing passes. A direct card, directional path,
complete path, or topic-path anchor remains fixed; global actions use every
changed card as a seed without inventing a special view. Undo and redo run the
same convergence. The seed plus at most two graph hops and one collision halo
form the only movable neighborhood; everything outside is a fixed boundary.
Nearby silhouettes repel, visible relation neighbors attract, and radial plus
tangential springs retain the canonical ring and angular order. Drag release
uses the same bounded settlement while the selected cards remain anchors.
Automatic force movement never creates a manual pin; pan and zoom are preserved
and fitting remains explicit.
Synthetic multi-target theme nodes stay
readable while their targets are eligible but are excluded from card sizing and
sizing history.
Canonical placement uses deterministic compact-radial core layers: synthetic multi-
target themes occupy the innermost core, target cards occupy the next central
ring, and remaining cards move outward by undirected graph distance from the
target set. Packet order seeds every ring; eight fixed circular neighbor sweeps
followed by at most 48 adjacent ring-swap candidates may reorder cards only
when the exact scored crossing tuple improves. Exact chord-based ring radii use
the current full or minimized silhouette for every card. A bounded weighted-
link/same-ring relaxation then shortens maximum and total relation length only
if crossings, card collisions, and a protected 72-model-pixel connected-card
boundary gap do not worsen. A fixed ring-spacing margin keeps reset layouts
clear of that exact acceptance floor.
This placement is presentation-only and runs only on initial load or explicit
layout reset; bounded settlement runs only after sizing or drag release, never
while idle.

Any real card can be minimized or maximized independently. Canvas labels and
hover use only the first six object-hash digits plus localized role and plane;
the full record stays in the right panel. V5 Fact summaries humanize machine
anchors and delimit a bounded historical ASCII-math grammar for MathJax while
formal/original text and hashes remain exact. A minimized card remains selectable
and draggable. In both silhouettes, the size-control center occupies the same
normalized point: 29% of rendered width and 50% of rendered height. Resizing
compensates the node position so the replacement plus or minus stays at the same
screen coordinate. Full-card text widths and margins are paired by role to keep
the control-plus-label envelope within 3% of the card center across supported
zoom while retaining clearance from the control and silhouette; multiline
real-card labels are left-justified so short wrapped lines do not pull the
visual center to the right. Hovering any part of a card, including its internal
toggle, applies one continuous related-edge emphasis and dims unrelated edges
until the pointer leaves the whole card. The toggle itself is
click-, tap-, and keyboard-only; a
gesture that begins on it never drags or pins the card. Direct dragging from the
rest of either card size remains available. The renderer applies deterministic
two-axis pivot compensation to every changed card; if that card already has a
session pin, it updates that pin, and it never creates a pin for an unpinned
card. Minimum canvas zoom is bounded so compact cards do not lose their
internal size control at an unreadable scale. Selection keeps a crisp
moonlight-yellow outline plus a soft halo clipped to the active role silhouette.
In Plaques, the inner ornamental stroke is deliberately dimmer than the outer
stroke without changing plane or status semantics. Every semantic relation uses
an enlarged category-colored marker at its midpoint and another at its target,
giving two evenly spaced direction cues while retaining solid, dashed, or dotted
line semantics. Synthetic theme-grouping links remain arrowless. Double-
clicking a card performs one atomic path-sizing action:
it maximizes the anchor plus the union of its complete directed upstream and
downstream closures and minimizes the currently eligible complement.
Secondary-click or trackpad auxiliary click opens only `maximize all upstream`
and `maximize all downstream`; each includes the anchor and records one atomic
sizing action. There is no hidden focus mode or Back/Escape return state.

Sizing undo and redo are bounded to 100 in-memory size deltas. No-op actions
create no entry, a new sizing action after undo clears redo, and the standard
Cmd/Ctrl+Z and Cmd/Ctrl+Shift+Z shortcuts leave native editing undo untouched.
Undo and redo store only card-size deltas and no position snapshots; applying an
inverse size recomputes the same pivot compensation. They never restore
selection, pan, zoom, layer filters, search, locale, appearance, or detail settings.
Faceted is the default appearance scheme and Plaques is the alternative. The
scheme changes node silhouettes only; it does not change plane colors, status
borders, relation styling, positions, size state, or history. Appearance is
session-only and is distinct from packet `theme_order`.

Treat the canvas as trackpad-first: two-finger gestures pan and pinch zooms
around the pointer. Primary-button dragging on empty canvas box-selects with a
soft green silhouette; dragging a selected card moves only that selected set by
one common offset. It cancels pending convergence and pins only the moved set,
so the canonical neighborhood stays stable. Card-size changes alone run the
fixed fourteen-pass convergence; idle reading never runs it. Modifiers add the
next rectangle. Touch/pen contact pans. Movement remains session-only and never
changes topology. Sizing preserves the current
viewport and graph ordering by recomputing deterministic compensation from the
old and new 29%/50% rendered anchors. When a changed card already has a session
pin, the renderer replaces that existing pin. Neighbor coordinates produced by
the post-size convergence become session pins; the anchored card itself is not
newly pinned. The renderer never automatically refits the graph, and
`Fit view` is explicit. Layer switches change eligibility without changing size
state or sizing history, so re-enabling a layer restores each card's prior size.
Manual positions and interface state last only for the page session. Generate
the final page directly; do not create a preview gate, watcher, background
refresh process, persistent visualization history, sidecar, local-storage
state, or writeback.
Warnings remain visible but do not become facts. PDF conversion is a separate
case-by-case request. See the reader-export reference for the exact packet and
failure contract.

## Audit before reporting completion

Run:

```bash
"$MGRAPH" --root "$PROJECT" --role main audit
"$MGRAPH" --root "$PROJECT" --role main mode-status
```

Report separately:

- current mode and exact mode-event binding;
- completed versus unresolved exploration obligations;
- Paper, Audit, Blackboard, Fact, and Learning status;
- candidate claims versus admitted facts;
- computation replay status;
- audit errors, warnings, and residual uncertainty.

For an adverse-routing-enabled project, produce the host-task attack report
before closing CHX. Keep its worker-reported counterexamples, proposed route
changes, and pending user decisions under a separate **Attack report** label;
never classify them as CHX architecture issues or as admitted Facts.

After those checks, close the task's CHX runtime ledger immediately before the
final response. If `report_required=true`, report each included CHX issue with
its causal mechanism, effect, disposition, and ledger path.
If `report_required=false`, say nothing about the CHX ledger. If ledger startup,
validation, or close failed, disclose that host-procedure failure instead of
claiming a compliant post-0.4.1 run.

Do not deploy, replace installed skills, package an archive, or migrate an active project merely because this candidate exists. Installation and cutover require separate explicit authorization.
