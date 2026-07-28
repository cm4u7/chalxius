# Workflow data contracts: V3 compatibility and V4 additions

> **V5 authority boundary.** The V3/V4 schemas below remain readable
> compatibility contracts. They do not define V5 truth transitions and no V4
> review, acceptance marker, profile closure, import, or migration receipt is
> V5 authority. Current truth-bearing data follows `Research -> Candidate
> Release -> Certification Decision -> Fact` under `admission_contract.md`.
> Compatibility commands that submit new work map into that V5 lifecycle.

All ids are lowercase hexadecimal: fact ids are 16 characters, memory ids 12, and review,
submission, packet, and return hashes full 64-character SHA-256 values. Unknown fields fail in review
and worker-return contracts. Schema-v1 through v3 evidence remains readable; an explicitly selected
workflow-evidence V4 project uses the strict V4 task, return, bundle, campaign, and migration
contracts in the linked V4 references.

## Contents

1. Exploration memory
2. Round and worker return
3. Submission, packet, review, and admission
4. Fact Markdown
5. Automatic repair branches
6. Novelty ledger
7. V4 inheritance, append anchors, and expert assurance
8. Paper Logic and Audit Graph evidence

## Exploration memory

`memory-add` generates the id; callers must not provide `id`.

```json
{
  "kind": "conjecture",
  "status": "open",
  "claim": "One precise research direction",
  "rationale": "Why it matters and what can fail",
  "dependencies": ["0123456789abcdef"],
  "priority": 0.8,
  "novelty": 0.7,
  "testability": 0.9,
  "risk": 0.4,
  "suggested_actions": ["prove directly", "seek counterexample"],
  "tags": ["topic"],
  "source": "primary source or local artifact"
}
```

Kinds are `conjecture`, `example`, `counterexample`, `proof_attempt`, `plan`, `dead_end`,
`direction`, `obstacle`, `literature`, `computation`, and `guidance`. Metrics are finite numbers in
`[0,1]`. Dependencies must already be admitted facts.

For newly created workflow-v4 memory, prefer the compact profile:

```json
{
  "decision_profile": {
    "impact": 0.8,
    "information_value": 0.7,
    "tractability": 0.9,
    "burden": 0.2
  },
  "workload_profile": {
    "schema_version": 1,
    "policy_revision": "mathgraph-0.3.0",
    "activity": "proof",
    "audience": "internal",
    "computation": {
      "role": "none",
      "estimated_wall_seconds": 0,
      "stage_count": 0,
      "resume_required": false
    },
    "fact_output": {
      "candidate_count": 1,
      "internal_dependency_count": 0,
      "atomic_visibility_required": false
    },
    "semantics": {
      "source_claim": false,
      "source_ambiguity": false,
      "convention_sensitive": false,
      "quantifier_sensitive": false,
      "terminology_sensitive": false
    }
  }
}
```

`semantics.source_ambiguity` is an optional Chalxius workload-profile boolean.
Its absence means `false` for routing, and validation preserves the omission
exactly so a frozen pre-unified V4 profile and every dependent plan/binding hash
remain byte- and hash-identical. An explicitly present `false` is a new,
distinct profile hash; `true` is valid only when `source_claim=true`. This field
controls exploration routing only. It never replaces or weakens
`source_claim_gate`.

The four-factor profile is a user-authorized V4 revision of the guide's eight-dimensional proposal.
Do not mix `decision_profile` with the legacy eight-metric v4 input. The engine derives readiness,
projects historical metrics without rewriting them, and uses a neutral four-factor profile for a
new item that has not yet been scored. It does not synthesize eight legacy fields. Each V4 frontier
entry carries `"score_role": "priority_ordering_only"`. Score, `estimated_wall_seconds`,
`estimated_cost`, and `burden` may order priority/load only; none selects an algorithm or controls
eligibility, launch, scale, notification, continuation, or stopping. The engine binds the workload's
deterministic adoption policy into every v4 task card. See
[adoption_policy_v4.md](adoption_policy_v4.md).

An assignment-specific blackboard capability may also be frozen from memory:

```json
{
  "blackboard_write_space_ids": ["bbn-64hex"],
  "blackboard_cross_space_endpoint_node_ids": ["bbn-64hex"]
}
```

Both lists are unique existing graph IDs. Write IDs must name spaces; endpoint IDs must already be
visible. Planning rejects any ID absent from the one frozen round snapshot. When the write list is
omitted, planning retains the compatibility default of all current project spaces; when present,
the engine seals only those spaces into that worker's task card.

A frozen legacy adoption binding is immutable compatibility evidence. Validate it against its exact
recorded bytes and policy rather than recomputing it with the current trigger surface. If that
historical policy used an estimate as an experiment gate, it is archival-only: active experiment,
worker-return, ingestion, admission, and required-receipt paths reject it and require a current
round. A new policy can enter durable state only through a new round and newly frozen task card.

Memory statuses are `open`, `supported`, `challenged`, `verifying`, `resolved_by_fact`,
`replaced_by_fact`,
`resolved_by_evidence`, `resolved_no_obstruction`, `refuted_by_fact`, `dead_end`, and `blocked`.
Fact-resolved statuses require `resolution_fact_id`, `related_fact_id`, and a compatible typed
`claim_relation`:

- `resolved_by_fact`: `proves` or `strengthens`;
- `refuted_by_fact`: `refutes`;
- `replaced_by_fact`: `replaces`.

`weakens` leaves the literal seed challenged; `unrelated` leaves it open. No memory status is
`verified`.

## Round and worker return

`plan-round` stores a schema-v3 manifest with project-relative prompt, return, and designated artifact
paths, a complete assignment contract, its SHA-256, and a prompt SHA-256. The contract and generated
prompt preserve the memory item's exact claim, rationale, research source/locator, and admitted
dependencies so a clean-context worker can actually inspect the named primary artifact. Every return
repeats these exact binding fields:

```json
{
  "project_id": "problem-id",
  "round_id": "round-20260719T120000Z-1234abcd",
  "assignment_id": "a01-0123456789ab-prove",
  "assignment_sha256": "64hex",
  "worker": "a01-0123456789ab-prove",
  "memory_id": "0123456789ab",
  "mode": "prove",
  "outcome": "fact_submission",
  "notes": "limits and checks",
  "claim_relation": "proves",
  "statement": "Fully quantified atomic statement",
  "proof": "Proof citing exact predecessor ids",
  "predecessors": ["0123456789abcdef"],
  "glossary_introduces": {"symbol": "fact-local meaning"},
  "external_refs": [],
  "elementary_uses": [],
  "intuition": "Optional non-proof explanation"
}
```

Outcome-specific required fields are:

- `fact_submission`: `statement`, `proof`, `predecessors`; optional `glossary_introduces`,
  `external_refs`, `elementary_uses`, `intuition`, and `artifacts`; required `claim_relation` is one
  of `proves`, `refutes`, `strengthens`, `weakens`, `replaces`, or `unrelated`.
- `counterexample`: `claim`, `construction`, `verification`.
- `evidence`: `claim`, `method`, non-null `result`, object-list `artifacts`, and string or string-list
  `limitations`.
- `dead_end`: `claim`, `method`, `failure_mode`, `what_remains_open`.

Each artifact declaration is:

```json
{
  "path": "rounds/ROUND/artifacts/ASSIGNMENT/file.ext",
  "sha256": "64hex"
}
```

The path must be below that assignment's designated artifact directory. Symlinks, missing files,
hash mismatches, undeclared files, and files in another assignment's directory fail validation.
The hard ceiling is 256 files, 16 MiB per file, and 64 MiB total per assignment. Artifact, graph,
event, and checkpoint caps are safety and integrity limits for containment and replay; they are not
economic budgets or scheduling thresholds.

Before the canonical return exists, the worker runs
`preflight-return ROUND ASSIGNMENT --input WORK_DRAFT.json` on exact draft bytes below its work
directory. Preflight, `validate-return`, and ingestion share one complete validator; preflight
success or failure writes no project state. The worker copies passing bytes without reserialization
to the canonical return, runs `validate-return`, reports its `return_sha256`, and stops editing.
A merely present return is a draft.
`ingest-return` reruns validation, records the return and artifact hashes, and makes all declared
files read-only. Counterexamples become `challenged`, evidence `supported`, and dead ends `dead_end`;
none is a proof premise.
For a pulse-bound core commitment, main ingestion with a matching worker-final SHA converts any
complete validation, graph, or pulse-semantic exception into one immutable
`core-failures/<commitment_id>.json` record and an abort receipt that binds its content hash.
The failure record binds the assignment, canonical return hash, worker-final hash, error class, and
original error message. Optional-commitment failures create no whole-pulse abort. A canonical core
return without an ingestion receipt is not ready state: barrier and closure require ingest or abort.
For collaboration pulses, even that canonical draft is also an irreversible ordering signal:
`pulse-plan` must already exist for Wave 1, and host dispatch must already exist for Wave 2.
Ingestion transactions remain ordering evidence if canonical return or receipt files disappear.

### V4 experiment lifecycle

Experiment commands accept only a task card equal to the frozen card and SHA-256 recorded in the
round manifest. `experiment-resume` takes an `experiment_id`, checkpoint `event_id`, and a JSON
object containing the current compatibility fields. It records a content-addressed `resumed` event
only when the checkpoint is below `checkpoints/`, its current bytes still match, its completed stage
was recorded, and the compatibility hash agrees. A failed experiment rejects progress/finalization
until then. A finalized experiment rejects new events.

Finalize first resolves and hashes every selected source, rejects duplicate destination basenames
and existing byte collisions, and only then copies outputs to the assignment artifact directory.
This prevents a validation failure from leaving a partially selected artifact set. The final receipt
remains the binding used by a required experiment gate; work files and checkpoints remain nontruth.

The experiment gate is required only for multi-stage or `resume_required` computation. A
single-stage non-resumable computation remains eligible for ordinary frozen artifacts even when its
duration estimate is huge or unknown. Estimates do not change the algorithm, experiment
requirement, agent launch/scale, notification, continuation, or stop behavior.

`events.jsonl` is canonical. `events.index.sqlite3` is a schema-versioned derived cache containing
event-id lookups, byte ranges, raw-line hashes, and completed-stage entries. Event mutation writes
and syncs JSONL before the cache transaction. Cache absence, corruption, copied-log inode mismatch,
same-size log modification, or an interrupted cache commit causes validation and atomic rebuild;
an ordinary log-first crash appends only the missing tail. The cache is excluded from selected
outputs and mathematical evidence.

### Host duration notice

The duration clock is host-observed cumulative task active time: take the union of active
intervals across parallel workers, resumes, experiments, and expansion, and exclude pauses.
Exactly 1200 seconds does not trigger. The first observation strictly greater than 1200 seconds
creates exactly one immutable notice while managed work remains runnable. The notice
records the experimental nature, actual elapsed time and observed resources, progress and latest
checkpoint, importance and continuation value, and stopping impact. Worker telemetry cannot drive,
reset, or satisfy this transition.
The durable `governance_task_id` is derived from project and the task card's hashed
`host_task_scope_id`, not memory, experiment, or campaign. All bound workers and later rounds in
the same host task read one ledger; another host task does not inherit it. Interval coordinates
share one task-relative monotonic timeline, so physical overlap is unioned even when source
`clock_epoch` labels differ. The scope source must be explicit, `MATHGRAPH_HOST_TASK_SCOPE_ID`, or
`CODEX_THREAD_ID`; absence fails before round creation. Schema-2 event campaign/memory fields are
validated provenance but do not redefine the clock identity.

Any stored notice or optional response object is cooperative evidence, not authenticated user
identity or host process control. No response is required. Only an explicit recorded stop rejects
later managed writes; the CLI never pauses, terminates, or sends a process signal.

### Expert communication lint receipt

`lint-expert-document` writes one immutable receipt below
`reports/expert-lint-receipts/`. Its schema binds `project_id`, `receipt_relpath`,
`linter_revision`, `draft_sha256`, both the raw claim-card bytes SHA-256 and semantic
`claim_card_sha256`, `fact_id`, `audience`, the complete `errors` list, `ok`, the exact lint scope,
`truth_effect="communication_readiness_only"`, and `lint_receipt_sha256`.

The receipt validator can check its structure alone for audit, or re-run against exact draft and
claim-card bytes. The communication-readiness consumer requires the latter. When the bound adoption
feature `terminology_export_lint` is required, missing, failed, or stale evidence rejects release.
A passing receipt has no fact-admission effect.

### Exploration interpretation lint receipt

`lint-interpret-document` consumes only an `export-interpret-card` card for one immutable
current-project `mechanism` node with `truth_status="exploration"`. It writes below
`reports/interpret-lint-receipts/` and binds `project_id`, exact receipt/card paths, `node_id`,
node-content hash, audience, exact draft/card byte hashes, semantic card hash, complete errors,
interpretation-only scope, `truth_effect="none"`, and its own hash. Audit reopens the exact card and
current node. The interpretation and fact schemas reject one another; neither receipt admits,
promotes, or proves anything.

### Reader HTML packet and fixed visualization

`export-reader-html --packet INPUT.json` consumes strict reader-packet schema
v1 and atomically replaces
`visualizations/knowledge-map.html`. The packet binds the project id, one source
snapshot id/hash, English audience and presentation text, audit warnings,
explicit theme/target/prerequisite order, typed nodes and edges, exact original
text hashes, and native plane/status/truth labels. Unknown fields, duplicate
JSON keys, identity mismatch, dangling endpoints, prerequisite cycles,
contradictory order, exact-text drift, and Fact-authority relabeling fail before
the fixed output is written.

The packet and HTML have `truth_effect="none"`. They are derived presentation,
not a snapshot, graph plane, audit disposition, learning record, campaign
projection, or admission object. The renderer performs no model or network
call, writes no persistent history or sidecar, and never consumes the page as a
research premise. The page may keep at most 100 in-memory card-size deltas for
session undo/redo, but card minimization, appearance choice, manual positions,
and their runtime controls are not packet fields, snapshots, source evidence,
or writeback. Refresh clears them. Audit warnings remain displayable and do not
block this low-stakes export. The full schema, visual vocabulary,
deterministic-byte claim, and example packet are in
[reader_html_export.md](reader_html_export.md).

### V4 atomic verifier package

`make-bundle-verifier-task` writes `packet.md`, zero or more
`interfaces/FACT_ID.json` statement-only predecessor interfaces, and
`verification_manifest.json`. The verification manifest binds the atomic candidate manifest,
packet SHA-256, predecessor statement SHA-256 values, and interface SHA-256 values. A bundle review
return therefore includes:

```json
{
  "fact_bundle_id": "factbundle-64hex",
  "manifest_sha256": "64hex",
  "verification_manifest_sha256": "64hex",
  "packet_sha256": "64hex",
  "verdict": "correct",
  "findings": [],
  "reviewer": "fresh-verifier-identity"
}
```

The packet must contain every external admitted predecessor statement/interface and no predecessor
proof. Review and admission both revalidate the package bytes. During audit, an accepted atomic
bundle supplies local Fact provenance only after its manifest, verifier package, clean review,
acceptance marker, and exact profile-closure binding all revalidate. A damaged marker or closure
therefore removes provenance from every Fact in that bundle; hash-consistent marker tampering is
not enough to retain admission.

### Derived interfaces, indices, and read purity

`MathGraphStore.statement_interface(FACT_ID, materialize=True)` may create the
optional `fact_graph/interfaces/FACT_ID.json` projection and therefore always
passes through the project mutation guard. `materialize=False` returns the
stored interface when present or reconstructs the same validated object only in
memory when absent. Audit, validation, and claim-card readers use this pure
form. On a legacy V1-V3 root or a mode-less root in the pre-Chalxius V4 format,
the default materializing call fails before any byte changes; the explicit pure
call remains readable.

Likewise `blackboard.reindex(apply=False)` computes and compares the desired
index without writing, while `apply=True` is guarded. Experiment status and
resume validation read canonical JSONL directly: they do not create
`.mathgraph.lock`, materialize a missing log, or rebuild the derived SQLite
cache. Cache recovery occurs only in mutation paths.

For every new submission with nonempty `external_refs`, each source object must contain `key`,
`title`, `use_kind`, `cited_for`, a stable primary-source identifier, and the exact applicability
certificate specified in
[external_theorem_applicability.md](external_theorem_applicability.md). The engine rejects a bare
citation, duplicate source key, missing hypothesis/convention map, inconsistent bridge verdict, or
certificate anchor that does not occur exactly once in the hashed proof. A `use_kind="formula"`
source additionally requires `source_fidelity`, including the exact primary artifact SHA-256,
source-TeX or rendered-primary inspection, a nonempty load-bearing token list, a finding, and one
exactly-once `[SRC:SOURCE_KEY:LABEL]` proof anchor. In a new v3 round that artifact SHA-256 must occur
in the return's declared, byte-verified artifact list; formula-bearing direct submissions are
rejected. Historical admitted facts remain readable.

Every new external source object also uses `source_evidence_version: 3` and the exact
`source_trace` and `critical_audit` schemas in
[external_source_reliability.md](external_source_reliability.md). `source_trace` binds the exact
primary artifact SHA-256, versioned artifact locator, retrieval date, exact result locator, exact
UTF-8 statement transcription and its SHA-256, and a source-TeX or rendered-primary inspection
method. For formula use, its artifact hash equals `source_fidelity.artifact_sha256`.

`critical_audit` declares `profile`, `risk_triggers`, theorem-level `sanity_checks`, a canonical
`source_audit`, and bounded `source_audit_reuse`. Baseline profile contains notation/binding,
type/domain, and quantifier/scope exactly once. Strict profile contains all five check kinds and at
least one enumerated risk trigger. `source_audit` binds the same artifact hash/locator, one check
date, all three source-level search classes, empty unresolved signals, and its canonical SHA-256.
Reuse is limited to 30 days; repeated exact artifacts in one submission must reuse the first source
key. The only admissible assessments are `as_stated`, `minor_typo_corrected`, and
`official_erratum_applied`. A minor typo must be non-semantic; an official erratum carries its own
locator and SHA-256. Ambiguous, material-unofficial, contradicted, retracted, unresolved, or
misclassified results remain exploration memory. Applicability-only and source-evidence-v2
certificates remain readable as historical source trust and are never silently upgraded.

`elementary_uses` follows the exact schema and closed whitelist in
[elementary_result_exemption.md](elementary_result_exemption.md). Each entry binds a result,
category, nonempty hypothesis-witness list, exact used conclusion, nonempty scope-limitation list,
packet-reconstructible check, and unique exactly-once `[ELM:KEY]` proof anchor. It is available only
for non-attributed fixed/local textbook steps; the independent verifier decides semantic eligibility.

## Submission, packet, review, and admission

A v3 submission binds the complete logical fact plus worker, memory, round, assignment identity,
assigned research claim, and `claim_relation` in `submission_sha256`. `make-verifier-task` freezes a
packet under
`verification_queue/by-hash/<packet_sha256>.md` and a manifest under
`verification_queue/by-fact/<fact_id>.json`. Its host payload repeats the hash-bound
`assigned_claim` and `claim_relation` beside the packet and review paths, so the clean-context
verifier receives the semantic relation it must check without access to exploration memory.

If the packet contains external-source evidence, the verifier may open the exact primary artifact,
the exact issue-search locators, and perform the tiered current status checks using the cited
identifier or title. It repeats baseline theorem checks for every item, groups status work by
`source_audit.audit_sha256`, spot-checks one current status query for a baseline-only group, and
repeats all three searches plus the two extra theorem checks for strict evidence. This is an
exception to project isolation, not permission to search for a replacement theorem: project facts
and memory remain inaccessible, secondary summaries cannot establish a correction, and source
unavailability, hash mismatch, stale reuse, or risk misclassification is a review gap.

The packet prints the assigned research claim and asserted relation. The verifier must reject an
incorrect relation even if the submitted theorem is true. The verifier return contains exactly:

```json
{
  "fact_id": "0123456789abcdef",
  "submission_sha256": "64hex",
  "packet_sha256": "64hex",
  "verdict": "correct",
  "critical_errors": [],
  "gaps": [],
  "repair_hints": [],
  "reviewer": "fresh-verifier-identity"
}
```

The gateway adds `reviewed_at`, a semantic `review_id`, and `record_sha256`, then stores the review
append-only at `reviews/by-id/<review_id>.json`. The submitter and reviewer are compared case-folded.
A `correct` verdict cannot contain errors/gaps; `reject` must contain at least one. Admission requires
the latest review's explicit id and writes a hash-bound acceptance event. The `record-review` CLI
receipt repeats `fact_id`, `verdict`, and a derived `clean` flag; the `admit` receipt reports state
`accepted`, matching the persisted submission state.

Submission states are `pending_review`, `rejected`, `accepted`, and `revoked`. A later rejection
prevents an older clean review from being admitted. An accepted fact cannot be re-reviewed; a new
objection enters the challenge/revocation workflow.

## Fact Markdown

Facts use YAML-compatible frontmatter whose complex values are JSON flow values, followed by exactly
one `## statement`, exactly one `## proof`, and at most one trailing `## intuition`. Other level-two
headings are preserved inside sections. Before submission and admission, serialization is parsed back
and compared field-for-field, then its content id is recomputed.

The 16-hex Danus-compatible id hashes problem id, sorted predecessors, local glossary, normalized
statement, and normalized proof. Author, bibliography metadata, and intuition are outside that id;
scope-bearing citation claims must therefore remain in the hashed proof text.

## Automatic repair branches

`plan-repair-round MEMORY_ID --trigger-memory-id CHALLENGE_ID` creates two new exploration entries:

1. a minimal correction that changes the fewest load-bearing symbols, hypotheses, domains, or
   quantifiers forced by the challenge;
2. a strongest-defensible replacement that attacks overstrong variants and minimizes
   counterexamples.

It then plans one bound worker round for the two branches. Both remain exploration until separately
submitted, reviewed, and admitted.

## Novelty ledger

`novelty-record` appends one query-level event for a memory or admitted fact. Required fields are
`subject_kind`, `subject_id`, `corpus`, `query`, `status`, and `hits`; optional `notes` is prose.
Statuses are `known`, `likely_known`, `no_exact_match_found`, and `unsearched`. Every hit has `title`,
`locator`, and relation `exact`, `partial`, or `background`. `known` requires an exact hit, while
`no_exact_match_found` forbids one. The generated timestamp and event hash make the search record
auditable, but they do not establish priority.

## Unified round profile closure

A new unified V4 `round.json` contains `profile_obligations`. Its value is the
canonical output of the bound assignment execution profiles and contains the
feature-status aggregation, exact required-feature list, per-assignment feature
statuses, and `obligations_sha256`. Absence on a historical unified round is a
replan blocker, not permission to reconstruct a weaker checklist.

`profile-closure-record ROUND_ID --input INPUT.json --actor ACTOR` consumes:

```json
{"evidence": [{"feature": "one_exact_required_feature", "evidence_kind": "typed"}]}
```

The feature names must equal the frozen required-feature set exactly. The
write-once receipt is stored at
`governance/unified-mode/profile-closures/by-round/ROUND_ID.json` and binds:

- schema/policy/project, round id and round creation time;
- reasoning mode/event, round-manifest hash, frozen profiles and obligation hash;
- the exact input evidence and re-materialized evidence bindings;
- every assignment's execution-profile, assignment, task-card, return, and
  ingestion hashes plus canonical outcome and effect;
- actor, record time, `truth_effect="workflow_readiness_only"`, and the
  content-derived `profileclose-*` id.

The feature evidence families are closed:

- clean-context panel: machine pulse closure plus procedural host-capacity
  attestation, exact selected required assignments, and full eligible width;
- barriered pulse: a `closed_machine_ready` native pulse covering every
  required assignment;
- specialist escalation: procedural host attestation with core and specialist
  roles, distinct specialties, distinct artifact hashes, and artifacts only in
  each exact assignment's return/artifact path;
- campaign expansion: one or more campaign entries forming an exact,
  non-overlapping assignment partition; each assignment must carry that
  campaign in its task card, with current-round native expansion event IDs and
  distinct, scoped before/after JSON artifacts;
- Paper Logic/Audit: reviewed, current, non-superseded `pls-*` snapshots covering
  the exact assignment source hash; Audit additionally requires a current Logic
  base and cross-feature descent from the chosen Logic snapshot;
- full Paper mirror: native full-fidelity projection receipts of the chosen,
  current assignment Paper snapshot;
- computation: finalized native experiment receipts for every required
  assignment;
- novelty: sorted unique native event IDs recorded no earlier than the round
  and covering each required assignment's memory;
- expert synthesis: native passing expert/interpret lint receipt plus exact
  draft/card bytes and a procedural scope artifact binding the assignment task
  card, return, ingestion, outcome, and effect.

Evidence levels are not interchangeable. Native validation is
`machine_verified`; host-only claims are `procedural_host_attestation`; a
composite is `mixed_procedural_and_machine_verified`. No-required-feature rounds
return `not_required` from `profile-closure-status` and permit no receipt.
Required closure is revalidated before single-Fact or atomic-bundle verifier
construction, review recording, and admission, on accepted idempotent retry,
and during current audit. Direct low-level verifier-bundle and FactBundle
writers lack admission authority and fail before writing; only the owning
`MathGraphStore` may pass authority after closure succeeds. It is deliberately
outside the invariant Fact admission contract, so the Fact-contract hash is
unchanged.

## V4 inheritance, append anchors, and expert assurance

A project-level legacy migration receipt binds the full source-tree digest, source project semantic
hash, immutable legacy inventory, byte length and SHA-256 of every inherited append-only prefix,
mutable projection policy, and the rule that recorded legacy assurance is never relabeled V4.

Inherited rounds and adoption bindings remain frozen under their recorded policy. The current
four-factor ordering and actual-time continuation rules apply only to newly planned V4 rounds; do
not rewrite an inherited task card, assignment, return, or receipt to simulate an upgrade.

For historical acceptance events, only an absent `evidence_version` or strict integer version `1`
is legacy provenance. Versions `2`, `3`, and `4` must pass their hash-bound validators. Every other
explicit value is invalid rather than legacy, including stringified versions and booleans.

Each post-migration event written to a shared legacy JSONL path has one content-addressed sidecar in
`migrations/append-anchors/`. The sidecar binds writer engine, governed log path, event id, exact
event hash, and event object. V4 audit compares both directions: every suffix event needs one
sidecar, and every sidecar needs one visible suffix event. This detects cooperative suffix edits,
truncation, and wrong-engine writes without claiming authenticated filesystem security.

New Chalxius sidecars retain `writer_engine: "operate-mathgraph-unified"`, the current
package writer identity. The validator also accepts the frozen historical value
`"mathgraph-chalk-version"` as pre-Chalxius V4 schema-lineage evidence and
includes that original value when recomputing its anchor id; historical anchors
are therefore neither rewritten nor rehashed. No other writer identity is
accepted.

An expert claim card contains:

```json
{
  "admission_evidence_version": 3,
  "assurance_label": "legacy-v3-inherited",
  "limitations": [
    "Admission assurance is inherited from workflow-evidence v3; this V4 export does not relabel the fact as V4-reviewed."
  ]
}
```

A newly V4-reviewed fact instead uses evidence version `4` and
`assurance_label: "v4-independent-review"`. The policy revision on the card identifies the export
schema; it does not overwrite the fact's admission assurance.

## Paper Logic and Audit Graph evidence

The optional `paper_logic/` store uses a separate feature revision
`paper-logic-1`. It does not change the project container schema or the global V4
`policy_revision: "mathgraph-0.3.0"`.

Paper node prefixes identify their plane:

- `psn-64hex`: exact source artifact or source unit;
- `prn-64hex`: researcher reconstruction object;
- `pan-64hex`: paper audit object.

Paper edge prefixes are `pse-`, `pre-`, and `pae-`. Revisions, reviews,
transactions, snapshots, bridges, and projections use `plr-`, `plv-`, `plt-`,
`pls-`, `plb-`, and `plp-`, each followed by a full SHA-256.

A staging bundle has exact top-level keys:

```json
{
  "schema_version": 1,
  "feature_revision": "paper-logic-1",
  "project_id": "problem-id",
  "paper_id": "source-specific-id",
  "graph_kind": "logic",
  "domain_profile": "philosophy",
  "builder": "builder-id",
  "builder_context_id": "fresh-builder-context",
  "source": {},
  "base_snapshot_id": "",
  "supersedes_snapshot_id": "",
  "coverage": {},
  "nodes": [],
  "edges": []
}
```

Logic graphs have no base snapshot. Audit graphs require an exact frozen base.
Every input edge must be exactly implied by node-declared ports; extra,
missing, reversed, or neighboring-evidence edges fail. A revision is not
query-visible until its two required independent reviews pass and `freeze`
publishes an immutable snapshot.

An inference's `defeater_claim_ids` are ports, not prose annotations: each
produces one typed `defeats` edge from the defeater claim to that inference.
At least one `headline` target is required; other argument-relevant components
may terminate at declared `supporting` targets without becoming headline
premises.

Every Paper Logic object, review, readiness facet, bridge, mirror projection,
and snapshot has `truth_effect: "none"`. Complete schemas and correction rules
are in [paper_logic_graph_v1.md](paper_logic_graph_v1.md).
