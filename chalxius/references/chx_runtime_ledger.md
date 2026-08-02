# CHX runtime architecture ledger

This contract is mandatory for every Chalxius run started after the 0.4.1
activation boundary. It creates one task-scoped, append-only account of
problems caused by the Chalxius architecture or materially amplified by it.
The ledger is host operational evidence only: `truth_effect=none` and
`project_effect=none`.

## Compatibility boundary

The rule applies prospectively to runs started after the 0.4.1 activation boundary.
Runs already underway under 0.4.0 must not be backfilled, migrated, reopened, or
reclassified. A missing CHX runtime ledger on such a run is
never an audit warning, certification blocker, or reason to redo work. Loading some 0.4.1-or-later bytes while an
older run continues does not change that run's original contract or status.
Ledger revisions 1 and 2 remain byte-exact readable. Revision 3 is prospective
for newly started runs and adds a finding gate, typed issue relationships,
successor-ledger lineage, and deterministic architecture-report verification;
it never rewrites an older ledger.

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

For a newly frozen 0.4.4 worker card, invoke the `chx_ledger.py` located under
the candidate skill root bound by that card and add `--task-card /exact/card.json`.
Startup validates the card semantic hash, canonical skill-root identity,
expected `VERSION`, `MANIFEST.sha256` file hash, and every manifest-listed
runtime byte before it creates a ledger.
An older global Chalxius runtime must fail closed instead of starting a
wrong-version worker ledger. This is prospective: historical cards and running
0.4.0/0.4.3 work have no new field, warning, invalidation, or redo obligation.
When newer Chalxius bytes inspect a terminal round, status and audit verify the
card's exact frozen VERSION, manifest, and all manifest-listed bytes instead of
comparing it only to the caller's current runtime. If the mutable original root
has been replaced, schema-1 and schema-2 cards may resolve through the
host-managed archive outside skill discovery. Resolution requires both one
sealed exact-file-set content object and one immutable identity-registry record;
the task card cannot select the host trust root, and archived code is never
imported or executed. A terminal round is either joined
to a validated abort or has a complete assignment set whose ingestion receipts,
return bytes, Research records, and optional adverse/program-math side records
all validate. Missing or damaged receipts leave the round active or fail closed;
an active round, worker ledger, return path, experiment, Pulse, and every write
still require exact current-runtime equality. Missing, linked, writable,
extra, tampered, cross-device, or registry-mismatched archive data fails closed.
One successful scan may be shared only by identical identities inside the same
bounded phase; it is not an authority cache. Completion never requires an
artificial abort and never rewrites the frozen round.

## Record every discovery before classifying it

Revision 3 first records every newly discovered candidate mechanism as a stable
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

An unreconciled finding blocks close. `record` on a revision-3 ledger performs
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

## Gate public release disclosure

Before packaging or publishing a Chalxius release, compare the exact private
release ledger with the machine-readable `chx_public_disclosure` contract in
`INHERITANCE.lock.json`:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" verify-public-disclosure \
  --ledger "$LEDGER_PATH" --skill-root "$SKILL_ROOT"
```

The gate requires every current release-ledger issue to be resolved, every
finding to be reconciled, the ledger issue set to equal the public registry,
the complete public issue range to be contiguous, and
`KNOWN_LIMITATIONS.md` plus release traceability to contain their declared
enumeration and semantic markers. It returns hashes and the current ledger
event head. It does not copy the private ledger or research content into the
release and has `truth_effect=none`.

## Immutable successors and deterministic reports

After a predecessor ledger is closed, start a revision-3 successor when later
work discovers a related mechanism:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" start \
  --project-root "$PROJECT" --task "successor architecture work" \
  --predecessor-ledger "$CLOSED_LEDGER" \
  --inherited-finding /absolute/path/to/late-finding.json
```

The successor binds the predecessor path, exact SHA-256, and prior issue ids.
Inherited findings remain visible and must be reconciled. This is append-only
lineage, not permission to reopen or modify the predecessor.

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

- Revision-3 close must already contain the exact verified
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
