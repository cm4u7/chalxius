# V5 worker return: exact public contract

This is the public contract for a current assurance-bound V5 worker return. It
applies only to newly generated cards. A frozen older card keeps its original
schema and is never rewritten or sent back for rework.

The task card is authoritative for identities, obligations, capabilities, risk
signals, and whether adverse routing is present. This reference explains how to
project those frozen values into one return without reading implementation code
or private tests.

## Copy the binding

Copy `project_id`, `round_id`, `assignment_id`, `worker_id`, and
`blackboard_snapshot_sha256` from the card. Copy `task_card_sha256` from the
assignment in `round-status` or the generated prompt. The card's
`return_contract`, `assurance_contract`, and `artifact_capability` determine the
remaining shape and bounds.

Do not invent or omit an obligation, reuse another assignment's hash, or add an
explanatory top-level key.

If `control_plane.independent_adverse_pair` is present, also obey its exact
role and `worker_context_id`. A `paired_adverse` worker must not receive,
inherit, summarize, or share the primary worker's active context. It attacks
the same frozen source Research using the card's `adverse_routing` rules. This
is a worker-allocation and provenance contract only: the return is nontruth
Research, and it creates neither a second Candidate review nor certification
authority.

## Exact top-level object

A current assurance-bound card without `adverse_routing` uses exactly:

```json
{
  "schema_version": 5,
  "project_id": "COPY_FROM_CARD",
  "round_id": "COPY_FROM_CARD",
  "assignment_id": "COPY_FROM_CARD",
  "worker_id": "COPY_FROM_CARD",
  "task_card_sha256": "COPY_FROM_ROUND_STATUS_OR_PROMPT",
  "blackboard_snapshot_sha256": "COPY_FROM_CARD",
  "outcome": "insight",
  "claim": "One precise claim made by this Research return.",
  "content": "The bounded argument, evidence, counterexample, or blocker.",
  "narrative": {
    "rationale": "Why this result addresses the target.",
    "summary": "A concise summary.",
    "intuition": "A clear ordinary-language explanation.",
    "limitations": "What remains unproved or outside scope."
  },
  "artifacts": [],
  "obligation_dispositions": [],
  "computation_manifest": null,
  "research_assurance": {
    "source_uses": [],
    "route_invalidations": [],
    "extremal_cases": [],
    "claim_strength": [],
    "contour_substitutions": [],
    "claimed_structures": [],
    "program_math_alignments": []
  }
}
```

`outcome` is `proof`, `counterexample`, `evidence`, `dead_end`, `insight`, or
`challenge`. `claim` and `content` are nonempty. `narrative` has exactly the
four shown string fields, each bounded to 400 words.

The three assurance fields are present if and only if the card has
`assurance_contract`. If the card has `adverse_routing`, add exactly one
top-level `attack_learning` field. It is `null` unless the return meets the
productive-challenge or surviving-counterexample contract in
[adverse_routing_evolution.md](adverse_routing_evolution.md). If the card lacks
`adverse_routing`, adding the field is an error.

The copyable no-adverse template is
`assets/worker_return.v5.assurance-no-adverse.template.json`. Its uppercase
strings are placeholders, not valid bindings.

## Artifacts

For an assurance-bound card, each artifact has exactly:

```json
{
  "path": "rounds/ROUND/artifacts/ASSIGNMENT/analysis.json",
  "sha256": "64_lowercase_hex_for_exact_bytes",
  "role": "paper_target_analysis"
}
```

The project-relative path must resolve inside the exact card artifact
directory, name an ordinary file, and match the declared hash. Roles are
nonempty and unique. File count and byte sizes stay within the card's caps.

### Two-subround Research specializations

If `research_cycle.subround="production"`, the work mode is `compute`, and
the source Research has no `approved_computation_execution`, this is design,
not execution. Return exactly three artifacts with roles
`computation_source`, `computation_design`, and
`computation_dependencies`. Use `computation_manifest=null` and an empty
`program_math_alignments` list. Do not include output, logs, runtime receipts,
or a formal target result.

If `research_cycle.subround="supervision"`, return a
`research_supervision_report` artifact that covers every exact receipt in the
source Research's `research_supervision` binding. The supervisor attacks the
frozen outputs; it does not rewrite them or use Pulse to negotiate a mutable
repair.

If a production compute source contains `approved_computation_execution`, the
return is a formal execution. Its `computation_source` and
`computation_dependencies` hashes must exactly equal the frozen
`design_artifacts` hashes. It must also include `computation_output`, the
`computation_log`, the ordinary computation manifest, and the full
program-math alignment. Any code
or dependency change fails preflight and requires a new design and supervision
cycle.

## Per-obligation dispositions

Create exactly one entry for every object in
`assurance_contract.obligations`. Each entry has exactly:

```json
{
  "obligation_id": "COPY_EXACT_CARD_OBLIGATION_ID",
  "status": "complete",
  "witness_artifact_sha256s": ["DECLARED_RETURN_ARTIFACT_HASH"],
  "rationale": "Explain how the cited bytes discharge this obligation."
}
```

Rules:

- ids exactly cover the card's obligation ids once each;
- status is `complete`, `blocked`, or `not_applicable`;
- `not_applicable` is allowed only when the obligation explicitly permits it;
- every witness is the hash of a declared return artifact;
- a `complete` entry cites the artifact for every role named in that
  obligation's `required_artifact_roles`;
- a `proof` return cannot mark an obligation `blocked`.

For a Paper continuation card, declare one `paper_target_analysis` artifact and
repeat its hash in every disposition whose required role is
`paper_target_analysis`. Do not use an empty list when the card has obligations.

## Computation manifest

When `assurance_contract.computation_stage_count` is zero,
`computation_manifest` is exactly `null`. Otherwise it is exactly:

```json
{
  "stage_count": 1,
  "entries": [{
    "obligation_id": "COPY_STAGE_OBLIGATION_ID",
    "source_artifact_sha256": "DECLARED_SOURCE_HASH",
    "output_artifact_sha256": "DECLARED_OUTPUT_HASH",
    "command": ["python3", "relative_script.py"],
    "runtime": {"implementation": "CPython", "version": "3.x"},
    "role": "load_bearing",
    "manual_contract": "State the mathematical quantity computed."
  }]
}
```

Entries exactly cover the declared stage count. Both hashes name returned
artifacts. `role` is `load_bearing` or `supporting`. Command arguments after the
executable may not be absolute or contain a `..` path component.

## Research assurance

The object always has exactly these seven lists:

```json
{
  "source_uses": [],
  "route_invalidations": [],
  "extremal_cases": [],
  "claim_strength": [],
  "contour_substitutions": [],
  "claimed_structures": [],
  "program_math_alignments": []
}
```

Empty lists are valid only when the frozen risk signals and computation-stage
count do not require evidence.

Each `source_uses` item has exactly `source_key`, `use_kind`,
`source_strength`, `target_strength`, `source_artifact_sha256`,
`toy_check_artifact_sha256`, and `bridge_artifact_sha256s`. `use_kind` is
`result`, `definition`, or `formula`. Strength is `fixed_object`,
`local_family`, or `relative_family`, in increasing order. A formula requires
an artifact-bound toy check; a stronger target requires an artifact-bound
bridge.

`route_invalidations` is a duplicate-free list of exact 12-hex Research ids.
Only `counterexample`, `challenge`, or `dead_end` may invalidate a route.

Each `extremal_cases` item has exactly `case_id`, `status`,
`witness_artifact_sha256s`, and `finding`. Status is `pass`,
`counterexample`, or `not_applicable`; witnesses name declared artifacts.

Each `claim_strength` item has exactly `claim_id`, `claimed_strength`,
`downstream_required_strength`, `comparison`, `disposition`, and `rationale`.
`comparison=equal` requires `disposition=retained`.
`comparison=stronger_than_required` requires `pruned` or
`retained_with_necessity`.

Each `contour_substitutions` item has exactly `source_contour`,
`target_contour`, `swept_region`, `poles`, `crossed_pole_ids`,
`uniform_noncollision_witness`, `residue_accounting`, and `degeneration_test`.
Each pole has exactly `pole_id`, positive integer `multiplicity`,
`parameter_behavior`, and `disposition`. Pole disposition is `distinguished`,
`excluded_by_uniform_witness`, or `retained_additional_residue`.
`residue_accounting` is `distinguished_is_complete_enclosed_sum` or
`all_additional_residues_retained`. `degeneration_test` has exactly `family`,
`boundary_behavior`, `interior_zero_behavior`, and `result`.

Each `claimed_structures` item has exactly `kind`,
`domain_artifact_sha256`, `forward_map_artifact_sha256`,
`inverse_map_artifact_sha256`, `multiplicity_artifact_sha256`,
`negative_control_artifact_sha256`, `typed_record_fields`,
`automorphism_controls`, and `value_free=true`. `kind` is `bijection`,
`involution`, `matching`, or `pairing`. All hashes name declared artifacts;
`typed_record_fields` includes `occurrence_identity` and `multiplicity`.

There is exactly one `program_math_alignments` item per computation stage. Its
exact top-level fields are `stage_index`, `obligation_id`,
`formula_projection`, `domain_projection`, `representation_projection`,
`approximation_budget`, `output_interpretation`, and `independent_checks`.

- `formula_projection`: exactly `formula_literal`, `formula_sha256`,
  `source_locator`, `code_artifact_sha256`, `code_anchor`, and
  `sign_and_convention_map`;
- `domain_projection`: exactly `mathematical_domain`,
  `code_iteration_domain`, nonempty `boundary_cases`, and
  `witness_artifact_sha256`;
- `representation_projection`: exactly nonempty `mathematical_objects`,
  nonempty `code_types`, `identity_and_multiplicity_policy`, and
  `witness_artifact_sha256`;
- `approximation_budget`: exactly `mode`, `required_order`,
  `implemented_order`, `precision_or_error_bound`, and
  `derivation_artifact_sha256`;
- `output_interpretation`: exactly `output_artifact_sha256`,
  `claimed_quantity`, and `units_and_conventions`;
- each independent check: exactly `kind`, `artifact_sha256`, and `finding`.

Approximation mode is `exact`, `symbolic`, `truncated`, `numeric`, or `mixed`.
Only `truncated` and `mixed` use nonnegative integer order fields, with
`implemented_order >= required_order`. Check kind is
`independent_reimplementation`, `symbolic_oracle`, `metamorphic_relation`,
`degeneration_case`, `boundary_exhaustion`, `negative_control`, or
`dimensional_analysis`. A load-bearing stage needs at least two distinct checks
and one of the first three strong kinds; a supporting stage needs at least one.

## Paper continuation pattern

For the usual non-computational Paper target:

1. write one clear `paper_target_analysis` artifact inside the assigned
   artifact directory;
2. hash and declare its exact bytes;
3. create one `complete` disposition per frozen obligation and cite that hash;
4. use `computation_manifest=null` and the exact seven-list assurance object;
5. add `attack_learning=null` only when the card has `adverse_routing` and no
   qualifying attack case exists;
6. preflight the draft, then copy passing bytes unchanged to the canonical path.

The analysis should explain the issue, importance, burden, strongest charitable
objection, response or revision, failure surfaces, and writing mapping in clear
ordinary language. A technical term is allowed only when it is plainly defined
and genuinely needed; it must not stand in for a missing premise or inference.

## Commands and effects

```bash
mgraph --root PROJECT --role worker preflight-return ROUND_ID ASSIGNMENT_ID \
  --input DRAFT.json
mgraph --root PROJECT --role worker validate-return ROUND_ID ASSIGNMENT_ID
mgraph --root PROJECT --role main ingest-return ROUND_ID ASSIGNMENT_ID \
  --worker-final-sha256 EXACT_SHA256
```

`preflight-return` is read-only and may inspect a noncanonical draft. Copy the
passing bytes without reserialization. `validate-return` checks the canonical
path. Ingestion records Research; it does not create a Fact, decide Paper
adequacy, approve an attack route, or modify a CHX report.
