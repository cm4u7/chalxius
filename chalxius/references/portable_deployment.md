# Chalxius portable deployment

The 0.7.15 `Research Obligation Closure` release artifact contains one self-contained `chalxius`
skill,
no live project, credentials, service dependency, bytecode, or symlink. Python
3.11+ is required. The native local Paper/Evidence Library CLI is bundled under
`scripts/`; its records and PDFs stay in an explicit external library root. The
Chalxius research engine is the only embedded research kernel; retired
predecessor, coordinator, and standalone companion skills are not runtime
dependencies.

The release retains the prospective Research commands:
`plan-supervision-round SOURCE_ROUND_ID [--component-id COMPONENT_ID]` and
`plan-computation-execution SOURCE_ROUND_ID ASSIGNMENT_ID`. Existing frozen
rounds remain single-wave and retain their exact automatic computation-review
behavior. New public production is constructive-only and leaves formal
Research attack to the second logical subround. New production manifests freeze
Research-ancestry components before dispatch: a completed component can enter
supervision while unrelated workers continue, whereas related integration waits
for its full component. Multi-component calls require the exact component id;
timing-derived subsets and overlapping scope coverage fail closed. Cycle-safe
command-local validation and content-addressed retry repair partial supervision
writes without introducing a persistent authority cache. Historical
component-free production retains conservative whole-round waiting. Candidate
work checks completed live supervision before expensive validation and again
under the seal lock. Formal computation ignores aborted program-math reviews
and revalidates its exact approval plus latest disposition under the
execution-round lock. No project migration or Candidate/Fact schema rewrite is
required.

Generic production planning now removes a source Research obligation only when
an exact valid ingestion receipt exists in a non-aborted production round. The
receipt-produced worker Research remains available for continuation, and
explicit Research-ID planning plus history views retain their prior behavior.
Immediately before publishing a generic production round, the mutation lock
uses a fresh inspection to reject a newly closed obligation without writing
round bytes. Main-role `memory-add` also reuses complete identical unbound
semantics across actor labels; operator and task/assignment-bound writes remain
actor-sensitive. No persistent index, scheduler, new lifecycle state, or truth
authority is added.

The release adds `selective-fact-checkpoint` as a Main-only pre-Candidate
operation. It freezes one bounded nontruth readiness receipt and a deterministic
dependency-closed Candidate batch partition over explicit Research ids.
Dependency-connected selected targets stay atomic; independent targets remain
singleton failure-isolation units. It neither
automates truth selection nor weakens Candidate adverse, verifier,
Certification, Gateway, or Fact admission. Existing projects need no migration;
the governance directory is created lazily by the ordinary V5 initializer.

Main may then use `plan-candidate-adverse RESEARCH_ID` for one exact current
Candidate-Fact target. Candidate checks reuse only a command-local validated
inspection context and repeat supervision liveness under the seal lock. No
persistent cache or new lifecycle owner is installed.

If that target is an exact supervised production result, Main may first use
`prepare-candidate-adverse-target PRODUCTION_RESEARCH_ID`. Current
Candidate-adverse cards use a dedicated compact bootstrap; current supervision
cards inherit a content-addressed projection of the attacked production Fact
premises and exact source/input capabilities. Historical cards remain
byte-exact under their archived runtime.

Candidate-local assurance shape and exact current-assurance statement-interface
errors reject from submitted Fact bytes and immutable selected-Research
envelopes before global replay. Active-Fact validation may reenter only through
one command-local provisional Release/marker/Fact projection; the outer frame
still performs complete authority replay and requires exact equality. Approved
computation replay preserves the same inspection context through its nested
design and supervision closure. No recursion-limit change, alternate authority,
or persistent cache is installed.

A newly generated current production worker or supervisor reads the full skill,
exact prompt/card, and its manifest-bound compact bootstrap before mathematical
inputs. Production then reads the public return contract and only its role-
specific expansion; supervision loads broader computation, source,
attack-learning, CHX-repair, or unprojected assurance protocols only for the
exact scope or observed event. Legacy or invalid cards retain the ordinary
full protocol path. Computation-design cards use exactly the canonical source,
design, and dependency roles and reject incompatible obligations before round
bytes. This is context routing and early satisfiability only: task-card
validation, worker CHX, return preflight and exact-byte ingestion, Candidate
fresh adverse, verifier, Certification, Gateway, and Fact admission are
unchanged.

## Verify a received release

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

For a complete release matrix, prefer the manifest-bound coordinator and write
its receipt outside the candidate:

```bash
python3 scripts/release_validation.py \
  --candidate-root "$SKILL_ROOT" \
  --expected-manifest-sha256 APPROVED_MANIFEST_FILE_SHA256 \
  --receipt /absolute/path/to/release-validation-receipt.json
```

It constructs canonical manifest-only lane copies, isolates temporary and
runtime-archive state, runs the complete mutation-registry applicability check
beside architecture reconnaissance in phase 1, runs compatible baseline checks
in parallel only after the cheap gates pass, then runs the snapshot-sensitive
mutation audit behind a phase barrier. Every lane and the source must retain one
exact identity. Run
`python3 scripts/aggressive_bug_audit.py` directly only when the narrower
mutation evidence is required; it independently suppresses bytecode, compares
one exact pre/post path-kind-mode-content snapshot, and fails on drift. Before
any baseline subprocess, its mutant registry preflight checks every target and
old fragment exactly once, so a stale plan fails cheaply rather than consuming
the full audit budget.

## Preserve runtime continuity before every global cutover

A global skill path is a mutable discovery alias, not an immutable historical
runtime locator. For protected projects, first build one approved validation
receipt. Its request names the exact candidate manifest, prior runtime
identity, protected roots, prior current-audit receipt, complete release matrix,
exact changed-path classification, and whether those changes require one fresh
deep audit:

```bash
python3 -B /absolute/path/to/candidate/scripts/runtime_cutover_project_validation.py \
  --candidate-root /absolute/path/to/candidate \
  --installed-root /absolute/path/to/.codex/skills/chalxius \
  --archive-root /absolute/path/to/.codex/skill-runtime-archives/chalxius \
  --request /absolute/path/to/approved-project-validation-request.json \
  --expected-request-sha256 APPROVED_REQUEST_SHA256 \
  --output /absolute/path/to/project-validation-receipt.json
```

The builder verifies the complete request and matrix hashes, exact runtime
diff, prior current audit, terminal round states, and every historical runtime
binding. It hashes all audit-relevant project bytes while excluding only the
explicit non-authority `work/`, `output/`, lock, desktop metadata, and bytecode
surfaces. If the approved classification says the runtime delta affects deep
audit semantics, the builder runs one full audit. Otherwise it reuses the prior
audit only when no protected byte is newer than that exact anchor. Either path
emits one write-once receipt; a changed project, matrix, request, runtime, or
receipt invalidates it.

Current receipt v2 is stricter than a timestamp anchor. The approved JSON helper
hashes and parses one byte read; booleans cannot substitute for integer version
or process-count fields. Every path, digest, timestamp, snapshot revision,
validation mode, project witness, and runtime binding is checked centrally.
Exact reuse follows immutable predecessor receipts with a fixed depth limit and
cycle detection, requires the same project snapshots and terminal maps at every
link, and must terminate at one valid `single_deep_audit` receipt. It reads that
lineage only; it never reruns an ancestral audit. Candidate-path identity is
retained as provenance, while the live installed runtime must match the prior
receipt's path-independent content and manifest hashes. This is what permits the
next release generation to reuse a byte-identical installed copy.

The normal one-to-two-minute and uncommon four-minute administrative targets
are telemetry, not receipt semantics. Crossing either target emits diagnostics
without termination, downgrade, retry, or approval. A separate explicit finite
watchdog stops genuinely lost work and produces no receipt.

Administrative cost is reduced in this order:

1. eliminate work at its source: choose the smallest public projection, derive
   applicability before opening authority, skip an exactly absent optional
   subsystem, and validate one canonical immutable collection before deriving
   filtered views; routine `mgraph status` is a bounded dashboard, while
   `mgraph status --with-audit` explicitly requests the forensic payload;
2. thread one locally owned aggregate inspection context through every subaudit
   and reuse only successful projections under the same exact command and
   snapshot;
3. measure the remaining real path with bounded timing or profiling before
   selecting another optimization;
4. consider a persistent index or genuinely independent isolated parallel lanes
   only after measurement establishes that command-local elimination and reuse
   are insufficient. A persistent index requires an explicit invalidation,
   rebuild, and recovery contract.

This ordering targets agent misoperation, hallucinated retries, accidental broad
commands, and duplicate call paths rather than hostile external attack.
Parallelizing duplicate reconstruction is not a repair. The policy does not cache
failed validation, cross a command or snapshot boundary, relax a release lane,
or replace a required audit. When profiling a new large project, inspect
Blackboard graph projection, parallel-verification and research-draft deep reads,
Paper Evidence Library collection rebuilds, mode/Pulse/experiment summaries, and
Reader aggregation as possible duplicate-work surfaces; treat them as profiling
targets until measured, not as authority or defect claims.
The complete prospective route register, measurement protocol, and fail-closed
boundaries are maintained in
[`administrative_cost_playbook.md`](administrative_cost_playbook.md).

Then perform the replacement or rollback with every protected project named
explicitly:

```bash
python3 -B /absolute/path/to/candidate/scripts/runtime_cutover.py \
  --candidate-root /absolute/path/to/candidate \
  --installed-root /absolute/path/to/.codex/skills/chalxius \
  --rollback-root /absolute/path/to/.codex/skills/chalxius-prior \
  --archive-root /absolute/path/to/.codex/skill-runtime-archives/chalxius \
  --project-root /absolute/path/to/protected-project \
  --expected-candidate-manifest-sha256 APPROVED_64_HEX \
  --project-validation-receipt /absolute/path/to/project-validation-receipt.json \
  --expected-project-validation-receipt-sha256 APPROVED_RECEIPT_SHA256
```

The gate requires either one or more `--project-root` values or the explicit
`--confirm-no-protected-projects` assertion. It verifies the exact candidate
file set and self-test, rejects every nonterminal protected project, archives
the installed runtime and every matching frozen card identity, performs a
same-parent rename cutover, archives and self-tests the new install, and
rechecks the exact receipt identity and project digest. It does not repeat a
semantic audit after copying identical bytes. Any post-swap failure
automatically restores the prior installation. A protected-project cutover
without a receipt is rejected by default. The explicit
`--force-full-project-audit` escape runs one full pre-swap audit and reuses its
in-memory exact snapshot post-swap; it never authorizes two duplicate audits.
An explicit rollback uses the same gate with `--operation rollback`, the exact
rollback tree as `--candidate-root`, and a new backup root.

The low-level `scripts/archive_runtime.py` command copies only manifest-listed
regular files, verifies every hash and the exact resulting file set, seals one
content object read-only, and publishes one immutable identity-registry record.
The archive is validation data only: it
must never be added to skill discovery, imported, executed, or treated as Fact,
Evidence, Paper, Research, Candidate, Certification, or Gateway authority.

To seed a legacy schema-1 identity, use one exact frozen task card and a source
tree whose VERSION, MANIFEST, and all declared file hashes match that card:

```bash
python3 -B /absolute/path/to/0.6.4/scripts/archive_runtime.py \
  --source-root /absolute/path/to/exact-historical-runtime \
  --archive-root "$ARCHIVE_ROOT" \
  --task-card /absolute/path/to/frozen-task-card.json \
  --expected-runtime-identity EXACT_64_HEX_ID
```

Inputs, runtime roots, archive roots, registry paths, manifest directories, and
files are traversed component by component without following links. Traversal,
special files, hard links, nested cross-device entries, extra archive files,
registry drift, or a host-root mismatch fail closed. An optional
`CHALXIUS_RUNTIME_ARCHIVE_ROOT` is host configuration and must equal the locator
frozen into any new schema-2 card; all processes serving one project must use
the same value.

The receipt builder runs the necessary terminal-round checks once. Refuse
replacement while any protected round remains active; complete it or
explicitly abort it first. A terminal completed
or aborted card may use the archive only for read/status/audit interpretation;
worker CHX startup, returns, ingestion, experiments, Pulse, and every mutation
still require the exact current live runtime. Cards, receipts, Research, Paper,
Evidence, Candidate Releases, decisions, admissions, Facts, and CHX ledgers are
never rewritten during archive seeding or cutover.

## Start and finish the CHX ledger

For every run begun after the 0.4.1 activation boundary, start exactly one
task-scoped CHX ledger before substantive work, using
`scripts/chx_ledger.py start`. For project-bound work, store it at
`PROJECT/chx-ledgers/`; for projectless work, use private host task state outside
the skill. This operational file has no project-audit or truth effect. Close it
after applicable audits and immediately before final reporting. Report it only when close returns
`report_required=true`; when false, emit no ledger message at all. See
`chx_runtime_ledger.md` for the exact commands and causal schema.

For publication, an immutable predecessor need not be rewritten merely because
its repair was completed by a successor. The public-disclosure gate accepts an
unresolved predecessor only through exactly one strictly later, explicitly
`supersedes`, publication-resolved issue; every other unresolved or ambiguous
lineage still fails closed.

## Consult the global PHX route guide

PHX is a private host-global, nontruth reference guide for significant reusable
architecture routes distilled from CHX and other evidence. Concrete problems
remain in CHX. A cost or performance CHX repair must persist a PHX search receipt
before selecting its mechanism and bind that receipt in tactical or integrated
evidence. Route recording, retrieval, evaluation, and reporting do not authorize
implementation. Any route that would change active architecture requires an
informed user consultation recorded before implementation, supporting digest-
bound evaluation, exact scope and constraints, alternatives, risks, and rollback.

The default ledger root is `~/.codex/chalxius/phx-ledgers/`, owned by the current
user with private permissions; reports and search receipts remain below that
root and never enter a research project. A custom root is expert-only and must be
explicitly authorized. The present consultation record is an auditable agent-
supplied assertion, not a host-signed approval token, so deployment and cutover
must continue to obtain explicit user authorization through their own boundary.

This requirement is prospective. A task already running under 0.4.0 keeps its
original status even if the installed skill changes or it loads some 0.4.1-or-later
bytes. Do not backfill its ledger, recertify it, mark it noncompliant, invalidate
its work, or request a redo.

## Produce Attack reports prospectively

Global installation makes the adverse-routing commands available but does not
rewrite any project. The standing authorization makes V5 status and zero
reports available read-only; the first newly frozen refute card lazily
materializes project-local governance. The compatibility command may do so
explicitly before planning:

```bash
"$MGRAPH" --root "$PROJECT" --role operator attack-route-enable \
  --actor USER --reason "Enable prospective user-governed Attack reports."
"$MGRAPH" --root "$PROJECT" --role main attack-route-status
```

Do not materialize it in V1-V4 roots, in the middle of a frozen work unit, or
merely to modernize an old project. Never backfill attack cases, change an old
return schema, invalidate prior work, or request a redo. Every previously
frozen task card remains byte-for-byte under its original contract.

For every host task, produce the separate report even when it has zero
cases:

```bash
"$MGRAPH" --root "$PROJECT" --role main attack-report \
  --host-task-scope-id HOST_TASK_SCOPE_ID
```

The default report contains at most three selective, family-deduplicated attack
types with one reviewed ordinary-language sentence saying what each checks,
its applicability, and its support. It exposes no technical case internals or
worker-authored instructions. Unknown families remain in `--full` until their
user-facing explanation is reviewed. Use `--full` only for the complete
worker-reported nontruth coverage/case audit. Main alone may reject a report or
synthesize a compact mechanism-level rule; the operator may disable an active
rule. Decisions affect future task cards only.
Attack reports never become CHX architecture reports or Fact evidence.

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

Under `auto` or `deep`, a user-stated research objective is enough to provision the
internal advisory scope; the user does not need to say `Campaign`:

```bash
"$MGRAPH" --root "$PROJECT" --role operator research-goal-intake \
  --input goal.json --actor USER
```

`goal.json` contains exactly revision `chalxius-bf-goal-intake-2` and the
user's objective. The result returns an internal Campaign id for future
Research and computes BF-1. It does not select `ACTIVE`, retag prior Research,
plan, or dispatch. BF-2/BF-3 remain unavailable until a real exact blockage
with an ingested attempt passes the inherited validator.

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

For new 0.6.4 work, Main compiles task context and Operator retains governance;
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
source and output artifacts are present. New ordinary challenges receive the
original eight baselines plus the general hidden-conjunct split. Only an exact
frozen `philosophy` or `mixed` domain adds the three philosophy baselines;
words in the claim do not. The program-math rule is scoped to that generated
review, and old frozen cards retain their exact earlier baseline.

Materialize a V5 verifier capsule into an absent directory or an existing empty
directory with mode `0700`:

```bash
python3 -B "$SKILL_ROOT/scripts/prepare_verifier_capsule.py" \
  --project-root "$PROJECT" --release-id RELEASE_ID \
  --capsule-root /absolute/external/verifier-capsule
```

The materializer recomputes the release and capsule from the project, rejects
an explicit capsule that differs from those bytes, copies only authorized
artifacts, and writes a decision template, standalone validator, and host
submission program. The verifier writes only `output/review-draft.json`. The
host then runs:

```bash
python3 -B /absolute/external/verifier-capsule/host/submit_review.py \
  --capsule-root /absolute/external/verifier-capsule
```

An invalid draft remains under `output/quarantine/` with structured
JSON-pointer diagnostics and creates no project effect. The gateway may consume
`output/review.json` only after the host command returns `formally_returned`
with its content-addressed receipt. The verifier never records a decision or
admits a Fact; those remain gateway operations.

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

Revision 17 reintroduces only a bounded two-hop/collision-halo force around
direct manipulation, with the manipulated set fixed, radial-memory springs,
and no idle simulation. Revision 18 then used that prior radial result only as
a deterministic angular seed and projected real cards onto one concentric orbit
per theme. Revision 19 preserves the seed but gives each theme its own center
and one equally spaced ring per up to six presentation members. Strong
prerequisite/support target-closure overlap gives shared nodes multiple field
assignments and deterministic overlap placement. Locked orbit rings remain
presentation-only.
Revision 20 preserves that geometry and changes only orbit-off collision
response: a current drag anchor may repel an actually colliding old Cartesian
pin, updating that existing pin while unrelated pins remain fixed and no new
pin is created.
Default-on session gravity gives drag a rolling two-frame local response and
settles released real cards or resized neighborhoods for at most 24 frames;
released cards retain per-center angles and return to one or more assigned
theme fields. At most 240
active neighborhood nodes move on any map, while all other visible nodes remain
measured fixed boundaries. Reduced-motion settlement is synchronous. The
session toggle, rings, angles, and forces create no packet, source, graph,
storage, service, authority, admission, or writeback state.

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
