# PHX global architecture-route reference

PHX is Chalxius's global, append-only reference guide for significant
architecture routes. Performance and administrative-cost reduction are one
route domain, not the definition of PHX. The same guide may preserve routes for
coordination, evidence governance, extensibility, release and deployment,
reliability, research workflow, usability, and verification.

PHX stores reusable architectural direction. CHX stores architecture-caused or
architecture-amplified problems. A CHX issue may motivate one or more PHX
routes, but the problem remains in CHX and its tactical repair, integrated
repair, disposition, and release disclosure remain governed by the CHX
contract. PHX must not reproduce the issue as a second problem ledger.

Every PHX event has `truth_effect=none`, `project_effect=none`, and
`premise_eligible=false`. A route, measurement, consultation, adoption record,
or report is never Paper, Evidence, Research, Candidate, Certification,
Gateway, Fact, proof, or empirical authority.

## Global location and scope

The default PHX root is:

```text
~/.codex/chalxius/phx-ledgers/
```

It is host-global and deliberately outside every Chalxius project and outside
the installed skill tree. A PHX route can therefore be consulted across
projects and domains without copying authority from one project into another.
Production uses the canonical root. A custom root is an explicit expert/test
override, requires declared project roots, and is labeled `custom_expert` in
status and search output. The root must be user-owned mode `0700`; ledgers,
search receipts, and reports must be user-owned mode `0600`.
Run-local route ids are qualified by their ledger run id when referenced from a
different run. The ledger is append-only and hash-chained; deterministic
reports are projections of closed ledger bytes, not an independent source of
authority.

The first implementation uses validated ledger scans rather than a persistent
index. `search` can filter by domain, qualified source-CHX issue, typed PHX
relation, and ordinary route language. It returns current and historical
routes, marks reverse `supersedes` state, ranks current heads first, and warns
when one stable key has multiple unlinked current heads. Every result exposes
the route event hash, route-prefix hash, and owning ledger hash. With
`--write-receipt`, the query, filters, scanned ledger heads, and returned route
heads are stored under the global `search-receipts/` directory as a
content-addressed nontruth receipt. A future index is itself a PHX architecture route and requires measured
need, explicit invalidation and recovery semantics, and the adoption procedure
below.

## What a route records

A route is a reusable proposal or reference pattern, not an instruction to
modify the runtime. Each route records:

- a stable route key, title, summary, domain, kind, and origin;
- applicability signals that make consultation of the route relevant;
- a measurement plan that can distinguish benefit from conjecture;
- one or more implementation options rather than a falsely mandatory design;
- fail-closed boundaries that the route must preserve;
- qualified source-CHX references when the route is synthesized from CHX; and
- typed relations to earlier PHX routes.

Permitted origins distinguish CHX synthesis, architecture review, measurement,
and direct user direction. A route synthesized from CHX must bind its source
issue events. It summarizes the architectural lesson; it does not copy the
problem narrative, close the source issue, or inherit any project authority.

Routes may be linked by `extends`, `refines`, `derived_from`, `supersedes`, and
`related_to`. Use these relations to preserve the history of architectural
reasoning instead of silently rewriting an earlier route. An `extends` route
widens applicability; a `refines` route narrows or makes a mechanism more
precise; a `derived_from` route records intellectual provenance; a
`supersedes` route replaces a recommendation while preserving history; and a
`related_to` link records a non-hierarchical connection. Cross-run relations
bind a closed target ledger and its immutable digest. Same-run relations may
refer only to an already recorded route.

## Recording is not authorization

Recording a PHX route does **not**:

- authorize implementation or deployment;
- establish that the route is beneficial in the current workload;
- permit weakening a validator, authority boundary, or release gate;
- resolve, dispose, or replace a CHX issue;
- change the installed runtime or any project; or
- commit the user to the proposed architecture.

This separation lets Chalxius preserve a substantial architecture suggestion
as soon as it is recognized while leaving judgment about adoption with the
user. Declined or deferred suggestions remain useful reference history and must
not be silently implemented.

## Mandatory consultation for significant adoption

Before implementing a PHX proposal that would materially change Chalxius's
architecture, ask the user. The consultation must identify the route, explain
the proposed change and its meaningful alternatives, state the expected
benefit and cost, and name the fail-closed boundaries and migration or rollback
consequences. Do not treat the existence of a PHX route, a broad research goal,
or a request to inspect architecture as approval to adopt it.

Record the consultation as a PHX event bound to the route before active
implementation begins. The record preserves the proposal summary, exact user
question and response, response SHA-256, host-task and user-turn locator,
authorization scope, implementation state, at least two alternatives, expected
benefits, costs and risks, migration or rollback route, decision, constraints,
and consultation context. Decisions are `approved`,
`approved_with_constraints`, `declined`, or `deferred`.

- `approved` permits the measured proposal to proceed within the stated scope.
- `approved_with_constraints` permits only the recorded constrained form.
- `declined` prohibits that adoption; do not reinterpret it as permission for a
  nearby route.
- `deferred` leaves the route unadopted until a later explicit consultation.

An adoption record requires both a supporting digest-bound evaluation and the
latest approved or approved-with-constraints consultation. It must acknowledge
the exact authorization scope and every constraint, then bind implementation
anchors, implementation hashes, regression evidence and hashes, applicability,
and residual boundaries. Adoption records
describe what was actually implemented; they do not themselves perform the
change. A route with no adoption record remains a recommendation only.

Evaluations are not restricted to timing benchmarks. Their kind may identify an
architecture review, compatibility or reliability matrix, operational trace,
isolated prototype, benchmark, or user study. A `supported` outcome requires at
least one evidence digest. Read-only and isolated-sandbox evaluations may
precede consultation. Any evaluation that mutates active architecture must
bind the latest approved consultation and acknowledge its exact scope and
constraints before that mutation begins.

The response digest and host locator make a claimed decision auditable but do
not cryptographically authenticate the surrounding chat by themselves. The
operating agent must still show the alternatives, benefit, cost, boundary, and
rollback question to the actual user; an independent review should compare the
stored locator and response digest when approval provenance is disputed.

Routine, already authorized maintenance need not be inflated into a major
architecture consultation merely because it uses a known implementation
technique. If a purported tactical repair changes global lifecycle,
coordination, authority, persistence, automation, compatibility, or deployment
semantics, however, it is a significant architecture adoption and requires
consultation before implementation.

## CHX-to-PHX synthesis and repair workflow

When a CHX finding exposes a reusable architecture lesson:

1. Keep the concrete failure and its causal account in CHX.
2. Query PHX by applicability signal, domain, mechanism, source-CHX relation,
   and route relations before designing a new mechanism.
3. Apply the CHX contract's bounded, reusable tactical repair without treating
   that tactical record as resolution.
4. Record a new PHX route only when the lesson is globally reusable and is not
   already covered. Prefer extending or refining an earlier route over creating
   an unlinked duplicate.
5. If the proposed route is a significant architecture change, obtain and
   record the user's decision before implementation.
6. Measure the route in the relevant workload. Record unsupported or
   inconclusive results as faithfully as supported ones.
7. At the task-stage boundary, coordinate all tactical repairs and applicable
   PHX guidance into the CHX integrated repair. Preserve, revise, replace, or
   decline mechanisms based on their interactions and evidence.
8. Record PHX adoption only for the actually implemented, measured, and
   user-approved form.

For a performance-related CHX issue, a PHX route lookup with a persisted search
receipt is mandatory before
selecting the repair route. Start with work elimination, scope separation, and
command-local reuse; persistent indexing or parallelism is not presumed. The
lookup must not delay an in-scope bounded tactical repair, but it must prevent
repeated invention and must inform the later coordinated integration. Name the
receipt path, receipt SHA-256, and selected qualified route ids (or the
hash-bound no-match result) in CHX tactical or integrated evidence. The
separate user-consultation gate applies when the selected route would be a
significant architecture adoption.

## Operating boundary

PHX is a global route memory, not an automatic architecture governor. It may be
triggered by language such as cost reduction, performance improvement,
architecture recommendation, global redesign, coordination, simplification,
or recurring mechanism reuse. Semantic triggering means consult and, when
appropriate, record the guide. It never means silently implement a route.

PHX should stay compact by recording major reusable routes, meaningful
measurements, explicit consultations, and actual adoptions. Local symptoms,
ordinary bugs, one-off timings, and CHX dispositions belong elsewhere. The
ledger's value is durable architectural judgment with provenance, not a larger
administrative burden.

Standalone PHX commands are part of the governed interface contract. Capability
inventory must not infer reachability merely from parser and handler presence:
command-specific options must be forwarded only to their owning callable, and
public subprocess probes cover `start` and `search --write-receipt`.

An applicability route must specify both branches. Exact canonical absence may
eliminate subsystem work; canonical presence must consume a complete validated
owner view before the first state read. Reuse the binding already established by
the gate when possible rather than reopening the owner closure.

Deterministic PHX reports may be created only below the owning global root's
`reports/` directory. They never overwrite a different existing file, never
write into a research project, and omit the raw user response while retaining
its decision and digest.
