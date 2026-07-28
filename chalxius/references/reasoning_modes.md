# Reasoning modes and switching

## Two different notions of mode

`reasoning_mode` is the project-level future-work budget: `fast`, `auto`, or
`deep`. `plan-round --mode` is an assignment intent such as `prove`, `refute`,
or `compute`. They are stored separately and are never aliases.

| Property | fast | auto | deep |
|---|---|---|---|
| Chalxius engine and audits | full | full | full |
| Fact admission contract | identical | identical | identical |
| Expensive exploration | user-selected | selected from task signals | all applicable exploration requested |
| Missing truth evidence | explicit blocker | explicit blocker | explicit blocker |

Modes do not create a universal exploration checklist. Paper, novelty,
experiments, campaigns, Pulse, or external-source work is activated only when
applicable to the bounded task. `deep` may allocate more exploration, but it
cannot create Fact authority or require ceremonial evidence for an irrelevant
feature.

`profile-closure-status` and `profile-closure-record` survive in V5 only as
process-readiness compatibility commands. Status emits object-specific repair
suggestions. Record appends advice or acknowledgement to Research. Neither
closes a round nor participates in Candidate Release, Certification, or Fact
admission.

Initialize a V5 project with `init --reasoning-mode MODE`, query with
`mode-status`, and append a future-only switch with `mode-switch --to MODE`.
Every frozen task card retains its original mode event and Fact-contract hash.

To cancel one frozen work unit explicitly, use `work-unit-abort`. Cancellation
blocks future managed return and experiment mutations, plus new Pulse
commitments or dispatch for that round, but preserves all readable state and
already-ingested Research. A mode switch alone never cancels work.

Report the current mode, mode-event id, and future-only effect separately from
Fact status. Never describe a reasoning-mode change as a certification change.
