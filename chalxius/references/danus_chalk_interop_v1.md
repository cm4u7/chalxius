# Danus-Chalk Grill Me interoperability v1

> **Legacy interoperability history, not current routing.** This document is
> retained to explain compatibility with existing mounts. New unified projects
> use `unified_learning_plane.md`; the old runtime-owner and Danus-family names
> below do not describe the current embedded learning plane. Standalone Grill
> Me 0.3.2-code cannot use this protocol; Chalxius itself owns all current
> academic mounts and learning records.

This protocol replaces absolute non-sharing with a narrow, read-only consumer
boundary. It does not merge the Danus and Chalk research runtimes.

## Roles and authority

| Component | Owns | May expose to Grill Me | Must not do |
| --- | --- | --- | --- |
| Danus Stable | admitted Fact Graph and its research workflow | exact fact artifacts, targets, and certificates | interpret or mutate Chalk project state |
| Chalk | Paper Logic, Audit, Blackboard, and Chalk Fact Graph stores | frozen pls Paper snapshots and frozen bbs Blackboard snapshots | write learner state or inherit teaching evidence as research truth |
| Grill Me | Danus-family learning, coverage, mastery, and pedagogical overlay | bounded teaching context and lightweight source concerns | invoke a research runtime, admit facts, repair source graphs, or write back |

The former Danus-Chalk no-sharing rule is therefore split in two:

1. Active research runtimes and writable project state remain mutually
   exclusive. A project root is never jointly operated by Stable and Chalk.
2. Immutable snapshot artifacts may be co-mounted by Grill Me as foreign
   anchors outside both research stores. This is interoperability, not runtime
   federation or truth-store sharing.

An explicit skill-maintenance task may inspect all three packages to validate
this contract. An ordinary research mutation must still select exactly one of
Danus or Chalk. An ordinary teaching session selects Grill Me; its static
reader does not activate either research runtime.

## Mount contract

- A Danus Fact node keeps the exact source artifact SHA-256 as its native
  learning key and may retain admitted as its source truth status.
- A Chalk Paper node requires an immutable pls snapshot, its manifest hash,
  object id, and canonical object hash. Paper source, reconstruction, and audit
  nodes remain distinct and all have nontruth learning statuses.
- A Chalk Blackboard node requires an immutable bbs snapshot and remains
  exploration-nontruth. A Paper mirror on the Blackboard is still a Blackboard
  exploration object, not a second authoritative Paper node.
- A bounded Blackboard snapshot may expose an edge whose other endpoint was
  omitted by the query. Grill Me preserves that endpoint only as a nonlearnable
  boundary stub bound to the omission receipt. It never invents the missing
  payload or silently drops the boundary edge.
- Foreign identities are namespaced by source kind, frozen snapshot id, source
  object id, and exact source-object hash. Identical-looking text never merges
  nodes across planes or snapshots.
- Every imported source relation preserves its original direction, type,
  object id, and hash. Filters and bounded context calls must return an explicit
  omission receipt.

## Pedagogy and performance boundary

Coverage, mastery, hints, error classes, spaced-review dates, explanations,
examples, and misconception repairs live only in the Grill Me overlay. They
receive lightweight content hashes but no Chalk review profile, multi-agent
audit, snapshot transaction, or Danus fact-admission gate. A mastery score says
how well the learner understands a mounted object; it never changes that
object's truth status.

Mounting and context retrieval use local JSON, JSONL, Markdown, and hashes
only. They do not call a MathGraph wrapper, network service, worker, verifier,
or source-research workflow. Optional plane, node-type, seed, radius, and
maximum-node filters bound cost without weakening source identity checks.

## If a mounted graph is wrong

Grill Me records a content-addressed source concern against the exact mounted
node. A blocking concern prevents new teaching from that node, while testing
may still measure whether the learner understands the defect. The concern does
not edit or supersede the source graph.

A real correction occurs in a separate task using the source-owning runtime.
For Chalk Paper or Audit material, freeze a new reviewed snapshot; for a
Blackboard issue, freeze a new query snapshot or source correction as
appropriate. Grill Me then mounts the replacement and appends a resolution
event binding the old concern to the new node and any external receipt. Old
learning evidence remains attached to the old snapshot-bound identity and is
never silently migrated.
