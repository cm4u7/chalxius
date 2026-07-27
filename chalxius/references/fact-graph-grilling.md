# Chalxius Learner: graph-aware teaching

Use this reference only after the user explicitly requests academic teaching,
questioning, testing, paper learning, exam training, mastery tracking, or spaced
review and a paper, project, or study plan has load-bearing claim
dependencies, an existing Fact, Paper, Audit, or exploration graph, rejected
routes, or a fixed deadline.
The graph organizes questioning; it does not turn teaching evidence into
mathematical proof.

Do not activate Chalxius Learner for ordinary research, audit, Fact admission,
ordinary coding, or a request to test Chalxius's research capability. Do not
mount a graph unless it materially improves the requested learning session.

## Enforce the low-cost boundary

Graph-aware teaching uses the unified lightweight nontruth learning plane: a
static reader plus a small pedagogical overlay. It may read frozen Fact Graph
files, including legacy-compatible inputs, or immutable Chalxius `pls-*`
Paper and `bbs-*` Blackboard snapshots, verify their artifact bindings, and
update only the user's learning evidence. Apply
[unified_learning_plane.md](unified_learning_plane.md) for mounts. The graph
algorithm is inherited from Grill Me; that reuse does not invoke or embed a
Danus or Grill research runtime.

Never invoke the unified research engine, a legacy MathGraph runtime, another
graph-generation or audit skill, multi-agent proof work, web research, or fresh
fact admission from this mode.
Never run a proof verifier merely to choose a drill question. A local hash check
only establishes artifact identity and drift, not mathematical correctness.

If a certificate or snapshot manifest disagrees with source bytes, a required
endpoint is missing without an omission receipt, or the graph format is
unsupported, fail closed and report the exact problem. Preserve receipt-bound
Blackboard boundary endpoints as nonlearnable stubs. Do not repair or regenerate
the source graph; that requires a separate source-owning task.

## Keep two linked projections

Maintain three logically separate views:

1. **Source-authority projection** — admitted Fact artifacts, Paper source and
   reconstruction objects, Paper Audit objects, and Blackboard exploration
   objects retain distinct authority and nontruth statuses. A legacy Danus fact
   remains identifiable as an imported source artifact.
2. **Mastery projection** — what the learner has actually demonstrated, with
   evidence, hint depth, error class, last review, and next due review.
3. **Pedagogical projection** — explanations, examples, misconceptions, and
   classroom objections, all explicitly not facts.

Link mastery to the exact source anchor it concerns, but never copy `admitted`,
`reviewed`, or `exploration` into `mastered`. Likewise, a strong learner answer
does not admit a fact or validate a reconstruction, audit, or exploration node.

For a persistent learning graph, key every Fact-aligned node by the
**exact full SHA-256 of the corresponding source fact artifact**. Preserve the
source graph's `fact_id` verbatim as an alias. Mastery, hints, errors, and review
events are an overlay under that key; they are not part of the mathematical
fact's content hash. Give every evidence event its own canonical SHA-256.

Key a foreign snapshot anchor by a canonical binding containing source kind,
immutable snapshot id, source object id, and exact object SHA-256. Preserve the
full source object and relation payload for bounded context retrieval, but never
map its status to admitted. A Blackboard Paper mirror and its authoritative
Paper object remain different nodes even when their embedded prose is identical.

This identity contract permits exact cross-graph alignment:

- identical full source-fact hashes share one learning node and may accumulate
  several source references;
- identical short `fact_id` values with different full hashes are distinct nodes
  and must be reported as a collision;
- a changed source file creates a new fact hash and makes the old source
  reference stale;
- a new `pls-*` or `bbs-*` snapshot creates new foreign identities, so old
  learning evidence cannot silently migrate to a correction;
- a misconception, teaching explanation, or exercise with no source-fact
  counterpart receives its own pedagogical hash and links to the truth-aligned
  node with `tests_mastery_of` or `repairs`.

Do not set a learning record's own content hash equal to a source fact hash. That
would falsely claim byte identity between two different artifacts.

Keep source prose, exploration, admitted facts, obstacles, rejected candidates,
learner state, and reconstructed exposition distinct. A theorem-looking sentence
in a paper is not automatically an admitted fact. A fact-graph closure is evidence
about dependencies and reviews, not a formal proof certificate.

## Ground an existing graph

Inspect the exact project artifacts before questioning:

- frozen source or paper hashes and target statements;
- target IDs and their admitted predecessor closure;
- fact statements and declared hypotheses, not only titles;
- rejected candidates, review errors, repairs, and replacement edges;
- scope exclusions, conventions, orientations, and external-source certificates;
- current audit compatibility and whether the graph is historical or live.

Use only user-selected exact graph versions. The unified learning plane may
co-mount immutable Fact, Paper, and Blackboard artifacts without starting any
research runtime. Read-only source inspection is the default. Do not mutate a
persistent source graph, admit facts, or write learner data unless the user
explicitly authorizes the separate learning overlay.

When no persistent graph exists, maintain an in-session projection rather than
inventing fact IDs or silently creating files.

## Import and maintain the learning overlay

Use the bundled standard-library tool for persistent overlays:

```bash
python3 -B scripts/learning_graph.py init \
  --source-root /absolute/path/to/source-project \
  --output /absolute/path/to/learning-graph.json

python3 -B scripts/learning_graph.py import \
  --source-root /absolute/path/to/another-source-project \
  --graph /absolute/path/to/learning-graph.json

python3 -B scripts/learning_graph.py mount-paper \
  --source-root /absolute/path/to/chalk-project \
  --snapshot-id pls-FULL_64_HEX \
  --graph /absolute/path/to/learning-graph.json \
  --current-audit-only

python3 -B scripts/learning_graph.py mount-blackboard \
  --source-root /absolute/path/to/chalk-project \
  --snapshot-id bbs-FULL_64_HEX \
  --graph /absolute/path/to/learning-graph.json

python3 -B scripts/learning_graph.py teach \
  --graph /absolute/path/to/learning-graph.json \
  --node FULL_64_HEX_LEARNING_KEY_OR_UNAMBIGUOUS_SOURCE_ID \
  --coverage taught-unchecked \
  --note "Explained the local estimate and its role in the next dependency."

python3 -B scripts/learning_graph.py add-teaching-node \
  --graph /absolute/path/to/learning-graph.json \
  --kind proof-discussion \
  --title "Why the cold residues must be grouped" \
  --summary "Compared the common-arrow argument with the rejected local-germ route." \
  --anchor-node FULL_64_HEX_LEARNING_KEY_OR_UNAMBIGUOUS_SOURCE_ID

python3 -B scripts/learning_graph.py record \
  --graph /absolute/path/to/learning-graph.json \
  --node FULL_64_HEX_LEARNING_KEY_OR_UNAMBIGUOUS_SOURCE_ID \
  --mastery 3 --status reconstructable \
  --evidence "Blank-page derivation with one nonstructural sign slip."

python3 -B scripts/learning_graph.py context \
  --graph /absolute/path/to/learning-graph.json \
  --node SOURCE_OBJECT_ID --radius 2 --max-nodes 60

python3 -B scripts/learning_graph.py record-source-concern \
  --graph /absolute/path/to/learning-graph.json \
  --node SOURCE_OBJECT_ID --kind misconstructed-edge --severity blocking \
  --description "The support edge appears to reverse the paper's inference."

python3 -B scripts/learning_graph.py verify \
  --graph /absolute/path/to/learning-graph.json
```

Every adapter is read-only with respect to its source graph. The Fact Graph adapter discovers
`fact_graph/facts/*.md`, verifies any available
`reports/target-closure-certificate.json`, copies exact source IDs and
predecessor edges into a hash-keyed overlay, and records source-graph
fingerprints. Refuse to continue on a certificate mismatch. Run `verify` before
using stored mastery after source artifacts may have changed. Here `verify`
means only local schema, content-hash, edge, and drift checks; it never calls a
proof system or upgrades the source graph. `--source-root` accepts either the
source project root or its `fact_graph` directory.

`mount-paper` accepts only manifest-bound immutable `pls-*` snapshots and
preserves Paper source, reconstruction, audit, current/inactive audit state,
targets, and typed relations. `mount-blackboard` accepts only immutable `bbs-*`
snapshots and preserves exploration status, query omissions, and boundary
stubs. Use repeated plane, node-type, or seed options to bound a large mount;
use `context` for a radius-bounded working copy with an omission receipt.

Do not create or update a persistent learning overlay merely because Chalxius
is active. The user must request persistence or select a tracking location.
Standalone `$grill-me` is code-only and never reaches this workflow.

Teaching-mode events update only `coverage`, `last_taught_at`, and
content-addressed teaching notes. They must not change `mastery`, testing status,
error class, or testing evidence. Classroom objections and possible proof defects
belong in these notes or a lightweight source concern until an independent graph
workflow resolves them. A blocking source concern prevents new teaching from
that anchor. It does not alter the source object, and mastery of the defect is
still mastery of understanding rather than source validation. Use `record` only
for a declared testing-mode attempt.

For a lesson corresponding exactly to one source object, use `teach` so the event
is stored under that exact native or foreign binding. For a cross-anchor lesson,
proof discussion, analogy, example, or misconception repair, use
`add-teaching-node`. Its immutable pedagogical content receives its own hash and
links to one or more `--anchor-node` objects. Do not record the same lesson by
both routes merely to inflate coverage.

## Use explicit node and edge semantics

For each load-bearing mathematical node, track:

- exact statement and scope;
- hypotheses and conventions;
- prerequisites;
- proof mechanism or source certificate;
- known failure mode or counterexample;
- truth status and confidence boundary.

Use directed edges with concrete meanings:

- `requires`: a prerequisite needed before the target can be used;
- `supports`: evidence for, but not a complete proof of, a claim;
- `proves`: a complete stated implication within the recorded scope;
- `specializes`: instantiates a general result without strengthening it;
- `repairs` or `replaces`: closes a named defect in an earlier route;
- `refutes`: gives a counterexample to the literal claim;
- `contrasts_with`: compares routes without asserting implication;
- `tests_mastery_of`: links a question or reconstruction to a truth node.
- `teaches`: links a teaching lesson to the source anchor it explains;
- `discusses_validity_of`: links a proof-health discussion to the source anchor examined.

Do not use a vague edge such as `related_to` when a stronger logical relation can
be stated.

## Build the questioning frontier

For the learner's target, compute the conceptual prerequisite closure. At every
turn select one frontier node by this order:

1. unresolved prerequisite that blocks several downstream nodes;
2. rejected or repaired step whose failure mode is easy to repeat;
3. convention, sign, uniformity, or transport bridge that changes the theorem;
4. due spaced review of a previously weak load-bearing node;
5. transfer or research-judgment node after the core closure is mastered.

Break ties by mathematical risk, dependency fan-out, forgetting risk, and the
cost of discovering the gap late. Ask exactly one production question about that
node. Do not jump to a downstream theorem because the learner remembers its
conclusion.

## Update mastery only from evidence

Keep paper coverage orthogonal to mastery:

- `unseen`: not yet encountered;
- `located`: placed in the paper and proof map;
- `read`: learner has read the source block;
- `taught-unchecked`: explanation or guided derivation completed;
- `reviewed`: revisited after prior teaching or reading.

None of these coverage values implies a positive mastery score.

After an answer, update only the atomic nodes actually tested:

| Score | Evidence |
|---:|---|
| 0 | untested or no relevant answer |
| 1 | recognizes terms after substantial prompting |
| 2 | states part of the claim but misses a load-bearing condition |
| 3 | reconstructs the local argument with a small nonstructural gap |
| 4 | gives a correct blank-page derivation and handles one stress test |
| 5 | transfers the mechanism, states scope limits, and diagnoses a nearby failed route |

Record the exact evidence and highest hint level used. A supplied explanation is
not mastery evidence. Require a later blank-page reconstruction before raising
the score, and a spaced transfer variant before assigning 5.

When an answer exposes a misconception, add a pedagogical node for that
misconception and a `repairs` edge from the corrective example or explanation.
Keep it outside the admitted mathematical fact store.

## Turn a target closure into a deadline plan

Plan by mastery gates, not page counts:

1. freeze the target and its prerequisite closure;
2. mark nodes as already evidenced, weak, untested, or blocked;
3. put high-risk bridges and repaired failures before downstream assembly;
4. assign each day one primary closure block and one short spaced reconstruction;
5. reserve the final block for full blank-page proof mapping and scope review;
6. keep explicit buffer for a prerequisite that takes longer than expected.

A day's work is complete only when its named evidence artifact exists: for
example, a theorem statement with hypotheses, a proof skeleton, a derivation of
one key estimate, a counterexample to the rejected route, or an oral explanation
that survives follow-up.

For advisor-facing readiness, require the learner to reconstruct the target's
critical path, explain every repair edge, state what remains conditional, and
identify which graph/audit claims are historical rather than freshly verified.

## Checkpoint projection

At a checkpoint, show only the useful slice:

- current target;
- mastered prerequisites with evidence;
- blocking or weak frontier nodes;
- rejected routes the learner can now diagnose;
- next due reconstruction.

Do not overwhelm the learner with the entire persistent graph. The purpose is to
make the next dependency and the evidence standard obvious.
