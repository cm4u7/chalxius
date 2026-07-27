# Validation

Result: PASS.

## Public package

- Version: `0.3.4`.
- Renderer: `chalxius-reader-html-11`.
- Manifest entries: 138, excluding `MANIFEST.sha256` itself.
- Manifest-file SHA-256:
  `7a52b8142d30bffbb711bfc75c1e29453f9c1b3385cbf7c921adda34978e44df`.
- Public archive: `chalxius-0.3.4-public.tar.gz`.
- Public archive SHA-256:
  `8a91161e50bacb6c45e7072ef3cfb1a800822f968095a69b3cfac54defd73cd1`.
- Archive size: 1,428,010 bytes.
- Archive headers use numeric UID/GID 0, contain no local owner/group name, and
  use a fixed member timestamp with the gzip timestamp disabled.
- Two independent package builds were byte-identical.

## Automated checks

- Complete unittest suite: 425/425 PASS.
- Focused reader suite: 24/24 PASS.
- Chalxius self-test: PASS.
- Official Skill Creator validation: PASS.
- Python AST parse: 67 files PASS.
- JavaScript syntax and JSON parsing: PASS.
- Exact-tree manifest verification before and after tests: PASS.
- Cold archive extraction and validation: PASS.

## Privacy and packaging checks

- No absolute local paths, usernames, private fixture identifiers, email
  addresses, credentials, private keys, or common secret patterns were found.
- No symlinks, cache directories, bytecode, `.DS_Store`, duplicate archive
  members, absolute archive paths, or path traversal entries were found.
- Apache-2.0 and all vendored component license texts are included.

## Deterministic reader export

Two installed exports produced identical HTML SHA-256:
`efa87e99ff184f51eea286acd5305109c3e842d1045c72dac8f41da4bab2a2bb`.

Reader Finalize accepted all 9 nodes and bound canonical packet SHA-256
`e5f45b412e3f7f38bf1d28d22e63ac720d3e86f6b01fc9d9a048b66f5acac0a7`
with `scope="presentation_readiness_only"` and `truth_effect="none"`.
