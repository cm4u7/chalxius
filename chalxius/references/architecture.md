# Architecture and trust model

> **Historical V4 storage reference.** This file preserves the detailed V4
> object layout and audit vocabulary for read compatibility. It is not the V5
> authority model. The current prospective path is `Research -> frozen
> nontruth Fact package -> independent verifier decision -> Gateway Research
> certification`. The older Candidate Release / Certification Decision CLI is
> procedurally reserved for an explicitly selected 0.x completion or audit; the
> runtime does not authenticate pre-1.0 provenance and no identity gate is
> implied. A packager-requested split pauses Fact work and returns to a Research
> repair worker plus ordinary proof/source supervision; no Fact-side split
> supervisor exists. The historical fast lane is only bounded one-to-one
> complete-node minor COW with a full same-verifier component recheck; split or
> structural ambiguity returns to ordinary Research, and Gateway stays
> independent. See `unified_architecture.md` and `admission_contract.md` for current
> rules. Everything below remains frozen V4 storage history.

```text
hash-bound execution profile -> required: full-width distinct clean-context dispatch
                             -> available: opt-in dispatch; not_applicable: omit
host observation -> active-interval union + strict >1200s notice-only observation
paper source -> reviewed Paper Logic snapshot -> reviewed correctable Audit snapshot
             -> bounded query or governed Blackboard mirror (all nontruth)
main strategy -> workload preflight + compact adoption binding
              -> exploration memory/blackboard (not truth)
              -> frozen snapshot + bound V4 worker rounds
              -> pulse plan -> ingestion barrier -> cross-review closure/abort
              -> typed return + shared visibility receipt
              -> candidate submission or atomic mini-DAG
              -> statement-only verification bundle
fresh bundle-only verifier -> immutable structured review
gateway -> hash-bound acceptance event/marker -> content-addressed fact DAG
counterexample -> two-branch repair round -> same ordinary verifier gate
```

## Load-bearing invariants

1. Only `fact_graph/facts/*.md` are proved premises.
2. Local facts require a clean independent review; finalized imports are explicitly inherited trust.
3. Fact ids bind exact logical content and direct admitted predecessors; facts must losslessly round-trip.
4. Project ids match exactly. Candidate-on-candidate proof chains are forbidden.
5. The latest review controls admission and every accepted fact links one immutable clean review,
   submission hash, packet hash, and stored-fact hash.
6. Exploration outcomes never receive a truth label. Fact resolution names the resolving admitted id
   and a typed relation: `proves`, `refutes`, `strengthens`, `weakens`, `replaces`, or `unrelated`.
7. A V4 worker first runs the shared read-only `preflight-return` core on mutable work-directory
   bytes; only a passing draft is copied exactly to the manifest-bound canonical return.
   Ingestion derives the canonical return SHA-256 and locks the return plus every declared artifact
   read-only; an optional legacy worker-final hash is only an equality assertion. Undeclared or
   out-of-directory artifacts fail validation.
8. In V4, active campaign proof targets derive `TARGETS.txt`; target certificates bind every closure
   file and audit rejects an independently edited projection.
9. Revocation removes all transitive descendants and preserves historical acceptance evidence.
10. Notation remains fact-scoped; global glossary flattening is forbidden.
11. Unknown roles and verifiers receive no project CLI capability. Role labels remain cooperative,
    not authenticated OS principals.
12. Every external source used by a new submission carries a submission-bound applicability
    certificate, while its scope-bearing witnesses are repeated in the fact-id-hashed proof. A fresh
    verifier checks the exact cited primary-source version and may not substitute a different result.
13. External-source evidence v3 binds exact source bytes, a statement transcription and its hash,
    three per-item baseline checks, explicit strict-risk escalation, one canonical status audit per
    exact artifact with a 30-day reuse window, a constrained disposition, and `[CRIT:...]` proof
    anchors. Formulas, bridge/transport, corrections, and other declared high-risk uses require the
    two additional strict checks. Ambiguous, material-unofficial, contradicted, retracted, unresolved,
    or misclassified source claims cannot enter a new submission.
14. Formula-level source use binds the exact primary artifact, inspection method, load-bearing glyphs,
    and a unique proof anchor. Plain extracted text is insufficient for glyph-level claims.
15. Novelty is query-scoped evidence. The append-only ledger binds subject, query, corpus, result
    status, and hits; `no_exact_match_found` never means globally new.
16. A non-attributed fixed/local textbook invocation may use the closed elementary-result ledger.
    Its hypotheses, used conclusion, scope limits, reconstruction, and `[ELM:...]` proof anchor are
    submission-bound; semantic eligibility remains a fresh-verifier obligation.
17. Every formula-level source-fidelity artifact hash in a new v3 round must equal a declared,
    byte-verified assignment artifact hash. Direct formula submissions are rejected.
18. Every v4 task card binds the mandatory control/mathematical-state/narrative protocol and a
    deterministic workload-shape feature policy. Multi-stage or resume-required experiment
    mechanics cannot be silently disabled by a worker; estimates never activate them.
19. A required multi-stage or resume-required computation cannot validate without a finalized
    experiment receipt whose
    selected outputs are declared frozen artifacts. Experiment commands must match the frozen round
    card; failed jobs require a byte- and compatibility-bound resume; selected-output collisions
    fail before any artifact copy; finalized jobs reject new events. Canonical experiment JSONL is
    append-first; its SQLite lookup cache is derived, byte-bound, and rebuildable rather than truth.
    Read-only status/resume validation never materializes the log, rebuilds that cache, or creates
    the project advisory lock; recovery is mutation-only.
20. Atomic bundles remain outside truth until one clean review and all-or-none acceptance marker.
    Their reviews bind an immutable verifier packet/manifest containing external predecessor
    statement interfaces but no predecessor proofs. Accepted bundle facts participate in ordinary
    show/search/context/closure, campaign targets, statement interfaces, and cascade revoke.
    Missing statement-interface projections are reconstructed byte-pure with `materialize=False`;
    the default materializing API and applying reindex remain guarded mutations.
21. Legacy-to-unified inheritance is copy-only. Legacy immutable objects stay byte-exact, shared logs
    retain an exact legacy prefix plus sidecar-anchored V4 suffix, derived projections remain
    rebuildable, and inherited assurance is never relabeled as V4 review.
22. The compact four-factor model is a user-authorized V4 revision. Legacy eight-dimensional
    memory is a read-only compatibility projection. Every frontier score has role
    `priority_ordering_only`: no score, estimated budget, duration, cost, or burden controls
    algorithm choice, eligibility, launch, scale, notification, continuation, or stopping.
23. A bound execution profile controls high-cost exploration. When its panel feature is required,
    work uses all callable clean-context slots while genuinely distinct eligible channels remain;
    when available the panel is opt-in, and when not applicable it is omitted. Only the
    host-observed task active-interval union can trigger a notice:
    exactly 1200 seconds does not trigger; the first observation strictly greater than 1200 seconds
    creates one five-field notice without blocking continuation or sending a process signal. A
    host/user response is optional; only an explicit recorded stop forbids later managed writes.
    The hashed task-card
    `host_task_scope_id` separates later independent host tasks even when they reuse a campaign;
    source-clock epochs share one task-relative timeline, and campaign/memory IDs remain provenance
    when one host task crosses campaigns. No stable scope means planning fails before any round
    write. Worker telemetry is non-authoritative.
24. A frozen legacy adoption binding remains byte-exact under its recorded policy. An
    estimate-gated historical binding is audit-readable but cannot enter active execution; replan
    under the current four-factor and actual-time policy. Historical task cards and receipts are
    never rewritten.
25. Expert lint emits immutable, project-contained communication evidence bound to exact draft and
    claim-card bytes. Required communication readiness consumes a current passing receipt; audit
    validates stored receipt structure and path. This boundary never promotes mathematical truth.
26. A V4 collaboration pulse binds a write-once plan, actual first-wave ingestion receipts, a fresh
    barrier snapshot, committed cross-review evidence, and exactly one closure or whole-pulse abort.
    Core commitments cannot be voided. A main ingest failure after a canonical core return's matching
    worker-final hash writes immutable assignment/return/error evidence bound by the automatic abort.
    A canonical core return without an ingestion receipt blocks barrier and closure until ingest or
    abort. Draft preflight and canonical validation remain read-only. Procedural readiness is
    distinct from trusted-host machine-verified clean-context readiness. The plan must predate all bound Wave-1 canonical
    returns, and each host dispatch must follow its native spawn but predate that Wave-2 canonical
    return; canonical markers plus transaction-ledger evidence reject retrospective attestation.
27. Blackboard history is append-only while current projection deterministically excludes
    superseded/closed nodes and retracted placements. Legal namespaced custom types remain opaque
    until registered. Cross-project, cross-machine, and multi-root federation is disabled.
28. New V4 task cards bind fixed hard safety and integrity caps for experiment events and bytes,
    checkpoints, governance records, and pulse controls. Pre-write cap failure has zero effect.
29. Paper Logic is an optional additive store with separate source, researcher-reconstruction, and
    paper-audit planes. Only independently reviewed immutable snapshots are query-visible.
    Blackboard copies are reserved full-fidelity mirrors with exact projection receipts, not paper
    authority or truth. Audit corrections append challenges, dispositions, and replacement
    snapshots; they never rewrite old audit nodes. See `paper_logic_graph_v1.md`.
30. The integrated teaching boundary is snapshot-only. The lightweight unified nontruth learning
    plane may bind frozen Fact artifacts and immutable `pls-*` and `bbs-*` objects; no research
    runtime is invoked, no source truth is inherited, learner evidence never writes back, and
    algorithm reuse from Grill Me does not imply a Danus runtime.
31. Every new unified V4 round freezes exact `profile_obligations`. Required
    high-cost exploration must close through one immutable, per-round receipt
    that binds the manifest, profiles, task cards, returns, canonical ingestion
    outcomes/effects, and typed evidence before single-Fact or atomic-bundle
    verification/admission. No-required-feature rounds are recomputably
    `not_required` and have no receipt. The gate has
    `truth_effect="workflow_readiness_only"`, remains outside the invariant Fact
    contract, and cannot alter its hash. Accepted retries and audit revalidate
    it. Paper evidence must remain current/non-superseded; campaign and novelty
    events must be no earlier than the governed round; procedural host evidence
    is never relabeled machine-verified.

## Storage

```text
PROJECT/
  project.json                 # container schema 2; workflow_evidence_version 3 or 4
  .mathgraph.lock              # cooperative single-writer filesystem lock
  TARGETS.txt
  fact_graph/
    facts/<fact_id>.md
    _revoked/<fact_id>.md
    verification_log.jsonl
    revocation_log.jsonl
    fact_metadata.jsonl
  submissions/<fact_id>.json
  verification_queue/
    by-hash/<packet_sha256>.md
    by-fact/<fact_id>.json
  review_inbox/                # untrusted designated verifier returns
  reviews/by-id/<review_id>.json
  memory/global.jsonl
  rounds/<round_id>/
    round.json
    assignments/<assignment_id>.md
    returns/<assignment_id>.json
    returns/<assignment_id>.receipt.json
    artifacts/<assignment_id>/
    work/<assignment_id>/experiments/<experiment_id>/
      events.jsonl              # canonical append-only experiment ledger
      events.index.sqlite3      # disposable/rebuildable lookup cache
  blackboard/
    pulses/by-hash/<pulse_id>/
      plan.json
      barrier.json
      closure.json | abort.json
      core-failures/<commitment_id>.json
      host-dispatch/*.json
      voids/*.json
  paper_logic/
    store.json
    artifacts/by-sha256/<artifact_sha256>.artifact
    cas/nodes/by-hash/<paper_node_id>.json
    cas/edges/by-hash/<paper_edge_id>.json
    revisions/by-id/<revision_id>.json
    reviews/by-id/<review_id>.json
    transactions/by-id/<transaction_id>.json
    snapshots/by-id/<snapshot_id>/{manifest.json,nodes.jsonl,edges.jsonl}
    bridges/by-id/<bridge_id>.json
    projections/by-id/<projection_id>.json
  claims/
  conventions/
  campaigns/
  fact_graph/bundles/            # candidate mini-DAGs + all-or-none acceptance markers
  migrations/
    <migration_receipt_id>.json
    append-anchors/<anchor_id>.json
  novelty/ledger.jsonl
  governance/unified-mode/
    current.json
    mode-events.jsonl
    profile-closures/by-round/<round_id>.json
  reports/
    target-closure-certificate.json
    expert-lint-receipts/<receipt>.json
    interpret-lint-receipts/<receipt>.json
  imports/
```

Atomic replace/write-once primitives and one project advisory lock protect normal cooperative
mutations. All mutating CLI commands use that lock; a process-local reentrant lock also serializes
threads sharing a project root. Multi-file operations are recoverable/auditable but are not a
database transaction: a process crash can leave partial state that `audit` reports and a retry may
repair. Checksums are not digital signatures against a local actor who can rewrite both data and
hashes.

Artifact, graph, event, and checkpoint caps are hard safety and integrity boundaries for
containment, deterministic replay, and recovery. They are not economic budgets, frontier cutoffs,
or inputs to subagent allocation.

The experiment SQLite file is not a second event store. JSONL is written and synced first; cache
metadata binds the log inode, size, timestamps, row ordinals, raw-line hashes, and byte ranges.
Tail recovery or an atomic full rebuild repairs cache lag. Removing the cache loses performance,
not evidence.

Schema-v1 through schema-v3 evidence stays readable and is reported as historical evidence or
warnings. It is not silently rewritten into stronger provenance. The project container itself
remains `project.json` schema version 2 and separately declares `workflow_evidence_version: 3` or
explicitly selected `4`; validators dispatch by the recorded workflow-evidence version.

Applicability-only and source-evidence-v2 external certificates likewise remain readable historical
trust. New source uses must carry the v3 trace, tier, and critical audit; correcting an old citation
creates a new submission rather than rewriting admitted evidence.

## Scope

The engine is key-free standard-library Python. The host supplies live subagents, clean-context
isolation, active-interval observation, and process control. The CLI is a cooperative evidence layer:
it cannot authenticate the user behind a notice or optional response, and it never pauses or sends
signals to a process. It can only reject later managed writes after an explicit recorded stop. It is
not a formal proof assistant, cannot authenticate reviewer identity, and
cannot make an LLM verifier infallible. Host OS isolation, primary-source checks, formal computation
where useful, and final expert human review remain necessary. The source-reliability gate is designed
to catch simple typos, internal inconsistencies, version drift, and known issue signals while avoiding
theorem-by-theorem repetition of paper-level searches; it does not prove the external theorem or
guarantee that no undiscovered counterexample exists.
