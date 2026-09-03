# Blackboard Exploration Graph v4

Read this reference before changing blackboard graph types, spaces, queries, snapshots, merges,
indices, or promotion.

## Truth boundary

The blackboard is a content-addressed exploration graph, not a fact database and not a shared
prompt. A blackboard node or edge can never be a predecessor. The edge names `proves` and `refutes`
are forbidden. Evidence-like nodes remain nontruth until an explicit promotion creates ordinary
memory and the normal fact workflow succeeds.

## Storage model

Nodes and edges are immutable canonical JSON objects stored by content hash. Append-only type
registries define their semantics. Transaction receipts determine visible graph state; indices are
derived caches and can be rebuilt.

Core node types include spaces, conjectures, formulas, definitions, obligations, obstacles,
experiments, computation results, source locators, intuitions, notes, conflicts, mechanisms,
predictions, display-only fact-interface mirrors, and reserved Paper Logic mirrors.

Exact core node names are `space`, `conjecture`, `formula`, `definition`, `obligation`, `obstacle`,
`experiment`, `computation_result`, `source_locator`, `intuition`, `note`, `conflict`, `mechanism`,
`prediction`, `fact_interface_mirror`, `paper_logic_mirror`, and `type_registry`.

Exact core edge names are `placed_in`, `subspace_of`, `overlaps_with`, `suggests_proof`,
`suggests_refutation`, `supports_candidate`, `challenges`, `refines`, `generalizes`, `specializes`,
`analogous_to`, `depends_on_experiment`, `motivates`, `blocks`, `resolves`,
`convention_variant_of`, `source_for`, `derived_from`, `duplicates`, `supersedes`, `closes`,
`retracts_placement`, `explains_candidate`, `predicts`, `fails_on`, and
`paper_relation_mirror`. Only relations registered
with an acyclic policy reject cycles. General exploratory relations may cycle. Near-synonyms are
not aliases: for example, use `supports_candidate`, not an unregistered `supports` edge.

A syntactically legal unregistered `x-namespace:name` custom type is preserved with opaque
semantics until an operator registers its exact type/version definition. It does not drive
traversal, acyclic closure, scoring, conflict synthesis, or truth. An opaque edge appears in a
snapshot only when both endpoints were independently selected. Unregistered core-like names and
near-synonyms still fail validation.

## Spaces and placement

A node is stored once and may have multiple `placed_in` edges. A space is a view and collaboration
boundary, not an ownership copy. Cross-space edges remain visible when both endpoints are authorized.

Workers may:

- read only nodes/edges in their frozen snapshot;
- write placements only to task-card `write_space_ids`;
- connect to listed cross-space endpoints;
- create a space only when `allow_create_space` is true.

They may not mutate existing CAS objects or write into an undeclared space.
They also cannot create `paper_logic_mirror` or `paper_relation_mirror` objects. Those reserved
types are accepted only through the Paper Logic projection transaction described in
`paper_logic_graph_v1.md`.
The orchestrator derives assignment-specific write and endpoint lists from the corresponding
memory entry when `blackboard_write_space_ids` or
`blackboard_cross_space_endpoint_node_ids` is present. This permits three workers to share one
frozen snapshot while the engine—not worker prose—enforces distinct source, computation, and
geometry write lanes.
The exact return validator dry-runs registry, endpoint, cycle, placement, capability, and budget
checks before a worker declares final handoff; ingestion repeats the same graph preflight. A
commitment-bound pulse edge additionally runs the exact closure vocabulary, binding, witness, and
relation/disposition checks at this pre-write stage.

## Query and snapshot

A query declares seed nodes, direction, hop limit, edge/node type allowlists, and node/edge budgets.
Traversal and output ordering are deterministic. If a budget truncates the graph, the snapshot
records an omission receipt rather than silently pretending completeness.

Snapshot identity depends on the deterministic current projection and query, not worker completion
order. `supersedes` and `closes` deactivate their targets from the current node/edge projection;
`retracts_placement` removes that placement from the current layout. Their immutable objects and
events remain visible through history. Edges incident to an inactive current endpoint are excluded.
Every assignment in a round that explicitly uses Blackboard binds the same
snapshot id and byte hash.

Prospective ordinary V5 Research has no implicit Blackboard query or snapshot.
Its persistent card, assignment, manifest, and return contract carry exact
`null` snapshot bindings, with empty read/write space lists. Routine V5
planning JSON omits that absent projection, while exact round status and frozen
bytes retain the full shape. An exact promoted query or an explicitly requested
write-space capability creates, binds, and foregrounds one bounded snapshot for
that round. Historical cards retain their frozen root or wider snapshots and
write capabilities and are validated against those exact bytes. This removes
the unused per-round default snapshot ceremony without deleting Blackboard
state, Paper mirrors, promotions, explicit snapshots, or Learner mounts.

New public V5 Pulse planning is retired because the production/supervision
cycle owns prospective Research collaboration. V4 Pulse and operations needed
to inspect or finish an already-created record remain compatible. They preserve
their original immutable commitments and receipts and do not become Fact
authority. Routine V5 Main/host help does not advertise this family. A
historical V5 Pulse operation can create a new compatibility commitment only
from a round that explicitly bound a Blackboard snapshot; an ordinary
snapshot-free round is not retrofitted after freeze.

## Merge and conflicts

Validate the complete delta before changing visibility. Merge is hash-bound and idempotent. The
same logical key under a `unique_conflict` policy never uses last-write-wins: retain both immutable
objects and synthesize a conflict node. Multi-value types retain all values.

Placement retraction appends a `retracts_placement` relation; it does not erase historical layout.
Use a new node or edge for corrected content.

## Paper Logic mirror sandbox

`paper-logic-project-blackboard` can place a complete, non-omitted slice of one frozen Paper Logic
snapshot into a named space. Each mirror node embeds the full source paper node plus its source
snapshot/object hash; each relation mirror embeds the full source paper edge. The Paper Logic
projection receipt binds the query, view, node map, mirrored edge inventory, Blackboard
transaction, and target space.

Mirrors remain `truth_status="exploration"` and cannot be edited or promoted directly. An agent
must create its own exploration node, cite the mirror, and use the ordinary promotion workflow.
Generic direct writes and worker deltas reject the mirror types. Audit reports an unbound mirror,
tampered source binding, or mismatched transaction as an error.

The first release is local to one project and one physical root. Cross-project, cross-machine, and
multi-root federation is disabled; raw remote peer endpoints are rejected.

`assets/blackboard_graph_delta.v4.example.json` shows the envelope. Content ids in a real return
must be generated from canonical object bytes.

## CLI workflow

Use JSON input files for structured mutations:

```bash
"$MGRAPH" --root "$PROJECT" --role main blackboard-query --input QUERY.json
"$MGRAPH" --root "$PROJECT" --role main blackboard-snapshot \
  --input QUERY.json --actor main
"$MGRAPH" --root "$PROJECT" --role operator blackboard-reindex --dry-run
"$MGRAPH" --root "$PROJECT" --role operator blackboard-reindex --apply \
  --actor operator
```

Type registration and applied reindexing are operator-only. Use `blackboard-promote-node` only to
create an actionable memory projection; promotion does not admit a fact.

## Audit and recovery

Audit must recompute ids, type registrations, endpoints, cycle policies, transactions,
current/history projections, snapshots, and derived indices. A dry-run reindex is read-only.
Applied reindex must be reproducible.

Orphan CAS bytes after a failed pre-receipt write are not visible truth or visible graph state, but
remain auditable. Candidate submission, memory effect, and blackboard transaction share one
ingestion receipt as their visibility marker. A crash before that marker has zero visible delta;
recovery rebuilds derived indices from the immutable receipt and an identical retry is idempotent.

## Embedded unified learning-plane consumption

The package-local `scripts/learn` consumer may mount an exact immutable `bbs-*`
query snapshot into the unified nontruth learning plane. Every mounted node
remains exploration-nontruth, including `paper_logic_mirror` nodes. The consumer
must bind manifest, query, node, and edge hashes and must not query or mutate the
live Blackboard. Historical `danus-chalk-readonly-snapshot-mount-v1` / external
Grill Me metadata is accepted only for read-only import compatibility and is
normalized on load; it is not a current runtime route.

A bounded snapshot can contain an edge to a node omitted by its query budget.
When the omission receipt declares that endpoint, the embedded learning plane
preserves it only as a nonlearnable boundary stub and keeps the exact edge. It may not invent the
payload, drop the edge silently, treat the stub as a Paper object, or infer that
the snapshot is a complete exploration graph.
