# Paper continuation, philosophical atomicity, and clarity

This is a prospective V5 contract. It repairs the Paper-to-Research continuity,
semantic compression, and false-completion failures recorded as
`run-20260730T145847217907Z-eedfc9368ea0/CHX-001` through `CHX-003`.
It never rewrites or downgrades an existing Paper snapshot, Research entry,
Candidate Release, Certification Decision, admission, or Fact.
Copyable exact-key disposition, release-overlay, EvidenceRef, and philosophy
atomicity inputs are in [paper_input_contracts.md](paper_input_contracts.md).
The exact managed worker-return projection, including per-obligation
dispositions, is in
[v5_worker_return_contract.md](v5_worker_return_contract.md).

## Boundary

Paper Logic and Audit remain immutable nontruth source planes. Paper adequacy is
not Fact truth, and a clean Fact audit is not a claim that a paper is complete.
The new contract adds three linked but separate gates:

1. continuation: every selected `paper_target` becomes one low-cost Research
   frontier item carrying its exact upstream reconstruction and source closure;
2. adequacy: Main records a current terminal disposition and revised-writing
   mapping for every selected target;
3. release: a release descended from this frontier must use the exact Paper
   source and closure, then pass fresh Fact verification as usual.

`auto` orders and deepens these Research items but does not drop low-scoring
targets. A target remains unresolved until a managed worker result and Main
disposition exist.

## Start an explicit continuation

The input file has exactly four fields:

```json
{
  "selection_mode": "all_targets",
  "target_node_ids": [],
  "objective": "Continue every selected argument and objection into revised work.",
  "source_artifact_sha256": "64 lowercase hex or empty only when the snapshot has one source"
}
```

Use `explicit_targets` with one or more exact `paper_target` node ids for a
deliberately bounded subproblem. It does not assert whole-paper adequacy.

```bash
mgraph --root PROJECT --role main paper-continuation-plan LOGIC_SNAPSHOT_ID \
  --input continuation-plan.json --actor main
mgraph --root PROJECT --role main paper-continuation-status PLAN_ID
```

Creation is content-addressed and materializes the complete selected target
frontier without a score cutoff. Each Research item freezes:

- the exact Logic snapshot and source artifact hashes;
- target, target claim, inference, premise, defeater, definition, variant,
  source-anchor, source-artifact, and edge ids in that target closure;
- obligations for dialectical salience, burden, charitable objection, response,
  independent failure surfaces, clear ordinary-language explanation, technical
  term definitions, terminal disposition, and revised-writing coverage.

The worker return remains Research only. It cannot decide adequacy, activate a
route rule, certify a Fact, or modify the Paper graph.

## Record a target disposition

`paper-continuation-dispose PLAN_ID --input disposition.json --actor main`
accepts exactly one managed worker result descended from that target. Outcomes
are `retained`, `rejected`, `replaced`, or `out_of_scope`. `replaced` requires
successor Research; only `out_of_scope` may use `writing_coverage.status` equal
to `not_applicable`.

Every philosophy or mixed-domain disposition must state:

- the issue, why it matters, and who bears the burden;
- a plain-language summary;
- each necessary technical term, its plain definition, and why it cannot be
  replaced without loss;
- the strongest charitable objection and the response or revision;
- one or more independently challengeable failure surfaces;
- the exact revised-writing file hash and section ids.

The writing file is copied into a content-addressed immutable store. A later
correction appends a new disposition naming the exact current disposition in
`supersedes_disposition_id`; the old record remains readable. Concurrent stale
updates fail and must be retried against the new head.

## Adequacy status

Status reports, separately from the ordinary V5 audit:

- total and frontier-materialized targets;
- targets with managed Research results;
- current dispositions and unresolved targets;
- successor-mapped targets;
- revised-manuscript-covered targets;
- `adequacy_complete`.

Zero plans produce `declaration_state=not_declared`, not a completion claim.
An explicit plan is complete only while its source snapshot remains current and
every selected target has a current disposition and writing mapping.

## Candidate Release binding

Research ancestry is followed transitively. Binding only a worker result cannot
erase the Paper plan from which it descended, and Research from different plans
cannot be mixed in one release.

A bound release must include:

- `requested_assurance.validation_granularity=paper_target_closure`;
- the exact selected reconstruction and source node ids as load-bearing nodes;
- exact coverage of every node and at least one `fact_bundle_member` mapping for
  every Candidate Fact;
- one Logic EvidenceRef covering the exact selected closure plus a current Audit
  EvidenceRef;
- a current `paper_continuation_ref` binding the plan, adequacy receipt, and
  current disposition ids;
- verifier-visible `paper_continuation_evidence` containing the selected node
  and edge objects, exact target task scopes, managed Research results,
  dispositions, and revised-writing bindings rather than only their ids;
- the exact Paper source as an authorized `paper_source` artifact and every
  covered revision as an authorized `paper_revised_writing` artifact;
- the `paper_continuation_adequacy` certification check.

The theorem-mode, empty-coverage, and empty-Paper-ref escape paths are rejected.
Historical sealed releases validate their exact old disposition ids without
claiming those ids are still current. Verifier-capsule creation, certification,
and admission recheck current state and reject a superseded disposition.

## Philosophy semantic atomicity

Philosophy and mixed-domain releases also require
`philosophy_semantic_atomicity`. Every Candidate Fact declares exactly one
primary conclusion, exactly one independently falsifiable conjunct, its source
targets, defeasible conditions, decomposition rationale, and failure surfaces.
The conjunct statement must equal the exact Fact statement. Multiple declared
conjuncts must be split into a Candidate Fact mini-DAG with edge-level checks.

This structural preflight cannot prove that a producer disclosed every hidden
conjunct. The fresh verifier must independently reconstruct the claim's clauses
and reject any omitted independently falsifiable component. Passing JSON shape
alone is never philosophical validation.

## Plain-language clarity gate

Philosophy and mixed-domain releases additionally require
`philosophy_plain_language_clarity`.

- Every Fact carries an ordinary-language paraphrase with no protocol anchors.
- The release carries a plain-language abstract.
- Its technical-term ledger must exactly preserve the target-level reviewed
  ledger and may not introduce unreviewed jargon.
- The fresh verifier compares each paraphrase with the formal statement and
  rejects loss of quantifier, scope, modality, burden, exception, or conclusion.
- Undefined or unnecessary terminology, and terminology that substitutes for a
  premise or inferential step, is a rejection condition.

The independent verifier receives both the ordinary-language and technical
forms plus the actual source and revised-writing bytes. It must identify terms
the producer omitted from the ledger; an empty ledger is therefore a claim to
be challenged, not evidence that the prose is clear.

This is not a lexical ban list. A precise term is allowed when it is defined in
plain language and genuinely needed. Clear wording is the default; terminology
must earn its place.

## Historical and authority policy

The contract is activated only by a new explicit continuation plan. It does not backfill old tasks
or tell users that earlier work violates a newer standard.
Existing admitted Facts retain their recorded authority until ordinary
copy-on-write correction and fresh admission replace them. Paper plans,
dispositions, adequacy receipts, and clarity records have `truth_effect=none`;
only the unchanged V5 fresh-verifier and Fact-Gateway path can admit a Fact.
