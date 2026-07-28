# Chalxius 0.4.0 architecture

## One engine, three execution profiles

Chalxius is the only active research runtime. `fast`, `auto`, and `deep` vary
future exploration budgets only. They never select a retired Danus, Chalk, or
coordinator runtime and never weaken or strengthen Fact admission.

Original Danus 0.2.9 and later predecessor releases are behavioral and
performance references only. Chalxius 0.4.0 imports no predecessor runtime,
writer, Fact, review, receipt, or mutable project state. V4 projects remain
readable in their original roots but are historical nontruth from the point of
view of a new V5 authority root.

## Authority domains and truth path

V5 has three persistent authority domains and one derived presentation surface:

| Domain | Contents | Truth effect |
|---|---|---|
| Research Ledger | cumulative claims, attempts, insights, challenges, counterexamples, obstacles, experiments, repairs, and dispositions | none |
| Certification Ledger | immutable decisions over exact sealed Candidate Releases | certification evidence only |
| V5 Fact Graph | admitted statements, active predecessor edges, admissions, and revocations | sole premise store |
| Reader projection | deterministic packet-v1/HTML view over the domains plus Paper/Audit, Blackboard, and optional background | none |

The only truth-bearing path is:

```text
Research --release--> Candidate Release --decide--> Certification Decision --admit--> Fact
```

There is no Round Closure, Pulse Closure, Profile Closure, Campaign Closure, or
separate adverse-review object on this path. Compatibility commands may report
process readiness, but they cannot supply admission authority.

Candidate Release automatically binds every existing challenge,
counterexample, or obstacle that targets its selected Research branch. The
producer must dispose every such attack, and `adverse_actor_ids` must exactly
match the actors of the bound adverse Research. An unrelated project-wide
challenge is not pulled into the release. V5 does not require inventing a new
attack when none exists and does not add a second adverse filter.

## Three communication planes and immutable task cards

Every V5 work unit keeps three communication planes distinct:

1. control: bounded prompt, host commands, and exact final hash handoff;
2. mathematical state: one frozen Blackboard snapshot, admitted predecessor
   interfaces, exact related Research context, and default-if-present
   project background;
3. narrative: bounded rationale, summary, intuition, limitations, and open
   boundary.

The immutable task card is the capability boundary. A worker may not infer
permissions from filesystem visibility. All workers in one planned round share
the same Blackboard snapshot. A bad return is quarantined locally; other valid
returns remain independently ingestible and cumulative.

`work-unit-abort` is reserved for an explicit user cancellation of one frozen
unit. It blocks future managed return and experiment work for that unit but does
not delete its Research, snapshots, or already-ingested receipts.

## Pulse collaboration

Pulse remains an optional two-wave coordination layer:

- Wave 1 commits independent assignments to one snapshot.
- Each valid contribution is ingested separately into Research.
- A barrier binds the after-snapshot and exact Wave-1 Research hashes.
- Wave 2 receives exact peer Research in its task-card mathematical state.
- A malformed peer is locally quarantined; it does not destroy valid peers.
- Pulse closure is advisory coordination status with no admission authority.
- `pulse-abort` stops future dispatch while preserving all existing Research.

Host dispatch is fail-closed unless a trusted host issuer and fresh-context
binding are configured.

## Paper Logic, Audit, Blackboard, and computation

Paper Logic and Audit retain their mature append-only storage and correction
semantics. A V5 paper Candidate Release binds current, nonsuperseded Logic and
Audit snapshots through exact `paper_evidence_refs`, nodewise target coverage,
source artifact hashes, and explicit certification checks. Paper/Audit objects
are never copied into the Fact Graph.

Blackboard remains typed cumulative exploration. Promotion creates Research,
never Fact. Claims, conventions, campaigns, novelty evidence, experiments, and
expert/interpretation exports remain optional task-local capabilities; no
automatic campaign or profile expansion is required.

Load-bearing series-product computation uses a machine-derived valuation
budget. For `[t^p] product_i f_i`, factor `i` must be retained through
`p - sum_{j != i} valuation(f_j)`. A bound deeper replay must extend the
truncation and reproduce the result. The aggressive boundary and mutation
suite is a release-time check only; it is not part of normal runtime.

## Project background and historical readability

Legacy and abandoned work may be summarized in exactly one
`PROJECT_BACKGROUND.md`. The host may generate or refresh that file only after
an explicit user instruction to do so. If the file already exists, every
substantive V5 work unit and Reader projection reads it by default and binds
its full UTF-8 body and hash. If it is absent, work proceeds without it and
Chalxius does not synthesize one. The summary is capped at 256 KiB. It is
nontruth context only. Any load-bearing use must return to and bind the exact
cited source.

V4 roots and original Danus material are never rewritten or recertified by V5.
Their readability is preserved by the original files and, when present, the
single background projection—not by inherited Fact authority.

## Reader and Learner boundaries

The Reader packet-v1 validator and renderer revision
`chalxius-reader-html-15` are unchanged. The V5 adapter deterministically
projects active Facts, Research, releases, decisions, current and superseded
Paper/Audit snapshots, and Blackboard state. Research-like lifecycle objects
use explicit Reader projection labels and never masquerade as Facts. If the
unchanged packet limits cannot express the selected project without
truncation, export fails visibly.

Chalxius Learner remains explicit and nontruth. It activates only for a user
request to teach, question, test, drill, or record learning. Grill Me Code is a
separate explicit programming-assistance surface with no research graph mount
or certification authority.
