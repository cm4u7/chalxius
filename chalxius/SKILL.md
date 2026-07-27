---
name: chalxius
description: Operate Chalxius, the integrated system for mathematical, philosophical, paper-led, computational, and academic teaching work. Use it to choose or switch fast, auto, and deep reasoning profiles; build source-bound Paper Logic and Audit Graphs; run Blackboard exploration and replayable verification; admit facts through one invariant gate; import legacy Danus facts; explicitly export a human-readable offline knowledge map; or, when academic teaching or testing is explicitly requested, activate Chalxius Learner over frozen Fact, Paper, and Blackboard snapshots.
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
- V4 memory, routing, or adoption decisions: [references/adoption_policy_v4.md](references/adoption_policy_v4.md).
- Round creation, worker execution, return validation, or ingestion: [references/agent_protocol_v4.md](references/agent_protocol_v4.md).
- Blackboard graph types, query, snapshots, merge, or pulses: [references/blackboard_graph_v4.md](references/blackboard_graph_v4.md).
- Computation, checkpoints, artifact replay, or numerical evidence: [references/computational_verification_v4.md](references/computational_verification_v4.md).
- Campaigns, targets, historical projects, and migration: [references/campaigns_and_migration_v4.md](references/campaigns_and_migration_v4.md).
- External theorems or sources: [references/external_theorem_applicability.md](references/external_theorem_applicability.md) and [references/external_source_reliability.md](references/external_source_reliability.md).
- Explicitly requested academic teaching or testing over graph snapshots: [references/unified_learning_plane.md](references/unified_learning_plane.md) and [references/fact-graph-grilling.md](references/fact-graph-grilling.md).
- Explicitly requested human-readable single-file graph visualization: [references/reader_html_export.md](references/reader_html_export.md).
- Engine or release changes: [references/capability_difference_audit.md](references/capability_difference_audit.md) and [references/unified_release_traceability.md](references/unified_release_traceability.md).

## Preserve the four-plane boundary

Keep these stores distinct:

1. Paper Graph: source-authority objects, researcher reconstruction, and correctable paper audit.
2. Blackboard Graph: agent-created exploration, obstacles, challenges, plans, experiments, and mirrors.
3. Fact Graph: the only admitted mathematical or philosophical premises.
4. Learning Graph: teaching coverage, mastery evidence, misconceptions, and pedagogical nodes; always nontruth.

A full-fidelity Paper mirror on the Blackboard remains an exploration projection with an exact receipt. It is not Paper authority and not a Fact. An Audit node may challenge a reconstruction or a paper claim without admitting the challenge as truth. If an Audit Graph is wrong, append a challenge, disposition, replacement object, and new snapshot; never rewrite the historical audit.

## Choose a reasoning mode

Use one of the following project-level profiles:

- `fast`: low-orchestration Chalxius research. High-cost exploration is opt-in. All hashes, snapshots, source checks, verifier separation, review binding, audit, and admission gates remain active.
- `auto`: deterministic workload routing. Paper, explicit source ambiguity, computation, multi-candidate, novelty, and external-output signals activate only the applicable expensive features. `source_ambiguity=true` requires `source_claim=true`; its absence is legacy-compatible `false` and never weakens the independent source-claim admission gate.
- `deep`: every applicable expensive research feature is required. A genuinely irrelevant feature is recorded `not_applicable`; it is never faked merely to fill a checklist.

If the user does not choose, use `auto`. The new project-level `reasoning_mode` is separate from the existing assignment `plan-round --mode auto|prove|refute|...`; never conflate them.

Deep requirements are durable obligations. Every new unified round freezes a
`profile_obligations` map derived from its assignment profiles. A required Paper
snapshot, Audit snapshot, computation receipt, campaign expansion, clean-context
panel, barriered pulse, or synthesis pass must be completed and hash-bound in a
round profile-closure receipt before verifier-task construction, review
recording, or admission, or the work remains blocked. Fast cannot waive an
admission obligation: missing
replay, source, convention, quantifier, atomic-bundle, or fresh-verifier evidence
leaves the result `candidate_only_until_gate_satisfied` or
`blocked_requires_mode_switch_or_external_evidence`.

Profile closure has `truth_effect="workflow_readiness_only"` and is a
workflow-readiness gate adjacent to, but outside, the
invariant Fact admission contract. It never changes that contract's hash or
certification strength. A round with no required exploration features is
recomputably `not_required`, needs no receipt, and rejects an attempt to create a
ceremonial receipt.

## Initialize a new project

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

New writes use workflow-evidence V4 only. The engine still recognizes older
pre-Chalxius V4 projects without unified governance as read-only historical
state. Do not call them corrupt. Explicitly activate future unified writes:

```bash
"$MGRAPH" --root "$LEGACY_PROJECT" --role operator mode-init \
  --mode auto --actor operator \
  --reason "Activate Chalxius routing; preserve all frozen predecessor evidence."
```

`mode-init` first runs a byte-pure current audit before creating the advisory
lock. Only a clean project enters the transition lock; inside that lock the
audit and inventory are recomputed before any governance byte is written. It
then inventories and hashes
existing rounds plus the exact byte set supporting every already-accepted
ordinary Fact and atomic FactBundle. Only those exact accepted objects receive
a future-only historical exemption; pending candidates are never exempt, and
later byte drift fails audit and blocks further mutation. No public API or CLI
writer—including writers reached through exposed child stores—may change a
mode-less, partial, or corrupt V4 project before that explicit activation. The
receipt does not relabel or rewrite historical work. A unified V4 round created
before `profile_obligations` existed must be replanned; closure evidence must
not be synthesized retroactively. V1-V3 state is strictly read-only at both API
and CLI layers and must use the documented isolated copy-upgrade flow before
`mode-init`. The Python-only `reasoning_mode=None` escape is reserved for the
internal inherited-project fixture seam; it is not an official writable
unified-project path, and the CLI initializes new projects in `auto` unless
another profile is explicit.

Public constructors expose no `allow_legacy_*` writer switches. The underscored
legacy-format and V1-V3 fixture/copy-migration constructors use module-private
identity tokens and are only internal compatibility seams. This is cooperative
in-process integrity, not an authentication, ACL, sandbox, or hostile Python
reflection boundary; direct filesystem access or deliberate invocation of
private internals is outside the claim.

Read-like APIs must not repair projections or caches implicitly. In particular,
`statement_interface(..., materialize=True)` is mutation-guarded, while
`materialize=False` reconstructs a missing optional interface only in memory.
Audit and claim-card construction use the pure form. Blackboard
`reindex(apply=False)` is a pure comparison; experiment status and resume
validation neither create the advisory lock nor rebuild the derived SQLite
index. Explicit applying/mutating calls retain the normal write guard.

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

The abort blocks future managed returns, experiment writes, pulse planning, dispatch, barrier, void, and closure actions for that round. Read-only status and audit remain available; a whole-pulse abort remains available as terminal cleanup.

## Run research work

1. Initialize or select a campaign and exact target.
2. For a paper-led task, freeze the source bytes and construct Paper source and reconstruction planes. Obtain `source_fidelity` and `graph_structure` reviews from two distinct fresh reviewers/contexts before freezing the logic `pls-*`. Then construct the Audit Graph and obtain `target_binding` and `audit_reasoning` reviews from two distinct fresh reviewers/contexts before freezing or relying on the audited snapshot.
3. Create V4 memory with an explicit workload profile and source, convention, quantifier, computation, candidate-DAG, audience, and terminology signals.
4. Plan the round. The engine binds the current mode event, invariant admission contract, deterministic execution profile, adoption plan, frozen Blackboard snapshot, campaign, and `host_task_scope_id` into every task card and assignment contract.
5. Execute only from the frozen task card. Use `preflight-return` while a worker draft is repairable; ingest exact worker-final bytes only after validation.
6. Satisfy every required exploration feature. For substantive deep work, use all currently callable clean-context worker slots for genuinely distinct channels, with the score used only for priority/load ordering.
7. For collaborative work, use the durable two-wave barriered Blackboard pulse. Bind `--host-config`, record `pulse-dispatch` only after the native clean-context spawn, and distinguish `procedural_ready` from `machine_verified_ready`. A failed core ingestion writes `pulse-abort`; federation is deliberately disabled.
8. After all governed assignment returns are canonically ingested, inspect
   `profile-closure-status ROUND_ID`. If it reports required features, create one
   exact evidence input and run `profile-closure-record`; recheck status before
   asking for a verifier. The receipt binds each assignment's task card, return,
   ingestion, outcome, and effect, so evidence from a neighboring assignment or
   earlier round cannot substitute.
9. Keep candidate synthesis on the Blackboard until a separate admission workflow succeeds.

```bash
"$MGRAPH" --root "$PROJECT" --role main profile-closure-status ROUND_ID
"$MGRAPH" --root "$PROJECT" --role main profile-closure-record ROUND_ID \
  --input PROFILE_CLOSURE.json --actor main
```

Evidence labels are literal. Native stores can provide machine-verified
receipts; host capacity, specialist identity, campaign scope, and the
assignment-specific meaning of an expert synthesis are procedural host
attestations. A composite must say
`mixed_procedural_and_machine_verified`, not inflate the whole feature to
machine-verified. Novelty and campaign expansion events must be recorded no
earlier than the governed round. Paper evidence may intentionally reuse an
earlier reviewed snapshot only while it remains the current, non-superseded
snapshot; an Audit snapshot whose Logic base was superseded is stale.

The V4 duration rule is based only on the host-observed active-interval union. Exactly 1200 seconds does not trigger; a notice appears only when elapsed work is strictly greater than 1200 seconds. Worker telemetry cannot trigger it, the notice never sends SIGKILL, and managed work remains runnable until an explicit stop or work-unit abort.

For load-bearing computation, record immutable commands, implementation and version, staged checkpoints, replay artifacts, independent checks, and exact output hashes. Prepare a frozen verifier capability with `scripts/prepare_verifier_capsule.py`; a verifier receives only that capability and never the research workspace.

## Admit facts through one contract

No mode directly writes truth. Only `fact_graph/facts/*.md` is admissible premise state. Every new fact must pass the same contract hash and the same gates:

- content-addressed statement, proof, direct predecessors, source evidence, task card, and candidate bytes;
- active statement-only predecessor closure;
- exact source and applicability fidelity, including notation, hypotheses, witnesses, conventions, formula glyphs, quantifiers, and transports;
- independent replay for load-bearing computation;
- an atomic internal mini-DAG bundle when candidate facts depend on one another;
- a different fresh verifier using the frozen packet or bundle capability;
- hash-bound review, gateway acceptance, admission, and stored fact;
- cascade revocation and a clean current audit.

Fact communication uses claim cards and expert lint receipts. Exploration communication uses interpretation cards and `interpret-lint-receipts`; neither is admission. If any gate is missing, report candidate status and the exact blocker instead of downgrading the gate because the project is in fast mode.

## Import legacy Danus facts

Danus 0.2.12 is a legacy import source and behavioral performance reference, not a runtime dependency. Import only exact frozen facts, certificates, targets, and hashes. Preserve their inherited assurance and provenance. Never reinterpret or silently recertify an imported admitted fact. Every fact created after import goes through the Chalxius admission contract.

Retired predecessor packages remain mutually exclusive rollback writers. This
skill does not start an old runtime, combine two mutable project roots, or
transplant a predecessor protocol. The retired coordinator is rollback lineage
only.

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
graph ordering, and direct card dragging. Every changed card receives only the
derived model-position compensation needed to keep its size-control pivot fixed
on both rendered axes.
Synthetic multi-target theme nodes stay
readable while their targets are eligible but are excluded from card sizing and
sizing history.

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

Treat the canvas as trackpad-first: two-finger gestures pan, pinch gestures
zoom, and card bodies remain directly draggable. Sizing preserves the current
viewport and graph ordering by recomputing deterministic compensation from the
old and new 29%/50% rendered anchors. When a changed card already has a session
pin, the renderer replaces that existing pin; it never automatically refits the graph or
creates a pin for an unpinned card, and
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
