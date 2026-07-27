# Chalxius

Chalxius is a research and learning skill for Codex. It keeps source,
interpretation, audit, exploration, admitted Fact, and learning authority
separate; uses one invariant Fact-admission contract across fast, auto, and deep
reasoning modes; and can explicitly export a deterministic offline
knowledge-map reader.

New to these terms? Start with
[`ARCHITECTURE.md`](ARCHITECTURE.md). It explains from first principles what
Chalxius does, how a candidate becomes a Fact, why its authority classes remain
separate, and why Learner and Reader output cannot change research truth.

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

Chalxius gratefully acknowledges the authors of **Danus: Orchestrating
Mathematical Reasoning Agents with Fact-Graph Memory** (Liu et al.,
arXiv:2607.06447v2), a separate published mathematical-reasoning system. Its
public design informed the fact-graph layout, but it is not a runtime dependency
and no Danus source code is inherited here.

Chalxius also thanks **Matt Pocock** for the public
[`/grill-me`](https://github.com/mattpocock/skills/blob/main/docs/productivity/grill-me.md)
skill. Its one-question-at-a-time decision-tree interview inspired the
requirements-discovery method used while shaping the Reader. This is design
attribution, not a runtime dependency. See
[`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) for full citations and scope
statements.

Licensed under Apache-2.0. Third-party notices and vendored component licenses
are included in the skill directory.
