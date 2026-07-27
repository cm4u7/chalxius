# Chalxius Learner: nontruth academic learning plane

`Chalxius Learner` is a lightweight static consumer embedded in Chalxius. The
phrase "internal Grill learner" is a compatibility description, not the name of
a second skill or runtime. Chalxius Learner owns the academic teaching and
testing functions inherited from Grill Me
0.2.0: mathematical and philosophical tutoring, paper-reading modes,
qualifying-exam drilling, graph-aware question selection, mastery evidence, and
spaced review. It does not invoke a Grill Me or Danus runtime and does not
participate in Chalxius research orchestration.

Chalxius Learner is off by default. Activate it only for explicit academic
teaching, questioning, testing, paper-learning, exam-training, mastery-tracking,
or spaced-review intent. It never activates merely because `$chalxius` is used,
because a research graph exists, or because the user asks to test Chalxius's
research capability. A learning request may remain in-session; persistent
learning-graph writes need separate user authorization.

The research reasoning profile is a separate axis. `deep` does not activate
Chalxius Learner, and Learner activation does not switch `fast`, `auto`, or
`deep`, create a research round, or alter the invariant Fact admission gate.

Standalone Grill Me 0.3.2-code, publicly distinguished as `Grill Me Code`, is
intentionally unrelated to this plane. It is globally available to routing but
semantically on demand: only explicit programming Grill or Socratic intent
activates it. It is a programming assistant and cannot mount Fact, Paper, Audit, Blackboard, or
learning artifacts. Ordinary coding does not activate it.

## What it may mount

- a frozen Fact Graph, including legacy Danus-compatible facts and certificates;
- an immutable Chalxius `pls-*` Paper snapshot, with source, reconstruction, and
  audit authority preserved;
- an immutable Chalxius `bbs-*` Blackboard snapshot, including omission receipts
  and nonlearnable boundary stubs.

Mounting verifies local bytes, manifests, ids, edges, and drift. This is artifact
identity checking, not mathematical verification. The adapter never writes back
to a mounted source.

## What it may write

Only a separately user-authorized learning graph may receive mastery attempts, hint depth,
error classes, review schedule, teaching coverage, pedagogical explanations,
misconceptions, and source concerns. These records use separate content hashes.
They are excluded from Chalxius Fact, Paper, Audit, Blackboard, round,
verification, and admission stores.

Teaching does not require a Chalxius multi-agent research audit. This is a
performance and pedagogical boundary, not a weaker truth gate: teaching evidence
has no truth effect. A suspected source defect is recorded as a concern. If the
user wants it resolved, open a normal unified research work unit and build the
appropriate Paper Audit or Fact candidate evidence.

Use `scripts/learn --help` and [fact-graph-grilling.md](fact-graph-grilling.md)
for commands and one-question teaching policy. Invoke this surface through
`$chalxius`, not through standalone `$grill-me`.
