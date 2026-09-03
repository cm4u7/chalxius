# Chalxius

**Persistent Research memory, a reliable working frontier, and sparse Fact
certification for long-running Codex projects.**

[Download v1.0.17](https://github.com/cm4u7/chalxius/releases/tag/v1.0.17) ·
[Release notes](RELEASE.md) · [Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md) · [License](LICENSE)

> [!IMPORTANT]
> **Graph Browser and graphical graph generation are temporarily unavailable.**
> Chalxius 1.0.17 does not present either as a supported release capability.
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
2. search existing Research before choosing a named cut;
3. attach useful older results as context or promote them to an active head;
4. plan production or independent supervision;
5. ingest the result and read the newly exposed boundary.

After a context handoff, Main also revisits recent attainments and historical
landmarks before choosing the next cut. Landmarks are sparse, persistent, and
not subject to a numeric quota; routine views show bounded previews while exact
state retains the full set.

## Install

Release assets for v1.0.17 are:

- `chalxius-1.0.17-literal-input-continuity.tar.gz`
- `chalxius-1.0.17-literal-input-continuity.tar.gz.sha256`

Verify and install:

```sh
shasum -a 256 -c chalxius-1.0.17-literal-input-continuity.tar.gz.sha256
tar -xzf chalxius-1.0.17-literal-input-continuity.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
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

The default frontier is the bounded decision surface. `--diagnostic` adds deep
topology plus the complete target/head/context/landmark decision surface when
Main is investigating a discrepancy, while ordinary Campaign membership stays
at count, digest, and a small role preview. `--diagnostic --full-members` is the
explicit forensic read of the complete Campaign member-role table.
`--maintenance` is the compact complete working-memory view: it covers every
active target, head, context and landmark identity and reason, plus current
round decisions, but omits repeated hydrated summaries and deep successor
tables. Maintenance changes attention only when the evidence warrants it; a
reasoned no-op is a valid outcome.

## v1.0.17 — Literal Input Continuity

This release carries the durable Campaign memory of v1.0.14 forward and closes
three later continuity failures found during live Research:

- source capability belongs to the exact source-owned assignment, so proof and
  other siblings do not inherit a recursive source gate from historical
  reviews;
- explicit head replacement remains a Main choice and transfers only the named
  old head's context, while exact `plan-repair-round` retries reuse the
  canonical existing round; and
- work that consumes a literal historical formula, definition, convention, or
  theorem statement freezes an exact selected artifact that actually contains
  that input instead of relying on a downstream symbol mention.

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
