# Chalxius v0.3.5 — Readable math, topic paths, and safer graph layout

Chalxius 0.3.5 advances the offline Reader to renderer revision 12. It improves
dense-map reading and public onboarding while preserving the same research
authority and Fact-admission boundaries.

## Reader improvements

- Mathematical detail now scales visibly with the existing 90%-150% text-size
  control. MathJax SVG output is no longer constrained by the global icon size,
  and exact TeX source uses the panel-relative scale.
- Multi-target topics use smooth, dashed, arrowless bezier links instead of
  orthogonal routes.
- Double-clicking a topic performs one undoable sizing action over the union of
  every eligible member target's complete upstream and downstream chains.
- Initial placement and explicit Reset layout now run a deterministic,
  fixed-sweep weighted-barycentric search for graphs with at most 1,200 cross-
  rank edges.
  - Packet order is the baseline.
  - Exact proper-crossing count is the primary score.
  - A candidate is retained only when its score is strictly better.
  - The final layout therefore never has more scored crossings than the packet-
    order baseline; larger graphs keep packet order.
  - This is a bounded readability heuristic, not a global-optimum claim.
- Card sizing, topic sizing, undo/redo, and layer filtering still do not rerun
  layout, so the reader's working positions remain stable.

## Clearer public introduction

- The README now explains Chalxius's features, authority classes, Fact-
  admission flow, correction model, Learner, Reader, and installation without
  assuming prior knowledge.
- `fast`, `auto`, and `deep` are introduced directly, including when to choose
  `fast` or `deep` and the invariant admission standard they share.
- Current-facing wording consistently names the Chalxius research engine;
  predecessor terminology is confined to exact compatibility identifiers where
  changing it would invalidate frozen project hashes.
- Two public, self-contained Reader demonstrations and screenshots are now
  included through [`USE_CASES.md`](USE_CASES.md) and the GitHub Pages gallery.

## Validation

- Focused Reader suite: 25/25 PASS.
- Complete suite: 426/426 PASS, both before packaging and from cold public and
  local-install archives.
- Self-test, official Skill Creator validation, Python AST, JSON parsing,
  JavaScript syntax, exact-tree manifests, deterministic archive rebuilding,
  and cold extraction: PASS.
- A synthetic layout fixture improved from one crossing to zero. The guarded
  x-y public case stayed at one crossing rather than accepting a seven-crossing
  candidate; the philosophy case stayed at three.
- Topic double-click changed the guarded case from 2 full / 6 minimized cards
  to 8 full / 0 minimized cards and selected the topic detail.
- At 100% -> 150%, the measured detail font changed 15 -> 22.5 px, exact TeX
  12.3 -> 18.45 px, and MathJax 16.2 -> 24.3 px.
- Browser warnings and errors: none.
- Local transactional upgrade from 0.3.4: PASS, with the prior version preserved
  as a recoverable rollback.

See [`VALIDATION.md`](VALIDATION.md) for hashes and bounded evidence.

## Scope boundary

This release does not change:

- Reader packet schema version 1;
- the Fact-admission contract or its hash;
- the reasoning-mode policy object or its hash;
- graph topology, source authority, source order, or provenance;
- Chalxius Learner activation rules; or
- any research project or Fact Graph.

The Reader remains offline and self-contained. It adds no watcher, polling,
fetch loop, model runtime, local storage, sidecar, graph writeback, or PDF
management. Its metadata continues to report `truth_effect="none"`.

The x-y interchange page is explicitly a **potential application only**. Its
predecessor archive does not pass the current workflow audit, was not created by
0.3.5, and has not been confirmed by the relevant authors.

## Upgrade notes

- Existing generated pages remain unchanged until `export-reader-html` is run
  again with a complete Reader packet.
- After export, use Reload graph or reload the browser page to load the newly
  replaced fixed HTML file.
- Verify the public archive with `SHA256SUMS`, then verify the extracted skill
  with `chalxius/MANIFEST.sha256` before installation.

## Acknowledgements

Chalxius acknowledges Liu et al., **Danus: Orchestrating Mathematical
Reasoning Agents with Fact-Graph Memory**, arXiv:2607.06447v2, as a separate
published system whose public design informed the fact-graph layout. It is not
a runtime dependency and no Danus source code is inherited.

Chalxius also thanks **Matt Pocock** for the public
[`/grill-me`](https://github.com/mattpocock/skills/blob/main/docs/productivity/grill-me.md)
requirements-interview design. This is design attribution, not a runtime
dependency. See [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md).
