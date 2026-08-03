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

Version 0.6.4 gives `auto` and `deep` one prospective intake trigger: an explicit user
research objective is sufficient semantic authority for Operator to call
`research-goal-intake`, even when the user never says `Campaign`. The compiler
creates or lexically exact-matches one internal Campaign, enables only the fixed
advisory BF policy, and computes BF-1. This is not an `ACTIVE` default or a
planner. BF-2/BF-3 still require exact ingested-attempt blockage evidence, and
all planning or dispatch remains a separate ordinary action. `fast` retains the
explicit BF activation path.

Current V5 task cards freeze the mode event and their exact assurance contract.
They do not automatically attach the historical V4 `execution_profile` or
`profile_obligations`. `adoption-plan` remains available as standalone advice;
reconnecting its panel, Pulse, Paper/Audit, novelty, campaign, computation, or
expert-synthesis recommendations to automatic V5 planning requires a separate
user decision.

Mode is also separate from priority. The V5 frontier orders active Research by
impact, information value, feasibility, and burden/economy, projecting legacy
eight-metric entries without rewriting them. The score has no cutoff and no
truth effect; explicit low-scored Research remains schedulable in every mode.
An explicitly named Campaign may filter that frontier to exact stored
associations and freeze nontruth planning context, but never changes the score,
mode, assurance contract, or Fact gate; no Campaign flag means global selection.

New V5 refutation task cards receive the fixed low-cost attack vocabulary plus matching user-approved
rules in every reasoning profile. This is worker guidance for an already
selected refutation assignment, not a requirement to run every attack, spawn an
extra worker, close exploration, or alter Fact admission. Rule approval and
disablement remain future-only and profile-independent. The general vocabulary
includes hidden-conjunct splitting; the three philosophy attacks require an
exact frozen `philosophy` or `mixed` domain and cannot be inferred from claim
wording.

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
already-ingested Research. `round-status` joins the validated abort authority,
uses `frozen_aborted` for unfinished assignments, reports zero live awaiting
returns, and exposes the exact abort id; strict audit rejects a stale waiting
projection. A mode switch alone never cancels work.

Report the current mode, mode-event id, and future-only effect separately from
Fact status. Never describe a reasoning-mode change as a certification change.
