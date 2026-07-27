# Paper Logic Graph and Audit Graph v1

Use this protocol for a paper-led task in philosophy, mathematics, or a mixed
domain. It adds a reusable, source-bound representation layer before ordinary
agent exploration. It does not weaken the Fact Graph admission boundary.

## Four distinct planes

Keep these planes separate even when an agent sees them in one query:

1. `paper_source`: exact artifact and source units with page/region locators,
   byte/text hashes, speaker, inspection method, rendered-page hash, and an
   explicit ledger for negation, quantifiers, modality, conditionals,
   comparators, and normative operators.
2. `paper_reconstruction`: claims, definitions, formulas, inferences, and
   declared paper targets. Every object says whether it is a literal source
   item, paraphrase, researcher reconstruction, local emendation, or official
   erratum.
3. `paper_audit`: findings, counterexamples, repairs, impact assessments,
   challenges to prior audit nodes, and dispositions of those challenges.
4. `agent_exploration`: the existing Blackboard. It contains agent-created
   plans, objections, calculations, and hypotheses. It may contain a governed
   read-only mirror of a frozen paper snapshot, but that mirror remains an
   exploration aid.

All Paper Logic, Audit, mirror, bridge, readiness, and review objects have
`truth_effect="none"`. Only independently admitted Fact Graph facts are proof
premises.

## Required order

For a paper-led task:

1. Hash and preserve the exact source artifact.
2. Inspect rendered primary pages or source TeX for every load-bearing span.
   Text extraction or OCR may help locate text but is not primary evidence for
   a sign, negation, quantifier, bracket, subscript, or superscript.
3. Stage a bounded or full Paper Logic Graph revision.
4. Obtain two clean-context reviews:
   `source_fidelity` and `graph_structure`. The builder cannot review it, and
   the two profiles need distinct reviewers and distinct fresh contexts.
5. Freeze the reviewed revision as an immutable snapshot.
6. Query or project an exact snapshot slice for exploration.
7. Stage an Audit Graph against that exact snapshot.
8. Obtain independent `target_binding` and `audit_reasoning` reviews, then
   freeze the audit snapshot.
9. Admit a mathematical result only through the existing Fact Graph verifier
   gate. A paper snapshot or audit conclusion never enters predecessor lists.

Coverage is explicit. A bounded graph must state included and excluded
locators and cannot call itself a full-paper graph. Any unresolved
load-bearing unit blocks freezing.

## Construction safeguards

### Source fidelity

- A literal claim must be an exact substring of its declared source units.
- Attribution must agree with the source-unit speaker. Quoted authors,
  interlocutors, objections, editors, and the paper's author are distinct.
- Every scanned high-risk surface operator needs exactly one ledger entry.
  Omitting `not`, changing `all` to `some`, or changing `<` to `<=` therefore
  changes the object and normally fails source review.
- A researcher reconstruction is attributed to the researcher and carries a
  semantic-difference note. A local emendation has an explicit parent claim.
  Neither is silently rewritten into the author's voice.
- Formulas require a glyph ledger. Definitions used by claims are explicit
  graph nodes rather than unexplained prose vocabulary.

### Graph structure

- Inferences have ordered premises, one conclusion, a type, strict or
  defeasible strength, authorial status, explicit bridge claims, and explicit
  defeater claims. Each defeater is materialized as a typed `defeats` edge
  from the claim to the inference; it is not merely buried in node payload.
- Normative conclusions from wholly nonnormative premises require a declared
  normative bridge. Default-presumption conclusions are defeasible.
- Inference dependencies must be acyclic.
- At least one headline target is required. Every argument-relevant claim must
  reach some declared paper target, which may be headline or supporting. This
  preserves independent subtheses without falsely making them premises of the
  paper's main route.
- Input edges must exactly match the ports declared by the nodes. Reversing
  `premise_of`, attaching evidence to a neighboring sentence, or inventing an
  undeclared edge fails staging.

## Audit safeguards

An audit finding names one exact target node, exact evidence source units, an
observed excerpt, compared text, and load-bearing tokens. For a source-sensitive
finding, evidence must be anchored to that exact target. A sentence elsewhere
in the same paragraph or paper is not interchangeable evidence.

A counterexample records:

- the exact target representation;
- a construction;
- one witness for every premise of one exact targeted inference;
- an explicit conclusion-failure witness;
- whether the interpretation was preserved;
- nontriviality and reproducible evidence;
- a provisional exact logical effect.

For mathematics, `refutes_exact_claim` is legal only when the exact
representation is demonstrably refuted: all premises hold, the conclusion
fails, the interpretation is preserved, and evidence is reproducible.
Philosophical importance weighting does not weaken this exact logical test.

For philosophy, record two effects separately:

- `logical_effect`: what happens to the exact represented claim or inference;
- `dialectical_effect`: what happens to the paper's broader thesis.

Allowed philosophical outcomes distinguish clarification, trivial exception,
local repair, scope revision, substantive revision, variant refutation, core
refutation, and indeterminacy. A local repair must identify a local,
core-preserving repair. `refutes_core` requires demonstrated exact refutation
and no viable core-preserving repair. A trivial counterexample cannot be
inflated into variant or core refutation.

This philosophy-only weighting responds to the expert evaluation about
over-refutation, undefined concepts, and evidential overstatement. It does not
apply a "抓大放小" rule to mathematics.

## If the Audit Graph is wrong

Never edit or delete the old node or snapshot.

1. An agent records an ordinary Blackboard challenge and freezes the relevant
   Blackboard snapshot.
2. `paper-logic-link-exploration` creates a receipt with relation
   `exploration_challenges_audit`, binding the exact audit object, exact paper
   snapshot, exact Blackboard object, exact Blackboard snapshot, hashes, and
   rationale.
3. A new Audit Graph revision adds an `audit_challenge`.
4. A new `audit_disposition` records one of `upheld`, `narrowed`, `corrected`,
   `withdrawn`, or `unresolved`. Narrowing or correction names replacement
   nodes.
5. Independent reviewers check the new revision. Freezing it creates a new
   immutable snapshot and may supersede the old audit snapshot.
6. `current_audit` hides corrected, narrowed, or withdrawn targets while the
   historical snapshot remains queryable.

If the defect lies in source transcription or the Paper Logic reconstruction,
create a new full Logic Graph revision that supersedes the old Logic snapshot.
Audits whose base is superseded are reported stale. Do not silently retarget
them.

Reasonable philosophical disagreement can remain as challenged parallel audit
judgments. Do not settle a load-bearing dispute by majority vote.

## Blackboard use

`paper-logic-query` is the normal strong-access interface. It returns full
objects and edges from one exact frozen snapshot, has explicit views
(`source`, `reconstruction`, `audit`, `current_audit`, `combined`), and reports
any node or edge omission caused by budgets.

When an agent needs the graph spatially present for planning or derivation,
use `paper-logic-project-blackboard` with `projection_mode="full_fidelity"`.
The projection creates reserved `paper_logic_mirror` nodes and
`paper_relation_mirror` edges inside a named Blackboard space, plus an exact
projection receipt. Generic writes and worker deltas cannot create these
reserved types.

Mirrors are visually and semantically distinct from agent work:

- mirror nodes contain the complete frozen paper object and source binding;
- mirror nodes remain `truth_status="exploration"`;
- agents cannot mutate or directly promote a mirror;
- an agent may create a new exploration node that cites a mirror, then promote
  that new node through the ordinary campaign/memory path;
- cross-store ordinary edges are forbidden. Use a snapshot-bound bridge
  receipt instead.

## CLI

Initialize and stage:

```bash
"$MGRAPH" --root "$PROJECT" --role main paper-logic-init --actor MAIN
"$MGRAPH" --root "$PROJECT" --role main paper-logic-stage \
  --input logic-bundle.json --artifact paper.pdf --actor BUILDER
```

Review and freeze:

```bash
"$MGRAPH" --root "$PROJECT" --role paper-auditor \
  paper-logic-record-review --input review.json
"$MGRAPH" --root "$PROJECT" --role main \
  paper-logic-freeze REVISION_ID --actor MAIN
```

Query, mirror, bridge, and audit:

```bash
"$MGRAPH" --root "$PROJECT" --role main paper-logic-query SNAPSHOT_ID \
  --view combined --input query.json
"$MGRAPH" --root "$PROJECT" --role main paper-logic-project-blackboard \
  --input projection.json --actor MAIN
"$MGRAPH" --root "$PROJECT" --role main paper-logic-link-exploration \
  --input bridge.json --actor MAIN
"$MGRAPH" --root "$PROJECT" --role main paper-logic-audit
```

`paper-auditor` can inspect frozen paper evidence and append one review. It
cannot stage, freeze, project, modify the Blackboard, write memory, or admit
facts. Workers receive Paper Logic context only through bounded task-card
material selected by the orchestrator; they cannot query live paper state.

## Embedded unified learning-plane consumption

The package-local `scripts/learn` consumer may mount an exact frozen `pls-*`
directory into the unified nontruth learning plane. It verifies the manifest and
every canonical node and edge hash, preserves all three planes and
current/inactive Audit state, and assigns only nontruth learning statuses. This
static read does not start a second runtime, create a projection receipt, or
authorize any legacy writer to inspect the project. The historical pre-Chalxius
`danus-chalk-readonly-snapshot-mount-v1` and external Grill Me identity are
accepted only as read-only import metadata and are normalized on load; they are
not current routing protocols.

If teaching exposes a possible misread or misconstructed Audit node, the
learning plane records only a source concern against the snapshot-bound
identity. If the user requests resolution, a separate work unit in the same
Chalxius research engine must append the challenge/disposition/repair,
obtain the normal independent reviews, and freeze a superseding snapshot. The
learning graph may then bind the old concern to a node in that new snapshot;
old learning evidence stays on the old immutable identity. A proposed repair
and a claim-refuting objection remain distinct typed research outcomes.
