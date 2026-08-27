# Chalxius

**Persistent research memory and a reliable working frontier for Codex.**

[Live graph](https://cm4u7.github.io/chalxius/) ·
[Download v0.9.12](https://github.com/cm4u7/chalxius/releases/tag/v0.9.12) ·
[Use cases](USE_CASES.md) ·
[Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md)

Chalxius is a local research runtime for projects that outgrow one chat. It
keeps sources, Research, computations, objections, dependencies, supervision,
failed routes, and admitted Facts in one content-addressed graph without
collapsing their different authority levels.

Its ordinary frontier is Main's working memory: a compact view of the current
mathematical boundary, exact work in flight, recently attained results,
historical landmarks, and places that genuinely require judgment. Main chooses
the direction. Chalxius records and projects that choice; it does not select or
dispatch research automatically.

[![Open the anonymized Chalxius Reader](docs/assets/anonymized-research-topology.png)](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)

*A content-free projection of a real research topology. Click to explore it.*

## Start

Ask Codex:

```text
Use $chalxius to continue this project. Read the active Campaign goals and
frontier, search exact Research before choosing a new target, and keep every
unproved bridge explicitly conditional.
```

`auto` is the default profile. `fast` narrows the next work unit; `deep` allows
broader source, route, and computation exploration. Profiles never change the
Fact-admission standard.

Main's ordinary loop is short:

1. read the objective and active Campaign goals;
2. inspect the bounded frontier;
3. search existing Research before choosing a named target;
4. plan useful production or independent supervision;
5. ingest the result and read the newly exposed boundary.

Campaign goals hold durable, non-procedural objectives. Frontier state is
compact and replaceable. Immutable Research and round records remain the
history and evidence; neither Campaign nor frontier is a second truth path.

## Truth boundary

```text
Research -> Candidate Release -> Certification Decision -> Gateway -> Fact
```

Research may be incomplete, disputed, or wrong and still be valuable. A Fact
must freeze its exact claim, dependencies, sources, and adverse work and pass
the independent admission path. A report, worker receipt, frontier label, or
successful computation cannot bypass it.

## Install

Download from the
[v0.9.12 release](https://github.com/cm4u7/chalxius/releases/tag/v0.9.12):

- `chalxius-0.9.12-frontier-lifecycle-closure.tar.gz`
- `chalxius-0.9.12-frontier-lifecycle-closure.tar.gz.sha256`

Then verify and install:

```sh
shasum -a 256 -c chalxius-0.9.12-frontier-lifecycle-closure.tar.gz.sha256
tar -xzf chalxius-0.9.12-frontier-lifecycle-closure.tar.gz
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
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 5
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 5 --diagnostic
```

The default frontier is the bounded decision surface. `--diagnostic` adds deep
topology only when Main is investigating a discrepancy.

## v0.9.12 — Frontier Lifecycle Closure

- exact historical copy-on-write repair chains now reach their actual terminal
  Research when the frozen graph determines one unambiguous edge;
- real `await_return` work remains the foreground state of a multi-head goal,
  while older reconciliation branches stay visible;
- one frontier command reuses Research bytes already hash-validated in that
  command, then still performs full record and artifact validation;
- Main resumes a still-running host command instead of mistaking an
  intermediate yield for blank output and duplicating a mutating plan.

The release adds no automatic selector, scheduler, daemon, compatibility layer,
workflow gate, Candidate effect, or Fact effect. See [RELEASE.md](RELEASE.md)
for the complete release note and [VALIDATION.md](VALIDATION.md) for exact
software evidence.

## Explore

- [Anonymized research topology](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)
- [Philosophy source-and-audit workflow](https://cm4u7.github.io/chalxius/cases/philosophy.html)
- [Guarded proof graph](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html)
- [Skill contract](chalxius/SKILL.md)
- [Worker return contract](chalxius/references/v5_worker_return_contract.md)
- [Fact admission contract](chalxius/references/admission_contract.md)

Examples demonstrate workflow and graph structure; they do not declare the
displayed mathematics admitted. Software validation establishes package
behavior, not a theorem. Licensed under [Apache-2.0](LICENSE); see
[acknowledgements](ACKNOWLEDGEMENTS.md) for design lineage and credits.
