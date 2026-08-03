# 🧭 Chalxius application cases

Start with the [🚀 interactive case gallery](https://cm4u7.github.io/chalxius/).
Each case opens as one self-contained Reader page: select a node, inspect its
mathematical explanation, drag cards, and double-click a branch to expose its
complete prerequisite and downstream paths.

## 📚 Demonstrated workflow: philosophy argument research

**[▶️ Open the interactive Reader](https://cm4u7.github.io/chalxius/cases/philosophy.html)** ·
[📄 Inspect the public source snapshot](docs/cases/philosophy.source.md)

[![Philosophy workflow Reader preview](docs/assets/philosophy-case.png)](https://cm4u7.github.io/chalxius/cases/philosophy.html)

### 🧰 What this workflow does

- anchors a reconstruction to exact passages from a published paper;
- separates the author's claims from the researcher's interpretation;
- maps conclusions, definitions, objections, and dependency paths;
- obtains independent source-fidelity and graph-structure review;
- retains rejected and superseded revisions instead of erasing them; and
- turns the finished graph into a Reader that can be studied or presented.

### 🖱️ What to try in the Reader

1. Select a conclusion and read its summary, intuition, importance, and route.
2. Double-click the conclusion to expose its complete relevant chain.
3. Toggle research or learning layers to see how supporting material remains
   distinguishable from the main argument.
4. Drag the cards and resize the detail panel to create a comfortable reading
   layout.

### 🛡️ Claim boundary

The underlying workflow audit passed, but the public example intentionally
contains no private argument and admits no philosophical conclusion as a Fact.
It demonstrates a method for organizing argument research; it does not establish
a uniquely correct interpretation, authorial intent, or a philosophical
position.

## 🧮 some math research

> ⚠️ **Potential application only.** The predecessor archive was not produced
> by Chalxius 0.3.5, does not pass the current Chalxius workflow audit

**[▶️ Open the guarded Reader](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html)** ·
[📄 Inspect the public source snapshot](docs/cases/xy-swap-potential.source.md)

[![Potential proof Reader preview](docs/assets/xy-swap-potential-case.png)](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html)

### 🧰 What this kind of project can use

- 🎯 a target closure showing exactly which prerequisites support each result;
- 🧮 replayable symbolic or numerical artifacts attached to load-bearing steps;
- 🧩 several candidate proof routes kept separate until they are compared;
- 🔍 independent review of source, convention, quantifier, and computation use;
- ♻️ explicit revocation with visible downstream dependency effects; and
- 🗺️ a compact Reader for navigating a graph too large for linear notes.

The historical snapshot contains 53 active legacy Facts, 95 dependency edges,
a 21-target closure, and one explicit revocation. These numbers describe its
recorded structure, not mathematical correctness or publication status.

### 🔬 Why this is a useful `deep`-mode candidate

The mathematical question combines source interpretation, several plausible
routes, substantial computation, and a possible literature/novelty claim.
Those signals can make the following advanced features applicable: independent
clean-context panels, barriered Blackboard cross-review, long-horizon campaign
expansion, a computation lane, novelty search, and an expert synthesis pass.
Migration, source repair, fresh verification, and author confirmation would
still be separate future work.

## 🛠️ Reuse the patterns in your own work

Try prompts such as:

```text
Use $chalxius in auto mode to map this paper's main result, definitions, and
prerequisite lemmas. Keep unclear steps as Blackboard obstacles.
```

```text
Use $chalxius in deep mode to compare proof strategies for this target. Include
source checks, independent reasoning channels, computation replay, and a bounded
novelty search where applicable.
```

```text
Prepare the graph for Reader Finalize, write complete sidebar explanations, and
export one offline HTML file.
```

## 🖱️ Reader controls at a glance

- 🎯 The default view emphasizes every target.
- 📖 Click a card to open its full explanation and provenance on the right.
- 🛤️ Double-click a card or multi-target topic to expose complete connected
  paths and minimize unrelated material.
- 🧱 Use Layers to reveal optional research, learning, Reader-note, or context
  nodes.
- 🖐️ Drag cards or the canvas; use trackpad gestures to pan and zoom.
- ↩️ Use Undo/Redo for card-sizing operations.
- 🌐 Switch the interface between Chinese and English.
- 💾 Download the HTML to use the Reader offline with no network request.

## ♻️ Deterministic rebuild

The public packets and Reader pages can be regenerated with:

```sh
python3 examples/build_case_demos.py
```
