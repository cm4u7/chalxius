# Chalxius V5 release traceability through 0.4.4 — Back to the Future

## Candidate identity and scope

- Current candidate version: `0.4.4`.
- Release codename: `Back to the Future`; this names the bounded restoration of
  selected legacy context connections, not a legacy runtime or authority revival.
- Release predecessor: the exact locally installed Chalxius `0.4.3` tree. Its
  earlier protected mathematical runtime descends from Chalxius `0.4.0` at
  repository commit `2fc8bd8`; its V5 predecessor was exact Chalxius `0.3.6`
  at `316d29e`.
- Minimal-kernel reference: original MathGraph/Danus `0.2.9` tree frozen at
  repository commit `0a93a5a`; original Danus 0.2.9 and later versions remain
  behavioral and performance references only.
- During 0.4.4 candidate construction and validation, installed
  `$CODEX_HOME/skills/chalxius` remains intentionally unchanged at `0.4.3`.
  Installation status is a host-side release receipt, not a property inferred
  from package bytes.
- Project migration and cutover: not performed; either remains a separate
  explicit user decision from package validation.

The 0.4.0 baseline changed the truth-bearing architecture while preserving
unrelated 0.3.6 product capabilities. The 0.4.1 patch changes only the CHX
architecture-ledger procedure and preserves the protected 0.4.0
project/runtime bytes, project schemas, and Fact contract. The 0.4.2 release
adds one explicitly enabled project-local adverse-routing extension; projects
and frozen work units without that activation retain the earlier schema and
behavior. The prospective 0.4.3 candidate repairs CHX-058 through CHX-075,
adds scoped program-math adverse review, and reconnects compact V5 frontier
ordering without changing frozen work. Its copy-on-write successor also repairs
the task-context omission recorded as
`run-20260728T180420869461Z-5d4e882a1c9c/CHX-001`. The same successor repairs the
Reader title/projection, detail-math, hover, and direct-drag instability recorded
in this release run. None of these releases claims that software tests or
release gates prove a mathematical theorem.

The isolated 0.4.4 successor restores user-approved L1 promoted-query seeding
and L2 bounded mode hints, and changes new-card background delivery to a
complete exact-byte index with an immutable round snapshot. It preserves Main,
Operator, and dedicated Host authority boundaries; uses equivalence receipts
to prevent a hint from changing assurance or adverse capabilities; and leaves
all old projects and frozen cards untouched.

## Authority model

The only V5 truth path is:

```text
Research -> Candidate Release -> Certification Decision -> Fact
```

These are four durable states and three happy-path truth transitions. A new V5
root starts with an empty Fact Graph. V4 and predecessor artifacts remain
readable but are not V5 predecessors, reviews, receipts, or admission evidence.

Research is cumulative nontruth. A release automatically binds every existing
challenge, counterexample, or obstacle linked to its selected Research branch
and requires an exact disposition for each. The fresh verifier receives only a
frozen capsule. Gateway admission revalidates the exact accepted decision.

## Preserved and adapted capabilities

- Immutable worker task cards retain control, frozen mathematical-state, and
  bounded narrative planes.
- Pulse remains an optional two-wave collaboration adapter. Each valid return
  enters Research independently; malformed peers are locally quarantined;
  Pulse closure has no admission authority.
- `profile-closure-status` and `profile-closure-record` remain compatibility
  surfaces for repair suggestions only. They append nontruth Research and
  cannot complete or certify work.
- Paper Logic and Audit retain append-only correction, independent review,
  current/superseded snapshots, and exact nodewise Candidate Release binding.
- Blackboard, claims, conventions, campaigns, novelty, experiments, atomic
  FactBundles, source/applicability checks, expert/interpretation lint, Reader,
  and Chalxius Learner retain their bounded user outcomes. Optional modules add
  task-local bindings rather than a universal closure.
- Reader packet v1 remains backward-compatible and renderer revision 17 uses
  bounded V5 titles, hash6/role/plane canvas identities, MathJax-ready readable
  projections of bounded historical ASCII Fact notation, and localized radial-
  memory force settlement. Exact Fact text remains unchanged. Native Fact, Research, Certification,
  Paper/Audit, and Blackboard authority labels remain intact; silent graph
  truncation still fails.

The complete public-command accounting is in `v5_capability_matrix.md`.

## 0.4.1 additive CHX-ledger patch

CHX-057 identified that task completion had no mandatory causal CHX run ledger
or silent-zero feedback rule. Version 0.4.1 adds `scripts/chx_ledger.py`, an
exact-schema, append-only, locked, fsync-backed, SHA-256-chained ledger. Every
run started after the 0.4.1 activation boundary opens one ledger before
substantive work and closes it immediately before final reporting. Only
architecture-caused or materially-amplified issues survive the filter; a
zero/excluded-only close is silent.

Contract revision 1 initially stored all ledgers in private host task state
outside skill and project roots. Contract revision 2 changes the default for
new project-bound runs to `PROJECT/chx-ledgers/`; projectless runs retain the
external fallback. The project-local directory is an operational container,
not a graph plane, and normal project audit and Fact admission ignore it. The
reader accepts both revisions, and every append or close preserves the
revision bound by the ledger's opening event, so an already-open revision-1
ledger remains appendable and closable after the placement amendment.

The activation boundary is prospective. Runs already underway under 0.4.0 are
not backfilled, reclassified, invalidated, or asked to redo work, even if they
later load some 0.4.1-or-later bytes. The runtime ledger has `truth_effect=none` and
`project_effect=none` and cannot change any research or certification status;
the latter describes authority/status effect rather than the intentional
project-local ledger file.

## 0.4.2 user-governed adverse-routing candidate

The new extension is absent until `attack-route-enable` is issued by the
`operator` role in one V5 project. It stores immutable attack cases, route
proposals, user decisions, active rules, and rule disablements below
`PROJECT/governance/adverse-routing/`. No installed skill or active project is
modified merely because the isolated candidate exists.

An extension-bound `counterexample` return carries structured premise and
conclusion-failure witnesses, reproduction steps, an exact success boundary,
and a proposed rule. Ingestion records the case and proposal but does not
activate them. The separate `attack-report` command aggregates one exact host
task and presents pending proposals even when the report is empty. Only an
operator may approve, supply and approve a modified rule, reject, or disable.
Every accepted or disabled rule affects future task cards only.

Refutation cards bind eight fixed low-cost attack families plus at most 24
matching active user-approved rules. Exact hashes and stored lineage prevent a
proposal, decision, or active-rule drift from being accepted silently. The
24-rule bound fails visibly rather than truncating. A task card frozen before
project activation retains the legacy card and return schema even if the
project is enabled later.

The extension has `truth_effect=none`; cases remain worker-reported nontruth
Research. Attack reporting and route approval neither certify a refutation nor
enter Candidate Release, Certification Decision, Fact admission, Paper/Audit,
Blackboard, Reader, Learner, or CHX reporting. Attack and CHX reports are
explicitly separate.

## 0.4.3 prospective assurance and routing repair

The current assurance revision applies only to newly frozen task cards. It
adds exact obligation dispositions, computation manifests, related-artifact
capabilities, and risk-specific Research assurance. Historical cards and
returns keep the 0.4.2 legacy revision and are neither warned nor reopened.

CHX-058, CHX-061, CHX-068, and CHX-070 are addressed by a complete
machine-copyable Certification Decision template, a standalone field-level
preflight validator, and neutral V5 capsule materialization from a release id,
capsule id, or exact capsule JSON. The verifier receives only authorized bytes,
writes and preflights one review, and never assumes the gateway role.

CHX-059 and CHX-060 are addressed by exact per-obligation artifact witnesses,
typed computation-stage manifests, and capability-bound related Research
artifacts. CHX-062, CHX-063, CHX-066, and CHX-067 add formula toy checks,
fixed-to-family bridge artifacts, topology extremal cases and claim-strength
comparison, value-free structure constructors, and complete moving-pole
accounting.

CHX-064, CHX-065, CHX-069, CHX-071, and CHX-072 define current source-evidence
v4: complete-statement coverage, mechanically consistent status summaries,
transported frozen query responses or narrow query capabilities, aggregate
locator diagnostics, typed conclusion transports, and rejection of
mathematical bridges hidden as convention prose. Source-evidence v3 remains
readable for its frozen contract.

CHX-073 and CHX-074 add machine-readable premise interfaces and typed
geometric stage/ambient/space/genus transport. CHX-075 requires exact proof-byte
preservation for interface-only successors and a complete predecessor proof-
unit conservation map for rewritten proofs; verifier capsules display statement
and proof diffs separately.

The V5 automatic frontier now uses the compact four-factor score and projects
historical eight-metric Research without rewriting. It has no score cutoff and
does not restrict explicit scheduling. If adverse routing is enabled, a
successfully ingested actual computation may queue one future nontruth
program-math review. Only that exact generated review receives the ninth
baseline rule; ordinary refutation cards retain eight. Attack proposals remain
subject to user decision, and CHX issues are never imported into routes.

Static capability review also found legacy connections that remain present but
not automatically enabled in V5: campaign-scoped frontier selection, repair-
leaf collapse, promoted-node/query snapshot seeding, suggestion-driven work
mode selection, and automatic V4 execution-profile feature activation. They
remain disabled pending explicit user decisions and are not part of this
candidate's repair scope.

## 0.4.3 post-admission attack-context repair

The supplied causal ledger showed a refutation card that retained only the
source Research claim and rationale. It omitted the source challenge content,
source locator, and metadata, while a frozen nontruth project background still
described an empty Fact Graph after the target release had been admitted. The
round stopped before dispatch, so the ledger records no mathematical effect.

The copy-on-write successor adds the prospective task-context revision
`chalxius-v5-task-context-0.4.3-2`. Every newly planned card binds the complete
validated source Research record plus a task-referenced current V5 authority
snapshot. Exact attack metadata expands the capability boundary only to the
named Candidate Release and Certification Decision, their admission marker and
admitted Facts when present, and the Release's sealed artifacts. Partial or
inconsistent target bindings fail before the round directory is created.
Machine-validated authority controls current status when project-background
prose conflicts, but the background remains immutable nontruth history.

The original card and every card without the new revision remain readable
under their original schema. They are not backfilled, relabeled, or treated as
work that must be repeated. The user's source project and globally installed
0.4.2 tree were exercised read-only and not migrated or deployed during this
candidate repair.

## 0.4.4 bounded context restoration

The current revision is
`task_context_revision="chalxius-v5-task-context-0.4.4-1"` with
`context_selection.revision="chalxius-v5-context-selection-0.4.4-1"`. Main
compiles one frozen receipt; Operator retains explicit governance and override;
the technical Host role keeps exactly its preexisting Pulse dispatch, status,
and audit commands.

L1 accepts a promoted Blackboard query only with exact origin node, origin
snapshot, query, promotion-task and hash lineage. It is planned as one task
under fixed node/edge budgets. An origin that later becomes inactive blocks a
new plan while leaving every earlier frozen card valid.

L2 accepts only exact `prove`, `refute`, `compute`, `literature`, or `interpret`
tokens. Free prose is visibly rejected. An automatic suggestion must have the
same hashed cross-component signature as the kind-derived default: it may not
change the assurance contract, attach or remove an active adverse capability,
or suppress a computation's later program-math review. Explicit user `--mode`
remains the only authorized cross-boundary override.

For new cards, `PROJECT_BACKGROUND.md` remains an explicitly generated,
256-KiB-capped nontruth source. The card embeds only a complete exact-byte
chunk index, selected/unselected receipt, and hash/path to an immutable
round-local source copy. Main/Operator may inspect current bytes; a worker must
name a frozen task card. All chunks remain retrievable, and post-compaction
rehydration rereads the card/index and exact chunks. Historical 0.4.3 cards
retain their full-body schema without warning, backfill, or redo.

## 0.4.4 candidate validation evidence

All evidence below was produced from the isolated pre-decision 0.4.4 tree on
2026-07-29. It is software/compatibility evidence, not installation, project
migration, mathematical certification, or a request to redo frozen work:

- focused 0.4.4 context plus inherited V5 lifecycle set: `24/24` passed;
- complete inherited regression suite: `492/492` passed in `22.130 s`;
- `scripts/self_test.py`: PASS, including exact background rehydration,
  unchanged Host role, CHX, adverse routing, V4/V5 compatibility, and the
  500-line skill limit;
- Skill Creator validation: `Skill is valid!`;
- release-only aggressive audit: `26/26` mutants killed with
  `candidate_unchanged=true`, including context authority, frozen background,
  mode-equivalence, Host-capability, and worker-card bypass mutants;
- protected runtime surface: `70` files, SHA-256 tree digest
  `944797b665fd43c9751b8ec17a8209bd562421ecc3a9e59cc1293b98ed45db24`.

Final self-excluding manifest, cold-extraction comparison, and independent
forward testing remain required before the candidate may be proposed for
installation. The installed 0.4.3 tree and all active projects remain outside
this candidate.

## 0.4.3 candidate validation evidence

All evidence below was produced from the isolated pre-decision `0.4.3`
candidate tree on 2026-07-29. It validates a release candidate; it is not an
installation, migration, mathematical certification, or request to redo any
frozen work:

- focused CHX-058--075, program-math routing, proof-lineage, source-evidence,
  capsule, and four-factor frontier set: `7` tests passed;
- complete inherited plus `0.4.3` regression suite: `486` tests passed in
  `20.007 s`;
- `scripts/self_test.py`: PASS, including current V5 assurance,
  `priority_ordering_policy=PASS`, `chx_runtime_ledger=PASS`, and
  `adverse_routing=PASS`;
- Skill Creator validation: `Skill is valid!`;
- release-only aggressive audit: `8/8` mutants killed with
  `candidate_unchanged=true`;
- Reader revision 16 projected the real `GAP-PROTO-0721-V5` snapshot to `109`
  nodes and `293` edges with maximum generated title length `31`, no title over
  the `64`-character protocol bound, and no TeX environment in a title;
- browser QA of those exact output bytes rendered `42` readable and `80`
  formal math items in the selected target, kept the compact hover box to one
  line, moved only the directly dragged node while every other node remained
  at displacement `0`, and restored the canonical layout with maximum
  displacement `0`; the browser reported no warnings or errors;
- the explicitly requested project export replaced only the derived
  `visualizations/knowledge-map.html`; the other `982` project files retained
  the same content fingerprint
  `2c1db004f2c8fa6e7a592f79a0a4382c6db1f68c6508a6ba24404f75f6de819f`;
- Python AST and JSON reconstruction: PASS;
- protected runtime surface: `69` files, SHA-256 tree digest
  `09da8f3ed1fb723d5881fdae9c988318cad946125367d6ffcc6e9ce8128e6080`;
- final self-excluding manifest: `159/159` candidate files.

The final manifest, cold-extraction replay, and independent forward test are
also required before this candidate may be proposed for installation. The
installed `0.4.2` tree and all active `0.4.0` projects remain outside the
candidate and are never opened for migration or backfill.

## 0.4.2 validation evidence

All evidence below was produced from the isolated 0.4.2 candidate tree on
2026-07-28; it is candidate evidence and is not an installation or project
cutover receipt:

- focused adverse-routing set: `10` tests passed;
- adverse-routing, V5 lifecycle, and protected-capability set: `30` tests
  passed in `2.546 s`;
- complete inherited plus 0.4.2 regression suite: `476` tests passed in
  `21.192 s`;
- `scripts/self_test.py`: PASS with `adverse_routing=PASS` and
  `chx_runtime_ledger=PASS`;
- Skill Creator validation: `Skill is valid!`;
- release-only aggressive audit: `8/8` mutants killed directly from the
  versioned candidate directory with `candidate_unchanged=true`;
- Python syntax reconstruction: `80` files parsed successfully;
- protected runtime surface: `64` files, SHA-256 tree digest
  `2a63bd27119314fb3243aa033a321b909625071ad080a3e638171ee2937bc583`;
- independent forward testing exercised proposal creation without activation,
  modified approval, future-card-only selection, and separate zero/nonzero
  reports; additional tests passed V4 zero-write rejection, proposal tamper and
  missing-lineage fail-closed behavior, pre-enable frozen-return compatibility,
  and approve/reject/disable behavior;
- final self-excluding manifest: `155/155` candidate files.

The independent test also reconstructed a complete return from the published
V5 adverse template and passed preflight, validation, and ingestion. Facts and
Certification Decisions remained empty in its test projects. These checks
establish the software contract only; they do not certify the worker's
counterexample or any mathematical claim.

## 0.4.1 validation evidence

All evidence below was produced from the 0.4.1 candidate worktree on
2026-07-28:

- focused CHX and runtime-preservation set: `14` tests passed, including
  silent-zero closure, causal inclusion, nonarchitectural exclusion, required
  resolution evidence, tamper/post-close rejection, symlink rejection,
  concurrent sequential IDs, CLI startup, prospective compatibility, and the
  exact protected-runtime digest;
- complete inherited plus 0.4.1 regression suite: `461` tests passed in
  `21.256 s`;
- `scripts/self_test.py`: PASS with `chx_runtime_ledger=PASS`;
- Skill Creator validation: `Skill is valid!`;
- release-only aggressive audit: `8/8` mutants killed with
  `candidate_unchanged=true`;
- protected 0.4.0 project/runtime surface: `63` files, SHA-256 tree digest
  `f8edf3ea6fe4c978eb7ab5c9bb7f249311bfb8557e5961b384f55e9cbf96599b`;
- final self-excluding manifest: `152/152` candidate files.

Installation and installed-tree validation remain host receipts. They do not
retroactively alter any 0.4.0 task or project.

### Contract-revision-2 placement amendment evidence

The project-local placement amendment was validated from the same 0.4.1
candidate worktree on 2026-07-28:

- focused CHX ledger set: `15` tests passed, including exact project-local
  placement, projectless fallback, V5 initialization/audit coexistence,
  revision-1 open-ledger append/close compatibility, causal filtering,
  concurrency, tamper rejection, and prospective 0.4.0 policy;
- complete inherited plus amended 0.4.1 regression suite: `466` tests passed in
  `22.758 s`;
- `scripts/self_test.py`: PASS with a project-local silent-zero ledger;
- Skill Creator validation: `Skill is valid!`;
- release-only aggressive audit: `8/8` mutants killed with
  `candidate_unchanged=true`;
- protected 0.4.0 project/runtime surface: `63` files, SHA-256 tree digest
  `f8edf3ea6fe4c978eb7ab5c9bb7f249311bfb8557e5961b384f55e9cbf96599b`;
- final self-excluding manifest: `152/152` candidate files.

These checks establish software and compatibility behavior only. In
particular, the project-local audit canary starts the CHX ledger before V5
initialization, obtains a current project audit, observes an empty Fact Graph,
and verifies that the ledger bytes remain unchanged by initialization/audit.

## Back to the Future field-repair successor

The practical handoff snapshot with SHA-256
`4c2eb4c14605aacf18d4515e4f5515427321fa968f77b9ce2e5b8032dc1f4522`
identified six architecture defects in a live higher-genus workflow. The
copy-on-write field-repair candidate preserves version/codename identity and
does not replace the earlier frozen 0.4.4 candidate. It repairs:

- CHX-006: two-phase nonrecursive active-lineage validation and recoverably
  transactional Fact admission; marker visibility is unchanged and exact
  post-marker event/interface projections are idempotent;
- CHX-005: named legacy-premise resolution to one exact predecessor clause and
  a full-hash witness obligation, without rewriting legacy interfaces;
- CHX-001: public `memory-add --current-assurance` source capabilities and a
  fail-closed planning boundary for path-only source prose;
- CHX-003: immutable refute-assignment provenance independent of return kind,
  with mandatory release disposition/verifier exclusion and counterexample-only
  attack learning;
- CHX-002: candidate-root/version runtime identity in future task cards and
  `chx_ledger.py start --task-card` mismatch rejection; and
- CHX-004: explicit read-only Fact Graph inventory and exact append-target
  routing, with no cross-project Fact import, federation, or silent authority.

All new card/planning/interface requirements are future-only. Frozen cards,
running 0.4.0 work, historical releases, and already completed assignments are
not backfilled, warned, invalidated, reordered, or asked to redo work. The sole
recovery exception is exact idempotent completion of an already written 0.4.4
admission marker with the same Decision and gateway.

The subsequent closed field ledger
`run-20260729T081913970946Z-2f0a9e345447/CHX-001`, ledger SHA-256
`7919cab1d7592d700a4682f2eb21bdf548c36fc39465ee38189b70174d51d521`,
identified one additional control-plane projection defect. The immutable abort
record correctly blocked continuation, but V5 `round-status` still reported two
live `awaiting_return` assignments and strict audit did not compare that view
with the abort authority. The repair adds a validated read-only abort query,
projects unfinished assignments as `frozen_aborted`, exposes the exact abort id,
sets the live awaiting count to zero, and makes audit fail closed on any
abort/status mismatch. It preserves existing receipts and makes no Research,
Certification, Fact, or project-history mutation.

The same field-repair candidate closes a Reader interface defect observed on
Fact object SHA-256 prefix `18d012`. The readable summary no longer copies
`[CLAIM:*]` and `[HYP:*]` machine anchors or delimiter-free historical ASCII
notation directly into the MathJax panel. A bounded deterministic compatibility
projection emits readable anchor labels and TeX delimiters for explicit
subscript, superscript, and relation tokens, while native TeX passes through and
the formal/original Fact text and every authority hash remain byte-identical.
Renderer revision 17 also replaces the former drag-versus-stability tradeoff:
selected cards remain session anchors, a two-hop plus immediate-collision
neighborhood receives bounded attraction, repulsion, radial-ring, and angular-
order forces, and every node outside that neighborhood is a fixed boundary.
No idle simulation, graph mutation, authority effect, or writeback is added.

Field-repair validation on the isolated candidate produced:

- focused BTTF field-repair plus Reader regressions: `39/39` passed;
- complete inherited and current suite: `502/502` passed in `23.584 s`;
- `scripts/self_test.py`: PASS, including Reader, CHX ledger, adverse routing,
  priority ordering, and the Skill line bound;
- Skill Creator validation: `Skill is valid!`;
- release-only aggressive audit: `30/30` mutants killed with
  `candidate_unchanged=true`, including explicit Reader-summary and radial-
  memory bypasses;
- current protected runtime surface: `71` files at SHA-256
  `ae03a3b33e7cb8ee8cda1151b09b690f3402cd6b6bb4c233a1e03760bfba75fe`;
- isolated real-project Reader output SHA-256
  `ff9f7943267a5c3abecb558d3d82b64d9639cfd1f2380dd0df1deb0145fe6451`:
  Fact `18d012` rendered 12 MathJax containers and 12 SVGs with no readable
  machine anchors or browser warnings/errors; and
- live force QA ran 14 bounded passes with one fixed anchor, a seven-of-eight
  node force neighborhood, one exact-zero outside displacement, and reset
  pairwise rendered-geometry error below `0.008` pixels after removing common
  viewport translation.

The active project's admitted Fact and existing HTML hashes were byte-identical
before and after QA. Manifest freeze, cold extraction, installed-tree checks,
and remote publication verification remain separate gates. This section
describes software contract scope and does not certify any mathematical claim.

## Historical project background

Creating, rebuilding, refreshing, or incrementally updating
`PROJECT_BACKGROUND.md` requires an explicit user instruction. If the file
exists, V5 Reader preserves its projection. New 0.4.4 task cards bind a complete
exact-byte index and round-local immutable source snapshot without embedding
the body; earlier cards retain their complete UTF-8 body and SHA-256. If absent,
Chalxius continues without generating one. The file is capped at 256 KiB, has
no truth effect, and cannot replace an exact load-bearing source binding.

## Program-mathematics boundary

For a series-product coefficient `[t^p] product_i f_i`, the V5 computation gate
derives each factor's minimum retained power as
`p - sum_{j != i} valuation(f_j)`. The x-y swap canary rejects retaining
`omega11` only through `t^0` when `t^2` is required, and requires a bound deeper
replay. The separate mutation harness attacks truncation, exact-set, panel, and
coverage boundaries only at release time; no normal runtime imports it.

## 0.4.0 baseline validation evidence

All evidence below was produced from the candidate worktree on 2026-07-28:

- complete inherited and V5 regression suite: `450` tests passed in `19.728 s`;
- `scripts/self_test.py`: PASS, including empty V5 authority and default
  background-read canaries;
- skill-creator `quick_validate.py`: `Skill is valid!`;
- `scripts/aggressive_bug_audit.py`: `8/8` mutants killed and
  `candidate_unchanged=true`;
- targeted V5 lifecycle, Pulse, experiment, and Reader set: `46` tests passed;
- inheritance lock JSON parse and `git diff --check`: PASS at the validation
  checkpoint.

The small-flow performance canary ran two isolated workflow regressions nine
times per version, including Python startup. Median wall times were:

| Tree | Median |
|---|---:|
| original Danus/MathGraph 0.2.9 | 0.109132 s |
| Chalxius 0.3.6 | 0.127687 s |
| Chalxius 0.4.0 V5 candidate | 0.141953 s |

The V5 pair exercises its stronger Candidate Release and Certification path,
so this is a latency canary rather than an equal-instruction throughput proof.
It shows a 14.266 ms median difference from 0.3.6; the release mutation audit is
not responsible because it is absent from all runtime imports.

A separate twelve-run three-worker task-card benchmark measured default
background binding:

| Background | Median plan time |
|---|---:|
| absent | 0.006323 s |
| 64 KiB | 0.009245 s |
| 256 KiB cap canary | 0.016226 s |

This supports the single-summary design without claiming zero cost.

## Issue-ledger disposition

The append-only architecture issue ledger is delivered separately at
`chalxius-upgrade-issue-ledger.md`. CHX-049 and CHX-050 remain historical but
are excluded by the user's architecture-causation ruling. Candidate resolution
evidence must be appended only after the final manifest and regression rerun;
no issue entry itself has mathematical truth effect.

CHX-056 records stale active V4 deployment guidance found during public-release
preparation. The release replaces admission-authoritative profile closure,
whole-pulse failure, and V4 authority-inheritance instructions with the V5
advisory/local-quarantine/read-only-lineage rules, and self-test now rejects
those exact stale claims.

CHX-057 records the missing task-scoped causal completion ledger. Its 0.4.1
resolution requires the frozen manifest, focused ledger tests, full inherited
suite, self-test, mutation audit, protected-runtime byte check, and installed-
tree verification; evidence is appended to the external ledger only after those
checks pass.

## Residual boundaries

- Package validation establishes a validated candidate, not an installed release;
  a receiving host must verify installation separately.
- No active V4 project was migrated, rewritten, or accepted into V5.
- A background summary may be stale; default reading never upgrades it to
  authority and never refreshes it silently.
- Performance measurements are local canaries, not universal hardware claims.
- Software validation establishes the stated contracts only, not mathematical
  correctness or Fact admission for any research claim.
