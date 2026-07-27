# Stable/Chalk capability difference audit

## Audit question

Could using Chalk 0.4 as the only implementation base silently lose a Danus
certification or source-reliability capability?

## Source comparison result

The installed `run-multi-agent-mathgraph` 0.2.12 and `mathgraph-chalk-version`
0.4.0-chalk packages were compared before integration.

- `scripts/mathgraph/applicability.py`, `elementary.py`, `graph.py`, and
  `search.py` are byte-identical. The core external applicability, elementary
  exemption, graph, and search logic therefore needs no Danus transplant.
- Chalk V4 adds the higher-assurance capabilities relevant here: Paper Logic and
  correctable Audit Graphs, source-bound claims and quantifiers, immutable
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
facts use Chalk V4. This avoids two certification paths and makes parity a
contract invariant rather than a router promise.

The embedded learning algorithm is copied from Grill Me 0.2.0 only because its
static hash-bound overlay is the desired teaching data structure. Its academic
workflow, CLI, and docs are now the opt-in Chalxius nontruth learning plane,
publicly named Chalxius Learner;
algorithm reuse does not imply a Danus or Grill runtime dependency. Standalone
Grill Me 0.3.2-code, distinguished as Grill Me Code, is globally injected for
natural-language routing but semantically limited to explicitly requested
programming Grill or Socratic assistance and contains no
graph adapter, teaching ledger, or MathGraph protocol.

The integration adds a closure layer that neither legacy package had. A round
freezes exact `profile_obligations`; required high-cost features then need a
content-addressed `profile-closure` receipt bound to every assignment's exact
task, return, ingestion, outcome, and effect before verification/admission. The
receipt is explicitly `workflow_readiness_only` and outside the invariant Fact
contract, so it closes the execution-routing gap without creating a second
certification path or changing the common Fact-contract hash.

Evidence assurance is intentionally heterogeneous. Native graph, pulse,
experiment, novelty, projection, and lint validators can establish their own
machine-checkable properties. Host capacity, true context orthogonality,
campaign-scope meaning, and expert-synthesis subject linkage remain procedural
attestations; mixed features say so. This prevents the new router from claiming
that orchestration facts have Chalk-level mathematical certification.

The deterministic reader-HTML export in candidate 0.3.0 is a new communication
surface, not a recovered Danus certification feature. It consumes an explicit
nontruth packet and preserves native plane/status labels, exact original text,
source hashes, and human order. It neither replaces Chalk's expert-lint paths
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

Renderer revision 11 is the current 0.3.4 presentation-only candidate. It pairs
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

## Residual risks to test

- deterministic auto triggers may need calibration against real workloads;
- a feature marked required must be matched to native closure evidence rather
  than accepted from prose;
- previous-round campaign or novelty events, superseded Paper snapshots, stale
  Audit bases, sibling artifact paths, and unrelated pulse commitments must not
  close current work;
- accepted-idempotent retries and audits must fail after closure-evidence drift;
- legacy Danus import must preserve assurance without silently recertifying;
- old Chalk V4 projects must remain read-only until explicit `mode-init`, and
  V1-V3 must remain read-only until isolated copy upgrade;
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
