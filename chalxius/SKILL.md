---
name: chalxius
description: Operate Chalxius for source-bound mathematical and philosophical research, Paper and Evidence graphs, two-subround Research, verifier-gated Fact admission, computation, architecture repair, Reader export, and explicitly requested academic teaching through Chalxius Learner.
---

# Chalxius 1.0.0 — Fact Alpha

Chalxius is one research runtime. `fast`, `auto`, and `deep` are execution
profiles; they never change the Fact-admission contract. The historical
`operate-mathgraph-unified` name is schema compatibility only. Cross-version
operation is defined by the MathGraph itself: node and edge identity, content
hashes, dependencies, provenance, workflow stage, and owner boundaries. A
runtime path, installation identity, archive locator, or obsolete receipt is
diagnostic provenance, not a prerequisite for ordinary graph work.

## Forward-upgrade rule

Future releases do not owe runtime or procedural forward compatibility. An
upgrade may replace or remove old adapters, migration ceremonies, runtime
identity checks, and administrative gates when the MathGraph semantic surface
remains operable. The continuity obligation is semantic: an agent must be able
to interpret and operate valid node/edge hashes, dependencies, provenance,
workflow stages, and owner boundaries. Mathematical-safety and Fact-authority
checks stay at their owning boundaries; procedural legality is not a second
truth path.

Worker-ingestion receipts are workflow markers only. They document that a
return passed through ingestion and provide optional replay provenance, but do
not grant a Research capability or mathematical status. A complete hash-bound
Research product with valid assignment provenance can be consumed by later
workflow stages when its derived receipt is absent; missing products,
stage/owner/hash drift, and independent verifier, Certification, Gateway, Fact,
terminal-seal, or final-experiment checks remain blocking at their own owners.

## Fact Alpha: one Research graph, sparse certification

Fact Alpha treats the immutable Research graph as the only mathematical node
graph. A Fact is an append-only certification grant on one exact complete
Research record and its top-level `claim`; it is not a second prose node and
does not require a `claim_sha256` beside the record hash. Legacy admitted Facts
remain readable authority but are explicitly unmapped: Chalxius never invents
Research identities or statement surfaces for them.

Main records load-bearing importance with `fact-frontier-mark`. The derived
`fact-frontier` follows exact COW lineage, hydrates current claims, reports
supervision and packaging state, propagates `needs_reverification` through
certified predecessor grants, and derives certified heads. Only the importance
mark and an explicit `active`, `deferred`, or `dropped` disposition persist;
the frontier, batches, heads, counts, and next actions are live projections.
They have no Research or truth effect.

Fact work is intentionally asynchronous. At a Campaign milestone, a meaningful
backlog, a direction switch, a context handoff, or an explicit user request,
Main chooses one or more ready marks and runs `plan-fact-packaging`. There is no
timer, threshold, watcher, scheduler, or automatic Candidate launch. One frozen
plan can be handled by one `fact-packager` agent across several independent
components. That narrow role can read the derived Fact frontier and seal the
explicit plan, but cannot mark importance, verify, decide, or certify.
`fact-package-seal` requires every selected Research node to be
either packaged or explicitly returned as `needs_split`/`blocked`; a bad
component does not discard a correct independent component.

Packaging does not rewrite proofs. For each complete Research node it supplies
one semi-formal statement interface whose conclusion is byte-for-byte the
Research `claim`, plus assumptions, domain/types, quantifiers, limitations, and
explicit certified Research predecessors. Those predecessor ids are the rigid
load-bearing Fact edges; descriptive Research `relation` strings are never
reinterpreted as proof dependencies. A predecessor must be in the same acyclic
component or already have an active grant.

`fact-verifier-capsule` gives one independent correctness verifier the frozen
Research bytes, interfaces, and component edges. The verifier performs fresh
whole-node mathematical, scope, dependency, source/computation, and interface
checks. The learned theorem-attack vocabulary belongs to ordinary Research
supervision, so Fact verification does not train a second adverse role.
`fact-verification-record` records component-local decisions; `fact-certify`
is a mechanical, independent Gateway visibility switch for correct components.

A minor verifier finding returns the complete affected component through COW.
`plan-fact-packaging --minor-repair-decision ...` requires every node of that
component, at least one real COW successor for each affected node, and the same
verifier for a complete recheck; ordinary supervisor dispatch is omitted for
that bounded lane. The verifier may not author the repair. A fundamental error
abandons that component and returns to ordinary Research/COW/supervision.
Existing grants whose Research or certified predecessor acquires a COW
successor become `needs_reverification`; historical bytes remain readable.

New Research may name `certified_research_dependencies`. Chalxius resolves
them to exact active Research/grant hashes and freezes their statement
interfaces and proof bytes into future task cards. This is the operational
meaning of Fact being a property of Research rather than a parallel graph.

## 摸石头过河

Main continues mathematical Research by default. When live operation exposes a
material Chalxius architecture failure that threatens reliable research,
Main saves the exact Campaign target, active Research heads, live rounds,
returns, ingestion, and pending supervision; performs the bounded integrated
repair and local installation; rereads those exact graph bytes; and resumes the
same mathematical boundary. Ordinary mathematical uncertainty, an open proof
obligation, or a merely interesting refactor does not trigger the repair leg.
This is a Main operating semantic, not a scheduler, timer, watcher, automatic
issue detector, automatic installer, publication action, lifecycle gate,
Candidate effect, or Fact effect.

The 0.9.18 repair makes the compact frontier's advertised breadth usable
through the ordinary Campaign operations. One shared limit of sixteen now
governs legacy checkpoint reading, current working-state validation,
`plan-round --frontier-target`, manual frontier reconciliation, and live goal
projection. Main-selected heads are never reduced to the old eight-head write
surface; derived successor summaries remain bounded and diagnostic topology
remains available explicitly. Routine mathematical summaries use a larger
decision budget—300 characters per head claim, 400 for the root, and 320 for
each projected historical claim—while the exact complete Research remains
retrievable by id. This is bounded working-memory capacity, not paging,
automatic head selection, scheduling, Candidate authority, or Fact authority.

The 0.9.17 repair also finishes the routine frontier representation boundary.
Every active head and every applicable supervision scope remains visible, with
its concise mathematical claim, current route Research ids, next action, and
exact actionable Research/round ids. Repeated route summaries, terminal trees,
evidence lists, hashes, empty fields, and equivalent action labels remain
available through `frontier --diagnostic` instead of being copied into each
routine head action. Main therefore receives mathematical working memory rather
than repeated forensic topology; no head is selected, hidden, closed, or
dispatched automatically. The ordinary default window is twelve Campaign
targets, and each projected target retains all of its active heads; an explicit
`--limit` changes the target window, never an intra-target head cap.

The 0.9.16 repair makes three ordinary Main coordination paths agree with the
graph state they already read. Default supervision planning subtracts exact
completed or in-flight component scopes and returns a read-only no-op when no
scope remains; explicit scope selection and overlap rejection stay strict.
Routine Campaign frontier applies its requested limit to the nested goal
projection and keeps the complete target count, digest, ids, and mathematical
summaries; `--diagnostic` retains the full view. Source-bearing task artifacts
use one shared structural role predicate: the historical standalone `primary`
token and the exact `authoritative_source` spelling both denote direct source
bytes, while computation, analytic, secondary, or concatenated lookalikes do
not. These are coordination and capability projections only, with no automatic
mathematical choice, scheduler, compatibility layer, Candidate effect, or Fact
effect.

The 0.9.15 repair keeps semantic COW completion separate from operational
workflow identity. A COW terminal may prove that an older workgroup is
completed or ambiguous, but it cannot lend its own assignment, round, product,
component, or supervision lineage to that older group. Frontier actions are
projected from the exact physical workgroup members, with the existing
hash-bound product-to-source assignment redirect used only when its provenance
validates. This preserves complete COW history while preventing one repair
route from hiding another route's real product or review state. It adds no
selector, scheduler, compatibility layer, Research effect, Candidate effect,
or Fact effect.

For immutable 0.x Candidate records only, Candidate-level fresh-adverse review
remains scoped to explicitly selected constructive Research heads carrying
`independent_adverse_required=true`. This rule preserves old authority; new
Fact Alpha packages use the one independent Fact verifier and do not launch a
second Candidate-adverse worker.

Structured source-evidence capabilities are interpreted by their graph
semantics, not one runtime-era field spelling. Current `artifact_path` and
`artifact_sha256`, compact `path` and `sha256`, and the historical
`card_authorized_path` plus `returned_copy_path` declaration are equivalent
only when every declared concrete path exists inside the project and has the
same declared SHA-256. A locator by itself never grants file capability.

The 0.9.14 repair gives Candidate enforcement and Main's frontier one shared,
typed supervision-coverage reader. For every exact production component and
applicable scope it distinguishes `completed`, `missing`, `pending`,
`conflicting`, and `unsafe`; ordinary absence is no longer collapsed into
`supervision_result_lineage_unreadable`. Malformed or inaccessible graph bytes
remain unreadable and fail closed. Candidate construction still requires every
applicable scope to have exactly one completed, ingested result. The projection
is bounded nontruth working context: it adds no scheduler, automatic dispatch,
compatibility layer, receipt, Candidate effect, or Fact effect.

The 0.9.13 repair makes typed workflow structure authoritative without adding
a second relation dictionary. For worker products, supervision plans/results,
and structured repairs, existing assignment provenance, `kind`, frozen source
receipts, and exact `repair_of_research_id`/`trigger_research_id`/`source`/
`related_research_ids` identities determine the lifecycle edge; `relation`
remains concise Main-authored mathematical context. A supervision receipt set
must remain unique and fully covered by `related_research_ids`, but the latter
may also carry exact review context. A structured repair may name a Main
synthesis trigger instead of a direct supervisor return; when that trigger's
complete `research:` source set exactly equals its related ids, those reviewed
inputs lead through the trigger to the repair. Cross-Campaign, malformed,
backward-time, ambiguous, incomplete-product, or non-hash-bound completion
shapes still do not close work. Every new repair product still requires its
applicable supervision before completion; no Research, Candidate, or Fact
status is inferred from the edge alone.

`round-status` now gives every supervision assignment a read-only
`reviewer_independence` projection containing the attacked source assignment
and product ids. Main compares the actual live reviewer with those source
assignments before dispatch. One independent reviewer session may still be
reused across scopes or later COW stages; a reviewer that authored an attacked
product must not self-review it. This is Main-visible dispatch context, not an
identity registry, scheduler, receipt gate, or automatic rejection mechanism.

The 0.9.12 repair closes three frontier lifecycle seams without adding a
second state machine. Exact historical Main-authored COW roots may complete a
workgroup when their existing relation, complete source-id set, single
obligation-complete production product, explicit challenge companions,
Campaign, dependencies, and chronology determine one unambiguous repair edge.
In a multi-head Campaign goal, an exact `await_return` branch is the foreground
goal state even when an older sibling still needs reconciliation; every sibling
action remains visible. One frontier command also reuses Research envelope
bytes already hash-validated in that command before running the full record and
artifact checks. Historical bytes are not rewritten, and no compatibility
layer, automatic selector, hidden branch deletion, persistent index, Candidate
effect, or Fact effect is introduced.

The 0.9.11 repair treats routine frontier context as Main's mathematical
working memory rather than as a byte-minimization exercise. Goal rows retain
exact actions, compact current mathematics, and bounded recent and historical
summaries while removing mechanically repeated diagnostic topology.
`plan-round --frontier-target` can hand off an active route when the selected
successor descends from its completed terminal products or reviews, not only
from the old head itself. Batch round status ignores only a narrowly
recognized private staging name and reports that fact in a bounded diagnostic;
visible malformed round names remain visible diagnostics. A downstream
source-scope supervisor follows only explicit direct Research workflow
provenance to a completed prior source-scope review and receives that review
plus the exact primary-source hashes it actually used. These are bounded read
and nontruth-navigation repairs: they add no semantic search, compatibility
layer, monitor, gate, Candidate effect, or Fact effect.

The ordinary frontier has one exact workgroup/completion projection. Exact duplicates have one actionable representative; exact related Research remains material to task-card and supervision authority. Completed production and applicable supervision disappear only from actionable views; history remains intact. `limit` bounds entries and members, zero-target planning avoids Fact inventory, and the full set remains a count/digest.

The 0.9.1 ordinary frontier is lifecycle-aware: no product means `production`; live work or a published return means waiting/ingestion; a current product means `supervision`; invalidation means `repair`; and ambiguous evidence means `main_reconciliation` with exact bounded ids. A Campaign `research_goal` keeps its exact Research subject as an immutable provenance anchor. Main may append a nontruth `campaign_frontier_head_checkpoint`; the newest generation supplies bounded exact lifecycle work heads and attained checkpoints, so routine reads do not walk an obsolete branch from the anchor. Zero heads ask Main to select the next question, multiple heads remain jointly visible, and a missing/cross-Campaign head requests bounded exact recovery from the nearest attained checkpoint. The note never updates itself, dispatches, closes, or affects Candidate/Fact authority. Campaigns without such a note retain the anchor projection. Default `mgraph frontier` is compact; `--diagnostic` is bounded forensic detail; `ACTIVE` is a hint, never a filter. No fuzzy selector, persistent index, automatic target rewrite, compatibility layer, monitor, scheduler, or gate is added.

The 0.9.2 repair separates completion of a selected checkpoint head from
semantic completion of its active Campaign goal. A finished single head, all
finished parallel heads, or a finished anchor with no checkpoint now asks Main
for `main_disposition`; an empty checkpoint asks Main to select a new exact
head. Only explicit target archive removes the goal. Checkpoint diagnostics
remain advisory. Production mode also remains a default supervision-scope
hint, not a prohibition: Main may explicitly select any registered primary
scope that is materially applicable to the complete frozen successor. This
does not auto-review, duplicate an already completed review, dispatch, close a
goal, or affect Candidate/Fact authority.

The 0.9.3 integrated cleanup makes this surface directly operable. Main may create Campaign-bound Research atomically with `memory-add --campaign`; the Campaign is checked before semantic identity and again under the write lock. Each new production round freezes Main's selection source, exact Research ids, Campaign id, mode, and copy-safe replay argv. Frontier and goal rows expose compact `next_attention`, `disposition`, exact basis ids, and `plan_round_argv`.

An already-live supervision round is always projected before the planner asks whether the source product is safe for a new supervisor suggestion. The former Brave Future/goal-intake command family is removed without aliases; historical sidecar bytes are inert nontruth provenance. CHX inventory treats liveness as an explicit Main declaration, bounds historical lists by default, and uses content-addressed copy-on-write administrative dispositions for abandoned, superseded, or externally completed ledgers. Such dispositions never hide or resolve a mathematical or architecture issue.

The 0.9.4 Campaign repair keeps unlimited append-only history without history-sized routine reads or writes. Main `campaign-status` receives one compact current view, the latest minimal frontier checkpoint, and a fixed recent event-summary tail; there is no paging protocol, while exact old event bytes remain available for targeted forensics. New checkpoints persist only routing Research ids, recovery roots, and concise Main disposition. Campaign-scoped rounds freeze active current semantics plus an exact ordered history-prefix commitment: a later tail is valid, but prefix rewrite, reorder, or truncation is not. The 256 KiB cap guards anomalous current state rather than Campaign lifetime. Repair Research and its round inherit the exact source Campaign; an unbound source never infers `ACTIVE`. The 0.9.5 repair projects exact workflow successors and literal Research references. The 0.9.6 repair makes ordinary `search`/`show` operate on immutable Research as well as Facts and compares checkpoint active heads with exact later workflow routes. It reports stale heads, productive current routes, clean terminal review evidence, and a nonblocking refresh recommendation; Main alone decides and writes a later checkpoint. Historical semantic COW edges remain visible without requiring a later optional repair-spec field. None of these projections infers relevance, mutates a checkpoint, dispatches work, or changes truth authority.

The 0.9.8 repair fuses Main's exact Campaign-target selection with ordinary
production planning. `plan-round --frontier-target` atomically advances one
compact replaceable nontruth working-memory state containing bounded active
heads, recent attained results, historical mathematical landmarks, and one
recovery root per target. Frontier hydrates concise mathematical summaries
from canonical Research instead of copying node bodies. Sparse explicit
updates remain available for genuine branch reordering or history curation;
history-review advisories ask Main to inspect accumulated results but never
select, dispatch, close, or gate work. Invalid state falls back visibly to the
last checkpoint or Campaign roots, and targetless auxiliary or supervision
planning has no head effect. Structured source-evidence projection also keeps
its concrete declared files marked as primary-source capabilities, so a
source-scope supervisor may bind the exact frozen primary SHA-256 directly
without returning a redundant copy. Neither mechanism affects Candidate,
Certification, Gateway, Fact, or truth authority.

The 0.9.9 repair closes the overlapping-round successor handoff left by
0.9.8. When Main selects a positive Research descendant with
`plan-round --frontier-target`, the selected descendant replaces the exact
active predecessor route even if that predecessor still has supervision in
flight. The supervision remains visible and ingestible as workflow state, but
the predecessor no longer survives as a second head and later asks Main to
repeat the same semantic choice. Challenge, investigation, disposition, and
other nonadvancing relations do not retire a head. This changes only compact
nontruth navigation; it has no Research-result, Candidate, Certification,
Gateway, or Fact effect.

The 0.9.10 repair keeps terminal authority content-addressed when macOS Finder
materializes `.DS_Store` in the terminal bundle root or its sole `artifacts`
directory. Those two exact regular-file locations are host decoration, not
Research authority. Every expected seal, return, and artifact byte remains
path- and SHA-256-bound; unknown files, unexpected directories, writable
authority files, symlinks, hard links, special entries, device crossings, and
hash drift still fail. The repair neither rewrites frozen products nor adds a
compatibility layer, migration, workflow gate, Candidate effect, or Fact
effect. The same release also makes one ordinary frontier invocation reuse one
ephemeral exact-snapshot inspection of Research COW/repair topology, completion
state, and assignment product/receipt bindings. Research or round publication
invalidates the affected command-local state before any later read. Nothing is
persisted, and output, selection, dispatch, Candidate, and Fact semantics are
unchanged.

The 0.9.7 repair keeps Main on the current semantic frontier after deeper
copy-on-write and supervision chains. Exact task bindings project an ingested
product through its production root; in-flight supervision remains attached to
that stable root instead of making the checkpoint look stale; narrowly
recognized legacy repair relations remain traversable; and Campaign work not
mapped to an active goal moves into a bounded secondary attention summary
instead of filling the primary queue. `scripts/candidate_identity.py` exposes
the exact candidate root, manifest, Git worktree, and installed-tree difference
before source edits. Routine goal rows retain the exact head-to-workflow-root
map, current route/terminal ids, actionable Research/round, replay argv,
checkpoint freshness, and Main disposition; repeated successor hashes and
per-branch diagnostic trees move behind explicit `frontier --diagnostic`.
Routine `campaign-status` keeps eight recent event summaries beside the latest
checkpoint while exact older history remains directly readable. After
reconnect or context compaction, Main reconciles the
current and recent orphaned CHX ledger by instruction, without a monitor,
automatic issue generator, selector, mutation, compatibility layer, or truth
effect.

Source assurance is activated by structure rather than incidental prose:
literature work, source-dependent metadata, source/applicability obligations,
and exact primary-source capabilities require `source_uses` with exact
obligation coverage. Existing frozen cards are not backfilled or rewritten.
The 0.8.8 direct Fact and primary-source capability union remains unchanged:
ordinary Research validates only the exact admitted Fact nodes it consumes,
and a card-authorized exact `primary` artifact may be used without a returned
copy while toy checks and bridges remain return-bound.

The 0.8.11 repair keeps orchestration in Main's judgment: planning creates cards; Main launches workers, confirms starts, and recovers only on positive failure evidence. Artifact silence alone is not failure; context compaction, bounded startup reading, and deep reasoning are valid no-artifact intervals. Before interrupting or reassigning, Main checks fresh ordinary host status, messages, tool errors, and round bytes. Recovery requires an explicit disconnect/error or sustained total nonresponse corroborated by more than artifact silence, with no timer, heartbeat, watcher, receipt, recovery state, or gate.
A copy-on-write successor is a new complete product. Prior defects and repair obligations are mandatory but non-exhaustive attack seeds. Within the exact authorized product and assigned scope, its supervisor freshly reviews the whole successor and conserved claims for new, inherited, repair-induced, and cross-component defects. PHX constrains ceremony, never mathematical or source scrutiny.
Main owns cross-round and copy-on-write search, completion projection, duplicate exclusion, and final `DISPATCH`/`NO-DISPATCH`; Scouts may collect bounded evidence only. After mathematical dispatch or receipt, Main checks visible free slots and exact current Research boundaries; when a nonduplicative, logically independent high-value mathematical target exists, keep at least two workers active on useful mathematics. For non-mathematical engineering, delegate only when a bounded independent subtask is expected to shorten the critical path after startup, context-transfer, coordination, and merge costs. This is opportunity use, not filler work or a slot quota.
Slot use takes priority over reviewer-session reuse. After useful independent mathematical slots are filled, Main may continue with the same independent supervisor for another applicable scope of the same frozen product or for a later copy-on-write successor in the same route. This saves startup and repeated source loading; it creates no persistent supervisor binding, no receipt dependency, and no requirement to wait for that reviewer when another qualified reviewer is available.
A client `Reconnecting...` banner is transport state, not worker or round state. After transport returns, Main inspects agents, canonical return bytes, ingestion, and round state, reports any missed completion, and resumes without duplicate dispatch or reclaim solely because of reconnect. This creates no reconnect gate or liveness scheduler.
When a host command yields a still-running process/session without a final exit
code or the expected final JSON, Main resumes that same session. It does not
classify the first yield as blank stdout and does not retry a mutating planner
solely to obtain output. Only a completed command whose required output is
missing or invalid is an output defect. This is an operating instruction, not
a receipt, transaction layer, retry service, or gate.
The 0.8.10 repair makes Main run one bounded exact Research search over stable names/identifiers before freezing a named frontier, review completed production, repair, and supervision, and choose `related_research_ids`; it adds no automatic selection/expansion, fuzzy match, whole-project audit, index, receipt, state, scheduler, or gate.
The 0.8.7 repair makes Main notice elapsed time already visible through ordinary
host interaction. Unexpected duration relative to apparent complexity or a
recent comparable operation diagnoses repeated validation, broad rescans, or
idle work; it is not a numeric threshold or monitoring subsystem.

The same repair eliminates reproduced work: selective checkpoints share one command-local inspection; exact supervision retry filters unrelated manifests before rebuilding Research; and independent Research without Fact dependencies skips active-Fact lineage. Proof/program/integration supervisors receive the production card, selected outputs, and active Fact premises; only source-scope projects source-only capabilities. Existing exact path/SHA-256/role artifacts remain directly operable regardless of historical assurance labels. Projections never persist across commands or mutations. Content bytes/final SHA-256 outrank harmless mtime/ctime drift, while device, inode, type, size, link, containment, and hash checks remain exact. Worker examples execute the selected skill root's `scripts/mgraph` shell entry.

Main may author the exact canonical Candidate Fact bytes, including a canonical
Fact file inside a sealed Main-authored Candidate Release. Worker authorship,
container identity, and other provenance metadata remain useful lineage, but
none is a mathematical validity gate. Main calls
`prepare-candidate-adverse-target SELECTED_RESEARCH_ID --candidate-fact PROJECT_RELATIVE_PATH`.
The public command fixes the actor to Main and accepts no `--actor` override.
It consumes those exact canonical Fact bytes and binds every
applicable completed supervision result for the selected Research (possibly
none when no supervision scope applies); it does not infer, rewrite, or
validate the theorem merely from provenance. Fresh adverse work, its
disposition, a fresh verifier, Gateway-owned `certification-record`, and Gateway
Fact admission remain separate mandatory boundaries.

## Start through the smallest applicable contract

Read this complete router first. Then select exactly one startup path:

1. A current task card with `research_cycle.subround="production"` uses
   [references/v5_production_worker_bootstrap.md](references/v5_production_worker_bootstrap.md).
2. A current task card with `research_cycle.subround="supervision"` uses
   [references/v5_supervisor_worker_bootstrap.md](references/v5_supervisor_worker_bootstrap.md).
3. A current whole-Candidate refute card with no `research_cycle` and literal
   `independent_adverse_required=true` uses
   [references/v5_candidate_adverse_worker_bootstrap.md](references/v5_candidate_adverse_worker_bootstrap.md).
4. An explicitly requested, bounded edit of an existing Chalxius Learner
   teaching Markdown uses
   [references/learner_document_edit_bootstrap.md](references/learner_document_edit_bootstrap.md)
   only when every selector condition in that file holds.
5. Every other Main, Operator, legacy, malformed, uncertain, or escalated task
   uses the ordinary path: read
   [references/unified_architecture.md](references/unified_architecture.md),
   [references/reasoning_modes.md](references/reasoning_modes.md),
   [references/admission_contract.md](references/admission_contract.md), and
   [references/chx_runtime_ledger.md](references/chx_runtime_ledger.md), then
   only the directly applicable references below.

Compact paths are complete contracts, not summaries. They load a broader
protocol only at an explicit fail-closed branch. Never preload release,
admission, Paper, Blackboard, Learner, PHX, or attack protocols merely because
they exist.

### Direct reference router

- Round creation, legacy worker execution, return validation, or ingestion:
  [references/agent_protocol_v4.md](references/agent_protocol_v4.md).
- Paper reconstruction, inherited drafts, Paper Logic/Audit, Evidence, or
  continuation:
  [references/paper_logic_graph_v1.md](references/paper_logic_graph_v1.md),
  [references/paper_input_contracts.md](references/paper_input_contracts.md),
  [references/evidence_plane.md](references/evidence_plane.md), and
  [references/paper_research_pipeline.md](references/paper_research_pipeline.md).
- External theorems and sources:
  [references/external_theorem_applicability.md](references/external_theorem_applicability.md)
  and [references/external_source_reliability.md](references/external_source_reliability.md).
- Computation or replay:
  [references/computational_verification_v4.md](references/computational_verification_v4.md).
- Candidate/adverse routing:
  [references/adverse_routing_evolution.md](references/adverse_routing_evolution.md).
- Campaigns, historical migration, and Main's active frontier:
  [references/campaigns_and_migration_v4.md](references/campaigns_and_migration_v4.md).
- Blackboard or historical Pulse compatibility:
  [references/blackboard_graph_v4.md](references/blackboard_graph_v4.md).
- Explicit academic teaching/testing:
  [references/unified_learning_plane.md](references/unified_learning_plane.md)
  and [references/fact-graph-grilling.md](references/fact-graph-grilling.md).
- Reader export: [references/reader_html_export.md](references/reader_html_export.md).
- Architecture, release, installation, or performance repair:
  [references/capability_difference_audit.md](references/capability_difference_audit.md),
  [references/v5_release_traceability.md](references/v5_release_traceability.md),
  [references/phx_architecture_routes.md](references/phx_architecture_routes.md),
  and [references/administrative_cost_playbook.md](references/administrative_cost_playbook.md).

## Immutable authority boundary

The prospective truth path is:

`Research -> frozen package -> independent verifier decision -> Gateway Research certification`

Research, Evidence, Paper/Audit, Blackboard, Reader, Learner, CHX, PHX, and
attack proposals are nontruth. They never become premises by credibility,
repetition, ingestion, lint, audit, or presentation. Active legacy V5 Facts and
active Fact Alpha Research grants are the only premise authorities.

Every worker task card retains three communication planes: compact control, one
frozen mathematical-state view, and bounded narrative. The card is the
immutable capability boundary. Current task-referenced authority overrides
conflicting background prose. Historical artifacts remain readable and are
repaired copy-on-write, never rewritten.

## Legacy 0.x Fact admission

`selective-fact-checkpoint`, Candidate Release, Candidate adverse,
Certification Decision, and physical Fact-node commands remain available only
to read, audit, or complete already frozen 0.x authority. Do not start that
path for a new 1.0.0 certification. Its exact historical contract is retained
in [references/admission_contract.md](references/admission_contract.md).

## CHX and PHX

For runs started after the 0.4.1 activation boundary, start one task-scoped CHX
ledger before substantive project work. Project-bound ledgers live under
`PROJECT/chx-ledgers/`; projectless ledgers use private host task state outside
the skill. Historical runs must not be backfilled.

Record architecture-caused or materially amplified mechanisms, not ordinary mathematical difficulty. Tactical repair is only for a project run-local change
that remains project-local; coordinate related local repairs at its stage
boundary. Any repair intended for global Chalxius installation is an integrated
repair and uses the cross-ledger global path directly, including an explicitly
requested historical settlement. Validate every ledger and observed qualified
issue against one exact candidate; never manufacture tactical entries merely
to legalize global installation. Performance issues consult PHX before mechanism selection. Main
directly observes both worker progress and the elapsed duration of commands or
work units through ordinary visible host interaction. Main may reclaim or
redirect a worker that stops producing useful visible progress, and treats an
operation unexpectedly slow for its apparent complexity or a recent comparable
run as a diagnostic signal worth inspecting. This instruction creates no timer,
daemon, watcher, numeric threshold, heartbeat record, persistent performance
state, or lifecycle/admission gate. PHX is advisory and user
adoption remains explicit. A current card-bound worker ledger projects any genuine finding into
the project's small CHX observation inbox when the return is ingested; a pure
mathematical challenge creates no architecture observation. This replaces
reliance on host memory and does not create Blackboard, Pulse, scoring, or truth
authority.

Before a stage-wide repair or any claim that the project's CHX work is closed,
run `chx_ledger.py inventory --project-root PROJECT`. Treat issue identity as
`RUN_ID/CHX-NNN`: numbering is local to one predecessor chain. The read-only
inventory separates active issues, closed orphan issues, resolved successor
chains, and historical report-renderer compatibility drift; it never rewrites
old ledgers or reports. Its default output is bounded; `--full` exposes every
validated ledger and chain only for an explicit forensic need.

Before editing a proposed local Chalxius candidate, run its
`scripts/candidate_identity.py --root CANDIDATE --installed-root INSTALLED`
projection.  Main selects the source root from the reported canonical path,
VERSION, Git worktree/HEAD/dirty state, manifest validity, and installed-tree
difference.  Directory names and version-looking path fragments are diagnostic
only.  The projection is read-only and advisory: it does not switch branches,
rewrite manifests, choose a candidate automatically, or gate graph operation.

For a user-directed full historical settlement, `record-global-repair` binds
the complete qualified issue inventory, exact candidate root, version and
manifest, the revision-3 `covered_issue_snapshot_sha256`, one disposition per
observed issue, disjoint mechanism groups, and reproducible risk/regression
evidence.
Regression evidence must be a digest-bound `project:` receipt; candidate files
are implementation anchors only. `verify-global-repair` and every later
inventory read fail closed after covered-ledger, candidate-manifest, lineage,
or report drift. Exact retries are idempotent. The copy-on-write record lives
under `PROJECT/chx-ledgers/global-repairs/`, has no truth or project authority,
and never edits historical JSONL or architecture reports.
The inventory binds the exact bytes currently visible and may include open
ledgers; an open flag is not proof that a task remains active and is not a
global-repair gate. Independent open or abandoned ledgers remain visible, and
every issue already observed in them must still receive an exact disposition.
Closed parallel successor subtrees remain separate `RUN_ID`-qualified
projections; open parallel subtrees stay represented by their ordinary ledger
and chain snapshot. Malformed predecessor lineage or competing cross-branch
`supersedes` successors still fails closed. Candidate identity means the
complete exact manifest tree.
Anchors and evidence are candidate- or project-relative file references bound
to SHA-256; same-ledger or excluded `supersedes` relations never discharge an
earlier issue. A later valid zero-issue ledger does not stale an existing
repair, and an issue in a newly appended ledger remains uncovered until a
successor global repair covers it. Any later mutation of an open ledger whose
issues were covered naturally stales that exact covered-ledger snapshot; it
does not erase or silently hide the new bytes.
Historical global-repair candidate roots are immutable locators, not a demand
that every old worktree remain installed forever. Inventory parses a canonical
absolute historical locator even after that directory is archived, then marks
the old repair `stale` with a bounded reason. Recording or verifying the current
repair still requires the live canonical non-symlink root, exact version,
manifest bytes, manifest tree, and file set.

If `report_required=false`, do not surface CHX bookkeeping to the user. CHX is
never an audit warning, certification blocker, or reason to redo otherwise
valid work.

## Modes and project setup

Default to `auto` unless the user explicitly selects fast or deep. Modes affect
future exploration only. Missing source, replay, convention, quantifier,
atomic-DAG, adverse-disposition, or fresh-verifier evidence remains an explicit
Candidate or Certification blocker in every mode.

Initialize a writable project outside the skill tree:

```bash
SKILL_ROOT=/absolute/path/to/chalxius
MGRAPH="$SKILL_ROOT/scripts/mgraph"
PROJECT=/absolute/path/to/project
python3 -B "$SKILL_ROOT/scripts/self_test.py"
"$MGRAPH" --root "$PROJECT" --role operator init \
  --project-id PROBLEM_ID --title "TITLE" --reasoning-mode auto
"$MGRAPH" --root "$PROJECT" --role main audit
```

Mode switches append future-facing events. Abort an unfinished work unit only
through `work-unit-abort`; completed rounds remain historical. Read APIs never
repair caches implicitly.

## V5 Research cycle

1. Add cumulative Research with exact dependencies, sources, and artifact
   path/SHA/role capabilities. Finished external work enters Evidence, not Fact.
2. For a research draft, freeze the artifact, reconstruct the complete
   load-bearing target DAG, preserve its domain and quantifiers, and expose any
   weaker theorem as a typed gap rather than a solution to the original target.
3. Main reads the goal-aware frontier and actively names load-bearing Research
   IDs. When a Campaign has durable subgoals, bind each to one exact
   `research_goal` root and use its derived coverage to distinguish work already
   completed from the next production, return, supervision, repair, or semantic
   choice. For a named object/class/theorem, first run the exact search above,
   review completed work, and choose `related_research_ids`. Production never
   plans refute; exact IDs do not rebuild the global frontier; Main launches and
   confirms every planned worker, then uses genuinely independent current
   boundaries when visible capacity exists.
   Successive ranks, dimensions, charges, examples, or other discrete cases are
   mechanism probes, not a default progress ladder. Before raising such a
   parameter, Main asks whether the completed cases support a reusable lemma,
   invariant, obstruction, factorization, or induction interface and normally
   advances that mechanism-level statement. A higher case is selected when it
   is the cheapest bounded test of the proposed mechanism, locates its first
   failure, or supplies genuinely new geometry. This is a research preference,
   not a gate: Main may continue an important case calculation, but does not
   substitute mechanical coverage growth for progress toward the Campaign goal.
4. Logical components, not wall-clock barriers, determine supervision. A
   completed component may enter subround 2 while unrelated production
   continues. Use at most three failure-informed supervisors: `proof_logic`,
   `source_scope`, `program_math`, and `integration` only for a genuine
   cross-primary interface.
5. Completing one Research subround is not completing the host task. At that
   boundary validate the exact card, hash-bound Research product, supervision
   state, and affected local projection; treat a worker-ingestion receipt as
   optional provenance rather than a startup capability gate; do not automatically run a whole-
   project audit. Reserve the full audit for an explicit user request,
   Candidate/Fact or final-delivery boundary, shared-runtime change, detected
   drift, or a user-configured cumulative cadence. No fixed round-count
   threshold is implicit.
6. A supervisor challenge opens a later copy-on-write repair round. The repair
   Research stores its original worker mode. Its successor is a complete new
   product: prior defects are non-exhaustive seeds for fresh whole-successor
   review inside the exact scope, never the limit of that review.
7. New V5 Pulse planning is retired. The production/supervision cycle is the only prospective Research collaboration path.
   Existing historical Pulse records retain status, audit, dispatch, close, void, and abort compatibility.
8. Fact work is asynchronous. Main marks important Research while ordinary
   research continues, then freezes a useful multi-node package at a natural
   window. The Fact verifier is the one fresh correctness review; do not add a
   Candidate-adverse duplicate. Minor repair returns to the same verifier and
   fundamental repair returns to ordinary Research.
9. Generic actionable planning uses one exact workgroup and completion
   projection. Exact completed or duplicate work is omitted only
   from actionable views; original Research, provenance, history, and explicit-
   ID planning remain available. Main `memory-add` reuses identical unbound
   semantics across actor labels only for the current Main CLI role; actor text
   never grants that authority.

Admitted Fact dependencies are frozen premises, not default counterexample
targets. Exact contradiction evidence is routed separately for governed
reopening.

## Computation

Prospective computation is code-before-execution. Subround 1 returns exactly
`computation_source`, `computation_design`, and `computation_dependencies`.
Program-math supervision reviews those bytes before execution. A missing or
blocking disposition is checked before expensive artifact reconstruction, and
the exact authority is checked again under the final write lock.

For one bounded run, the default hard surface is one production validation path
plus the smallest independent mathematical check. Additional controls are
diagnostics unless a recorded failure family selects them. Every load-bearing
stage still binds formula, code anchor, domains, representation, truncation,
output interpretation, and replay. Multi-stage or resumable jobs use the
experiment layer; a one-stage exact script need not.

Before allocating code, name the open target node or explicit architecture
smoke-test purpose. A computation that merely reproduces an already available
derivation is advisory-eliminated, not sent through another gate stack.

## Sources

Load-bearing theorem/formula use requires exact source bytes, locator,
hypotheses, conventions, and applicability. Current erratum/retraction status is
optional metadata in ordinary Research: retain a negative status claim only
with an exact frozen response receipt. Otherwise mark it `not_assessed` or
`unresolved`; this alone does not trigger a repair cycle. Candidate and Fact
work may demand stricter current-status evidence when it is load-bearing.

## Candidate, verifier, and Fact

Candidate preflight binds exact statements, proofs, active predecessor closure,
sources, computation evidence, internal mini-DAGs, supervision, adverse work,
and dispositions. Send only the frozen verifier capsule to a fresh verifier.
The verifier returns review bytes but does not publish Certification.
`certification-record` is Gateway-owned and records one immutable decision;
Gateway separately revalidates and admits accepted Facts. Never weaken a
missing gate because a mode is fast or a result is plausible.

`validate-return` is one bounded read-only snapshot of the canonical return and
its declared artifacts. A transient `ENOENT` or `ESTALE` visibility failure
before that safe snapshot exists may be retried after the same paths stabilize,
without quarantine. An unsafe filesystem object or visible malformed,
hash-drifted, schema-invalid, or semantically invalid bytes remain fail-closed
and retain the ordinary local-quarantine path. Snapshot retry is not a worker
receipt or admission shortcut.

One Candidate command may reuse one ephemeral fully validated inspection
context across its immutable Research, adverse, and historical-runtime
projections. The context never persists across commands or mutation boundaries;
Candidate sealing recomputes live supervision under the final lock. Automatic
selection may form dependency-closed authoring batches, but it never atomizes
claims. Each later Fact must expose exactly one semantic conclusion, and any
multi-Fact batch requires explicit Candidate-DAG closure. A Main-approved batch
merge still requires the exact dependency and failure-surface checks recorded by
the selective checkpoint. New `candidate_fact` worker outputs are canonical-Fact
validated before ingestion; an exact repair specification, when supplied, is
hash-bound into both repair Research and its task card.

Candidate preflight rejects assurance cardinality, internal-edge, and exact
statement-interface mismatches from the submitted Candidate bytes before global
Research replay. This early projection is nonauthoritative: the complete
assurance validator still reruns after Research, source, artifact, predecessor,
and adverse closure. Manual or historical Research does not inventory
supervision rounds unless a selected constructive record actually carries
production-assignment provenance.

Active-Fact reconstruction uses one two-phase command-local projection. A
reentrant task-card check may read only locally hash-validated Release,
admission-marker, and admitted-Fact bytes; the outer frame then performs the
complete Research, runtime, Decision, successor, and lineage replay and rejects
any provisional/final drift. Approved-computation replay propagates the same
inspection context through its design, supervision, receipt, disposition, and
task-card closure. This is a recursion boundary, not an admission shortcut or a
persistent authority cache.

Workers report at most three deduplicated, well-supported concrete failure
families and their success boundaries. They do not author persistent attack
rules. Main may reject a report or synthesize one compact mechanism-level rule
for future work. Current rules use English internal prose, accept at most
sixteen active project rules, and fail closed on an oversized rule until Main
provides semantic compression; they are never truncated. This routing plane has
no truth or admission effect.

## Paper, Evidence, and Reader

Paper mirrors and Audit Graphs preserve exact source identity and immutable
correction lineage. Evidence import transfers source availability, never Fact
authority. Project background is optional nontruth context and must return to
exact sources for load-bearing use.

Generate Reader HTML only on explicit request. It is a deterministic,
presentation-only projection with visible native status; it writes nothing back
and has no truth effect.

## Chalxius Learner

Activate Chalxius Learner only when the user explicitly asks to be taught,
questioned, tested, guided through a paper, trained for an exam, or tracked for
mastery/review. Ordinary research, audit, or system testing does not activate
it. Frozen Fact, Paper/Audit, or Blackboard snapshots may be mounted read-only;
persistent learning evidence needs separate authorization and remains nontruth.

An already active read-only oral follow-up uses the bounded oral fast path in
[references/unified_learning_plane.md](references/unified_learning_plane.md).
An existing teaching Markdown edit may use the bounded document-edit bootstrap
only under its complete selector. Source conflict, fresh verification,
Research, truth-state mutation, persistent learning mutation, architecture,
publication, or nonlocal editing immediately restores the ordinary path.

The separate `$grill-me` companion is Grill Me Code and is code-only. It has no
Paper, Fact, Audit, Blackboard, or Learning Graph authority.

## Runtime, release, and installation

Runtime identity and archive records may explain where a card or release was
created, but they do not authorize or deny ordinary graph operations. Agents
continue a legacy graph directly when its content hashes, dependencies,
provenance, and workflow owner checks are valid; no adapter, migration copy, or
mode-init ceremony is needed merely to read or append graph work. Release and
rollback tools remain deployment diagnostics and must not become a second truth
path or a graph-operation gate.

Architecture releases use failure-informed validation: changed files, affected
boundaries, manifest/inventory, focused regression, self-test, and only the
broader suite justified by shared-runtime risk. Main selects one validation
profile per exact manifest; a successful forensic profile subsumes the routine
profile for unchanged bytes, and its receipt exposes elapsed and slowest-lane
cost. Install the validated candidate locally before publication. The sole public host-global path is
`scripts/local_install.py`: it validates one complete candidate tree, runs the
self-test and the two changed-surface regressions, archives the prior runtime,
atomically swaps `/Users/<user>/.codex/skills/chalxius`, and keeps one direct
rollback copy outside skill discovery. It never reads or mutates a project and
does not require a project audit, release matrix, or worker receipt. The older
`scripts/runtime_cutover.py` remains an explicit forensic/protected-project
deployment tool. For this release workflow, an explicit publication request includes merging the corresponding reviewed change into `main` by default; the user may explicitly exclude merge. Installation and publication remain separate authorizations, and publication never authorizes an unreviewed or unrelated change.

Installation, validation, packaging, publication, rollback, and CHX settlement
remain eligible CHX observation surfaces even when the release succeeds. For a
global repair, finish install-time observations, reconcile and close/report the
current ledger, then record and verify one global repair against terminal bytes;
a later publication finding starts an ordinary successor. This adds no
post-install ceremony, automatic issue generator, timer, monitor, or gate.
