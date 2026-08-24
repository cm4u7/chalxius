# Chalxius v0.8.12 — Semantic Recovery

Chalxius 0.8.12 makes the Research frontier follow exact, validated
copy-on-write repair semantics. A clean successor can close the original named
work only when its lineage, repair objective, active invalidator, obligations,
production, and applicable supervision all agree. Ambiguity or later contrary
evidence leaves the work pending.

The release also sharpens Main's lightweight operating rules for semantic
selection, useful parallel work, and client-network recovery. These are agent
judgment rules, not new gates or background machinery.

The truth path is unchanged:

**Research → Candidate Release → Certification Decision → Gateway admission → Fact**

## What changed

### Exact copy-on-write frontier recovery

- Main projects a completed copy-on-write chain back to the original Research
  identity instead of redispatching the repaired objective under its old name.
- A valid repair must name one exact parent Research and product, bind the
  repair specification by hash, preserve campaign and dependencies, and
  exhaust the active invalidator it claims to repair.
- The terminal product must be non-adverse, complete its frozen obligations,
  and have complete applicable supervision.
- A second unhandled invalidator, ambiguous successor branch, drifted repair
  specification, unsafe product, incomplete round, or COW cycle keeps the
  original work pending.
- Distinct non-aborted products for one Research remain ambiguous. Byte-identical
  retry publication of the same product is tolerated.

### Main retains the broad semantic view

- Main owns exact cross-round Research search, COW lineage reconstruction,
  completion projection, duplicate exclusion, and final dispatch selection.
- A worker may gather bounded evidence, but its scout recommendation is not the
  authority for `DISPATCH` or `NO-DISPATCH`.
- After dispatch or return, Main checks visible free slots and may keep a second
  worker active when a real, independent, nonduplicative, high-value target
  exists. This is not a quota and does not justify filler work.

### Reconnect is transport state, not work loss

- A client banner such as `Reconnecting... waiting for network` says nothing by
  itself about worker or round liveness.
- After reconnect, Main checks live agents, canonical return bytes, ingestion,
  and round state, reports any completion missed by the UI interruption, and
  resumes from durable state.
- Main does not reclaim a live worker or duplicate a round solely because the
  client transport reconnected.

These rules complement the 0.8.11 rule that artifact silence or context
compaction alone does not establish worker loss.

## PHX boundary

This release adds no compatibility layer, migration adapter, daemon, automatic
dispatcher, scheduler, timer, watcher, heartbeat, receipt gate, slot quota,
reconnect gate, lifecycle state, or truth gate. It keeps exact mathematical and
source-correctness protection while reducing places where an agent can confuse
procedure with state.

## Validation

The frozen 262-entry manifest passed:

- the complete suite: 995 tests in 78.691 seconds, with 2 skipped;
- the forensic release matrix: 139/139 mutants killed, 42 behavioral features,
  and strict architecture reconnaissance with 0 errors and 0 warnings;
- the final routine matrix: self-test PASS, 36 changed-surface tests PASS, and
  21/21 semantic mutants killed;
- exact candidate-to-installed comparison across all 263 package files;
- deterministic double archive construction and cold manifest, self-test,
  architecture, and source-tree verification.

All validation lanes left the candidate source unchanged. These are software
and workflow checks; they do not certify a mathematical claim.

## Installation

The validated tree is installed globally as 0.8.12 through the project-free
local path.

| Item | SHA-256 or value |
|---|---|
| Manifest | `e47bdaeac15cfa1381264b04c9854fb99905a0dd2b863c6bb038f01841c82e77` |
| Runtime content | `ffb00b70da8035ff7939aef3a8050dbcd41492249398ac7a2fc3f4f6de233c03` |
| Installed runtime identity | `c0cdc2075fb6ac5a1b2d6c92da20a47dfdd37e806d47ec05b65d28ef968ca379` |
| Installed archive-tree identity | `d1250a57b007308853574ef6f7d5f1c91435754d4e31f1cf3ca68d092e9a675e` |
| Direct rollback | 0.8.11 content `de1d4a03ef94c0e47ed994b75493cc74504664fc4054a1d8c6809a0e2a4ebba9` |

Installation read and wrote no research project and required no restart.

## Global CHX settlement

The installed-root successor
`global-repair-c82951c65fad6ec03d324b330345ee770787ca504413dd3855ed49f4a99d02ed`
covers all 170 observed qualified issues:

- 164 resolved;
- 6 excluded as nonarchitectural;
- 0 unresolved or uncovered;
- 0 active open issues;
- 0 lineage errors or report drift.

Its canonical `record_sha256` is
`d2ba32cb5d0d977f2cfdadee2ebe2d7363cf6544ab313d536d6d8409abc02e0b`;
the complete record-file SHA-256 is
`b81f0a80d344fa4266245ef0ad7fc95260813d4a98532129e8f6915932b0ed69`.

The current task ledger is closed. It contains zero tactical and zero
per-ledger integrated repairs; the global installation is represented directly
by the global integrated successor. Historical ledger bytes were not rewritten,
and abandoned task-state flags own no active issue.

## Public distribution

Release assets:

- `chalxius-0.8.12-semantic-recovery.tar.gz`
- `chalxius-0.8.12-semantic-recovery.tar.gz.sha256`

The canonical archive contains 263 regular files and no synthetic directory
members. It is 2,581,988 bytes and has SHA-256
`8e93c0d6fb165c6c8e38a3925a17b6051dd0d05be9842307bf77db2a9773142a`.

Verify it with:

```sh
shasum -a 256 -c chalxius-0.8.12-semantic-recovery.tar.gz.sha256
tar -xzf chalxius-0.8.12-semantic-recovery.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

This architecture release created no Candidate Release, Certification
Decision, Gateway admission, or Fact.
