# Controlled elementary-result exemption

This is a narrow alternative to an external-source applicability certificate for a fixed, local,
textbook-level step that a packet-only verifier can reconstruct without consulting a source. It
reduces citation bureaucracy; it does not relax mathematical verification.

Use this lane only when all of the following hold:

1. The proof invokes a result instead of fully proving it. A calculation or argument already carried
   out in the hashed proof needs no ledger entry.
2. The result belongs literally to the closed category list below.
3. Every hypothesis has an explicit witness in the current fact or an admitted predecessor
   statement.
4. The imported conclusion is local/fixed and no stronger than the elementary result.
5. The `reconstruction` gives enough detail for the verifier to reproduce the step from the packet.
6. No conclusion depends on parameter-uniform estimates, degeneration, transport, topology,
   monodromy, a global normalization, or a source-specific formula/sign/coefficient.
7. The result is not attributed to a particular external source. Once a paper, book, or exact
   external formulation is load-bearing, use an external-source certificate instead.

The words `standard`, `classical`, `elementary`, `well known`, or `clear` never satisfy these
conditions by themselves.

## Closed category list

- `elementary_limit_series`: fixed-variable elementary limits, geometric/power-series manipulations,
  and termwise estimates whose convergence domain is checked in the packet.
- `finite_algebra`: finite polynomial/rational manipulation, factorization, discriminant or
  coefficient calculation, with every denominator and branch condition checked.
- `finite_linear_algebra`: finite-dimensional rank, determinant, change-of-basis, or uniqueness
  arguments with dimensions and nondegeneracy checked.
- `one_variable_cauchy`: the one-variable Cauchy formula/estimate and Laurent coefficient extraction
  on an explicitly contained circle or annulus.
- `iterated_polydisc_cauchy`: iterated one-variable Cauchy on an explicitly contained fixed
  polydisc. This does not cover arbitrary domains or parameter-uniform radii.
- `residue_winding`: the local residue theorem, winding-number evaluation, or coefficient/residue
  identification on an explicitly oriented fixed contour avoiding singularities.
- `identity_removability`: the one-variable identity theorem or removable-singularity criterion
  after connectedness, boundedness/vanishing, and punctured-domain hypotheses are exhibited.
- `local_inverse_implicit`: the finite-dimensional holomorphic inverse/implicit-function theorem at
  one explicitly specified point after the relevant Jacobian minor is computed nonzero. It yields
  only the local germ asserted by that theorem.
- `basic_metric_compactness`: elementary continuity, sequential compactness, finite subcovers, and
  uniform continuity on an explicitly fixed compact metric set. It does not include normal-family,
  moduli-compactness, or degeneration theorems.

If a plausible step does not fit one category literally, do not create a new category ad hoc. Prove
it, promote it to a separately reviewed predecessor, or supply an external-source certificate.

## Always outside the exemption

The following require a proof, an admitted predecessor, or an exact external-source certificate:

- Weierstrass preparation/division and substantive analytic factorization;
- existence or parameter-holomorphic variation of relative differentials, normalized Bergman
  kernels, period matrices, or other objects in a moving family;
- plumbing/sewing, stable reduction, topology change, marking completion, Picard--Lefschetz,
  Ehresmann, Riemann--Hurwitz, Dehn twists, or monodromy/descent;
- global compact-Riemann-surface normalization, Riemann bilinear relations, Abelian-differential
  existence, or global moduli statements;
- topological-recursion identities, special geometry, dilaton equations, graph-sum/DOSS formulas,
  free-energy integration, or model-to-general-curve transfer;
- any source-specific displayed formula, leading coefficient, sign, branch, bracket, index,
  differential, or normalization;
- a conclusion containing `uniform`, `for all nearby parameters`, `through the degeneration`,
  `single-valued`, `canonical`, `global`, `descends`, or an analogous transport claim unless the
  submitted proof independently establishes that extra assertion.

This boundary is intentionally asymmetric: the elementary theorem may be familiar, while a
family/global upgrade of it is not elementary.

## Submission schema

Add optional `elementary_uses` to a schema-v3 `fact_submission`. Use one entry per invocation:

```json
{
  "key": "IFT1",
  "result": "Holomorphic inverse-function theorem at one point",
  "category": "local_inverse_implicit",
  "hypothesis_witnesses": [
    "The displayed Jacobian determinant at (0,0) equals 1."
  ],
  "used_conclusion": "There is a unique holomorphic inverse germ near the displayed point.",
  "scope_limitations": [
    "Local germ only.",
    "No uniform parameter radius, continuation, or monodromy conclusion."
  ],
  "reconstruction": "Apply the finite-dimensional holomorphic IFT to the displayed map and the computed nonzero determinant; restrict both source and target to sufficiently small neighborhoods.",
  "proof_anchor": "[ELM:IFT1]"
}
```

Keys contain only ASCII letters, digits, dot, underscore, or hyphen and are unique. The anchor must
be exactly `[ELM:KEY]` and occur exactly once in the hashed proof beside the invocation. All fields
are submission-hash-bound. Separate invocations with materially different hypotheses or conclusions
need separate entries.

The engine validates the schema, whitelist, and proof-anchor binding. It cannot decide whether the
mathematics really stays inside the category; that is a mandatory verifier judgment.

## Verifier decision procedure

For every ledger item:

1. Locate its unique `[ELM:...]` anchor and identify the exact inference.
2. Check that the named result is literally within the declared category.
3. Check each hypothesis witness against the proof and admitted predecessor statements.
4. Reconstruct the inference using only the packet.
5. Compare the reconstructed conclusion with `used_conclusion`.
6. Enforce every `scope_limitations` item against the statement and all downstream uses in the same
   proof.
7. Search the inference for a hidden family/global/transport/source-fidelity claim.

Reject the fact if any step fails. Do not repair an ineligible ledger item by browsing for a theorem;
the worker must resubmit it with a proof, predecessor, or applicability certificate.

Examples from the conifold-gap audit:

- `r |log r| -> 0` after setting `r=e^{-s}` is eligible under
  `elementary_limit_series`.
- a displayed finite discriminant computation is eligible under `finite_algebra`.
- a local holomorphic inverse after a displayed nonzero Jacobian is eligible under
  `local_inverse_implicit`.
- Cauchy--Laurent extraction on a specified annulus is eligible under `one_variable_cauchy`.
- parameter-holomorphic normalized Bergman kernels in a degenerating family are not eligible.
- Weierstrass preparation and plumbing/topological marking arguments are not eligible.
