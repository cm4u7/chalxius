# V5 managed supervisor bootstrap

This is the complete **startup** contract for one current, machine-bound V5
Research supervisor. Its purpose is to start the exact proof, program, source,
or integration attack without loading Main-only planning and release protocols.
It changes no validator, lifecycle state, or truth boundary.

## Applicability gate

Use this compact path only when all of the following are literal task-card
facts:

- `research_cycle.subround="supervision"`;
- `work_mode="refute"`;
- `mathematical_state.source_research_dossier.metadata.research_supervision`
  is present;
- the exact task-card semantic hash and workflow owner are accepted by worker
  CHX.

`runtime_binding`, when present, is diagnostic provenance only. It does not
make a current installation or historical archive a prerequisite for
supervision.

If any condition is absent, inconsistent, legacy, or unvalidated, stop the
compact path and use the ordinary full protocol routed by `SKILL.md`. Never
infer supervision from prose, filenames, assignment timing, or the worker role.

For an applicable card, read completely, in this order:

1. the candidate's full `SKILL.md`;
2. the generated prompt and exact task card;
3. this reference;
4. every exact source return and artifact authorized by the card.

Read each unique path/hash byte object once even when the card repeats it under
several descriptive roles. Reuse the verified binding instead of rereading it.

Do not preload `unified_architecture.md`, `reasoning_modes.md`,
`admission_contract.md`, `v5_capability_matrix.md`, `brave_future_l3_l4.md`,
`agent_protocol_v4.md`, or `v5_worker_return_contract.md`. The task card plus
this contract contain the supervisor's needed projection of those boundaries.
Load a broader protocol only at one of the conditional branches below.

## Conditional expansion

- For `program_math`, read `computational_verification_v4.md` before judging
  mathematical-to-program projection or an actual computation output.
- For `source_scope`, read both `external_theorem_applicability.md` and
  `external_source_reliability.md`. A supervisor in another scope must also read
  them before introducing any new external theorem, formula, or source as
  evidence. Existing source bytes are not authority for a new use merely
  because the production return cited them.
- Keep `attack_learning=null` by default. Before returning a surviving
  `counterexample` or a non-null productive-challenge `attack_learning`, read
  `adverse_routing_evolution.md` and use its exact current failure-report
  schema. Report concrete evidence and boundaries only; never synthesize a
  persistent route rule. A concern, clean result, or non-load-bearing
  suggestion does not qualify.
- The compact CHX procedure below is sufficient for normal start and close. If
  the worker observes a problem caused or materially amplified by Chalxius
  architecture, read `chx_runtime_ledger.md` completely and record the finding
  before repair or omission. Mathematical mistakes and source defects are not
  CHX findings.
- The seven assurance lists below are normally empty for a supervisor. Before
  emitting a nonempty typed entry whose schema is not completely specified by
  the applicable conditional protocol, read `v5_worker_return_contract.md`.

Conditional expansion is local: loading one applicable protocol does not
activate the other broad references.

## First-output checkpoint

After startup and exact-card binding, the next progress milestone must be the
required `research_supervision_report` artifact or one explicit blocker naming
the missing capability, Research product, or premise. Do not emit consecutive
status-only updates such as "reviewing", "writing the report", or "almost at
preflight" while the authorized artifact directory remains empty. Main may
reclaim a supervisor that repeats a no-output milestone. This is a bounded
communication rule, not a watcher, timer, lifecycle state, audit, truth gate,
or packaging prerequisite. If the work contract itself causes or materially
amplifies a repeated no-output milestone, record that concrete architecture
finding in worker CHX before close. Do not turn it into a PHX route or
persistent attack rule; Main performs that later coordination.

Once the required supervision report exists, the next progress milestone must
be one explicit blocker or the strict preflight result. After preflight passes,
the next milestone must be canonical byte validation and CHX close. Do not
repeat "preflight soon", "closing", or equivalent status without a new result.
This completion checkpoint adds no gate: it only eliminates idle last-mile
turns while preserving the exact return contract.

## Frozen authority and scope

The card is the immutable capability boundary. Verify its semantic hash and use
only its frozen read capabilities, artifact directory, return path, and size
caps. The `research_supervision` binding identifies the exact source round,
logical component, product-descriptor hash, supervisor scope, and source
Research products. The historical `source_receipts` field name is retained for
schema compatibility; it does not require a separate receipt file. The
adjacent `failure_informed_assurance` binding identifies the exact static
failure family and concise attack focus. Cover every bound product descriptor and no
timing-derived subset.

Attack the new production Research and its declared artifacts. An admitted
Fact dependency is a frozen premise, not a default attack target. If exact new
evidence contradicts one, state the conflict separately for Main to route to an
authority-governed reopening; do not rewrite or silently invalidate the Fact.

For current cards, `supervised_production_authority` in the source Research
dossier is the content-addressed projection of each attacked production task
card. The supervisor's ordinary Fact dependencies and related-artifact
allowlist include the projection's active premises, production task card, and
exact input/source capabilities. Use those bytes for premise and source replay;
do not treat the supervisor Research's own narrower authority snapshot as a
description of the attacked production route. A missing or hash-drifted closure
is a capability blocker, not permission to reconstruct it from prose.

Scope meanings are narrow:

- `proof_logic`: test the asserted inference, hypotheses, quantifiers,
  boundary cases, typing, and claimed strength;
- `program_math`: test formula/domain/representation projection, conventions,
  computation plan or executed bytes, and output interpretation;
- `source_scope`: test exact locators, source strength, theorem hypotheses,
  conventions, and transport to the claimed target;
- `integration`: test only interfaces shared across the distinct primary scopes
  frozen into the component, including coordinates, conventions, premises, and
  output contracts.

Do not widen the assignment into a generic audit, score agents, search for new
counterexamples to already admitted Facts, or replace the production worker's
task with a new proof attempt. There is no live Pulse or Blackboard repair bus.
A defect is reported for a later copy-on-write Research repair cycle. The
logical subround order does not prevent unrelated work from running in time.

## Worker CHX

Before substantive attack, use the `chx_ledger.py` under the candidate root
bound by the task card:

```bash
python3 -B CANDIDATE_ROOT/scripts/chx_ledger.py start \
  --project-root PROJECT \
  --task "bounded description of this supervisor assignment" \
  --host-task-scope-id HOST_SCOPE_FROM_CARD \
  --task-card /absolute/path/to/exact-task-card.json
```

Runtime, version, manifest-file, manifest-tree, card-hash, or canonical-root
mismatch must fail before a ledger is created. Keep the returned ledger path.
If no architectural finding occurs, close it after return validation and before
the final handoff:

```bash
python3 -B CANDIDATE_ROOT/scripts/chx_ledger.py close --ledger LEDGER_PATH
```

Obey the close result: report qualifying architecture issues only when
`report_required=true`; say nothing about an issue-free ledger when it is
false. The worker does not run the host-level attack recommendation report.
The card-bound start event lets Main project a genuine finding into the small
nontruth CHX observation inbox at return ingestion; an issue-free supervisor
creates no inbox entry or second report.

## Required report

Write one concise `research_supervision_report` inside the exact artifact
directory and bind its SHA-256 in the return. Unless the card explicitly names
another required output role, this report is the only returned artifact. It
must identify:

- the supervisor scope and failure-family focus;
- every frozen product descriptor and reviewed artifact hash;
- each attack actually performed and its result;
- one of: clean bounded result, concrete defect, surviving counterexample, or
  explicit blocker;
- the precise affected claim, premise, file, formula, locator, interface, or
  computation boundary for every defect;
- what is outside the review, including any unreviewed source or Fact premise;
- whether later copy-on-write repair is required.

The report is nontruth Research. It does not mutate the attacked artifacts and
does not itself dispose a later Candidate challenge.

## Exact return

Use exactly the following top-level keys. Add `attack_learning` if and only if
the card contains `adverse_routing`; for current supervisor cards it is normally
present and normally `null`.

```json
{
  "schema_version": 5,
  "project_id": "COPY_FROM_CARD",
  "round_id": "COPY_FROM_CARD",
  "assignment_id": "COPY_FROM_CARD",
  "worker_id": "COPY_FROM_CARD",
  "task_card_sha256": "COPY_FROM_PROMPT_OR_ROUND_STATUS",
  "blackboard_snapshot_sha256": "COPY_FROM_CARD",
  "outcome": "evidence",
  "claim": "One precise bounded supervision conclusion.",
  "content": "The attack result and explicit limitations.",
  "narrative": {
    "rationale": "Why this review addresses the frozen focus.",
    "summary": "A concise result.",
    "intuition": "A clear ordinary-language explanation.",
    "limitations": "What was not established or reviewed."
  },
  "artifacts": [{
    "path": "CARD_ARTIFACT_DIRECTORY/research-supervision-report.md",
    "sha256": "SHA256_OF_EXACT_REPORT_BYTES",
    "role": "research_supervision_report"
  }],
  "obligation_dispositions": [{
    "obligation_id": "COPY_EXACT_CARD_OBLIGATION_ID",
    "status": "complete",
    "witness_artifact_sha256s": ["SHA256_OF_EXACT_REPORT_BYTES"],
    "rationale": "How the report covers this exact obligation."
  }],
  "computation_manifest": null,
  "research_assurance": {
    "source_uses": [],
    "route_invalidations": [],
    "extremal_cases": [],
    "claim_strength": [],
    "contour_substitutions": [],
    "claimed_structures": [],
    "program_math_alignments": []
  },
  "attack_learning": null
}
```

Copy identities literally. Create exactly one disposition for every card
obligation and no others. Status is `complete`, `blocked`, or
`not_applicable`; the last is allowed only when the card says so. Every witness
must be a declared artifact hash, and each complete obligation must cite every
required artifact role. `outcome` is one value allowed by the card. Use
`counterexample` only for a surviving falsification satisfying the full attack
learning contract; use `challenge` for a concrete bounded defect, and
`evidence` or `insight` for a clean bounded result. All four narrative values
are strings of at most 400 words.

`route_invalidations`, when justified by `challenge`, `counterexample`, or
`dead_end`, is a duplicate-free list of exact 12-hex Research ids. Do not use it
to invalidate an admitted Fact or an unbound route. A supervisor has no
computation stage, so `computation_manifest` remains `null` and
`program_math_alignments` normally remains empty even for `program_math`; the
mathematical-program attack belongs in the report.

## Preflight and handoff

Write a mutable draft under the card's work directory. Then run:

```bash
mgraph --root PROJECT --role worker preflight-return ROUND_ID ASSIGNMENT_ID \
  --input /absolute/path/to/draft.json
```

Preflight is read-only. If it fails, repair the draft or report a blocker; do
not weaken a field or invent a capability. After it passes, first confirm the
canonical return path does not exist, then copy the draft bytes without
reserialization. Confirm byte equality and SHA-256, and run:

```bash
mgraph --root PROJECT --role worker validate-return ROUND_ID ASSIGNMENT_ID
```

Close worker CHX, then hand off exactly `assignment_id`, `return_sha256`, and
`status`. Main alone ingests the exact hash. Ingestion creates cumulative
nontruth Research only. Candidate Release, fresh Candidate adverse review,
verifier, Certification Decision, Gateway, and Fact admission remain distinct
and unchanged.
