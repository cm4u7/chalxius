# Chalxius

Chalxius is a Chalk-native research and learning skill for Codex. It keeps
Paper, Audit, Blackboard, Fact, and Learning authority separate, uses one
invariant Fact-admission contract across fast, auto, and deep reasoning modes,
and can explicitly export a deterministic offline knowledge-map reader.

The installable skill is in [`chalxius/`](chalxius/). Verify its
`MANIFEST.sha256` before copying it into a Codex skills directory.

For a packaged install, download `chalxius-0.3.4-public.tar.gz` and
`SHA256SUMS` from the matching GitHub Release, keep them in the same directory,
and run:

```sh
shasum -a 256 -c SHA256SUMS
tar -xzf chalxius-0.3.4-public.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
```

## Current release

Version 0.3.4 adds Reader Finalize, same-document graph reload, balanced reader
card labels, a stable full/compact control anchor, and continuous whole-card
edge emphasis. See [`RELEASE.md`](RELEASE.md) for the complete release notes and
scope boundary, and [`VALIDATION.md`](VALIDATION.md) for the verified evidence.

The reader is a presentation-only projection with `truth_effect="none"`. It
does not change graph topology, source authority, Fact admission, or project
state, and it introduces no watcher, network runtime, local storage, sidecar,
or graph writeback.

## Public-source boundary

This repository excludes private local visual-QA paths, user-specific learning
profiles, and private historical forward-test evidence. Runtime and research
engine files are unchanged from the installed 0.3.4 build; only non-runtime
private documentation and its corresponding self-test inventory entries are
omitted from the public source distribution.

## Acknowledgements

Chalxius gratefully acknowledges **Danus: Orchestrating Mathematical Reasoning
Agents with Fact-Graph Memory** (Liu et al., arXiv:2607.06447v2). Danus informed
the public fact-graph design, but is not a runtime dependency and no Danus source
code is inherited here. See [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) for the
full citation and scope statement.

Licensed under Apache-2.0. Third-party notices and vendored component licenses
are included in the skill directory.
