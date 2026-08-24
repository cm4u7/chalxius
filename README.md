# Chalxius

**Persistent research memory and an active frontier for Codex.**

[Live graph](https://cm4u7.github.io/chalxius/) ·
[Download v0.9.0](https://github.com/cm4u7/chalxius/releases/tag/v0.9.0) ·
[Use cases](USE_CASES.md) ·
[Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md)

Chalxius keeps long mathematical, philosophical, and paper-centered projects
in a durable graph. Sources, conjectures, attempts, computations, objections,
dependencies, and failed routes survive across sessions without being
flattened into one fragile chat history.

Its ordinary frontier is a small decision surface for Main: it identifies what
has already been produced, what is waiting for return or ingestion, what needs
supervision or repair, and where semantic ambiguity still requires Main's
judgment. It does not automatically choose research direction or promote
mathematics to truth.

[![Open the anonymized Chalxius Reader](docs/assets/anonymized-research-topology.png)](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)

*An anonymized research topology. Click the image to explore it.*

## Start here

Ask Codex directly:

```text
Use $chalxius to continue this project. Read the current Campaign goal and
compact frontier, choose the most load-bearing open Research target, and keep
every unproved bridge explicitly conditional.
```

`auto` is the default research mode. `fast` narrows the next work unit; `deep`
permits broader source, route, and computation exploration. Mode changes never
lower the Fact standard.

Main's working loop is deliberately simple:

1. read the user's objective and the active Campaign goal;
2. inspect the compact, stage-aware frontier;
3. search exact Research identities when the semantic choice is not already
   clear;
4. actively select and dispatch the next useful unit;
5. preserve returns, invalidations, and unresolved bridges in the graph.

Campaign `research_goal` targets remember non-procedural research objectives.
They coordinate with the workflow queue through derived coverage and next
actions, but they are not tasks, proof targets, automatic dispatch rules, or a
second truth path.

## Truth boundary

```text
Research → Candidate Release → Certification Decision → Gateway admission → Fact
```

Research may be incomplete, disputed, or wrong and still be useful. A reusable
Fact must freeze the exact claim, dependencies, sources, and adverse work;
receive fresh independent review; and pass Gateway admission. Confidence,
polished prose, a worker receipt, or a successful computation cannot bypass
that path.

## Install

Download these assets from the
[v0.9.0 release](https://github.com/cm4u7/chalxius/releases/tag/v0.9.0):

- `chalxius-0.9.0-frontier-active-fix.tar.gz`
- `chalxius-0.9.0-frontier-active-fix.tar.gz.sha256`

Then verify and install:

```sh
shasum -a 256 -c chalxius-0.9.0-frontier-active-fix.tar.gz.sha256
tar -xzf chalxius-0.9.0-frontier-active-fix.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/local_install.py
```

The installer validates the candidate, archives the previous runtime, swaps
atomically, and verifies the installed copy. It does not inspect or mutate a
research project. See
[portable deployment](chalxius/references/portable_deployment.md) for rollback
and non-default layouts.

## CLI

`mgraph` is a shell executable, not a Python file:

```sh
MGRAPH=/absolute/path/to/chalxius/scripts/mgraph
PROJECT=/absolute/path/to/project

"$MGRAPH" --root "$PROJECT" --role main status
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 5
"$MGRAPH" --root "$PROJECT" --role main frontier --limit 5 --diagnostic
```

The default frontier is compact. `--diagnostic` adds bounded forensic detail;
it is for investigation, not ordinary context consumption. Run
`scripts/mgraph --help` for the complete interface.

## v0.9.0 — Frontier Active Fix

Version 0.9.0 makes the frontier lifecycle-aware and connects exact Campaign
goals to current Research coverage. On a large live project, Main selected a
real load-bearing repair boundary after two of three goals were already
covered. The same exercise exposed and fixed a whole-graph target-certificate
scan: an idempotent research-goal replay fell from about 294.5 seconds to about
3 seconds without adding a cache, daemon, scheduler, compatibility layer, or
new gate.

The release also leaves one unmistakable public installer, makes release
performance visible, checks repository-facing release identity, and treats
installation or publication defects as ordinary CHX observation surfaces.
Mathematical and Fact authority are unchanged. See [RELEASE.md](RELEASE.md)
and [VALIDATION.md](VALIDATION.md).

## Explore and extend

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
