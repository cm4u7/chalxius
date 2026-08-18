# Administrative cost playbook

This playbook is the performance-and-cost companion to the global
[`phx_architecture_routes.md`](phx_architecture_routes.md) contract. The table
below is a prospective source of candidates and measurement questions; the PHX
ledger is the durable cross-project record for a reusable route, its relations,
measurements, user consultation, and any eventual adoption.

Performance problems remain in CHX. PHX records the architecture route distilled
from them and must not duplicate their issue accounting. An entry here or in
PHX is not a defect, a CHX issue, a performance promise, proof that a route is
beneficial, or permission to weaken a required validator. When measurement
exposes an architecture-caused or architecture-amplified failure, record that
finding in the current CHX ledger before treating it as repaired. Consult PHX
before selecting the repair mechanism and persist the search receipt so CHX can
bind the exact query, ledger heads, selected routes, or no-match result. Recording a route does not authorize its
implementation; a significant architecture adoption requires a recorded user
consultation and decision under the PHX contract.

The primary operating hazard is an agent issuing a needlessly broad command,
retrying an unchanged operation, or reaching the same immutable closure through
several public readers. This playbook does not optimize substantive research,
proof, computation, source reading, or independent verification, and it does
not assume a hostile external attacker.

## Measurement and decision protocol

1. Identify the exact public command, project snapshot, runtime identity, and
   requested projection. Separate administrative time from substantive worker
   or computation time.
2. Take one bounded timing or profile. Do not create an index, parallel worker
   pool, or durable cache merely to learn where the time went.
3. Attribute repeated work by semantic object and validation boundary, not just
   by function-call count. Confirm whether the repeated reads use identical
   immutable bytes in one owning command.
4. Prefer, in order: remove inapplicable work; narrow the default projection;
   validate one canonical collection and derive views; reuse a successful
   command-local projection; then measure again.
5. Consider persistent indexing only for a demonstrated repeated
   cross-command workload with an explicit identity, invalidation, rebuild,
   corruption, recovery, and nonauthority contract. Consider parallelism only
   for genuinely independent remaining work.
6. Preserve first-access exact validation, drift detection, full explicit audit,
   release-lane isolation, final cutover rechecks, and every Research, Paper,
   Candidate, Certification, Gateway, Evidence, and Fact authority boundary.
7. Stop when the administrative path is comfortably operational. The one-to-
   two-minute target, with uncommon explained cases near four minutes, is
   guidance rather than a mandate to keep optimizing a path already measured in
   seconds.

## Prospective measurement routes

| Surface | Measure when | First measurements | Candidate mechanism if confirmed | Boundary that must remain |
|---|---|---|---|---|
| Blackboard aggregate audit | receipts, markers, task cards, snapshots, or edges make audit dominant | validated-object counts, repeated receipt/round/card reads, per-edge cycle checks, index reconstruction time | build one command-local object and assignment inventory; validate each immutable record once; perform cycle detection by edge family; derive the Reader/index projection from that inventory | full receipt, marker, snapshot, edge, and cycle validation; no persistent authority |
| Parallel Verification audit | many plans, packets, receipts, or aggregates repeat registry and head validation | deep-validation count by immutable identity; key-registry, nonce, plan-head, packet, and aggregate time | freeze one command-local key/nonce/head map and deep-validate each exact immutable object once; reject read-set drift at command end | signature, nonce, head, packet, aggregate, and freshness checks remain exact |
| Paper Evidence Library | catalog or verify repeatedly reloads collections or rebuilds SQLite | collection reads, per-paper version scans, repeated evidence-state calculation, SQLite rebuild time | construct one `LibraryReadSnapshot`, group objects once, hash each object once, and rebuild the nonauthority SQLite index only after source-state change | PDFs, versions, corrections, bridges, source state, and content hashes remain fully verified; SQLite never becomes authority |
| Research Draft audit | authorization, plan, and batch deep reads repeatedly reopen the same Paper and source objects | deep-object validation count keyed by path, content hash, runtime, and mode | command-local deep-object cache keyed by every semantic identity and validation mode | proposition-total coverage, authorization, stance/target continuity, source bytes, and Paper topology remain fail-closed |
| Mode, Pulse, and Experiment summaries | aggregate audit repeats round status, mode events, aborts, commitments, or experiment ledgers | repeated round-status and runtime validations; event-log passes; absent-subsystem counts | share the owning inspection context; prebuild command-local event/abort/receipt maps; apply optional-state gates before subsystem-specific deep validation | active-mode, abort, commitment, task-card, ledger, and hard-cap validation remains exact |
| Reader export | Reader first scans every plane and later runs another complete audit | per-plane reads before and during audit; duplicate Paper/Fact/Research/Release/Decision validation | run the required audit first and render from its validated command-local projections | Reader remains deterministic nontruth output and cannot substitute for audit or Fact authority |
| Architecture reconnaissance | file bytes, hashes, and ASTs are reread by inventory, topology, behavior, duplicate, and comparison passes | reads and hashes per candidate path; AST parses per Python file | create one immutable candidate-file snapshot and derive hashes, ASTs, registries, duplicate checks, and reports from it | exact tree drift and manifest mismatch remain observable; reconnaissance is not reliability proof |
| Release validation setup | routine validation pays for forensic lanes or duplicates a check already performed inside the semantic audit | bytes and time copied per selected lane; repeated target preflight; changed-surface versus whole-suite duration | keep routine validation to self-test, explicit changed-surface tests, and the semantic audit; materialize full-suite, behavioral, reconnaissance, and full-registry lanes only under explicit forensic scope | every executed lane remains an exact manifest-bound copy; manifest identity, source nonmutation, semantic probes, and the selected routine or forensic lane set remain exact |
| CHX ledger history | append/status/report time becomes dominated by validating a long immutable prefix | event count, full-prefix validation time, number of repeated operations on one unchanged head | only after measurement, consider a nonauthority head checkpoint bound to the exact prefix and always verify the new suffix plus final head | append-only history, event hashes, predecessor lineage, close/report parity, and public disclosure remain exact; high-risk route |
| Runtime cutover snapshots | the same exact candidate or project tree is rehashed several times inside one cutover boundary | full-tree snapshot count and time; distinguish necessary pre/post TOCTOU checks from identical intermediate reads | merge only redundant snapshots inside one sealed operation and retain the final drift check | manifest-only copy, pre/post project identity, rollback, archive validation, and final TOCTOU protection remain mandatory; high-risk route |

## Current measured mechanisms

CHX-100 through CHX-109 already establish nine reusable mechanisms:

- explicit separation of routine monitoring from forensic audit;
- one ephemeral inspection context across the complete aggregate and all nested
  subaudits;
- applicability before expensive authority expansion;
- one canonical immutable collection validation before partition projection;
- an exact optional-subsystem state gate before subsystem-specific validation;
- canonical applicability derived from validated frozen ownership rather than
  unvalidated path bytes;
- one project-owned shared snapshot lock across aggregate reads and ordinary
  writer commits.
- real parser-to-handler option ownership for standalone public commands;
- complete validated owner-view construction before the first present optional-
  subsystem state read, while exact absence remains bounded.

On one protected philosophy-project canary, their coordinated descendants
reduced the complete audit from an interrupted run beyond seven minutes to a
successful approximately six-second run. That observation motivates the ordering in this
playbook but does not establish a universal benchmark or pre-approve any route
above.

Every route is domain-general where its object model applies. Philosophy,
mathematics, empirical research, mixed research, and software release may have
different substantive targets, but none benefits from repeating an identical
administrative validation without a semantic reason.
