# External theorem applicability gate

Use this gate whenever a new fact relies on an external theorem, lemma, proposition, definition, or
formula. A citation is not a premise by itself. The proof must establish that the cited source says
the required thing and applies to the exact target object, domain, conventions, and limiting regime.
Also apply the traceability and critical-source gate in
[external_source_reliability.md](external_source_reliability.md). A theorem can be faithfully cited
and applicable but still contain a typo, a misstated quantifier, a version conflict, an erratum, or a
known counterexample.
There is no exemption merely because a result is called standard. A non-attributed fixed/local
textbook invocation may instead use the controlled closed ledger in
[elementary_result_exemption.md](elementary_result_exemption.md); everything outside that whitelist
must be proved locally, cited as an admitted predecessor, or certified here. Any load-bearing
attribution to a particular source still requires this certificate.

## Contents

1. Source fidelity before application
2. Map every hypothesis to a target witness
3. Compare conclusion strength and audit transport
4. Required certificate for new submissions
5. Independent verifier procedure

## 1. Source fidelity before application

Use the primary source. Record a stable identifier and an exact locator: source version/date,
theorem/lemma/proposition/definition/equation label, section, and page when available. Read the
definitions immediately governing the result, its proof when scope is ambiguous, and nearby remarks,
exceptions, errata, and counterexamples. Never reconstruct a theorem from an abstract, introduction,
search snippet, secondary paper, or another model's summary.

Freeze the exact artifact and theorem statement under the source-evidence
revision required by the task card before mapping hypotheses. A prospective
0.4.3 V5 card requires v4; frozen compatibility cards may require v3. Hash the
source bytes and exact UTF-8 transcription, run the three baseline sanity checks
for every item, and reuse one hash-bound version/erratum/status audit per exact
source artifact. Escalate formulas, bridge/transport, degeneration, target-
critical uses, corrections,
conflicts, and suspicious checks to the five-check strict profile. Do not silently repair source
text.

Write down separately:

- the source's ambient category and object type;
- every explicit and inherited hypothesis, including definitions referenced by the statement;
- the exact conclusion, quantifiers, parameter range, topology, and uniformity;
- source conventions: signs, normalization, orientation, branches, coordinates, polarization, and
  stable/unstable or genus range;
- stated exclusions and whether the result is local, coverwise, sectorial, formal, asymptotic,
  analytic, smooth-family, nodal, compact/proper, toric, or model-specific.
- the polarity and dependency of every quantified choice: whether a neighborhood, exceptional set,
  coordinate, marking, branch, orientation, or normalization is universal, existential, canonical,
  or allowed to depend on earlier parameters.

If the exact primary source cannot be opened by the independent verifier, the application is not
admissible. Put it in exploration memory until source access is restored or a suitable primary-source
extract is added under an independently hash-checked artifact protocol.

### Formula and glyph fidelity

Classify every imported displayed equation, coefficient identity, operator formula, or sign-sensitive
normalization as `use_kind="formula"`. Plain PDF text extraction and OCR are not faithful to bracket
scope, an outer differential, accents, subscripts, superscripts, minus signs, or operator binding.
Workflow schema v3 therefore requires a sibling `source_fidelity` object:

```json
{
  "source_fidelity": {
    "artifact_sha256": "64 lowercase hex characters",
    "inspection_methods": ["source_tex", "rendered_primary"],
    "load_bearing_tokens": [
      "d_z is outside the bracket",
      "the second summand has a minus sign"
    ],
    "finding": "Exact transcription and the discrepancy with extracted plain text.",
    "proof_anchor": "[SRC:SOURCE_KEY:GLYPH]"
  }
}
```

At least one inspection method must be `source_tex` or `rendered_primary`. Hash the exact primary
artifact that was inspected. List every token whose placement could change the mathematical claim,
and put the `[SRC:...]` anchor exactly once beside the independent transcription check in the hashed
proof. If source TeX and the rendered primary page disagree, stop in exploration memory and report the
conflict. Do not evade the gate by labelling a displayed formula as a generic `result`.

## 2. Map every hypothesis to a target witness

For each source hypothesis `H_i`, name the exact target object instantiating it and give a proof
witness. The witness must be either a cited admitted predecessor or an argument in the current hashed
proof. Similar terminology is not a witness. Check at least these mismatch classes when relevant:

- smooth fiber versus a nodal limit; punctured disc versus the central fiber;
- fixed curve or fixed coordinate versus a moving family or moduli derivative;
- compact/proper/algebraic versus noncompact/analytic/formal;
- toric/model spectral curve versus an arbitrary spectral curve;
- full marking versus invariant polarization versus coverwise marking;
- local/sectorial/coverwise statement versus a single-valued statement on the full base;
- correlators with `n >= 1` versus the unstable or integrated `n = 0` free energies;
- leading singular asymptotic versus a full gap statement with forbidden subleading poles;
- pointwise convergence versus uniform convergence sufficient to exchange a limit with a residue,
  sum, integral, derivative, recursion, or analytic continuation.

An unstated bridge between two rows is a new lemma, not “standard compatibility.” Prove it as an
admitted predecessor or in the current atomic proof.

An existential witness is not a canonical target object. In particular, from “there exists a finite
set E such that the conclusion holds outside E” and a direct verification of the conclusion at one
point f, one may not infer f is outside the source's chosen E. One may replace E by E minus {f} only
after proving that every promised conclusion holds at f, so the smaller set remains a valid witness.
Apply the same rule to chosen neighborhoods, coordinates, markings, branches, and orientations.

### Applicability does not disappear after admission

When a certified external conclusion is later consumed through an admitted predecessor, the
descendant does not reopen that predecessor's source certificate, but it must still satisfy every
scope restriction and hypothesis written in the predecessor statement. Admission certifies the
theorem only on that stated interface; it does not make the conclusion polymorphic over new ambient
categories. A descendant that changes fixed to moving, globally meromorphic to logarithmic-atlas,
connected to componentwise, smooth to degenerate, or coverwise to descended must prove that new
bridge itself. If the predecessor statement omitted a condition needed for safe reuse, first issue a
corrected atomic replacement rather than recovering the condition from predecessor proof text.

## 3. Compare conclusion strength and audit transport

State the exact delta used from the source. Classify the source conclusion as `exact`,
`source_stronger`, or `bridged`. Never upgrade a weaker conclusion. In particular, a theorem giving a
universal leading coefficient does not by itself give pole exclusion; a theorem for normalized
correlators does not automatically give an integrated free energy; and a theorem on a fixed smooth
curve does not automatically commute with degeneration.

List every operation between the literal source conclusion and the target conclusion: specialization,
base change, pullback/descent, coordinate change, analytic continuation, differentiation,
integration, residue, summation, recursion, or passage to a limit. Each operation needs its own
justification and proof anchor. If none occurs, use an empty list rather than silently omitting the
field.

The only admissible applicability verdicts are:

- `direct`: every source hypothesis and convention is matched and no unproved transport is needed;
- `bridged`: the mismatch is repaired by an explicit bridge statement and proof;
- not applicable: do not submit the fact; record the failed route in exploration memory.

## 4. Required certificate for new submissions

Use one certificate for one exact labeled result, definition, or formula and
one delta conclusion. If one paper supplies several logically distinct items,
split them into separate keys such as `HMO26-T5.1` and `HMO26-R2.3` rather than
hiding several applications in one broad locator. The excerpt below is the
source-evidence-v3 compatibility shape retained for frozen cards. Its
`source_trace` and `critical_audit` siblings are defined in
[external_source_reliability.md](external_source_reliability.md).

```json
{
  "key": "SOURCE_KEY",
  "title": "Primary-source title",
  "arxiv": "arXiv:YYMM.NNNNNvN",
  "use_kind": "result",
  "cited_for": "Exact delta conclusion used in this fact",
  "applicability": {
    "source_version": "arXiv vN or named published edition",
    "source_locator": "Theorem X.Y, version vN, p. Z",
    "source_scope": "Ambient objects, domain, quantifiers, and parameter range",
    "target_scope": "The exact objects and regime in the submitted fact",
    "source_conclusion": "Literal mathematical strength of the source result",
    "used_conclusion": "Exact conclusion imported into this proof",
    "hypothesis_map": [
      {
        "source_hypothesis": "H1 from the source, including inherited definitions",
        "target_witness": "Why H1 holds here and where it is proved",
        "proof_anchor": "[APP:SOURCE_KEY:H1]"
      }
    ],
    "convention_map": [
      {
        "source_convention": "Source normalization/sign/branch",
        "target_convention": "Target convention and conversion, if any",
        "proof_anchor": "[APP:SOURCE_KEY:C1]"
      }
    ],
    "transport_obligations": [
      {
        "operation": "Limit, residue, base change, integration, or other transport",
        "justification": "The precise theorem or argument permitting it",
        "proof_anchor": "[APP:SOURCE_KEY:T1]"
      }
    ],
    "exclusions_checked": [
      "Nearby Remark X.Z and Definition X.0 checked; no additional exclusion applies"
    ],
    "strength_comparison": "exact",
    "verdict": "direct",
    "proof_anchor": "[APP:SOURCE_KEY:USE]"
  }
}
```

`use_kind` is `result`, `definition`, or `formula`. Every use needs a nonempty `hypothesis_map` and
`convention_map`: definitions and formulas inherit ambient assumptions too, and an unconditional
item should receive an explicit ambient `H0` entry. Write an explicit no-material-difference
convention entry when appropriate. Use a stable primary-source identifier in
one of `doi`, `arxiv`, `url`, `isbn`, `mr`, or `zbmath`.

External-source evidence v3 binds source bytes, a statement transcription,
three mandatory baseline checks, strict escalation triggers, one hash-bound
source-level status audit with bounded reuse, the source-reliability
disposition, and unique `[CRIT:...]` proof anchors. Applicability-only and
source-evidence-v2 certificates remain historical evidence.

For a newly frozen 0.4.3 V5 assurance contract, use source-evidence v4. Its
applicability rows add:

- one `source_coverage_id` on every hypothesis row;
- typed convention `conversion_kind` values;
- typed transport records with stable `transport_id`, source and target object
  types, and an optional validated contour-substitution object;
- a nonempty `conclusion_map` linking literal source-conclusion spans and target
  proof anchors to those transports.

The complete source transcription separately binds exact coverage rows for all
hypotheses, the source conclusion, and the used conclusion. Different
conclusion language or object type requires a referenced transport; prose in a
convention row cannot supply it. Current source-status searches must transport
their frozen response artifacts or an exact narrow live-query capability, and
their mechanically derived status summary must agree with the narrative. See
the reliability reference for the full exact schema.

For a bridged use, set both `strength_comparison` and `verdict` to `bridged`, and add:

```json
{
  "bridge_statement": "Exact lemma closing the source-to-target mismatch",
  "bridge_proof_anchor": "[APP:SOURCE_KEY:BRIDGE]"
}
```

Every certificate proof anchor must occur exactly once in the fact's hashed proof, next to the
corresponding mathematical argument. The certificate is submission-hash-bound; the anchors prevent
scope-bearing applicability claims from living only in mutable bibliography metadata.

For `use_kind="formula"`, add the `source_fidelity` sibling shown above. Its `[SRC:...]` anchor is
separate from the certificate's `[APP:...]` anchors: applicability checks whether the formula may be
used, while source fidelity checks what symbols the primary artifact actually contains.
For every bound round, `source_fidelity.artifact_sha256` must also match one
declared assignment artifact whose bytes pass the engine's hash check. Formula-
bearing direct submissions are rejected; use the frozen round workflow. Under
the current assurance contract, Research formula use additionally requires an
artifact-bound toy check and any fixed-object-to-family strengthening requires
an explicit bridge artifact.

## 5. Independent verifier procedure

The verifier may read the frozen packet and open the exact primary-source and issue-search locators
named in its certificates. It may repeat the narrowly targeted reliability searches prescribed
below, but must not search for a more convenient replacement theorem or use secondary summaries to
establish a correction. It first inventories every external attribution and named result used in the proof; an
external logical source use without a certificate is a gap even when `external_refs` is empty, while
any declared elementary invocation is judged under the separate closed-ledger policy. For each
certificate it independently reconstructs the source hypothesis list and compares
it with the submitted list, then checks every target witness, convention, exclusion, conclusion
strength, transport step, and bridge. Missing source access, an inexact locator, version drift, an
omitted inherited hypothesis, or an unsupported bridge requires `verdict="reject"` with a named gap.

It also reproduces each `source_trace`, compares the statement transcription with source TeX or the
rendered primary page, and repeats the three baseline checks for every item. It groups status evidence
by `source_audit.audit_sha256`, verifies each distinct source audit and reuse record once, and performs
the current spot-check/full-search policy specified in
[external_source_reliability.md](external_source_reliability.md). It repeats the two additional
sanity checks for strict items and rejects or escalates any baseline misclassification. It must not
trust the worker's `as_stated` or correction classification. A minor typo is usable only when the
correction is unique, non-semantic, non-strengthening, and proof-bound; an official erratum must
have an exact locator and artifact hash. Any ambiguous, material-unofficial, contradicted, retracted,
or unresolved source claim requires rejection and a new local proof or source route.

For every formula use, independently inspect source TeX or the rendered primary page and compare every
declared load-bearing token with the proof transcription. Reject a missing or misplaced differential,
operator, bracket, sign, index, exponent, or normalization. Text extracted from the PDF is only a
search aid and cannot satisfy this check.

The combined gates perform a bounded source-critical audit; they do not prove the external theorem
or make an LLM verifier infallible. Preserve expert human review for publication-grade work.
