# Validation — Chalxius v0.9.12

This report records software, package, installation, live-project performance,
sensitive-information, and CHX-settlement evidence for **Chalxius 0.9.12 —
Frontier Lifecycle Closure**. It does not certify a mathematical claim.

## Frozen identity

| Field | Value |
|---|---|
| Version | 0.9.12 |
| Release date | 2026-08-28 |
| Manifest entries | 265 |
| Package files, including manifest | 266 |
| Manifest SHA-256 | `090139e03f8aa43e69e9b3144f084ee7ec9a7461cc0fda31576bdadc1fd818cc` |
| Archive | `chalxius-0.9.12-frontier-lifecycle-closure.tar.gz` |
| Archive bytes | 2,637,850 |
| Archive regular-file members | 266 |
| Archive SHA-256 | `fa9b0d6e68c3a1da0a6b33f0b985cc956c7a5f1948a90cd0e17a4c9580f24468` |
| Checksum-file SHA-256 | `b03881cd86af36e7a12f1a05cbba1bed3ea2dbcf4d767b3693618a291c7073bb` |

Independent builds at the repository path and `/tmp` were byte-identical. The
archive contains only sorted regular files rooted at `chalxius/`; it contains
no directory, link, device, cache, or bytecode member.

## Routine release matrix

One routine profile was selected for the exact final manifest.

| Lane | Result | Elapsed |
|---|---|---:|
| Self-test | PASS | 0.844 s |
| Changed-surface tests | 114 tests, PASS | 9.768 s |
| Semantic mutation audit | 32/32 killed | 44.832 s |

The matrix took 54.888 wall seconds. Every lane ran in an isolated
manifest-only copy and reported an unchanged source tree. The receipt-file
SHA-256 is
`03e1803572f4aeed5008473c11d615b438a660700f141a06ea4163235280082f`.

The complete historical suite, full mutation registry, behavioral registry,
and whole-tree reconnaissance remain an opt-in forensic profile. They are not
an ordinary release gate.

## Focused regression surface

The release regressions establish that:

- exact legacy Main-authored COW roots can reach a unique terminal Research
  without changing historical bytes;
- multi-head aggregation keeps real `await_return` work foregrounded while all
  reconciliation branches remain visible;
- record validation reuses the exact envelope bytes already hash-validated in
  one command and still performs full record/artifact checks;
- an ongoing host session is resumed and does not trigger a duplicate mutating
  planner;
- the 0.9.11 frontier/source-continuity behavior remains covered;
- release and local-install changed-surface matrices include these regressions.

No regression grants Candidate, Certification, Gateway, or Fact authority.

## Installation and live-project canary

| Field | Result |
|---|---|
| Installer | `scripts/local_install.py` |
| Installed version | 0.9.12 |
| Candidate-to-installed tree | exact; 266/266 files unchanged |
| Installed manifest SHA-256 | `090139e03f8aa43e69e9b3144f084ee7ec9a7461cc0fda31576bdadc1fd818cc` |
| Previous runtime archived | yes |
| Direct rollback available | yes |
| Project reads / writes by installation | 0 / 0 |
| System restart | not performed |

The installed local-$\mathbb F_0$ canary contained 1,963 Research entries.
`frontier --campaign campaign-62013035c1ff --limit 4` completed in 2.696
seconds and emitted 23,960 bytes with SHA-256
`3f893ed4fee738708fde80627aaa7081b7a49c559ca392d3f4d1a6641d3774ca`.

The read-only audit completed in 12.240 seconds and reported:

| Signal | Result |
|---|---|
| `current_ok` | true |
| `history_clean` | true |
| Graph errors | 0 |
| Workflow errors | 0 |

These measurements characterize one project snapshot and are not universal
performance guarantees.

## Sensitive-information scan

The packaged tree was scanned for the local username and absolute user path,
private-key headers, common cloud access keys, GitHub/OpenAI/Slack token forms,
and common secret assignments. No true positive was found. Two OpenAI-token
lexical matches were reviewed: one occurred inside the example identifier
`hosttask-0123456789abcdef0123456789abcdef`, the other inside
`v5-task-local-experiment-governance`.

This bounded scan is release evidence, not a general secret-detection
guarantee. The exact package remains inspectable through `MANIFEST.sha256`.

## Global CHX settlement

| Field | Result |
|---|---|
| Global repair | `global-repair-844467f1b76e85af05f240a0970c34897b3c3bcb317c63ce52b8b8267a7c9aa5` |
| Canonical `record_sha256` | `a3509d5bf88da988a5379d19b24d906ffb76018a3d74ffc4193a1d4cf9e844ff` |
| Record-file SHA-256 | `aea2ae11ac87692e85f928709a015d3b575830f1535364d8c82a553726f43461` |
| Inventory SHA-256 | `332f37ff29a419e3a3bbf269117156fe9b3408fbf1bbf50f567e97bf07f91038` |
| Covered snapshot SHA-256 | `00bec38182e3ad6ef480c04d8e9bc4f950dc0f3dc0fab8962363789d6d5c325c` |
| Observed / globally resolved | 225 / 225 |
| Revalidated prior / newly fixed | 221 / 4 |
| Unresolved / uncovered | 0 / 0 |
| Active open issues | 0 |
| Lineage errors / report drift | 0 / 0 |

Historical ledger bytes were not rewritten. Thirty-four raw historical ledgers
retain old open-state provenance, but all of their issue identities are covered
by the current global settlement; none remains actionable merely because of
that historical bit.

## Research and truth boundary

Installation wrote no project byte. The live canary performed read-only audit
and frontier operations. CHX settlement is administrative. This release
created no Candidate Release, Certification Decision, Gateway admission, or
Fact. Software validation is not a theorem proof.
