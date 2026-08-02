# Paper Research Pipeline: inherited draft research without graph compression

This reference governs prospective Paper-led research in Chalxius 0.6.3. It
turns the reusable mechanisms recovered from the 2026-08-01/02 field run into a
domain-general pre-admission pipeline for philosophy, mathematics, empirical
research, and mixed-domain drafts. Every record produced here is nontruth.
Native Paper review/freeze, a fresh independent verifier, Certification, and the
ordinary Fact Gateway remain mandatory.

## Intake authority

Classify the artifact before research:

- `research_draft`: freeze its exact bytes, decompose it into a proposition-
  total Paper DAG, inherit and repair that DAG copy-on-write, and treat its
  claims as candidates for later Fact admission. Preserve the draft's exact
  research target under the appropriate domain adapter.
- `external_finished_publication`: bind it as nontruth Evidence. Reputation,
  peer review, citation count, DOI identity, or complete PDF bytes never make it
  a Fact. A claim can become a premise only through an explicit bridge and the
  normal fresh admission path.

Do not replace a research draft with a small convenience FactBundle. Do not
start research from prose after a Paper Graph exists. The current Paper Graph,
its targets, ordered premises, bridges, defeaters, source components, and exact
source lineage are the research substrate.

The domain-general invariant is **research-target continuity**, not stance.
The `research_continuity_contract` dispatches by frozen `domain_profile`:

- philosophy preserves the declared argumentative direction and headline;
- mathematics preserves the exact conjecture/question, hypotheses, domains,
  quantifiers, and target claim ids, while permitting `proved`, `disproved`, or
  `unresolved_with_obstruction` as outcomes;
- empirical work preserves question, estimand, population,
  intervention/exposure, outcome, and scope while permitting support,
  disconfirmation, or an inconclusive result; and
- mixed work declares at least two component adapters and keeps their shared
  target ids explicit.

A counterexample to an unchanged mathematical conjecture is target-preserving,
not a stance reversal. Conversely, proving a weakened or re-quantified theorem
does not resolve the original target merely because it points in the same
direction. Only an exact Operator target-revision authorization may replace a
bound target. The current philosophy Paper uses the argumentative-stance
adapter, so its conditional restorative position remains preserved.

## Prospective activation and copy-on-write succession

The stronger path applies only when an activation record says:

```json
{
  "activation_policy": "prospective_only",
  "source_role": "research_draft",
  "authority_effect": "none",
  "truth_effect": "none"
}
```

`successor` never edits a predecessor graph. It preserves every local node id
and edge, materializes only native contract extensions, hashes every dropped
non-native top-level field into a separate receipt, and requires the result to
pass native Paper stage/review/freeze. A receipt is not a Paper freeze and
conveys no inherited Fact authority.

The strict successor adds two distinct semantic layers:

- proposition hierarchy: every source proposition has an explicit
  `component_level`, `partition_path`, and `child_component_ids`; atomic leaves
  cannot silently hide a partition;
- source occurrence accounting: exact unit-local token spans and dispositions
  live in `source_occurrence_ledger`. They are not inserted into
  `operator_ledger` merely because a surface word was scanned. The operator
  ledger remains the semantic transport of logical operators.

Inference `semantic_operation` separately labels argumentative inference,
normative or conceptual bridges, definition/classification repairs, and
relation materialization. A classification or topology repair cannot acquire
normative-bridge authority by relabelling.

## Ordered Paper frontier

`frontier` computes the complete upstream closure of the selected Paper
headline claims. It retains:

- every selected claim and inference;
- premise order through both position-bearing edges and a premise-order hash;
- bridge and defeater roles as distinct topology;
- Paper targets and source-unit anchors;
- one work unit per claim or inference, with no score cutoff.

`auto` may prioritize or rapidly research the work units. It may not delete,
merge, summarize away, or otherwise compress Paper topology. `frontier-verify`
recomputes the projection from the bound graph and rejects any drift.

## Evidence identity and claim-level support

`evidence` validates each retained source at two levels:

1. publication identity: exact bound bytes plus title, authors, year, and DOI
   where applicable; Crossref records are checked field by field rather than
   accepted because the DOI string exists;
2. claim support: an exact locator, retained witness, support kind, access
   class, mapped Paper objects or targets, and an independent support-review
   disposition.

Bibliographic context cannot satisfy substantive support. A claim witness must
occur in the byte-bound source material. PDF extraction uses
`corroborated-layout-dehyphen-v2`: only extraction-visible line-break
hyphenation is normalized, while ordinary inline compounds remain unchanged.
Use a Python environment containing `pypdf`; in Codex workspaces the bundled
workspace Python may provide it even when `/usr/bin/python3` does not.

## Atomic Paper preflight

`preflight` binds the exact Paper graph, verified ordered frontier, evidence
receipt, optional native-successor receipt, research-continuity contract, and atomic
Candidate DAG. It requires:

- `validation_subject.kind="paper"` and the same Paper identity/source role;
- one independently challengeable semantic component per atomic claim;
- exact predecessor edges and a valid topological order;
- target, predecessor, bridge, defeater, interface, and source closure;
- all target-required claims, the exact domain adapter, and no forbidden
  retired claims;
- `native_gateway_required=true` and
  `compatibility_fact_bundle_substitute=false`.

Passing this preflight establishes structural/evidential readiness only. It
does not certify philosophical equivalence or truth and does not replace native
Paper review, composable verification, Certification, or Gateway admission.

Evidence and successor receipts are exact-schema, content-addressed objects.
Preflight recomputes each receipt id, rejects unknown fields, and binds the
canonical hash of the complete receipt into its own id. A producer-supplied id
cannot hide nested content drift. This receipt rule is domain-neutral and
applies equally to philosophical sources, mathematical derivations, empirical
datasets/extractions, and mixed-study artifacts.

## Reliability matrix

`reliability-matrix` runs deterministic negative tests over the supplied real
pipeline. It mutates Paper topology, the ordered frontier, atomic DAG, research-
continuity contract, evidence receipt, and native-successor receipt independently. Every
mutation must fail with a declared pipeline error; an unexpected exception is
a harness error, never a credited kill. The receipt includes exact input
hashes, per-category counts, error signatures, and any survivor sample.

The matrix is a release reliability artifact, not Certification or truth. Its
implementation dispatches the explicit philosophy, mathematics, empirical, or
mixed continuity adapter and rejects cross-domain substitution.

## Delta and merge discipline

Use `stable_identity_merge` for shard results. Duplicate values are not a merge
key: one stable identity with different semantics fails closed. Heterogeneous
copy-on-write delta receipts first pass `delta-normalize`, which binds their
original canonical hash and emits one nontruth IR. A normalized delta cannot
authorize a node cut. Strict research-draft succession preserves the complete
node/edge set; any later cut needs an explicit successor mapping and full
inbound component/topology coverage.

## CLI

```bash
PIPELINE="$SKILL_ROOT/scripts/paper_research_pipeline.py"

python3 -B "$PIPELINE" frontier \
  --graph PAPER_GRAPH.json --headline HEADLINE_ID --output FRONTIER.json
python3 -B "$PIPELINE" frontier-verify \
  --graph PAPER_GRAPH.json --frontier FRONTIER.json
python3 -B "$PIPELINE" successor \
  --graph PAPER_GRAPH.json --activation ACTIVATION.json \
  --actor main --builder-context-id RUN_ID \
  --bundle-output SUCCESSOR.json --receipt-output SUCCESSOR_RECEIPT.json
python3 -B "$PIPELINE" evidence \
  --project-root PROJECT --registry EVIDENCE_REGISTRY.json \
  --frontier FRONTIER.json --output EVIDENCE_RECEIPT.json
python3 -B "$PIPELINE" preflight \
  --graph PAPER_GRAPH.json --frontier FRONTIER.json \
  --dag ATOMIC_DAG.json --continuity RESEARCH_CONTINUITY.json \
  --evidence-receipt EVIDENCE_RECEIPT.json \
  --successor-receipt SUCCESSOR_RECEIPT.json --output PREFLIGHT.json
python3 -B "$PIPELINE" delta-normalize \
  --input DELTA.json --output NORMALIZED_DELTA.json
python3 -B "$PIPELINE" reliability-matrix \
  --graph PAPER_GRAPH.json --frontier FRONTIER.json \
  --dag ATOMIC_DAG.json --continuity RESEARCH_CONTINUITY.json \
  --evidence-receipt EVIDENCE_RECEIPT.json \
  --successor-receipt SUCCESSOR_RECEIPT.json \
  --mutations 1200 --seed 6202 --output RELIABILITY.json
```

All output writes are atomic. Run native Paper stage/audit after successor
materialization, then the ordinary strict research-draft lifecycle. Never call
the preflight receipt an admitted Fact.

## L3/L4 boundary

This pipeline may supply ordered nontruth work units to the existing scheduler
and may coexist with explicitly enabled Brave Future BF-1 through BF-3. It does
not enable `plan_one`, `execute_one`, `plan-round --reassessment`, automatic
dispatch, Campaign closure, Research creation, or any Candidate/Certification/
Gateway/Fact write. The finite L3/L4 recovery remains advisory and separately
audited under [brave_future_l3_l4.md](brave_future_l3_l4.md).
