# Deterministic reader HTML export

Read this reference before preparing or rendering a reader packet. The feature
is an explicitly requested, presentation-only export. It is not a watcher, an
Obsidian bridge, a PDF manager, a learning record, a research work unit, or a
Fact admission path.

## Authority boundary

The Chalxius host step may read frozen Fact, Paper, Audit, Blackboard, Learning,
and reader-note material and assemble one `reader packet`. That packet has
`truth_effect="none"`. It may simplify presentation, but it must preserve every
formula, quantifier, hypothesis, negation, edge direction, source status, exact
original text, and source binding that it includes.

The deterministic renderer only validates JSON and assembles static bytes. It
does not invoke a model, search, network service, API, or another skill. It does
not infer missing nodes or relations. It never promotes Paper, Audit,
Blackboard, Learning, or reader-note content to Fact authority. A candidate,
open item, challenged reconstruction, or exploratory claim must retain its
native nontruth status.

The page is a low-stakes reading aid. The project graph and its immutable source
objects remain authoritative. A successful export says nothing about
mathematical correctness, novelty, admission readiness, or graph audit quality.

## Public command and fixed output

Prepare a UTF-8 JSON packet, then run:

```bash
MGRAPH=/absolute/path/to/chalxius/scripts/mgraph
PROJECT=/absolute/path/to/chalxius-project
READER_PACKET=/absolute/path/to/reader-packet.json

"$MGRAPH" --root "$PROJECT" --role main export-reader-html \
  --packet "$READER_PACKET"
```

For a V5 project with at least one admitted Fact, the host may instead request
the deterministic projection adapter:

```bash
"$MGRAPH" --root "$PROJECT" --role main export-reader-html \
  --v5-projection
```

That adapter projects active Facts, cumulative Research, Candidate Releases,
Certification Decisions, current and superseded Paper/Audit snapshots, and
Blackboard objects into the unchanged packet-v1 schema. It labels every
non-Fact object as nontruth and refuses to relabel Research as knowledge. When
`PROJECT_BACKGROUND.md` exists, it is included by default with its complete
body and hash; absence does not create it. Packet limits fail visibly instead
of silently truncating the graph.

`operator` may run the same command. No other role receives it. The command has
no output-path option. It atomically replaces exactly:

```text
PROJECT/visualizations/knowledge-map.html
```

### Reader Finalize

Reader Finalize is the strengthened validation-and-render stage inside this
same `export-reader-html` command. It is not another CLI command, persistent
receipt, graph plane, research work unit, or Fact gate. Before any output byte
is replaced, every included node—including nodes hidden by default optional
layer switches—must provide nonempty, non-whitespace `summary`, `intuition`,
`importance`, and `reasoning` strings. Missing or incomplete sidebar material
therefore fails closed while the previous fixed HTML remains unchanged.

For a valid packet, the renderer deterministically creates
`reader_finalize` schema 1 metadata with status `ready`, scope
`presentation_readiness_only`, source-snapshot id and SHA-256, canonical packet
SHA-256, node count, complete-sidebar count, and `truth_effect="none"`. The
metadata is embedded in the page build metadata and returned in command stdout;
it creates no sidecar or durable receipt and does not certify the graph or its
mathematics.

Top-level `source_snapshot` is the host-declared aggregate freeze for this
export, not a requirement that every native object originate from one snapshot
id. Per-node and per-edge `provenance.snapshot_id` values may legitimately
differ across Fact, Paper, Audit, Blackboard, Learning, and reader-note sources.
The canonical `reader_finalize.packet_sha256` collectively binds those native
provenance values together with the complete sidebar and packet bytes.

The exporter creates no persistent visualization history, receipt ledger,
layout file, sidecar, local-storage entry, graph mutation, or writeback. The
page may retain at most 100 in-memory card-size deltas for session undo and
redo. The input packet may be ephemeral. Re-running the command replaces the
one page. Browser refresh or the bilingual Reload graph button then navigates
to that same document and clears size history, manual layout changes,
appearance choice, and all other runtime interface state. The button uses
`window.location.reload()` only: it performs no fetch, polling, watcher,
WebSocket, storage, or background synchronization.

Because the command writes a derived project file, ordinary project mutation
locking and unified-mode write guards still apply. This write has no truth
effect and does not change any Fact, Paper, Audit, Blackboard, campaign, target,
or Learning object.

## Reader packet v1

The complete machine-checkable example is
[`assets/reader_packet.v1.example.json`](../assets/reader_packet.v1.example.json).
Unknown or missing fields fail closed. The top-level fields are:

| Field | Meaning |
|---|---|
| `schema_version` | Exact integer `1` |
| `project_id` | Must equal the selected Chalxius project |
| `language` | Exact string `en` for this release |
| `title`, `audience` | Reader-facing identity |
| `source_snapshot` | Frozen source id, SHA-256, and description |
| `presentation` | Subtitle and short introduction |
| `audit` | Current flag, concise summary, warnings, and unresolved items |
| `theme_order` | Explicit order of target groups |
| `target_order` | Exact target order, equal to ordered theme target lists |
| `prerequisite_order` | Per-target tie-break order covering every prerequisite ancestor exactly |
| `themes` | Target groups and their readable descriptions |
| `nodes`, `edges` | Strict reader graph |

`theme_order`, `target_order`, and `prerequisite_order` are semantic input, not
mutable runtime layout state. The renderer validates and preserves those lists
verbatim, and `target_order` remains the navigation order. Canonical spatial
placement is separate: synthetic multi-target themes occupy the innermost core,
target cards occupy a central ring, and every remaining packet node occupies an
outward ring indexed by its undirected graph distance from the target set.
Packet order seeds each ring. For at most 1,200 scored edges, exact radial
proper-crossing scoring retains the best of that baseline, eight fixed circular
neighbor-sweep pairs, and at most 48 deterministic adjacent ring swaps across
two refinement passes, so the selected order cannot contain more scored
crossings than the baseline. Ring radii use exact chord spacing. For at most
320 nodes and 1,200 edges, a second bounded deterministic phase applies
weighted edge attraction, same-ring repulsion, and seed-angle tethering, then
scores fixed blends. It never accepts more crossings, boundary-clearance
violations, maximum edge length, or total edge length than the selected radial
seed. Canonical placement measures each card in its current full or minimized
state and preserves at least 72 model pixels between connected-card boundaries,
plus a fixed ring-spacing margin, so compaction cannot erase the visible
relation segment and direction markers.
Larger graphs preserve the deterministic seed. Neither search rewrites semantic
lists, topology, or packet bytes, and card sizing does not invoke them.

Every node includes:

- one safe packet-local `id`, title, reader role, source plane, visual status,
  knowledge/research layer, and theme;
- a nonempty readable summary, intuition, importance, and reasoning route, plus
  the exact list of direct prerequisite node ids;
- a formal block containing hypotheses, statement, proof or reasoning record,
  exact relations, and exact original text;
- provenance containing source plane/status, truth status, object id, snapshot,
  locator, object SHA-256, exact-text SHA-256, and replacement lineage.

The exact-text SHA-256 is recomputed by the renderer. The object SHA-256 and
snapshot SHA-256 retain upstream identity; the renderer checks their syntax but
does not pretend to re-audit the upstream object. Full ids and hashes are folded
by default in the page but remain viewable and copyable.

Truth-status vocabulary is plane-specific:

| Plane | Permitted truth-status labels |
|---|---|
| Fact | `admitted_fact`, `historical_inactive` |
| Paper | `source_authority`, `interpretation`, `historical_inactive` |
| Audit | `audit_evidence`, `historical_inactive` |
| Blackboard | `exploration`, `historical_inactive` |
| Learning | `learning`, `historical_inactive` |
| Reader note | `reader_note` |

Fact-plane nodes whose source status contains candidate, pending, exploration,
open, verifying, or challenged vocabulary are rejected. If an admitted Fact is
under external challenge but remains active, keep its source status `admitted`
and use the separate visual status `challenged`; do not rewrite its authority.

Every edge includes packet-local id, source, target, one reader category,
readable relation, exact source relation type, weak flag, layer, and provenance.
The packet direction is always prerequisite/supporting material toward the
dependent conclusion. Exact relation types remain visible on selection.

The four displayed categories are deliberately compressed:

| Reader category | Display |
|---|---|
| `prerequisite` | blue solid line with triangle head |
| `support` | green heavy line with vee head |
| `repair` | amber dashed line with hollow diamond head |
| `conflict` | magenta dotted line with tee terminator |

Prerequisite edges must be strong knowledge-layer edges. Their endpoints must
exist, their node-declared direct-prerequisite lists must match edge order, and
the prerequisite subgraph must be acyclic. Research-process and weak contextual
relations remain hidden by default.

## Human-readable page behavior

The first view shows all targets, grouped by `theme_order` and listed in exact
`target_order`. A one-target theme is rendered as a topic label on its target;
only a multi-target theme becomes a draggable presentation node with dashed
grouping links. Those links are smooth, dashed, arrowless Bezier curves,
synthetic reader structure, and never source relations. Synthetic presentation
nodes remain visible while at least one of their targets is eligible, but they
are not packet source cards and are excluded from card minimization, sizing
history, and source-card counts.

Every currently eligible real packet node and every currently eligible packet
edge remains present on one continuing canvas. Minimization changes only a
card's visual size: it never hides a node, suppresses an edge, or changes graph
topology. The initial `All targets` sizing action keeps eligible targets full-
size and minimizes every eligible non-target card. `All cards` maximizes every
eligible real card, including isolated cards. These are sizing actions rather
than view modes; if every eligible node is a target, their resulting size states
may be identical. A compact floating dock also provides explicit `Fit view`,
layout reset, sizing undo/redo, appearance selection, and optional-layer
controls.

Primary-button dragging from empty canvas draws a visible selection rectangle.
Every visible node whose rendered bounds overlap that rectangle joins the
selection; Shift, Option, Control, or Command preserves the existing set and
adds the new rectangle. Dragging any selected card body moves every selected
node by the same model-space offset, preserving their relative positions.
Those manual coordinates are page-session pins only. Selection and movement do
not alter packet topology, edge direction, semantic order, source text, or
authority. A background click clears the set. Direct touch or pen contact pans
the canvas instead of creating a selection rectangle.

Any real card, regardless of role, has a node-local size toggle that minimizes
or maximizes that card only. Full and compact cards place the toggle center at
the same normalized point—29% of the rendered width and 50% of the rendered
height. Minimization and maximization compensate around that shared anchor, so
the replacement plus or minus stays at the same rendered coordinate and
repeated size changes require no pointer repositioning. The control size is 45%
of the compact role height at the current zoom, clamped to 11–20 rendered
pixels. The toggle is
click-, tap-, and keyboard-only: pointer movement beginning on it never moves or
pins the card. A minimized card remains selectable and directly draggable from
the rest of its card body without adding a sizing-history entry. Every changed
card receives deterministic compensation on both model axes from the old and
new rendered anchors. If
it already has a session pin, that pin is replaced with the compensated model
position; an unpinned card does not acquire a pin. The canvas
minimum zoom is bounded so the smallest compact role still contains its minimum
readable control and internal padding; users pan rather than losing the control
at an unreadable overview scale.
Hover exposes the readable title, selecting opens the same full right-panel
detail, and the selected card retains a vivid moonlight-yellow outline plus a
soft role-silhouette halo rather than a rectangular aura. Its smaller
silhouette therefore saves space without discarding identity, provenance, or
access to the complete readable record.

Double-clicking any real card performs one atomic path-sizing action. It
maximizes the chosen anchor and the union of its complete directed upstream and
downstream closures, then minimizes the currently eligible complement. This is
not an undirected connected-component traversal and does not create a focus
mode, saved return surface, or Back/Escape exit state. Secondary-click,
trackpad auxiliary click, or Shift+F10 opens a two-command node menu:
`maximize all upstream` and `maximize all downstream`. Each traversal is
directed, includes the chosen anchor, changes sizes only, and records one atomic
sizing action. Previous and next target buttons continue to follow exact
`target_order`.

Double-clicking a synthetic multi-target theme performs the analogous group
operation without making that theme a source card. For every currently eligible
member target, the renderer takes its complete directed upstream and downstream
closures, unions those real-card ids, maximizes the union, and minimizes the
eligible complement. The entire change is one atomic sizing action. It creates
no theme-specific focus mode, adds no packet edge, and leaves the synthetic
theme outside card-size state and history.

The reader keeps at most 100 in-memory size deltas for undo and redo. A single-
card toggle, `All targets`, `All cards`, real-card or theme double-click path
maximization, and either context-menu command each form at most one history
action. A no-op adds no entry, and a new sizing action after undo clears the
redo stack. Cmd/Ctrl+Z
undoes sizing; Cmd/Ctrl+Shift+Z, and Ctrl+Y where expected, redo it. Editable
fields retain native undo. Sizing history stores no coordinate snapshots; an
inverse size recomputes the same pivot compensation. It never restores
selection, pan, zoom, layer filters, search, language, appearance, detail width,
or text scale.

Research-process, teaching/learning, reader-note, and weak contextual material
are separate switches and are off by default. Layer switches change eligibility
only. They do not mutate card size state or sizing history, and a card hidden by
a layer switch returns at its prior size when the layer is enabled again.

Every sizing action preserves the current selection, pan, zoom, graph ordering,
and normalized 29%/50% control pivot. The exporter computes one deterministic
canonical position for every packet node. Synthetic multi-target theme nodes
occupy the innermost core, targets occupy the next central ring, and all other
nodes occupy progressively outward rings by undirected graph distance from the
target set. Packet order deterministically seeds each ring. Eight fixed circular
weighted-neighbor sweep pairs followed by at most 48 adjacent ring-swap
candidates across two refinement passes may reorder nodes within a ring; prerequisite,
support, repair, and conflict relations have weights `4`, `2`, `1`, and `1`.
When the packet has at most 1,200 scored edges, the renderer exactly counts
proper crossings after every half-sweep and retains the best-so-far radial
order. Crossing count is primary; weighted crossing penalty and packet-order
displacement provide deterministic tie breaks. Since packet order is the
initial best-so-far, the final order is guaranteed to have no more scored
crossings than that baseline. Packets above the edge bound skip the quadratic
comparison and preserve packet order. This bounded search does not claim a
global minimum. Ring radii use chord spacing rather than circumference
averages. A subsequent deterministic angular relaxation, bounded to 320 nodes
and the same 1,200-edge ceiling, minimizes maximum and total link length
subject to no-worse crossing, card-clearance, and collision constraints. The
canonical boundary gap for connected cards is 72 model pixels. It runs only
for initial canonical placement and explicit
`Reset layout`, never for card sizing, sizing undo/redo, layer changes, or box
selection. Compact silhouettes collapse about the control pivot, and
Cytoscape reattaches each visible edge to the changed silhouette. Sizing derives
one two-axis model-position compensation for every changed card to keep that
pivot fixed. If the card was manually pinned, the renderer also replaces that
existing pin; it never creates a session pin for an unpinned card. Sizing never silently fits the
canvas, so attention does not jump to another card. `Fit view` remains an
explicit action and uses a fixed maximum zoom.

Card sizing does not rerun the canonical radial search, but every effective
size delta does run a separate deterministic fourteen-pass convergence after
the new silhouettes exist. This includes a local toggle, the directional and
complete-path actions, a multi-target topic path, `All targets`, `All cards`,
undo, and redo. A direct card or path/topic anchor is fixed at the compensated
29%/50% pivot; bulk actions have no arbitrary fixed card and seed the force with
the complete changed set. All visible pairs near those seeds may repel below
the 72-model-pixel gap, and visible relation neighbors may attract only above
the 116-model-pixel comfortable gap. The current pan and zoom are preserved,
the pass count is fixed rather than animated to idle, and graphs above 240
visible nodes keep the size change without automatic convergence.

The canvas follows trackpad conventions: two-finger scrolling pans in both
axes and pinch input performs explicit pointer-centered zoom. Primary-button
dragging on empty canvas performs
box selection; every member receives a soft pale-green silhouette glow while
the single active/read node retains its moonlight-yellow cue. Dragging a
selected card body moves the entire selection by one common offset. On canvases
of at most 240 visible nodes, while a card or group is directly dragged, a
deterministic local force pass repels
nearby card silhouettes below the 72-model-pixel gap and weakly attracts
relation neighbors whose visible link gap exceeds 116 model pixels. The
dragged set is fixed, release performs at most fourteen settling passes, and then
motion stops. Card sizing uses the separate fixed fourteen-pass path described
above. Layer changes and idle frames do not run either path. Direct
dragging of an unselected card moves that card alone. The size toggle itself
never initiates a card drag. Touch and pen contact
pan rather than box-select. A manually moved card or group is pinned only in the
current page session; later sizing actions may replace an existing anchor pin
for pivot compensation and may pin only neighbors actually moved by the
post-size convergence. `Reset layout` clears all session pins. The Reload graph
button or ordinary browser refresh clears every runtime
size, history, selection, pin, and appearance choice while loading the latest
atomically replaced file.
There is no watcher, local storage, or graph writeback. There is also no
persistent visualization history or sidecar.

Node shape communicates reader role; pale fill plus a text badge communicates
the source plane; border style communicates current, research, challenged, or
inactive status. Semantic relations carry an enlarged category-colored marker
at the rendered midpoint and another at the target, so direction is repeated at
equal half-edge intervals without filling the line with visual noise. Solid,
dashed, and dotted patterns remain authoritative for relation styling, and
synthetic theme-grouping links remain dashed and arrowless while following
smooth Bezier curves rather than orthogonal taxi segments.
Faceted is the default appearance scheme and Plaques is the
alternative. The scheme changes node silhouettes only. It does not alter packet
`theme_order`, plane colors, status borders, edge categories or dash patterns,
selection, coordinates, card size, or sizing history, and it lasts only for the
current page session. Full-card role-specific text maximum widths are 106, 102,
98, and 92 model pixels, with horizontal margins 18, 18, 17, and 17 for target,
definition, result, and explanation cards, respectively. These paired measures
retain at least 8 model pixels of clearance from the shared size control and
keep the control-plus-label envelope within 3% of the card center at minimum,
canonical, and maximum supported zoom. Multiline labels on real cards are
left-justified inside the role-specific measure; synthetic theme labels remain
centered. Hovering the card body or its internal size control uses the same node
emphasis, so related edges stay bright and unrelated edges stay dim through the
internal boundary and restore only after the pointer leaves the whole card.
Plaques uses a bright outer plane/status stroke and a
lower-brightness inner ornamental stroke; selection changes the temporary outer
cue to moonlight while preserving the underlying semantic treatment. The right
panel opens with intuition, importance,
prerequisites, and reasoning route. Formal hypotheses, statement, proof,
relations, exact source, and provenance remain readable in folded sections.
TeX in `\\(...\\)` and `\\[...\\]` is rendered locally as SVG while the exact
source string remains copyable. Detail-panel MathJax containers use a `1.08em`
baseline, and their direct SVG children explicitly escape the global fixed-size
icon rule. Exact TeX source uses a `0.82em` monospace measure. Both therefore
inherit the panel's text scale instead of remaining visually frozen while prose
grows; oversized display equations scroll inside the panel.

UI controls, navigation, role labels, legends, and provenance labels switch as
one unit between Chinese and English, with Chinese as the default. The selected
language lasts for the current page session only. Packet titles and mathematical
body text remain in their source language. The detail panel's separator can be dragged or adjusted
with arrow keys between bounded widths; double-click resets its width. A range
control scales detail prose, rendered MathJax SVG, and exact TeX source from 90%
to 150%. Both settings are session-only and `Reset UI` restores their defaults.

The full-height graph stays in the center and readable selected-node detail
stays in a resizable right panel on wide screens. The flat dark forest palette
uses cyan for Fact, amber for Paper, violet for Audit, gray for Blackboard,
green for Learning, and teal for reader notes. Knowledge edges remain solid by
category, while every research-layer edge has an explicit dashed pattern;
repair and synthetic grouping relations also retain their specified dash
patterns. On narrow screens the detail panel moves below the graph without
changing graph order or packet meaning.

## Determinism and offline boundary

The renderer canonicalizes the validated JSON, embeds pinned Cytoscape.js
3.34.0, MathJax 3.2.2 `tex-svg`, and 15 selected Tabler Icons 3.45.0 SVG assets
whose generated sprite SHA-256 is
`2fc9b17bafe11e9866ae515ad9b6b06790c8ceabece75e5b9362d41320093e87`,
and derives canonical coordinates from target-distance radial rings,
packet-order seeds, and, for at most 1,200 scored edges, eight fixed circular
weighted-neighbor sweep pairs plus at most 48 adjacent ring-swap candidates
with exact best-so-far proper-crossing scoring.
That bounded search has deterministic tie breaks and no global-optimum claim;
larger graphs preserve packet order. It records no timestamp or random id. The
same semantic packet and same manifest-bound renderer assets therefore produce
identical HTML bytes.
Viewport size changes the final fit on screen but not the file or graph order.

The output contains no external script, stylesheet, image, font, or CDN link.
Its content-security policy denies network connections and workers. Standard
TeX/AMS math supported by the embedded bundle renders offline; unsupported
macros remain visible as source rather than triggering a network load.

## Failure and warning policy

Fail without writing when any node lacks a nonempty, non-whitespace `summary`,
`intuition`, `importance`, or `reasoning` field; when the packet is not strict
UTF-8 JSON, has duplicate keys, exceeds hard containment limits, mismatches the
project identity, contains duplicate/colliding ids, has dangling endpoints, has a prerequisite
cycle, contradicts explicit orders, breaks exact-text hashes, crosses plane
authority, or targets a symlinked/unsafe fixed output.

Audit warnings, historical warnings, and unresolved research issues do not by
themselves block this low-stakes export. Put them in the packet's `audit`
section so the page shows one concise warning with a folded complete list. A
warning never changes a node's native source or truth status.

PDF production is outside this feature. If the user later requests a PDF,
handle that conversion case by case from the generated page or another explicit
source without making Chalxius a PDF manager.
