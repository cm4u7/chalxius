# Chalxius portable deployment

The 0.3.5 candidate contains one self-contained `chalxius` skill,
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
retired predecessor skills. The exact task-card `execution_profile` decides
whether the clean-context panel, durable two-wave pulse, Paper/Audit work,
computation lane, campaign expansion, novelty search, and expert synthesis are
`required`, `available`, or `not_applicable`. Truth/adoption gates and the
Fact-admission contract are invariant in all modes.

For a required panel, use all genuinely distinct currently callable
clean-context slots. For a required pulse, produce actual plan, ingestion,
barrier, trusted dispatch, cross-review, and closure evidence. An available
feature is opt-in; an inapplicable feature is not manufactured. Estimated cost,
duration, burden, and score are priority/load ordering only and never weaken a
required feature or truth gate.

Every new round freezes `profile_obligations`. After canonical ingestion, run
`profile-closure-status`; if required, record exact typed evidence with
`profile-closure-record` before constructing a verifier task. The receipt binds
each task card, return, ingestion, outcome, and effect. It is
`workflow_readiness_only`, outside the invariant Fact contract, and cannot
change that contract's hash. A Fast round with no required feature is
`not_required` without a receipt. Machine-native and procedural host evidence
must retain their distinct labels.

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

## Historical projects

An existing project in the pre-Chalxius V4 format (`mathgraph-chalk-version`
0.4.0) is read-only until an operator records `mode-init`; audit emits a
compatibility warning rather than corruption. This is enforced by the public
Python API, exposed child-store writers, and CLI—not only by command routing.
Activation first requires a clean byte-pure current audit before creating
`.mathgraph.lock`, then repeats audit and inventory under the transition lock.
The schema-2 receipt hashes the frozen round inventory and every exact byte
backing already-accepted ordinary and atomic admissions. Only that exact
accepted set is grandfathered for future profile closure; pending candidates
are not, and any baseline drift or symlink substitution fails closed.

For a legacy V1-V3 project, all public mutation—including exposed child-store
methods—is disabled and the active root must never be migrated in place. Use
`upgrade-project-copy --source LEGACY_ROOT` with a nonexistent destination,
inspect audit and trust debt, then run `mode-init` on the copy. Keep
`cutover_status=not_performed` until the user explicitly selects the unified
copy. Imported facts retain inherited assurance; new facts use the invariant
unified gate.

An old unified V4 round with no frozen `profile_obligations` must be replanned;
do not backfill a closure receipt. The internal Python `reasoning_mode=None`
compatibility seam is only for internal fixtures representing pre-Chalxius V4
projects. Official CLI initialization defaults to `auto`.

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
external project root, select a reasoning mode, and report mode event, required
feature closure, audit state, and candidate/admitted boundary. Installation,
global replacement, packaging, migration, and cutover each require separate
explicit authorization.
