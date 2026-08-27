# Chalxius

**Persistent research memory and a reliable working frontier for Codex.**

[Live graph](https://cm4u7.github.io/chalxius/) ·
[Download v0.9.10](https://github.com/cm4u7/chalxius/releases/tag/v0.9.10) ·
[Use cases](USE_CASES.md) ·
[Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md)

Chalxius is a local research runtime for projects that outgrow one chat. It
keeps sources, Research, computations, objections, dependencies, failed routes,
supervision, and admitted Facts in one content-addressed graph while preserving
their different authority levels.

The ordinary frontier is Main's working memory. It connects durable Campaign
goals to the current Research boundary, shows exact work already in flight or
awaiting ingestion, and identifies where Main must make a mathematical choice.
It does not choose a research direction, dispatch workers, or promote Research
to Fact automatically.

[![Open the anonymized Chalxius Reader](docs/assets/anonymized-research-topology.png)](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)

*A content-free projection of a real research topology. Click to explore it.*

## Start here

Ask Codex:

```text
Use $chalxius to continue this project. Read the current Campaign goal and
frontier, search existing Research before choosing a new target, and keep every
unproved bridge explicitly conditional.
```

`auto` is the default profile. `fast` narrows the next work unit; `deep` permits
broader source, route, and computation exploration. Profiles never change the
Fact-admission standard.

A typical Main loop is deliberately short:

1. read the user's objective and active Campaign goals;
2. inspect the compact frontier;
3. search exact Research identities before creating overlapping work;
4. choose and dispatch a useful production or supervision unit;
5. ingest the result and let the graph expose the next boundary.

Campaign goals store non-procedural objectives. Frontier state stores compact,
replaceable navigation memory. Immutable Research and round records remain the
history and evidence; neither Campaign nor frontier is a second truth path.

## Truth boundary

```text
Research → Candidate Release → Certification Decision → Gateway admission → Fact
```

Research may be incomplete, disputed, or wrong and still be useful. A reusable
Fact must freeze its exact claim, dependencies, sources, and adverse work and
pass the independent admission path. A polished report, worker receipt,
frontier label, or successful computation cannot bypass it.

## Install

Download these assets from the
[v0.9.10 release](https://github.com/cm4u7/chalxius/releases/tag/v0.9.10):

- `chalxius-0.9.10-terminal-seal-hygiene.tar.gz`
- `chalxius-0.9.10-terminal-seal-hygiene.tar.gz.sha256`

Then verify and install:

```sh
shasum -a 256 -c chalxius-0.9.10-terminal-seal-hygiene.tar.gz.sha256
tar -xzf chalxius-0.9.10-terminal-seal-hygiene.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
python3 -B scripts/local_install.py
```

The installer validates one complete manifest-bound tree, archives the previous
runtime, swaps atomically, and retains a direct rollback copy. It does not read
or mutate a research project. See
[portable deployment](chalxius/references/portable_deployment.md) for details.

## CLI

`mgraph` is a shell executable, not a Python file:

```sh
MGRAPH=/absolute/path/to/chalxius/scripts/mgraph
PROJECT=/absolute/path/to/project

"$MGRAPH" --root "$PROJECT" --role main status
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 5
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 5 --diagnostic
```

Default frontier output is the bounded decision surface. `--diagnostic` adds
forensic topology only when Main is investigating a discrepancy.

## v0.9.10 — Terminal Seal Hygiene

This release consolidates the Campaign/frontier work completed after 0.9.0:

- production planning and Campaign working memory now share Main's one explicit
  target choice, including positive successor, repair, overlapping-supervision,
  and compatible multi-branch handoff;
- ordinary search and show navigate immutable Research as well as Facts;
- exact source capabilities survive supervision handoff without duplicate byte
  returns;
- Finder-created `.DS_Store` at two exact terminal locations no longer
  invalidates otherwise hash-exact work;
- one frontier command reuses one ephemeral exact-snapshot inspection instead
  of repeatedly rescanning the same Research and round data.

On the 1,778-Research local-F0 canary, the last repair preserved the exact
42,528-byte frontier output and reduced six-run median time from 2.4116 to
1.8115 seconds. It adds no persistent cache, daemon, scheduler, compatibility
layer, workflow gate, Candidate effect, or Fact effect.

See [RELEASE.md](RELEASE.md) for the complete release note and
[VALIDATION.md](VALIDATION.md) for reproducible identities and test results.

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
