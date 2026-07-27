# Validation

Result: PASS.

## Public package

- Version: `0.3.5`.
- Renderer: `chalxius-reader-html-12`.
- Layout contract: `deterministic_ranked_barycenter`.
- Manifest entries: 138, excluding `MANIFEST.sha256` itself.
- Manifest-file SHA-256:
  `017d0f0a5c1ce81145af23bd7fe4f886eb2a39c83bdc28c7869df0ed7a900fc9`.
- Public archive: `chalxius-0.3.5-public.tar.gz`.
- Public archive size: 1,425,506 bytes.
- Public archive SHA-256:
  `7ed57b0e54b6e504affa0a25e1d70504fb06d328db9d21a76fc45785df92f43e`.
- Two independent public builds were byte-identical.

The archive contains only regular files in sorted order. Its USTAR headers use
numeric UID/GID 0, empty owner/group names, fixed member time
`2026-07-27T00:00:00Z`, safe relative paths, and gzip timestamp 0. It has no
duplicate member, directory member, symlink, absolute path, or traversal path.

## Automated checks

- Complete unittest suite: 426/426 PASS.
- Focused Reader suite: 25/25 PASS.
- Chalxius self-test: PASS.
- Official Skill Creator validation: PASS.
- Python AST: 67 files PASS.
- JavaScript syntax and JSON parsing: PASS.
- Exact-tree manifest verification: PASS before and after tests.
- Cold public archive: manifest, validator, self-test, full suite, and two
  byte-identical official Reader exports PASS.
- Cold local-install archive: manifest, validator, self-test, and full suite
  PASS.

## Reader behavior and browser evidence

- Proper-crossing regression fixture: baseline 1, rejected candidate 7, final 1.
- Synthetic improvement fixture: baseline 1, final 0.
- Philosophy case: baseline 3, final 3.
- Topic double-click: 2 full / 6 minimized -> 8 full / 0 minimized; the topic
  became the selected detail and the action remained undoable.
- Detail scaling at 100% -> 150%:
  - panel font: 15 -> 22.5 px;
  - exact TeX: 12.3 -> 18.45 px;
  - MathJax container: 16.2 -> 24.3 px;
  - measured sample SVG: 11.02 x 8.73 -> 16.05 x 12.72 px.
- Topic links rendered as smooth dashed bezier grouping links.
- Browser warnings and errors: none.

The layout search is evaluated only for at most 1,200 cross-rank Reader edges.
Above that bound packet order is preserved. The result is deterministic and no
worse than its scored baseline; it is not claimed to be globally optimal.

## Deterministic Reader artifacts

- Cold example packet SHA-256:
  `c9e7c4350c241c34088f4ab0dc0b4e92c7f592ab4e8b3c7d8545270c6feff912`.
- Cold example HTML SHA-256:
  `3f946a225cbc100e61de027db420ed28fd3a3e4116e361e66a626ce6dac6d6eb`.
- Reader Finalize: 9/9 sidebar-complete, `status="ready"`,
  `scope="presentation_readiness_only"`, `truth_effect="none"`.
- Philosophy case HTML:
  `8163154eab3af5a77186d875c0dce415a5e52658da0d3a9e3fe92162c2b2f186`.
- Guarded x-y case HTML:
  `250eff7d5533b7bfbbd72d01ace0d6a833ab1d7b8e766a7f1cc27e99cc71b91c`.

## Privacy and claim boundaries

- Public-tree scans found no absolute local path, username, temporary local
  path, private-key marker, GitHub token pattern, or AWS access-key pattern.
- No cache directory, bytecode, `.DS_Store`, or symlink is present.
- The philosophy case is anonymized and demonstrates workflow structure, not a
  philosophical conclusion.
- The x-y case says potential application, current audit not PASS, and no author
  confirmation in its page, packet, source snapshot, screenshot context, and
  use-case documentation.

## Local transactional installation

- Upgrade: 0.3.4 -> 0.3.5 PASS.
- Installed manifest SHA-256:
  `0eb3bd13d32ea2b83bc3c45ff71a25d016456ade96a739bca8d5efcef925fa4f`.
- Previous 0.3.4 tree: preserved in a separate recoverable rollback directory.
- Staged and post-cutover validation each passed 25/25 focused tests and 426/426
  complete tests.
- The `scripts/mathgraph/contracts.py` file SHA-256 remained
  `5bd04ce9dc5fea159805e50b921a225875124946ec26e3e119af4236d03d75e1`.
- The runtime Fact-admission contract SHA-256 remained
  `68c4785a8c36558ee7effb79be755405d2be785ee00f81795328c6cc5a211289`.
- Reasoning-mode policy SHA-256 remained
  `0e1939213c834c3f326a20bea5953e387e8fb5ec30ad39386e71a0f7693af1af`.
- Grill Me Code manifest and host routing file remained unchanged.
