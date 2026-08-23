# Chalxius v0.8.11 — Agent Judgment Integrity

Chalxius 0.8.11 makes Main's judgment—not ceremony—the control surface for
research selection, worker recovery, and supervision. It also publishes the
named-frontier work prepared in the unpublished 0.8.10 tree. The result is a
smaller operational spine: agents can act directly on exact graph objects,
while mathematical and source-correctness boundaries remain explicit.

The truth path is unchanged:

**Research → Candidate Release → Certification Decision → Gateway admission → Fact**

## What changed

### Main actively chooses the Research boundary

- Main chooses a named Campaign, object, or proposition before freezing work.
- It performs an exact Research lookup and completion projection for that
  selection, so an already-produced or safely closed node is not redispatched
  merely because a broad frontier listing is stale.
- Frontier output remains a bounded selection surface. It does not mechanically
  expand coverage or replace direct graph access.
- The graph remains fully operable through exact identifiers; no compatibility
  layer, cache, scheduler, or additional lifecycle gate was introduced.

### Worker recovery uses evidence visible to Main

- Artifact silence, one quiet wait, elapsed time, context compaction, bounded
  startup reading, and deep reasoning are not by themselves evidence that a
  worker was lost.
- Main consults current host status, worker messages, explicit tool errors, and
  round bytes before deciding what happened.
- A live worker that repeatedly produces no useful progress may be reclaimed as
  unproductive. Loss or reassignment requires an explicit failure signal or
  sustained total nonresponse corroborated beyond artifact silence.
- This is an instruction-level judgment rule. It adds no timer, watcher,
  heartbeat, receipt requirement, recovery state, or liveness schema.

### Copy-on-write supervision is fresh and complete

- Every copy-on-write successor is reviewed as a new complete product within
  each assigned proof, source, program, or integration scope.
- Prior defects and repair obligations are mandatory attack seeds, but never a
  defect allowlist.
- Supervisors may find inherited, new, repair-induced, and cross-component
  defects. PHX removes redundant procedure; it never narrows correctness or
  source scrutiny.

### Public architecture now matches the runtime

README, architecture, use cases, deployment text, limitations, worker
bootstraps, and release traceability now agree on current ownership:

- Main schedules and ingests; workers produce and independently supervise.
- Certification records decisions; Gateway owns Fact admission.
- The prospective Pulse path is retired from current operation.
- Global installation repairs are integrated repairs directly, not tactical
  repairs preceded by synthetic project-local ceremony.
- Background reading is indexed and task-bounded rather than universally
  front-loaded.

## PHX boundary

This release removes fragile procedural assumptions and leaves agents room to
recover from ordinary mistakes. It does not weaken exact source identity,
applicable supervision, Candidate adversity, fresh verification, Certification,
Gateway admission, revocation, or mathematical correctness.

No compatibility adapter, migration layer, daemon, automatic dispatcher,
timer, watcher, heartbeat, receipt gate, or new truth gate was added.

## Validation

The frozen 261-entry manifest passed:

- the complete suite: 987 tests in 78.480 seconds, with 2 skipped;
- the full forensic mutation matrix: 134/134 targets found and 134/134 mutants
  killed;
- the 42-feature behavioral gate with 0 orphans;
- strict candidate, installed, and cold-archive architecture reconnaissance
  with 0 errors and 0 warnings;
- the final exact-manifest routine matrix: self-test PASS, changed-surface
  29/29 PASS, and semantic mutants 16/16 killed;
- exact candidate-to-installed comparison across all 262 package files;
- deterministic double archive construction and cold manifest, self-test,
  architecture, and source-tree verification;
- public CHX disclosure against the exact closed historical ledger chain.

All isolated validation lanes left the candidate source unchanged. These are
software and workflow checks; they do not certify a mathematical claim.

## Installation

The validated tree is installed globally as 0.8.11 through the project-free
local path.

| Item | SHA-256 or value |
|---|---|
| Manifest | `114555be38fa461c68cc3b699bf7e63bb26857ebcf7317bbf881114d768546d0` |
| Runtime content | `de1d4a03ef94c0e47ed994b75493cc74504664fc4054a1d8c6809a0e2a4ebba9` |
| Installed runtime identity | `27ec3fa853fda91393a471e4920aed1f57a52987989927111e8954e00980b694` |
| Installed archive-tree identity | `c2c9e3e9febcf3de50621181311f34138057147220ad3951a14bee92d347cde5` |
| Direct rollback | 0.8.10 content `50ff63f2ba0c7bc5760337dd70b22ffab2591ae45ee44670c73b282a846bed2c` |
| Install elapsed | 3.4 seconds |

Installation read and wrote no research project and required no restart.

## Global CHX settlement

The installed-root successor
`global-repair-adc53add43febe72e78cae0f88c3b728b0992b93e25a2852fe7d3aba42a75a4f`
covers all 166 observed qualified issues:

- 160 resolved;
- 6 excluded as nonarchitectural;
- 0 unresolved or uncovered;
- 0 active open issues;
- 0 lineage errors or report drift.

Its canonical `record_sha256` is
`2b2c1b52a1503846c2044dafd858683556548956094f4971a36ee7f8a5cdb68c`;
the complete record file SHA-256 is
`cb6806351a6a99b09ed7bf718aa999d78b338208575fce8f1fd38a2d1465865f`.

The current task ledger is closed. It contains zero tactical and zero
per-ledger integrated repairs; the global installation is represented directly
by the global integrated successor. Historical ledger bytes were not rewritten,
and historical task-state flags own no active issue.

## Public distribution

Release assets:

- `chalxius-0.8.11-agent-judgment-integrity.tar.gz`
- `chalxius-0.8.11-agent-judgment-integrity.tar.gz.sha256`

The canonical archive contains 262 regular files and no synthetic directory
members. It is 2,572,660 bytes and has SHA-256
`b81fcbd25823a15d61a0653eae666da342fd76d28158d1d3a0fdf0f51813774c`.

Verify it with:

```sh
shasum -a 256 -c chalxius-0.8.11-agent-judgment-integrity.tar.gz.sha256
tar -xzf chalxius-0.8.11-agent-judgment-integrity.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

This architecture release created no Candidate Release, Certification
Decision, Gateway admission, or Fact.
