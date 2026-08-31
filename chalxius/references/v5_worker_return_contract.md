# V5 worker return: exact public contract

This is the public contract for a current assurance-bound V5 worker return. It
applies only to newly generated cards. A frozen older card keeps its original
schema and is never rewritten or sent back for rework.

The task card is authoritative for identities, obligations, capabilities, and
risk signals. Newly generated cards do not contain adverse routing. A frozen
older card may still contain it; this reference explains how to satisfy that
historical byte-bound contract without reactivating its retired learning plane.
That old path is procedurally reserved for explicitly selected 0.x completion
or audit. The runtime does not authenticate pre-1.0 provenance, and no new
provenance or identity gate is implied.

## Copy the binding

Copy `project_id`, `round_id`, `assignment_id`, `worker_id`, and
`blackboard_snapshot_sha256` from the card exactly. For an ordinary current
round the Blackboard value is JSON `null`; for a round with an explicitly
bound Blackboard snapshot it is the exact hash string. Copy `task_card_sha256` from the
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
Research, and it creates neither a current Fact-package review nor certification
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
  "blackboard_snapshot_sha256": null,
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
`assurance_contract`. Only when a frozen historical card has
`adverse_routing`, add exactly one
top-level `attack_learning` field. It is `null` unless the return meets the
productive-challenge or surviving-counterexample failure-report contract in
[adverse_routing_evolution.md](adverse_routing_evolution.md). If the card lacks
`adverse_routing`, adding the field is an error.

For current cards the worker reports the concrete failure, witnesses,
reproduction and boundary in the ordinary Research or supervision result.
There is no attack proposal, persistent-rule synthesis, activation, or extra
report step.

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
repair. The adjacent `failure_informed_assurance` binding freezes the exact
release registry hash, family id, and concise focus for that scope. Review only
that evidenced focus and the exact receipt set: do not widen into a generic
audit, add agent scoring, or re-attack admitted Fact premises without separate
contradiction evidence. A worker cannot edit or propose a replacement for the
registry through its return.

If a prospective schema-v3 Research repair card sets
`repair_spec.output_shape="research_split_batch"`, the return still belongs to
one assignment but specializes its product shape. Include exactly one artifact
with role `research_split_batch`. That JSON artifact declares the complete
actual successor membership chosen after reading the old product; Main does not
predeclare a member count. It contains two through 128 distinct coherent
successor claims with their content, rationale, old-material disposition and
limitations, plus shared assumptions, residual/open material, abandoned
material and one completeness rationale. A current batch also includes
`internal_relations`, `external_relations`, and a nonempty
`relation_allocation_rationale`. Each relation has one rigid type,
`proof_dependency` or `context`, plus a free label and rationale. Internal
targets use surface keys because Research ids do not exist yet; external targets
use exact existing Research ids. The worker must classify the actual logical
relations and omissions rather than manufacturing sibling-order edges. Do not
return a guessed placeholder count, several independent returns, or a partial
batch. Ingestion derives the successor Research ids, resolves the relation map,
and publishes the assignment owner and commit only after all records exist.
The planner creates a new card of this form only after exact one-shot
`--user-authorized-split` selection following a current explicit user request.
The authorization is not part of the return and is not rechecked during frozen-
card validation, ingestion, idempotent retry, or commit-last recovery.

When performing proof-logic supervision of a current committed split batch, the
`fact_statement_interfaces` artifact uses revision
`chalxius-supervised-statement-interfaces-2`. It covers every committed member
and includes one `split_relation_reviews` entry per batch. The supervisor checks
every declared member-member and member-external relation, searches for omitted
relations, and may confirm, remove, retype, or add relations for the mechanical
package recommendation. The recommended `proof_dependency` targets for each ready member must exactly equal that
member's `certified_predecessor_research_ids`; final `context` relations have no
Fact authority.
Source-scope supervision still reports whether each member is a coherent
surface, but checks only external-source identity, exact extraction, the
source's literal hypotheses/qualifiers/conventions, coverage, and corresponding
context relations. Mathematical applicability and theorem use belong to
proof-logic supervision; source scope must not certify the proof-dependency set.

On the procedurally reserved 0.x path, task cards frozen by Chalxius 0.7.13 or
later treat an artifact with role
`candidate_fact` is not a generic Markdown attachment. Worker preflight parses
the exact bytes as Fact Markdown, requires canonical round-trip serialization,
and requires exactly one semantic conclusion atom. A typed semantic interface
may separate premises from that conclusion; without one, the statement must
contain exactly one `[CLAIM:*]` clause. This prospective gate does not rewrite
or retroactively reject returns frozen under an older runtime. It also does not
require worker authorship: Main may author the same exact canonical Candidate
Fact bytes. Author and other provenance metadata preserve lineage but are not a
mathematical gate. The runtime does not authenticate pre-1.0 provenance; Main
must explicitly select this historical completion/audit path.

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

`source_artifact_sha256` names either a declared return artifact or an exact
task-card related artifact whose role contains the standalone token `primary`.
The latter is already a frozen graph capability and therefore must not be
copied into the return merely to become usable. Both capability kinds coexist:
historical returned-source bindings remain valid when a task card also carries
primary bytes. Toy checks and bridges are new work products and remain bound to
declared return artifacts.

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

Let `MGRAPH` name the executable `scripts/mgraph` shell entry under the exact
Chalxius root selected for this task. Invoke it directly rather than through a
Python interpreter or a bare command assumed to be on `PATH`.

```bash
"$MGRAPH" --root PROJECT --role worker preflight-return ROUND_ID ASSIGNMENT_ID \
  --input DRAFT.json
"$MGRAPH" --root PROJECT --role worker validate-return ROUND_ID ASSIGNMENT_ID
"$MGRAPH" --root PROJECT --role main ingest-return ROUND_ID ASSIGNMENT_ID
```

`preflight-return` is read-only and may inspect a noncanonical draft. Copy the
passing bytes without reserialization. `validate-return` checks the canonical
path through one bounded read-only return/artifact snapshot. A transient
`ENOENT` or `ESTALE` before a safe snapshot is visible may be retried after the
same paths stabilize and creates no quarantine. A symlink, escape, special or
otherwise unsafe object, or visible malformed, hash-drifted, schema-invalid, or
semantically invalid bytes remains fail-closed and follows the ordinary local-
quarantine path. The final handoff contains `assignment_id` and
`status="final"`; its
legacy `return_sha256` field is optional. Ingestion derives the SHA-256 from
the canonical bytes and treats a supplied legacy value only as an equality
assertion. Ingestion records Research; it does not create a Fact, decide Paper
adequacy, approve an attack route, or modify a CHX report. A later verifier
returns nontruth review bytes only; Gateway alone certifies Research. The old
`certification-record` command belongs to procedurally reserved 0.x
compatibility.
