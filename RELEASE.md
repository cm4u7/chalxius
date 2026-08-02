# Chalxius v0.6.2 — Paper Graph Continuity / Brave Future BF-1–BF-3

Chalxius 0.6.2 makes a research draft—not a compressed convenience summary—the
continuing research object. It preserves the V5 truth path while adding a
prospective, domain-general Paper Research Pipeline and a deliberately bounded
advisory restoration of Brave Future L3/L4.

The release does not rewrite old Paper snapshots, Research, Candidates,
Certification Decisions, Facts, task cards, Evidence, or CHX ledgers. Stronger
contracts apply only when an Operator explicitly starts a new strict
\`research_draft\` plan or opts a Campaign into BF-1 through BF-3.

## Research drafts and finished external papers

A research draft is treated as the origin of the project:

1. Freeze the exact draft bytes and declared research target.
2. Decompose the draft into a proposition-total Paper DAG with source
   occurrences, operators, qualifiers, ordered premises, targets, bridges,
   objections, and defeaters.
3. Continue Research from the inherited Paper Graph. Copy-on-write successors
   keep stable local identities and explicit predecessor relations.
4. Review literature support claim by claim, with publication identity,
   locators, witnesses, and an independent support judgement.
5. Run a Paper-subject atomic preflight, composable verification,
   Certification Decision, and the ordinary Fact Gateway.

The \`auto\` reasoning mode may reduce research cost; it may not compress Paper
topology, provenance, atomic claims, target closure, or Fact requirements.

A finished external paper follows a different route. It may become immutable,
cross-project Evidence, but neither reputation, peer review, a DOI, a PDF, nor a
citation grants Fact authority. Its exact claims require an explicit bridge and
fresh project-local verification before admission.

## Domain-indexed research continuity

There is no single cross-domain “stance preservation” surrogate:

| Domain | Frozen continuity object | Valid terminal outcomes |
|---|---|---|
| Philosophy | Argumentative direction, headline thesis, required and forbidden claims | \`preserved\` or \`strengthened\`, unless the Operator authorizes an exact major revision |
| Mathematics | Exact problem/conjecture, hypotheses, domains, quantifiers, and target claim ids | \`proved\`, \`disproved\`, or \`unresolved_with_obstruction\` |
| Empirical | Question, estimand, population, exposure/intervention, outcome, and scope | supported, disconfirmed, or inconclusive |
| Mixed | Explicit component adapters and their shared target ids | Composition of the component outcomes |

A counterexample to the unchanged conjecture preserves a mathematical target.
A proof of a weakened or re-quantified statement does not resolve it.

## Composable verification

CHX-014 is resolved with a risk-derived, immutable verification work plan
rather than one omniscient verifier:

- a planner signs the exact Candidate/capsule-derived shard plan before
  dispatch;
- the Host signs immutable role and artifact capabilities;
- reviewers are project-registered, distinct, scope-bound, and blind to peer
  results;
- signed receipts cover claims, targets, predecessors, defeaters, interfaces,
  transport, and artifacts;
- a deterministic aggregate fails closed on missing, duplicate, conflicting,
  stale, or incomplete receipts;
- adjudication and the Fact Gateway remain separate from shard reviewers.

This is a reusable mechanism for philosophy, mathematics, empirical work, and
mixed projects. Parallelism changes verification organization, never the truth
gate.

## Brave Future BF-1 through BF-3

The cautious L3/L4 restoration is advisory and requires an exact, explicitly
activated Campaign:

- **BF-1:** read-only projection of typed, complete repair lineage from one
  frozen planning snapshot;
- **BF-2:** deterministic zero-write reassessment of that same snapshot;
- **BF-3:** after explicit opt-in, one same-volume atomic nontruth advisory
  receipt.

Repeated blockage parks and escalates without another write. There is no active
Campaign pointer selection, second scheduler, background loop, \`plan_one\`,
\`execute_one\`, round planning, worker dispatch, score writeback, Campaign
closure, Reader/Learner mutation, or Candidate/Certification/Gateway/Fact
effect.

## CHX architecture closure and disclosure

The public registry explicitly enumerates CHX-001 through CHX-057. For this
release, every short id is qualified by ledger namespace
\`run-20260801T233737840117Z-a29d00a787c1/CHX-NNN\`; a same-numbered issue from
another immutable ledger is not the same issue.

The prospective mechanisms are documented in
[\`chalxius/KNOWN_LIMITATIONS.md\`](chalxius/KNOWN_LIMITATIONS.md) and bound into
\`INHERITANCE.lock.json\`. A publication-disclosure preflight compares the
public list and required documentation markers with the exact private ledger
and fails if an issue is missing, unresolved, or assigned to the wrong run.
Private source content and the private ledger are not distributed.

Resolved field mechanisms are evidence for this release contract, not a claim
that no future architecture defect can exist. A new discovery opens a new
append-only CHX issue; it never weakens Fact admission.

## Compatibility and authority

The only truth path remains:

\`\`\`text
Research -> Candidate Release -> Certification Decision -> Fact
\`\`\`

The release is prospective. It performs no automatic project migration,
backfill, reclassification, forced redo, authority inheritance, or global
runtime replacement. Frozen work remains readable under its exact runtime
identity. Historical runtime archives are validation data and are never
executed or used for active writes.

## Validation summary

- Complete suite: 622/622 PASS on the final tree and 622/622 PASS after a cold
  archive extraction.
- Targeted installed-tree CHX/Paper tests: 37/37 PASS.
- Release mutation audit: 110/110 killed with
  \`candidate_unchanged=true\`.
- Field Paper Pipeline reliability matrix: 1200/1200 semantic mutations killed,
  with zero surviving mutations and zero harness errors.
- Manifest: 201/201 entries; cold extracted tree exact; no symlinks, caches,
  bytecode, or unexpected files.
- Deterministic archive: 202 regular files; two builds byte-identical.
- Public examples: 3/3 deterministic/privacy validations PASS.
- Transactional global-cutover rehearsal and final cutover: all ten audit
  rounds completed before and after replacement, with rollback preserved.

These checks establish bounded software and workflow properties only. They do
not prove a theorem, establish philosophical or empirical truth, establish
novelty, certify a private graph, or admit a research claim. See
[\`VALIDATION.md\`](VALIDATION.md).

## Install

Download the two adjacent release assets and verify before extraction:

\`\`\`sh
shasum -a 256 -c chalxius-0.6.2-paper-graph-continuity-brave-future-bf1-bf3.tar.gz.sha256
tar -xzf chalxius-0.6.2-paper-graph-continuity-brave-future-bf1-bf3.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
\`\`\`

Replacing a currently installed skill remains a separate explicit cutover
decision. Never replace the runtime beneath an already-frozen work unit.
