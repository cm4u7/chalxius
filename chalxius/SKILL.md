---
name: chalxius
description: Operate Chalxius, the integrated system for mathematical, philosophical, paper-led, computational, and academic teaching work. Use it to choose or switch fast, auto, and deep reasoning profiles; build source-bound Paper Logic and Audit Graphs; run cumulative Research and replayable verification; certify V5 Facts through one invariant gate; use a user-generated project background or export an offline knowledge map; or, when academic teaching or testing is explicitly requested, activate Chalxius Learner over frozen Fact, Paper, and Blackboard snapshots.
---

# Chalxius

Use the bundled Chalxius research engine as the only research runtime. Fast,
auto, and deep are execution profiles of that one engine. The Fact Graph
admission contract is identical in every profile.

`chalxius` is the public skill name. The earlier
`operate-mathgraph-unified` label survives only as an archived candidate name
and a compatibility protocol identifier in already-defined artifact schemas;
it is not a second runtime or user-facing route.

## Read the governing references

Before any project write, read [references/unified_architecture.md](references/unified_architecture.md), [references/reasoning_modes.md](references/reasoning_modes.md), and [references/admission_contract.md](references/admission_contract.md).

Read the directly applicable Chalxius reference before acting:

- Paper reconstruction, audit, correction, mirroring, or paper-led planning: [references/paper_logic_graph_v1.md](references/paper_logic_graph_v1.md).
- V5 Research, lifecycle, retained capabilities, or release work: [references/v5_capability_matrix.md](references/v5_capability_matrix.md).
- Historical V4 memory, routing, or adoption behavior: [references/adoption_policy_v4.md](references/adoption_policy_v4.md).
- Round creation, worker execution, return validation, or ingestion: [references/agent_protocol_v4.md](references/agent_protocol_v4.md).
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

Every worker task card retains three communication planes: compact control,
one frozen mathematical-state view, and bounded narrative. The card is the
immutable capability boundary. Never replace it with prompt prose or infer
capabilities from filesystem visibility.

A full-fidelity Paper mirror on the Blackboard remains an exploration
projection with an exact receipt. If an Audit Graph is wrong, append a
challenge, disposition, replacement object, and new snapshot; never rewrite
historical audit bytes.

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

Every switch appends a content-addressed event. It applies to future work units only. A frozen round retains its original mode event, deterministic execution profile, and admission-contract hash until completion. To discontinue it explicitly:

```bash
"$MGRAPH" --root "$PROJECT" --role main work-unit-abort ROUND_ID \
  --actor main --reason "Superseded by a newly planned deep round."
```

The abort blocks future managed returns, experiment writes, and new Pulse
commitments or dispatch for that round. It preserves existing Research,
receipts, and read-only audit. Use whole-pulse abort only to stop future Pulse
dispatch while retaining accumulated contributions.

## Run research work

1. Add or select cumulative Research. Challenges, counterexamples, obstacles,
   insights, repairs, and dispositions remain separate immutable entries.
2. For paper-led work, freeze exact Paper Logic and Audit snapshots with their
   independent reviews.
3. Plan a round. The card binds the current mode, one Blackboard snapshot,
   exact admitted predecessor interfaces, related Research context, and the
   three communication planes. Bind the actual host task/thread through
   `host_task_scope_id` when that identifier is available.
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

```bash
"$MGRAPH" --root "$PROJECT" --role main profile-closure-status ROUND_ID
"$MGRAPH" --root "$PROJECT" --role main profile-closure-record ROUND_ID \
  --input PROFILE_CLOSURE.json --actor main
```

`profile-closure-status` may still be used for local repair suggestions, but a
recorded suggestion never marks the work complete. Paper evidence may reuse an
earlier reviewed snapshot only while it remains current and nonsuperseded.

For load-bearing computation, record immutable commands, implementation and version, staged checkpoints, replay artifacts, independent checks, and exact output hashes. Prepare a frozen verifier capability with `scripts/prepare_verifier_capsule.py`; a verifier receives only that capability and never the research workspace.

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

V5 does not accept V4 or Danus Facts as authority. Preserve historical roots
unchanged and readable. When the user explicitly asks to generate or refresh a
project background, read the relevant project files broadly and write exactly
one `PROJECT_BACKGROUND.md` summary. Do not generate, refresh, or incrementally
update it from mere file presence.

Once the summary exists, every substantive V5 work unit and V5 Reader
projection reads it by default and binds the full body and hash:

```bash
"$MGRAPH" --root "$PROJECT" --role main plan-round --workers 1 \
  --memory-id RESEARCH_ID
```

If the file is absent, Chalxius proceeds without background and does not create
one. Treat the summary as nontruth context; return to the exact cited source
for every load-bearing use. Retired predecessor packages remain rollback
lineage only and are never started beside V5.

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
of `--packet` to project the current Fact, Research, Certification,
Paper/Audit, Blackboard, and default-if-present project-background views into
the same packet-v1 renderer. Non-Fact planes remain visibly nontruth, and an
oversized projection fails rather than truncating silently.

Successful Reader Finalize deterministically binds the frozen source snapshot,
canonical packet SHA-256, node count, and complete-sidebar count into
`reader_finalize` metadata. The same metadata is embedded in the page build
metadata and returned in command stdout with
`scope="presentation_readiness_only"` and `truth_effect="none"`; it creates no
receipt file or new authority object.

The deterministic renderer overwrites only
`PROJECT/visualizations/knowledge-map.html`. It embeds all graph, interaction,
and math-rendering code, performs no network request or model call, and writes
nothing back to the source graphs. Its bilingual Reload graph control performs
only same-document navigation, so a browser reload reads the latest atomically
replaced file and resets runtime UI state. It is not a watcher, poller, fetch
loop, or hot-reload service. Every currently eligible packet node and
edge remains on one continuing canvas; card minimization changes only visual
size and never graph topology or edge eligibility. The initial `All targets`
size action leaves eligible targets full-size and minimizes eligible non-target
cards. `All cards` maximizes every eligible real card. These are reversible
sizing actions, not navigation modes, and they preserve selection, viewport,
graph ordering, and direct card dragging. Every changed card first receives the
derived model-position compensation needed to keep its size-control pivot fixed
on both rendered axes. After the new silhouette is applied, the renderer runs
exactly fourteen deterministic spacing passes. A direct card, directional path,
complete path, or topic-path anchor remains fixed; global actions use every
changed card as a seed without inventing a special view. Undo and redo run the
same convergence. Nearby silhouettes repel below the protected gap and visible
relation neighbors attract only above the comfortable link gap. Pan and zoom
are preserved and fitting remains explicit.
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
layout reset.

Any real card can be minimized or maximized independently. A minimized card
remains selectable and draggable from its card body, exposes its readable title
on hover, and opens the same complete right-panel detail. In both full and
compact silhouettes, the size-control center occupies the same normalized
internal point: 29% of rendered width and 50% of rendered height. Resizing
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

Treat the canvas as trackpad-first: two-finger gestures pan, while pinch input
is handled explicitly as pointer-centered zoom rather than delegated to an
environment-dependent browser default. Primary-button dragging on empty canvas
draws a selection rectangle and
gives every selected node a soft green silhouette glow;
dragging any selected card body then moves the entire selected set by the same
offset, preserving relative positions. For at most 240 visible nodes during
direct drag, nearby cards repel below the protected gap and relation neighbors
weakly attract above a
comfortable link gap; release settles for at most fourteen passes, then motion
stops. Every effective card-size change runs a separate fixed fourteen-pass
convergence after sizing; idle reading never runs the force. Shift, Option,
Control, or Command adds
the next rectangle to the selection. Direct touch/pen contact pans instead of
starting a box selection. Single-card and group movement create session pins
only and never change graph topology. Sizing preserves the current
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

Do not deploy, replace installed skills, package an archive, or migrate an active project merely because this candidate exists. Installation and cutover require separate explicit authorization.
