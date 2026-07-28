# V5 capability preservation matrix

This matrix governs the 0.3.6-to-0.4.0 upgrade. Exact Chalxius 0.3.6 behavior is the preservation
baseline. The four-state V5 model constrains only the truth-bearing critical path; it is not a
license to delete unrelated product capabilities.

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
| Project and Fact reading | `init`, `status`, `audit`, `show`, `search`, `closure`, `context`, `targets`, `set-targets`, `export-mermaid` | keep/adapt | CHX-039, CHX-040, CHX-048 | empty V5 Fact start; V4 readable nontruth; clean Fact closure and audit |
| Single-Fact certification | compatibility commands `submit`, `packet`, `make-verifier-task`, `record-review`, `admit`, `revoke`; primary V5 transitions `candidate-release`, `verifier-capsule`, `certification-record`, `fact-admit` | adapt | CHX-009, CHX-021, CHX-024, CHX-025, CHX-032, CHX-039, CHX-048 | exact candidate, fresh verifier capsule, immutable decision, admission and cascade revocation |
| Atomic FactBundles | `fact-bundle-submit`, `fact-bundle-record-review`, `fact-bundle-admit` | keep/adapt | CHX-022, CHX-029, CHX-030, CHX-034, CHX-039 | all-or-none mini-DAG visibility without profile-closure coupling |
| Research memory and repair | `memory-add`, `memory-update`, `frontier`, `plan-repair-round` | adapt | CHX-011, CHX-013, CHX-015, CHX-030, CHX-039, CHX-041 | cumulative Research Ledger; counterexamples and insights survive later rounds |
| Novelty evidence | `novelty-record`, `novelty-status` | keep | CHX-020, CHX-033 | query/corpus/date-bounded status; no automatic campaign/paper expansion |
| Three-plane task execution | `plan-round`, `round-status`, `preflight-return`, `validate-return`, `ingest-return`, `work-unit-abort` plus immutable task cards | adapt | CHX-004, CHX-006–013, CHX-016, CHX-019, CHX-024–028, CHX-031, CHX-032, CHX-034, CHX-035, CHX-037, CHX-052 | control/state/narrative planes remain distinct; exact card/snapshot/return binding; local quarantine |
| Blackboard exploration | `blackboard-space-create`, `blackboard-node-add`, `blackboard-edge-add`, `blackboard-type-register`, `blackboard-show`, `blackboard-query`, `blackboard-snapshot`, `blackboard-snapshot-query`, `blackboard-reindex`, `blackboard-promote-node` | keep/adapt | CHX-018, CHX-026, CHX-027, CHX-030, CHX-039–041 | typed cumulative nodes/edges; immutable snapshots; no automatic Fact promotion |
| Pulse collaboration | `pulse-plan`, `pulse-status`, `pulse-barrier`, `pulse-dispatch`, `pulse-void`, `pulse-close`, `pulse-abort`, `pulse-audit` | adapt | CHX-001–003, CHX-005, CHX-014, CHX-015, CHX-017, CHX-018, CHX-022, CHX-023, CHX-027–031, CHX-036, CHX-037, CHX-039, CHX-041, CHX-048, CHX-052 | same-snapshot Wave 1 and snapshot-mediated Wave 2 remain; each contribution ingests independently; no peer destruction |
| Reasoning profiles and adoption | `mode-init`, `mode-status`, `mode-switch`, `adoption-plan` | adapt | CHX-005, CHX-020, CHX-033, CHX-036, CHX-039, CHX-048 | fast/auto/deep remain exploration budgets; adoption remains advice; neither creates universal certification closure |
| Process readiness (V4 profile-closure compatibility) | `profile-closure-status`, `profile-closure-record` | adapt; user-approved 2026-07-28 | CHX-014, CHX-023, CHX-029, CHX-036, CHX-039, CHX-048 | retain and strengthen repair suggestions; recording appends guidance to Research only and has no admission authority |
| Campaigns | `campaign-create`, `campaign-activate`, `campaign-status`, `campaign-target-add`, `campaign-target-archive`, `campaign-update` | keep/adapt | CHX-020, CHX-033, CHX-039 | explicit planning/history capability remains; no automatic per-repair expansion gate |
| Claims, conventions, and exposition | `claim-add`, `claim-show`, `claim-variant`, `convention-add`, `convention-show`, `export-claim-card`, `export-interpret-card`, `lint-expert-document`, `lint-interpret-document` | keep | CHX-006, CHX-007, CHX-009, CHX-010, CHX-016, CHX-019, CHX-024, CHX-034 | exact interfaces, quantifiers, conventions, and lint semantics remain available |
| Replayable computation | `experiment-start`, `experiment-event`, `experiment-observe`, `experiment-decision`, `experiment-status`, `experiment-resume`, `experiment-finalize` | keep/adapt | CHX-039, CHX-048, CHX-054 | immutable commands/artifacts/checkpoints and independent replay remain; V5 load-bearing series products add a valuation-derived order budget and bound depth extension; task-local binding only |
| Paper Logic and Audit | `paper-logic-init`, `paper-logic-stage`, `paper-logic-record-review`, `paper-logic-freeze`, `paper-logic-status`, `paper-logic-show`, `paper-logic-query`, `paper-logic-audit`, `paper-logic-link-exploration`, `paper-logic-project-blackboard` | keep/adapt | CHX-033, CHX-038, CHX-043 | source/reconstruction/audit separation, append-only correction, current snapshot and nodewise target binding |
| Reader visualization | `export-reader-html`, packet v1, renderer revision 15 | keep/adapt | CHX-042 | unchanged renderer and authority labels; deterministic V5 projection adapter |
| Project background | single `PROJECT_BACKGROUND.md` nontruth summary | adapt | CHX-040, CHX-048, CHX-051, CHX-052 | generation/refresh requires user instruction; every substantive V5 work unit and Reader reads the existing full body/hash by default; absence never generates |
| Migration and legacy import | `upgrade-project-copy`, `upgrade-workflow`, `import-danus` | adapt | CHX-040, CHX-044–047, CHX-051, CHX-052 | read-only historical access; user-directed summary generation; default reading when present; no V5 authority inheritance |
| Chalxius Learner | `scripts/learn`, `scripts/learning_graph.py`, academic routing | keep | none | explicit activation, nontruth-only writes, frozen read-only mounts |
| External-source and elementary gates | source/applicability validators and controlled elementary ledger | keep | CHX-033 only affects auto-routing | exact source/version/glyph/erratum/applicability checks remain admission requirements |
| Verifier capability isolation | `scripts/prepare_verifier_capsule.py` | keep/adapt | CHX-039, CHX-041 | exact allowlist, fresh independent verifier, no exploration workspace access |

## Three-plane invariant

Every V5 task card binds all three planes without embedding their full contents in the prompt:

1. control: compact prompt, bounded control-only follow-ups, exact final handoff;
2. mathematical state: one frozen bounded snapshot and exact read/write capabilities;
3. narrative: bounded rationale, summary, intuition, limitations, and open boundary.

The task card remains immutable capability data. Removing it, replacing it with prompt prose, or
allowing a worker to infer capabilities from filesystem visibility is not a permitted simplification.

## Release check

Before candidate freeze, enumerate the actual public commands and compare them with this inventory.
Every missing command needs an explicit mapped replacement or a user-approved removal. Run the
applicable inherited 0.3.6 regressions in addition to V5 canaries; a smaller suite is insufficient.
