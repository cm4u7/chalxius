# Chalxius

Chalxius is a research, audit, learning, and visualization skill for Codex. It
helps turn source material and exploratory work into a traceable knowledge
graph while keeping a strict distinction between “recorded,” “interpreted,”
“tested,” and “admitted as a reusable Fact.”

No prior knowledge of Chalxius or knowledge-graph software is required.

## What it can do

- Reconstruct a paper or argument from exact, frozen source passages.
- Audit that reconstruction without overwriting rejected or superseded states.
- Organize questions, proof attempts, computations, counterexamples, and
  obstacles on a research Blackboard.
- Admit a claim to the Fact Graph only after the complete evidence and fresh-
  verification contract passes.
- Teach or test a learner from frozen research snapshots when learning is
  explicitly requested.
- Export a prepared graph as one offline, interactive HTML file for human
  reading and presentation.

## The central mechanism: authority stays attached

Chalxius does not treat every convincing paragraph as equally trustworthy. An
object keeps the authority of the process that created it:

| Area | What it contains | What it is allowed to mean |
|---|---|---|
| Source | Exact passages and source relations | Evidence of what a source says |
| Reconstruction | An explicit reading of those passages | Interpretation, not source text |
| Audit | Objections, decisions, repairs, and replacement history | Review evidence, not a premise |
| Blackboard | Questions, attempts, experiments, and candidate synthesis | Exploration only |
| Fact Graph | Claims that passed the full admission contract | Reusable research premises |
| Learning | Explanations, hints, attempts, and mastery evidence | Teaching evidence only |

This separation is the main safety property. Copying a source claim to the
Blackboard does not turn it into a Fact. Passing a workflow audit does not prove
a theorem. Answering a lesson correctly does not modify research authority.

## How a claim becomes a Fact

The normal flow is:

1. Freeze the exact source and the current graph snapshot.
2. Explore the claim, its prerequisites, proof, computations, objections, and
   scope without granting it Fact authority.
3. Build a content-addressed candidate package: changing any bound byte changes
   its identity.
4. Give that frozen package to a fresh verifier that did not create the
   candidate.
5. Admit the claim only if its prerequisites are already active Facts, source
   applicability and quantifiers are checked, required computations replay,
   review bindings match, and the current graph audit is clean.

If one required gate is missing, the claim remains a candidate or an explicit
blocker. Corrections append a challenge, decision, and replacement relation;
they do not erase history. Revoking a Fact is likewise explicit and can revoke
dependent Facts.

## Reasoning profiles

The profiles change how much exploration Chalxius performs, not the strength of
Fact admission:

| Profile | Exploration behavior | Fact-admission contract |
|---|---|---|
| `fast` | Expensive exploration is usually opt-in | Full and unchanged |
| `auto` | Applicable tools are selected from deterministic workload signals; this is the default | Full and unchanged |
| `deep` | Every applicable expensive research feature must be completed | Full and unchanged |

Choose `fast` for a narrow, well-specified task whose sources and prerequisites
are already clear—for example, checking one local proof step or replaying one
known computation. It reduces automatic orchestration, but it cannot skip a
source check, verifier separation, replay requirement, or any other gate needed
for Fact admission. Missing evidence still leaves a candidate or blocker.

Choose `deep` for source ambiguity, several competing proof routes, novelty or
literature questions, substantial computation, or a result whose failure would
invalidate important downstream work. Every expensive feature that actually
applies must finish and be bound into the workflow evidence. An irrelevant
feature is recorded as not applicable; Chalxius does not manufacture ceremonial
work merely to make `deep` look busier.

Use `auto` when neither extreme is requested. It selects the applicable work
from the structure of the task while preserving the same admission standard.

A profile switch affects future work units. It never retroactively changes a
frozen task or creates a weaker class of Fact.

## Learner and Reader

Chalxius Learner starts only when academic teaching, questioning, testing, or
mastery recording is explicitly requested. It may read frozen Source, Audit,
Blackboard, and Fact snapshots, but its notes have no truth effect and cannot
enter Fact admission.

The Reader is a separate presentation surface. Before export, every included
node must have a human-readable summary, intuition, importance, and reasoning
route. The exporter then creates the fixed
`visualizations/knowledge-map.html` file:

- one self-contained HTML document with no runtime network request;
- bilingual Chinese/English interface switching;
- draggable cards and trackpad-style pan/zoom;
- per-card full/minimized sizing with undo and redo;
- double-click expansion of any node's complete upstream/downstream chain;
- topic expansion across all of that topic's target chains;
- optional research, learning, Reader-note, and contextual layers;
- a resizable right detail panel with scalable mathematical text; and
- deterministic initial placement with bounded crossing reduction that never
  accepts more proper crossings than packet order.

Reader interactions are session-only. They do not change source text, graph
topology, Fact status, provenance, or project data; exported metadata reports
`truth_effect="none"`.

For lower-level schemas and invariants, see
[`ARCHITECTURE.md`](ARCHITECTURE.md) and the references inside
[`chalxius/`](chalxius/).

## Install and verify

The installable skill is in [`chalxius/`](chalxius/). For a packaged install,
download `chalxius-0.3.5-public.tar.gz` and `SHA256SUMS` from the matching
GitHub Release, keep them in the same directory, and run:

```sh
shasum -a 256 -c SHA256SUMS
tar -xzf chalxius-0.3.5-public.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
```

## Current release

Version 0.3.5 makes dense maps easier to read without changing their research
meaning. Mathematical formulas and exact TeX scale with the detail-panel text
control, topic links use smooth dashed curves, a topic can expose the complete
chains of all its targets, and the initial ranked layout uses a deterministic
best-so-far crossing-reduction pass. See [`RELEASE.md`](RELEASE.md) for the
complete release notes and [`VALIDATION.md`](VALIDATION.md) for frozen evidence.

## Interactive examples

The [public use cases](USE_CASES.md) link directly to two self-contained Reader
pages:

- a demonstrated, anonymized philosophy-argument audit; and
- a guarded **potential** x-y interchange application that is neither current-
  audit PASS nor author-confirmed.

Open the [interactive case gallery](https://cm4u7.github.io/chalxius/) or read
the source snapshots, packets, and claim boundaries in
[`USE_CASES.md`](USE_CASES.md).

## Public-source boundary

This repository excludes private local visual-QA paths, user-specific learning
profiles, and private historical forward-test evidence. The public and locally
installed 0.3.5 packages share the same research and Reader runtime; the local
installation additionally retains those non-runtime private references and
their self-test inventory entries.

## Acknowledgements

Chalxius gratefully acknowledges the authors of **Danus: Orchestrating
Mathematical Reasoning Agents with Fact-Graph Memory** (Liu et al.,
arXiv:2607.06447v2), a separate published mathematical-reasoning system. Its
public design informed the fact-graph layout, but it is not a runtime dependency
and no Danus source code is inherited here.

Chalxius also thanks **Matt Pocock** for the public
[`/grill-me`](https://github.com/mattpocock/skills/blob/main/docs/productivity/grill-me.md)
skill. Its one-question-at-a-time decision-tree interview inspired the
requirements-discovery method used while shaping the Reader. This is design
attribution, not a runtime dependency. See
[`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) for full citations and scope
statements.

Licensed under Apache-2.0. Third-party notices and vendored component licenses
are included in the skill directory.
