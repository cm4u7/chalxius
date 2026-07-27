# Exposition and notation closure

Use this gate whenever admitted facts are assembled into a proof narrative,
companion note, tutorial, review bundle, or PDF.  It audits communication, not
mathematical truth: a fact may remain admitted while an exposition containing it
fails this gate.

## Contents

1. Freeze scope and audience
2. Build a first-use notation ledger
3. Use independent reader roles
4. Preserve sources when making a companion
5. Render and inspect deliverables
6. Acceptance record

## 1. Freeze scope and audience

Record the exact admitted target closure used by the exposition.  State the
reader profile: assumed mathematics, rusty topics, unknown topics, language,
and whether the original source must remain unchanged.  Do not silently use
facts outside the frozen closure or silently strengthen the theorem while
simplifying it.

Build an assumption-parity table, even if it remains an internal audit artifact: for every cited
admitted fact, match each hypothesis and contract to the exact sentence or displayed definition in
the exposition.  An omitted contract is a failed gate.  A topological reformulation--for example,
replacing a full single-valued symplectic marking by an invariant Lagrangian plus coverwise dual
cycle--is a new mathematical statement and must be labelled open or independently admitted.

When an admitted fact relies on an external source, carry its applicability certificate,
`source_trace`, and `critical_audit` into the source-alignment audit. Recheck the exact
primary-source version, artifact hash, statement transcription, and locator, then compare the
narrative against both the source scope and the fact's target instantiation. Preserve every declared
typo or erratum correction explicitly. Compression must not erase a hypothesis, convention
conversion, exclusion, transport operation, bridge, correction, or source-reliability warning.

## 2. Build a first-use notation ledger

Run the mechanical inventory before reader review:

```bash
python3 -B "$SKILL_ROOT/scripts/notation_inventory.py" PROOF.md \
  --from-heading "RELEVANT HEADING" --format markdown
```

The output is conservative and may include standard notation.  It is a prompt
for semantic review, never a pass certificate.

For every nonstandard symbol, require its definition before its first semantic
use.  A definition must state enough of the following to determine the object:

- type: scalar, coordinate, point, map, cycle, chain, differential,
  bidifferential, operator, correlator, free energy, parameter, or set;
- domain and codomain, fiber, coordinate chart, and parameter dependence;
- normalization, orientation, branch, polarization, and sign convention;
- quantifiers and uniformity regime behind asymptotic notation;
- relation to earlier objects and whether the object is exact, leading-order,
  or auxiliary.

Domains must exclude critical loci where a construction is unavailable.  For degenerating
families, distinguish a lift defined on the relative smooth locus from an invariant form that may
extend meromorphically, and distinguish finite scaling-cover deck transformations from
Picard--Lefschetz monodromy on homology.

An equation alone is not always a definition.  For example, an affine curve
equation does not define the spectral data needed for topological recursion;
the projection, initial one-form, bidifferential, involution, branch points,
and normalization must also be named before correlators of that curve appear.

Create a collision table for reused glyphs.  Treat identical glyphs as
different symbols when their types, arguments, fibers, or roles differ.  Pay
special attention to:

- a base parameter versus a curve point or integration variable;
- a map versus a primitive bearing the same Greek letter;
- an $A$ or $B$ coefficient versus an $A$- or $B$-cycle;
- a kernel versus a Bernoulli number;
- a local coordinate versus a homology cycle;
- a superscript used as a polarization label rather than an exponent;
- a model object versus its family-dependent approximation.

Do not postpone essential definitions to an end glossary.  Put a compact
section ledger before first use and keep the end glossary only as a lookup aid.

## 3. Use independent reader roles

For a substantial exposition, use distinct clean-context agents when the host
supports them:

1. **Source-alignment auditor** receives the original source, frozen closure, exact external-source
   applicability and critical-audit certificates, and draft. It reproduces source and statement
   hashes, reruns the three baseline checks for every item, groups repeated source audits by hash,
   applies the baseline spot-check or strict full-search policy, and reports omissions, simple typos,
   version drift, errata/status conflicts, strengthened claims, changed conventions, lost
   transport/bridge conditions, and whether source text and corrections were preserved.
2. **Notation auditor** receives only the draft and audience profile.  It lists
   every undefined, late-defined, overloaded, or mistyped symbol with its first
   line and a proposed definition.
3. **Cold reader** attempts to follow the proof in order without access to the
   intended explanation.  It reports the first point at which the argument
   becomes nonlocal or requires guessing.
4. **Format auditor** inspects the rendered artifact, not only the Markdown.

Do not leak the writer's suspected bugs or intended fixes to a forward-test
reader.  Resolve every severity-P0 item and rerun a fresh pass.  P0 includes an
undefined load-bearing object, a symbol collision that changes meaning, missing
normalization/sign data, or a claim that depends on an unstated regime.

## 4. Preserve sources when making a companion

When the user asks to retain the original:

- never overwrite the original Markdown or PDF;
- record their hashes before and after the work;
- keep every original line in the companion in exact order, allowing only
  inserted annotations; verify this as an exact line subsequence;
- mark corrections to source typos as companion notes rather than silently
  rewriting historical text;
- use nonnested collapsible blocks and put load-bearing notation ledgers before
  the text that needs them.

## 5. Render and inspect deliverables

For PDF output, expand all collapsible definitions, render the actual final
Markdown, and inspect every page or a page contact sheet plus all high-risk
pages at full size.  Check:

- no clipped equations, tables, links, or page headers;
- no page begins with an unexplained continuation of a long callout;
- math is legible and, where the pipeline permits, searchable and copyable;
- bookmarks, metadata, page size, and source name are correct;
- internal/local links resolve in the delivered environment or are explicitly
  labeled as archival;
- the PDF contains the revised notation ledgers, not a stale render.

Keep a reproducible builder and style file with the source when a PDF is a
maintained deliverable.  Pin external renderer versions and discover local
runtime paths rather than hard-coding one machine's paths.

## 6. Acceptance record

Before delivery, report separately:

- mathematical status inherited from the fact graph;
- exposition status: notation-closed, source-aligned, and cold-reader checked;
- format status: rendered and visually inspected;
- unresolved warnings, archival links, or external comparison steps.

Never call an exposition verified merely because every source fact is admitted.
Compression, notation, ordering, and rendering can introduce new errors that do
not exist in any individual fact node.
