# Tiered external-source traceability and critical audit

Use this gate together with
[external_theorem_applicability.md](external_theorem_applicability.md) for every new external
theorem, lemma, proposition, definition, or formula. Applicability asks whether the source result
implies the desired target conclusion. This gate asks whether the exact statement was recovered
faithfully and whether cheap internal checks or known issue signals make it unsafe to use.

This is a bounded critical audit, not a proof that the external theorem is true. Require expert human
review for publication-grade mathematics.

## Contents

1. Freeze the exact source and statement
2. Audit source status once per exact artifact
3. Select baseline or strict theorem review
4. Run theorem-level sanity checks
5. Classify defects and corrections
6. Record source-evidence v3
7. Verify independently without duplicate work
8. Preserve historical evidence

## 1. Freeze the exact source and statement

Use an exact primary artifact, not an abstract, search snippet, secondary citation, OCR transcript,
or model summary. For arXiv, pin the explicit `vN` identifier and download that version's source or
PDF. Do not use an unversioned `/abs/ID` or `/pdf/ID` URL as the artifact locator. For a published
edition, pin the DOI/edition and exact artifact actually inspected.

Record in `source_trace`:

- SHA-256 of the exact inspected artifact bytes;
- an absolute versioned artifact locator;
- retrieval date in `YYYY-MM-DD`;
- exact theorem/lemma/proposition/definition/equation locator;
- the complete load-bearing statement transcription and its UTF-8 SHA-256;
- whether source TeX or the rendered primary artifact was inspected.

Include inherited qualifiers that can change the logical interface: quantifiers, object types,
parameter ranges, exclusions, locality, uniformity, topology, normalization, and the exact
conclusion. Set `statement_locator` equal to `applicability.source_locator`.

Use PDF text extraction or OCR only to find the passage. Compare the transcription against source
TeX or the rendered page before hashing it. A formula additionally needs `source_fidelity`, and its
artifact hash must equal `source_trace.artifact_sha256`.

If the artifact later downloads with a different hash, stop. Resolve the version or repository
discrepancy before using the result. Matching titles or arXiv numbers do not substitute for matching
bytes.

## 2. Audit source status once per exact artifact

Version history, errata, retraction status, and paper-level counterexample signals normally apply to
the source artifact, not separately to each theorem. Run these three searches once for each exact
artifact SHA-256:

1. `version_history`: compare relevant arXiv versions or named editions and record statement drift;
2. `errata`: inspect official author, journal, publisher, or repository correction pages and run an
   exact-title/identifier query with `erratum` or `correction`;
3. `retraction_or_counterexample`: inspect official status pages and run an exact-title/identifier
   query with `retraction`, `counterexample`, or `false`.

Record the check date, exact queries, absolute locators, concrete findings, an overall finding, and
`unresolved_signals`. An admissible source audit has an empty `unresolved_signals` list.

Compute `source_audit.audit_sha256` as SHA-256 of the canonical UTF-8 JSON object containing every
`source_audit` field except `audit_sha256`, with keys sorted, no insignificant whitespace, and
non-ASCII characters preserved. The engine recomputes this hash.

### Reuse rule

Reuse only when the exact artifact SHA-256 and artifact locator match and the reuse date is no more
than 30 days after `source_audit.checked_at`.

- For a newly performed audit, use `mode="fresh"`, `origin="current_submission"`, and set
  `reused_at` equal to `checked_at`.
- For another source item in the same submission, copy the identical `source_audit`, use
  `mode="reused"`, and set `origin="external_ref:FIRST_KEY"`.
- For a record copied from an admitted fact, use `mode="reused"` and
  `origin="fact:FACT_ID:SOURCE_KEY"`.

When one submission cites several items from identical artifact bytes, the engine requires one
identical source audit and requires every later item to reuse the first source key. Reuse saves status
searches only. It never exempts the new theorem statement from exact transcription, statement hash,
applicability mapping, or theorem-level sanity checks.

Refresh the source audit immediately when the reuse window expires, the artifact changes, a search
locator becomes unavailable, a new version or correction appears, any unresolved signal is found, or
the verifier sees a conflicting current result.

## 3. Select baseline or strict theorem review

Use `profile="baseline"` only when all of these conditions hold:

- `use_kind` is `result` or `definition`, not `formula`;
- the applicability verdict is direct and has no transport obligation;
- the source is used as stated, with no suspected defect or correction;
- no version/text conflict or source-status signal is present;
- the result is not target-critical and does not carry a declared high-risk feature.

Baseline uses an empty `risk_triggers` list.

Use `profile="strict"` whenever any of these applies, and name at least one exact trigger:

- `formula_or_sign_sensitive`;
- `version_or_text_conflict`;
- `suspected_source_defect`;
- `official_correction`;
- `applicability_bridge_or_transport`;
- `boundary_or_toy_case_concern`;
- `statement_proof_tension`;
- `target_critical`;
- `degeneration_or_limit`;
- `verifier_escalation`.

The engine forces strict mode for formula use, any bridge or transport, a minor typo correction, and
an official erratum. The worker must also declare semantic risks that code cannot infer, especially
target-critical use, degeneration, delicate signs/coefficients, or suspicious proof behavior. A
verifier that finds an omitted risk must reject or escalate the item; baseline is not a loophole.

## 4. Run theorem-level sanity checks

Record each performed check exactly once with status `pass`, `issue`, or `not_applicable` and a
concrete finding. Do not write only “checked.”

Every profile requires these three cheap checks:

### `notation_and_binding`

Check that every symbol is introduced and used consistently in nearby definitions and the proof.
Look for changed variable names, unbound indices, missing decorations, swapped subscripts, wrong
labels, or one symbol standing where another is forced.

### `type_and_domain`

Check that both sides of relations have compatible types and domains. Substitute declared objects
into maps, operators, integrals, sums, and limits. A point used as a function, an index outside its
range, or a map evaluated outside its domain is a source defect even when the repair seems obvious.

### `quantifiers_and_scope`

Compare `for every`, `there exists`, uniqueness, dependency of choices, exclusions, parameter
ranges, and local/global or pointwise/uniform scope with the proof. Look for missing negations,
reversed implications, strict/non-strict inequalities, endpoint errors, or scope words present in
only one place.

Strict profile additionally requires:

### `boundary_or_toy_case`

Test the smallest legal index, an endpoint, a zero or identity object, a dimension-one case, or
another cheap example. Use symbolic or exact computation when practical. If no honest toy case
exists, use `not_applicable` and explain why.

### `statement_proof_consistency`

Read enough of the proof to confirm that it establishes the literal statement rather than a nearby
variant. Track the final quantified conclusion and hypotheses introduced during the proof. A proof
of a corrected theorem is evidence of a source issue, not permission to rewrite the statement
silently.

For a result use, the three baseline checks and `statement_proof_consistency` cannot be
`not_applicable`; only `boundary_or_toy_case` may be inapplicable with a concrete reason.

## 5. Classify defects and corrections

Only these assessments may enter a new submission:

- `as_stated`: all required checks pass, no issue is declared, and the source audit has no unresolved
  signal;
- `minor_typo_corrected`: an unambiguous, non-semantic typo is uniquely forced by nearby definitions,
  the proof, or another exact version;
- `official_erratum_applied`: an official correction is pinned by its exact locator and artifact
  SHA-256, and the proof uses precisely the corrected statement.

Every correction requires strict profile. Record literal source text, corrected text, evidence,
impact, and one unique `[CRIT:SOURCE_KEY:LABEL]` proof anchor. Bind the overall assessment with a
separate `[CRIT:SOURCE_KEY:USE]` anchor.

Do not submit the source use when:

- the intended correction is ambiguous;
- the change is material without an exact official erratum;
- the statement conflicts with definitions, proof, or a toy case;
- versions conflict and no controlling version resolves them;
- a proof gap, counterexample, retraction, or artifact mismatch remains;
- the verifier cannot reproduce source trace or required current checks.

Record that route in exploration memory. Then prove the statement locally, cite a different exact
source through a new certificate, or submit a corrected atomic lemma through the ordinary independent
review gate. Never attribute a locally repaired theorem to the uncorrected source.

## 6. Record source-evidence v3

Every new `external_refs` item contains:

```json
{
  "source_evidence_version": 3,
  "source_trace": {
    "artifact_sha256": "64 lowercase hex characters",
    "artifact_locator": "https://arxiv.org/pdf/2604.25622v3",
    "retrieved_at": "2026-07-24",
    "statement_locator": "Theorem 2.1, arXiv v3, p. 7",
    "statement_text": "Exact UTF-8 load-bearing statement transcription",
    "statement_sha256": "SHA-256 of statement_text UTF-8 bytes",
    "inspection_methods": ["source_tex", "rendered_primary"]
  },
  "critical_audit": {
    "profile": "baseline",
    "risk_triggers": [],
    "sanity_checks": [
      {
        "kind": "notation_and_binding",
        "status": "pass",
        "finding": "Concrete finding"
      },
      {
        "kind": "type_and_domain",
        "status": "pass",
        "finding": "Concrete finding"
      },
      {
        "kind": "quantifiers_and_scope",
        "status": "pass",
        "finding": "Concrete finding"
      }
    ],
    "source_audit": {
      "artifact_sha256": "same artifact SHA-256",
      "artifact_locator": "same exact artifact locator",
      "checked_at": "2026-07-24",
      "issue_searches": [
        {
          "kind": "version_history",
          "query": "Exact identifier version history",
          "locator": "https://example.org/exact-version-history",
          "finding": "Concrete finding"
        },
        {
          "kind": "errata",
          "query": "Exact title erratum correction",
          "locator": "https://example.org/exact-errata-result",
          "finding": "Concrete finding"
        },
        {
          "kind": "retraction_or_counterexample",
          "query": "Exact title retraction counterexample false",
          "locator": "https://example.org/exact-status-result",
          "finding": "Concrete finding"
        }
      ],
      "unresolved_signals": [],
      "finding": "Why the source-level status is clear",
      "audit_sha256": "canonical hash of this object without audit_sha256"
    },
    "source_audit_reuse": {
      "mode": "fresh",
      "reused_at": "2026-07-24",
      "origin": "current_submission"
    },
    "assessment": "as_stated",
    "issues": [],
    "justification": "Why this theorem is safe under the selected bounded profile",
    "proof_anchor": "[CRIT:SOURCE_KEY:USE]"
  }
}
```

Strict items use all five sanity-check kinds and a nonempty `risk_triggers` list. For
`minor_typo_corrected`, add a `kind="typo"` issue with `impact="non_semantic"`. For
`official_erratum_applied`, use `kind="official_erratum"` and include `correction_locator` and
`correction_sha256`.

## 7. Verify independently without duplicate work

Give the fresh verifier the frozen packet. It may open only the exact source and source-audit
locators, plus the prescribed narrow current status queries.

For every source item, require the verifier to:

1. compare the exact statement transcription with source TeX or the rendered primary page;
2. reproduce the statement hash and the three baseline sanity checks;
3. verify applicability, conventions, exclusions, conclusion strength, and transports;
4. reject or escalate any item incorrectly labelled baseline.

For each distinct `source_audit.audit_sha256`, not each theorem, require it to:

1. reproduce the source artifact and source-audit hashes;
2. check exact-artifact binding and reuse provenance;
3. inspect all three stored search locators once;
4. for a baseline-only group, repeat at least one unpredictably selected current status query;
5. if any grouped item is strict, repeat all three current status searches.

For every strict item, additionally repeat `boundary_or_toy_case` and
`statement_proof_consistency`. Verify each correction and `[CRIT:...]` anchor exactly. Reject any
undisclosed, ambiguous, material-unofficial, contradicted, retracted, or unresolved defect.

For \(k\) low-risk theorem items from one artifact, this policy performs three source-status searches
once plus three cheap theorem checks per item. It does not perform three status searches and five
theorem checks \(k\) times. Strict items pay the heavier cost only where the declared or observed
risk justifies it.

## 8. Preserve historical evidence

Applicability-only and source-evidence-v2 certificates remain readable historical trust. Do not
rewrite admitted evidence or claim that it passed v3 tiering. Any new source use or corrected
citation must create a new source-evidence-v3 submission.
