# Chalxius

**A persistent research graph for source-bound work with Codex.**

[Live examples](https://cm4u7.github.io/chalxius/) ·
[Download v0.8.8](https://github.com/cm4u7/chalxius/releases/tag/v0.8.8) ·
[Use cases](USE_CASES.md) ·
[Architecture](ARCHITECTURE.md) ·
[Validation](VALIDATION.md)

Chalxius is a Codex skill and local runtime for long-running mathematical,
philosophical, and paper-based research. It keeps sources, claims, proof
attempts, objections, computations, and reviews in a persistent graph instead
of compressing them into one increasingly fragile conversation.

> Research is allowed to be unfinished or wrong. Reusable Facts are not easy
> to create.

That separation is the point. Exploration remains flexible; a claim becomes a
Fact only through an exact Candidate, fresh verification, Certification, and
Gateway admission.

## Start in one prompt

There is no prompt language to learn. Name `Chalxius` or `$chalxius`, describe
the research object, and state the boundary that matters:

```text
Use $chalxius to continue this local-F0 project. Inspect the current graph,
choose the most load-bearing open Research target, and keep every unproved
A/B-model transport explicitly conditional.
```

Chalxius then works from the graph that actually exists: it resolves the
relevant sources and dependencies, selects a bounded next target, records new
work as Research, and attaches focused review to the logical component being
tested. It does not silently turn a plausible report into mathematical truth.

Use `fast mode` for a narrow, low-cost unit or `deep mode` for broader source,
route, and computation work. The default is `auto`. Modes change research
effort, never Fact-admission standards.

## See a real graph

[![Open the 175-node anonymized Chalxius Reader](docs/assets/anonymized-research-topology.png)](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)

The featured Reader preserves the topology of a working run: 175 nodes, 364
edges, 17 targets, and 7 themes. Content-bearing fields were removed and node
identifiers were replaced with opaque HMAC-SHA-256 values generated from a
discarded key.

Other self-contained examples:

- [A philosophy workflow](https://cm4u7.github.io/chalxius/cases/philosophy.html):
  source reconstruction, independent audit, correction, and authority
  separation.
- [A proof graph](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html):
  computation, blockers, verification, and revocation in one Reader.

Readers are deterministic offline views. They support search, filters,
complete-path expansion, MathJax, and draggable cards without changing the
underlying graph.

## Why use a research graph?

**Long work loses structure.** A chat can remember prose while losing which
hypothesis, source version, branch, or computation a conclusion depended on.
Chalxius stores those relations explicitly.

**Sources need exact identity.** A citation alone does not say which bytes,
locator, convention, or theorem interface was used. Source-bound nodes do.

**Exploration and truth are different jobs.** Literature notes, promising
proofs, failed routes, and supervised Research remain useful without receiving
Fact authority.

**Corrections should not erase history.** Replacements, challenges, and
revocations are appended copy-on-write, so downstream impact stays visible.

## The authority model

```text
exact sources ──► Paper / Evidence ──► Research
                                            │
                              attempts · attacks · computation
                                            │
                                            ▼
                                    Candidate Release
                                            │
                                      fresh Verifier
                                            │
                               Certification Decision
                                            │
                                       Fact Gateway
                                            │
                                            ▼
                                        Fact Graph
```

| Plane | What belongs there | Creates mathematical truth? |
|---|---|---|
| Paper / Evidence | Exact sources, reconstruction, audit, correction | No |
| Research / Blackboard | Attempts, insights, objections, computation, synthesis | No |
| Candidate / Certification | Exact proposed Fact bytes and independent review | Not by itself |
| Fact Graph | Admitted reusable premises | Yes |

The sole truth path is:

```text
Research → Candidate Release → Certification Decision → Fact
```

A polished paper report, successful computation, review receipt, or Reader
page is not a Fact. Conversely, Research does not need Fact ceremony merely to
remain visible, useful, and extendable.

## What it supports

- reconstructing and auditing papers against frozen source bytes;
- continuing proofs without weakening the original target unnoticed;
- running independent proof, counterexample, literature, and computation
  routes without mixing their authority;
- focused second-stage review of source use, proof logic, integration, or
  program–mathematics alignment;
- replayable computations with code, versions, domains, representations,
  outputs, and checks bound to the claim they support;
- Candidate packaging, fresh verification, Certification, Fact admission, and
  later revocation;
- deterministic offline Readers for research delivery;
- optional teaching and testing through Chalxius Learner, which cannot modify
  Research or Fact state.

## Install and verify

Download the two adjacent assets from the
[v0.8.8 release](https://github.com/cm4u7/chalxius/releases/tag/v0.8.8):

- `chalxius-0.8.8-direct-graph-operations.tar.gz`
- `chalxius-0.8.8-direct-graph-operations.tar.gz.sha256`

Then verify the archive, the unpacked tree, and the runtime:

```sh
shasum -a 256 -c chalxius-0.8.8-direct-graph-operations.tar.gz.sha256
tar -xzf chalxius-0.8.8-direct-graph-operations.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 scripts/self_test.py
```

The unpacked [`chalxius/`](chalxius/) directory is the installable Codex skill.
For an authorized host-global local update, the bundled installer validates the
candidate, archives the previous runtime, swaps atomically, and verifies the
installed copy:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B chalxius/scripts/local_install.py
```

The normal installer does not read or write a research project. Deployment and
rollback details are in
[`portable_deployment.md`](chalxius/references/portable_deployment.md).

<details>
<summary><strong>Optional command-line entry</strong></summary>

Most work starts in ordinary language. For exact automation and diagnostics,
`mgraph` is a shell executable:

```sh
MGRAPH=/absolute/path/to/chalxius/scripts/mgraph
PROJECT=/absolute/path/to/project

"$MGRAPH" --root "$PROJECT" --role main status
"$MGRAPH" --root "$PROJECT" --role main frontier
```

Run `scripts/mgraph --help` for the full interface. Do not pass `mgraph` to the
Python interpreter.

</details>

## Direct Graph Operations in v0.8.8

This release removes two procedural detours from ordinary Research:

- exact admitted Fact premises are validated directly, without replaying
  unrelated admissions or historical Research;
- a task-card primary source can be used directly by SHA-256, without copying
  the same bytes into a worker return.

Existing returned-source bindings remain valid under the same semantic rule.
Fact-closure reconstruction, attack targets, computation bridges, verifier
review, Certification, Gateway admission, and Fact correctness checks remain
at the boundaries that own them. No compatibility layer, migration ceremony,
timer, monitor, receipt gate, or new lifecycle state was added.

See [RELEASE.md](RELEASE.md) for the complete change set and
[VALIDATION.md](VALIDATION.md) for reproducible evidence.

## Documentation

| Read this | For |
|---|---|
| [USE_CASES.md](USE_CASES.md) | End-to-end examples and expected outcomes |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System model, roles, planes, and authority boundaries |
| [SKILL.md](chalxius/SKILL.md) | Agent-facing router and operating contract |
| [Worker return contract](chalxius/references/v5_worker_return_contract.md) | Current bounded-return schema |
| [Admission contract](chalxius/references/admission_contract.md) | Candidate, verifier, Certification, and Fact rules |
| [Evidence plane](chalxius/references/evidence_plane.md) | Paper and cross-project Evidence lifecycle |
| [VALIDATION.md](VALIDATION.md) | Tests, package identity, installation, and canaries |

## Scope and credits

Software validation establishes package and workflow behavior, not a
mathematical theorem.

Chalxius acknowledges the authors of *Danus: Orchestrating Mathematical
Reasoning Agents with Fact-Graph Memory* (Liu et al., arXiv:2607.06447v2),
whose public design informed the fact-graph layout, and Matt Pocock for the
public `/grill-me` requirements-interview design that informed Reader
requirements work. Neither is a runtime dependency. See
[ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

Licensed under [Apache-2.0](LICENSE). Third-party notices and vendored licenses
are included in the skill directory.
