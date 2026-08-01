# Executable Paper input contracts

This reference is the public, exact-key companion to
`paper_logic_graph_v1.md` and `paper_continuation_contract.md`. Inputs reject
unknown fields. Empty strings are legal only where this reference says so.
Paper and continuation records remain nontruth.

## Known-good Logic fixture

`assets/paper_logic_minimal_logic_bundle.v1.example.json` and
`assets/paper_logic_minimal_source.txt` form a staging-tested pair. Replace only
`project_id` with the exact id from `PROJECT/project.json`; keep the source bytes
unchanged. The bundle then stages with:

```bash
mgraph --root PROJECT --role main paper-logic-init --actor main
mgraph --root PROJECT --role main paper-logic-stage \
  --input logic-bundle.json \
  --artifact SKILL_ROOT/assets/paper_logic_minimal_source.txt \
  --actor public-example-builder
```

The example is deliberately one line and one target. It proves interface
reachability, not paper adequacy.

After freezing it, copy
`assets/paper_logic_minimal_audit_bundle.v1.example.json`, replace its project,
Logic snapshot, and `c2` persistent node placeholders from the Logic review
packet/local-id map, then stage it against the same source. This Audit fixture
is likewise interface-only and makes no substantive correctness claim.

## Logic or Audit bundle

Every staging bundle has exactly these fields:

```json
{
  "schema_version": 1,
  "feature_revision": "paper-logic-1",
  "project_id": "PROJECT_ID",
  "paper_id": "SOURCE_SPECIFIC_ID",
  "graph_kind": "logic",
  "domain_profile": "philosophy",
  "builder": "ACTOR",
  "builder_context_id": "FRESH_CONTEXT_ID",
  "source": {},
  "base_snapshot_id": "",
  "supersedes_snapshot_id": "",
  "coverage": {},
  "nodes": [],
  "edges": []
}
```

`graph_kind` is `logic` or `audit`; `domain_profile` is `philosophy`,
`mathematics`, or `mixed`. Logic uses an empty `base_snapshot_id`. Audit uses
the exact current Logic `pls-*` id. `supersedes_snapshot_id` is empty unless
this is a copy-on-write replacement of the same paper and graph kind.

`source` has exactly:

```json
{
  "artifact_sha256": "64hex",
  "artifact_locator": "human-readable locator",
  "title": "title",
  "version": "exact paper version",
  "mime_type": "application/pdf",
  "retrieved_at": "timestamp",
  "inspection_methods": ["rendered_primary"]
}
```

Inspection methods must include `rendered_primary` or `source_tex`.

`coverage` has exactly:

```json
{
  "scope_kind": "full_artifact",
  "included_locators": ["page:1"],
  "excluded_locators": [{"locator": "appendix:A", "reason": "bounded scope"}],
  "units": [{
    "unit_id": "s1",
    "classification": "argumentative",
    "mapped_node_ids": ["s1", "c1"],
    "reason": ""
  }],
  "unresolved_load_bearing_units": [],
  "completeness_claim": "Exact bounded claim."
}
```

Logic `scope_kind` is `bounded` or `full_artifact`; Audit uses `audit_subset`.
Logic classifications are `argumentative`, `context`, `quotation`,
`bibliography`, `figure`, or `excluded`. Audit classifications are
`audit_target`, `audit_evidence`, or `excluded`. Logic requires exactly one
coverage unit for every local `source_unit`, with the same `unit_id`.

## Local node schemas

Every node envelope is exactly:

```json
{"local_id": "c1", "object_type": "claim", "payload": {}}
```

Local ids match `[A-Za-z][A-Za-z0-9_.:-]{0,127}`; `__source__` is reserved.
Payload fields are exact by `object_type`:

- `source_unit`: `unit_kind`, `order`, `locator`, `text`, `text_sha256`,
  `speaker`, `inspection_methods`, `render_sha256`, `context_before`,
  `context_after`, `operator_ledger`.
- `claim`: `representation_kind`, `attribution`, `discourse_role`,
  `content_type`, `statement`, `statement_sha256`, `source_unit_ids`,
  `semantic_diff`, `modality`, `scope_notes`, `operator_ledger`,
  `definition_ids`, `parent_claim_id`.
- `definition`: `representation_kind`, `attribution`, `definition_kind`,
  `term`, `definiens`, `source_unit_ids`, `semantic_diff`, `scope_notes`,
  `operator_ledger`.
- `formula`: `representation_kind`, `attribution`, `expression`,
  `expression_sha256`, `source_unit_ids`, `semantic_diff`, `scope_notes`,
  `glyph_ledger`.
- `inference`: `premise_ids`, `conclusion_id`, `inference_kind`, `strength`,
  `authorial_status`, `source_unit_ids`, `bridge_claim_ids`,
  `defeater_claim_ids`, `rationale`.
- `paper_target`: `target_role`, `claim_id`, `rationale`.
- `audit_finding`: `finding_kind`, `severity`, `status`, `target_id`, `claim`,
  `rationale`, `evidence_unit_ids`, `observed_excerpt`, `compared_text`,
  `load_bearing_tokens`.
- `counterexample`: `target_id`, `construction`, `premise_witnesses`,
  `conclusion_failure`, `interpretation_preserved`, `interpretation_notes`,
  `nontriviality`, `evidence`, `provisional_logical_effect`.
- `repair_proposal`: `target_id`, `addresses_ids`, `repair_kind`, `changes`,
  `core_preservation`, `ad_hoc_risk`, `new_statement`, `justification`.
- `impact_assessment`: `challenge_id`, `repair_id`, `domain_profile`,
  `logical_effect`, `dialectical_effect`, `core_target_id`,
  `core_preservation`, `repair_cost`, `evidence_strength`, `justification`.
- `audit_challenge`: `target_audit_id`, `claim`, `evidence`, `status`,
  `rationale`.
- `audit_disposition`: `target_audit_id`, `challenge_ids`, `disposition`,
  `replacement_ids`, `rationale`.

The working fixture shows complete `source_unit`, `claim`, `inference`, and
`paper_target` payloads. Important nested exact shapes are:

```json
{
  "locator": {
    "kind": "pdf",
    "pdf_page_index": 0,
    "printed_page_label": "1",
    "region": "paragraph:2"
  },
  "operator_ledger_entry": {
    "operator_id": "op-1",
    "token": "not",
    "occurrence": 0,
    "kind": "negation",
    "scope": "exact scope",
    "disposition": "logical",
    "depends_on": []
  },
  "glyph_ledger_entry": {
    "token": "<=",
    "role": "comparator",
    "finding": "Checked against rendered source."
  },
  "premise_witness": {
    "premise_id": "prn-64hex",
    "status": "satisfied",
    "witness": "reproducible witness"
  },
  "conclusion_failure": {
    "status": "fails",
    "witness": "reproducible witness"
  },
  "repair_change": {
    "field": "statement",
    "before": "old",
    "after": "new",
    "rationale": "why"
  }
}
```

Representation kinds are `source_literal`, `source_paraphrase`,
`researcher_reconstruction`, `local_emendation`, and `official_erratum`.
Attributions are `author`, `cited_author`, `interlocutor`, `objection`,
`editor`, and `researcher`. Inference strength is `strict` or `defeasible`;
target role is `headline` or `supporting`. The runtime reports any invalid enum
by its field name. Hash fields are SHA-256 of exact UTF-8 text bytes.

## Edges are derived, not guessed

Every input edge has exactly `relation_type`, `source`, `target`, and `payload`.
Generate them mechanically from nodes:

- every source unit: `contains`, `__source__ -> source_unit`,
  `{"order": ORDER}`;
- every claim/definition/formula/inference source unit: `anchors`,
  `NODE -> source_unit`, `{}`;
- claim definition: `uses_definition`, `claim -> definition`, `{}`;
- claim parent: `variant_of`, `claim -> parent`,
  `{"semantic_diff": TEXT}`;
- ordered premise: `premise_of`, `claim -> inference`,
  `{"position": ZERO_BASED_INDEX}`;
- inference conclusion: `concludes`, `inference -> claim`, `{}`;
- defeater: `defeats`, `claim -> inference`, `{}`;
- target: `targets`, `paper_target -> claim`, `{"role": ROLE}`;
- audit finding: `audits`, `finding -> base target`,
  `{"finding_kind": KIND}`, plus `evidence_for`,
  `base source_unit -> finding`, `{}`;
- counterexample: `counterexample_targets`, `counterexample -> base target`, `{}`;
- repair: `repairs`, `repair -> target`, `{"repair_kind": KIND}`, plus
  `responds_to`, `repair -> addressed challenge`, `{}`;
- impact: `assesses`, `impact -> challenge`, `{}`, and a second identical
  relation to nonempty `repair_id`;
- audit challenge: `challenges_audit`, `challenge -> base audit node`, `{}`;
- disposition: `disposes`, `disposition -> base audit node`,
  `{"disposition": VALUE}`; `responds_to` each challenge; and
  `supersedes_audit`, `replacement -> target`, for each replacement.

On mismatch, the CLI reports bounded `missing=` and `extra=` edge objects.

## Review input and freeze

Staging returns `revision_id`, `bundle_sha256`, `review_packet_path`, and the two
required profiles. The review packet is a public project artifact containing
`node_entries`, `edge_entries`, and `local_id_map`. Each independent review has
exactly:

```json
{
  "schema_version": 1,
  "feature_revision": "paper-logic-1",
  "project_id": "PROJECT_ID",
  "revision_id": "plr-64hex",
  "bundle_sha256": "64hex",
  "profile": "source_fidelity",
  "verdict": "correct",
  "reviewer": "INDEPENDENT_REVIEWER",
  "reviewer_context_id": "DISTINCT_FRESH_CONTEXT",
  "fresh_context_contract": "fresh-context-v1",
  "object_checks": [{
    "object_id": "psn-prn-pan-pse-pre-or-pae-64hex",
    "status": "pass",
    "finding": "Exact check finding."
  }],
  "global_checks": [{
    "kind": "artifact_hash",
    "status": "pass",
    "finding": "Exact global finding."
  }],
  "critical_errors": [],
  "gaps": [],
  "truth_effect": "none"
}
```

Verdicts are `correct`, `reject`, or `blocked`; object/global statuses are
`pass`, `issue`, or `not_applicable`. Only `formula_glyphs` may be
`not_applicable`. A correct review has no issue, critical error, or gap.

Object coverage is exact and derived from the public review packet:

- `source_fidelity`: every `paper_source` node; every claim, definition,
  formula, or inference with nonempty `source_unit_ids`; and every `contains`
  or `anchors` edge;
- `graph_structure`: every `paper_reconstruction` node and edge;
- `target_binding`: every node and edge in the Audit revision;
- `audit_reasoning`: every node in the Audit revision.

Global kinds are exact:

- `source_fidelity`: `artifact_hash`, `span_alignment`, `transcription`,
  `attribution`, `operator_ledger`, `formula_glyphs`;
- `graph_structure`: `endpoint_direction`, `premise_completeness`,
  `inference_kind`, `origin_separation`, `headline_reachability`, `coverage`;
- `target_binding`: `exact_target`, `evidence_anchor`, `graph_version`,
  `representation_identity`;
- `audit_reasoning`: `objection_strength`, `counterexample_validity`,
  `repair_vs_refutation`, `domain_profile_boundary`,
  `evidence_proportionality`.

The builder cannot review; the two profiles need different reviewers and
different fresh context ids. After both correct reviews:

```bash
mgraph --root PROJECT --role main paper-logic-freeze plr-64hex --actor main
```

For an Audit bundle, use the frozen Logic id as `base_snapshot_id`, use exact
base `psn-*`/`prn-*` ids inside Audit payloads and edges, obtain the
`target_binding` and `audit_reasoning` reviews, then freeze the Audit revision.

## Continuation disposition

`paper-continuation-dispose` accepts exactly:

```json
{
  "target_node_id": "prn-64hex",
  "result_research_id": "12hex",
  "outcome": "retained",
  "rationale": "bounded rationale",
  "successor_research_ids": [],
  "dialectical_analysis": {
    "issue": "plain issue",
    "importance": "why it matters",
    "burden_holder": "who must establish what",
    "plain_language_summary": "ordinary-language account",
    "technical_term_ledger": [{
      "term": "term",
      "plain_definition": "ordinary-language definition",
      "necessity": "why the term cannot be removed without loss"
    }],
    "strongest_charitable_objection": "strongest fair objection",
    "response_or_revision": "answer or exact revision",
    "independent_failure_surfaces": [{
      "surface_id": "fs-1",
      "statement": "what can fail",
      "why_independent": "why another claim may survive",
      "resolution": "current resolution"
    }]
  },
  "writing_coverage": {
    "status": "covered",
    "artifact_path": "output/revised.md",
    "artifact_sha256": "64hex",
    "section_ids": ["section-1"],
    "rationale": "where the target is visible"
  },
  "supersedes_disposition_id": ""
}
```

Outcomes are `retained`, `rejected`, `replaced`, or `out_of_scope`.
`replaced` alone requires nonempty successors. Only `out_of_scope` may use
`writing_coverage.status=not_applicable`, with null path/hash and empty sections.
A correction names the exact current `pcd-*` id.

## Candidate Release Paper overlay

The V5 Candidate Release requires these top-level fields and no others except
the listed optional overlays:

```json
{
  "schema_version": 5,
  "bundle_claim": "bounded claim",
  "candidates": [],
  "research_entry_ids": ["12hex"],
  "claim_relation": "proves",
  "artifacts": [{"path": "paper.pdf", "sha256": "64hex", "role": "paper_source"}],
  "verification_plan": {
    "mode": "closed_capsule",
    "authorized_artifact_roles": ["paper_source", "paper_revised_writing"],
    "required_checks": []
  },
  "requested_assurance": {},
  "challenge_dispositions": [],
  "paper_evidence_refs": [],
  "adverse_actor_ids": [],
  "paper_continuation_ref": {},
  "philosophy_atomicity": {}
}
```

Every artifact path is project-relative, contained, nonsymlinked, and must match
its hash. Copy the exact Paper source into the project before release. Include
and authorize every artifact named by the bound managed Research result, the
source as `paper_source`, and each covered revision as
`paper_revised_writing`; the closed verifier receives only authorized roles.

Optional generic overlays are `successor_contracts` and
`evidence_bridge_refs`. A continuation-descended release requires both Paper
overlays shown above. Each candidate Fact may use the exact fields returned by
ordinary `submit`; at minimum provide `problem_id`, `author`, `predecessors`,
`statement`, and `proof`. Omitting `fact_id` asks the runtime to compute it, but
the same computed id must be used by coverage and atomicity references.

The public content-id rule is the first 16 lowercase hex characters of SHA-256
over UTF-8 JSON with sorted keys for exactly `problem_id`, sorted
`predecessors`, sorted `glossary_introduces`, and whitespace-normalized
`statement` and `proof`; JSON uses `ensure_ascii=false` and the standard Python
separators. An ordinary nontruth `submit` also returns this id before any Fact
admission. Candidate Fact statements use the normal `[CLAIM:ID]` clause syntax.

Invariant required checks are `mathematical`, `typing`, `scope`,
`source_and_applicability`, `predecessor_interfaces`, `computation_replay`,
`challenge_dispositions`, and `assurance_scope`. Paper adds
`paper_source_fidelity`, `paper_graph_structure`, `paper_audit`, and
`paper_target_coverage`. Continuation adds `paper_continuation_adequacy`;
philosophy/mixed adds `philosophy_semantic_atomicity` and
`philosophy_plain_language_clarity`. Current-assurance worker Research also
adds the checks named by its task card, at least `research_obligation_evidence`.

`requested_assurance` is exactly:

```json
{
  "validation_subject": {
    "kind": "paper",
    "subject_id": "PAPER_ID",
    "artifact_sha256": "64hex",
    "load_bearing_node_ids": ["psn-or-prn-id"]
  },
  "validation_granularity": "paper_target_closure",
  "coverage": [{
    "paper_node_id": "psn-or-prn-id",
    "disposition": "fact_bundle_member",
    "fact_id": "16hex",
    "reason": ""
  }]
}
```

Coverage must exactly equal the plan's load-bearing set. Dispositions are
`fact_bundle_member`, `source_only`, `audit_only`, or `excluded`; non-Fact
entries use `fact_id: null` and a nonempty reason. Every Candidate Fact must be
mapped by at least one `fact_bundle_member` entry.

Each Paper EvidenceRef is exactly:

```json
{
  "paper_id": "PAPER_ID",
  "snapshot_id": "pls-64hex",
  "snapshot_sha256": "SHA256_OF_SNAPSHOT_MANIFEST_BYTES",
  "graph_kind": "logic",
  "target_artifact_sha256": "64hex",
  "target_node_ids": ["psn-or-prn-id"]
}
```

One current Logic and one current Audit ref are mandatory. The Logic ref for a
continuation release exactly covers its selected source and reconstruction ids.

`paper_continuation_ref` is exactly:

```json
{
  "contract_revision": "chalxius-v5-paper-continuation-1",
  "plan_id": "pcp-64hex",
  "plan_record_sha256": "64hex",
  "adequacy_receipt_sha256": "64hex",
  "disposition_ids": ["pcd-64hex"]
}
```

All values come from `paper-continuation-status PLAN_ID`; do not recompute or
guess them.

## Philosophy atomicity and clarity

`philosophy_atomicity` is exactly:

```json
{
  "contract_revision": "chalxius-v5-philosophy-semantic-atomicity-1",
  "plan_id": "pcp-64hex",
  "fact_units": [{
    "fact_id": "16hex",
    "primary_conclusion": "EXACT CANDIDATE FACT STATEMENT",
    "plain_language_paraphrase": "ordinary-language equivalent",
    "source_target_node_ids": ["prn-target-id"],
    "conjunct_ids": ["conj-1"],
    "defeasible_condition_ids": [],
    "decomposition_rationale": "why this is one independently falsifiable claim"
  }],
  "conjunct_inventory": [{
    "conjunct_id": "conj-1",
    "statement": "EXACT CANDIDATE FACT STATEMENT",
    "represented_by_fact_id": "16hex",
    "failure_surface_ids": ["fs-1"],
    "independence_rationale": "how failure is localized"
  }],
  "clarity_review": {
    "plain_language_abstract": "ordinary-language whole-release account",
    "technical_term_ledger": []
  }
}
```

There is exactly one Fact unit and one distinct conjunct entry per Candidate
Fact. The release term ledger must exactly equal the union of target-level term
ledgers. The independent verifier must still find omitted terms, hidden
conjuncts, lost modality, scope, quantifiers, burdens, exceptions, and
conclusions; JSON shape is only preflight.

`paper_continuation_evidence` is computed by the runtime and must not be placed in the input.
The sealed release and verifier capsule embed it after validating
the current plan, dispositions, Research records, selected Paper objects, and
authorized `paper_source` and `paper_revised_writing` bytes.
