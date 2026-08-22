# CHX runtime architecture ledger

This contract is mandatory for every Chalxius run started after the 0.4.1
activation boundary. It creates one task-scoped, append-only account of
problems caused by the Chalxius architecture or materially amplified by it.
The ledger is host operational evidence only: `truth_effect=none` and
`project_effect=none`.

## Compatibility boundary

For 0.8.0, compatibility is semantic rather than procedural. Future releases
may replace runtime layouts, adapters, migration ceremonies, and administrative
gates without preserving those old protocols. A current or legacy graph remains
operable when its node/edge hashes, dependencies, provenance, workflow stage,
and owner boundaries can be interpreted. Runtime identity and archive paths are
diagnostic provenance only; they cannot gate CHX startup, graph reads, Research
continuation, or graph writes. The remaining paragraphs preserve the historical
ledger-revision rules and must not be read as a runtime-compatibility mandate.

The rule applies prospectively to runs started after the 0.4.1 activation boundary.
Runs already underway under 0.4.0 must not be backfilled, migrated, reopened, or
reclassified. A missing CHX runtime ledger on such a run is
never an audit warning, certification blocker, or reason to redo work. Loading some 0.4.1-or-later bytes while an
older run continues does not change that run's original contract or status.
Ledger revisions 1, 2, 3, and 4 remain byte-exact readable and retain their
original append semantics. Revision 3 added a
finding gate, typed issue relationships, direct successor lineage, and
deterministic architecture-report verification. Revision 4 is prospective for
newly started runs and additionally freezes the complete digest-bound
transitive predecessor chain. It preserves issue numbering and typed relations
across multiple generations and issue-free intermediate ledgers; it never
rewrites an older ledger. Revision 5 is prospective for newly started runs. It
retains revision 4 lineage and adds the reconnaissance, reusable tactical
repair, and integrated-repair gates described below. It never projects those
requirements back onto revisions 1 through 4.

Project-bound runs store their ledger at `PROJECT/chx-ledgers/`.
Projectless runs use private host task state outside the skill. The project-local directory
is only an operational container: it is not Paper, Audit, Blackboard, Research,
Certification, Fact, Reader, or Learning data, is ignored by project audit and
admission, and must never be used as mathematical evidence. In
`project_effect=none`, “effect” means project status or authority; the visible
ledger file is the sole intended filesystem effect.

## Start one ledger before substantive work

After reading the governing references and before substantive analysis, tool
execution, or project writes, start exactly one ledger for the host task:

```bash
SKILL_ROOT=/absolute/path/to/chalxius
HOST_TASK_STATE=/absolute/private/host-task-state/chalxius-chx-ledgers
PROJECT=/absolute/path/to/chalxius-project

python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" start \
  --project-root "$PROJECT" \
  --task "bounded description of this Chalxius run" \
  --host-task-scope-id "host task or thread id when available"
```

For a run with no project, use the external fallback instead:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" start \
  --root "$HOST_TASK_STATE" \
  --task "bounded description of this projectless Chalxius run" \
  --host-task-scope-id "host task or thread id when available"
```

Keep the returned `ledger_path` for the whole run. Exactly one of
`--project-root` and `--root` is required. Failure to start the ledger is a
host-procedure blocker: do not claim a compliant 0.4.1 run, and disclose the
failure in the final response.

For a newly frozen worker card, invoke the `chx_ledger.py` located under the
available skill root and add `--task-card /exact/card.json`. Startup validates
the card semantic hash and owner-bound workflow fields before creating a
ledger. Any `runtime_binding` field is retained only as diagnostic provenance;
its absence, relocation, or version drift is not a CHX startup failure.
For current revision-5 worker ledgers, the start event also stores the exact
round id, assignment id, task-card file SHA-256, and task-card semantic SHA-256.
The field is optional for existing revision-5 ledgers, so no historical bytes or
contract revision are rewritten. When Main later ingests the matching return, a
closed card-bound ledger contributes only its genuine `finding_observed` events
to a small content-addressed `chx-observations/by-id/` projection. That inbox is
nontruth and pending coordination; it does not promote an issue, consult or
adopt PHX, alter project authority, or create Blackboard/Pulse state. A closed
ledger with no finding produces no observation object.
Historical cards and terminal rounds remain readable through their own frozen
content, receipts, and graph lineage. A missing archive or changed runtime may
reduce diagnostic detail, but it does not make a valid graph operation require
an upgrade, migration, or compatibility closure. Hash drift, missing
dependencies, malformed receipts, wrong-stage artifacts, and Fact-authority
violations still fail at their owning boundaries. Completion never requires an
artificial abort and never rewrites the frozen round.

## Record every discovery before classifying it

Revisions 3 and 4 first record every newly discovered candidate mechanism as a stable
content-derived `finding-*` id. This prevents a host from noticing a mechanism
and then silently omitting it because issue classification or the report is
performed later. The finding JSON contains exactly `classification`,
`mechanism_type`, `mechanism`, `trigger`, `observed_effect`,
`mathematical_effect`, `current_workaround`, `upgrade_requirement`, and
`audit_anchors`:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" finding \
  --ledger "$LEDGER_PATH" --input /absolute/path/to/finding.json
```

Before close, every finding must be reconciled in exactly one of three ways:

- `promoted_to_issue`: transactionally append the issue and reconciliation;
- `merged_with_reason`: bind it to an already recorded issue with a reason;
- `excluded_with_reason`: preserve why the causal test failed.

An unreconciled finding blocks close. `record` on a revision-3 or revision-4 ledger performs
finding creation, issue promotion, and reconciliation in one locked append. It
may receive `--relations-input` containing typed `related_to`, `extends`,
`discovered_from`, or `supersedes` links to existing issue ids. A late finding
after an immutable predecessor report belongs in a successor ledger, never in a
hand-edited report.

Promote an issue only when there is an auditable causal chain from a Chalxius
mechanism to the observed problem:

- `caused`: without the mechanism, the problem would not have occurred in the
  relevant run;
- `materially_amplified`: an independent problem existed, but the mechanism
  substantially increased its likelihood, scope, persistence, recovery cost, or
  risk to mathematical status.

Name the responsible mechanism type: `state_model`, `coupling`,
`automatic_trigger`, `validation_boundary`, `recovery_rule`,
`authority_boundary`, or `interface_contract`. Also record the mechanism,
trigger, observed effect, mathematical effect, workaround, upgrade requirement,
and at least one exact audit anchor.

Do not record ordinary mathematical mistakes, host/tool failures, malformed user
input, external-service failures, or implementation bugs that the architecture
neither caused nor materially amplified. If a suspected entry is later shown to
be nonarchitectural, append an `excluded_nonarchitectural` disposition; never
erase history. Mark an issue `resolved` only with reproducible regression evidence.

The CLI accepts an exact JSON object:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" record \
  --ledger "$LEDGER_PATH" --input /absolute/path/to/issue.json \
  --relations-input /absolute/path/to/relations.json

python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" dispose \
  --ledger "$LEDGER_PATH" --issue-id CHX-001 \
  --input /absolute/path/to/disposition.json
```

The disposition JSON contains exactly `status`, `reason`, and
`regression_evidence`. Use `status="resolved"` only with at least one
reproducible regression-evidence string; otherwise use
`status="excluded_nonarchitectural"` only after the causal test fails.

Each JSONL event is exact-schema, sequentially numbered, SHA-256 chained, locked,
flushed, and fail-closed on tampering. Never edit the file by hand.

## Gate revision-5 resolution through reconnaissance and coordinated repair

Revision 5 separates project-run repair from globally installed architectural
settlement. A tactical repair is only a bounded change made and retained inside
one project run. Do not postpone that in-scope task merely to design the entire
future architecture, and do not require the full high-cost reliability matrix
when focused evidence is sufficient. The tactical record preserves the local
mechanism, applicability, implementation, boundaries, and bounded evidence so
the project-stage integration can evaluate it. A change intended for global
Chalxius installation is integrated repair from the outset and must not acquire
synthetic tactical records as procedural prerequisites.

A tactical repair is **not** a resolved disposition. It is provisional
implementation evidence and may later be retained, generalized, narrowed,
replaced by an existing mechanism, or deprecated. The issue stays open until a
subsequent integrated repair coordinates it with every other resolved issue and
the disposition carries reproducible regression evidence. This prevents a
locally successful patch from becoming an unexamined permanent architecture.

At the task-stage boundary, review the complete CHX issue set, all tactical
repairs, and the existing reusable-mechanism registry. The integrated repair
must address interaction, duplicated mechanisms, lifecycle reachability,
authority boundaries, migration and rollback implications, and the choice to
retain, adapt, replace, or remove each tactical mechanism. It is the coordinated
settlement for that stage, not a concatenation of tactical summaries.

For every performance- or administrative-cost-related CHX issue, consult the
global PHX architecture-route guide in
[`phx_architecture_routes.md`](phx_architecture_routes.md) before selecting a
repair mechanism and persist the hash-bound search receipt. Reuse, refine, or extend a matching route rather than silently
creating another wheel. Name the consulted qualified PHX route ids in an
available tactical summary or integration rationale together with the search
receipt path and SHA-256; if none applies, cite the receipt's hash-bound empty
result and record a new global route only when the lesson is genuinely
reusable. The concrete problem and its resolution remain in CHX. PHX supplies
nontruth route guidance and never substitutes for the CHX repair gates. A
significant global architecture change identified through PHX still requires a
recorded user consultation and decision before implementation.

For the project-run-local per-ledger route described in this section, first run the complete
architecture reconnaissance over the Chalxius candidate tree and write its
JSON report outside that tree. Then record the report before any tactical
repair event:

```bash
python3 -B "$SKILL_ROOT/scripts/architecture_reconnaissance.py" \
  --root "$SKILL_ROOT" --output /absolute/path/to/reconnaissance.json --quiet
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" record-reconnaissance \
  --ledger "$LEDGER_PATH" --input /absolute/path/to/reconnaissance.json
```

The receipt requires the exact full-report schema, canonical candidate root,
candidate version, file count, capability-registry hash,
behavioral-feature-registry hash, and the scanner's content-derived
`inventory_sha256`. A pre-repair report may contain errors or warnings: the
receipt proves that the complete topology was inspected before the repair; it
does not assert that the inspected tree was already clean. Recording consumes
only a report whose canonical root and version match the ledger runtime. It
does not rerun the administrative scan during later status,
disposition, or close operations.

Next record exactly one reusable tactical repair for each issue whose repair
will remain in this project run and be resolved through the per-ledger route:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" record-tactical-repair \
  --ledger "$LEDGER_PATH" --issue-id CHX-001 \
  --reconnaissance-id reconnaissance-<sha256> \
  --input /absolute/path/to/tactical-repair.json
```

The tactical JSON contains exactly `mechanism_id`, `summary`, `applicability`,
`implementation`, `fail_closed_boundary`, sorted `reusable_domains`, sorted
`implementation_anchors`, and sorted `bounded_validation_evidence`. The
content-derived tactical id binds the issue to a previously recorded full-tree
receipt. A tactical repair cannot be recorded after that issue's disposition,
and a second tactical record for the same issue is rejected.

After the scoped repairs are implemented, record their coordinated integration:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" record-integrated-repair \
  --ledger "$LEDGER_PATH" --input /absolute/path/to/integrated-repair.json
```

The integrated JSON contains exactly sorted `included_issue_ids`, canonical
`coordination_decisions`, sorted `risk_evidence`, and sorted
`regression_evidence`. Every coordination decision has exactly `decision_id`,
sorted `affected_issue_ids`, `decision`, and `rationale`; together the
decisions must cover every included issue. The ledger derives an immutable
reusable-mechanism registry from the included tactical records, groups
consistent mechanism definitions with their issue-specific bindings, embeds
the registry, and binds its SHA-256 in the integrated event. The event also
binds the complete tactical closure and the preceding integrated-repair id.

A project-local per-ledger `resolved` disposition is appendable only when its tactical repair has a
prior reconnaissance receipt, the latest integrated repair covers the target
and every already resolved issue, and the disposition's regression evidence is
included in that integrated repair. An issue classified
`excluded_nonarchitectural` does not require repair records. If a late issue is
discovered in that project-local route, append it normally, record its tactical repair, and append a new
integrated repair that supersedes the earlier one and again covers every
already resolved issue. Close rechecks that the latest integration covers all
resolved issues. A globally installed repair instead uses the direct
cross-ledger global integrated route below and creates no tactical precursor.
All repair layers remain `truth_effect=none` and have no
Paper, Research, Candidate, Certification, Gateway, or Fact authority.

## Gate public release disclosure

Before packaging or publishing a Chalxius release, compare the exact private
release ledger with the machine-readable `chx_public_disclosure` contract in
`INHERITANCE.lock.json`:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" verify-public-disclosure \
  --ledger "$LEDGER_PATH" --skill-root "$SKILL_ROOT"
```

The gate walks the exact closed private predecessor chain from the supplied
current ledger and compares it with an ordered public lineage of run ids,
ledger digests, contract revisions, predecessor links, and per-run issue
ownership. It requires every included issue in every contributing ledger to be
publication-resolved, every finding to be reconciled, non-overlapping and
contiguous issue ownership, and
`KNOWN_LIMITATIONS.md` plus release traceability to contain their declared
enumeration and semantic markers. It returns hashes and the current ledger
event head. It does not copy the private ledger or research content into the
release and has `truth_effect=none`.

Direct `resolved` status is publication-resolved. An unresolved immutable
predecessor is also publication-resolved only when exactly one strictly later
issue carries an explicit `supersedes` relation to it and that successor is
itself publication-resolved. Missing, backward, cyclic, ambiguous, unresolved,
or non-superseding relations fail closed. This permits append-only repair
succession without allowing a later issue to erase or rewrite predecessor
history.

## Inventory all task-scoped ledgers before integrated repair

`CHX-001` is local to one predecessor chain. Never report a bare issue id as a
project-global identity; use `RUN_ID/CHX-NNN`. Before a stage-wide repair or a
claim that all known CHX issues are closed, run the read-only project inventory:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" inventory \
  --project-root "$PROJECT"
```

The inventory validates every project-local JSONL event chain, reconstructs
each predecessor lineage, and distinguishes direct resolution, resolution by a
unique final `supersedes` successor, active open issues, closed orphan issues,
and pending successor chains. It also reports historical architecture-report
renderer drift separately from ledger validity. The command never closes,
disposes, rewrites, repairs, or otherwise mutates a ledger, report, or project
artifact. A closed ledger with an open issue remains visible until exact
successor or disposition evidence exists.

Only a genuinely later ledger's `resolved` issue may discharge a predecessor
through `supersedes`. A same-ledger relation and a successor later classified
`excluded_nonarchitectural` are retained as ignored relationship evidence and
have no repair effect. Missing or external predecessors, cycles, malformed
edges are lineage errors. Open parallel successor subtrees remain ordinary
exact ledger/chain snapshots rather than blocking unrelated cleanup. Fully
closed parallel successor subtrees also receive the compact closed-subtree
projection; if two branches offer competing `supersedes` successors for one
earlier issue, global repair still fails closed.

The default projection is bounded to counts, active run ids, unresolved issues,
lineage errors, and report compatibility drift. Use `--full` only when the
complete validated ledger and predecessor-chain inventory is required.

### Cross-ledger integrated repair for global installation or historical settlement

The per-ledger tactical route is only for a repair that remains inside its
project run. When a repair is intended for global Chalxius installation, or the
user requests a full historical settlement across immutable ledgers, validate
the complete inventory and record one copy-on-write global integrated repair.
Do not append synthetic tactical records to current or old task ledgers:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" record-global-repair \
  --project-root "$PROJECT" --input /absolute/path/to/global-repair.json
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" verify-global-repair \
  --project-root "$PROJECT"
```

The revision-3 input names the exact candidate root, version, manifest SHA-256,
full pre-repair inventory SHA-256, a `covered_issue_snapshot_sha256` binding
each covered issue to its owning ledger bytes, every observed `RUN_ID/CHX-NNN`,
one disposition per issue, disjoint mechanism groups covering all issues, risk
evidence, regression evidence, and the latest global-repair predecessor id.
Regression evidence must use digest-bound `project:` receipts; candidate files
are implementation anchors only. The writer is serialized, an exact concurrent
retry is idempotent, and every record is content-addressed under
`PROJECT/chx-ledgers/global-repairs/`. Unexpected files, symlinks, multiple
terminals, orphan predecessors, covered-ledger drift, candidate-manifest drift,
inventory drift at record time, or incomplete issue coverage fail closed.

The inventory is an exact current snapshot, not a liveness census. Open ledgers
may be included because an open flag does not prove that a task is active and
does not grant it veto power over unrelated cleanup. Every already observed
qualified issue, including one in an open or abandoned ledger, must receive an
exact disposition. Predecessor lineage must be complete, competing
cross-branch `supersedes` successors remain invalid, and every applicable
historical report projection must be readable. Project-bound ledger creation
shares the global-repair writer lock, and the writer revalidates the complete
inventory immediately before the final copy-on-write record. Candidate
validation verifies every manifest entry and the exact candidate file set, not
merely the `MANIFEST.sha256` identity file.

Every implementation anchor and risk, regression, group, or issue evidence
entry is a digest-bound file reference of the form
`candidate:relative/path#sha256=DIGEST` or
`project:relative/path#sha256=DIGEST`. Implementation anchors must use the
candidate root. Issue evidence must be included in its mechanism-group evidence,
and group evidence must be included in the global regression evidence. A
`historical_nonarchitectural` basis is valid only for an
`excluded_nonarchitectural` disposition; every repair or revalidation basis is
valid only for `resolved`.

The latest valid global repair projects its dispositions over unresolved
inventory rows without changing any historical JSONL event or deterministic
architecture report. A later valid zero-issue ledger does not stale the
projection, and a later issue in a new ledger remains unresolved with an
explicit uncovered count. If a covered open ledger is later appended or
closed, its bound bytes change and the old projection becomes `stale`; the new
bytes remain visible and require a successor snapshot. Candidate drift,
covered-ledger drift, lineage/report drift, or a changed global-repair record
also makes the projection `stale`; create a complete successor global repair
rather than editing or deleting the old record. This path is nontruth
architecture accounting only and does not bypass Research, Candidate,
verifier, Certification, Gateway, or Fact requirements.

## Immutable successors and deterministic reports

After a predecessor ledger is closed, start a revision-4 successor when later
work discovers a related mechanism:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" start \
  --project-root "$PROJECT" --task "successor architecture work" \
  --predecessor-ledger "$CLOSED_LEDGER" \
  --inherited-finding /absolute/path/to/late-finding.json
```

The successor reads the chain once, rejects missing, mutable, cyclic, or
digest-mismatched predecessors, then binds the direct predecessor path/hash and
the ordered transitive run/digest/contract/issue lineage. Inherited findings
remain visible and must be reconciled. Routine status does not rescan this
chain. This is append-only lineage, not permission to reopen or modify a
predecessor.

After close, render and independently verify the deterministic architecture
report:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" report \
  --ledger "$LEDGER_PATH" --output /absolute/path/to/CHX_REPORT.md
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" verify-report \
  --ledger "$LEDGER_PATH" --report /absolute/path/to/CHX_REPORT.md
```

The close event binds the report semantic hash, finding reconciliation,
issue relationships, and included/excluded sets. Rendering order and content
are derived from ledger bytes, so architecture reporting cannot drift from the
accounting state.

## Close and condition final feedback

Close the ledger after all applicable project audits and immediately before the
final response:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" close --ledger "$LEDGER_PATH"
```

The close result is authoritative for host feedback:

- Revision-3, revision-4, and revision-5 close must already contain the exact verified
  `architecture_report` projection. The first close, an idempotent later close,
  and `status` expose the same durable projection; hosts need no hidden second
  read to discover the report.
- If `report_required=true`, report every included issue's run/issue id, causal
  mechanism, effect, disposition, and ledger path. Keep its nontruth and
  no-project-effect status explicit.
- If `report_required=false`, say nothing about the CHX ledger. Do not emit a
  success badge, empty-ledger notice, path, or zero count.
- If validation or close fails, disclose that failure because silent conditional
  feedback cannot be established.

Closing is idempotent. An excluded nonarchitectural suspicion does not make
feedback reportable; an open or regression-resolved qualifying issue does.
