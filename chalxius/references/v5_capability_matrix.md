# V5 capability preservation matrix

This matrix governs the 0.3.6-to-0.4.0 kernel upgrade, the additive 0.4.1
CHX-ledger patch, the explicitly enabled 0.4.2 adverse-routing release, and the
prospective 0.4.3 assurance and routing repairs.
The isolated prospective 0.4.4 `Back to the Future` candidate restores two bounded context-planning
connections: exact promoted-query snapshot selection and enum-only mode hints.
It also replaces full background bodies in new cards with an exact retrievable
index. The copy-on-write field repair adds source capabilities, runtime-bound
worker ledgers, adverse-assignment provenance, nonrecursive admission recovery,
legacy-premise witnesses, and explicit read-only prior-Fact inventory. Historical
cards and running work keep their frozen contracts.
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
| Single-Fact certification | compatibility commands `submit`, `packet`, `make-verifier-task`, `record-review`, `admit`, `revoke`; primary V5 transitions `candidate-release`, `candidate-release-check`, `verifier-capsule`, `certification-record`, `certification-decision-check`, `fact-admit` | adapt | CHX-009, CHX-021, CHX-024, CHX-025, CHX-032, CHX-039, CHX-048, CHX-058, CHX-068; field CHX-005–006 | exact candidate, hashed named-premise witnesses for legacy conditional reuse, fresh verifier capsule, immutable decision, nonrecursive/idempotently recoverable admission, and cascade revocation |
| Atomic FactBundles | `fact-bundle-submit`, `fact-bundle-record-review`, `fact-bundle-admit` | keep/adapt | CHX-022, CHX-029, CHX-030, CHX-034, CHX-039 | all-or-none mini-DAG visibility without profile-closure coupling |
| Research memory and repair | `memory-add` including `--current-assurance`, `memory-update`, `frontier`, `plan-repair-round` | adapt | CHX-011, CHX-013, CHX-015, CHX-030, CHX-039, CHX-041; field CHX-001 | cumulative Research Ledger; exact source capabilities for source-dependent planning; counterexamples and insights survive later rounds; compact four-factor automatic ordering with legacy eight-metric read projection, no cutoff, and explicit low-score scheduling |
| Adverse routing evolution and attack report | `attack-route-enable`, `attack-route-status`, `attack-report`, `attack-route-decide`, `attack-route-disable`; conditional task-card/return fields | adapt; explicit user request 2026-07-28 | none; additive opt-in capability | project-local explicit opt-in; immutable case/proposal/decision/rule lineage; operator-only activation; attack report separate from CHX; future-only approved rules; frozen/0.4.0 work unchanged; eight ordinary baseline rules plus one computation-evidence-gated program-math rule on generated reviews only; no Fact authority |
| Novelty evidence | `novelty-record`, `novelty-status` | keep | CHX-020, CHX-033 | query/corpus/date-bounded status; no automatic campaign/paper expansion |
| Three-plane task execution | `plan-round`, `round-status`, `preflight-return`, `validate-return`, `ingest-return`, `work-unit-abort` plus immutable task cards | adapt | CHX-004, CHX-006–013, CHX-016, CHX-019, CHX-024–028, CHX-031, CHX-032, CHX-034, CHX-035, CHX-037, CHX-052, CHX-059, CHX-060, CHX-062–067; `run-20260728T180420869461Z-5d4e882a1c9c/CHX-001`; `run-20260729T081913970946Z-2f0a9e345447/CHX-001`; this run/CHX-002–003; field CHX-002–003 | control/state/narrative planes remain distinct; exact candidate runtime/card/snapshot/return/artifact binding; complete source Research dossier; task-referenced current-authority snapshot with exact target capabilities; outcome-independent adverse assignment provenance; Main-planner-compiled context receipt; prospective marker and old-card compatibility; local quarantine; validated abort authority projects unfinished assignments as `frozen_aborted`, exposes the abort id, and leaves zero live awaiting returns, with strict audit consistency |
| Blackboard exploration | `blackboard-space-create`, `blackboard-node-add`, `blackboard-edge-add`, `blackboard-type-register`, `blackboard-show`, `blackboard-query`, `blackboard-snapshot`, `blackboard-snapshot-query`, `blackboard-reindex`, `blackboard-promote-node` | keep/adapt | CHX-018, CHX-026, CHX-027, CHX-030, CHX-039–041 | typed cumulative nodes/edges; immutable snapshots; no automatic Fact promotion |
| Pulse collaboration | `pulse-plan`, `pulse-status`, `pulse-barrier`, `pulse-dispatch`, `pulse-void`, `pulse-close`, `pulse-abort`, `pulse-audit` | adapt | CHX-001–003, CHX-005, CHX-014, CHX-015, CHX-017, CHX-018, CHX-022, CHX-023, CHX-027–031, CHX-036, CHX-037, CHX-039, CHX-041, CHX-048, CHX-052 | same-snapshot Wave 1 and snapshot-mediated Wave 2 remain; each contribution ingests independently; no peer destruction |
| Reasoning profiles and adoption | `mode-init`, `mode-status`, `mode-switch`, `adoption-plan` | adapt | CHX-005, CHX-020, CHX-033, CHX-036, CHX-039, CHX-048 | fast/auto/deep remain exploration budgets; adoption remains advice; neither creates universal certification closure |
| Process readiness (V4 profile-closure compatibility) | `profile-closure-status`, `profile-closure-record` | adapt; user-approved 2026-07-28 | CHX-014, CHX-023, CHX-029, CHX-036, CHX-039, CHX-048 | retain and strengthen repair suggestions; recording appends guidance to Research only and has no admission authority |
| Campaigns | `campaign-create`, `campaign-activate`, `campaign-status`, `campaign-target-add`, `campaign-target-archive`, `campaign-update` | keep/adapt | CHX-020, CHX-033, CHX-039 | explicit planning/history capability remains; no automatic per-repair expansion gate |
| Claims, conventions, and exposition | `claim-add`, `claim-show`, `claim-variant`, `convention-add`, `convention-show`, `export-claim-card`, `export-interpret-card`, `lint-expert-document`, `lint-interpret-document` | keep | CHX-006, CHX-007, CHX-009, CHX-010, CHX-016, CHX-019, CHX-024, CHX-034 | exact interfaces, quantifiers, conventions, and lint semantics remain available |
| Replayable computation | `experiment-start`, `experiment-event`, `experiment-observe`, `experiment-decision`, `experiment-status`, `experiment-resume`, `experiment-finalize` | keep/adapt | CHX-039, CHX-048, CHX-054, CHX-059, CHX-066, CHX-067 | immutable commands/artifacts/checkpoints and independent replay remain; current V5 stages bind formula, domain, representation, approximation budget, output meaning, and independent checks; task-local binding only |
| Paper Logic and Audit | `paper-logic-init`, `paper-logic-stage`, `paper-logic-record-review`, `paper-logic-freeze`, `paper-logic-status`, `paper-logic-show`, `paper-logic-query`, `paper-logic-audit`, `paper-logic-link-exploration`, `paper-logic-project-blackboard` | keep/adapt | CHX-033, CHX-038, CHX-043 | source/reconstruction/audit separation, append-only correction, current snapshot and nodewise target binding |
| Reader visualization | `export-reader-html`, packet v1, renderer revision 17 | adapt | CHX-042; this run/CHX-001 | backward-compatible packet validator; bounded V5 titles; hash6 plus role/plane canvas identity; MathJax-ready historical Fact summaries with exact source preserved; selected drag anchors plus bounded radial-memory neighborhood equilibrium; no authority effect |
| Project background | single `PROJECT_BACKGROUND.md` nontruth source; `project-background-index`, `project-background-read` | adapt | CHX-040, CHX-048, CHX-051, CHX-052; `run-20260728T180420869461Z-5d4e882a1c9c/CHX-001`; this run/CHX-001 | generation/refresh requires user instruction; new 0.4.4 cards freeze a complete exact-byte chunk index and immutable round snapshot instead of embedding the body; Main/Operator may inspect, Main-planner selection plus unselected counts are explicit, and the dedicated Host dispatch role is unchanged; every chunk remains hash-bound and rehydratable after context compaction; old cards keep their full-body schema; Reader compatibility remains; authority overrides background status prose |
| Migration and legacy import | `upgrade-project-copy`, `upgrade-workflow`, `import-danus` | adapt | CHX-040, CHX-044–047, CHX-051, CHX-052 | read-only historical access; user-directed summary generation; default reading when present; no V5 authority inheritance |
| Chalxius Learner | `scripts/learn`, `scripts/learning_graph.py`, academic routing | keep | none | explicit activation, nontruth-only writes, frozen read-only mounts |
| External-source and elementary gates | source/applicability validators and controlled elementary ledger | keep/adapt | CHX-033, CHX-064, CHX-065, CHX-069, CHX-071, CHX-072 | current source-evidence v4 binds complete hypotheses and conclusions, query evidence, structured status, and typed transports; v3 remains historical/readable |
| Verifier capability isolation | `scripts/prepare_verifier_capsule.py` | keep/adapt | CHX-039, CHX-041, CHX-058, CHX-061, CHX-068, CHX-070, CHX-071 | exact allowlist, neutral materialization, complete decision template, standalone field-level preflight, fresh independent verifier, no exploration workspace access |
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

- campaign-scoped automatic frontier selection (`frontier --campaign` is used
  by V4 but ignored by the V5 adapter);
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

## Release check

Before candidate freeze, enumerate the actual public commands and compare them with this inventory.
Every missing command needs an explicit mapped replacement or a user-approved removal. Run the
applicable inherited 0.3.6 regressions in addition to V5 canaries; a smaller suite is insufficient.
