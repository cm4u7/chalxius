# Chalxius

**Persistent research memory and a reliable working frontier for Codex.**

[Live graph](https://cm4u7.github.io/chalxius/) ·
[Download v1.0.0](https://github.com/cm4u7/chalxius/releases/tag/v1.0.0) ·
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

## One Research graph, sparse Fact certification

```text
free supervised Research growth
        ↓ Main selects important exact nodes
frozen multi-Research package -> independent verifier -> Gateway
        ↓
the same Research nodes carry append-only Fact certification
```

Research may be incomplete, disputed, or wrong and still be valuable. Fact is
not a second proof graph: it is certification of one exact whole Research
record. Main marks load-bearing nodes and batches them when useful. A packaging
agent extracts a semi-formal interface without rewriting the claim; one
independent verifier checks records, explicit certified-predecessor edges, and
interfaces; the Gateway makes only correct components visible.

The derived Fact frontier records where certification has reached, what Main
marked important, and what a COW made stale. It does not schedule work or force
Research and Fact to stay synchronized. Old 0.x Candidate/Fact authority
remains readable and is not silently migrated.

## Install

Download from the
[v1.0.0 release](https://github.com/cm4u7/chalxius/releases/tag/v1.0.0):

- `chalxius-1.0.0-fact-alpha.tar.gz`
- `chalxius-1.0.0-fact-alpha.tar.gz.sha256`

Then verify and install:

```sh
shasum -a 256 -c chalxius-1.0.0-fact-alpha.tar.gz.sha256
tar -xzf chalxius-1.0.0-fact-alpha.tar.gz
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

## v1.0.0 — Fact Alpha

- Fact certification is an append-only property of exact Research records;
- Main keeps sparse importance marks while certification state, COW
  reverification, heads, and batch opportunities are derived live;
- Candidate packaging batches multiple Research nodes and preserves their exact
  claims through semi-formal interfaces;
- one verifier replaces the duplicated Candidate-adverse/verifier roles;
- correct independent components can pass beside a failed component;
- minor repairs return complete COW successors to the same verifier, while
  fundamental errors return to ordinary Research;
- new Research can bind exact active certified Research premises directly.

The release adds no automatic selector, timer, scheduler, daemon, or background
Fact worker. See [RELEASE.md](RELEASE.md) for the complete release note and
[VALIDATION.md](VALIDATION.md) for exact software evidence.

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
