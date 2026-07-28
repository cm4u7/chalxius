# Validation

Result: PASS.

## Public package

- Version: `0.4.0`.
- Workflow authority: V5.
- Truth path: `Research -> Candidate Release -> Certification Decision -> Fact`.
- Renderer: `chalxius-reader-html-15`.
- Layout: `deterministic_compact_radial_core_layers`.
- Manifest entries: 149, excluding `MANIFEST.sha256` itself.
- Manifest-file SHA-256:
  `ca6882ab1f4a73661c101da626cdba2e7a001f85c023a8208a076e08fadc0211`.
- Public archive: `chalxius-0.4.0-public.tar.gz`.
- Public archive size: 1,518,813 bytes.
- Public archive SHA-256:
  `8e19dc4fdfaa6f65bf95f62dde57b5f0bf7f517926dbeec15b593152276ae56f`.
- Archive members: 150 regular files.
- Two independent public builds were byte-identical.

The archive is built from the manifest allowlist in sorted order. Its USTAR
headers use numeric UID/GID 0, empty owner/group names, fixed member time
`2026-07-28T00:00:00Z`, safe relative paths, and gzip timestamp 0. It has no
duplicate, directory, symlink, absolute, traversal, cache, bytecode, or
unlisted member.

## Automated checks

- Complete unittest suite: 450/450 PASS on the candidate, cold public archive,
  and final installed tree.
- Chalxius self-test: PASS, including empty V5 authority, default-if-present
  project background, local Pulse quarantine, and active-policy V5 markers.
- Official Skill Creator validation: PASS.
- Release-time aggressive audit: 8/8 truncation, off-by-one, exact-set,
  certification-panel, Paper-binding, and series-order mutants killed;
  `candidate_unchanged=true`.
- Exact-tree manifest verification: 149/149 PASS before packaging, after cold
  extraction, and after installation.
- Public privacy scan: PASS; no local absolute user path, username, credential
  marker, cache, bytecode, or `.DS_Store` is distributed.
- Git diff whitespace check and JSON/skill validation: PASS.

## Architecture regression evidence

- New V5 projects begin with zero inherited Facts.
- V4 artifacts remain readable but cannot serve as V5 predecessors, reviews,
  closures, or admission evidence.
- Every valid Pulse return survives a malformed peer; malformed returns receive
  local quarantine receipts.
- `profile-closure-*` produces Research repair advice and is absent from the V5
  admission-authority path.
- Candidate Release automatically binds existing linked adverse Research and
  requires exact dispositions.
- A fresh verifier capsule, immutable Certification Decision, and exact gateway
  binding are required before Fact exposure.
- The x-y swap canary rejects `omega11` retained only through `t^0` when
  valuation analysis requires `t^2`, and accepts only with exact deeper replay
  evidence.

## Reader and performance boundary

Reader packet schema 1 is unchanged. Renderer revision 15 remains offline,
deterministic, presentation-only, and non-writing. The full suite includes its
deterministic projection and interaction regressions. No release mutation audit
is imported by normal runtime modules.

Local latency canaries recorded in the package traceability report medians of
0.109132 s for original Danus 0.2.9, 0.127687 s for Chalxius 0.3.6, and
0.141953 s for the stronger V5 small flow. A three-worker background-binding
canary remained below 17 ms median at the 256 KiB summary cap. These are
machine-local canaries, not universal throughput claims.

## Local transactional installation

- Upgrade: 0.3.6 -> 0.4.0 PASS.
- Installed manifest entries and SHA-256 match the public package exactly.
- The final installed tree is byte-identical to the released `chalxius/` tree.
- The prior 0.3.6 tree is preserved in a recoverable rollback directory outside
  skill discovery.
- No active V4 project was migrated or cut over.

## Claim boundary

These checks establish software, packaging, and stated workflow properties.
They do not prove a mathematical theorem and do not Fact-admit any mathematical
claim.
