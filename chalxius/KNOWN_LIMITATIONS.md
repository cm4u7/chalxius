# Chalxius 1.0.5 architecture findings and residual boundaries

This file is the release, nontruth disclosure for Chalxius 1.0.5
**Split Opt-In Repair**. It describes architecture defects,
integrated repairs, and intentional residual boundaries; it is not mathematical
evidence and grants no Research, package, verifier, Gateway, or Fact authority.

## 1.0.5 Split Opt-In Repair

Live use showed statement splitting becoming a default repair reflex: a
supervisor or packager could recommend `needs_split`, Main could immediately
create a schema-v3 repair, and the same repair could be scheduled later through
ordinary `plan-round`. Version 1.0.5 keeps the diagnostic and historical batch
interfaces but disables every new split production by default. Both the coupled
repair planner and the common production-round boundary now require exact
Research selection plus the one-shot `--user-authorized-split` choice after a
current explicit user request. The choice is not stored, inferred, or replayed.

This is an execution pause, not a Fact veto. Supervisors may still diagnose a
mixed node; packagers may select an alternative whole-node interface, ordinary
one-to-one COW, or leave the route unready. Regular proof/source supervision is
unchanged. Frozen split cards, returns, commits, ingestion, and commit-last
recovery remain readable so interrupted historical work is not damaged. Generic
frontier planning reports a selected split instead of silently skipping it.
No scheduler, compatibility layer, second graph, project migration, or truth
authority was added.

An already-created pending split task can be made operationally dormant with
the existing `blocked` Research disposition. The derived COW/frontier route
then omits only that productless task while preserving its exact history and
every already-published repair outcome. Resumption remains an explicit Main
choice and still requires a current user split authorization.

## 1.0.4 Frontier Context Handoff Repair

Live local-F0 use reproduced one composition defect in the 1.0.3 working
memory: a unique `plan-round` head replacement detached its exact-search
context, and an explicit reattachment left both an unattached and an attached
copy. Version 1.0.4 carries context across a unique replacement, leaves true
multi-successor ambiguity unattached, and absorbs an unattached duplicate when
Main chooses a concrete head. No mathematical state or authority changes.

The context-handoff maintenance prompt also keeps the asynchronous Fact window
visible without making every compaction dispatch work. Main carries `Fact
window clock: n/4`, increments it only on an explicit host compaction, resets it
after a completed packager window, and dispatches one small window at `4/4`.
User deferral preserves `4/4 deferred` until lifted. This recovery instruction
creates no timer, daemon, automatic scheduler, or package/certification effect.

## 1.0.3 Research Route Coordination Repair

Graph Browser and graphical graph generation are temporarily unavailable as
supported release capabilities. Historical or experimental Reader code,
assets, and command entries may remain installed, but their presence is not a
compatibility promise and Main must not rely on them until the browser is
redesigned. Research graph storage, exact search, Campaign/frontier operation,
supervision, and Fact certification are unaffected.

Large Campaigns exposed a common coordination failure: completed repair tasks
could remain active, exact-search discoveries disappeared after context
handoff, Fact importance marks looked like ready packages, and split products
did not carry a complete reviewable allocation of their real logical
relations. Source/proof ownership and the historical adverse-learning loop also
duplicated review work and made ordinary supervision harder to reason about.

The repair keeps one compact Campaign working-memory projection with exact
active heads, attached context, sparse landmarks, recent attainment, and rigid
COW/split navigation. Recent attainment follows context compaction or a natural
curation window, not a hard four-entry clock. Sparse landmarks have no count
quota and may grow with the Research graph. The separate recent-attainment
queue keeps up to 64 entries only as a high-water runaway guard; routine
mathematical summaries preview four recent items and eight landmarks while
retaining exact total counts and identity digests. Full landmark ids remain
available from exact state and diagnostic reads, so the preview never silently
becomes the complete set. Main retains semantic choice. Programmatic projection
follows only unique structural workflow lineage; ambiguity is shown rather
than guessed. Exact-search context is durable but has no dispatch or truth
effect. The live local-F0 Campaign was reconciled from generation 179 to 183:
completed repair heads were removed, true open branches remained visible, and
clean bypass or side-product results became explicit landmarks without being
promoted to the intrinsic A-model frontier.

Fact frontier now separates navigation beacons, packager route selection,
mechanical package proposals, sealed package readiness, certification, and
re-verification. `--target` requires `--campaign`; route-needing landmarks rank
ahead of already certified history, and the bounded display preserves complete
identity count/digest so a 256-item preview cannot starve later landmarks. The packager may
choose a bounded predecessor-closed route from sparse landmarks and current
Research, including necessary unmarked prerequisites; Main need not repeat the
same package membership. Unique repair chains resolve advisory-only. A split
shows its exact batch and requires explicit retargeting—there is no automatic
fan-out, verifier launch, or authority effect. Clean `ready`/`needs_split`
supervision is a strong recommendation for the mechanical path only.
A direct-Research plan freezes its `selection_mode` and exact Main anchors;
every sealed component contains one anchor and connects any additional unmarked
node to it through the component's actual package dependency edges. Existing
`--mark-id` plans remain `existing_marks` and are outside this direct-route rule.
`plan-fact-packaging` may return `mechanical_proposal_ready` with a
`mechanical_package_proposal` and digest, but it never seals. The packager seals
exactly once and may accept that proposal, supply an alternative six-field
interface, choose the whole node, or route the node to Research COW/split;
ordinary COW branch choice does not change the Campaign active head.
If the packager requests an actual split, package work pauses while a Research
repair worker produces the complete batch and the ordinary proof/source
supervision layer reviews it. There is no Fact-side split supervisor.

Current supervision replaces prospective adverse learning with fixed,
scope-owned, non-exhaustive review guidance distilled from historical cases.
Source scope owns external identity, bytes, locators, faithful extraction,
literal hypotheses and conventions, and evidence coverage. Proof scope owns
all mathematical correctness and theorem application. Both scopes normally
reuse one author-independent supervisor session while retaining separate
cards, reports, returns, and ingestion. Historical cases, proposals, decisions,
and rules remain readable inert nontruth; they neither route new work nor
become an allowlist.

For a semantic split, one repair worker chooses the actual finite member set
and proposes rigid `proof_dependency` or `context` relations with free labels
and rationales. Proof supervision checks every member/member and
member/external relation, searches for omissions, and returns the complete
recommended relation set matching each ready statement interface. Source supervision
does not certify proof dependencies. The same independent supervisor identity
may perform a fresh review of new bytes; a new person is not a validity gate.
The independent Fact verifier still rechecks every exact Research record,
packager-selected interface, and dependency edge as one capsule; Gateway alone
certifies.

Intentional residual boundaries remain. Main still decides importance,
mathematical completion, direction, and whether a context node becomes active.
Landmarks stay sparse. Fact packaging remains asynchronous. Full forensic audit
of a very large project remains slower than routine frontier use; no persistent
index, cache, timer, daemon, automatic worker dispatch, or compatibility layer
was added.

## Frozen release-history boundary

Every lower version section is a frozen account of the contract then in force.
Words such as “current”, “prospective”, “Candidate”, or “adverse” below are
historical within that named release and do not override the 1.0.5 prospective
route above. The old Candidate CLI is procedurally reserved compatibility for
explicitly selected 0.x completion/audit; the runtime does not authenticate
pre-1.0 provenance, and this release adds no provenance or identity gate.

## 1.0.2 Capability Budget Audit Repair

The bounded capability reader introduced in 0.7.16 correctly limited one
structured Repair closure to 64 MiB, but a full-ledger inspection reused its
byte counter across every historical Repair. Once unrelated valid manifests
collectively crossed the bound, traversal order selected a later batch for the
misleading `Research capability artifact drifted` error even though each
manifest was individually below the cap and every declared file still matched
its frozen SHA-256. This latent scope defect is not a 1.0.1 capability-schema
change and requires no historical-card migration.

The repair separates manifest-local budget accounting from the command-local
read snapshot. Independent manifests receive independent 64 MiB counters;
exact repeated path/SHA bytes are still read once per command, and one shared
path-to-digest map still rejects conflicting declarations. A fresh command
continues to perform lexical containment, no-follow regular-file reads, and
SHA-256 validation, while a single oversized manifest remains invalid. No
frozen Research, task card, round, artifact, Candidate, Certification, Gateway,
or Fact byte is rewritten. Installation and publication remain separate,
explicit actions.

## 1.0.1 Fact Alpha Field Repair

The first live Fact Alpha run exposed three coordination gaps. An empty overlay
did not guide Main toward byte-exact legacy root carriers; a Campaign-scoped
view did not explain that unbound shared marks were filtered; and prospective
supervision discarded the exact statement-boundary work that a later packager
had to repeat. The `verifier` role projection was also unusably empty.

The repair adds bounded zero-state advice only for legacy root Facts with one
unique non-adverse constructive Research product carrying the byte-identical
`candidate_fact` artifact. It never writes a mapping, mark, Campaign binding,
grant, or authority effect. Scoped views expose global/in-scope/filtered mark
counts. Prospective clean supervisors may optionally return a Research-hash-
bound `ready` interface or `needs_split` disposition; in 1.0.1 all-ready plans
sealed mechanically. The current 1.0.3 path instead returns a mechanical
proposal and leaves the single seal to the packager. Missing historical interfaces still require a human/agent
packager, which may author the interface or send the node to Research split/COW.
The mathematical split belongs to a Research repair worker following a precise
surface/dependency/residual brief, not to the packager and not to a mechanical
prose cut. Split products require a fresh whole-product supervision pass and
receive their interfaces from that pass, not the repair worker or old packager.
"Fresh" binds the review pass and the new product bytes, not the person's
identity: the same author-independent supervisor may be reused when it rereads
the complete product and searches beyond the previously reported defects.

Prospective schema-v3 repair cards may instead request
`output_shape="research_split_batch"`. Main freezes the old Research and the
split brief but not a guessed member count. One repair worker declares the
complete actual finite membership (two through 128 coherent successors) in one
return. Ingestion publishes immutable member records and a single assignment
owner, then writes one commit record as the visibility boundary. A missing
commit leaves those staged records outside Research frontier and Fact marking.
The committed membership is the unit of fresh supervision. Each scope keeps a
separate report and return, but proof plus source normally run sequentially in
one author-independent supervisor session and one host slot. Any optional
interface artifact must cover every successor.

The mathematical interface remains six semantic fields. Evidence locators are
not duplicated: Research `metadata.artifacts` is the only path/SHA layer, and
the verifier capsule carries the complete Research record. The verifier CLI
role owns only capsule, decision-record, and decision-check commands.

The split-batch protocol does not infer mathematical completeness, certify the
successors, or automatically move old/new Fact marks. The repair worker states
the completeness rationale and residual/open/abandoned material; fresh
supervision judges each resulting product. Legacy cards and ordinary
single-product repairs keep their frozen contract and are not retrofitted.

## 1.0.0 Fact Alpha

Fact Alpha is prospective. It does not infer a Research identity for the
existing admitted Fact corpus, so legacy Facts and Research certification
grants remain two readable authority representations during this release.
Only new certification uses the single-Research-graph model. A deliberate,
source-bound migration may be designed later; 1.0.0 does not guess one.

Research records created before 1.0.0 have no internal statement surfaces.
Certification therefore covers the whole top-level Research `claim` and exact
proof/support bytes. A mixed claim must first be COWed or split into complete
Research nodes. The packaging interface is a verified semi-formal calling
signature, not a locator into arbitrary prose.

The Fact frontier still scans the immutable Research envelope once to resolve
exact COW terminals. It reports elapsed time and scan counts to Main. It does
not add a persistent cache, timer, monitor, or background index. This favors a
single trustworthy projection over another mutable synchronization surface;
future performance work should be driven by observed large-project timings.

Fact packaging is not automatic. Main maintains sparse Campaign landmarks or
importance marks and recognizes a useful review window; an authorized packager
then chooses a bounded predecessor-closed route from the graph. This preserves
mathematical judgment and lets efficiency-first runs defer Fact work, but it
also means host instructions must actively revisit the frontier at natural
handoffs. Neither a landmark nor a mark is package readiness.

The bounded minor-repair lane requires an exact prior `minor_repair` decision,
a one-to-one complete-node COW successor for every affected node, complete
recheck of the component, and the same independent verifier. This is the
historical 1.0.0 fast-supervision promise, not a general supervisor role or
execution mode. Split, statement-surface, relation-allocation, or other
structural ambiguity returns to a Research repair worker and ordinary
proof/source supervision. It does not yet provide an automatic
mathematical classifier between minor and fundamental errors; that judgment is
the verifier's recorded conclusion. The Gateway remains mechanical.

Legacy Candidate Release, adverse, Certification, and physical Fact-node code
remains procedurally reserved for explicitly selected frozen 0.x completion or
audit. The runtime does not authenticate pre-1.0 provenance and installs no new
identity gate. Prospective Fact Alpha commands do not call that route. Removing
the historical surface would make existing authority inaccessible and is
outside this release.

The existing cross-project Fact Evidence import/export contract still carries
only legacy admitted Fact files. Research certification grants are validated by
the project audit but are not yet serialized as external Evidence. Extending
that boundary requires a complete grant-and-interface evidence capsule; 1.0.0
does not expose a half-upgraded import path.

## 0.9.18 Frontier Breadth Parity

The 0.9.17 representation regression proved that a compact synthetic entry
could retain sixteen heads, but the normal Campaign state reader,
`plan-round` advancement, manual reconciliation, legacy checkpoint reader, and
live goal projection still used independent literal limits of eight. A ninth
Main-selected branch could therefore be rejected or omitted by the ordinary
working-memory path even though the renderer had sufficient capacity.

The integrated repair uses one explicit sixteen-head limit across those read
and write surfaces and adds an end-to-end checkpoint→reconcile→plan-projection
regression. The limit is per Campaign Target and is independent of the routine
Target window. Derived successor fan-out remains bounded with full counts and
digests; `--diagnostic` retains forensic detail. Routine head claims expand
from 160 to 300 characters, root claims to 400, and projected historical
claims to 320. On the live local-F0 Campaign this increases the all-target
routine view from 29307 to 31693 bytes while spending the difference on
mathematical content. Exact Research bytes remain unchanged and retrievable by
id. No pager, automatic head selection, scheduler, compatibility layer,
Candidate effect, or Fact effect is introduced.

## 0.9.17 Stepping-Stones Continuity

The 0.9.16 goal-count bound left a representation-level residual: one projected
goal still copied overlapping route summaries, terminal/evidence sets, hashes,
empty fields, and synonymous state into every active-head action. The local-F0
routine frontier therefore remained much larger than the Main decision it
represented.

The integrated repair retains every active head and supervision scope while
reducing each ordinary action to concise mathematical identity, current-route
Research ids, next action, and exact actionable Research/round ids. Full
forensic fields remain in `frontier --diagnostic`. The candidate reduced the
live one-goal projection from 19797 to 13462 bytes and the eight-goal projection
from 40485 to 29306 bytes. Frontier still builds the global Research envelope
and takes roughly 2.3–2.8 seconds on this project; no persistent index or
parallel scan is introduced. The ordinary target default is twelve and a
16-active-head regression remains lossless; `--limit` controls targets, not
heads within a target.

The release also names **摸石头过河** as a Main continuation rule around material
architecture failures. It is an instruction to preserve and resume exact graph
state, not an automatic failure detector, scheduler, timer, installer,
publication action, lifecycle gate, Candidate effect, or Fact effect.

## 0.9.16 Bounded Research Coordination

Three live-research defects had independent symptoms but one practical cost:
Main was asked to reconstruct state already present in exact graph bytes.
Default supervision planning could reselect an applicable scope already
reserved or completed; routine `frontier --limit N` still expanded every
Campaign goal before truncating the visible surface; and a task card could
declare exact `authoritative_source` bytes that source-assurance recognized but
return validation did not.

The integrated repair subtracts exact completed or in-flight supervision
coverage before a default plan and returns an informative no-op when nothing
remains. Explicit scope requests, exact retry, and conflicting overlap remain
fail-closed. Routine frontier now bounds the complete nested Campaign goal
projection while preserving full counts, digests, projected ids, and concise
mathematical summaries; explicit diagnostic mode retains the full topology.
Finally, assurance production and return validation share one structural
direct-source role predicate covering the historical standalone `primary`
token and exact `authoritative_source` semantics, but not computation,
analytic, secondary, or concatenated lookalikes.

The routine frontier still builds the existing global Research envelope, so
this is not a persistent index or universal store-scan elimination. Main still
chooses mathematics and dispatches workers. No scheduler, pagination layer,
compatibility adapter, Research status inference, Candidate effect, or Fact
effect is introduced.

## 0.9.15 Frontier Exact Workflow Identity

The Campaign frontier previously used a semantic COW terminal as the
operational workflow root of the earlier workgroup it completed. When that
terminal belonged to a distinct repair assignment, the older head inherited
the repair's round, product, component, and supervision. Main could therefore
see a mathematically unrelated product in place of the exact product that had
actually been produced and challenged.

The integrated repair limits COW terminals to completion and ambiguity. The
action projector derives workflow state only from the physical workgroup
members, while retaining the existing exact product-to-source assignment
redirect when its frozen provenance validates. The live local-F0 canary now
maps `ad2545c15572` to its true product `565fb0655309` and production round
`round-20260828T023255Z-bd8f8f93`, not the unrelated `e3ebd063441b` route.
COW topology, historical landmarks, explicit Main choices, and all truth
boundaries are unchanged. No scheduler, compatibility layer, Candidate effect,
or Fact effect is introduced.

## 0.9.14 Typed Supervision Coverage

The ordinary frontier previously caught a readable missing supervision scope
under the same generic `supervision_result_lineage_unreadable` label used for
malformed or inaccessible bytes. Main therefore had to reconstruct exact scope
coverage manually and could repeat a completed review or misclassify ordinary
unfinished work as corrupted lineage.

The integrated repair extracts one structural coverage reader shared by the
Candidate gate and frontier. It reports each applicable production component
and scope as completed, missing, pending, conflicting, or unsafe, including the
exact result and round ids needed for Main's next action. Truly malformed or
inaccessible bytes remain unreadable. Candidate construction remains strict:
every applicable scope still needs exactly one completed, ingested result.
There is no scheduler, automatic dispatch, compatibility layer, new receipt,
Research effect, Candidate effect, or Fact effect.

## 0.9.13 Repair and Review Lineage

Two field failures came from treating descriptive relation vocabulary or one
trigger author type as workflow capability. First, a valid structured repair
triggered by Main's exact synthesis of multiple supervisor results remained
parallel to those results, so frontier kept the repaired ancestor and old
challenges actionable. Second, a reviewer session could be reused across
scopes without Main seeing which production assignment authored the attacked
product. A related historical mismatch required source-receipt ids to equal an
entire supervision plan's related-id set even though the write contract permits
additional exact review context.

The integrated repair uses the existing typed gear train: assignment
provenance identifies products and review results; a challenge record plus its
validated supervision binding identifies the plan; and `kind=repair` plus
exact repair-of, trigger, source, related ids, Campaign, and chronology
identifies a structured repair. Relation strings remain descriptive. A Main
synthesis trigger advances only when its complete research-source set exactly
matches its related ids. Workgroup completion remains narrower: the source
must be a complete production product and the repair objective must remain
hash-bound; the repair's own product and supervision are still required.

`round-status` exposes attacked source assignment/product ids for Main's live
reviewer comparison. It deliberately cannot authenticate a live agent and does
not block or dispatch anything. Main may reuse a genuinely independent reviewer
across scopes and COW stages, but not across the attacked product's author
boundary. The old disposed local-P2 repair remains noncurrent, and malformed,
ambiguous, cross-Campaign, or backward-time shapes remain pending. No identity
registry, new relation vocabulary, compatibility layer, Candidate effect, or
Fact effect is introduced.

The first integrated-install attempt also exposed a false positive in exact
runtime-tree validation: two empty `__pycache__` leaves contained no bytes but
were treated like unmanifested files. Runtime identity has always been bound to
manifest files, so the validator now ignores only byte-free interpreter-cache
leaves. A cache containing any file, an unexpected nested tree, or any other
unmanifested file still fails before installation; historical archives remain
manifest-only and sealed.

## 0.9.12 Frontier Lifecycle Closure

Three field defects remained after 0.9.11. First, an exact historical COW chain
could still appear pending because its Main-authored repair root predated the
dedicated `kind=repair` metadata shape. Second, a multi-head goal could display
`needs_main_choice` even though Main's latest exact branch was already
`await_return`. Third, bounded frontier work still reread a Research file after
the same command had already hash-validated and parsed its immutable envelope.

The repair recognizes only the complete legacy relation/source/product/
challenge/Campaign/dependency/chronology shape, gives real in-flight work
foreground precedence while retaining every sibling action, and reuses the
command-local envelope bytes while rerunning full record and artifact
validation. It neither rewrites old Research nor deletes a branch. Ambiguous
legacy shapes remain pending.

One operating defect was procedural but did not justify another protocol:
Main could mistake a tool's intermediate yield for successful blank stdout and
retry a planner whose original process was still running. Current instructions
require resuming the same session; only a completed command with missing or
invalid required output is defective. There is no retry service, receipt gate,
monitor, compatibility layer, or new lifecycle owner.

## 0.9.11 Frontier and Source Continuity

Large Campaigns exposed three coupled navigation defects. Routine frontier
rows repeated deep diagnostic topology after their actionable and
mathematical content was already present; a target-bound production selection
could fail to retire an old head when the bridge ran through completed
terminal products or reviews; and batch round discovery treated an abandoned
private atomic-staging directory as a public round. The repair keeps bounded
current, recent, and historical mathematics, extends exact handoff through
terminal lineage, and distinguishes narrowly named private staging from
visible malformed entries. None of these projections chooses mathematics or
changes immutable history.

A separate source-continuity defect arose when a downstream production cited
an upstream product or its proof review but did not repeat the upstream
source-scope sibling. New source-scope planning now follows only that explicit
workflow provenance to completed source reviews, carries the review Research,
and projects only primary hashes listed in its `source_uses`. It does not scan
the project for semantic similarity, copy every old capability, or require a
redo. The focused 42-test surface and the complete 1,041-test suite pass; two
unrelated tests remain intentionally skipped.

## 0.9.10 Terminal Seal Hygiene

The terminal seal correctly bound the exact return and artifact bytes, but its
tree-set check also treated Finder's writable `.DS_Store` as sealed authority.
Browsing one terminal directory could therefore invalidate its production and
every dependent supervision, Research ledger, novelty ledger, and audit
projection even though all expected SHA-256 values still matched.

Terminal validation now excludes only regular `.DS_Store` files at the bundle
root and its sole expected `artifacts` directory from the authority inventory.
The no-follow tree walk still rejects symbolic links, special files,
multiply-linked files, device crossings, and unexpected directories. Unknown
regular files still change the exact file set; every seal, return, and artifact
must remain read-only and hash-exact. No historical product is rewritten.

The live local-F0 project retained the original `.DS_Store` and passed a fresh
candidate audit with `current_ok=true`, no workflow or graph errors, and clean
history in 15.66 seconds. This is a host-metadata boundary repair, not a new
compatibility layer or a relaxation of mathematical authority.

The same project exposed a separate frontier performance defect: a bounded
`--limit 8` read rebuilt the complete Research COW/repair adjacency once per
workgroup and revalidated identical assignment products and ingestion receipts
inside one command. The repair shares one ephemeral inspection context across
that exact command snapshot, memoizes exact successful bindings and completion
states, and clears the relevant state at Research or round publication. It
creates no persistent index, cache file, daemon, scheduler, or new gate.

On the local-F0 canary, six alternating warm runs preserved the exact output
SHA-256 and reduced median elapsed time from 2.4116 to 1.8115 seconds. A profile
reduced Research repair-continuity checks from 8,758 to 151 and ingestion-
receipt validations from 327 to 60. These measurements establish the repaired
repeated-work mechanism on that snapshot; they are not a universal latency
guarantee.

## 0.9.9 Frontier Successor Handoff

The 0.9.8 working state could retain an old active head when Main deliberately
planned a positive descendant while the old product's supervision was still
running. Once supervision ended, an unsafe or counterexample product could
turn that retained head into `main_reconciliation`, causing the target to say
`needs_main_choice` even though the new round was visibly awaiting return.

Planning now treats the selected Research's exact positive dependency relation
as Main's branch handoff. It retires only an active route intersecting that
dependency, retains unrelated parallel heads, and leaves the old supervision
in the ordinary workflow projection until it is ingested. Nonadvancing
challenge, investigation, repair-response, and disposition relations do not
perform this handoff. No automatic mathematical choice, workflow gate, or
truth-stage effect is introduced.

## 0.9.8 Frontier Working Memory

The 0.9.7 Campaign frontier still required Main to repeat one semantic choice:
after exact target selection and round planning, a separate checkpoint write
was needed before the chosen work became the active head. On large and
branching Campaigns this could leave planned work outside routine working
memory or make stale heads invite duplicate research. The repair binds one
explicit target to production planning and atomically advances a compact
replaceable nontruth state. It stores only bounded Research ids for active
heads, recent attainment, historical landmarks, and recovery roots. Canonical
Research remains the owner of mathematical content.

This working state is navigation, not history or authority. Exact Campaign
events and immutable Research remain intact; malformed state falls back with a
diagnostic, and Main retains sparse branch/history curation. Advisories ask
Main to inspect accumulated mathematical progress but do not decide which
result matters, launch work, close a goal, or affect Candidate or Fact status.

A source-scope field run also showed that files declared inside structured
source evidence lost their primary-role token when projected into a supervisor
card. Their exact path and SHA-256 remained present, but direct source use was
incorrectly rejected. The projection now retains `primary_source`; the
existing exact containment, byte hash, source-use, and obligation checks remain
unchanged.

## 0.9.7 Frontier Continuity

The 0.9.6 decision surface could stop too early on deep legacy repair/COW
lineage, classify an already ingested product as a fresh production task, and
let goal-unmapped historical Campaign items consume the complete bounded Main
queue. It also left candidate selection vulnerable to stale directory names
and allowed mechanism-worthy observations to remain only in conversation
memory after reconnect or compaction.

The integrated repair follows exact task bindings and narrowly recognized
legacy repair relations, keeps in-flight supervision attached to its stable
workflow root, and separates active-goal work from bounded unmapped attention.
A read-only candidate-identity projection reports exact manifest and worktree
state; concise Main guidance recovers CHX observations across continuation
boundaries. These surfaces remain advisory. They do not infer mathematical
relevance, select or dispatch work, mutate Campaign or Research state, create a
monitor or compatibility layer, or affect truth authority.

Self-test reports the current SKILL line count as a context-cost observation
but no longer turns an arbitrary formatting threshold into an installation
gate. Exact manifest, metadata, behavior, and authority checks remain strict.

Post-install generation-45 use exposed a residual of the earlier compact
frontier repair: semantically correct default goal rows still copied their
complete diagnostic successor trees, and Campaign status retained twenty
recent event summaries in addition to the latest checkpoint. Routine goal rows
now preserve the exact action, head-to-root mapping, current route/terminal ids,
round, replay argv, freshness, and Main disposition while `--diagnostic` owns
the repeated per-branch hashes and topology. The ordinary status tail is eight
event summaries; complete immutable history remains available for exact
forensics. This is an output projection only, not a score cutoff or work gate.

## 0.9.6 Frontier Freshness

Installed 0.9.5 made exact attained-checkpoint successors visible but did not
tell Main when a checkpoint's active heads had themselves become stale. It also
kept ordinary `search` and `show` Fact-only and let one target diagnostic mark
unrelated Campaign rows malformed. The successor repairs all three on existing
read surfaces: typed Main navigation includes immutable Research; stale heads
expose productive current routes separately from clean review evidence; and a
bounded refresh recommendation remains advisory and nonmutating. Exact legacy
COW edges do not need a later optional repair-spec field merely to be visible.

Main still owns semantic selection and checkpoint authorship. The runtime does
not continuously refresh Campaign state, infer relevance, dispatch work, or
add a monitor, scheduler, persistent index, compatibility layer, Candidate
condition, or Fact gate.

## 0.9.5 Exact Frontier Context

Campaign checkpoints remain Main-authored advisory records rather than
self-updating pointers. Their read projection now exposes exact uncheckpointed
terminal workflow successors, which prevents an attained but stale root from
hiding later production or supervision. The output is deliberately bounded and
nonselecting; Main still judges mathematical relevance and direction.

Exact Research ids named in a selected source's prose are now directly frozen
as predecessor context only when the corresponding current Research exists and
validates. This removes a brittle dependence on one structured field but does
not interpret vague prose or infer relevance. Historical cards are unchanged.

## 0.9.4 Campaign History Compaction

Long Campaigns remain append-only and may grow without an event-count limit.
The former planning envelope copied every historical update into every round,
so a healthy Campaign eventually crossed a 256 KiB cap and could no longer
enter production or supervision. New scope-2 snapshots freeze only active
current semantics and an ordered history-prefix commitment. Tail append stays
valid; prefix rewrite, reorder, and truncation fail closed. The cap remains a
guard on anomalously large current state, not on project age.

Routine `campaign-status` is one bounded current view rather than a history
browser: it includes the latest minimal frontier checkpoint and a fixed recent
event-summary tail. There is deliberately no paging or cursor protocol. Exact
old bytes remain readable at `campaigns/CAMPAIGN_ID/events.jsonl` for targeted
forensics. Future checkpoints store only routing identifiers and a concise
Main disposition; existing verbose generations are neither rewritten nor
deleted. Copy-on-write repair rounds now inherit the repaired Research's exact
Campaign together with the repair node and never infer `ACTIVE`. Main's worker
opportunity instruction is also narrowed: parallel mathematical production
and review should use genuine independent slots, while ordinary engineering is
delegated only when its coordination-adjusted critical path is shorter.

## 0.9.3 Integrated Frontier Cleanup

Six field CHX defects are repaired together: Main's exact selection is
frozen in new production manifests; Research and Campaign binding is atomic;
frontier rows expose compact next attention and semantic disposition; live
supervision is visible before the new-supervisor safety recommendation; the
parallel Brave Future/goal-intake command family is removed without aliases;
and CHX ledger liveness is explicit, bounded, and administratively disposable
by content-addressed copy-on-write records. Administrative ledger disposition
never resolves or hides an issue and is excluded from the global issue
snapshot hash. Existing Research, rounds, products, Campaigns, Candidate
Releases, decisions, admissions, and Facts are not rewritten.

Final validation exposed three release-integration CHX findings before
installation: one behavioral feature reused a test for two distinct probe
roles; the capability/behavior registries omitted or misbound new public
surfaces; and all new mutants were initially placed in the bounded routine
semantic profile. The candidate now has distinct positive/predicate-false/
tamper probes, zero topology or behavior orphans, a 32-mutant routine semantic
profile, and a complete 144-mutant forensic registry. These repairs simplify
release evidence; they add no runtime gate or truth authority.

## 0.8.12 Semantic Recovery

Frontier completion now follows an exact command-local COW lineage and projects
one unique current terminal result back to the original workgroup. An exact
later invalidator reopens the work; malformed, incomplete, cyclic, or ambiguous
lineage cannot hide it. This does not infer COW from prose or broad contextual
links and does not rewrite frozen Research.

Main owns exact cross-round search and final dispatch. It uses real independent
work when visible slots exist, and reconstructs agent/return/ingestion/round
state after a client reconnect. These are ordinary agent instructions, not a
slot quota, filler-work policy, monitor, timer, scheduler, receipt, reconnect
gate, compatibility layer, or truth gate.

## 0.8.11 Agent Judgment Integrity

Main no longer treats artifact silence, one quiet wait, elapsed time, context
compaction, bounded startup reading, or deep reasoning as proof that a worker
is lost. Before interruption or reassignment, Main uses fresh ordinary host
status, messages, tool errors, and round bytes. Repeated no-useful-output
milestones may justify reclaiming a live but unproductive worker; loss requires
an explicit disconnect/error or sustained total nonresponse corroborated by
more than artifact silence. This is agent judgment, not a timer, heartbeat,
watcher, receipt, recovery state, or gate.

A copy-on-write Research successor is treated as a new complete product in
every assigned supervision scope. Prior defects and repair obligations seed
the attack but do not form a defect allowlist. The supervisor freshly checks
the whole exact successor and conserved in-scope claims for new, inherited,
repair-induced, and cross-component defects. PHX limits architecture ceremony;
it does not limit mathematical, source, integration, or program scrutiny.

The public architecture, use-case, release-lock, and checksum projections are
also rebuilt from their current owners. This removes stale verifier/Gateway,
Pulse, repair-route, background-loading, and archive-member claims without
adding a second authority path or compatibility layer.

## 0.8.10 Semantic Frontier Control

Main's explicit load-bearing selection now includes one bounded semantic
discipline for a frontier stated as a specific named object, class, theorem, or
exact identifier. Before freezing a card, Main searches exact Research over
the subject's stable names and identifiers, reviews matching completed
production, copy-on-write repair successors, and applicable completed
supervision, and then chooses the relevant `related_research_ids`.

This is an instruction-surface repair for stale named-frontier selection. It
does not infer relevance, automatically expand or choose work, run a
whole-project audit, add fuzzy matching, persist an index, create a receipt or
lifecycle state, schedule a worker, or gate Research or Fact authority. Main
may omit irrelevant matches and remains responsible for the final frontier.

## 0.8.9 Frontier Reliability

Ordinary and Brave Future actionable views now consume the same command-local
exact-workgroup and completion projection. Exact duplicate work receives one
deterministic actionable representative, and a workgroup closed by a valid
production product plus its applicable completed supervision is not presented
as new work. History still exposes every immutable Research record and its
provenance; no old Research or task card is rewritten. Exact related Research
inputs remain part of work identity because they feed task-card and
supervision authority; different related-input sets are never collapsed.

Prospective Brave Future projection writers emit
`chalxius-bf-frontier-projection-3`; frozen v1/v2 projections remain readable
as immutable history and are never upgraded in place.

`limit` now bounds the serialized entry and member windows instead of allowing a
small request to emit a fixed broad projection. Full-set identity is retained
compactly by count and digest, and a plan with zero active proof targets decides
that condition before opening a Fact inventory. These are command-local work
eliminations, not a persistent cache, index, timer, watcher, migration,
compatibility adapter, or lifecycle gate.

Source assurance is now selected from structured work semantics. Literature
mode, source-dependent metadata, source/applicability obligations, and exact
primary-source capabilities activate `source_uses` and exact obligation
coverage even when incidental logic-signal prose is empty. Current cards get
the stronger applicable contract; frozen historical cards remain byte-exact
readable and are not backfilled. This validates source-use evidence structure,
not the truth of the cited theorem or its mathematical application.

## 0.8.8 Direct Graph Operations

An admitted Fact is now directly operable as its own graph node. Ordinary
Research validates only the exact Fact premises it consumes through their
immutable local Release, acceptance marker, Certification Decision, acceptance
event, statement interface, Fact bytes, and revocation visibility. It no
longer replays unrelated admissions or historical Research already settled at
admission. Explicit Fact-closure reconstruction and attack-target work retain
the broad path, so this work elimination does not weaken their mathematics or
authority checks.

Frozen primary sources are also directly operable. A task-card related
artifact whose role contains the standalone token `primary` may be named by
`source_uses` without copying its bytes into the return. Returned artifacts
remain valid source capabilities; toy checks and stronger-target bridges remain
return-bound. Thus existing canonical returns and future direct-primary returns
follow the same semantic capability union, with no version branch, migration,
compatibility layer, receipt gate, or new lifecycle state.

The current local-F0 canary projected two exact Fact premises in about 0.003
seconds without constructing the broad active-Fact projection. A historical
canonical return revalidated, and the same frozen task card accepted its
primary TeX hash without a copied primary artifact. These measurements are
diagnostic observations only, not thresholds or mathematical evidence.

## 0.8.7 Main Observation and CHX Snapshot

Main now receives the complete lightweight performance instruction: directly
notice both visible worker progress and the end-to-end elapsed time of commands
or work units already exposed by the host. Unexpectedly long duration relative
to apparent complexity or a recent comparable operation is a diagnostic signal
to inspect for repeated validation, broad rescans, or idle work. It is not an
automatic failure, timeout, or admission decision.

This closes an instruction-surface omission in 0.8.6. It adds no timer, daemon,
watcher, polling loop, heartbeat, numeric threshold, persistent performance
state, receipt, lifecycle state, or mathematical gate.

Global CHX repair no longer treats every unclosed foreign ledger as proof of
live work or as a prerequisite that another task must close. One repair binds
the exact current inventory and every issue already observed, including issues
inside open or abandoned ledgers. If a covered open ledger later changes, the
old covered-ledger snapshot becomes stale and the new bytes remain visible for
an incremental successor. Malformed lineage, report drift, incomplete issue
coverage, competing cross-branch `supersedes`, candidate drift, and evidence
drift still fail closed.

Four reproduced runtime costs are removed at their existing owner boundaries.
An independent Research append with no Fact dependencies no longer reconstructs
the unrelated active-Fact lineage. A selective checkpoint reuses one
command-local inspection across its explicit targets; the field five-target
canary fell from about 82.9 seconds to 3.01 seconds. Exact supervision retry
filters unrelated manifests and returns the existing round before rebuilding
planner Research; the same field retry fell from roughly 10--17 seconds to
1.63 seconds. A historical partial-supervisor Research replay also completed a
new round in 2.40 seconds on an APFS clone. These are local diagnostic canaries,
not timing guarantees, persistent caches, automatic pass conditions, or truth
evidence.

Supervision capability closure is now scope-sensitive. Proof-logic,
program-math, and integration cards bind the exact production card, applicable
output artifacts, and active Fact premises without copying source-only
baseline bytes; source-scope cards retain the exact source capability closure.
Artifact capability is also decided by exact project-relative path, SHA-256,
and role structure rather than a historical assurance-revision label. Exact
legacy declarations therefore remain usable directly, while missing,
malformed, unsafe, or hash-drifted bytes still provide no capability.

For ordinary content-addressed capabilities, byte identity is authoritative.
FileProvider/APFS mtime or ctime changes during an unchanged read no longer
create false artifact drift; device, inode, file type, size, containment, link,
and final SHA-256 checks remain exact. Current worker bootstraps also invoke the
selected skill root's executable `scripts/mgraph` shell entry directly. They do
not pass that shell entry to Python or assume a global `mgraph` PATH alias.

## 0.8.6 Bounded PHX Repair

Load-bearing selection and execution are now stated as separate Main
responsibilities. Main explicitly names the Research ids, then treats planning
and immutable card creation only as preparation. Main must launch each worker
through the host and confirm the start. No durable dispatch receipt, scheduler,
compatibility shim, or additional mathematical gate is introduced; direct OS
process identity remains a cooperative host boundary.

Candidate Fact authorship is producer- and container-neutral. Main may author
canonical Fact bytes, seal them in a Candidate Release, and select that
canonical Fact file, while actor and provenance metadata remain nontruth
lineage rather than correctness evidence. The current Main-only form is
`prepare-candidate-adverse-target SELECTED_RESEARCH_ID --candidate-fact PROJECT_RELATIVE_PATH`.
It fixes `actor="main"`, accepts no `--actor` override, canonical-validates and
consumes those exact project-contained bytes, and
derives every applicable completed supervision id for the selected Research;
the valid set may be empty only when no supervision scope applies. The command
still creates nontruth preparation only. Adverse review/disposition, a fresh
verifier, Gateway-owned `certification-record`, and Gateway admission remain
mandatory and separate.

Canonical return validation observes one bounded snapshot. A transient
`ENOENT` or `ESTALE` before a safe canonical return/artifact view exists may be
retried without quarantine. Unsafe filesystem objects and visible malformed,
hash-drifted, schema-invalid, or semantically invalid bytes remain fail-closed
and locally quarantinable. Filesystem visibility can still fluctuate outside a
single snapshot; retry does not attest to worker identity or mathematical
quality.

Performance observation is deliberately an ordinary Main-visible instruction.
Main may reclaim or redirect work that stops making visible progress, but
Chalxius supplies no timer, daemon, watcher, heartbeat, numeric threshold, or
persistent performance state. PHX remains advisory; this repair does not turn
performance guidance into lifecycle or admission authority.

## 0.8.5 Terminalized Worker Lifecycle

After the immutable terminal seal is published, V5 performs a copy-on-write
terminalization of the assignment-owned return, artifact, and work paths. The
canonical successors are rebuilt from sealed bytes and made read-only; the
detached worker paths and their hash-bound marker are nontruth recovery data.
This projection is best-effort and replayable after the Research product and
receipt are written, so a host filesystem race cannot become a mathematical or
admission gate. Ordinary stale direct writes therefore fail without changing
the sealed Research authority. A worker holding an already-open writable file
descriptor or an uncooperative process can outlive filesystem permissions;
Main must reclaim that worker, and the shared returns parent remains a known
atomic-replacement boundary. Neither limitation changes Research, Candidate,
Certification, Gateway, or Fact ownership.

## 0.8.4 Semantic Graph Handoff

Candidate Release now closes only the explicitly selected constructive branch,
its responding adverse work, and completed supervision products. Generic
historical `related_research_ids` remain readable provenance but do not expand
a local Candidate into administrative project history.

Source-scope supervision recognizes exact path/hash source declarations by
semantic shape. Canonical, compact, and historical path field spellings are
accepted only when every declared concrete file has the same SHA-256. A locator
alone remains non-authorizing. Historical Research, cards, source evidence,
Candidate Releases, Decisions, admissions, and Facts are not rewritten.

## 0.8.3 Canonical Handoff

The worker/Main hash-transcription defect is repaired at the interface boundary.
Workers still declare an explicit final handoff, while Main derives the return
hash from the canonical bytes it reads. A legacy supplied hash remains an
optional equality assertion. Receipts retain the derived hash so tampering,
replay, and byte drift remain visible. The remaining boundary is intentional:
the worker must still identify the assignment and declare `status="final"`;
file appearance alone is not a final handoff.

## 0.8.2 Explicit Route Boundaries

`route_invalidations` now names exact stale Research targets only. A broad
`related_research_ids` reference may record source, provenance, context, or an
ordinary dependency, but it no longer transmits route staleness to every later
record. This prevents false hiding of independent Research while retaining the
explicit invalidator and the stale status of the named target.

The routine global installer is deliberately narrow. It validates the full
candidate manifest, self-test, and focused regressions, then archives and
atomically swaps the discovery runtime with one direct rollback copy outside
skill discovery. It does not inspect or alter projects. Protected-project
cutover remains an explicit forensic option, not a default installation gate.
The residual boundary is intentional: exact-target invalidation cannot express
a future transitive semantic invalidation relation until that relation is
modeled as its own explicit graph edge and tested independently.

## 0.8.1 Scoped Candidate Adversity

Fresh Candidate adverse obligations are no longer inherited from arbitrary
historical `related_research_ids` ancestors. A current Candidate derives them
only from its explicitly selected, constructive Research heads whose own
metadata literally requires independent adverse review. If several such heads
are selected, the target set is reduced to maximal selected heads. The actual
review remains strict: it must directly respond to that target, bind the exact
Candidate Fact bytes, use an independent actor, carry a valid disposition, and
remain excluded from the verifier. Historical readiness revision 1 records
remain readable; newly created readiness records use revision 2.

This is a scope repair, not a relaxation of Fact authority. It removes only an
unrelated administrative inheritance path and introduces no new state,
receipt, planner, cache, or truth route.

## 0.8.0 MathGraph First

Cross-version operation is carried by the MathGraph: node and edge content
hashes, dependency references, creation/session provenance, workflow stage, and
owner boundaries. Runtime identity, installation paths, historical archives,
and obsolete receipts are diagnostic provenance only. No runtime-compatibility
closure, legacy adapter, migration copy, compatibility database, or second
graph data plane is required for ordinary graph reads, Research continuation,
or append-only nontruth writes.

The simplification does not weaken mathematical safety. Malformed graph state,
hash drift, missing dependencies, wrong-stage artifacts, failed adverse or
verifier work, and Candidate/Certification/Gateway/Fact authority violations
still fail at their owning boundaries. Release and rollback tools remain
deployment diagnostics and do not authorize graph or Fact operations.

For this release workflow, an explicit publication request includes merging
the corresponding reviewed release change into `main` by default unless the
user explicitly excludes merge. Installation remains separately authorized;
publication never authorizes an unrelated or unreviewed change.

## Historical 0.7.16 Bounded capability hygiene

The current overlay keeps repair capability bytes inside one command-local,
content-addressed inspection context, applies a 64 MiB aggregate byte cap, and
performs a fresh no-follow read across every mutation boundary. It also rejects
the newly introduced C0 control-byte family prospectively for textual worker
artifacts while preserving frozen 0.7.15 card behavior and binary artifacts.
Python entrypoints disable bytecode emission before imports; package startup
hygiene is limited to the interpreter's own cache and never changes project
records. These are runtime-hygiene repairs only: they do not add a truth path,
authority cache, scheduler, Candidate gate, or Fact admission shortcut.

Project CHX inventory now treats fully closed parallel successor subtrees as
independent qualified chains instead of rejecting concurrency as a lineage
fork. The topology is digest-bound. Active or malformed subtrees, missing
predecessors, cycles, and competing cross-branch `supersedes` successors remain
fail-closed. This changes lifecycle accounting only and does not reinterpret
historical issue contents.

The 0.7.16 release remains nontruth architecture work. Existing historical
ledgers and reports stay immutable. Project-run-local repair may use the
per-ledger tactical/integrated route; globally installed repair uses the direct
copy-on-write global integrated route without a tactical precursor.

## 0.7.15 Research obligation closure

Field run `run-20260813T182913219213Z-39649c18119c` first recorded the two
mechanisms under task-local identifiers `CHX-001` and `CHX-002`. Those private
identifiers are source evidence only and are not published as a second issue
numbering domain. Public release successor
`run-20260813T234901055084Z-22649ebe6545` inherits the immutable lineage through
`CHX-031` and owns continuous identifiers `CHX-032` and `CHX-033` for the same
validated mechanisms.

Final release validation then opened continuous successor
`run-20260814T001848013126Z-a494126a5017/CHX-034`. One whole-call deletion
mutant survived because its focused regression mocked only behavior inside the
deleted call. The repair exercises the real existing preflight path before a
post-preflight sentinel. It adds no gate or runtime mechanism.

The next complete mutation campaign exposed continuous successor
`run-20260814T004319766703Z-fdfc7f3fd6e2/CHX-035`. The registered
`frontier_limit_minus_one` mutant changed the include-history slice, while its
named regression exercised only the ordinary active-frontier branch. The
repair adds an exact ordered-prefix and endpoint witness on the mutated branch;
it changes no production code, release lane, or runtime mechanism.

The integrated repair excludes a source obligation from the default frontier
only after exact receipt and non-abort validation, repeats that check under the
round-publication lock, preserves worker-result and explicit/history views, and
lets only the current Main CLI role request complete-semantic unbound reuse.
Task/assignment provenance remains distinct and actor text is never authority.
The exact closed successor-ledger digests are bound in `INHERITANCE.lock.json`;
all referenced ledgers and their deterministic reports remain nontruth
operational evidence outside the release package.

No persistent index, background watcher, scheduler, new lifecycle state,
automatic Candidate construction, verifier substitution, Certification,
Gateway, or Fact authority is introduced.

The 0.7.5 local-install integration extends the architecture issues reproduced after the
0.7.2 local installation, including the bounded teaching-document edit in task
`019fa908-8cf5-7a70-a867-dde76a1c6182`. Its exact current ledger lineage is
bound in `INHERITANCE.lock.json`; older immutable ledgers are not rewritten.
That lineage is `run-20260811T013254358017Z-46283133a345` followed by
`run-20260811T085034084387Z-6c87c04d5462` and the resolved successor
`run-20260811T191546409764Z-b156c46cab1c`, with the final disclosure repair
at `run-20260811T193354268477Z-7a6dcfe41bb0`, the 0.7.4 successor
`run-20260812T073631884601Z-53f28d3790b8`, the three measured predecessors
`run-20260812T082458508253Z-50fef06fdcab`,
`run-20260812T084555825183Z-c0da7ae56f95`, and
`run-20260812T085042959321Z-48034fc56b06`, and the resolved 0.7.5 successor
`run-20260812T110223791595Z-71cc17e3531b`, followed by the strict-scan repair
`run-20260812T130915592717Z-6300da6b4bad`, and the selective-admission successor
`run-20260812T164021036787Z-e3fa69b57a73`, which supersedes
`run-20260812T134234791817Z-ae0fd96bef2e/CHX-001`.

The selective-admission predecessor is
`run-20260812T175055302224Z-943735ad5337`. It adds a public Main-only exact
Candidate-adverse planner, command-local Candidate preflight reuse, and a
dependency-closed batch seed. CHX-003 through CHX-005 in that task lineage are
local-install issues and are not remote-publication claims.

The current local-install repair lineage is
`run-20260812T200026180866Z-ccb9d355783f`. It preserves CHX-005 dependency-
closed atomization, inherits the 0.7.8 CHX-006 early Candidate-shape repair,
and owns the 0.7.9 CHX-007 statement-interface precheck and CHX-008 reentrant
active-Fact reconstruction repair. It is not a remote-publication claim.

The 0.7.10 successor adds project run
`run-20260812T232944429816Z-e3c8a9130f6f/CHX-009`. Candidate-adverse exact
retry now excludes a validated aborted work unit before reconstructing its old
round or task card. Active cards remain current-runtime validated, completed
cards remain archive validated, and full project audit retains frozen-byte
coverage. This local repair does not alter automatic selection or dependency-
closed atomization and is not a remote-publication claim.

## Public issue enumeration

1. **CHX-001 — production startup predecessor.** The 0.7.2 compact production
   bootstrap remains the immutable predecessor for the broader 0.7.3
   role-selected startup repair.
2. **CHX-002 — excluded production observation.** This issue is
   `excluded_nonarchitectural`; 0.7.3 neither repairs it nor treats it as a
   release mechanism.
3. **CHX-003 — planning-read predecessor.** The command-local inspection repair
   remains valid, while CHX-013 supersedes its later exact-selection full-frontier
   recurrence.
4. **CHX-004 — computation-role predecessor.** The canonical three-role
   preexecution contract remains publication-resolved and unchanged.
5. **CHX-005 — repair-mode loss.** Aborting and replanning a repair under
   `auto` could lose the source assignment mode; CHX-014 supersedes it.
6. **CHX-006 — excessive one-off assurance.** Redundant controls and unsupported
   negative source-status checks caused avoidable repair rounds; CHX-015
   supersedes this mechanism.
7. **CHX-007 — missing architecture-observation handoff.** Reusable worker
   findings could disappear unless Main remembered a separate ledger action;
   CHX-016 supersedes it.
8. **CHX-008 — late computation disposition check.** A missing disposition was
   rejected only after expensive design closure reconstruction; CHX-017
   supersedes it.
9. **CHX-009 — late information-value decision.** A remodeling-derived table
   was recomputed before the route was recognized as irrelevant to the open
   A-model interface; CHX-018 supersedes it.
10. **CHX-010 — excluded source-direction observation.** The observed automatic
    role choice was source- and task-dependent, so it is
    `excluded_nonarchitectural` and has no successor repair.
11. **CHX-011 — mutation-audit temporary-path alias.** On macOS the audit built
    its isolated runtime beneath `/var`, then correctly rejected its own
    symlinked ancestor; CHX-019 supersedes it.
12. **CHX-012 — compact root and Learner edit successor.** It supersedes
    CHX-001 for the measured bounded edit in task
    `019fa908-8cf5-7a70-a867-dde76a1c6182`: the root skill is now a compact
    router and an existing local teaching-Markdown edit has a 71-line,
    fail-closed contract.
13. **CHX-013 — direct exact-selection projection.** It supersedes CHX-003 for
    explicit Research ids by validating only the selected records, required
    ancestry, Campaign scope, and typed invalidation/disposition events.
14. **CHX-014 — immutable repair work mode.** It supersedes CHX-005 by storing
    the exact source assignment mode on cumulative repair Research and reusing
    it through abort/replan.
15. **CHX-015 — failure-informed selective assurance.** It supersedes CHX-006:
    a one-off computation keeps one production validator plus the smallest
    independent mathematical check, and a negative current-source-status claim
    alone requires a frozen response receipt.
16. **CHX-016 — typed worker CHX observation projection.** It supersedes
    CHX-007 by projecting only closed, exact task-card-bound, reconciled worker
    findings into one content-addressed nontruth inbox; empty and excluded runs
    remain silent.
17. **CHX-017 — cheap disposition precheck with lock revalidation.** It
    supersedes CHX-008 by rejecting missing supervision disposition before deep
    closure reconstruction while recomputing the latest safe state under the
    final round-write lock.
18. **CHX-018 — preallocation information-value elimination.** It supersedes
    CHX-009 by requiring an open target interface or explicit smoke-test purpose
    before computation code allocation; this remains advisory rather than a new
    gate.
19. **CHX-019 — canonical isolated audit root.** It supersedes CHX-011 by
    resolving the already-created temporary parent before copying the audit
    runtime, without weakening runtime ancestor-symlink rejection. The complete
    audit then killed 148 of 148 mutants with unchanged candidate bytes.
20. **CHX-020 — explicit exclusion ownership in public lineage.** Public
    disclosure now retains an `excluded_nonarchitectural` issue's immutable id,
    relation, and owner ledger while preserving exclusion as distinct from
    repair. Open issues still require one strictly later resolved `supersedes`
    successor, and every hash, document, and contiguous-id check remains exact.
21. **CHX-021 — Main-governed bounded attack routing.** Workers now return
    concrete failure evidence and success boundaries without drafting route
    text. Main alone may reject or synthesize a persistent mechanism-level
    rule. Current rules use English internal prose, reject rather than truncate
    oversized text, permit at most sixteen active rules per project and per
    new card, and remain future-only nontruth guidance. Historical user-rule
    cards retain their frozen twenty-four-rule compatibility bound.
22. **CHX-022 — first-output work elimination.** After exact startup, a compact
    production worker or supervisor must make its next milestone one durable
    artifact or one explicit blocker. Consecutive status-only drafting updates
    while the authorized artifact directory remains empty permit Main to
    reclaim the work. Architecture-caused repetition uses the existing worker
    CHX path; no watcher, timer, lifecycle state, audit, truth gate, or packaging
    prerequisite is added.
23. **CHX-023 — goal-intake cumulative-scan predecessor.** Ordinary goal intake
    scanned broad Research state before binding one objective. CHX-026
    supersedes this measured predecessor.
24. **CHX-024 — ancestry-scan and partial-round predecessor.** Explicit planning
    revalidated unused ancestor artifacts and could expose task-card bytes before
    `round.json`. CHX-027 supersedes both parts of this defect.
25. **CHX-025 — forensic attack-report predecessor.** The concise Main report
    reconstructed complete host-scope round coverage before discarding it.
    CHX-028 supersedes this measured predecessor.
26. **CHX-026 — content-addressed goal-root projection.** Goal intake now filters
    immutable Research bytes for exact objective identities, validates structural
    envelopes for matches, fully validates the selected root, and retains the
    complete Research audit as an explicit separate path. It supersedes CHX-023.
27. **CHX-027 — selected authority, structural ancestry, atomic publication.**
    Selected Research and every direct authority input remain fully checked;
    unconsumed ancestry supplies only content-addressed connectivity envelopes.
    A round is built in a private same-filesystem directory and becomes visible
    by one atomic rename only after staged validation and final liveness checks.
    It supersedes CHX-024.
28. **CHX-028 — host-scoped attack case projection.** The default concise report
    reads exact cases, proposals, decisions, and active rules directly, declares
    `coverage_status=case-projection` and `scope_complete=false`, and leaves full
    forensic reconstruction behind the explicit full option. It supersedes
    CHX-025.
29. **CHX-029 — monotone worker completion checkpoint.** It extends CHX-022:
    after all required artifacts exist, the next update is a concrete blocker or
    preflight result; after preflight passes, the next update completes canonical
    validation and CHX closure. No watcher or lifecycle state is added.
30. **CHX-030 — direct active-Fact planning projection.** The current advisory
    planning snapshot validates active Fact bytes, exact visibility markers,
    revocations, dependencies, interfaces, acceptance events, and owner heads.
    Recursive Candidate and verifier provenance remains available through the
    explicit Fact Evidence audit, and older snapshot revisions remain readable.
    It extends CHX-026.
31. **CHX-031 — behavioral producer topology after atomic wrapping.** The
    private atomic-round implementation became the direct caller of compact
    prompt and logical-component producers, while two registry edges still
    named the public wrapper. The registry now points to `_create_round_impl`;
    the public `create_round` atomic boundary and executable behavior are
    unchanged. Strict architecture reconnaissance passes after this repair.
32. **CHX-032 — validated production-obligation closure.** A generic production
    frontier omits a completed source Research obligation only after validating
    its exact ingestion receipt, production assignment, non-aborted round, and
    return. It repeats the selected closure from fresh bytes under the
    round-publication lock. Worker-result Research, history, explicit-ID
    continuation, supervision, and all truth gates remain unchanged.
33. **CHX-033 — explicit Main unbound-Research reuse.** The public Main
    `memory-add` path may reuse an immutable unbound Research record only when
    every normalized semantic field except actor is identical. Operator,
    worker, task-bound, assignment-bound, historical, and semantically distinct
    writes remain actor-sensitive; actor text grants no authority.
34. **CHX-034 — whole-call mutation witness for the existing release gate.**
    The focused release regression now exercises the real mutation-registry
    preflight before its postcondition sentinel, so deleting the complete call
    is observable. The mutation registry, release lane set, phase order, normal
    runtime, and every mathematical and truth boundary remain unchanged.
35. **CHX-035 — exact-branch ordered-prefix mutation witness.** The focused
    frontier regression now exercises the exact include-history slice changed
    by the registered boundary mutant and verifies every positive ordered
    prefix plus the final endpoint. The repair changes only test evidence; the
    frontier implementation, registry size, release lanes, runtime behavior,
    and every mathematical and truth boundary remain unchanged.

CHX-021 and CHX-022 are publication-resolved in the latest immutable ledger.
They preserve the 0.7.3 **Selective Startup** mechanisms and all prior
`supersedes` relations without rewriting their evidence.

CHX-023 through CHX-031 were local-install-resolved in the immutable 0.7.5
lineage, whose publication was intentionally deferred at that time. The
preceding 0.7.4 **Bounded Main Routing** disclosure and the 0.7.5 **Bounded Projections**
disclosure remain immutable predecessors. The continuous 0.7.15
successors make CHX-032 through CHX-035 publication-resolved and are authorized
for protected global installation followed by GitHub source, tag, and Release
publication. Pull-request creation or merge remains excluded.

## 0.7.6 selective-admission successor

The separate local-install lineage
`run-20260812T164021036787Z-e3fa69b57a73/CHX-002` supersedes
`run-20260812T134234791817Z-ae0fd96bef2e/CHX-001`. It adds one Main-only,
bounded, content-addressed readiness receipt. At most sixteen explicit Research
targets are fully checked for ancestry, structural reuse, supervision,
assurance, and blockers. The receipt includes a singleton-default Candidate
batch seed, but performs no automatic ranking, Candidate authoring, review
dispatch, Certification, Gateway admission, or Fact promotion. This private
task ledger is bound by exact runtime validation but is not spliced into the
older public CHX-001 through CHX-031 numbering.

These repairs are deliberately simple: no persistent frontier index, background
watcher, agent reputation, dynamic scoring, second semantic validator, new
Blackboard/Pulse plane, or automatic PHX adoption is introduced.

## 0.7.14 bounded-handoff successor

Project-bound run `run-20260813T083233526366Z-39d8bc3904ff` groups six
observations made after the 0.7.13 installation into four reusable mechanisms.
Its CHX-015 through CHX-020 identifiers belong to that private run and do not
renumber the public issue enumeration above.

- Main now derives one supervised Candidate-adverse target with
  `prepare-candidate-adverse-target`; workers do not manually synthesize the
  target from production and supervision bytes.
- Candidate-adverse refute cards use a dedicated compact bootstrap rather than
  the production bootstrap or the ordinary broad preload.
- Frontier, logical-component, certification, and repair planning reuse only
  command-local validated projections. Unselected Research ancestry contributes
  a hash-checked structural envelope; selected or authority-bearing records are
  still fully validated. Certification performs a distinct fresh recheck while
  holding its narrow publication lock.
- Prospective supervisor cards inherit a content-addressed projection of the
  attacked production card, active Fact premises, and exact source/input
  capabilities. Repair cards carry the challenged Research artifacts forward.
  Historical task cards retain their frozen semantics.

These changes do not add automatic Fact selection or atomization, a persistent
cache, a background scheduler, a second truth path, or a shortened
Candidate/verifier/Certification/Gateway/Fact path. Seal-lock liveness checks
remain mandatory. The local installation is authorized; remote publication is
not.

## 0.7.9 reentrant admission closure successor

The current local-install successor preserves every 0.7.8 truth boundary and
resolves two adjacent failures observed during selective A-model Fact
admission. Exact missing-premise statement-interface failures now reject from
submitted Candidate bytes and immutable selected Research envelopes before
global Research replay. Valid Candidates still reach the complete assurance,
source, artifact, adverse, supervision, verifier, Certification, Gateway, and
Fact gates.

Active-Fact reconstruction now uses a bounded command-local provisional view
only when full validation reenters through a frozen task-card authority check.
That view validates local Release, acceptance-marker, and admitted-Fact bytes;
the outer frame performs full Research, historical-runtime, Decision,
successor, and lineage replay and requires exact agreement. The same inspection
context is propagated through approved-computation design and supervision
replay. The repair neither raises recursion limits nor introduces a persistent
cache or a second admission authority.

## 0.7.8 early Candidate gate successor

The current local-install successor preserves every 0.7.7 truth and assurance
boundary while resolving one work-order defect observed during selective
A-model Fact admission. A singleton Candidate incorrectly labelled as an
atomic DAG previously spent more than three minutes replaying global Research
and supervision history before reporting a shape mismatch decidable from the
submitted Candidate bytes.

Candidate Release now rejects only local cardinality and internal-edge
mismatches before global replay. This projection is nonauthoritative and cannot
accept a Candidate: valid inputs continue through the unchanged complete
assurance validator and every source, adverse, verifier, Certification,
Gateway, and Fact gate. Supervision-round inventory is also deferred until a
selected Research record actually proves production-assignment provenance;
manual and historical Research trigger no unrelated scan.

This release does not make Candidate construction generally constant-time.
Valid Candidates still pay all exact closure checks justified by their active
Research, source, artifact, adverse, and supervision surfaces. No persistent
cache, index, watcher, scheduler, automatic Fact selection, or remote
publication is introduced.

## 0.7.7 Candidate admission efficiency successor

The current local-install successor preserves the 0.7.6 checkpoint and every
truth gate while repairing three adjacent interfaces. Main can plan one exact
Candidate-bound refute through `plan-candidate-adverse`; ordinary production
still rejects `refute`. One Candidate command reuses only a transient, fully
validated inspection context and performs a fresh supervision derivation under
the seal lock. The batch seed now records selected dependency edges, groups
dependency-connected selected targets into disjoint atomic units, and propagates
a blocked selected premise to its selected dependents. Independent units remain
singletons. Automatic ranking, Candidate authoring, verifier dispatch,
Certification, Gateway admission, and Fact effects remain absent.

The observed A3 Candidate preflight improved from more than 95 seconds to about
10.52 seconds before reaching an unchanged fail-closed source-artifact gate.
The speedup removes repeated immutable reconstruction; it does not cache across
commands and does not weaken dependency, staleness, source, adverse, verifier,
Certification, or Gateway checks. No remote publication is authorized.

The 0.7.2 integration is owned by project-bound run
`run-20260811T013254358017Z-46283133a345`: CHX-001 records production-worker
startup cost, CHX-003 records repeated supervision-planning validation cost,
and CHX-004 records an unsatisfiable computation-role contract. CHX-002 in that
run is explicitly excluded as nonarchitectural and is neither repaired nor
claimed by this release.

## 0.7.2 issue enumeration

1. **`run-20260811T013254358017Z-46283133a345/CHX-001` — disproportionate
   production startup.** Current production cards
   now select a manifest-bound compact bootstrap. Every worker still reads the
   full skill, exact prompt/card, return contract, authorized bytes, and its
   role-specific protocol. General architecture, mode, admission, capability,
   Paper, Blackboard, or unrelated computation/source stacks are not preloaded.
   Legacy, malformed, or inapplicable cards fall back to the full path.
2. **`run-20260811T013254358017Z-46283133a345/CHX-003` — repeated
   supervision-planning validation.** One planning command
   now shares one command-local, cycle-safe inspection context across source
   receipt, component, Research, frontier, and round-manifest subaudits. The
   context is discarded at command exit. Mutation-sensitive overlap, abort,
   runtime, authority, and liveness state is still recomputed under the final
   round-write lock; no persistent cache or generation sidecar is introduced.
3. **`run-20260811T013254358017Z-46283133a345/CHX-004` — unsatisfiable
   computation roles.** Assurance construction and
   lifecycle return validation now import one canonical set:
   `computation_source`, `computation_design`, and
   `computation_dependencies`. A task-specific adapter, probe, or derivation is
   bundled inside those artifacts. Any obligation requesting an extra role is
   rejected before round directories or task cards are written.

The 0.7.1 scoped-bootstrap issue is owned by the project-bound run
`run-20260811T002058829626Z-42d7d269ac6d/CHX-001`. The immutable 0.7.0
**Failure-Informed Efficiency** release lineage remains historical:

- `run-20260809T104247487967Z-561e6b0b599d/CHX-001`;
- `run-20260810T091643131656Z-0972f636748d/CHX-002`; and
- `run-20260810T094527949129Z-70b4cac32984/CHX-003` through
  `run-20260810T094527949129Z-70b4cac32984/CHX-006`.

The private JSONL ledgers are not included in the release. Their exact ordered
run ids, hashes, predecessor links, contract revisions, and per-run issue
ownership are bound by `INHERITANCE.lock.json` and checked by
`verify-public-disclosure` before publication.

## Inherited 0.7.1 issue enumeration

1. **`run-20260811T002058829626Z-42d7d269ac6d/CHX-001` — disproportionate
   supervisor startup protocol.** A representative `proof_logic` supervisor
   paid 243,389 bytes and 29,063 words of prompt, task-card, skill, Main/lifecycle,
   return, adverse, and CHX protocol before reading a bound proof artifact. The
   card had already frozen the exact component, receipt set, failure family,
   artifact capability, obligation, and return path. The reusable repair adds
   one manifest-bound compact supervisor bootstrap selected only by an exact
   current supervision card. Program-math, new source use, non-null attack
   learning, architecture repair, and unprojected assurance types expand locally
   to their full references; every invalid or non-supervision case falls back to
   the ordinary full protocol. Machine validation and truth gates are unchanged.

## Inherited 0.7.0 issue enumeration

1. **Historical CHX-001 — Learner administrative coupling.** A bounded read-only oral
   clarification paid full research audit, mode, attack, and reference-loading
   costs. Its immutable ledger remains unchanged. CHX-002 explicitly
   supersedes this project-local first repair.
2. **Historical CHX-002 — global bounded Learner follow-up.** The reusable repair adds one
   fail-closed fast path for an already-active Learner session that needs only
   a directly relevant learning rule and mathematical source slice. Any edit,
   persistence, fresh correctness check, Research, architecture work, or
   external effect exits the path and restores the full applicable workflow.
3. **Historical CHX-003 — bounded Paper-continuation ancestry.** Candidate and Fact reads
   no longer scan all project Research merely to discover a continuation plan.
   They traverse only the explicitly selected Research ancestry through the
   existing command-local inspection context, preserving exact record and
   continuation validation while eliminating the reproduced recursive broad
   read.
4. **Historical CHX-004 — typed Fact-closure authority.** A Research task receives the
   admitted predecessor closure only when both its frozen logic signals and a
   typed obligation request `fact_closure_reconstruction`. Every named root and
   reached predecessor must be active and path/id-consistent before dispatch.
   Ordinary tasks remain direct-reference-only and empty authority remains
   zero-cost.
5. **Historical CHX-005 — selective proof-risk supervision.** Current component-aware
   production preserves a small frozen set of proof-boundary signals for
   supervisor selection. An interpretive result marked `proof_architecture`,
   `proof_logic`, `authority_boundary`, or `scope_transport` receives
   `proof_logic` supervision; ordinary interpretive insight still receives no
   blanket proof review. Historical descriptor hashes and supervisor cards
   remain byte-exact readable.
6. **Historical CHX-006 — immutable-predecessor disclosure succession.** Public disclosure
   now evaluates the complete ordered issue lineage. An unresolved predecessor
   is publication-adequate only when exactly one strictly later issue carries
   an explicit `supersedes` relation and is itself publication-resolved.
   Missing, backward, cyclic, ambiguous, unresolved, or merely related
   successors remain rejected; exact ledger and document equality is unchanged.

## Failure-informed release gates

The 0.7.3 gate set retains the 0.7.0 reproduced high-loss checks rather than every
conceivable mistake. Four focused mutation probes cover the three A-model
stability repairs: project-wide Research scan regression, skipped typed closure
expansion, acceptance of a non-active closure root, and loss of a frozen
proof-risk signal. A fifth focused probe protects CHX-006 successor semantics.
They reuse ordinary regression tests and add no normal-runtime hook.

The scoped-bootstrap probe additionally asserts both sides of the routing
predicate: a current supervisor prompt names the compact contract and omits the
unrelated broad startup references, while an ordinary production prompt keeps
the full public worker-return contract. The runtime manifest binds the compact
reference, so card-bound execution rejects byte drift. This is a static prompt
projection and adds no cache, background process, dynamic scoring, or authority
store.

The 0.7.2 probes additionally assert that current production prompts select
their compact bootstrap, incompatible computation roles fail before any round
bytes, valid canonical roles remain accepted, and all planning subaudits share
one inspection read phase without weakening the fresh final-lock checks.

The static second-subround registry remains limited to program-math projection,
proof boundary/scope, source locator/applicability, and cross-output contracts.
It is release data, not dynamic scoring, agent reputation, or truth authority.
New attack-route suggestions remain sparse, nontechnical, and inactive until an
Operator explicitly approves one for future task cards.

## Intentional residual boundaries

- Software validation establishes only the stated architecture behavior. It
  does not validate any A-model claim or admit any Research result as a Fact.
- Exact workgroup collapse is intentionally exact, not fuzzy theorem matching.
  A changed dependency, obligation, source capability, artifact hash, Campaign,
  convention, or stop condition remains separate work.
- A globally ordered bounded frontier may still inspect the eligible headers
  needed to choose its prefix. The release bounds serialization and local
  explanation expansion and removes inapplicable broad replay; it does not
  promise constant-time ranking for arbitrarily large projects.
- Existing frozen task cards, returns, Paper objects, Research, Candidate
  Releases, decisions, admissions, and Facts are never backfilled or rewritten.
- Candidate fresh-adverse review, verifier, Certification, Gateway, and exact
  Fact admission remain separate mandatory stages.
- The default Blackboard capability is one root node with no write space.
  Blackboard storage and historical projections remain because current Paper,
  Learner, promoted-query, and compatibility consumers still exist.
- New V5 Pulse planning remains unavailable, but historical and V4 Pulse
  inspection and completion paths remain readable. They are not falsely
  classified as unused code.
- Routine status and bounded applicability checks do not replace an explicitly
  requested forensic audit. Release-time isolated validation remains separate
  from normal research execution.
- PHX remains a private advisory route guide. It neither supplies mathematical
  evidence nor authorizes implementation, installation, publication, or attack
  route activation.

Earlier release findings and their qualified owner ledgers remain documented in
`references/v5_release_traceability.md`. This current disclosure intentionally
does not republish private ledger bodies or research content.
