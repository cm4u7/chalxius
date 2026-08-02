# Known architecture limitations in Chalxius 0.6.3

The numbered entries below retain their immutable owner ledger: CHX-001 through
CHX-017 belong to `run-20260801T072127934348Z-16d73c1b37d5`, CHX-018 through
CHX-057 belong to `run-20260801T233737840117Z-a29d00a787c1`, CHX-058
through CHX-060 belong to `run-20260802T190108619281Z-6b046e728879`, and
CHX-061 belongs to `run-20260802T203525083918Z-e81514efe3c7`, while CHX-062
belongs to `run-20260802T214123599238Z-d206bd85e676`.
The qualified current head is
`run-20260802T214123599238Z-d206bd85e676/CHX-062`; a short identifier never
changes owner merely because a later release includes it.
The two immediately preceding qualified heads were
`run-20260802T203525083918Z-e81514efe3c7/CHX-061` and
`run-20260802T190108619281Z-6b046e728879/CHX-060`.

Chalxius 0.6.3 retains the 0.6.0/0.6.1/0.6.2 prospective repairs for every architecture mechanism recorded as
CHX-001 through CHX-017 in the 2026-08-01 research-draft field run, plus the
Campaign-lineage and CHX close/status integration issues found while cautiously
restoring Brave Future L3/L4 and exercising revision-3 accounting. It also repairs
CHX-020 through CHX-035, including durable stance authorization, cryptographic
principal coordination, Certification/Gateway integration, registry-wide audit and
cache authority, complete active-runtime validation, terminal write isolation,
pre-write planning atomicity, and transactional global-cutover continuity. It
extends closure through CHX-036 to CHX-062 with the reusable Paper Research
Pipeline, which preserves inherited Paper topology, separates source
occurrences from logical operators, validates claim-level literature support,
requires a Paper-subject atomic preflight before the native admission path,
preserves domain-indexed research-target continuity, and binds public release
disclosure back to the exact private CHX ledger. Closure is
based on executable regressions, full inherited-suite
validation, a frozen independent review matrix, and installed-tree validation;
package hashes or successful installation alone are not issue evidence.

The repair does not rewrite a historical Paper snapshot, Research record,
Candidate Release, Certification Decision, admission, Fact, task card, CHX
ledger, or external Evidence object. Old contracts remain byte-exact readable.
Users must explicitly create a new strict research-draft plan and copy-on-write
successor artifacts to use the stronger path.

## Resolved field mechanisms

1. **CHX-001 — draft authority routing.** New Paper intake distinguishes
   `research_draft` from `external_finished_publication`. A draft must enter the
   strict whole-Paper admission path; a finished external work remains Evidence
   until an explicit bridge and fresh admission.
2. **CHX-002 — domain-general draft lifecycle.** One lifecycle core now freezes
   profile-specific philosophy, mathematics, empirical, or unioned mixed
   closure obligations before release.
3. **CHX-003 — cross-plane preflight.** Candidate sealing, checking, capsule,
   decision, and Gateway replay the same hash-bound research-draft preflight and
   validated dependency receipt.
4. **CHX-004 — single-row Fact mapping.** Node disposition is separate from
   many-to-many Paper/Facts successor mappings; one Paper node may split and one
   Candidate may inherit several Paper predecessors.
5. **CHX-005 — failure-surface collision.** Failure surfaces are target,
   component, statement-hash, scope, modality, quantifier, and applicability
   qualified under graph-global content ids.
6. **CHX-006 — weaker-paraphrase shadowing.** Every paraphrase declares a
   semantic direction, exact source components, residual dispositions, and
   qualifier transport; narrowing or broadening cannot claim equivalence.
7. **CHX-007 — source-unit self-coverage.** Full-artifact coverage is
   proposition-total and a source unit cannot count as its own argumentative
   reconstruction.
8. **CHX-008 — generated-version witness drift.** Source spans, proposition
   components, and semantic mappings are version-neutral and hash-bound;
   version labels in generated witness prose fail the strict gate.
9. **CHX-009 — speaker/proposition leakage.** Exact spans, speakers,
   attributions, source-unit locality, and reciprocal mappings prevent adjacent
   or quoted text from silently supporting another claim.
10. **CHX-010 — repeated disposition scans.** One target-total batch validates
    the immutable plan and Research index once and publishes all dispositions
    atomically.
11. **CHX-011 — technical-term conflict.** A normalized term/sense registry
    binds exact definitions across the whole plan and rejects one sense with
    conflicting definitions.
12. **CHX-012 — release/read revalidation cost.** A content-addressed dependency
    receipt and stat/hash fingerprint cache revalidate only changed inputs while
    retaining fail-closed hash checks.
13. **CHX-013 — unpromoted discoveries.** CHX ledger revision 3 records a stable
    finding first, requires transactional promotion, reasoned merge, or reasoned
    exclusion before close, preserves typed relations, and supports immutable
    successor ledgers plus deterministic report verification.
14. **CHX-014 — monolithic verification.** A risk-derived immutable work plan,
    context-bounded reviewer capabilities, Ed25519 host attestations, and
    deterministic monotone aggregation provide composable independent review;
    conflict adjudication and Gateway admission remain separate authorities.
15. **CHX-015 — project-relative Paper refs.** Every Paper EvidenceRef implies a
    release-relative transport closure; release, capsule, decision, and Gateway
    validate the same sealed bytes.
16. **CHX-016 — language/domain interface loss.** Candidate authors supply a
    language-neutral schema-6 semantic interface with explicit operators,
    hypotheses, quantifiers, typed roles, temporal/applicability/comparison
    scope, and predecessor transport. Lexical detectors remain suspicion
    generators only.
17. **CHX-017 — self-declared atomicity.** Candidate component inventories are
    derived from source propositions, must be Candidate-total, and are checked
    against independently challengeable failure surfaces and fresh reviewer
    reconstruction.
18. **CHX-018 — Campaign result lineage.** A Campaign-scoped V5 worker result now
    inherits the exact frozen Campaign id at ingestion, preserving the causal
    chain needed by explicit L3/L4 projections without consulting `ACTIVE`.
19. **CHX-019 — first-close/report projection drift.** Revision-3 close writes
    the deterministic architecture report and then returns the same verified
    status projection as every idempotent close and status read; callers cannot
    mistake an initially incomplete response for the durable ledger state.
20. **CHX-020 — self-asserted stance reversal.** A major research-draft
    narrowing or reversal now requires a durable Operator-authored decision
    bound to the exact plan, target, prior stance, impact, and disposition batch.
21. **CHX-021 — self-supplied verifier identity.** Parallel verification now
    uses a project-bound Operator trust registry with strict prime-order
    Ed25519, principal, role, Host-context, and trust-domain bindings.
22. **CHX-022 — detached verification protocol.** Candidate Release,
    Certification, Gateway, immutable heads, freshness, and admission all
    require and revalidate the same eligible aggregate.
23. **CHX-023 — public-key identity aliasing.** One Ed25519 public key cannot be
    registered under multiple principals, roles, Host contexts, or trust
    domains.
24. **CHX-024 — locally reassuring registry audit.** Subsystem and top-level
    audits validate the complete key registry, including cross-record
    uniqueness, rather than accepting individually valid rows.
25. **CHX-025 — idempotent-registration authority bypass.** An existing-key
    retry validates the full current registry before returning success.
26. **CHX-026 — warm-cache authority bypass.** Direct reads and immutable-record
    cache hits recheck registry-wide authority; a cache stores bytes, never an
    authorization decision.
27. **CHX-027 — global cutover erased historical readability.** Terminal V5
    cards may authenticate their exact historical runtime through a
    host-managed content object plus immutable identity registry, without
    rewriting cards or treating archived code as executable. Active work and
    all writes remain bound to the exact live runtime.
28. **CHX-028 — archive trust-root and ancestor-link escape.** Runtime roots,
    archive roots, registry inputs, manifest parents, and files are traversed
    with component-wise no-follow checks. The archive lives outside skill
    discovery, rejects traversal, links, special or cross-device entries, is
    sealed read-only, and is fully revalidated on every historical resolution.
29. **CHX-029 — identity-only active runtime checks.** Active task cards and
    worker CHX startup rehash every manifest-listed byte; one bounded phase may
    deduplicate only the same successful identity scan.
30. **CHX-030 — terminal experiment write escape.** V5 experiment finalize now
    requires an active work unit like every other experiment writer; terminal
    retries fail before mutation and preserve an exact byte inventory.
31. **CHX-031 — post-write plan preflight.** `plan-round` validates the complete
    live runtime under the project lock before any snapshot, directory, context,
    prompt, or task-card write.
32. **CHX-032 — manual cutover coupling.** Install and rollback use one
    executable gate with explicit project inventory, exact candidate bytes,
    prior/new archives, pre/post status and audit, and automatic restoration on
    any post-swap failure.
33. **CHX-033 — one live alias required to match every historical version.**
    Dry-run and real cutover share one archive-eligibility preflight: the live
    installation is archived once, while each distinct old task-card identity
    must resolve through its freshly revalidated sealed host archive. A
    multi-version project never asks one mutable path to contain several
    historical runtimes simultaneously.
34. **CHX-034 — optional candidate approval binding.** The cutover CLI and
    programmatic gate require the exact externally approved candidate manifest
    hash for dry-run, install, and rollback; internal self-consistency cannot
    substitute for release authorization.
35. **CHX-035 — weak stance surrogate in release regression.** End-to-end
    research-draft fixtures freeze and hash the complete limited restorative
    stance: a justified minimum moral-agency or motivational-capacity threshold,
    conditional restoration for later voluntary choice, and rejection of
    universal or maximization-oriented compulsion. The mechanism remains
    domain-general; bytes preserve operator intent while fresh reviewers judge
    philosophical equivalence and atomicity.
36. **CHX-036 — strict Paper features activated too late.** One prospective
    activation record now gates the stronger research-draft path. Legacy Paper
    bytes stay readable but cannot silently claim current strict adequacy.
37. **CHX-037 — successor research detached from the inherited DAG.** The
    native successor is copy-on-write, keeps every stable local node id and
    edge, and hash-binds all non-native metadata that cannot enter the native
    bundle.
38. **CHX-038 — source operator/qualifier occurrences omitted.** Exact
    source-unit occurrence spans and dispositions are materialized in a
    separate `source_occurrence_ledger`; they do not inflate the semantic
    `operator_ledger` merely because a lexer found a surface word.
39. **CHX-039 — atomic semantics and topology checked separately.** The Paper
    validator jointly checks claim/inference/target edges, ordered premises,
    source-component mappings, composition witnesses, and exact source spans.
40. **CHX-040 — retained predecessor identity could drift semantically.**
    Stable-identity merge rejects same-id/different-content collisions, and
    successor receipts bind predecessor graph and coverage hashes.
41. **CHX-041 — strict cutover conflicted with immutable Paper lineage.** A
    prospective native successor is staged and reviewed as a new object; no
    legacy Paper graph is rewritten and no predecessor Fact authority is
    inherited.
42. **CHX-042 — DOI or bytes accepted without publication identity.** The
    evidence gate checks bound identity records against title, authors, year,
    DOI where present, and exact retained source bytes.
43. **CHX-043 — citation presence substituted for claim support.** Every
    substantive literature claim now needs a locator, retained witness,
    support kind, mapped Paper objects/targets, and independent support-review
    disposition. Bibliographic context cannot satisfy substantive support.
44. **CHX-044 — closed operator vocabulary rejected exact new operators.** A
    producer-observed unrecognized token may enter only as exact anchored
    `kind=other`; known semantic kinds and scope checks remain strict.
45. **CHX-045 — represented source components could map to zero graph nodes.**
    Represented components require nonempty valid mappings and a composition
    witness; exclusions require a reason and no mapping.
46. **CHX-046 — shard merge deduplicated by full value.** Merge now keys on
    stable identity and fails on semantic collision instead of treating
    equality or list position as identity.
47. **CHX-047 — node cuts lost inbound component coverage.** The strict native
    successor forbids topology cuts by preserving the complete node/edge set.
    Normalized deltas remain nontruth and cannot authorize later cuts without
    explicit successor and inbound coverage mappings.
48. **CHX-048 — heterogeneous delta receipts had no common semantics.** Known
    receipt dialects normalize into one content-bound, authority-free delta IR
    with stable identity redirects.
49. **CHX-049 — flat source components hid partitions.** Source proposition
    components now carry atom/partition hierarchy and paths; hierarchy cycles,
    unknown parents, and atom children fail closed.
50. **CHX-050 — normative bridges and classification repairs shared one
    label.** Inference `semantic_operation` distinguishes argumentative,
    normative, conceptual, definition/classification, and relation operations;
    relabelling cannot acquire normative authority.
51. **CHX-051 — PDF line hyphenation produced false witness mismatches.** The
    corroborated layout profile joins extraction-visible line breaks while
    preserving ordinary inline compounds.
52. **CHX-052 — frontier construction discarded premise order.** The ordered
    frontier retains position-bearing premise edges and a premise-order hash;
    recomputation rejects permutations, gaps, or payload/edge disagreement.
53. **CHX-053 — new runtime files escaped the declared compatibility
    closure.** A shared runtime-compatibility validator now expands the exact
    protected path contract, rejects links and nonregular files, recomputes the
    path/content digest and count, and checks that every declared changed path
    lies inside that closure and matches one canonical inventory digest. Both
    self-test and capability-preservation tests call the same mechanism rather
    than maintaining another literal inventory, including the public Paper
    Pipeline CLI.
54. **CHX-054 — receipt ids were trusted without recomputation.** Evidence and
    native-successor consumers now enforce exact receipt field sets, recompute
    the type-prefixed content address, validate count and authority invariants,
    and bind the complete receipt hash into Paper preflight. The domain-neutral
    reliability matrix mutates both receipt families alongside graph, frontier,
    DAG, and stance surfaces.
55. **CHX-055 — research continuity conflated mathematical targets with
    argumentative stances.** One domain-indexed
    `research_continuity_contract` now preserves argumentative stance for
    philosophy, exact targets/hypotheses/domains/quantifiers for mathematics,
    exact questions/estimands/populations/exposures/outcomes/scopes for
    empirical work, and explicit component adapters for mixed work.
    Mathematics expressly permits `proved`, `disproved`, or
    `unresolved_with_obstruction`; a counterexample to the unchanged target
    is not a stance reversal, while a proof of an altered target is not a
    resolution.
56. **CHX-056 — resolved mechanisms could be omitted from public release
    disclosure.** A machine-readable contiguous public issue registry now
    binds the exact release-ledger issue set, latest issue id, explicit
    `KNOWN_LIMITATIONS.md` enumeration, and required release-traceability
    semantics. The publication preflight fails on unresolved findings,
    unresolved issues, registry drift, omitted ids, stale target semantics, or
    document mismatch while keeping the private ledger and research content
    out of the public package.
57. **CHX-057 — public CHX short identifiers collided across immutable
    ledgers.** The public-disclosure registry now binds the exact
    `ledger_run_id`, returns qualified `run_id/CHX-NNN` identities, and
    requires public documentation to state the namespace. A matching short id
    from another historical ledger can no longer satisfy the publication gate.
58. **CHX-058 — routine continuation status exported the complete Paper
    closure.** This is the graph-scale applicability extension of CHX-012:
    `paper-continuation-status` now defaults to a bounded deterministic summary
    with exact identity, state, currentness, counts, adequacy, and receipt.
    Topology, bindings, unresolved ids, and dispositions require explicit
    `--full`; compact and full views share the same receipt and have no truth or
    admission effect.
59. **CHX-059 — a single-run public registry requalified predecessor issue
    identities.** Public disclosure revision 2 now binds an ordered ledger lineage
    with exact run ids, file digests, contract revisions, predecessor
    links, and non-overlapping per-run issue ownership. Qualified ids are
    derived from their actual owner, never the newest run.
60. **CHX-060 — successor ledgers lost transitive issue lineage.** Ledger
    revision 4 reads and freezes the complete digest-bound predecessor chain at
    successor creation, rejects cycles or digest drift, and preserves numbering
    and typed relations across issue-free intermediate ledgers. Revision 3
    remains byte-exact readable and is not rewritten.
61. **CHX-061 — bounded status still reconstructed the complete Paper
    closure.** The compact serializer introduced for CHX-058 reduced output but
    still called the full validator, repeating plan, Paper, Research,
    disposition, and writing scans. Routine status now validates only an atomic
    content-addressed HEAD plus immutable receipt. Every supported mutation
    advances the index; directory-generation drift fails closed until an
    explicit full rebuild proves exact count, adequacy, and receipt equality.
    On the inherited two-plan field project, the one-time rebuild took 310.45 s;
    indexed all-plan and current-plan reads then took 0.10 s and 0.12 s. This is
    an observation-path repair with `truth_effect=none`.
62. **CHX-062 — exact-runtime host entrypoints self-contaminated before
    validation.** Ordinary Python invocation imported local runtime modules
    before validating the candidate, allowing default bytecode generation to
    create unmanifested `.pyc` files and make the official cutover reject its
    own otherwise exact tree. `runtime_cutover.py`, `archive_runtime.py`, and
    `chx_ledger.py` now disable bytecode writes before any local import. A clean
    copied-tree subprocess regression removes all bytecode-control environment
    variables and proves that every default entrypoint creates zero cache or
    bytecode files; three independent mutants guard the three seams. Genuine
    unexpected files remain rejected, and the repair has `truth_effect=none`.

## Deliberate residual boundaries

- Brave Future implements only BF-1 through BF-3 in advisory mode. It can
  project strict L4 repair lineage and persist one bounded reassessment receipt,
  but cannot plan, dispatch, create Research, mutate Campaign state, close a
  Campaign, or affect truth. `plan_one`, `execute_one`, and
  `plan-round --reassessment` remain unimplemented and rejected.
- Research-draft preflight and composable verification establish structural and
  evidential readiness, not philosophical, mathematical, or empirical truth.
  Fresh independent reviewers and the ordinary Fact Gateway remain mandatory.
- `auto` may allocate broad research work quickly; it cannot compress Paper
  topology, source provenance, atomic components, verifier coverage, or Fact
  admission requirements.
- Historical role-less or 0.5.0 Paper objects remain readable as legacy
  nontruth. They cannot satisfy a new strict whole-draft admission claim without
  an explicit copy-on-write reconstruction.
- External publications, citations, peer review, Evidence bridges, Reader
  projections, Learner records, Blackboard nodes, CHX findings, Brave Future
  receipts, and prose remain nontruth unless their exact claims separately pass
  the normal Candidate, Certification, and Gateway path.

These boundaries are intentional authority separations, not open CHX defects.
Any newly observed architecture-caused mechanism must enter a new revision-3
finding ledger before it may be omitted, merged, promoted, reported, or closed.
