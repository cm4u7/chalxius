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
placement is separate. It first computes the former target-distance radial
layout as a deterministic angular seed: packet order, eight fixed circular
neighbor-sweep pairs, at most 48 adjacent swaps, and the bounded angular
compaction remain available for this seed. It then creates one deterministic
local center per theme. Explicit `theme_id` remains the primary membership;
the renderer additionally derives presentation-only shared membership when a
node lies in the strong `prerequisite`/`support` upstream closure of targets
from another theme. Weak, `repair`, and `conflict` edges never create shared
membership. This derivation changes no packet field or source relation.

Each theme receives `ceil(member_count / 6)` local rings. Ring radii use current
card footprints and exact chord density, and every ring around one center has
the same centerline spacing. Within a local ring, seed angles determine cyclic
order and a deterministic circular mean determines phase. A one-theme node is
placed on its assigned local ring. A multi-theme node receives one assignment
per field and is placed deterministically in their geometric overlap; for two
intersecting assigned circles this is an exact circle intersection, while a
bounded symmetric solver supplies the deterministic compromise for higher-order
overlap. Synthetic multi-target theme cards sit at their theme centers.

The target-distance seed retains its no-worse-crossing and bounded-compaction
guarantees; those guarantees are not misreported as an optimization guarantee
for the final multi-center projection, whose crossing and clearance scores are
recorded only as diagnostics. Larger graphs preserve the same deterministic
theme projection. Neither phase rewrites semantic lists, topology, or packet
bytes, and later card sizing never reruns the angular search.

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

Packet v1 remains read-compatible with historical free-text titles. New V5
projections use `object kind · hash-prefix` titles bounded to 64 characters and
never copy a claim or TeX environment into that navigation field. On every
packet, the canvas and hover identity is derived from the first six lowercase
digits of `provenance.object_sha256` plus localized reader role and source
plane. Full statements, proofs, and exact TeX remain in the right panel.

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

Every theme also receives one or more dashed, color-coded local concentric
orbits around its own center. Orbit nodes are locked, ungrabbable, unselectable,
event-free presentation geometry. They
are excluded from packet-node and edge counts, search, box selection, collision
forces, provenance, and authority. Their short labels contain only the localized
words `Theme field` plus the `theme_order` ordinal on the innermost ring, so a
long theme label or TeX body
cannot become an oversized canvas label. The full theme label remains in its
reader detail.

Every currently eligible real packet node and every currently eligible packet
edge remains present on one continuing canvas. Minimization changes only a
card's visual size: it never hides a node, suppresses an edge, or changes graph
topology. The initial `All targets` sizing action keeps eligible targets full-
size and minimizes every eligible non-target card. `All cards` maximizes every
eligible real card, including isolated cards. These are sizing actions rather
than view modes; if every eligible node is a target, their resulting size states
may be identical. A compact floating dock also provides explicit `Fit view`,
layout reset, sizing undo/redo, appearance selection, optional-layer controls,
and a session-only orbit-gravity toggle. Orbit gravity defaults on.

Primary-button dragging from empty canvas draws a visible selection rectangle.
Every visible node whose rendered bounds overlap that rectangle joins the
selection; Shift, Option, Control, or Command preserves the existing set and
adds the new rectangle. Dragging any selected card body moves every selected
node by the same model-space offset, preserving their relative positions during
the gesture. With orbit gravity on, release records each real card's new
page-session angular anchor relative to every assigned theme center; damped
gravity then attracts it back to one local ring or balances it in the overlap
of multiple theme fields. A synthetic multi-target theme card or any card dragged
while orbit gravity is off keeps an ordinary page-session Cartesian pin.
During an orbit-off drag, the gesture set remains fixed, but an existing
Cartesian pin that actually enters the protected collision gap yields to
repulsion and atomically replaces its own pin with the displaced coordinate.
Unrelated pins stay fixed, pinned cards receive no attraction or radial tether,
and the solver creates no new pin.
Selection and movement do not alter packet topology, edge direction, semantic
order, source text, or authority. A background click clears the set. Direct
touch or pen contact pans the canvas instead of creating a selection rectangle.

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
Hover exposes the same compact hash/role/plane identity used by the canvas;
selecting opens the complete right-panel detail. The selected card retains a
vivid moonlight-yellow outline plus a
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
canonical position for every packet node. A bounded target-distance radial
search first supplies graph-aware seed angles. The final projection then assigns
one radius per theme in exact `theme_order`; all real cards with that `theme_id`
share the radius, while seed angle order and phase keep the initial result
deterministic. Synthetic multi-target theme nodes occupy the innermost core.
This search runs only for initial canonical placement and explicit `Reset
layout`, never for card sizing, sizing undo/redo, layer changes, or box
selection. Compact silhouettes collapse about the control pivot, and Cytoscape
reattaches each visible edge to the changed silhouette. Sizing derives one
two-axis model-position compensation for every changed card to keep that pivot
fixed. If the card has an ordinary Cartesian pin, the renderer also replaces
that existing pin; it never creates a session pin for an unpinned card. Sizing
never silently fits the canvas, so attention does not jump to another card.
`Fit view` remains an explicit action and uses a fixed maximum zoom.

Card sizing does not rerun the canonical angular search, but every effective
size delta recomputes safe orbit radii and starts a bounded 24-frame damped
convergence after the new silhouettes exist. This includes a local toggle, the
directional and complete-path actions, a multi-target topic path, `All targets`,
`All cards`, undo, and redo. A direct card or path/topic anchor is fixed at the
compensated 29%/50% pivot; bulk actions have no arbitrary fixed card and seed
the force with the complete changed set. The force neighborhood is the seed set
plus at most two visible graph hops and one immediate collision halo. At most
240 active neighborhood nodes move; all other visible nodes are still measured
as fixed collision and relation boundaries, so a large map does not lose local
response merely because its total visible-node count exceeds 240. Nearby
silhouettes repel below the 72-model-pixel gap, visible relation neighbors
attract only above the 116-model-pixel comfortable gap, and separate radial and
tangential springs retain every assigned local theme ring and per-center angular
anchor. Shared nodes average those bounded field forces and receive a weak
canonical overlap tether until the user gives them new page-session angles. The
current pan and zoom are preserved. Ordinary displays expose the bounded frames
as visible motion; `prefers-reduced-motion` executes the same bounded settlement
without animation. Neither path becomes an idle simulation.

The canvas follows trackpad conventions: two-finger scrolling pans in both
axes and pinch input performs explicit pointer-centered zoom. Primary-button
dragging on empty canvas box-selects; every member receives a soft pale-green
silhouette while the active/read node retains its moonlight cue. Dragging a
selected card moves only that selection by one common offset. Starting a drag
cancels any queued convergence. While the pointer moves, a two-frame rolling
local force lets nearby relation and collision neighbors respond without
destabilizing the whole map. On release, each real selected card records its
per-center release angles and becomes movable under the 24-frame multi-center
theme-field force; a
synthetic theme card remains an ordinary fixed pin. Only the bounded two-hop
plus immediate-collision neighborhood may settle, outside nodes remain fixed,
and force-moved unpinned neighbors acquire neither angular nor Cartesian pins.
With gravity off, a previously pinned card may yield only when it actually
collides with the current gesture anchor; its existing Cartesian pin is updated
to the repelled coordinate, while every unrelated pin remains fixed. Layer
changes and idle frames do not run the force. Direct dragging of an unselected
card makes that card the sole release seed. The size toggle itself never
initiates a card drag. Touch and pen contact pan rather than box-select. Turning
orbit gravity off hides the presentation rings and retains subsequent manual
positions as Cartesian pins; turning it back on converts real-card pins to
per-center angular anchors and attracts them to their assigned fields. `Reset layout` clears
both session pin forms. The Reload graph
button or ordinary browser refresh clears every runtime
size, history, selection, pin, and appearance choice while loading the latest
atomically replaced file.
There is no watcher, local storage, or graph writeback. There is also no
persistent visualization history or sidecar.

For V5 Fact nodes only, the readable summary is a deterministic presentation
projection rather than a second authority record. Native delimited TeX passes
through unchanged. Historical machine anchors become readable Claim,
Hypothesis, or Quantifier labels, and a bounded compatibility grammar adds TeX
delimiters only to unspaced ASCII tokens already carrying an explicit relation,
subscript, or superscript, plus a small legacy symbol set. The exact admitted
statement remains byte-for-byte in the formal/original fields and its hashes do
not change; the converter does not infer mathematics or rewrite a Fact.

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
TeX in `\\(...\\)`, `\\[...\\]`, `$...$`, `$$...$$`, and supported
`\\begin{...}` environments is rendered locally as SVG in the detail title,
readable sections, and formal sections while exact source remains copyable.
Escaped dollars remain literal. Detail-panel MathJax containers use a `1.08em`
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
and derives angular seeds from target-distance radial rings, packet order, and,
for at most 1,200 scored edges, eight fixed circular weighted-neighbor sweep
pairs plus at most 48 adjacent ring-swap candidates with exact best-so-far
proper-crossing scoring. It then deterministically projects those angles onto
the concentric radii fixed by `theme_order`, card footprints, and theme density.
That bounded seed search has deterministic tie breaks and no global-optimum
claim; larger graphs preserve packet order. It records no timestamp or random id. The
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
