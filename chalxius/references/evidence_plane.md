# Evidence plane and cross-project bridge contract

## Source role is orthogonal to authority

Current Paper Logic/Audit bundles declare one `source_role`:

- `research_draft` identifies a document produced inside the research process;
- `external_finished_publication` identifies a separately published or cited
  finished source. `external_reference` is a read-only 0.5.0 spelling.

The role survives Paper revision, snapshot, Evidence attestation, and query
projection. An Audit bundle must use the same role as its base Logic snapshot.
Historical objects without the field remain readable and project as
`legacy_unspecified`; they are not rewritten.

`source_role` is neither a trust level nor an authority promotion. Both roles
remain nontruth Paper/Evidence material, with the fixed permitted uses
`background`, `citation_source`, `inspiration`, and `research_material`.
Neither role is premise-eligible without a separately sealed bridge, fresh
verification, and Fact Gateway admission. A `research_draft` intended for
further graph-led research must instead pass the strict whole-draft lifecycle
and complete Fact admission described in `paper_continuation_contract.md`.

## Authority invariant

Evidence is a persistent cross-project nontruth plane between Research and the
current project's Fact Graph. Its two implemented kinds are
`reviewed_paper_graph` and `external_fact_graph`. Every Evidence, disposition,
query result, outbox request, receipt, and bridge has `truth_effect="none"` and
is never premise eligible by itself.

The only truth path remains:

```text
Research -> Candidate Release -> Certification Decision -> Fact
```

An Evidence bridge is an input to that path, not a new transition around it.
It never copies or federates source-project Fact authority.

## Persistence split

The shared library is an append-only JSON/event/content-addressed store.
Derived JSON and SQLite indexes are rebuildable and have no authority. Each
project owns only its adapter state under `PROJECT/evidence/`:

- `outbox/by-id/pes-*.json`: immutable Paper sync requests;
- `receipts/by-snapshot/*.json`: immutable successful sync receipts;
- `fact-capsules/by-id/efc-*.json`: explicit external Fact captures;
- `association-planning/by-id/eap-*.json`: content-addressed, immutable
  attempts to derive exact Paper/Fact Evidence associations after a Fact
  capture has entered the shared library;
- `association-outbox/by-id/eas-*.json`: immutable association requests
  derived only from exact release Paper Evidence refs and local receipts;
- `association-effects/by-request/eas-*.json`: immutable successful
  association effects;
- an optional exact `library-binding.json`.

The binding contract is `chalxius-evidence-library-binding-1`. Resolution order
is the explicit `CHALXIUS_EVIDENCE_LIBRARY_ROOT` environment setting, the
project binding, then the host binding at
`~/.codex/chalxius/evidence-library.json`. A missing or invalid binding is not a
Fact or Paper failure; Paper sync remains pending and explicit Evidence
commands fail closed.

The release bundles `scripts/paperlib` and `scripts/paper_library.py`, so a new
local library has no user-specific code-path dependency. Initialize any
explicit library root with the bundled command. A binding may name a separate
exact `paperlib_cli`; otherwise Chalxius uses `LIBRARY/bin/paperlib` when that
regular non-symlink file exists, then falls back to the bundled CLI. Library
records, PDFs, graph captures, and indexes remain outside the installed skill.

## Reviewed Paper default

`paper-logic-freeze` first completes the existing immutable freeze. Only after
that succeeds does the Evidence adapter run. It requires:

1. the exact source artifact and SHA-256;
2. real PDF bytes beginning with `%PDF-`;
3. the frozen snapshot manifest and graph tree;
4. both required independent review profiles for the graph kind;
5. a clean current Paper Logic/Audit report;
6. the complete node-id set in that exact snapshot; and
7. exact Chalxius version and manifest provenance.

A successful sync registers the paper/version/PDF, captures the graph tree,
creates a reviewed Evidence attestation, and writes the local receipt. A
superseding snapshot names the preceding graph and Evidence item. Failure after
freeze returns `pending_unconfigured`, `pending_missing_exact_pdf`, or
`pending_error`; it never rolls back, mutates, or downgrades the frozen local
snapshot. `evidence-sync-retry` is idempotent.

## Non-paper Fact Graph import

There is no automatic scanner or project discovery trigger. Only Operator may
run `evidence-import-fact-graph`, and the command requires an explicit source
root, exact expected source project id, actor, and reason. The source must be a
V5 project with at least one active admitted Fact and must pass the scoped
`chalxius-v5-fact-evidence-audit-1` authority audit. That audit validates the
exact active Fact graph, interfaces, Candidate Releases, correct Certification
Decisions, admission markers, revocations, acceptance events, and dependency
closure. It deliberately does not gate import on frozen rounds, task cards,
modes, Blackboard, Paper/Audit, campaigns, Pulses, or experiments. Those
nontruth workflow surfaces may have been created by an older Chalxius runtime
and are not part of the captured Fact authority.

This is version compatibility, not a weaker truth gate. Supported older V5
Release, Decision, and interface schemas remain readable under their recorded
contracts, and no old task card is rewritten, warned, or reopened. A broken
Fact lineage, missing acceptance event, active revocation, unsupported
authority schema, V1-V4 source, or stale upstream Evidence dependency still
fails closed. Historical revision-1 Fact Evidence capsules remain readable;
new captures label their scoped source audit and exact active Fact set.

The `chalxius-external-fact-evidence-capsule-1` capture embeds, for every active
Fact, the exact Fact bytes, Candidate Release, clean Certification Decision,
admission marker, and statement interface. The shared library validates all
metadata-to-byte hashes and lineage joins. The result is
`source_project_fact_certified` Evidence in the destination library, never an
active destination Fact. If a captured Candidate Release used Evidence
bridges, import also validates the exact library/bridge bindings and records
the selected upstream Evidence ids; it rejects stale or foreign-library
dependencies. Repository verification independently re-derives the dependency
set from the frozen capsule and cross-checks the same immutable bridge records.

After the shared library accepts that Fact capture, the destination
EvidencePlane writes the `eap-*` planning attempt before it inspects any Paper
receipt or creates an `eas-*` request. A failure in that pre-request interval is
therefore visible in `evidence-library-status`. An all-associations retry first
rehashes the original local capsule, checks the library's exact Fact Evidence
record and stored capsule copy, and compares every source Candidate Release
with the release bytes frozen in the capsule. It then revalidates the exact
Paper Evidence refs, snapshots, sync requests, and receipts before deriving and
executing any missing `eas-*`. A changed or missing bound object fails closed;
the retry never substitutes a title, DOI, bibliographic similarity, or source
credibility inference. Planning attempts, requests, and effects remain
nontruth, premise-ineligible Evidence state and never import source-project
Fact authority.

## Retrieval order

Within the shared library, `evidence-query` ranks current
`external_fact_graph` before current `reviewed_paper_graph`. In combined
project planning the order is:

```text
active local Fact
> current external-Fact Evidence
> current reviewed-Paper Evidence
> ordinary Research
> Background index
```

This is a retrieval priority only. Inactive Evidence is excluded unless
`--include-inactive` is explicit, and no query result enters a predecessor
list.

## Verified bridge

`evidence-bridge-prepare` accepts one explicit destination-bound selection.
Paper items accept attested node ids only; external Fact items accept captured
Fact ids only. The library freezes each Evidence record hash, state, and
disposition head into an `evb-*` record with status `prepared_nontruth`.

To use it in a proof, a new Candidate Release must:

1. seal the exact bridge JSON under artifact role
   `evidence_bridge_capsule`;
2. bind `bridge_id` and the artifact SHA-256 in `evidence_bridge_refs`;
3. authorize that artifact role;
4. include the `evidence_bridge_current` required check; and
5. satisfy every ordinary mathematical, typing, scope, source/applicability,
   predecessor, computation, challenge, and assurance check.

Chalxius independently validates the bridge record hashes and destination,
then asks the live library to recheck its disposition head at Candidate Release
creation, verifier-capsule generation, certification, and Fact admission. The
fresh verifier receives the exact bridge in the closed capsule and must verify
the destination claim independently. The existing gateway remains the sole
Fact visibility switch.

## Correction and propagation

Evidence correction is append-only. Operator may mark an item `challenged`,
`superseded`, `withdrawn`, `stale_source`, or restore it with a new `active`
disposition that supersedes the complete current head. `superseded` requires a
replacement Evidence id. Historical bytes are never deleted.

Any head change makes every old bridge stale, even if a later disposition says
`active`; a new bridge must freeze the new head. The library reports all
affected prepared bridges and destination project ids. The project adapter
reports matching Candidate Releases and admitted Fact ids. It does not silently
rewrite or revoke an admitted Fact. Operator must choose a reviewed repair,
reaffirmation through a new bridge/release, or ordinary Fact revocation and
cascade.

Correction propagation is transitive across re-export. An external Fact
Evidence item whose source release used now-ineligible upstream Evidence
derives `stale_source`; any later Evidence depending on it does the same to a
fixed point. The disposition result reports every Evidence id and prepared
bridge whose current state changed, while historical Facts remain visible for
explicit Operator review.

## Roles and commands

- Main: `evidence-library-status`, `evidence-query`, `evidence-sync-retry`,
  `evidence-bridge-prepare`, `evidence-bridge-check`,
  `evidence-impact-report`.
- Operator: all Main commands plus `evidence-import-fact-graph` and
  `evidence-mark`.
- Host remains dispatch/status/audit only and gains no Evidence reading,
  planning, or mutation authority.
- Worker and verifier receive Evidence only through their already bounded task
  or verifier capsules; they do not query the live cross-project library.

## Compatibility

The feature is additive. Projects without `evidence/` remain readable. New
Candidate Releases may add `evidence_bridge_refs`; historical releases and
verifier capsules without the field retain their exact hashes and behavior.
No running 0.4.0 project is backfilled, rejected, or asked to redo work.
An importing runtime never compares a frozen source task card with itself to
decide whether admitted source Facts are eligible for Evidence capture.
