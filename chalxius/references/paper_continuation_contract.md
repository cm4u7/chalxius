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

Research depth does not force full-history validation. A changed-surface plan
binds the exact changed Paper nodes and their necessity-derived predecessor,
defeater, source, downstream-target, and writing closure. Unchanged sealed
dependencies may reuse current receipts; missing, stale, drifted, ambiguous,
schema-changed, or forensic state falls back to full validation. New or
invalidated Candidate Facts still receive fresh verification.

## Strict research-draft successor path

The legacy continuation commands remain readable and usable for their original
prospective contract. A new `research_draft` that is intended to become the
substrate for further research uses the stricter successor path instead:

```bash
mgraph --root PROJECT --role main research-draft-plan LOGIC_SNAPSHOT_ID \
  --input research-draft-plan.json --actor main
mgraph --root PROJECT --role main research-draft-disposition-batch PLAN_ID \
  --input research-draft-batch.json --actor main
mgraph --root PROJECT --role main research-draft-status PLAN_ID --deep
```

Current plan revision 2 always has `objective`, `source_artifact_sha256`, and
`term_registry`, plus exactly one policy selected from the frozen domain:
`stance_policy` for philosophy, `mathematical_target_policy` for mathematics,
or `domain_target_policy` for empirical/mixed work. Historical revision-1
plans retain their original `stance_policy` bytes and remain readable.

Philosophy `stance_policy` has exactly `policy`, `headline_target_ids`,
`declared_stance`, and
`major_revision_requires_operator_authorization=true`. The default policy for
strengthening an existing argument is `steelman_headline`; narrowing, reversing,
or withdrawing a headline requires an immutable Operator authorization record.
Create it with `research-draft-authorize-major-revision`; the batch carries only
its exact `decision_id` and `decision_record_sha256`. The stored decision binds
the project, plan id/hash, headline target, declared-stance hash, exact impact,
actor, role, and reason. A producer-supplied actor, key, or authorization story
cannot substitute for that record.

Mathematics has no stance field. `mathematical_target_policy` hash-binds the
exact target statement, canonical target and hypothesis claim ids, at least one
exact domain binding, every quantifier/scope binding, the exact root outcomes
`proved`, `disproved`, and `unresolved_with_obstruction`, and the rule that
target substitution requires Operator authorization. Canonical target claim
ids are resolved through the frozen graph's `targets` edges, not through
source-local payload aliases. This prevents local/global identifier drift from
making the normal production path unusable.
`term_registry` is sense-aware: each entry binds `term`, `sense_id`,
`exact_definition`, and `necessity`, and one sense id cannot carry conflicting
definitions across targets.

The plan freezes every Paper target, its complete source/reconstruction/edge
closure, exact snapshot bytes, domain closure profile, declared stance, and
source artifact. It has `auto_topology_effect=none`: `auto` may schedule broad
research cheaply but cannot omit or merge Paper nodes.

One disposition batch covers the exact complete target set and supersedes the
exact current batch. Every entry separately records its Paper-node disposition,
Research ids, its applicable domain outcome, successor mappings, term senses,
complete profile-specific obligation dispositions, target-qualified failure
surfaces, and revised-writing bytes/sections. A philosophy entry records stance
impact and any exact major-revision authorization. A mathematics entry instead
records the exact-root/typed-refinement DAG; a verified weaker theorem, special
case, added hypothesis, weakened conclusion, counterexample, or obstruction
must expose its exact deltas and remaining gap and cannot close or directly
reconstruct an open root. Empirical and mixed entries retain their own outcome
adapters. Node disposition is not a one-to-one Fact
mapping: one Paper node may split into several Candidate components and one
Candidate may be supported through several Paper predecessors. Publication is
all-or-none under one V5 mutation lock and one atomic batch-directory rename;
no per-target partial state is visible.

The domain profile is versioned and target-total. Philosophy covers claims,
normative bridges, objections, defeaters, authority routes, scope, and failure
surfaces. Mathematics covers definitions, hypotheses, lemmas, proof
obligations, cases, transports, counterexamples, and conclusion. Empirical work
covers hypotheses, design, method, measurement, data lineage, uncertainty,
causal identification, transport, and limitations. `mixed` is their union.

A Candidate descended from this path must use the prospective research-draft
assurance, a Paper validation subject, the exact current plan and batch, and
the required checks `research_draft_admission_preflight`,
`composable_parallel_verification`, and `validated_dependency_receipt`. The
native preflight recomputes Paper closure, source-derived atomic components,
many-to-many Paper/Fact mappings, semantic interfaces and edge transports,
the applicable philosophy stance, mathematical exact-target/refinement, or
empirical/mixed target adapter, revised-writing authorization, release-relative Paper
transport closure, active/revoked Fact authority, and verifier shard coverage.
It seals a content-addressed dependency receipt; unchanged reads use the
validated fingerprint cache, while any changed dependency is revalidated.

For this strict path, each Candidate Fact exports exactly one schema-6 semantic
component. Its component id, source-component ids, and failure-mode ids must
equal the atomicity/failure-surface records, and every source operator and
qualifier must survive in that interface. More than one independently
challengeable source proposition must be represented as an explicit Candidate
mini-DAG. These are structural gates; they do not claim that a machine has
discovered every philosophically possible decomposition.

Passing this preflight is structural nontruth evidence, not certification.
Fresh independent reviewer receipts must aggregate monotonically; a missing or
conflicting shard rejects. The Operator first registers project-bound planner,
Host, and reviewer prime-order Ed25519 keys. The project registry is revalidated
from immutable records on every use and forbids one public key from appearing
under multiple role, principal, Host, or trust-domain identities. Every registration
branch validates the complete registry before a new write or an idempotent return. Public key, signed-plan, packet, receipt, and aggregate reads also revalidate the complete registry; immutable-record caches may save byte I/O but never cache authority. A signed exact release/capsule-derived plan
precedes dispatch; Host packets and reviewer receipts are blind-to-peer and use
durable project-wide nonrepeating nonces. `verification-aggregate` performs no
semantic inference. Public verification status, the subsystem audit, and the
top-level V5 audit all revalidate the registry-wide invariant. The Certification Decision and Fact Gateway both revalidate
the same eligible aggregate before admitting the complete Candidate DAG. Only that admitted Fact Graph,
not the original draft, batch, prose, or preflight receipt, becomes the
authoritative base for inherited further Research.

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

Every materialized Paper target also freezes
`independent_adverse_required=true`. `workers` still counts only the selected
primary targets. Planning adds one independent `refute` worker/context for each
applicable primary, except when that primary is already refutation-mode or the
target Research is itself a challenge. The adverse card retains the complete
same Paper target closure and source capabilities. Philosophy controls only
its additional attack vocabulary and stance continuity; mathematics uses the
same allocation predicate while preserving its exact target, hypotheses,
domain, and quantifiers and may prove, disprove, or return an obstruction.

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

`paper-continuation-status` is a bounded monitoring interface by default. It
returns identity, state, snapshot currentness, adequacy, target counts, the
exact adequacy receipt, and an explicit `detail.request`; it does not serialize
the inherited node, edge, binding, unresolved-id, or disposition arrays. Use
`paper-continuation-status PLAN_ID --full`, or the no-plan form with `--full`,
only for an intentional forensic export. The compact view validates an atomic
content-addressed status HEAD and its immutable receipt; it does not call the
full status path or rescan plans, Research, dispositions, writing artifacts, or
Paper snapshots. Plan creation and materialization, managed Research writes,
disposition and writing publication, and Paper snapshot writes synchronously
advance the indexed state. Out-of-band directory generation drift fails closed
instead of silently falling back to the expensive path.

An inherited project without a current index, or a project whose protected
continuation directories changed out of band, must pay the full validation cost
explicitly once:

```bash
mgraph --root PROJECT --role main paper-continuation-status-index-rebuild \
  --actor main
```

The rebuild commits a new HEAD only when every indexed count, adequacy result,
and receipt exactly equals the full forensic status. Compact and full views
therefore carry the identical adequacy receipt without making routine
monitoring reconstruct the closure. Neither view nor the index changes
Research, Candidate, Certification, Gateway, or Fact authority.

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
- one runtime-computed, content-addressed
  `paper_continuation_release_capsule` containing verifier-visible evidence:
  the selected node and edge objects, exact target task scopes, managed
  Research results, dispositions, and revised-writing bindings rather than
  only their ids;
- the exact Paper source as an authorized `paper_source` artifact and every
  covered revision as an authorized `paper_revised_writing` artifact;
- the `paper_continuation_adequacy` certification check.

The theorem-mode, empty-coverage, and empty-Paper-ref escape paths are rejected.
Historical sealed releases validate their exact old disposition ids without
claiming those ids are still current. Verifier-capsule creation, certification,
and admission recheck current state and reject a superseded disposition.

### Scoped continuation release capsule

For a newly sealed continuation-descended release, Candidate Release computes
exactly one `chalxius-v5-paper-continuation-release-capsule-1`. The producer
cannot supply this object in its input. The runtime persists it by its `pcrc-*`
content id below
`paper-continuations/release-capsules/by-id/` and embeds the same exact object
in the Candidate Release and neutral verifier capsule. It replaces the former
duplicate top-level `paper_continuation_evidence`; carrying both forms is
rejected. Historical releases that already contain only the former evidence
shape remain byte-exact readable through the compatibility validator.

The capsule binds, without becoming a second continuation-state owner:

- the exact continuation plan and `paper_continuation_ref`;
- one bounded status proof over the current status-index generation, HEAD,
  immutable plan state, status receipt, and adequacy receipt;
- the current Logic snapshot id plus manifest and file hashes, one exact Audit
  EvidenceRef binding, and the normalized complete Paper EvidenceRef set;
- the exact source-artifact path/hash, selected targets, work-unit hashes,
  reconstruction/source/edge closure, and any changed-surface receipt;
- the complete Candidate statement interfaces and their aggregate hash; and
- one evidence hash covering the exact Paper objects, managed Research,
  current dispositions, and immutable revised-writing bindings exposed to the
  verifier.

Candidate validates that bounded proof and materializes the evidence once.
Release reread, neutral verifier preparation, Certification, and Gateway reuse
the sealed capsule; they do not reconstruct the same Paper evidence a second
time. Current Paper EvidenceRefs and the ordinary V5 fresh-verifier and Gateway
checks remain independent gates. The capsule and every timing/fallback receipt
have `truth_effect=none` and cannot relax Fact admission.

### Observable full-validation fallback

If the indexed witness is missing, stale, ambiguous, corrupt, or hash/CAS
mismatched, release preparation does not silently trust it and does not fail
with an opaque cache error. It records one content-addressed request under
`paper-continuations/release-capsules/fallbacks/by-id/pcrf-*/`, runs the full
continuation validation once, and writes one immutable completion receipt. The
request binds the exact raw status-generation surface, plan/ref, normalized
Paper EvidenceRefs, and Candidate interfaces. The completion binds the full
status projection and hash, adequacy/currentness result, exception count,
full-validation timing, and the explicit recovery command
`paper-continuation-status-index-rebuild --actor main`.

An unchanged retry reuses that completion. Any generation-surface change makes
it stale and requires a new bounded request, so a prior fallback is never a
cross-generation authority cache. Candidate also records one idempotent
operation receipt with indexed-witness, full-validation,
evidence-materialization, persistence, and total phase timings. These timings
are operational diagnostics only; they do not impose a research-time limit or
convert the fallback into Fact evidence. A rebuilt index restores the normal
bounded path without rewriting the sealed capsule or historical release.

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
