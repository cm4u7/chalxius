# Chalxius use cases

This page assumes no prior knowledge of Chalxius. Chalxius keeps source text,
interpretation, audit, exploration, admitted Facts, and learning evidence in
separate authority classes. The examples below show why that separation is
useful. Their interactive maps are presentation-only: clicking, rearranging, or
resizing a card cannot change research data or admit a Fact.

## Demonstrated workflow: philosophy argument audit

[Open the interactive HTML](https://cm4u7.github.io/chalxius/cases/philosophy.html)
or inspect the [hash-bound public case snapshot](docs/cases/philosophy.source.md).

[![Philosophy workflow Reader preview](docs/assets/philosophy-case.png)](https://cm4u7.github.io/chalxius/cases/philosophy.html)

A private workflow built around a previously published philosophy paper was
audited read-only and then summarized without identifying the paper, its author,
or the private argument. The workflow separated exact source anchors from
interpretive reconstruction, required independent source-fidelity and
graph-structure review, and retained rejected or superseded revisions as
history.

The current read-only audit passed. The important result is structural: the
Fact Graph still contained zero admitted Facts and zero candidates. A clean
workflow therefore did not silently convert an interpretation, objection, or
teaching note into a trusted premise.

The interactive map shows two conclusions:

1. a philosophical argument can be reconstructed in a source-bound form; and
2. Paper, Audit, Blackboard, Learner, and Fact authority can remain separate.

This does **not** prove a philosophical position, establish a uniquely correct
interpretation, cover an entire literature, confirm authorial intent, or replace
academic peer review. The underlying artifact predates current unified-write
activation and remains read-only until a separate future activation workflow is
explicitly started.

## Potential application: x-y interchange research

> **Status: potential application only.** The predecessor archive was not made
> with Chalxius 0.3.5, does not pass the current Chalxius workflow audit, and
> has not been confirmed by the relevant authors.

[Open the guarded interactive HTML](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html)
or inspect the [hash-bound public case snapshot](docs/cases/xy-swap-potential.source.md).

[![Potential x-y interchange Reader preview](docs/assets/xy-swap-potential-case.png)](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html)

A private predecessor archive studies how exchanging the two coordinate
functions of a spectral curve may affect topological-recursion free energies.
The public case deliberately withholds its unpublished mathematical conclusion.
Observed workflow features include a content-addressed dependency graph,
target-closure checks, frozen candidate packets, independent review, replayable
computational evidence, and explicit revocation.

At the audited snapshot the archive contained 53 active legacy Facts, 95
dependency edges, a 21-target closure, and one explicit revocation. Those
numbers describe historical workflow state. They do not recertify a legacy
Fact, establish mathematical correctness, or imply publication or endorsement.

A current Chalxius read-only audit found no graph-structure error and found the
recorded history internally consistent, but the overall result was not PASS:
thirteen legacy rounds fail newer source-evidence requirements and inherited
warnings remain. No current-format Paper store, Blackboard store, or Chalxius
Reader export was found in the predecessor project.

The interactive map therefore starts with the blockers and only then shows a
possible future use: an explicit migration could separate source
reconstruction, audit, exploration, verifier-gated Facts, and Reader
presentation. Migration, evidence repair, fresh review, and external author
confirmation would all be separate future work.

## Reading the maps

- The default view emphasizes every target.
- Click a card to read its summary, intuition, importance, reasoning, and
  provenance in the right panel.
- Double-click any card—or a multi-target topic—to enlarge its complete
  upstream and downstream chain while minimizing unrelated cards.
- Use the Layers control to reveal optional research, learning, or Reader-note
  material.
- Drag cards or the canvas, use a trackpad to pan and zoom, and use Undo/Redo for
  sizing actions.
- The two HTML files are self-contained and offline after download. They make
  no network request and have `truth_effect="none"`.

The case packets and pages can be rebuilt deterministically with:

```sh
python3 examples/build_case_demos.py
```
