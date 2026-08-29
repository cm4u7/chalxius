# Fact admission contract: 1.0.0 Fact Alpha and legacy V5 authority

## Current prospective path: Research certification overlay

From 1.0.0 onward, new Fact work uses one mathematical graph: immutable
Research nodes plus append-only certification grants. The certified unit is an
entire exact Research record and its top-level `claim`. Chalxius does not create
a duplicate Fact statement/proof node, does not derive internal statement
surfaces from historical prose, and does not add a redundant `claim_sha256` to
the record hash.

Current admission requires:

1. Main has explicitly marked the exact Research node as load-bearing in the
   Fact frontier. The mark and its rationale have no truth effect.
2. `plan-fact-packaging` freezes the active marks, exact current COW terminals,
   record hashes, Campaign/target associations, and Research supervision
   coverage. The plan neither selects mathematics nor launches a worker.
3. A packaging agent classifies every selected node as packaged,
   `needs_split`, or `blocked`. Each packaged node receives a semi-formal
   interface whose conclusion exactly equals the Research `claim`; assumptions,
   domain/types, quantifiers, limitations, and certified Research predecessors
   are explicit.
4. Every certified predecessor is either earlier in the same acyclic component
   or already has an active Research certification grant. Descriptive
   `relation` strings, receipts, source links, and general Research context are
   never proof-dependency edges.
5. One independent verifier checks the complete Research bytes, mathematics,
   scope, proof dependencies, sources/computation, and interface. Component
   decisions are isolated: correct components may advance even if an
   independent component has a minor or fundamental error.
6. The verifier differs from the Research authors and packager. The verifier
   may falsify freely, but does not train or duplicate the ordinary Research
   supervisor's theorem-attack learner.
7. The mechanical Gateway differs from verifier and packager, rechecks exact
   current Research/COW and predecessor-grant bindings, writes all grants, and
   publishes one acceptance marker as the sole visibility switch.
8. A minor error uses complete-node COW and a same-verifier batch recheck of
   the complete affected component, without another ordinary supervisor. The
   verifier cannot author the repair. A fundamental error returns to ordinary
   Research and may abandon the Candidate component.
9. A COW successor or inactive certified predecessor makes the affected grant
   and its certified descendants `needs_reverification`. Old grants remain
   historical; they are not silently relabelled or deleted.

`fact-frontier` is a derived certification work view. Only Main's importance
marks and explicit dispositions persist; ready batches, in-flight state,
certified heads, and re-verification propagation are recomputed. Main schedules
packaging at natural research windows. No timer, backlog threshold, automatic
worker dispatch, or synchronous Research-to-Fact requirement exists.

New Research may declare `certified_research_dependencies`. The Research writer
resolves each id to an active grant and freezes exact Research/grant hashes;
future task cards carry the certified statement interface and proof bytes.
Legacy V5 Facts remain readable authority with no invented Research mapping.

## Legacy V5 Candidate/Fact authority

The remainder of this document specifies the immutable 0.x Candidate Release,
Certification Decision, and physical Fact-node path needed to read and audit
existing authority. It is not the prospective authoring path for Fact Alpha.

The Fact admission contract is identical in `fast`, `auto`, and `deep`. Only
the V5 lifecycle may expose new Fact bytes.

Admission requires all of the following:

1. an exact sealed Candidate Release containing one Fact or an atomic internal
   mini-DAG, with all external predecessors already active V5 Facts;
2. exact statement interfaces, predecessor uses, quantifiers, conventions,
   external-source fidelity, applicability witnesses, and controlled elementary
   uses; a current-assurance use of a legacy conditional clause with no exported
   premises must resolve one exact named premise clause on an exact predecessor
   and witness its full statement hash, or fail closed;
3. for a newly frozen 0.4.3 card, exact per-obligation dispositions and the
   risk-specific Research assurance required by that card; frozen older cards
   retain their original contract;
4. current source-evidence v4 for new external uses, including complete
   hypothesis/conclusion coverage, reproducible status-query evidence, and
   typed conclusion transports;
5. exact artifact hashes, formula-to-code semantic alignment, and independent
   replay for load-bearing computation;
6. for series-product coefficient computations, a machine-derived valuation
   order budget plus a bound deeper truncation replay;
7. exact Paper Logic/Audit snapshot and nodewise coverage bindings when the
   validation subject is a paper; a continuation-descended release also carries
   one content-addressed currentness capsule over the status generation, changed
   closure, dispositions, source/writing artifacts, and Candidate interfaces;
8. for any Evidence use, one exact destination-bound bridge capsule whose
   Evidence record hashes and disposition heads are current, sealed under the
   authorized `evidence_bridge_capsule` role, and covered by the
   `evidence_bridge_current` verifier check; the bridge remains nontruth;
9. automatic inclusion and explicit disposition of every existing adverse
   Research item linked to the selected Research branch, including a completed
   refute assignment whose outcome was evidence or insight rather than a
   counterexample; adverse assignment provenance, not outcome kind alone,
   controls binding and verifier exclusion;
10. proof-lineage conservation for copy-on-write successors, with statement and
   proof changes reviewed separately;
11. a fresh independent verifier restricted to the neutral frozen capsule,
   using the complete decision template and standalone preflight, with exact
   candidate and edge panels and every requested check covered once; for V5 the
   verifier writes a draft only, while the copied host submission program
   quarantines invalid drafts and is the sole producer of the immutable formal
   review plus its content-addressed success receipt;
12. one immutable Certification Decision bound to the release and capsule,
   recorded only by the Gateway through `certification-record`; a verifier
   supplies frozen review bytes but does not own Certification publication;
13. gateway revalidation of the accepted decision followed by all-or-none Fact
   visibility; active lineage validation uses a two-phase command-local
   projection so a bounded frozen-authority reentry validates only local
   Release, marker, and Fact bytes, while the outer frame completes all Research,
   historical-runtime, Decision, successor, and lineage checks and requires
   exact provisional/full agreement; one ephemeral admission inspection
   context may be shared by immutable pre-lock readers, but it is discarded at
   the publication boundary and a distinct fresh context is created under the
   mutation lock for historical-release and lineage replay; the admission
   marker remains the sole visibility switch and post-marker event/interface
   completion is exact and idempotent; and
14. cascade revocation plus a clean current graph and workflow audit.

Research, Evidence, Candidate Release, Certification Decision, Paper/Audit,
Blackboard, Pulse status, profile-readiness advice, campaigns, experiments,
novelty records, project background, Reader packets/HTML, expert prose, and
Learning records are not Fact premises.
Campaigns, goal coverage, plan-selection receipts, next-attention projections,
and historical retired advisory sidecar bytes remain in that nontruth set.
They supply context and lineage only and create no Fact premise.

## Selective checkpoint and Candidate batch seed

`selective-fact-checkpoint` is a Main-only, nontruth operation after Main has
explicitly selected the load-bearing Research ids and before Candidate
authoring. Its exact input is one object with `schema_version=1`, a nonempty
`objective`, one to sixteen `target_rationales` containing exact `research_id`
and nonempty `reason` strings, and zero to thirty-two `excluded_research`
entries with the same exact fields. Targets and exclusions must be disjoint.

The command fully validates every selected Research record, its ancestry,
staleness, review-only status, and required current supervision. Unselected
Research contributes only bounded content-addressed structural envelopes for
connectivity and invalidation checks. The immutable receipt reports assurance,
source-use, computation-manifest, obligation-disposition, downstream-reuse,
and blocker projections. It does not infer mathematical correctness from
centrality and does not select a target automatically.

Every receipt includes a deterministic Candidate batch seed. It freezes the
dependency edges among explicitly selected targets and partitions the ready
set into disjoint dependency-connected **authoring batches**. These batches are
not Fact atoms: every later Candidate Fact must expose exactly one semantic
conclusion atom, while an authoring batch may produce several such Facts joined
by an explicit internal Candidate DAG. Independent targets remain singletons so
one failed adverse review or verifier decision does not invalidate unrelated
packaging. A blocked selected premise propagates a checkpoint blocker to each
selected dependent. Main may later combine independent batches only after
reviewing their common failure surface and must still preserve one-conclusion
Fact atomicity plus exact predecessor closure. The seed is planning input only:
it does not automatically atomize Research, author a Fact statement or proof,
launch a worker, or waive Candidate preflight, fresh adverse review, verifier
coverage, Gateway-owned Certification, or Gateway admission. Assignment or card
creation is not dispatch; Main must launch the selected worker through the host
and confirm the actual start.

Before Research replay or packaging, every prospective Candidate command applies
the same cheap semantic gate. If a Fact carries a semantic interface, exactly
one component may be a conclusion, mathematical claim, or empirical hypothesis;
premise components may remain separate. Without that interface, exactly one
`[CLAIM:*]` statement clause is allowed. New 0.7.13 worker cards that require a
`candidate_fact` artifact also require exact canonical Fact Markdown bytes at
return preflight. Main may instead author the same exact canonical Candidate
Fact bytes, including a canonical Fact file in a sealed Main-authored Candidate
Release. Authorship, container, actor labels, and other provenance metadata
preserve lineage but do not establish mathematical validity or add an admission
gate.
Older frozen task cards retain their original byte contract and remain
replayable as historical nontruth lineage.

For each exact Candidate-Fact target, Main may call
`plan-candidate-adverse RESEARCH_ID`. The target must be active, non-stale, bind
exactly one current `candidate_fact` artifact, and carry
`independent_adverse_required=true`. The planner is host-scope-bound and
idempotent for an exact retry. It creates only a nontruth refute assignment and
card; Main must still launch and confirm the worker. The Candidate disposition
and every later truth gate remain mandatory.

For exact canonical Candidate Fact bytes selected for one Research target, Main
first calls
`prepare-candidate-adverse-target SELECTED_RESEARCH_ID --candidate-fact PROJECT_RELATIVE_PATH`.
The public command is Main-only, fixes `actor="main"`, and accepts no
`--actor` override. It canonical-validates and consumes those exact project-contained
bytes, derives every applicable completed supervision result for the selected
Research (possibly none when no supervision scope applies), and creates or
reuses one content-addressed nontruth synthesis target. The bytes may be
Main-authored; producer, container, author, and other provenance metadata remain
lineage rather than mathematical gates. The command does not perform
atomization, Candidate packaging, adverse disposition, fresh verification,
Gateway-owned Certification, Gateway admission, or Fact admission.

`validate-return` observes one bounded read-only snapshot of the canonical
return and declared artifacts. A transient `ENOENT` or `ESTALE` while a safe
snapshot is not yet visible may be retried after visibility stabilizes and must
not create quarantine evidence. Unsafe filesystem objects and visible
malformed, hash-drifted, schema-invalid, or semantically invalid bytes remain
fail-closed and follow the ordinary local-quarantine contract. This retry rule
adds no truth or admission state.

Reasoning depth does not define the validation blast radius. Current receipts
may cover unchanged sealed dependencies, but every new or invalidated atomic
claim and the necessity-derived changed predecessor/defeater/source/interface/
writing/admission closure must be freshly checked. Missing, drifted, ambiguous,
schema-changed, or forensic state fails closed to full validation. Paired
adverse workers add Research pressure to load-bearing targets, not a second
Certification or Fact gate.

V4 and original Danus Facts are readable historical artifacts but are not
active V5 predecessors. If their mathematics is needed in V5, it must be
submitted and certified as a new V5 Candidate Release; V5 never silently
inherits or relabels their authority.
