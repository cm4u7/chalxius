# Pre-Chalxius capability difference audit

## Audit question

Could using the pre-Chalxius `mathgraph-chalk-version` 0.4.0 codebase as the
only implementation base silently lose a Danus certification or
source-reliability capability?

## Source comparison result

The installed `run-multi-agent-mathgraph` 0.2.12 and `mathgraph-chalk-version`
0.4.0-chalk packages were compared before integration.

- `scripts/mathgraph/applicability.py`, `elementary.py`, `graph.py`, and
  `search.py` are byte-identical. The core external applicability, elementary
  exemption, graph, and search logic therefore needs no Danus transplant.
- The pre-Chalxius V4 codebase provided the higher-assurance capabilities relevant
  here: Paper Logic and correctable Audit Graphs, source-bound claims and
  quantifiers, immutable
  Blackboard snapshots and pulses, experiment replay, atomic fact bundles,
  verifier capsules, expert/interpretation lint, hard caps, and current/history
  audit projections.
- The Stable package contains a later guard that prevents the old engine from
  writing into a V4-root. That is an isolation patch for the legacy runtime, not
  an admission capability. Importing it would reintroduce a second-engine
  assumption and is intentionally excluded.

## Integration decision

No Danus runtime or V3 protocol code is copied. Danus remains a behavioral
latency reference and frozen fact-import source. All new research and all new
facts use the Chalxius research engine and invariant Fact admission contract.
This avoids two certification paths and makes parity a contract invariant
rather than a router promise.

The embedded learning algorithm is copied from Grill Me 0.2.0 only because its
static hash-bound overlay is the desired teaching data structure. Its academic
workflow, CLI, and docs are now the opt-in Chalxius nontruth learning plane,
publicly named Chalxius Learner;
algorithm reuse does not imply a Danus or Grill runtime dependency. Standalone
Grill Me 0.3.2-code, distinguished as Grill Me Code, is globally injected for
natural-language routing but semantically limited to explicitly requested
programming Grill or Socratic assistance and contains no
graph adapter, teaching ledger, or MathGraph protocol.

The 0.3.x integration added a V4 closure layer that neither legacy package had.
Historical cards and rounds retain exact `execution_profile` and
`profile_obligations` bytes. Current V5 cards do not freeze those V4 fields.
Instead, `profile-closure-status` and `profile-closure-record` are adapters for
local process repair advice. A record is appended to cumulative Research with
`truth_effect="none"`; it is not required before a verifier capsule, Candidate
Release, Certification Decision, or Fact admission. The standalone
`adoption-plan` remains callable, while automatic V5 attachment of all its
recommendations is a dormant legacy coupling pending an explicit decision.

Evidence assurance is intentionally heterogeneous. Native graph, pulse,
experiment, novelty, projection, and lint validators can establish their own
machine-checkable properties. Host capacity, true context orthogonality,
campaign-scope meaning, and expert-synthesis subject linkage remain procedural
attestations; mixed features say so. This prevents the new router from claiming
that orchestration facts have mathematical certification.

The deterministic reader-HTML export in candidate 0.3.0 is a new communication
surface, not a recovered Danus certification feature. It consumes an explicit
nontruth packet and preserves native plane/status labels, exact original text,
source hashes, and human order. It neither replaces Chalxius expert-lint paths
nor introduces another graph, verifier, writer, admission route, learner, or
runtime. Renderer revision 2 changes only the reader presentation: a flat
dark-navy shell, left control rail, fixed right detail panel, responsive
fallback, and vendored Tabler controls. It does not change packet validation,
truth authority, ordering, or graph persistence. `export-mermaid` remains
unchanged for its narrow Fact-only use.

Renderer revision 7 is likewise presentation-only. It keeps every eligible
packet node and edge on one canvas, replaces relation-disclosure state with
global visual card minimization, adds bounded session-only sizing undo/redo,
uses double-click for atomic directed upstream/downstream path maximization, and
offers Faceted and Plaques appearance schemes. None of those runtime states
enters the packet schema, source snapshots, graph planes, truth authority,
ordering, admission, or writeback path. Revision-7 implementation is present;
the focused reader suite passed 18/18, the full suite passed 419/419, the
self-test passed, and the browser/design audit passed. Deterministic official
export hashing, final manifest freeze, packaging, and installation remain
separate release gates, so no release PASS is claimed at this checkpoint.

Renderer revision 8 remains presentation-only. It repairs direct dragging from
the minimized plus control, gives both size states one stable internal control
anchor, replaces the rectangular selection underlay with a pointer-transparent
role-silhouette halo, and separates the Plaques outer semantic stroke from a
lower-brightness inner ornament. Interrupted mouse drags now terminate on lost
button state, window blur, or page hiding, and a readability-bounded minimum
zoom keeps the internal control available. These changes do not alter packet validation,
source text, graph topology, semantic ordering, plane/status authority, Fact
admission, persistence, or writeback. The focused reader suite passed 19/19,
the complete inherited suite passed 420/420, browser/design QA passed, and two
official exports matched at SHA-256
`8470662cba79d7aa4e7ad9398ca7446e546652a20ccb2219ad59070150becf91`.
Manifest, cold-package, and installed-tree checks remain separate release
gates, and none of these checks promotes presentation reliability to graph or
mathematical truth.

Renderer revision 9 remains presentation-only and supersedes revision 8 only
for size-control interaction and geometry. The full-card minus occupies the
left inner edge, the compact silhouette collapses about that fixed control
pivot, and the replacement plus retains the same rendered coordinate. The size
button is click-, tap-, and keyboard-only; direct dragging remains available
from the card body. Every resized card receives deterministic horizontal pivot
compensation. An existing session pin is replaced when present, while an
unpinned card never acquires a pin from sizing. This patch also enlarges
category-colored relation markers and repeats each semantic
direction cue at the edge midpoint and target; synthetic grouping links remain
arrowless and all dash semantics are unchanged. It does not alter the reader
packet, graph topology, eligible edges, source text,
semantic ordering, plane/status authority, Fact admission, persistence, or
writeback. Renderer, browser, determinism, manifest, package, and installed-tree
results remain separate release gates, so no revision-9 release PASS is claimed
at this documentation checkpoint.

The final revision-9 candidate subsequently passed 19/19 focused reader tests,
420/420 inherited tests, self-test, syntax/parsing checks, official Skill
Creator validation, responsive and interaction browser QA, same-state combined
design inspection, and byte-identical double export at SHA-256
`ed1b79129f0aad28dfaf5fa7090ed839e01bd09ac222afc8585a2883996ee362`.
Manifest, cold-package, and installed-tree verification remain separate gates.

Renderer revision 10 is the frozen 0.3.3 candidate contract and remains
presentation-only. Reader Finalize strengthens the existing
`export-reader-html` validation stage: every included node must provide
nonempty summary, intuition, importance, and reasoning content before the fixed
HTML can be atomically replaced. Its deterministic metadata binds the source
snapshot, canonical packet hash, node count, and complete-sidebar count; it is
embedded in page build metadata and returned in stdout with
`scope="presentation_readiness_only"` and `truth_effect="none"`. It is not a
new graph, durable receipt, research-readiness claim, or Fact-admission gate.

The page adds a bilingual Reload graph control that invokes same-document
navigation only. It introduces no watcher, fetch/poll loop, network runtime,
storage, sidecar, service, or source writeback. Full and compact cards now share
one normalized control anchor at 29% of rendered width and 50% of rendered
height; resizing derives compensation on both model axes so the control does
not jump. Role-specific label margins move full-card text left while preserving
control and silhouette clearance. The final candidate passed 24/24 focused
reader tests, 425/425 inherited tests, self-test, syntax/parsing checks, lock
checks, official Skill Creator validation, responsive and interaction browser
QA, combined source inspection, and byte-identical double export at SHA-256
`f7382e9d62a9f68acf6754d37eb698e205b97dd600ee66f4fb2d530fca02e87b`.
The frozen candidate manifest binds these exact non-cache bytes. Cold packaging,
installation, and post-cutover checks remain separate external gates; revision-
10 presentation readiness does not certify graph or mathematical correctness,
and all revision-9 evidence above remains historical evidence for its exact
installed bytes.

Renderer revision 11 is the frozen 0.3.4 presentation-only contract. It pairs
narrower role-specific real-card text widths and margins with left-justified
multiline labels, retaining at least 8 model pixels of control clearance while
bounding the control-plus-label envelope to 3% of card center across supported
zoom. Card-body and internal-control hover now share one node-emphasis state,
preventing an internal-boundary restore or flicker. It otherwise preserves
revision 10 node sizes, the normalized size-control anchor, deterministic pivot
compensation, packet validation, graph topology, source text, and all authority
boundaries. Synthetic theme labels remain centered. Release and
installation evidence remain separate gates. The final candidate passed 24/24
focused reader tests, 425/425 inherited tests, self-test, syntax/parsing and lock
checks, official Skill Creator validation, bilingual responsive browser QA,
combined source inspection, and byte-identical double export at SHA-256
`efa87e99ff184f51eea286acd5305109c3e842d1045c72dac8f41da4bab2a2bb`.

Renderer revision 12 is the frozen 0.3.5 presentation-only release. Detail-
panel MathJax SVG escapes the global icon-size rule, uses an `em`-relative
baseline, and therefore grows and shrinks with the existing 90%-150% detail-
text control; exact TeX source is likewise sized relative to the panel rather
than frozen at a root-relative value. Synthetic multi-target theme links are
now smooth, dashed, arrowless Bezier curves. Double-clicking such a theme
performs one atomic sizing action over the union of the complete directed
upstream and downstream closures of its currently eligible member targets,
then minimizes the eligible complement; it does not create a focus mode or
change topology.

The canonical layout now seeds each prerequisite rank from explicit packet
order. When the packet has at most 1,200 cross-rank edges, it applies eight
fixed forward/backward weighted-barycentric sweep pairs within ranks and scores
the baseline plus every intermediate order by an exact pairwise count of proper
edge crossings. Prerequisite and support relations receive greater heuristic
weight than repair or conflict relations; weighted crossing penalty and packet-
order displacement break equal-crossing ties. Because packet order is the
initial best-so-far and a candidate replaces it only when the score improves,
the selected order is guaranteed to have no more proper crossings than that
baseline. Packets above the 1,200-edge bound skip the quadratic comparison and
retain packet order. The bounded search is deterministic but does not claim a
global minimum. It runs only for initial canonical placement and explicit
layout reset, so card sizing, undo/redo, and layer changes do not silently
reorder the working view. These changes do not modify packet authority,
semantic order lists, graph topology, source text, Fact admission, persistence,
or writeback. Focused tests, the full suite, browser QA, deterministic export,
manifest freeze, packaging, installation, and post-cutover checks remain
separate release gates; no revision-12 validation or release PASS is claimed at
this documentation checkpoint.

Renderer revision 13 introduced the 0.3.6 presentation-only candidate. It
replaces directional ranked columns with deterministic target-distance radial
core layers: synthetic multi-target themes occupy the innermost core, targets
occupy the next central ring, and other nodes move outward by undirected graph
distance from the target set. Packet order seeds every ring, and the bounded
crossing search evaluates eight circular neighbor sweeps and at most 48
adjacent ring swaps across two refinement passes, accepting a candidate only
when its exact scored radial crossing tuple improves on the best-so-far order.
Exact chord-based radii and a second bounded deterministic relaxation then
shorten maximum and total link length while refusing any increase in crossings,
card collisions, or protected 44-model-pixel boundary-clearance violations.
It also adds a visible custom
primary-drag selection rectangle and session-only group movement: dragging one
selected card applies the same offset to every selected node and preserves
their relative coordinates. Every box-selected node receives a soft green
silhouette glow while the active node remains moonlight yellow. For at most 240
visible nodes, direct drag also runs bounded local repulsion below the protected card gap and weak
relation-only attraction above a comfortable visible-link gap; release settles
for at most fourteen passes and leaves no idle simulation. Programmatic
two-finger panning and direct
touch/pen panning remain separate from mouse box selection. These changes do
not modify packet bytes, semantic orders, topology, sources, plane/status
authority, Fact admission, persistence, or writeback. Validation, packaging,
installation, and publication remain separate gates, so this checkpoint does
not claim a 0.3.6 release PASS.

Renderer revision 14 remains presentation-only and corrects reset-layout
geometry plus trackpad pinch handling. Reset now scores and spaces the actual
current full/minimized silhouette of each role instead of assuming that every
non-target is compact. The canonical connected-card boundary floor rises from
44 to 72 model pixels and ring construction carries a fixed safety margin, so
fully expanded cards do not compress and short relations remain visibly
directional. Control-wheel pinch input now performs explicit pointer-centered
zoom; ordinary wheel input keeps two-axis pan. These changes do not alter
packet bytes, graph topology, semantic order, sources, authority, admission,
persistence, or writeback. Release and installation evidence remain separate
gates.

Renderer revision 15 remains presentation-only and closes the live sizing gap
left by revision 14. After any effective card-size delta—including local,
directional, complete-path, topic-path, global, undo, and redo actions—the
renderer evaluates exactly fourteen deterministic spacing passes using the new
rendered silhouettes. The direct anchor remains fixed at its normalized control
pivot; global changes seed the whole changed set without choosing an arbitrary
focus. Repulsion clears local compression below the protected boundary gap and
relation-only attraction limits unnecessary separation. Browser QA verified
zero control-center displacement through repeated maximize/minimize, fourteen
executed passes for direct, bulk, undo, and redo actions, and an empty
warning/error log. This does not alter packet bytes, graph topology, semantic
order, sources, authority, admission, persistence, or writeback. Release and
installation evidence remain separate gates.

Renderer revision 16 remains presentation-only and closes the identity and
stability gaps exposed by a 109-node V5 export. Direct dragging no longer runs
the bounded size solver: it cancels queued work and moves/pins only the dragged
set. Canvas and hover text use hash6 plus localized role/plane, new V5 titles are
bounded and content-free, and complete mathematical content remains in the
right panel. That panel now typesets its title and recognizes parenthesis,
bracket, dollar, double-dollar, and supported environment TeX. Packet v1 stays
read-compatible; no source, topology, authority, admission, persistence,
service, or writeback capability changes.

Renderer revision 17 remains presentation-only and joins the two previously
separate stability strategies without restoring an unconstrained force graph.
On drag release, selected cards remain fixed session anchors; graph distance
expands one force neighborhood to at most two hops, immediate collisions join
one bounded halo, and every outside node is a fixed boundary. Participating
nodes combine visible-edge attraction and silhouette repulsion with separate
radial and tangential springs to their canonical compact-ring coordinates.
The same fourteen-pass ceiling applies and there is no idle simulation.
Revision 17 also gives V5 Fact summaries a conservative compatibility
projection: machine interface anchors become readable labels, native TeX stays
unchanged, and delimiter-free historical tokens carrying explicit relation,
subscript, or superscript syntax become MathJax input. Exact formal/original
Fact text and hashes are untouched. Packet bytes, topology, semantic ordering,
truth authority, admission, persistence, services, and writeback remain
unchanged.

Chalxius 0.4.1 adds only a CHX runtime ledger and its mandatory
start/close reporting procedure. CHX-057 identified that 0.4.0 could finish a
run without a task-scoped causal architecture account or a silent-zero rule.
Project-bound ledgers now live in the isolated `PROJECT/chx-ledgers/`
operational directory; projectless ledgers remain in external host state. This
directory is outside all truth/nontruth authority planes and ignored by project
audit. The protected mathematical runtime and Reader dependencies remain
byte-identical to 0.4.0; project schemas and Fact admission are unchanged. The
activation boundary is prospective, so no already-running 0.4.0 task is
backfilled, reclassified, invalidated, or made to repeat work.

The 0.4.2 adverse-routing candidate is deliberately not folded into the
0.4.1 protected-runtime claim. It adds a new optional project-local
orchestration capability and therefore uses a new candidate version. The
extension is absent until an operator explicitly enables it. An old project,
round, task card, or return that lacks the activation contract follows the
0.4.0/0.4.1 code path and schema unchanged.

The worker may autonomously abstract a counterexample into a route proposal,
but that proposal has no activation authority. The user-facing outcome is
preserved through a separate attack report and three operator decisions:
approve, approve after supplying a complete modified rule, or reject. Approved
rules are content-addressed, project-local, limited to future refutation task
cards, and independently disableable. This design avoids a mutable self-prompt,
unreviewed global learning, a second verifier, and any route from exploration
to Fact authority.

The extension does not auto-start Chalxius Learner, does not use Grill Me Code,
does not change `fast`/`auto`/`deep`, and does not alter Candidate Release,
Certification Decision, gateway admission, Reader, Paper/Audit, Blackboard,
computation, or CHX-ledger semantics. Attack reports and CHX reports remain
separate nontruth surfaces.

The prospective 0.4.3 candidate repairs CHX-058 through CHX-075 without
rewriting frozen work. It adds a complete verifier-decision template,
standalone field-level decision preflight, neutral V5 capsule materialization,
artifact-bound Research obligations, current source-evidence v4, typed
formula/topology/contour/structure assurance, conditional and geometric-stage
interfaces, and proof-lineage conservation. Historical 0.4.2 cards, returns,
releases, decisions, and source-evidence v3 remain readable under their exact
recorded contracts.

The V5 automatic frontier is reconnected prospectively to the compact
four-factor ordering and read-time projection of historical eight-metric
Research. Scores remain ordering-only with no eligibility cutoff. In an
adverse-routing-enabled project, actual computation stages may queue one
future nontruth program-math review with an additional scoped attack rule;
ordinary refutation cards still receive exactly the original eight rules.
Architecture issues are expressly forbidden from that route and remain CHX
ledger material only.

The prospective 0.4.4 successor restores only the user-approved L1 and L2
connections. L1 turns one promoted Blackboard item's exact bounded query into
one new snapshot-bound task with complete origin lineage. L2 accepts only exact
mode enum tokens and automatically applies one only when its assurance,
adverse-task capability, and later program-math review signature equals the
kind-derived default. Main compiles the receipt, Operator governs and may
explicitly override, and the technical Host retains its exact 0.4.3 dispatch
capability set.

The same successor turns `PROJECT_BACKGROUND.md` into a low-priority indexed
context source for new task cards. The full source remains an immutable
round-local byte snapshot and every chunk is retrievable, but the body no
longer occupies active task-card context. Historical full-body cards remain
unchanged, and neither background nor context selection receives truth or
admission authority.

The later field report
`run-20260729T081913970946Z-2f0a9e345447/CHX-001` exposed a control-plane
projection gap rather than an abort-authority failure: a valid work-unit abort
still blocked continuation, while status showed unfinished assignments as
awaiting and audit remained silent. The successor now reads the same immutable
abort authority into status, uses `frozen_aborted`, reports zero live awaiting
returns and the exact abort id, and makes strict audit reject any mismatch. It
does not rewrite the abort, task cards, returns, Research, or Facts.

## Residual risks to test

- deterministic auto triggers may need calibration against real workloads;
- a feature marked required must be matched to native closure evidence rather
  than accepted from prose;
- previous-round campaign or novelty events, superseded Paper snapshots, stale
  Audit bases, sibling artifact paths, and unrelated pulse commitments must not
  close current work;
- accepted-idempotent retries and audits must fail after closure-evidence drift;
- legacy Danus import must preserve assurance without silently recertifying;
- every pre-V5 project must remain readable and read-only as nontruth lineage;
  neither `mode-init` nor copy-upgrade grants V5 authority;
- learning writes must never appear in research audits or Fact admission.
- ordinary research must not auto-start Chalxius Learner, and global product
  availability must not cause ordinary coding to auto-start Grill Me Code.
- reader-packet normalization must not alter formulas, quantifiers, hypotheses,
  negations, exact relation direction, or source authority;
- vendored rendering code and the generated page must remain deterministic,
  offline, self-contained, and presentation-only;
- fixed overwrite must never create a persistent visualization history,
  sidecar, or local-storage record, and must never follow a symlink outside the
  selected project; the bounded in-memory sizing history must disappear on
  refresh.
- Reader Finalize must fail before replacement for missing or whitespace-only
  sidebar fields, and a failed refresh candidate must leave the previous fixed
  HTML byte-identical and reloadable;
- the Reload graph control must remain navigation-only and must not grow into a
  watcher, network request, storage surface, or background synchronization path.
