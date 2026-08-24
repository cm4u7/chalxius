# Chalxius v0.9.0 — Frontier Active Fix

Chalxius 0.9.0 turns the ordinary Research frontier into a compact,
lifecycle-aware decision surface for Main and connects exact Campaign goals to
the work already present in the graph. The result is practical on a large
project: Main can see what has been produced, what is in flight, what needs
ingestion, supervision, repair, or semantic reconciliation, and then actively
choose the next load-bearing target.

The release does not add an automatic dispatcher, persistent frontier state,
compatibility layer, cache, watcher, scheduler, timer, receipt gate, or new
truth path.

## Active frontier

The default `mgraph frontier` projection now derives one of these actions from
existing immutable graph and round bytes:

- `production` — no usable product exists;
- `await_return` — a live assignment has not published its canonical return;
- `ingest_return` — return bytes exist but are not yet ingested;
- `supervision` — a current product needs the applicable second logical round;
- `repair` — the current product is invalidated;
- `main_reconciliation` — duplicate, historical, malformed, branching, or
  otherwise ambiguous evidence needs Main's semantic judgment;
- `none` — no workflow action remains for that item.

The default surface stays bounded and small. `--diagnostic` exposes additional
bounded forensic fields when Main is investigating a discrepancy. No frontier
label closes mathematics, dispatches a worker, or changes Candidate or Fact
authority.

## Campaign goals and workflow

A Campaign can now hold exact `research_goal` targets naming existing Research
roots in that same Campaign. These targets preserve non-procedural objectives
and derive:

- coverage and progress;
- the current workflow queue;
- an exact actionable Research id when one exists;
- orphan and Main-choice signals when the graph cannot decide semantically.

An explicitly selected Campaign scopes the projection. The ordinary active
Campaign is only an `active_hint`, never a hidden queue filter. Main still
compares the graph with the user's goal and its broader memory, performs a
bounded exact Research search when needed, and makes the final choice.

## Whole-graph performance defect fixed in the live project

The first real `research_goal` exercise exposed a coupling defect: synchronizing
a research-only target generated an empty Fact-target certificate only after
loading and validating the entire admitted Fact graph.

On the 1,288-Research local-F0 project this took about 294.5 seconds, sampled at
roughly 544 MiB physical memory with a 1.0 GiB peak, to emit a 250-byte empty
certificate. The target event itself had already been written, making a retry
look tempting even though it could duplicate work.

The final implementation walks only exact selected proof targets and their
transitive predecessors. An empty proof-target set reads zero Facts. Existing
ordering, hash, missing-predecessor, and Fact-validation failures remain
intact.

Measured on the same project:

| Probe | Before | Final 0.9.0 |
|---|---:|---:|
| Research-goal target synchronization | ~294.5 s | 3.23 s installed replay |
| Candidate idempotent replay | — | 2.39 s |
| Explicit-Campaign frontier | — | 2.263 s |
| Campaign event count after retry | 7 | 7 |

This is a 98.97% measured reduction on the candidate path, achieved without a
cache, index daemon, timeout gate, or persistent frontier state.

The frontier then reported three exact goals: two covered and one
workflow-pending. Main selected Research `2050c5322ddd` as the actionable
repair for root `1a0f4f0fbceb`, with reason
`production_product_invalidated`. That selection is nontruth workflow state,
not a mathematical conclusion.

## Release and CHX simplification

- A successful forensic matrix now explicitly subsumes the routine profile for
  unchanged manifest bytes and reports total time, recorded lane time, and the
  slowest lane.
- Repository-facing version, release name, archive, manifest, and checksum
  identity are checked by the existing release validator; public prose remains
  agent-authored.
- `scripts/local_install.py` is the sole public installer. Its implementation
  is now unmistakably private at `scripts/mathgraph/_local_install.py`.
- CHX explicitly treats validation, installation, packaging, publication,
  rollback, and settlement as observation surfaces even after the operation
  succeeds.
- A global installation is represented directly by one cross-ledger integrated
  repair. It does not require a synthetic tactical repair.

## PHX boundary

Main is expected to use the goal and frontier actively, not obey a mechanical
queue. Ambiguity remains visible for judgment rather than being hidden behind a
fuzzy matcher or auto-close rule. The release preserves exact source,
mathematical, hash, and Fact-authority protections while removing avoidable
agent-error surfaces.

## Validation and installation

The frozen 264-entry manifest passed one forensic matrix on unchanged bytes:

- self-test: PASS in 0.954 seconds;
- complete suite: 1,006 discovered tests, PASS in 90.930 seconds;
- mutation registry: 145/145 unique targets;
- full mutation audit: 145/145 killed in 173.444 seconds;
- behavioral gate: 43 features in 21.323 seconds;
- strict architecture reconnaissance: 0 errors, 0 warnings, and 0 orphans in
  5.421 seconds.

The complete matrix took 291.871 wall seconds; the mutation audit was the
slowest lane. The same frozen tree was installed globally and compared exact
across all 265 package files. Installation read and wrote no research project.

| Item | SHA-256 or value |
|---|---|
| Manifest | `ad7e4a1b5ce81a35e62ac4d78cdc845a9289e226e866f0987d3d02258ff91d51` |
| Runtime content | `fe51aa8d051fc7bfae730cf3f17b4cc56a62b8c80aa1cbdcd08c66e6adf80fed` |
| Installed runtime identity | `164fded34389f5f491ed080eafc99a20c09fc5de2fd3e76345bbea029a8ef630` |
| Installed archive-tree identity | `349612debe0ce1685f1d5b0efa3ea84d923696d81aee06547f5d9199a7b11dce` |
| Direct rollback | 0.8.12 content `ffb00b70da8035ff7939aef3a8050dbcd41492249398ac7a2fc3f4f6de233c03` |

## Global CHX settlement

`global-repair-0b4d0d15520bc41f8273a3f6d962dc0129511b2a18440056fabbd2c9694e698a`
covers all 177 observed qualified issues:

- 171 resolved;
- 6 excluded as historical nonarchitectural items;
- 0 unresolved or uncovered;
- 0 active open issues;
- 0 lineage errors or report drift.

Its canonical `record_sha256` is
`14307aba1bc1af4791dff5e97f068d4df828a22e824af7bbed346cbb9302f7a2`;
the record-file SHA-256 is
`40720e2137716e1229e97f8920779ef88ecc68cb7e879c499dc9512bf2bd3bd0`.
Historical ledger bytes and old active flags were not rewritten; none retains
an open issue. The current task ledger contains zero tactical and zero
per-ledger integrated repairs.

## Public distribution

Release assets:

- `chalxius-0.9.0-frontier-active-fix.tar.gz`
- `chalxius-0.9.0-frontier-active-fix.tar.gz.sha256`

The deterministic archive contains 265 regular files, no directory members,
is 2,601,441 bytes, and has SHA-256
`30e6d08ff6546a454e4273efa42e561b57f67f8c3cf9e8c2337baef3fcc8519a`.

```sh
shasum -a 256 -c chalxius-0.9.0-frontier-active-fix.tar.gz.sha256
tar -xzf chalxius-0.9.0-frontier-active-fix.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

This architecture release created no Candidate Release, Certification
Decision, Gateway admission, or Fact.
