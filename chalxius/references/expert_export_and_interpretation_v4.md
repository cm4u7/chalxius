# Expert Export and Interpretation v4

Read this reference before using `interpret` mode, terminology provenance, claim cards, or an
expert-facing document export.

## Claim identity

Keep these objects machine-distinct:

- the literal, versioned published source claim;
- a researcher-defined variant with an explicit parent and nonempty semantic diff;
- the convention profile under which either claim is read;
- the admitted local conclusion, if any.

A researcher variant is not author-confirmed by default. Do not silently attribute a repaired,
strengthened, weakened, or convention-translated claim to the source.

## Statement and quantifier export

V4 facts expose labeled statement clauses and a quantifier ledger. An expert export must retain the
order, polarity, witness identity, and dependency of every load-bearing quantifier. In particular,
do not turn a dependent existential witness into a uniform witness.

Predecessor use is clause-specific and carries hypothesis witnesses. Export the admitted
statement-only interface, never a predecessor proof paragraph or a stronger proof-only lemma.

## Terminology provenance

Each load-bearing term records its definition, origin, source locator, export policy, replacement,
and one `[TERM:KEY]` proof anchor. Supported origins are source, standard, local shorthand, and
legacy unknown. Supported export policies are keep, define, replace, and forbid.

Before an advisor-facing email, note, or PDF:

- replace local shorthand;
- define terms before first use;
- reject forbidden or legacy-unknown terms;
- include the literal source claim, convention profile, admitted conclusion, and AI-assistance
  disclosure from the claim card.

Generate and lint the communication boundary explicitly:

```bash
"$MGRAPH" --root "$PROJECT" --role main export-claim-card FACT_ID \
  --audience advisor --output reports/claim-card.json
"$MGRAPH" --root "$PROJECT" --role main lint-expert-document \
  --input DRAFT.md --claim-card "$PROJECT/reports/claim-card.json" \
  --receipt-output reports/expert-lint-receipts/advisor-draft.json
```

The card is hash-bound and carries the literal source claim, researcher variant/diff, source
locator, exact convention summary, admitted conclusion, quantifier ledger, computation independence
matrices, limitations, reproduction artifacts, terminology, and an AI-assistance disclosure
placeholder. The document must replace that placeholder with one visible, substantive
`AI assistance:` disclosure before lint can pass. Required fields hidden in an HTML comment do not
count. Terminology matching is Unicode-normalized and case-insensitive, so capitalization is not an
escape from `replace` or `forbid`. The card also carries `admission_evidence_version` and an explicit
assurance label. A migrated V3 fact is labeled `legacy-v3-inherited`, and its mandatory limitation
states that a V4 export does not relabel it as V4-reviewed. Lint checks those communication
invariants only; it does not certify mathematical correctness.

The lint command always writes a project-contained, write-once receipt. If `--receipt-output` is
omitted, the engine derives one deterministic filename below
`reports/expert-lint-receipts/`. The receipt binds the project, linter revision, exact draft bytes,
exact claim-card bytes, semantic claim-card hash, audience, complete error list, scope, and its own
hash. Replaying identical bytes is idempotent; changing bytes at an explicit receipt path is an
immutable-evidence collision. Before external release, the communication-readiness consumer
revalidates the receipt against the current draft and card. Missing, failed, or stale evidence
cannot satisfy a required `terminology_export_lint` feature. Passing changes communication
readiness only, never fact admission or mathematical truth status.

Terminology/export lint is mandatory when preflight declares an expert, advisor, or publication
audience or terminology-sensitive output. It remains optional for purely internal exploration where
it would add clerical cost without changing truth status.

## Interpret mode

`interpret` turns a graph or computation into an exploration mechanism, not a theorem. A mechanism
must name what it explains, domain clauses, conventions, a mechanism statement, known failures,
remaining gaps, and at least one falsifiable consequence with a suggested next mode. Its
`truth_status` is always `exploration`.

If no falsifiable consequence can be stated, return a `dead_end`; do not decorate intuition as a
mechanism. Promotion creates actionable memory only. Proof or refutation still requires the normal
fact workflow.

External interpretation prose uses a separate nontruth card and receipt path:

```bash
"$MGRAPH" --root "$PROJECT" --role main export-interpret-card NODE_ID \
  --audience advisor --output reports/interpret-card.json
"$MGRAPH" --root "$PROJECT" --role main lint-interpret-document \
  --input DRAFT.md --interpret-card "$PROJECT/reports/interpret-card.json"
```

The card accepts only an immutable current-project `mechanism` node with
`truth_status="exploration"` and a fully valid mechanism payload. It binds that original node even
after explicit frontier promotion, plus exact source/explanation/domain/convention references,
statement, every consequence/failure/gap, terminology provenance, the literal
`candidate interpretation / not an admitted theorem` boundary, audience, AI-disclosure placeholder,
and its semantic hash. The linter requires those fields in visible prose; HTML comments do not
count. Its write-once receipt lives below `reports/interpret-lint-receipts/`, uses a distinct schema,
binds exact draft/card bytes, and has `truth_effect="none"`. It cannot satisfy fact claim-card lint,
promote a node, create admission evidence, or change any mathematical state.

## Domain certificate and atomic bundle

A reusable domain certificate must state all required labeled clauses, including base, poles,
zeros, ramification, disjointness, vital points, partner regularity, self-duality, and exclusions.
Reuse requires an admitted fact, not a candidate or blackboard note.

An atomic fact bundle is a candidate mini-DAG. Preflight requires it when candidate facts have
internal dependencies or explicitly need all-or-none visibility; several independent facts do not
trigger it. Its facts remain invisible until one accepted marker validates the whole acyclic
bundle. A partial write or crash exposes zero facts.

A task card that requires an atomic bundle rejects an ordinary single-fact return. Before its
acceptance marker, the dedicated mini-DAG is quarantined from truth. After one clean bundle review
and all-or-none acceptance, its facts enter ordinary `show/search/context/closure`, campaign target,
statement-interface, and cascade-revoke paths together.

Before review, `make-bundle-verifier-task` freezes a packet plus a verification manifest. Every
external admitted predecessor appears through its active statement-only interface and literal
statement; no predecessor proof is included. The review must bind the fact-bundle manifest, packet
SHA-256, and verification-manifest SHA-256. Tampering with the packet or an interface therefore
blocks both review and admission.
