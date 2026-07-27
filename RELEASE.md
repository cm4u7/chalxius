# Chalxius v0.3.4 — Balanced reader cards and reliable graph refresh

Chalxius 0.3.4 advances the reader from renderer revision 9 to revision 11.
It includes the revision-10 export improvements and the final revision-11
visual-balance and hover-continuity fixes. Installing 0.3.3 first is not
required.

## Features

- Added Reader Finalize to `export-reader-html`.
  - Every included node must contain nonempty `summary`, `intuition`,
    `importance`, and `reasoning` content before the fixed HTML is replaced.
  - Deterministic presentation-readiness metadata is embedded in the page and
    returned by the command.
- Added a bilingual Reload graph control.
  - It reloads the latest atomically replaced HTML through same-document
    navigation.
  - It clears session-only layout, sizing, appearance, and history state.
- Unified full and compact size controls at the same 29% × 50% internal anchor,
  with zero-jump two-axis compensation.

## Fixes

- Rebalanced full-card content with narrower role-specific text measures and
  left-justified wrapped lines.
  - Control-plus-label bias is bounded to 3% across supported zoom.
  - Every role retains at least 8 model pixels of control clearance.
- Fixed edge-emphasis flicker when moving between a card body and its internal
  size button. Edge emphasis now follows the whole card hover region.
- Kept synthetic theme labels centered and preserved both Faceted and Plaques
  appearance schemes.

## Validation

- 24/24 focused reader tests passed.
- 425/425 complete inherited tests passed.
- Self-test, Python AST, JavaScript syntax, JSON parsing, manifest verification,
  and the official Skill Creator validator passed.
- Faceted and Plaques browser QA passed in Chinese and English.
- Responsive checks passed at 820 × 900 and 560 × 900.
- Full ↔ compact control movement remained exactly `(0, 0)` rendered pixels.
- Browser diagnostics contained no warnings or errors.
- Two installed exports were byte-identical:
  `efa87e99ff184f51eea286acd5305109c3e842d1045c72dac8f41da4bab2a2bb`.

## Scope boundary

This is a presentation-only reader release. It does not change:

- reader-packet schema version 1;
- Fact admission, reasoning modes, or graph authority;
- graph topology, source text, source order, or provenance;
- Chalxius Learner or Grill Me Code activation;
- project persistence or research-engine behavior.

The reader remains offline and self-contained. It adds no watcher, polling,
fetch loop, model runtime, local storage, sidecar, graph writeback, or PDF
management.

## Upgrade notes

- Direct upgrade from 0.3.2 is supported; no intermediate 0.3.3 installation or
  project migration is required.
- Export validation is stricter: packets with incomplete sidebar fields now
  fail before replacing the existing HTML.
- Existing generated pages remain unchanged until `export-reader-html` is run
  again with a complete packet.
- Reload the browser page after export to load the new deterministic file.
- Verify the distributed artifact with `SHA256SUMS`, then verify the extracted
  skill with `chalxius/MANIFEST.sha256` before installation.

## Public-source boundary

The public distribution omits local visual-QA paths, a user-specific learning
profile, and private historical forward-test evidence. Those exclusions are
non-runtime documentation only. Research-engine and reader runtime files match
the installed 0.3.4 release.

## Acknowledgements

This release acknowledges Liu et al., **Danus: Orchestrating Mathematical
Reasoning Agents with Fact-Graph Memory**, arXiv:2607.06447v2. Danus informed
the public fact-graph design and compatibility surface; it is not a runtime
dependency and no Danus source code is inherited. See
[`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) for the full citation.
