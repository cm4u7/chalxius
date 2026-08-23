# Chalxius V5 architecture

Chalxius is one integrated system for source reconstruction, mathematical
exploration, replayable computation, certification, teaching, and offline
presentation. It has one research engine and one Fact-admission path.

Software checks establish whether recorded evidence satisfies Chalxius's
contract. They do not make a mathematical statement infallible.

## The four durable states

```text
Research -> Candidate Release -> Certification Decision -> Gateway admission -> Fact
```

1. **Research** is cumulative nontruth. It contains attempts, insights,
   challenges, counterexamples, obstacles, computations, repairs, and
   dispositions without treating any of them as premises.
2. **Candidate Release** freezes the exact claim or atomic internal mini-DAG,
   proof, direct predecessors, source evidence, computation evidence,
   Paper/Audit references, and linked adverse work proposed for certification.
3. **Certification Decision** is one immutable record written by the Gateway
   from a different fresh verifier's review of only the frozen capsule.
4. **Fact** is the exact accepted release exposed by the Gateway after all
   bindings are revalidated. Only current Fact nodes may be reused as trusted
   premises.

There are three happy-path authority transitions. Advice, votes, profile
closure, Reader output, teaching success, and prose confidence do not create a
fourth path.

## Authority and storage planes

| Plane | Purpose | Truth effect |
|---|---|---|
| Paper source | Preserve exact source bytes and relations | Evidence of what a source says |
| Paper reconstruction | Record an explicit interpretation of the source | Nontruth interpretation |
| Paper audit | Hold objections, corrections, decisions, and replacement history | Audit evidence only |
| Research | Accumulate exploration and adverse work | Nontruth |
| Blackboard | Hold typed exploratory nodes, edges, and snapshots | Nontruth |
| Candidate Release | Freeze one exact certification proposal | Candidate only |
| Certification | Store the verifier capsule and Gateway-written immutable decision | Evidence, not a premise by itself |
| Fact Graph | Store gateway-admitted active Facts and dependencies | Sole trusted premise store |
| Learning | Hold teaching, attempts, misconceptions, and mastery evidence | Nontruth |
| Reader | Present frozen projections in one offline page | Presentation only |

Authority labels are boundaries, not decoration. Copying a Paper node to the
Blackboard does not turn it into a source or Fact. A correct Learner answer
does not enter Research. A positive Certification Decision does not expose a
Fact until the gateway admits the exact same bytes.

## Certification contract

A V5 Candidate Release can become a Fact only when all applicable checks pass:

1. exact statement, proof, direct predecessors, source evidence, candidate
   artifacts, and release bytes are content-addressed;
2. every external predecessor is an active V5 Fact statement interface;
3. source version, hypotheses, notation, glyphs, conventions, quantifiers,
   witnesses, and applicability are checked exactly;
4. load-bearing computation is replayable and binds commands, versions,
   checkpoints, artifacts, outputs, and independent checks;
5. truncated series computations derive retained-order budgets from the
   requested coefficient and factor valuations and include a deeper replay;
6. dependent candidates form one acyclic all-or-none internal mini-DAG;
7. every linked challenge, counterexample, or obstacle is included and has an
   exact disposition;
8. the verifier is fresh and receives only the frozen capsule;
9. decision, release, capsule, gateway marker, and stored Fact match exactly;
   and
10. revocation cascades through dependents and the current audit remains clean.

If any gate is missing, Chalxius reports the exact blocker. It does not lower
the standard because a task uses `fast` mode or because an exploration profile
is incomplete.

## Research collaboration

Every worker receives an immutable task card with three communication planes:

- compact control and final handoff;
- one frozen bounded mathematical-state view; and
- bounded narrative rationale, summary, intuition, limitations, and open
  boundary.

New V5 Pulse planning is retired. Main explicitly selects Research, planning
creates immutable production or supervision assignments/cards, and Main
launches and confirms the workers. Completed logical components may enter fresh
supervision while unrelated production continues. Historical Pulse records
remain readable and retain their original status, audit, dispatch, close, void,
and abort operations.

Adverse work uses the Research plane. Candidate preparation binds the exact
selected canonical claim and all applicable completed supervision, then a
distinct fresh adverse worker reviews it and Main records the disposition.
Fresh verifier review, the Gateway-written Certification Decision, and Gateway
Fact admission remain separate owner boundaries.

`profile-closure-status` and `profile-closure-record` are compatibility
surfaces for repair advice. They can identify missing planned work and append
evidence-bound guidance to Research. They cannot complete, certify, or admit a
claim.

## Reasoning profiles

`fast`, `auto`, and `deep` allocate future exploration:

- `fast` keeps costly exploration opt-in;
- `auto` follows deterministic task signals and is the default;
- `deep` requests every costly feature that is genuinely applicable.

A mode switch affects future work units only. All modes share the same
Candidate Release, Certification, and Fact contract.

## Paper, Audit, and correction

Paper source, reconstruction, and audit remain separate. A current reviewed
Paper Logic snapshot and its Audit snapshot can be bound node-by-node into a
Candidate Release. Corrections append a challenge, disposition, replacement
object, and new snapshot; historical bytes are never rewritten.

Research may mirror Paper material onto the Blackboard for exploration, but the
mirror preserves its nontruth authority and exact receipt.

An active research draft follows the Paper-first lifecycle: freeze its exact
source, decompose it into a proposition-total DAG, bind targets and dependencies,
perform nodewise Research and admission work, and reconstruct a copy-on-write
successor Paper. A finished external publication instead enters the Evidence
plane with its exact PDF and reviewed Paper Graph. Neither route silently
inherits Fact authority.

Continuity is domain-indexed. Philosophy can preserve an explicitly declared
argumentative stance. Mathematics preserves the exact target, hypotheses,
domains, and quantifiers, and allows proof, disproof, obstruction, or separately
typed weaker progress. Empirical and mixed work use their own exact target
adapters rather than borrowing the philosophy stance rule.

## Architecture learning: CHX and PHX

CHX is the append-only issue and repair ledger. A finding is recorded before it
is classified. A tactical repair is confined to one project run; a repair
intended for global installation goes directly through the cross-ledger global
integrated-repair route, without a synthetic tactical precursor. Every observed
issue still receives an explicit disposition.

PHX is the host-global, project-independent route guide. It distills reusable
major architecture proposals and measured tradeoffs from CHX and other evidence
without duplicating concrete problems. PHX search, evaluation, and reporting
are advisory. A recorded route grants no implementation authority; changing the
active architecture requires a separate, informed user consultation.

## Historical projects and project background

A new V5 root starts with an empty Fact Graph. V1-V4 and Danus roots remain
unchanged and readable, but their Facts, reviews, profile closures, migration
receipts, and acceptance markers are not V5 authority. Chalxius does not
perform an in-place authority migration.

`PROJECT_BACKGROUND.md` is one bounded nontruth summary. Creating, rebuilding,
or refreshing it requires an explicit user instruction. A new card freezes its
complete exact-byte index and one round-local immutable snapshot, then workers
retrieve only selected chunks through that card; it does not preload the full
body into active context. If it is absent, Chalxius proceeds without generating
it. Every chunk remains retrievable, and load-bearing use returns to the exact
cited source.

## Learner and Reader

Chalxius Learner starts only after an explicit academic teaching or testing
request. It may read frozen snapshots and write only nontruth learning state.
Grill Me Code is a separate programming assistant and cannot mount research
graphs.

The Reader exports one deterministic offline HTML file. It preserves native
authority, status, source text, hashes, relation direction, and reading order.
Its runtime interaction state never writes back to Paper, Audit, Research,
Certification, Fact, Blackboard, or Learning data.

## Invariants to remember

1. V5 has one engine and one truth path.
2. Research is cumulative; malformed peers are isolated locally.
3. Only gateway-admitted V5 Facts are reusable premises.
4. V4 remains readable but supplies no V5 authority.
5. Profile closure is repair advice, not certification.
6. Modes change exploration cost, not Fact strength.
7. Paper/Audit corrections and Fact revocations preserve history.
8. Learner and Reader have no truth effect.
9. Research drafts continue from complete Paper DAGs; finished publications
   remain Evidence.
10. CHX records problems and repairs; PHX advises routes and never authorizes a
    cutover by itself.

For exact contracts, see
[`unified_architecture.md`](chalxius/references/unified_architecture.md),
[`admission_contract.md`](chalxius/references/admission_contract.md),
[`reasoning_modes.md`](chalxius/references/reasoning_modes.md), and
[`v5_release_traceability.md`](chalxius/references/v5_release_traceability.md).
