# 🧭 Chalxius

Chalxius helps mathematicians turn papers, proof ideas, computations, and
teaching goals into a working research graph that Codex can inspect, extend,
test, and present.

**[🚀 Explore the live cases](https://cm4u7.github.io/chalxius/)** ·
[📚 Read the use cases](USE_CASES.md) ·
[📦 Download v0.3.5](https://github.com/cm4u7/chalxius/releases/tag/v0.3.5) ·
[✅ See validation evidence](VALIDATION.md)

## 🚀 Start with the interactive cases

These are complete, self-contained Reader pages. Click either preview to open
the live graph, select nodes, inspect mathematical detail, and expand complete
dependency paths.

| 📚 Philosophy workflow | 🧮 Potential x-y interchange workflow |
|---|---|
| [![Open the philosophy workflow Reader](docs/assets/philosophy-case.png)](https://cm4u7.github.io/chalxius/cases/philosophy.html) | [![Open the potential x-y interchange Reader](docs/assets/xy-swap-potential-case.png)](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html) |
| Source-bound argument reconstruction, independent review, and a readable map of conclusions and dependencies. | A guarded visualization of a larger mathematical dependency graph, including computational evidence and an explicit revocation. **Potential application only; not author-confirmed.** |

## 🧰 What you can do with Chalxius

- 📄 **Read a paper structurally.** Preserve exact passages, reconstruct the
  argument, map definitions and lemmas, and keep source text distinct from your
  interpretation.
- 🧩 **Develop a proof as a dependency graph.** Track targets, prerequisites,
  competing routes, missing lemmas, counterexamples, and unresolved obstacles.
- 🧠 **Run several lines of reasoning without mixing them.** Keep exploratory
  attempts on the Blackboard, compare them, and synthesize only after their
  assumptions and outputs are visible.
- 🧮 **Make computation replayable.** Bind code, versions, checkpoints,
  artifacts, outputs, and independent replay evidence to the claim that uses
  them.
- 🔎 **Investigate source and novelty questions.** Check theorem applicability,
  conventions, quantifiers, nearby literature, and whether a claimed result is
  genuinely new within the searched corpus.
- ✅ **Promote only reusable results.** A candidate becomes a Fact only after
  its exact dependencies, sources, computation, review, and verifier package
  satisfy one stable admission contract.
- ♻️ **Correct without losing history.** Challenge, replace, refute, or revoke
  a node while retaining the old state and exposing downstream consequences.
- 🎓 **Teach from the research graph.** Chalxius Learner can question, explain,
  test, and schedule review from frozen research snapshots without changing
  research state.
- 🗺️ **Publish a readable map.** Export one offline HTML file with bilingual
  controls, draggable cards, mathematical detail, layer filters, and path
  exploration.

## ⚡ Apply it to a project

You can start from a paper, a directory of notes, a proof problem, or an
existing research archive. Useful prompts include:

```text
Use $chalxius in auto mode to reconstruct the main theorem of this paper,
identify its prerequisite chain, and put unresolved proof obligations on the
Blackboard.
```

```text
Use $chalxius in deep mode to investigate whether this claim follows under the
stated hypotheses. Compare independent proof routes, check the cited sources,
and replay the load-bearing computation.
```

```text
Use Chalxius Learner to test my understanding of this frozen graph one question
at a time. Do not change the research graph.
```

```text
Export the current target graph as a single-file Reader with complete sidebar
summaries and provenance.
```

The normal working loop is:

1. 🎯 Choose an exact target.
2. 📚 Freeze the relevant sources and current graph state.
3. 🧪 Explore proof routes, computations, objections, and missing prerequisites.
4. 🔍 Verify a frozen candidate from a fresh context.
5. ✅ Admit a reusable Fact, or record the exact blocker.
6. 🗺️ Export a Reader when you want to study or present the graph.

## 🎛️ Choose the reasoning profile

The profiles control research breadth and orchestration cost. They do not
change the Fact-admission standard.

| Profile | Best suited to | What Chalxius does |
|---|---|---|
| ⚡ `fast` | A narrow task with clear sources and prerequisites | Keeps expensive exploratory machinery opt-in while retaining source checks, replay requirements, verifier separation, and the full Fact gate |
| 🧭 `auto` | Most day-to-day mathematical work | Uses deterministic workload signals to activate the advanced features that the task calls for; this is the default |
| 🔬 `deep` | Ambiguous sources, competing proof routes, literature/novelty work, substantial computation, or high-impact conclusions | Requires every advanced research feature that is genuinely applicable and binds its completion before verification |

### 🔬 What `deep` can activate

`deep` evaluates the task against ten advanced capabilities and requires each
one that applies:

- 🧠 **Parallel clean-context panel** — independent reasoning channels attack
  distinct aspects of the problem without inheriting one another's draft.
- 🔄 **Barriered Blackboard pulse** — a two-wave collaboration round freezes
  the first wave, then requires cross-review against that shared snapshot.
- 📖 **Paper Logic Graph** — reconstructs the paper's claims, definitions,
  dependencies, and local identifiers from frozen source material.
- 🕵️ **Paper Audit Graph** — checks source fidelity, target binding, logical
  effect, and repair/refutation claims in a separate reviewed layer.
- 🪞 **Full-fidelity Paper mirror** — exposes the reviewed paper structure to
  exploration without turning the mirror into source authority.
- 🧭 **Orthogonal specialist escalation** — assigns genuinely different expert
  perspectives when a sensitive claim needs more than one reasoning style.
- 🌱 **Long-horizon campaign expansion** — develops several candidate routes or
  related targets instead of forcing a premature local answer.
- 🧮 **Computation exploration lane** — records checkpoints, artifacts, replay,
  and independent numerical or symbolic checks.
- 🔎 **Novelty search lane** — performs a bounded literature search and records
  the corpus/date scope of any novelty statement.
- 🧾 **Expert synthesis pass** — produces an audience-aware synthesis only
  after the contributing evidence and specialist outputs are bound.

An irrelevant capability is marked `not_applicable`; `deep` does not create
ceremonial work. Switching profiles affects future work units only, so a frozen
round keeps the profile and evidence contract with which it began.

## 🗂️ How the workspace stays usable

Chalxius separates material by what it is useful for:

| Workspace | Practical role |
|---|---|
| 📚 Source & reconstruction | Preserve exact paper material and your explicit reading of it |
| 🕵️ Audit | Hold objections, corrections, review decisions, and replacement history |
| 🧠 Blackboard | Develop questions, proof attempts, computations, and candidate synthesis |
| ✅ Fact Graph | Store the admitted premises that later work may reuse |
| 🎓 Learning | Store explanations, attempts, misconceptions, and mastery evidence |

This prevents a promising draft, copied theorem, numerical experiment, or
teaching note from silently becoming a premise. The detailed authority and
correction model lives in [ARCHITECTURE.md](ARCHITECTURE.md); most users can
begin with the workflows above.

## 🗺️ The offline Reader

Reader Finalize requires a useful right-panel explanation for every included
node: summary, intuition, importance, reasoning route, and provenance. The
exporter then writes one self-contained
`visualizations/knowledge-map.html` file with:

- 🌐 switchable Chinese/English controls;
- 🖐️ draggable cards and trackpad-style pan/zoom;
- ➕ per-card full/minimized sizing with undo and redo;
- 🛤️ double-click expansion of any node's complete upstream/downstream chain;
- 🧭 multi-target topic expansion;
- 🧱 optional research, learning, Reader-note, and contextual layers;
- 📐 a resizable detail panel with scalable mathematical text; and
- 🧹 deterministic initial placement with bounded crossing reduction.

Reader interaction changes presentation only. It does not edit graph topology,
source text, provenance, or Fact status.

## 📦 Install and verify

Download `chalxius-0.3.5-public.tar.gz` and `SHA256SUMS` from the
[matching GitHub Release](https://github.com/cm4u7/chalxius/releases/tag/v0.3.5),
keep them in the same directory, and run:

```sh
shasum -a 256 -c SHA256SUMS
tar -xzf chalxius-0.3.5-public.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
```

The unpacked [`chalxius/`](chalxius/) directory is the installable skill.

## 🆕 Current release

Version 0.3.5 improves dense-map reading: mathematical detail follows the
sidebar text scale, topic links use smooth dashed curves, topic double-click
opens all member-target chains, and deterministic placement never accepts more
proper crossings than packet order within its bounded search.

See [RELEASE.md](RELEASE.md) for release notes and
[VALIDATION.md](VALIDATION.md) for frozen test, package, and browser evidence.

## 🛡️ Scope and evidence

- The Reader has `truth_effect="none"` and performs no graph writeback.
- A workflow PASS establishes the stated workflow property, not mathematical
  truth by itself.
- The philosophy example demonstrates a research workflow, not a philosophical
  conclusion.
- The x-y interchange example is a **potential application only**. It is not
  current-audit PASS and has not been confirmed by the relevant authors.
- Private local QA material and user-specific learning profiles are excluded
  from the public package.

## 🙏 Acknowledgements

Chalxius acknowledges the authors of **Danus: Orchestrating Mathematical
Reasoning Agents with Fact-Graph Memory** (Liu et al., arXiv:2607.06447v2), a
separate published system whose public design informed the fact-graph layout.

It also thanks **Matt Pocock** for the public
[`/grill-me`](https://github.com/mattpocock/skills/blob/main/docs/productivity/grill-me.md)
requirements-interview design that informed the Reader's requirements work.
Neither is a runtime dependency. See
[ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md) for the complete attribution scope.

Licensed under Apache-2.0. Third-party notices and vendored component licenses
are included in the skill directory.
