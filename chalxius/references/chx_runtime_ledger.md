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
expected `VERSION`, and `MANIFEST.sha256` file hash before it creates a ledger.
An older global Chalxius runtime must fail closed instead of starting a
wrong-version worker ledger. This is prospective: historical cards and running
0.4.0/0.4.3 work have no new field, warning, invalidation, or redo obligation.

## Record only architecture-caused or amplified problems

Record an issue only when there is an auditable causal chain from a Chalxius
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
  --ledger "$LEDGER_PATH" --input /absolute/path/to/issue.json

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

## Close and condition final feedback

Close the ledger after all applicable project audits and immediately before the
final response:

```bash
python3 -B "$SKILL_ROOT/scripts/chx_ledger.py" close --ledger "$LEDGER_PATH"
```

The close result is authoritative for host feedback:

- If `report_required=true`, report every included issue's run/issue id, causal
  mechanism, effect, disposition, and ledger path. Keep its nontruth and
  no-project-effect status explicit.
- If `report_required=false`, say nothing about the CHX ledger. Do not emit a
  success badge, empty-ledger notice, path, or zero count.
- If validation or close fails, disclose that failure because silent conditional
  feedback cannot be established.

Closing is idempotent. An excluded nonarchitectural suspicion does not make
feedback reportable; an open or regression-resolved qualifying issue does.
