# Chalxius

**Persistent research memory for Codex.**

[Live graph](https://cm4u7.github.io/chalxius/) ·
[Download v0.8.12](https://github.com/cm4u7/chalxius/releases/tag/v0.8.12) ·
[Use cases](USE_CASES.md) ·
[Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md)

Chalxius turns long-running mathematical, philosophical, and paper-centered
work into a durable graph. Exact sources, hypotheses, attempts, computations,
objections, and dependencies survive across sessions without being flattened
into one increasingly fragile chat history.

[![Open the anonymized Chalxius Reader](docs/assets/anonymized-research-topology.png)](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)

*A 175-node anonymized research topology. Click the image to explore it.*

## What it gives you

- **Continuity:** the next session starts from the graph that actually exists,
  not from a prose reconstruction of the last conversation.
- **Active research:** Main explicitly selects the next load-bearing open node.
  For a named object or theorem it first runs one bounded exact Research search,
  then binds proof, literature, counterexample, and computation work to the
  chosen target and dependencies.
- **A clean truth boundary:** unfinished, disputed, and failed work remains
  useful Research. Nothing becomes a reusable Fact automatically.
- **A shareable Reader:** export a deterministic offline map with search,
  MathJax, filters, complete-path expansion, and draggable cards—without
  writing back to the graph.

## Use it

There is no special prompt language:

```text
Use $chalxius to continue this project. Inspect the current graph, choose the
most load-bearing open Research target, and keep every unproved bridge
explicitly conditional.
```

`auto` is the default. Ask for `fast` for one narrow, inexpensive work unit or
`deep` for broader source, route, and computation exploration. The mode changes
research effort, never the Fact standard.

## The trust model

```text
Research  →  Candidate Release  →  Certification Decision  →  Fact
```

Research may be incomplete or wrong. A reusable Fact must freeze the exact
claim, dependencies, sources, and adverse work; receive fresh independent
review; and be admitted by the Gateway. Confidence, polished prose, a review
receipt, or a successful computation cannot create a second truth path.

## Install

Download the archive and checksum from the
[v0.8.12 release](https://github.com/cm4u7/chalxius/releases/tag/v0.8.12), then:

```sh
shasum -a 256 -c chalxius-0.8.12-semantic-recovery.tar.gz.sha256
tar -xzf chalxius-0.8.12-semantic-recovery.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/local_install.py
```

The installer validates the candidate, archives the previous runtime, swaps
atomically, and verifies the installed copy. It does not read or modify any
research project. See [portable deployment](chalxius/references/portable_deployment.md)
for rollback and non-default layouts.

<details>
<summary><strong>CLI and automation</strong></summary>

`mgraph` is a shell executable, not a Python file:

```sh
MGRAPH=/absolute/path/to/chalxius/scripts/mgraph
PROJECT=/absolute/path/to/project

"$MGRAPH" --root "$PROJECT" --role main status
"$MGRAPH" --root "$PROJECT" --role main frontier
```

Run `scripts/mgraph --help` for the complete interface.

</details>

## Explore

- [Anonymized research topology](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)
- [Philosophy source-and-audit workflow](https://cm4u7.github.io/chalxius/cases/philosophy.html)
- [Guarded proof graph](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html)

The examples demonstrate graph structure and workflow; they do not claim that
the displayed mathematics or interpretation has been admitted as Fact.

## v0.8.12 — Semantic Recovery

This release makes exact copy-on-write completion visible at the original
frontier node and reopens it if the current terminal result is invalidated or
the lineage is ambiguous. Main owns cross-round search and final dispatch,
uses real independent work when slots are visible, and reconstructs state after
client reconnect without duplicating or reclaiming work from the banner alone.
No monitor, quota, scheduler, compatibility layer, new lifecycle state, or
truth gate is added. Mathematical and Fact-authority boundaries are unchanged. See
[RELEASE.md](RELEASE.md) and [VALIDATION.md](VALIDATION.md).

## Documentation

[Use cases](USE_CASES.md) ·
[Architecture](ARCHITECTURE.md) ·
[Skill contract](chalxius/SKILL.md) ·
[Worker return contract](chalxius/references/v5_worker_return_contract.md) ·
[Fact admission contract](chalxius/references/admission_contract.md)

Software validation establishes package behavior, not a mathematical theorem.
Licensed under [Apache-2.0](LICENSE). See
[acknowledgements](ACKNOWLEDGEMENTS.md) for design lineage and credits.
