# Chalxius v0.6.7 — Plain-Language Attack Recommendations

Chalxius 0.6.7 makes the short adverse recommendation report useful without
turning it into a technical attack transcript. Each suggested attack family now
includes one reviewed ordinary-language sentence explaining what it would
check. The proposal remains inert until the user approves it.

## User-visible change

The default report now presents recommendations in this form:

- `scope_transport` — check whether a local, special-case, or pointwise result
  has been expanded to a global, general, or uniform claim without a valid
  bridge.
- `missing_premise` — check whether the conclusion relies on an unstated
  premise or applicability condition.

These are explanations, not automatically enabled routes. Worker-authored
technical instructions remain available only through `--full`. A future attack
family that lacks a reviewed public explanation is omitted from the concise
report instead of leaking raw worker text or displaying an unexplained slug.

## Research order carried by this release

The prospective Research cycle remains conservative and separates three levels
of challenge:

1. Production subround 1 assigns proof, proposition-level refutation and
   counterexample search, literature, insight, interpretation, and computation
   design. A computation return contains frozen core code, mathematical design,
   and dependencies, but no execution output.
2. Supervision subround 2 consumes only the complete frozen first-subround
   returns. Up to three scoped supervisors attack proof logic, program–math and
   code alignment, source/scope, or integration. A defect creates a later
   copy-on-write Research repair round; it never edits a peer return in place.
3. Computation execution is permitted only after the matching program–math
   supervisor gives a safe explicit disposition. The executed source and
   dependency hashes must match the reviewed design, and the resulting code,
   log, manifest, and output receive another supervision round.

This 0.6.7 change does not alter Candidate formation semantics. Whole-Candidate
fresh adverse review, the independent Verifier, Certification Decision,
Gateway, and Fact admission remain distinct later mechanisms. Optional Pulse is
not invoked by the required production/supervision cycle.

## Compatibility and authority

This release includes the accumulated 0.6.5 and 0.6.6 Research-continuity,
behavioral-reachability, validation-cost, and pre-execution program–math repairs
that were not previously published in this repository. Historical Paper,
Research, Candidate, Decision, Fact, Evidence, task-card, and ledger bytes are
not rewritten or granted new authority.

The sole truth path remains:

`Research → Candidate Release → Certification Decision → Fact`

Adverse reports, supervisor results, software tests, release receipts, and
package hashes all have `truth_effect=none`.

## Validation

The exact 241-entry manifest passed one final manifest-bound six-lane matrix:

- strict architecture reconnaissance;
- mutation-registry preflight with 142 exact targets;
- 59 behavioral probes across 25 registered features;
- all 801 unit and integration tests;
- bundled self-test; and
- 142/142 mutation kills with source and every isolated lane unchanged.

The release archive is deterministic, symlink-free, bytecode-free, and contains
242 members including `MANIFEST.sha256`. A fresh extraction passed all 241
manifest hashes and the bundled self-test. Exact receipts and hashes are in
[VALIDATION.md](VALIDATION.md) and [RELEASE.lock.json](RELEASE.lock.json).

The validated candidate was not installed over the maintainer's global runtime;
that replacement is a separate explicit cutover decision and is not claimed as
release evidence.

## Install

Download adjacent assets:

- `chalxius-0.6.7-plain-language-attack-recommendations.tar.gz`
- `chalxius-0.6.7-plain-language-attack-recommendations.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.6.7-plain-language-attack-recommendations.tar.gz.sha256
tar -xzf chalxius-0.6.7-plain-language-attack-recommendations.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 scripts/self_test.py
```

Replacing an installed global runtime remains a separate cutover operation. Do
not replace the runtime beneath an already-frozen task card.

## Scope

Software validation establishes exercised workflow and byte-identity
properties. It does not prove a theorem, certify a manuscript, validate an
empirical result, or admit a Fact.
