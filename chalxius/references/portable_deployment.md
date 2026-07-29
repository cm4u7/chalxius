# Chalxius portable deployment

The 0.4.4 `Back to the Future` candidate or release artifact contains one self-contained `chalxius`
skill,
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

## Start and finish the CHX ledger

For every run begun after the 0.4.1 activation boundary, start exactly one
task-scoped CHX ledger before substantive work, using
`scripts/chx_ledger.py start`. For project-bound work, store it at
`PROJECT/chx-ledgers/`; for projectless work, use private host task state outside
the skill. This operational file has no project-audit or truth effect. Close it
after applicable audits and immediately before final reporting. Report it only when close returns
`report_required=true`; when false, emit no ledger message at all. See
`chx_runtime_ledger.md` for the exact commands and causal schema.

This requirement is prospective. A task already running under 0.4.0 keeps its
original status even if the installed skill changes or it loads some 0.4.1-or-later
bytes. Do not backfill its ledger, recertify it, mark it noncompliant, invalidate
its work, or request a redo.

## Enable Attack reports prospectively

Global installation makes the adverse-routing commands available but does not
write to or activate any project. When the user has given an explicit
host-wide prospective authorization, the operator may consume that
authorization at the start of each future V5 work unit by enabling the
project-local extension before planning a new round:

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-enable \
  --actor USER --reason "Enable prospective user-governed Attack reports."
"$MGRAPH" --root "$PROJECT" --role main attack-route-status
```

Do not enable it in V1-V4 roots, in the middle of a frozen work unit, or merely
to modernize an old project. Never backfill attack cases, change an old return
schema, invalidate prior work, or request a redo. A V5 project already in use
may consume the authorization only when its next new work unit begins; every
previously frozen task card remains byte-for-byte under its original contract.

For every enabled host task, produce the separate report even when it has zero
cases:

```bash
"$MGRAPH" --root "$PROJECT" --role main attack-report \
  --host-task-scope-id HOST_TASK_SCOPE_ID
```

The report contains worker-reported nontruth attack cases and pending route
proposals. Only the operator may approve, approve after supplying a modified
rule, reject, or disable. Decisions affect future task cards only. Attack
reports never become CHX architecture reports or Fact evidence.

## Initialize and route

```bash
MGRAPH="$SKILL_ROOT/scripts/mgraph"
PROJECT=/absolute/path/outside/the/skill
"$MGRAPH" --root "$PROJECT" --role operator init \
  --project-id PROBLEM_ID --title "TITLE" --reasoning-mode auto
"$MGRAPH" --root "$PROJECT" --role main mode-status
"$MGRAPH" --root "$PROJECT" --role main audit
```

`fast`, `auto`, and `deep` are Chalxius reasoning profiles. They never start
retired predecessor skills. A current V5 task card freezes the exact mode-event
binding and its prospective `assurance_contract`; it does not contain the V4
`execution_profile` or `profile_obligations` fields. The standalone
`adoption-plan` command can still advise whether a clean-context panel, Pulse,
Paper/Audit work, computation, campaigns, novelty search, or expert synthesis
would be useful. Automatic attachment of that legacy plan to V5 rounds is not
enabled. The Fact-admission contract is invariant in all modes.

When the operator adopts that advice, use genuinely distinct callable contexts
for a panel and produce actual plan, ingestion, barrier, trusted dispatch,
cross-review, and closure evidence for a Pulse. Each valid Pulse contribution
enters cumulative Research independently; a malformed peer is quarantined
locally. Estimated cost, duration, burden, and score remain priority/load
ordering only and never weaken a V5 Candidate Release or Certification
requirement.

After canonical ingestion, V5 `profile-closure-status` computes local process
repair advice from current round, release, decision, and admission state;
`profile-closure-record` may append that advice to cumulative Research. It does
not reconstruct or pretend to freeze the V4 profile fields. Neither command is
required before constructing a verifier capsule, sealing a Candidate Release,
recording a Certification Decision, or admitting a Fact. Missing source,
replay, adverse-disposition, atomic-DAG, convention, quantifier, or fresh-
verifier evidence still fails at its exact V5 gate.

The automatic V5 frontier uses the compact four-factor score and projects
legacy eight-metric Research without rewriting it. It is an ordering aid only,
has no cutoff, and does not prevent explicit scheduling of a low-scored item.

For new 0.4.4 work, Main compiles task context and Operator retains governance;
the technical Host role remains the unchanged trusted dispatch adapter. One
origin-bound promoted Blackboard item may seed its exact bounded query as one
task. Exact enum mode hints apply only across an equal assurance/adverse
signature; explicit `--mode` remains the user override.

When an explicitly maintained `PROJECT_BACKGROUND.md` exists, inspect its
complete index and optionally commit exact chunks into a new card:

```bash
"$MGRAPH" --root "$PROJECT" --role main project-background-index
"$MGRAPH" --root "$PROJECT" --role main plan-round --workers 1 \
  --memory-id RESEARCH_ID --background-chunk-id BGC_ID
"$MGRAPH" --root "$PROJECT" --role worker project-background-read BGC_ID \
  --task-card rounds/ROUND/task-cards/ASSIGNMENT.json
```

The card freezes the complete index and exact round-local source snapshot; it
does not embed the background body. After context compaction, reread the card
and retrieve required chunks again. Never refresh the source automatically.

For a current computation-bearing task card, each stage must bind formula,
domain, representation, approximation or truncation budget, output meaning,
and independent checks. In an adverse-routing-enabled project, successful
ingestion queues a nontruth future refutation review only when exact executable
source and output artifacts are present. Ordinary challenges keep the eight
baseline rules; the program-math rule is scoped to that generated review.

Materialize a V5 verifier capsule into an absent directory or an existing empty
directory with mode `0700`:

```bash
python3 -B "$SKILL_ROOT/scripts/prepare_verifier_capsule.py" \
  --project-root "$PROJECT" --release-id RELEASE_ID \
  --capsule-root /absolute/external/verifier-capsule
```

The materializer recomputes the release and capsule from the project, rejects
an explicit capsule that differs from those bytes, copies only authorized
artifacts, and writes a decision template and standalone validator. Run the
validator inside the neutral capsule before returning `output/review.json`.
The verifier never records a decision or admits a Fact; those remain gateway
operations.

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

Revision 16 repairs the Reader identity/projection boundary and direct-drag
stability. New V5 projection titles are bounded content-free object identities;
all canvas labels and hover text derive from the first six object-hash digits
plus localized role and plane, including legacy packets. Complete claims and
TeX remain in the right panel, whose title/readable/formal containers recognize
parenthesis, bracket, dollar, double-dollar, and supported environment syntax.
Direct drag cancels queued convergence, moves and pins only the dragged set, and
never launches neighbor forces; the bounded revision-15 solver remains scoped
to actual card-size changes. Packet v1, authority, and old project bytes remain
unchanged.

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
external project root, start the prospective CHX ledger in that project's
`chx-ledgers/` directory, select a reasoning
mode, and report mode event, repair advice, audit state, and
Candidate Release/Certification/Fact boundary. Close the ledger and apply conditional
feedback without changing any project status. Installation,
global replacement, packaging, migration, and cutover each require separate
explicit authorization.
