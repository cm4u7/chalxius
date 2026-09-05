# Chalxius

**Persistent Research memory, a reliable working frontier, and sparse Fact
certification for long-running Codex projects.**

[Download v1.0.23](https://github.com/cm4u7/chalxius/releases/tag/v1.0.23) ·
[Release notes](RELEASE.md) · [Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md) · [License](LICENSE)

> [!IMPORTANT]
> **Graph Browser and graphical graph generation are temporarily unavailable.**
> Neither is a supported capability in this release.
> Historical or experimental Reader code and commands may still be present in
> the repository, but users should not depend on them until the browser is
> redesigned. This limitation does not affect Research storage, exact search,
> Campaign/frontier coordination, supervision, or Fact certification.

> [!CAUTION]
> **Semantic splitting and Fact admission are disabled by default.** Routine
> splitting remains opt-in. Fact packaging, verification, certification, and
> admission begin only after an explicit user request; Research, supervision,
> Campaign maintenance, and the internal maintenance clock never start them.

Chalxius is a local research runtime for projects that outgrow one chat. It
keeps sources, Research, computations, objections, dependencies, supervision,
failed routes, and admitted Facts in one content-addressed system without
collapsing their different authority levels.

Its ordinary frontier is Main's working memory: a compact view of the current
mathematical boundary, exact work in flight, recent attainments, durable
historical landmarks, and places that genuinely require judgment. Main chooses
the direction. Chalxius records and projects that choice; it does not select or
dispatch research automatically.

## Core model

```text
Campaign objective
  └─ Targets
      └─ active Research heads + attached context + landmarks
           └─ production / supervision / COW history

one immutable Research graph
  └─ selected predecessor-closed Research packages
      └─ independent verification
          └─ append-only Fact certification on exact Research records
```

- **Research is cumulative nontruth.** Partial proofs, failed routes,
  counterexamples, repairs, and open bridges remain useful without becoming
  trusted premises.
- **Campaign and frontier are working memory.** They preserve objectives and
  the current boundary; they are not a second truth path.
- **Fact is sparse certification.** It is an append-only property of an exact
  Research record, not a duplicate proof graph.
- **Main retains mathematical judgment.** The runtime follows explicit rigid
  workflow relations, but does not infer mathematical completion or choose a
  research direction.

## Start

Ask Codex:

```text
Use $chalxius to continue this project. Read the active Campaign goals and
frontier, search exact Research before choosing a new target, and keep every
unproved bridge explicitly conditional.
```

`auto` is the default profile. `fast` narrows the next work unit; `deep` allows
broader source, route, and computation exploration. Profiles never change the
Research quality or Fact-certification standard.

Main's ordinary loop is short:

1. read the objective, active Campaign goals, frontier, and in-flight rounds;
2. read relevant head context and search existing results and obstructions
   before choosing a named cut;
3. attach useful older results as context or promote them to an active head;
4. plan production or independent supervision, inspect exact prior work, and
   launch an appropriate independent agent;
5. ingest the result and read the newly exposed boundary.

After a context handoff, Main also revisits recent attainments and historical
landmarks before choosing the next cut. Landmarks are sparse, persistent, and
not subject to a numeric quota; routine views show bounded previews while exact
state retains the full set.

## Agent dispatch

Main chooses by difficulty and error risk, not by role name:

| Work | Default |
| --- | --- |
| New mechanism proofs, delicate source interpretation, result assembly, subtle whole-product review, shared-runtime repair | Astra max |
| Bounded source-location checks, straightforward calculations, mechanical edits, focused regressions | Sol max |

Explicit user choices override these defaults. A useful Astra session may be
reused, but useful independent work takes priority over holding an idle slot.
One author-independent supervisor normally handles both applicable source and
proof scopes of a product and can review its later COW. It never reviews its
own production.

## Install

Release assets for v1.0.23 are:

- `chalxius-1.0.23-research-selection-continuity.tar.gz`
- `chalxius-1.0.23-research-selection-continuity.tar.gz.sha256`

Verify and install:

```sh
shasum -a 256 -c chalxius-1.0.23-research-selection-continuity.tar.gz.sha256
tar -xzf chalxius-1.0.23-research-selection-continuity.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/local_install.py
```

The installer validates one complete manifest-bound tree, archives the prior
runtime, and swaps atomically. It does not read or mutate a research project.
See [portable deployment](chalxius/references/portable_deployment.md).

## CLI

`mgraph` is a shell executable, not a Python file:

```sh
MGRAPH=/absolute/path/to/chalxius/scripts/mgraph
PROJECT=/absolute/path/to/project

"$MGRAPH" --root "$PROJECT" --role main status
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 8
"$MGRAPH" --root "$PROJECT" --role main frontier --campaign CAMPAIGN_ID \
  --maintenance
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 8 --diagnostic
"$MGRAPH" --root "$PROJECT" --role main frontier --campaign CAMPAIGN_ID \
  --diagnostic --full-members
"$MGRAPH" --root "$PROJECT" --role main search "exact topic" --scope research
```

The ordinary frontier has a final 32 KiB JSON budget. Exact identities,
counts, digests and drill-down commands remain visible when long prose is
omitted. `--diagnostic --full-members` is the explicit forensic read, not the
ordinary working view.

Full maintenance is a two-stage read: `--maintenance` gives the all-target
routing index; `--maintenance-target TARGET_ID` expands one target's complete
landmark reasons and head-context attachment identities. Context reasons are
expanded around decisions with `--maintenance-expand context-reasons`.
Main searches, compares branches and makes warranted head, landmark and
context changes; a reasoned no-op is valid. Nothing is automatically promoted.

Exact task history is available with `round-status --research-id RESEARCH_ID`.
The same history appears as a bounded advisory when production planning finds
existing work. Deliberate reruns remain legal; a different ID is not proof of
mathematical novelty.

## v1.0.23 — Research Selection Continuity

This release joins exact task history with Main's mathematical selection
practice. It adds prior-work reminders, makes the flat Research creation
envelope clearer, documents the direct production-card input entry for
supervisors, and defines difficulty-based agent dispatch. Main is prompted to
check existing obstructions and whether local results can supply a live
target's missing input, without forcing a DAG or automatic theorem assembly.

It also includes the improvements since the last public release: bounded
frontier output, landmark-centered full maintenance, explicit planning-time
head disposition, precise context reattachment, direct-source ownership and
collision-safe repair input roles. See [release notes](RELEASE.md).

Campaign context storage has no numeric quota, Fact admission remains off by
default, and Campaign membership remains a many-to-many nontruth overlay.
These are operating and coordination rules, not new truth authority or hidden
workflow gates.

The v1.0.5 split opt-in boundary remains in force: routine supervision and
Fact packaging ignore splitting, while a new low-level split requires explicit
current authorization.

Installation owns software correctness testing. Publication then checks the
exact asset identity, checksum, file set, and absence of sensitive local data.
Heavy mutation and forensic matrices remain optional diagnostics rather than
release gates. The release adds no automatic selector, scheduler, inferred
authorization, compatibility layer, second lifecycle, or truth effect.

## Authority boundary

Software validation establishes package behavior, not a theorem. Research,
coordination, diagnostic, and release records have no Fact effect. Only exact
verification followed by Gateway acceptance creates active Fact certification.

Licensed under [Apache-2.0](LICENSE). See
[ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md) for design lineage and credits.
