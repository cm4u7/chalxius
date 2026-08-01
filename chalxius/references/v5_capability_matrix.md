# V5 capability preservation matrix

This matrix governs the 0.3.6-to-0.4.0 kernel upgrade, the additive 0.4.1
CHX-ledger patch, the original opt-in 0.4.2 adverse-routing release, its later
prospective-default reporting revision, and the
prospective 0.4.3 assurance and routing repairs.
The isolated prospective 0.4.4 `Back to the Future` candidate restores two bounded context-planning
connections: exact promoted-query snapshot selection and enum-only mode hints.
It also replaces full background bodies in new cards with an exact retrievable
index. The copy-on-write field repair adds source capabilities, runtime-bound
worker ledgers, adverse-assignment provenance, nonrecursive admission recovery,
legacy-premise witnesses, and explicit read-only prior-Fact inventory. Historical
cards and running work keep their frozen contracts.
The isolated 0.5.0 Campaign successor connects only explicit exact-match V5
frontier scope plus a bounded frozen nontruth envelope; unscoped Main behavior,
active-Campaign defaults, frozen work, and Fact admission remain unchanged.
Exact Chalxius 0.4.0 project/runtime behavior remains the compatibility
baseline for projects and frozen work units without the new activation
contract. The four-state V5 model constrains only the
truth-bearing critical path; it is not a license to delete unrelated product
capabilities.

## Decision rule

- `keep`: preserve behavior and authority boundary; allow implementation cleanup only.
- `adapt`: preserve the user outcome while changing an issue-linked coupling or storage interface.
- `replace`: allowed only with cited CHX evidence and an equivalent-or-stronger regression.
- `remove`: allowed only after explicit user discussion plus cited CHX evidence.

No issue mapping means `keep` or interface-only `adapt`.

Original Danus versions, including 0.2.9 and later releases, are behavioral references only. The
candidate consumes no source module, runtime, writer, fact, review, receipt, or mutable store from
them.

## Public capability inventory

| Capability | 0.3.6 public commands or surface | V5 action | Issue mapping | Required preservation evidence |
|---|---|---|---|---|
| Project and Fact reading | `init`, `status`, `audit`, `show`, `search`, `closure`, `context`, `targets`, `set-targets`, `export-mermaid`, `fact-graph-inventory`, `fact-graph-append-target` | keep/adapt | CHX-039, CHX-040, CHX-048; field CHX-004 | empty V5 Fact start; V4 readable nontruth; clean Fact closure and audit; explicit prior-V5 inventory/append-target routing with no import or federation |
| Single-Fact certification | compatibility commands `submit`, `packet`, `make-verifier-task`, `record-review`, `admit`, `revoke`; primary V5 transitions `candidate-release`, `candidate-release-check`, `verifier-capsule`, `certification-record`, `certification-decision-check`, `fact-admit` | adapt | CHX-009, CHX-021, CHX-024, CHX-025, CHX-032, CHX-039, CHX-048, CHX-058, CHX-068; field CHX-005–006; `run-20260730T043905300313Z-41247ad11966/CHX-002–003` | exact candidate, shared local/gateway finding-class validator, hashed named-premise witnesses for legacy conditional reuse, immutable decision, seal-time lineage snapshots, pre-marker historical simulation, nonrecursive/idempotently recoverable admission, and cascade revocation |
| Atomic FactBundles | `fact-bundle-submit`, `fact-bundle-record-review`, `fact-bundle-admit` | keep/adapt | CHX-022, CHX-029, CHX-030, CHX-034, CHX-039 | all-or-none mini-DAG visibility without profile-closure coupling |
| Research memory and repair | `memory-add` including `--current-assurance`, `memory-update`, `frontier`, `plan-repair-round` | adapt | CHX-011, CHX-013, CHX-015, CHX-030, CHX-039, CHX-041; field CHX-001 | cumulative Research Ledger; exact source capabilities for source-dependent planning; counterexamples and insights survive later rounds; compact four-factor automatic ordering with legacy eight-metric read projection, no cutoff, and explicit low-score scheduling |
| Adverse routing evolution and attack report | `attack-route-enable`, `attack-route-status`, `attack-report`, `attack-route-decide`, `attack-route-disable`; conditional task-card/return fields | adapt; standing user requests 2026-07-30 and 2026-07-31 | none; prospective default nontruth capability | every V5 host task emits a separate report including zero; new refute cards lazily materialize project-local state; immutable surviving-counterexample/productive-challenge case and proposal lineage with concrete value effects; operator-only approval/modification/rejection; future-only approved rules; frozen/V1–V4 work unchanged and never redone; original eight baseline rules plus general hidden-conjunct split; exact philosophy/mixed domain adds only faithful plain-language substitution, atomic burden/strongest-charitable objection/independent-failure-surface, and quantifier-modal-scope-exception equivalence; claim keywords cannot activate them; one computation-evidence-gated program-math rule appears on generated reviews only; no Fact authority |
| Novelty evidence | `novelty-record`, `novelty-status` | keep | CHX-020, CHX-033 | query/corpus/date-bounded status; no automatic campaign/paper expansion |
| Three-plane task execution | `plan-round`, `round-status`, `preflight-return`, `validate-return`, `ingest-return`, `work-unit-abort` plus immutable task cards | adapt | CHX-004, CHX-006–013, CHX-016, CHX-019, CHX-024–028, CHX-031, CHX-032, CHX-034, CHX-035, CHX-037, CHX-052, CHX-059, CHX-060, CHX-062–067; `run-20260728T180420869461Z-5d4e882a1c9c/CHX-001`; `run-20260729T081913970946Z-2f0a9e345447/CHX-001`; `run-20260730T043905300313Z-41247ad11966/CHX-001`; field CHX-002–003; candidate run `CHX-001`, `CHX-004` | control/state/narrative planes remain distinct; active cards require the current candidate runtime; aborted or fully receipted `completed` cards validate exact bound root/VERSION/manifest bytes; completion also validates receipt, return, Research, and optional adverse/program-math records; complete source Research dossier; task-referenced current-authority snapshot with exact target capabilities; outcome-independent adverse assignment provenance; Main-planner-compiled context receipt; prospective marker and old-card compatibility; public exact V5 return schema, template, CLI/prompt pointers, and actionable missing/unknown obligation diagnostics; local quarantine; validated abort authority projects unfinished assignments as `frozen_aborted`, exposes the abort id, and leaves zero live awaiting returns, with strict audit consistency |
| Blackboard exploration | `blackboard-space-create`, `blackboard-node-add`, `blackboard-edge-add`, `blackboard-type-register`, `blackboard-show`, `blackboard-query`, `blackboard-snapshot`, `blackboard-snapshot-query`, `blackboard-reindex`, `blackboard-promote-node` | keep/adapt | CHX-018, CHX-026, CHX-027, CHX-030, CHX-039–041 | typed cumulative nodes/edges; immutable snapshots; no automatic Fact promotion |
| Pulse collaboration | `pulse-plan`, `pulse-status`, `pulse-barrier`, `pulse-dispatch`, `pulse-void`, `pulse-close`, `pulse-abort`, `pulse-audit` | adapt | CHX-001–003, CHX-005, CHX-014, CHX-015, CHX-017, CHX-018, CHX-022, CHX-023, CHX-027–031, CHX-036, CHX-037, CHX-039, CHX-041, CHX-048, CHX-052 | same-snapshot Wave 1 and snapshot-mediated Wave 2 remain; each contribution ingests independently; no peer destruction |
| Reasoning profiles and adoption | `mode-init`, `mode-status`, `mode-switch`, `adoption-plan` | adapt | CHX-005, CHX-020, CHX-033, CHX-036, CHX-039, CHX-048 | fast/auto/deep remain exploration budgets; adoption remains advice; neither creates universal certification closure |
| Process readiness (V4 profile-closure compatibility) | `profile-closure-status`, `profile-closure-record` | adapt; user-approved 2026-07-28 | CHX-014, CHX-023, CHX-029, CHX-036, CHX-039, CHX-048 | retain and strengthen repair suggestions; recording appends guidance to Research only and has no admission authority |
| Campaigns | `campaign-create`, `campaign-activate`, `campaign-status`, `campaign-target-add`, `campaign-target-archive`, `campaign-update`; explicit `frontier --campaign`, `plan-round --campaign` | adapt; user-approved 2026-07-30 | CHX-020, CHX-033, CHX-039 | optional durable multi-round objective/target/constraint/stop/history envelope; exact stored Campaign associations only; one bounded frozen nontruth scope per explicitly scoped round; Main's unchanged four-factor frontier remains the scheduler; no active-Campaign default, second scheduler, continuous advancement, expansion gate, closure, or Fact effect |
| Claims, conventions, and exposition | `claim-add`, `claim-show`, `claim-variant`, `convention-add`, `convention-show`, `export-claim-card`, `export-interpret-card`, `lint-expert-document`, `lint-interpret-document` | keep | CHX-006, CHX-007, CHX-009, CHX-010, CHX-016, CHX-019, CHX-024, CHX-034 | exact interfaces, quantifiers, conventions, and lint semantics remain available |
| Replayable computation | `experiment-start`, `experiment-event`, `experiment-observe`, `experiment-decision`, `experiment-status`, `experiment-resume`, `experiment-finalize` | keep/adapt | CHX-039, CHX-048, CHX-054, CHX-059, CHX-066, CHX-067 | immutable commands/artifacts/checkpoints and independent replay remain; current V5 stages bind formula, domain, representation, approximation budget, output meaning, and independent checks; task-local binding only |
| Paper Logic, Audit, and continuation | `paper-logic-init`, `paper-logic-stage`, `paper-logic-record-review`, `paper-logic-freeze`, `paper-logic-status`, `paper-logic-show`, `paper-logic-query`, `paper-logic-audit`, `paper-logic-link-exploration`, `paper-logic-project-blackboard`, `paper-continuation-plan`, `paper-continuation-status`, `paper-continuation-dispose` | keep/adapt | CHX-033, CHX-038, CHX-043; `run-20260730T145847217907Z-eedfc9368ea0/CHX-001–003`; candidate interface CHX-004 | source/reconstruction/audit separation and append-only correction; explicit all-target or bounded target continuation creates a complete no-cutoff Research frontier; transitive Research ancestry forces exact Paper closure and refs at release; adequacy remains separate from Fact truth; philosophy Facts expose one independently falsifiable conjunct each, ordinary-language paraphrases, explicit burden/objection/failure surfaces, and a reviewed necessary-term ledger; fresh verification rejects hidden conjuncts and jargon that conceals reasoning; public exact-key Paper and worker-return contracts, staging-tested Logic/Audit fixtures, templates, CLI/prompt schema pointers, and bounded missing/extra diagnostics make the strict path independently operable |
| Cross-project Evidence | `evidence-library-status`, `evidence-query`, `evidence-sync-retry`, `evidence-import-fact-graph`, `evidence-bridge-prepare`, `evidence-bridge-check`, `evidence-mark`, `evidence-impact-report`; optional Candidate Release `evidence_bridge_refs` | additive isolated candidate | current Evidence run/CHX-001; compatibility canary/CHX-001 | reviewed Paper freeze auto-archives exact PDF/version/graph/reviews; non-paper Fact import is explicit user + Operator only; a scoped runtime-independent authority audit accepts supported older V5 sources without reopening frozen nontruth work while retaining exact Fact/Release/Decision/admission/revocation/event/interface/closure checks; Evidence stays nontruth; bridge is content-addressed, destination-bound, fresh-verifier and Fact-Gateway checked; correction stales future reuse and reports impact without silent Fact revocation; historical releases and running projects unchanged |
| Reader visualization | `export-reader-html`, packet v1, renderer revision 20 | adapt | CHX-042; this run/CHX-001 | backward-compatible packet validator; bounded V5 titles; hash6 plus role/plane canvas identity; MathJax-ready historical Fact summaries with exact source preserved; deterministic per-theme centers and membership-scaled equally spaced rings; presentation-only shared membership from strong prerequisite/support target closures; multi-field overlap placement; default-on session gravity; orbit-off collisions let only the impacted old Cartesian pin yield and update; bounded local animated equilibrium with no idle simulation; no authority effect |
| Project background | single `PROJECT_BACKGROUND.md` nontruth source; `project-background-index`, `project-background-read` | adapt | CHX-040, CHX-048, CHX-051, CHX-052; `run-20260728T180420869461Z-5d4e882a1c9c/CHX-001`; this run/CHX-001 | generation/refresh requires user instruction; new 0.4.4 cards freeze a complete exact-byte chunk index and immutable round snapshot instead of embedding the body; Main/Operator may inspect, Main-planner selection plus unselected counts are explicit, and the dedicated Host dispatch role is unchanged; every chunk remains hash-bound and rehydratable after context compaction; old cards keep their full-body schema; Reader compatibility remains; authority overrides background status prose |
| Migration and legacy import | `upgrade-project-copy`, `upgrade-workflow`, `import-danus` | adapt | CHX-040, CHX-044–047, CHX-051, CHX-052 | read-only historical access; user-directed summary generation; default reading when present; no V5 authority inheritance |
| Chalxius Learner | `scripts/learn`, `scripts/learning_graph.py`, academic routing | keep | none | explicit activation, nontruth-only writes, frozen read-only mounts |
| External-source and elementary gates | source/applicability validators and controlled elementary ledger | keep/adapt | CHX-033, CHX-064, CHX-065, CHX-069, CHX-071, CHX-072 | current source-evidence v4 binds complete hypotheses and conclusions, query evidence, structured status, and typed transports; v3 remains historical/readable |
| Verifier capability isolation | `scripts/prepare_verifier_capsule.py` | keep/adapt | CHX-039, CHX-041, CHX-058, CHX-061, CHX-068, CHX-070, CHX-071; `run-20260730T043905300313Z-41247ad11966/CHX-002` | exact allowlist, neutral materialization, complete decision template, one shared enumerated finding-class validator executed locally and by gateway, fresh independent verifier, no exploration workspace access |
| CHX runtime ledger | `scripts/chx_ledger.py`, mandatory start/close procedure, worker `start --task-card` | adapt | CHX-057; field CHX-002 | one task-scoped hash-chained ledger for each new 0.4.1 run; future worker cards bind candidate root/version and reject older-global drift; project-bound default at `PROJECT/chx-ledgers/`, external projectless fallback, causal-only entries, silent zero, no project-authority/truth effect, and no 0.4.0 backfill or redo |

## Three-plane invariant

Every V5 task card binds all three planes without embedding their full contents in the prompt:

1. control: compact prompt, bounded control-only follow-ups, exact final handoff;
2. mathematical state: one frozen bounded snapshot and exact read/write capabilities;
3. narrative: bounded rationale, summary, intuition, limitations, and open boundary.

The task card remains immutable capability data. Removing it, replacing it with prompt prose, or
allowing a worker to infer capabilities from filesystem visibility is not a permitted simplification.

## Legacy main-path connections currently dormant

These mechanisms still exist in the package or historical schema but are not
connected to automatic V5 planning. Finding them does not authorize activation:

- default repair-lineage collapse to actionable leaves and the corresponding
  `--no-collapse-repairs` control;
- automatic attachment of the V4 `execution_profile` and
  `profile_obligations`; V5 keeps `adoption-plan` as standalone advice and uses
  the current assurance contract instead;
- automatic panel, Pulse, Paper/Audit, novelty, campaign-expansion, and expert-
  synthesis activation derived from that execution profile.

These are decision candidates, not missing Fact gates. V1-V4 authority import,
automatic project-background generation, automatic Learner/Grill activation,
and universal profile closure are intentionally retired safety boundaries and
must not be proposed as ordinary re-enablement.

## Prospectively restored context connections

The user explicitly approved L1 and L2 restoration for new work only. A
promoted Blackboard query may seed one exact new V5 task after its origin node,
origin snapshot, query, and hashes all validate; unrelated Research must be
planned separately, preserving the one-snapshot-per-round invariant. L2 accepts
only exact `prove`, `refute`, `compute`, `literature`, or `interpret` enum
values. An explicit `--mode` always wins; free text is rejected visibly; an
automatic hint applies only when its assurance, adverse binding, and later
program-math review signature equals the kind-derived default. The dedicated
Host role remains dispatch-only. Neither restoration backfills, reorders, or
invalidates a historical task.

The later user-approved Campaign connection is deliberately narrower than V4:
only an explicit Campaign id filters the V5 frontier and freezes its bounded
nontruth envelope. `ACTIVE` is never consumed implicitly; unscoped selection is
unchanged. Mixed Campaign ids fail before round creation, the four-factor score
still orders the scoped set, and no Campaign event creates Research or truth.

## Release check

Before candidate freeze, enumerate the actual public commands and compare them with this inventory.
Every missing command needs an explicit mapped replacement or a user-approved removal. Run the
applicable inherited 0.3.6 regressions in addition to V5 canaries; a smaller suite is insufficient.
