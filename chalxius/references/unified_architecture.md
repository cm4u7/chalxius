# Chalxius architecture

## One engine, three execution profiles

This package is a source fork of MathGraph Chalk 0.4.0. Chalk V4 is the only
research engine, object model, protocol, CLI, audit system, and Fact Graph
gateway. `fast`, `auto`, and `deep` select exploration intensity within that
engine. They do not dispatch into the installed Danus or Chalk skills.

Danus 0.2.12 contributes two bounded inputs: a latency/performance target and a
frozen legacy-fact import format. No Danus engine module, V3 round protocol,
writer, or admission path is part of this package. Grill Me 0.2.0 contributed
the static learning-graph algorithm and academic pedagogical workflow; those
functions are now native to the Chalxius nontruth learning plane, whose public
surface name is `Chalxius Learner`, not a research runtime. Standalone Grill Me
0.3.2-code, publicly distinguished as `Grill Me Code`, is a separate programming
assistant. It is globally available to natural-language routing but activates
only on explicit programming Grill or Socratic intent, and has no graph mount
or research authority.

The public dispatch name is `chalxius`. The earlier
`operate-mathgraph-unified` string is retained only where changing an artifact
protocol identifier would create needless migration risk. That compatibility
identifier never selects another engine.

The exact lineage is machine-readable in `INHERITANCE.lock.json`.

## Authority planes

| Plane | Owner | May contain | Truth effect |
|---|---|---|---|
| Paper source | Paper Logic store | exact author text and source relations | source authority only |
| Paper reconstruction | researcher | reconstructed claims and inferences | candidate interpretation only |
| Paper audit | independent paper auditor | objections, countermodels, dispositions, repair relations | audit evidence only |
| Blackboard | research agents | questions, candidates, experiments, mirrors, plans, obstacles | exploration only |
| Fact Graph | admission gateway | admitted facts and active predecessor relations | the only premise store |
| Learning | learner/tutor | mastery, coverage, errors, hints, pedagogical nodes | none |

Blackboard Paper mirrors have a reserved type and exact projection receipt. A
mirror remains distinguishable from the Paper object and from ordinary agent
exploration. A learning mount retains the native plane and status of every
anchor but cannot promote it.

The optional reader HTML is not another authority plane. It is one disposable,
fixed-path presentation projection assembled from a strict nontruth packet.
The packet retains each object's native plane, status, exact original text, and
source hashes; the renderer cannot admit, repair, supersede, teach from, or
write back to any source. Its output has `truth_effect="none"` and may be
regenerated or overwritten without becoming graph history.

## Paper graph access and repair

Agents query immutable `pls-*` snapshots with bounded context and omission
receipts. For a difficult inference they may project a full-fidelity Paper
snapshot to one reserved Blackboard space, then add separate exploration nodes
and edges around it. They must not edit mirror nodes or use agent-created edges
as source relations.

Paper Graph and Audit Graph mistakes are corrected append-only:

1. identify the exact source or audit object and snapshot;
2. append a typed challenge stating the alleged misreading or misconstruction;
3. obtain an independent disposition;
4. append replacement reconstruction or audit objects and explicit
   `replaces`, `repairs`, or `refutes` relations;
5. freeze and independently review a new snapshot;
6. leave old snapshots available as historical evidence.

An unresolved blocking challenge prevents downstream reliance. It does not
delete history and does not by itself become a Fact.

## Routing and frozen work units

Reasoning mode state lives under `PROJECT/governance/unified-mode/`. The
contract and policy envelopes are immutable; the event ledger is append-only;
`current.json` is a verified projection of the latest event. Each new V4 round
binds the event id, policy hash, Fact admission hash, and deterministic
execution profile in its manifest, assignment contracts, and task cards. It
also freezes a derived `profile_obligations` object: feature statuses, exact
required-feature set, exact required assignments per feature, and an obligation
hash.

Required exploration closes through one immutable receipt under
`governance/unified-mode/profile-closures/by-round/`. The receipt is written
only after canonical assignment ingestion and binds the round manifest,
profiles, task cards, returns, ingestion receipts, outcomes/effects, and typed
feature evidence. `profile-closure-status` is recomputable; a no-required-feature
round is `not_required` without a receipt. A required but unclosed round blocks
single-Fact and atomic-bundle verifier construction, review recording, and
admission. Acceptance retry and audit revalidate the same bytes. Low-level
verification-bundle and FactBundle writers require non-public authority passed
by `MathGraphStore` only after the same closure check.

This closure gate has `truth_effect="workflow_readiness_only"`. It is adjacent
to, not part of, the invariant Fact admission contract; no routing mode or
closure receipt changes the Fact-contract hash. Machine-native evidence and
procedural host attestations remain separately labelled, with mixed composites
reported as `mixed_procedural_and_machine_verified`.

A mode switch affects only future work units. Existing rounds retain their
original profile until they complete or receive an explicit content-addressed
work-unit abort. That abort blocks all managed round, experiment, and pulse
writes but preserves read-only inspection and terminal cleanup.

## Historical compatibility

An unmodified Chalk 0.4 V4 project has no unified governance directory. It is
recognized and audited with a warning, not called corrupt. The unified engine
permits read-only API and CLI operations until an operator records `mode-init`;
every exposed child-store writer shares that guard. Activation requires a clean
current audit before advisory-lock creation, then repeats audit and inventory
under the transition lock before writing. Its schema-2 receipt inventories exact existing round hashes and
the complete exact-byte evidence behind every already-accepted ordinary Fact
and atomic FactBundle. Only that exact accepted set is historically exempt;
pending candidates are not, and drift invalidates governance. New writes then
bind unified governance, while legacy rounds remain frozen.

V1-V3 projects still require the existing copy-upgrade path. Legacy Danus facts
may be imported with their original assurance and provenance, but no new fact
uses a Danus admission route. V1-V3 public API and CLI mutation attempts fail
closed; only read-only inspection and an explicitly isolated copy-upgrade or
its dry run are supported. `reasoning_mode=None` exists only as an internal
Python compatibility seam for inherited Chalk fixtures, not as a supported
writable unified initialization mode. Official CLI initialization defaults to
`auto`.

There is no public boolean legacy-writer constructor switch. Underscored
identity-token fixture and staged-copy constructors are internal cooperative
seams, not a security boundary against reflection or direct filesystem access.
Dual read/write projection APIs are explicit: statement-interface
materialization and `reindex(apply=True)` are guarded writes; interface
reconstruction with `materialize=False`, `reindex(apply=False)`, audit,
claim-card assembly, experiment status, and resume validation are byte-pure and
never rebuild caches or create `.mathgraph.lock`.

A historical unified V4 round that predates frozen `profile_obligations` is not
retroactively blessed: replan it under the current engine. Reviewed Paper
snapshots may be deliberately reused across rounds only while current and
non-superseded. Campaign-expansion and novelty events are different: they must
be no earlier than the governed round. An Audit snapshot becomes stale when its
Logic base is superseded.

## Failure boundary

Routing never changes truth authority. If the selected profile does not allocate
the exploration needed to satisfy a triggered adoption or admission gate, the
claim remains a candidate and the engine returns an explicit blocker. There is
no fast-path Fact write and no teaching-to-research promotion path.

## Companion boundary

Research cost and interaction surface are orthogonal axes. `fast`, `auto`, and
`deep` govern Chalxius research execution only; no reasoning profile activates
Chalxius Learner or Grill Me Code. Selecting either interaction surface does not
change the reasoning profile or the invariant Fact gate.

Chalxius owns research. Its internal `Chalxius Learner` owns academic learning
but is activated only by explicit teaching, testing, paper-learning,
exam-training, mastery, or review intent. Research and audit do not start it
automatically, and persistent learning records require separate authorization.

Standalone `Grill Me Code` owns only explicitly requested Socratic programming
clarification, implementation assistance, debugging, review, and test planning.
Ordinary code work does not start it automatically. A mixed research-code task
keeps these surfaces explicit: research claims and graph operations remain in
Chalxius; code decisions may be assisted by Grill Me Code when requested but
gain no research certification from that exchange. Neither surface may treat
the other's notes as admitted truth.
