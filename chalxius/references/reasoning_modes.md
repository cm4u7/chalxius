# Reasoning modes and switching

## Two different notions of mode

`reasoning_mode` is the project-level execution profile: `fast`, `auto`, or
`deep`. The existing `plan-round --mode` is an assignment work intent such as
`auto`, `prove`, or `refute`. Both are stored; they are never aliases.

## Profile semantics

| Property | fast | auto | deep |
|---|---|---|---|
| Chalxius research engine and audits | full | full | full |
| Fact admission contract | identical | identical | identical |
| Expensive exploration | available, not automatic | deterministic workload triggers | every applicable feature required |
| Inapplicable feature | `not_applicable` | `not_applicable` | `not_applicable` |
| Missing triggered truth evidence | candidate/blocker | candidate/blocker | candidate/blocker |

The deterministic profile covers the clean-context panel, barriered Blackboard
pulse, Paper Logic, Paper Audit, full-fidelity Paper mirror, orthogonal
specialist escalation, campaign expansion, computation exploration, novelty
search, and expert synthesis. Its applicability comes from the V4 workload
profile and adoption binding; wall-time or token estimates never change it.

In `deep`, a required status is an executable closure obligation. Each round
freezes `profile_obligations`, including the exact required assignments per
feature and its canonical hash. The main agent must produce and bind the native
or explicitly procedural evidence for that feature: a reviewed current `pls-*`
snapshot for Paper work, current Audit evidence whose Logic base is still
current, a governed projection receipt for a mirror, pulse plan/barrier/closure
for collaboration, experiment/final replay receipts for computation,
current-round campaign and novelty events, and lint plus assignment-scope
evidence for expert synthesis. If the host lacks a required capability, report
the blocker; do not mark the feature complete from prose.

After canonical ingestion, use `profile-closure-status` and, when required,
`profile-closure-record`. The immutable receipt covers exactly—not merely at
least—the frozen required features and binds every governed assignment's task
card, return, ingestion receipt, outcome, and effect. Evidence for another
round, assignment, memory, campaign, or submission subject cannot substitute.
A pre-closure unified round without frozen `profile_obligations` must be
replanned.

Evidence strength is typed rather than flattened. Native pulse closure,
reviewed snapshot structure, finalized computation, novelty event, and lint
validation can be machine-verified. Host capacity, specialist identity,
campaign before/after scope, and synthesis-to-assignment meaning are procedural
host attestations. A feature using both is
`mixed_procedural_and_machine_verified`. The closure's truth effect is only
`workflow_readiness_only`; it is outside the invariant Fact-admission contract,
whose hash and gates are identical in all three modes.

In `auto`, the same evidence is required whenever its deterministic workload
trigger fires. In `fast`, those exploration features remain available, but
source, convention, quantifier, replay, atomic-bundle, and verifier obligations
remain nonnegotiable. When a fast task triggers one of them, the execution
profile records `candidate_only_until_gate_satisfied` until evidence exists.
A round with zero required exploration features reports `not_required` from
the frozen round itself. It has no profile-closure receipt; a fake or ceremonial
receipt is rejected.

## State transitions

Initialize new projects with `init --reasoning-mode MODE`. Activate a historical
project in the pre-Chalxius V4 format with `mode-init --mode MODE`. Query with
`mode-status` and append a switch with `mode-switch --to MODE`.

Every mode event states:

- the previous event and mode;
- the new mode;
- actor and reason;
- `future_work_units_only` effect;
- frozen-work-unit retention;
- policy and invariant Fact-admission hashes.

Task cards and assignment contracts bind the entire deterministic execution
profile. Editing a status, trigger, event id, or contract hash causes validation
or audit failure. Verification-task construction, review recording, Fact or
atomic-bundle admission, accepted-idempotent retries, and current audit all
revalidate a required closure and its subject binding. Low-level verification-
or FactBundle stores cannot mint verifier/review/admission evidence without the
owning `MathGraphStore` authority, so later evidence drift cannot be hidden by
an earlier acceptance marker or a bypassed wrapper.

Historical mode-less state in the pre-Chalxius V4 format is API- and CLI-level
read-only. Explicit `mode-init` is permitted only after a clean current audit.
Its schema-2 receipt binds frozen rounds and inventories the exact acceptance
event, Fact, submission, review, verifier-package, atomic-bundle tree, and
acceptance-marker bytes for every already-accepted object. That exact set alone
is exempt from future round-profile requirements; pending candidates are not
grandfathered, and any bound-byte or symlink drift invalidates governance and
blocks writes.

## Switching during work

A switch never upgrades or downgrades a frozen round. Continue the old round
under its bound profile, or issue `work-unit-abort` and plan a new round after the
switch. Abort is append-only and does not terminate an OS process. It rejects
future managed return, experiment, and pulse mutations for that round; status,
audit, and necessary pulse-abort cleanup remain readable/available.

## Reporting

Always report the current mode, mode-event id, future-only semantics, frozen
round modes, missing profile obligations, and Fact candidate/admitted boundary.
Never summarize a mode change as a change in certification strength.
