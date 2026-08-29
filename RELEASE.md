# Chalxius v1.0.0 — Fact Alpha

Chalxius 1.0.0 introduces a post-Research correctness-certification layer
without creating a second mathematical graph. Research remains the single
immutable graph; a Fact is now an append-only certification grant attached to
the exact bytes of a whole Research node.

The release does not migrate or reinterpret legacy 0.x Candidate,
Certification, Gateway, or Fact authority. Those records remain readable as
historical, unmapped authority.

## Fact Alpha workflow

Main may mark mathematically important Research nodes in a lightweight Fact
frontier. Current terminals, certified heads, stale descendants, and batch
opportunities are derived live; there is no timer, background scheduler, or
automatic mathematical selector.

A packager freezes several exact Research nodes into one candidate package.
For each component it records the node's exact claim, assumptions,
domain/types, quantifiers, limitations, and exact certified predecessor grants.
The package is an inspection and batching object, not a second proof graph.

One independent verifier decides each component. Successful decisions create
append-only Research certification grants. A minor correction uses complete
component COW and may be rechecked by the same verifier without an extra
ordinary supervisor; a fundamental error returns to the ordinary Research
workflow. Replacing a certified Research node derives
`needs_reverification` for certified descendants through exact predecessor
grants.

New public commands are:

- `fact-frontier-mark`, `fact-frontier-dispose`, and `fact-frontier`;
- `plan-fact-packaging` and `fact-package-seal`;
- `fact-verifier-capsule`, `fact-verification-record`, and
  `fact-verification-check`;
- `fact-certify`.

The new `fact-packager` role is deliberately narrow. Learned theorem attacks
remain part of ordinary Research supervision rather than being duplicated in
Fact verification.

## Validation and installation

The exact 268-entry manifest passed whole-tree architecture reconnaissance,
141 behavioral probes, the complete 1,068-test suite, and the routine release
matrix:

| Lane | Result | Elapsed |
|---|---:|---:|
| Self-test | PASS | 0.954 s |
| Changed-surface regression | 132 tests, PASS | 11.153 s |
| Semantic mutation audit | 32/32 killed | 45.900 s |

The routine matrix completed in 57.426 seconds and left the source tree
unchanged. Architecture reconnaissance found no orphan module, behavioral
orphan, error, or warning.

The globally installed runtime is byte-exact with the candidate across all 269
package files. Direct rollback to 0.9.18 is available. Installation read and
wrote no project byte.

On the 2,247-Research local-$\mathbb F_0$ project, the installed
`fact-frontier --limit 8` completed in 0.942 seconds. A full read-only audit
completed in 14.789 seconds with `current_ok=true`, `history_clean=true`, and
no graph or workflow error. Project metadata was byte-identical before and
after the canary. These measurements describe one snapshot, not universal
latency bounds.

The bounded sensitive-information scan found no credential, private key,
personal path, or true token. Three fixture/documentation strings were reviewed
as non-secret examples.

## Global CHX settlement

`global-repair-f66daf8fa1046e7c4f8dfda1437cd76de7d781bceb4b3ea6f41e0468a88fac80`
covers all 239 observed qualified issues under the exact installed 1.0.0
manifest:

- 236 immutable prior dispositions were revalidated without replay;
- 1 current-round frontier precedence defect was revalidated as fixed;
- 2 Fact Alpha integration defects were fixed by this release;
- 0 issues remain unresolved or uncovered.

Historical task-ledger bytes were not rewritten. Thirty-seven old ledgers
retain an open-state provenance bit, but none carries an actionable issue under
the current settlement.

## Distribution

Release assets:

- `chalxius-1.0.0-fact-alpha.tar.gz`
- `chalxius-1.0.0-fact-alpha.tar.gz.sha256`

The deterministic archive contains 269 regular files, is 2,705,200 bytes, and
has SHA-256
`815fa9f6eaa910fafb653825cbe3e2c4e231d40938fea5c8bf3accb67841d850`.

```sh
shasum -a 256 -c chalxius-1.0.0-fact-alpha.tar.gz.sha256
tar -xzf chalxius-1.0.0-fact-alpha.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
python3 -B scripts/self_test.py
```

This local release is installed and sealed with tag `v1.0.0`. No remote push is
claimed by this document. Software validation and CHX settlement create no
mathematical Fact by themselves.
