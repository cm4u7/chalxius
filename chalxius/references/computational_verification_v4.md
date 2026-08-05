# Computational Verification v4

Read this reference before recording computation, running an experiment, creating an artifact replay
bundle, or reviewing a computation-backed candidate.

## Evidence is not truth

A numerical value, symbolic output, modular scout, plot, benchmark, checkpoint, or successful
program run is computational evidence. It becomes load-bearing only inside a candidate proof with
an exact `[COMP:KEY]` anchor and an independently replayable verification bundle. A mutable work
file or checkpoint can never enter a fact or verification bundle.

## Computational evidence record

Each record declares:

- `role`: `load_bearing` or `corroborative`;
- an exact proof anchor occurring once;
- artifact roles, project-relative paths, and SHA-256 hashes;
- the entrypoint role and argv-form command;
- interpreter implementation/version and arithmetic model;
- an algorithm specification;
- a truncation certificate with checked orders and limitations;
- exact expected output roles/hashes and replay checks;
- an eight-axis independence matrix.

All artifacts must already be in the assignment manifest. Absolute paths, parent traversal, work
files, and checkpoints fail. A load-bearing record requires `artifact_replay`, authorization for
every artifact role, and both algorithm inspection and execution.

Agreement at two truncation depths is corroborative evidence, not a load-bearing truncation proof.

## Current V5 program-mathematics alignment

A prospective 0.4.3 V5 task card declares an exact computation-stage count.
The return must cover every stage once with:

- a literal mathematical formula and hash, its source locator, the exact
  executable-source artifact, one code anchor occurring exactly once, and an
  explicit sign/convention map;
- mathematical and code iteration domains, including boundary cases and a
  bound witness artifact;
- mathematical objects, code types, and a policy preserving occurrence
  identity and multiplicity;
- an approximation mode and derivation artifact; `truncated` and `mixed`
  stages must show nonnegative integer orders with
  `implemented_order >= required_order`;
- the exact output artifact, claimed quantity, units, and conventions;
- at least one independent check for supporting computation, or at least two
  distinct checks for load-bearing computation, including one independent
  reimplementation, symbolic oracle, or metamorphic relation.

This is semantic assurance, not merely replay. It is designed to catch a
correctly executed program that implements the wrong formula, loop domain,
representation, truncation order, or output interpretation. Exact replay and
the older eight-axis independence matrix remain applicable where their frozen
contracts require them.

For new two-subround Research, semantic assurance begins before execution. A
first-subround computer returns exactly three artifacts: executable core code,
the program-mathematics design, and the dependency manifest. Its computation
stage count is zero; output, logs, and an execution manifest are forbidden.
`plan-supervision-round` gives these exact hashes to a `program_math`
supervisor. Formal execution is scheduled only after that supervisor result is
explicitly disposed as `resolved_no_obstruction` or `resolved_by_evidence`.

The approved execution card binds the design return, supervisor return,
disposition, code hash, and dependency hash. The execution return must repeat
the same source/dependency bytes, add output and the normal stage/alignment
manifest, and then undergo another explicit program-math supervision round.
Changing code or dependencies starts a new design/supervision cycle. The old
automatic future nontruth review queue remains only for legacy single-wave
computation cards; approved execution suppresses that duplicate queue.
Ordinary prose mentioning code activates neither mechanism, and no review has
truth effect or automatically changes attack routing.

## Independence matrix

Record each axis separately:

- input transcription;
- algorithm derivation;
- implementation;
- runtime;
- truncation method;
- orientation generation;
- functional evaluation;
- final arithmetic.

Use only the typed values supported by the schema. Do not replace this matrix with `independent:
true` or a scalar confidence score. Shared input or runtime is acceptable when disclosed; it is not
independent confirmation.

## Experiment/job layer

Run the workload preflight described in
[adoption_policy_v4.md](adoption_policy_v4.md). The experiment layer is mandatory when a computation
is multi-stage or requires resume. It remains available but optional for every single-stage
non-resumable computation, including one whose duration is huge or unknown. Estimated budget,
duration, cost, and burden are advisory priority/load-order fields only. They do not select an
algorithm and never require an experiment, gate launch or scale, trigger notification, authorize
continuation, or stop work. A start manifest must state the task-card binding, purpose, algorithm,
complexity model (including `unknown` when honest), resources, stages, escalation ladder, checkpoint
format, resume compatibility, and expected outputs.

Events are append-only. Heartbeats and checkpoints show work progress but carry no truth status.
Every experiment command rechecks the supplied task card against the exact frozen card and hash in
the round manifest. Cooperative CLI mutations share the project lock, so identical concurrent event
replays append once. A failed event closes ordinary progress until `experiment-resume` validates the
selected checkpoint's current bytes, completed stage, and declared compatibility fields and records
one bound `resumed` event.

Checkpoint paths must remain below the experiment's `checkpoints/` directory. A checkpoint can bind
only a previously recorded completed stage, and resuming an earlier checkpoint returns that
checkpoint's stage rather than a later global stage. Finalize preflights all source paths,
destination basenames, existing collisions, and duplicate selections before copying any output.
The final receipt hashes only the selected frozen bytes. A finalized experiment rejects new events.
When preflight marks experiment/checkpoint required, return validation also requires a valid
finalized receipt and requires every selected output to occur in the assignment's declared artifact
manifest.

Artifact, graph, event, and checkpoint size/count caps protect containment, replayability, and
recovery. They are hard safety and integrity caps, not economic budgets and not frontier signals.
Crossing one may fail or safely checkpoint the affected operation; it does not shrink the research
panel or create an estimate-based continuation decision.

Small exact scripts may remain ordinary assignment artifacts. Do not force every toy computation
through the experiment layer.

`events.jsonl` remains the only canonical experiment ledger. A single
`events.index.sqlite3` file is a disposable derived lookup cache: each indexed row binds the exact
canonical line bytes, event id, ordinal, and byte range. Mutations write and `fsync` JSONL first,
then commit the cache. A crash in between is recovered by synchronizing the unindexed tail; a
missing, copied, malformed, schema-changed, or byte-mismatched cache is atomically rebuilt from
JSONL. Read-only status does not create a missing cache.

Warm idempotence lookup is indexed rather than a full history scan. The first build, an inode
change, same-size log edit, or cache recovery still deliberately pays one O(N) validation pass.
The cache is mutable work infrastructure, never a selected artifact, checkpoint, verification
bundle byte, or truth source. Pure time segmentation does not improve global duplicate lookup;
per-event sidecars and 256 custom shard files were rejected on file-count and recovery-complexity
grounds after an isolated 80,000-event comparison.

## Host duration notice

The host, not worker telemetry, observes the task's cumulative active-interval union. Overlapping
worker intervals count once and paused intervals do not count. Exactly 1200 active seconds does not
trigger. The first observation strictly greater than 1200 seconds creates one immutable notice while
managed work remains runnable. That notice includes the experimental nature, actual
elapsed time and observed resources, progress and latest checkpoint, importance and continuation
value, and the exact stopping impact. Forecasts and worker heartbeats cannot create, suppress, or
reset this transition.
The engine keys this cooperative ledger by project plus the hashed `host_task_scope_id` frozen into
each new task card. Distinct memories, workers, rounds, resumes, experiments, and campaigns within
one host task therefore contribute to one clock, while later independent host tasks do not inherit
its elapsed time or notice. Codex derives this scope from `CODEX_THREAD_ID`; other adapters must
hold `MATHGRAPH_HOST_TASK_SCOPE_ID` or `plan-round --host-task-scope-id` stable for the task.
All `start_ns`/`end_ns` values use one host-maintained task-relative monotonic timeline.
`clock_epoch` records source-clock provenance only; overlapping physical spans across different
epochs are still unioned once.

Use `assets/experiment_observation.v1.example.json` for the host-observation shape. A later
host/user response is optional; if recorded using `assets/experiment_decision.v1.example.json`, it
must bind the exact `notice_id` returned by `experiment-observe`. `continue` acknowledges the
notice, while only an explicit `stop` forbids subsequent managed writes.

The CLI can record hash-bound evidence of the notice and optional response, but it is a cooperative
evidence layer rather than authenticated user identity or a process supervisor. It never pauses,
terminates, or sends a signal to a process.

## Verification bundle

Choose the narrowest capability:

- `closed_packet`: statement, proof, statement-only predecessor interfaces, claims, conventions,
  ledgers, and no computation bytes;
- `artifact_replay`: the closed packet plus exactly authorized artifacts and a replay manifest.

The bundle must exclude predecessor proofs, project state, memory, unrelated artifacts, credentials,
and work/checkpoint paths. Verify every bundled byte against its manifest before review.

A follow-up bundle may answer an evidence-access request by adding exact authorized bytes. It must
not convert a mathematical, typing, scope, or source-mismatch rejection into correctness for the
same submission.

## Scheduling and safety separation

The staged experiments support exact artifact binding and replay: the copied first-round F2 program
reproduced its frozen output byte-for-byte. They do not support mandatory experiment manifests for
every computation. Default to ordinary frozen artifacts for a single-stage non-resumable run.
Multi-stage or resume-required structure makes the experiment layer mandatory; estimate magnitude
does not. Algorithm choice follows mathematical correctness and capability requirements, never an
estimated budget, duration, cost, or burden.
