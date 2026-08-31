# Chalxius

**Persistent Research memory, a reliable working frontier, and sparse Fact
certification for long-running Codex projects.**

[Download v1.0.7](https://github.com/cm4u7/chalxius/releases/tag/v1.0.7) ·
[Release notes](RELEASE.md) · [Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md) · [License](LICENSE)

> [!IMPORTANT]
> **Graph Browser and graphical graph generation are temporarily unavailable.**
> Chalxius 1.0.7 does not present either as a supported release capability.
> Historical or experimental Reader code and commands may still be present in
> the repository, but users should not depend on them until the browser is
> redesigned. This limitation does not affect Research storage, exact search,
> Campaign/frontier coordination, supervision, or Fact certification.

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

Release assets for v1.0.7 are:

- `chalxius-1.0.7-campaign-attention-continuity.tar.gz`
- `chalxius-1.0.7-campaign-attention-continuity.tar.gz.sha256`

Verify and install:

```sh
shasum -a 256 -c chalxius-1.0.7-campaign-attention-continuity.tar.gz.sha256
tar -xzf chalxius-1.0.7-campaign-attention-continuity.tar.gz
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
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 8 --diagnostic
"$MGRAPH" --root "$PROJECT" --role main search "exact topic" --scope research
```

The default frontier is the bounded decision surface. `--diagnostic` adds deep
topology only when Main is investigating a discrepancy.

## v1.0.7 — Campaign Attention Continuity

This release keeps Campaign working memory stable while Main advances one
route:

- planning a successor retires only the active head it actually replaces;
- unrelated parallel heads and their attached context remain visible;
- context and its reason follow a unique replacement, while real branching
  ambiguity remains explicit;
- the same Research may serve several Campaigns or targets without cloning or
  retagging it; and
- Campaign roles remain nontruth working-memory references, never ownership or
  admission gates.

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
