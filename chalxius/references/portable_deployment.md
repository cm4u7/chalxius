# Chalxius portable deployment

The 0.4.0 release artifact contains one self-contained `chalxius` skill,
no live project, credentials, service dependency, bytecode, or symlink. Python
3.11+ is required. The Chalxius research engine is the only embedded research
kernel; retired predecessor, coordinator, and standalone companion skills are
not runtime dependencies.

## Verify a received candidate

```bash
SKILL_ROOT=/absolute/path/to/chalxius
cd "$SKILL_ROOT"
python3 -B /absolute/path/to/skill-creator/scripts/quick_validate.py "$SKILL_ROOT"
python3 -B scripts/self_test.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts \
  python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

If a separately authorized release archive contains `MANIFEST.sha256`, run
`shasum -a 256 -c MANIFEST.sha256` and reject unexpected files. Also verify
`INHERITANCE.lock.json` against the named source manifests. A workspace
candidate without a release manifest must not be represented as packaged.

## Initialize and route

```bash
MGRAPH="$SKILL_ROOT/scripts/mgraph"
PROJECT=/absolute/path/outside/the/skill
"$MGRAPH" --root "$PROJECT" --role operator init \
  --project-id PROBLEM_ID --title "TITLE" --reasoning-mode auto
"$MGRAPH" --root "$PROJECT" --role main mode-status
"$MGRAPH" --root "$PROJECT" --role main audit
```

`fast`, `auto`, and `deep` are Chalxius execution profiles. They never start
retired predecessor skills. The exact task-card `execution_profile` advises
whether the clean-context panel, durable two-wave pulse, Paper/Audit work,
computation lane, campaign expansion, novelty search, and expert synthesis are
`required`, `available`, or `not_applicable` for that research plan. The V5
Fact-admission contract is invariant in all modes; profile completion is not a
second truth or admission gate.

For a required panel, use all genuinely distinct currently callable
clean-context slots when carrying out that plan. For a required pulse, produce
actual plan, ingestion, barrier, trusted dispatch, cross-review, and closure
evidence. Each valid Pulse contribution enters cumulative Research
independently; a malformed peer is quarantined locally, and a whole-pulse abort
is reserved for an explicit stop of future dispatch. An available feature is
opt-in; an inapplicable feature is not manufactured. Estimated cost, duration,
burden, and score are priority/load ordering only and never weaken a V5
Candidate Release or Certification requirement.

Every new round freezes `profile_obligations` as repair guidance. After
canonical ingestion, `profile-closure-status` may identify incomplete planned
work, and `profile-closure-record` may append exact typed advice to cumulative
Research. Neither command is required before constructing a verifier capsule,
sealing a Candidate Release, recording a Certification Decision, or admitting
a Fact. Missing source, replay, adverse-disposition, atomic-DAG, convention,
quantifier, or fresh-verifier evidence still fails at its exact V5 gate.
Machine-native and procedural host evidence retain their distinct labels.

## Optional offline reader page

Only after an explicit visualization request, a main or operator may render a
validated English reader packet:

```bash
"$MGRAPH" --root "$PROJECT" --role main export-reader-html \
  --packet /absolute/path/to/reader-packet.json
```

The fixed output is `PROJECT/visualizations/knowledge-map.html`; each run first
completes Reader Finalize and then atomically replaces that one file. Every
included node must have nonempty summary, intuition, importance, and reasoning
content. The deterministic `reader_finalize` metadata is embedded in the page
build metadata and returned in stdout; it is presentation-readiness-only and
creates no sidecar or authority object. Cytoscape.js 3.34.0 and MathJax 3.2.2
`tex-svg` are manifest-bound inside the skill and embedded into the result, so
the page has no CDN or service dependency. The packet and page are
presentation-only with `truth_effect="none"`; they do not modify or certify any
graph plane. See [reader_html_export.md](reader_html_export.md).

Revision 12 retains revision 11's card minimization: the full minus and compact
plus occupy the same normalized 29%-width/50%-height internal anchor. Click-/
tap-/keyboard-only size toggles, card-body dragging, deterministic two-axis
pivot compensation with existing-pin replacement only, readable minimum
zoom, silhouette-following selection halo, lower-brightness Plaques inner
ornament, bounded 100-delta sizing undo/redo stack, manual positions, and
appearance choice exist only in the embedded page's current runtime. Full-card
labels use paired narrower role-specific measures and left-justified multiline
text so the internal control-plus-label envelope remains within 3% of card
center across supported zoom, without colliding with the control or silhouette.
Card-body and internal-control hover share one continuous related-edge emphasis;
unrelated edges return only after the pointer leaves the whole card. Browser
refresh and the bilingual
Reload graph button clear runtime state and load the current fixed file through
same-document navigation only. They require no watcher, polling, fetch loop,
service, persistent history, sidecar, local-storage record, packet field, graph
topology change, or graph writeback.

Revision 12 additionally lets detail-panel MathJax SVG and exact TeX source
follow the existing 90%-150% text scale. Synthetic multi-target theme links are
smooth, dashed, arrowless Bezier curves; double-clicking a theme applies one
atomic size operation to the union of the directed upstream and downstream
closures of its eligible member targets. Initial placement and explicit layout
reset use packet order as the baseline. For at most 1,200 cross-rank edges, they
search eight fixed forward/backward weighted-barycentric sweep pairs, exactly
count proper crossings after every half-sweep, and retain the best-so-far order.
The result therefore has no more proper crossings than packet order. Above that
bound the quadratic comparison is skipped and packet order is preserved. This
deterministic bounded search does not claim a global optimum, and ordinary card
sizing, undo/redo, or layer changes do not rerun it or reorder the working view.
This paragraph states the deployment boundary only; it is not renderer,
browser, determinism, packaging, or release QA evidence.

Revision 13 replaces ranked columns with deterministic target-distance radial
core layers: synthetic multi-target themes occupy the innermost core, targets
occupy the next central ring, and other nodes move outward by undirected graph
distance from the target set. Packet order seeds each ring; eight circular
neighbor sweeps and at most 48 adjacent ring-swap candidates across two
refinement passes keep a candidate only when its exact scored radial crossing
tuple improves. Exact chord-based radii plus bounded deterministic weighted-link
attraction, same-ring repulsion, and seed tethering shorten maximum and total
edge length only if crossings, card collisions, and the protected 44-model-
pixel connected-card boundary gap do not worsen. Primary-button dragging on empty canvas draws a visible
selection rectangle, modifier-drag adds nodes, and dragging any selected card
moves the whole set by one equal offset. Box-selected nodes receive a soft green
silhouette glow. For at most 240 visible nodes, direct drag runs bounded local
card repulsion and relation-only attraction, then stops after at most fourteen
release-settling passes. These
positions are session pins only.
Two-finger gestures still pan programmatically, while touch and pen pan directly.
No selection, movement, or layout state enters the packet, Fact graph, source,
sidecar, storage, or writeback path.

Revision 14 repairs two presentation regressions without changing that boundary.
Canonical reset geometry now chooses role-specific full or minimized card
footprints from the current sizing state; `All cards` therefore cannot be laid
out using compact-card assumptions. The protected connected-card boundary gap
is 72 model pixels, with a fixed ring-spacing safety margin. Pinch input is
handled explicitly as pointer-centered zoom, while ordinary two-finger input
continues to pan. These changes remain inside the generated page and create no
packet, graph, source, storage, sidecar, service, or writeback state.

Revision 15 adds post-size convergence without changing the canonical-layout
contract. Every effective local, path, topic, global, undo, or redo size delta
runs exactly fourteen deterministic force passes against the new rendered
silhouettes. Directly operated cards or topics remain fixed at their compensated
control pivot; bulk actions use all changed real cards as seeds. Nearby visible
cards repel below the 72-model-pixel gap and visible relation neighbors attract
only above the 116-model-pixel comfortable gap. The viewport is preserved, fit
remains explicit, motion stops after the bounded call, and graphs above 240
visible nodes retain the size action without automatic settling. This creates
only page-session presentation pins and no packet, graph, source, storage,
sidecar, service, or writeback state.

## Historical projects

V5 never activates a V1-V4 root or upgrades its authority through `mode-init`.
Keep every historical project unchanged and readable as nontruth background.
Start substantive V5 work in a separate nonnested root; it begins with an empty
V5 Fact Graph and accepts no predecessor Fact, review, receipt, closure, or
admission marker as V5 authority.

Historical inspection and copy-upgrade commands remain rollback-lineage tools
for reading old bytes. They must not be presented as a path that turns a V1-V4
root into a V5 project. If the user explicitly requests background generation,
read the relevant historical project files broadly and write one
`PROJECT_BACKGROUND.md` in the new V5 root. Once that file exists, substantive
V5 work reads its complete body and hash by default; absence never generates
it, and no summary has truth effect.

Old rounds and `profile_obligations` remain audit-readable but are not V5 work
units. Do not backfill a closure receipt or import their assurance. The internal
Python `reasoning_mode=None` seam exists only for frozen compatibility tests;
official V5 initialization defaults to `auto`.

No public constructor accepts an `allow_legacy_*` write switch. Private
identity-token fixture and staged-copy seams exist for tests and isolated
migration only. Their underscore naming and unexported tokens express a
cooperative in-process contract; they are not authentication and do not defend
against hostile reflection or direct filesystem mutation.

Read APIs do not heal state. Missing statement interfaces can be reconstructed
with `materialize=False` without writing; the default materializing form is a
guarded mutation. Blackboard dry-run reindex and experiment status/resume
validation do not create the advisory lock or rebuild derived caches.

Retired predecessor writers are rollback tools only and must not open the
unified writable root. The integrated learning plane, Chalxius Learner, is an
opt-in static nontruth consumer, not another runtime. Standalone Grill Me
0.3.2-code, distinguished as Grill Me Code, is a globally injected programming
companion whose semantic activation still requires explicit programming Grill
or Socratic intent; it has no graph mount and is not a Chalxius dependency.
Neither optional interaction surface starts for ordinary research or ordinary coding. Cross-project, cross-machine, and
multi-root federation remains disabled.

## Host handoff

Tell the receiving host to read `SKILL.md`, verify the candidate, choose an
external project root, select a reasoning mode, and report mode event, repair
advice, audit state, and Candidate Release/Certification/Fact boundary. Installation,
global replacement, packaging, migration, and cutover each require separate
explicit authorization.
