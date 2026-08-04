# 🧭 Chalxius

Chalxius helps researchers turn drafts, papers, proof ideas, computations, and
teaching goals into a working research graph that Codex can inspect, extend,
attack, verify, and present. Exploration stays useful; reusable Facts remain
explicitly verifier-gated.

**[🚀 Explore the live cases](https://cm4u7.github.io/chalxius/)** ·
[📚 Read the use cases](USE_CASES.md) ·
[📦 Download v0.6.5](https://github.com/cm4u7/chalxius/releases/tag/v0.6.5) ·
[✅ See validation](VALIDATION.md) ·
[🏗️ Architecture](ARCHITECTURE.md) ·
[🧾 Resolved CHX mechanisms](chalxius/KNOWN_LIMITATIONS.md)

## 🚀 Start with the interactive cases

These self-contained Reader pages are the quickest way to see the graph model.
Select cards, inspect exact detail, expand complete paths, and move around the
topology without changing any source or research authority.

| 🗺️ Working-scale topology | 📚 Philosophy workflow | 🧮 Graph of a proof |
|---|---|---|
| [![Open the 175-node anonymized Reader](docs/assets/anonymized-research-topology.png)](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html) | [![Open the philosophy workflow Reader](docs/assets/philosophy-case.png)](https://cm4u7.github.io/chalxius/cases/philosophy.html) | [![Open the proof Reader](docs/assets/xy-swap-potential-case.png)](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html) |
| Real run topology: 175 nodes, 364 edges, 17 targets, and 7 themes; every content-bearing field is anonymized. | Source-bound argument reconstruction, independent audit, correction, and authority separation. | A guarded visualization of computation, blockers, and revocation.  |

The featured graph uses opaque
HMAC-SHA-256 identifiers produced with a discarded ephemeral key; it preserves
structure, not private claims, formulas, names, or source locators.

## 🧰 What you can do with Chalxius

- 📄 **Research a draft from its Paper Graph.** Freeze the exact draft,
  decompose it into a proposition-total DAG, inherit every target and ordered
  premise, and strengthen it copy-on-write instead of replacing it with a tiny
  convenience Fact bundle.
- 📚 **Keep finished external papers as Evidence.** PDF bytes, DOI identity,
  peer review, and citations do not create Fact authority. Exact claims still
  need an explicit bridge, fresh verification, and ordinary admission.
- 🧩 **Develop or refute a mathematical target.** Preserve the exact
  conjecture, hypotheses, domains, quantifiers, and target ids; a valid result
  may be `proved`, `disproved`, or
  `unresolved_with_obstruction`.
- 🧠 **Run several lines of reasoning without mixing them.** Keep exploratory
  attempts, counterexamples, objections, repairs, and computations on the
  Research/Blackboard planes until their dependencies are visible.
- 🧮 **Make computation replayable.** Bind formulas, code, versions, domains,
  representations, checkpoints, outputs, and approximation budgets to the
  exact claim they support.
- 🔎 **Investigate sources and novelty.** Check publication identity, theorem
  applicability, locators, witnesses, conventions, nearby literature, and the
  bounded corpus behind a novelty statement.
- ✅ **Promote only reusable results.** The sole truth path remains
  `Research → Candidate Release → Certification Decision → Fact`.
- ♻️ **Correct without losing history.** Challenge, replace, refute, or revoke
  a node while preserving its old bytes and showing downstream impact.
- 🧾 **Learn from architecture failures.** Append-only CHX ledgers record every
  discovery before classification, preserve typed relations and predecessor
  runs, and gate public disclosure against the complete ordered ledger lineage.
- 🧭 **Consult a global architecture route guide.** PHX distills reusable,
  high-impact routes from CHX findings and other measured architecture work.
  Problems and repairs remain in CHX; a PHX route is advisory and any active
  architecture change still requires an informed user consultation.
- ⚡ **Query large Paper continuations without rescanning them.** Routine status
  reads one atomic content-addressed HEAD and immutable receipts. Full closure
  validation is explicit; stale directory generations fail closed instead of
  silently falling back to an expensive scan.
- 🪶 **Reuse expensive validation only when identity is exact.** Release-time
  mutation plans are checked before their baseline starts, and protected
  runtime cutover consumes a hash-approved project receipt. Unchanged project
  state is not audited twice; semantic drift still fails closed or triggers the
  one necessary deep audit.
- 🛰️ **Use only a cautious slice of Brave Future.** Under `auto` or `deep`, an explicit
  research objective can establish or reuse its exact prospective Campaign
  scope and project BF-1 without requiring Campaign jargon. BF-2/BF-3 still
  require real blockage evidence. None of these levels can plan rounds,
  dispatch agents, create Research, or affect Candidate, Certification,
  Gateway, or Fact.
- 🎓 **Teach from a frozen graph.** Chalxius Learner can explain, question,
  test, and schedule review without changing research state.
- 🗺️ **Publish a readable map.** Export one deterministic offline Reader with
  bilingual controls, MathJax, draggable cards, theme fields, and complete path
  exploration.

## 🧬 Preserve the research target, not one universal “stance”

The continuity rule is domain-indexed:

| Draft type | What stays exact | Legitimate outcomes |
|---|---|---|
| Philosophy | Declared argumentative direction, headline, required and forbidden claims | `preserved` or `strengthened`, unless the Operator authorizes an exact revision |
| Mathematics | Conjecture/question, hypotheses, domains, quantifiers, target claim ids | `proved`, `disproved`, or `unresolved_with_obstruction` |
| Empirical | Question, estimand, population, exposure/intervention, outcome, scope | supported, disconfirmed, or inconclusive |
| Mixed | At least two explicit component adapters and their shared target ids | The composed outcomes of those exact adapters |

A counterexample to an unchanged mathematical conjecture is target-preserving.
A proof of a weakened or re-quantified theorem is not a resolution of the
original target merely because it points in the same direction.

## Architecture in one minute

```text
frozen sources ──► Paper Logic ──► independent Audit ──► Evidence
                         │                                │
                         └────────► Research ◄────────────┘
                                      │
                         Blackboard / computation / adverse work
                                      │
                                      ▼
                              Candidate Release
                                      │
                              fresh Verifier
                                      │
                                      ▼
                           Certification Decision
                                      │
                               Fact Gateway
                                      │
                                      ▼
                                  Fact Graph
```

Main explores and compiles task context. Operator governs explicit activation,
overrides, imports, and route decisions. Host is a narrow dispatch/status/audit
boundary. Workers contribute bounded Research. Paper Auditor, Verifier, and
Gateway remain separate so the same actor cannot silently explore, certify, and
admit its own result.

Historical projects and old Evidence remain readable. Reading them does not
transfer their authority into a new V5 project, and upgrading Chalxius never
forces running work to restart under a newer contract.

## Install and verify

Download these adjacent release assets:

- `chalxius-0.6.5-integrated-research-continuity.tar.gz`
- `chalxius-0.6.5-integrated-research-continuity.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.6.5-integrated-research-continuity.tar.gz.sha256
tar -xzf chalxius-0.6.5-integrated-research-continuity.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
```

The unpacked [`chalxius/`](chalxius/) directory is the installable skill. A
replacement of an installed copy is a separate cutover decision; do not replace
the runtime beneath an already-frozen task card.

<a id="prompt-interface"></a>

## User prompt interface

You normally do **not** need to know any CLI command. Invoke the system by naming
`$chalxius` (most explicit) or `Chalxius`, then describe the object, action,
boundary, and desired output in ordinary language.

```text
Use $chalxius + [mode] + [subject] + [action] + [boundaries/output]
```

For example:

```text
Use $chalxius in auto mode to study this paper. Continue from its reviewed
Paper Graph, bind each Research node to its source target, and leave unresolved
obligations in Research.
```

```text
Use $chalxius in deep mode to compare independent proof routes, replay the
load-bearing computation, and prepare only verifier-ready claims for release.
```

### Reasoning modes

| Say this | Effect |
|---|---|
| `Use $chalxius` | Starts in `auto`, the default |
| `fast mode` | Narrow, low-cost exploration; Evidence and Fact gates remain unchanged |
| `auto mode` | Activates only the expensive capabilities indicated by the task |
| `deep mode` | Broad source, route, computation, novelty, and specialist planning when applicable |
| `switch future work to ...` | Changes future work units only; frozen rounds are not restarted |

### What to say for each feature

| You want | Natural-language command examples |
|---|---|
| Ordinary proof research | `Use $chalxius to build the exact target closure, identify missing premises, and compare proof routes.` |
| Build and audit a Paper Graph | `Use $chalxius to build a Paper Graph, bind every node to exact text, definitions, quantifiers, and dependencies, then send it to an independent Paper Auditor.` |
| Strengthen a research draft | `Decompose this research draft into a complete DAG. Continue from its Paper Graph, admit or repair claims node by node, and do not compress it into a few convenience Facts.` |
| Resolve an exact mathematical target | `Keep the conjecture, hypotheses, domains, and quantifiers exact. Prove or disprove it; if neither succeeds, return a checkable obstruction and separately record any weaker progress.` |
| Continue from a reviewed paper | `Continue from this reviewed Paper Graph and keep each Research node bound to its Paper target.` |
| Archive paper Evidence | `Archive the reviewed Paper Graph together with the exact paper version and PDF in the cross-project Evidence library.` A reviewed immutable freeze syncs automatically when a library is configured. |
| Import a non-paper Fact Graph as Evidence | `Explicitly import /path/to/fact_graph as non-paper Evidence without inheriting its Fact authority.` |
| Bridge Evidence into the current project | `Create verified bridges for these Evidence nodes, enumerate stale and correction risks, then use a fresh verifier and the Fact Gateway.` |
| Correct a Paper/Evidence graph | `Append a correction for this Paper Graph node, mark the old object stale, and report affected bridges and local Facts without rewriting history.` |
| Program–mathematics attack | `Attack the formula-to-code projection for truncation order, representation, domain, error budget, and independent replay.` |
| Goal-driven advisory scope | `Use Chalxius in auto or deep mode to research this objective.` The explicit objective can establish the exact internal scope and project BF-1 without Campaign jargon. |
| Lightweight Campaign | `Create a lightweight Campaign for these related targets; retain the four-factor frontier and do not treat the Campaign as a proof.` |
| Cautious Brave Future reassessment | `Run one BF-2 dry reassessment for this explicit Campaign. If I later approve, write only a BF-3 advisory receipt; do not plan or dispatch work.` |
| Adverse review | `Run a hostile/refute review of this conclusion and return the productive Attack report and reusable rule proposals without activating them.` |
| Philosophy-only attacks | `This is a philosophical argument. Apply plain-language substitution, burden of proof, strongest charitable objection, independent failure surfaces, and quantifier/modal/scope/exception equivalence attacks.` |
| Approve or reject a route proposal | `Approve rule R from the Attack report with this narrower scope ...` / `Reject rule R.` / `Disable rule R.` |
| Prepare a certified Fact | `Package these Research claims as a Candidate Release and send them to a fresh verifier; only the exact accepted decision may reach the Fact Gateway.` |
| Export the interactive Reader | `Export the current graph as a single-file Reader HTML and complete every node's summary, intuition, importance, reasoning, and provenance.` |
| Generate project background | `Generate or refresh PROJECT_BACKGROUND.md for this project and build its searchable index.` |
| Teach or test you | `Use Chalxius Learner to teach or test me from this frozen graph, one question at a time, without changing the research graph.` |
| Diagnose Chalxius architecture | `Read this CHX ledger and repair mechanisms caused or materially amplified by Chalxius; do not convert them into attack-routing rules.` |
| Reduce cost or assess a major architecture route | `Consult the global PHX guide for routes relevant to this cost or architecture goal. Report the measured options and ask before changing the active architecture.` |

Paths, exact targets, source versions, required outputs, and “do not ...”
boundaries can be written in the same ordinary sentence; there is no separate
prompt DSL.

### Default versus explicit behavior

Once `$chalxius` is invoked for a new governed V5 task:

- `auto` is selected unless you say `fast` or `deep`;
- an explicit research objective under `auto` or `deep` may establish or exactly reuse
  its prospective internal Campaign scope and project advisory BF-1; this does
  not plan or dispatch work;
- a task-scoped CHX ledger is opened and closed; it is reported only if a
  qualifying architecture issue exists;
- a task-end Attack report is produced, including an explicit zero report when
  no productive attack survives;
- a reviewed immutable Paper Graph is copied to the configured Evidence library
  with its exact paper version and PDF; sync failure is visible and retryable.

The following actions always require explicit language from the user:

- importing a non-paper Fact Graph into Evidence;
- activating, changing, approving, rejecting, or disabling an adverse route;
- generating or refreshing project background;
- starting Chalxius Learner or a Reader export, and manually activating or
  changing Campaign state beyond exact `auto`/`deep` goal intake;
- sealing a Candidate Release or attempting Fact admission;
- migrating or replacing an active project/runtime.

If you ask only for a “node graph” without naming Chalxius or another graph
implementation, the host asks which implementation you mean. Academic “teach
me / test me / grill me” language invokes Chalxius Learner; programming
requirements or debugging language refers to the separate Grill Me Code tool.

## Internal role boundaries

Users normally describe the desired outcome rather than choosing an internal
role. Chalxius binds every low-level operation to one explicit role:

| Role | May do | Must not do |
|---|---|---|
| `operator` | Initialize governance, switch modes, import Evidence, decide attack routes, perform explicit overrides | Treat a governance decision as mathematical verification |
| `main` | Inspect sources and graphs, plan Research, compile context, query Evidence, prepare releases and Readers | Certify its own release or bypass the gateway |
| `host` | Trusted dispatch, task status, and bounded audit transport | Read background for exploration, plan mathematics, or gain proof authority |
| `worker` | Execute one immutable task card and return bounded Research/artifacts | Infer capabilities from filesystem access or write Facts |
| `paper-auditor` | Independently review Paper Logic and correction coverage | Turn interpretation into source authority |
| `verifier` | Review one frozen verifier capsule and issue an immutable decision | Explore the live project or admit a Fact |
| `gateway` | Recheck the exact accepted decision and expose the admitted Fact | Repair a proof, waive evidence, or reinterpret the decision |

## Machine CLI (advanced)

<details>
<summary>Open the low-level command-family reference</summary>

Set explicit paths; Chalxius never guesses a project root inside the skill:

```sh
MGRAPH=/absolute/path/to/chalxius/scripts/mgraph
PROJECT=/absolute/path/to/my-project

"$MGRAPH" --root "$PROJECT" --role operator init \
  --project-id my-project \
  --title "My research project" \
  --workflow-version 5 \
  --reasoning-mode auto

"$MGRAPH" --root "$PROJECT" --role main status
"$MGRAPH" --root "$PROJECT" --role main audit
```

Run `mgraph --help` for the complete parser and
`mgraph ... COMMAND --help` for exact fields. The stable command families are:

| Interface | Commands |
|---|---|
| Project and mode | `init`, `status`, `audit`, `mode-init`, `mode-status`, `mode-switch`, `upgrade-project-copy`, `upgrade-workflow` |
| Fact inspection | `show`, `search`, `closure`, `context`, `targets`, `set-targets`, `fact-graph-inventory`, `fact-graph-append-target`, `revoke` |
| V5 release and admission | `candidate-release`, `candidate-release-check`, `verifier-capsule`, `certification-record`, `certification-decision-check`, `fact-admit` |
| Atomic mini-DAG admission | `fact-bundle-submit`, `make-bundle-verifier-task`, `fact-bundle-record-review`, `fact-bundle-admit` |
| Research and frontier | `memory-add`, `memory-update`, `frontier`, `adoption-plan`, `plan-round`, `plan-repair-round`, `round-status`, `work-unit-abort` |
| Worker boundary | `preflight-return`, `validate-return`, `ingest-return`, `make-verifier-task` |
| Paper Logic and Audit | `paper-logic-init`, `paper-logic-stage`, `paper-logic-record-review`, `paper-logic-freeze`, `paper-logic-status`, `paper-logic-show`, `paper-logic-query`, `paper-logic-audit`, `paper-logic-link-exploration`, `paper-logic-project-blackboard` |
| Paper continuation | `paper-continuation-plan`, `paper-continuation-status` (bounded by default; explicit `--full`), `paper-continuation-status-index-rebuild`, `paper-continuation-dispose` |
| Cross-project Evidence | `evidence-library-status`, `evidence-query`, `evidence-sync-retry`, `evidence-import-fact-graph`, `evidence-bridge-prepare`, `evidence-bridge-check`, `evidence-mark`, `evidence-impact-report` |
| Blackboard | `blackboard-type-register`, `blackboard-space-create`, `blackboard-node-add`, `blackboard-edge-add`, `blackboard-show`, `blackboard-query`, `blackboard-snapshot`, `blackboard-snapshot-query`, `blackboard-reindex`, `blackboard-promote-node` |
| Campaign and goal intake | `research-goal-intake`, `campaign-create`, `campaign-activate`, `campaign-update`, `campaign-status`, `campaign-target-add`, `campaign-target-archive`; scoped `frontier --campaign` and `plan-round --campaign` |
| Collaboration Pulse | `pulse-plan`, `pulse-barrier`, `pulse-dispatch`, `pulse-close`, `pulse-status`, `pulse-audit`, `pulse-void`, `pulse-abort` |
| Replayable experiment | `experiment-start`, `experiment-event`, `experiment-observe`, `experiment-decision`, `experiment-resume`, `experiment-status`, `experiment-finalize` |
| Adverse governance | `attack-route-enable`, `attack-route-status`, `attack-report`, `attack-route-decide`, `attack-route-disable` |
| Claims and exposition | `claim-add`, `claim-variant`, `claim-show`, `convention-add`, `convention-show`, `export-claim-card`, `lint-expert-document`, `export-interpret-card`, `lint-interpret-document` |
| Novelty and migration | `novelty-record`, `novelty-status`, `import-danus` |
| Presentation | `export-mermaid`, `export-reader-html --packet ...`, `export-reader-html --v5-projection` |
| Background index | `project-background-index`, `project-background-read` |

Compatibility commands such as `submit`, `packet`, `record-review`, `admit`,
and `profile-closure-*` remain available for bounded historical workflows. They
do not replace the V5 release/certification/gateway path.

</details>

## Paper Graph and Evidence lifecycle

For paper-led work, Chalxius binds research to an exact reviewed Paper snapshot
instead of treating a prose summary as sufficient context:

1. Freeze the exact paper version and PDF.
2. Stage source nodes, reconstruction nodes, typed edges, and target closure.
3. Obtain an independent Paper Audit and freeze the reviewed graph.
4. When an Evidence library is configured, archive the exact paper version,
   PDF, graph, and review attestation automatically.
5. Continue Research from selected Paper targets; report Paper adequacy
   separately from Fact validity.
6. If later correction marks Evidence stale, compute bridge and local-Fact
   impact without silently rewriting or revoking authority.

Non-paper Fact Graphs are different: importing them into Evidence requires an
explicit user request and the `operator` role. Older supported V5 graphs can be
audited and imported without reopening their completed work. A destination
project may use selected Evidence only through a content-addressed
`verified_bridge`, which is rechecked during release, verification, and Fact
admission.

The release includes the native local `paperlib` runtime; Zotero is not
required. Chalxius can initialize an explicit cross-project library root and
store append-only metadata, exact PDF versions, Paper Graph trees, corrections,
and rebuildable JSON/SQLite indexes there. It never stores library data inside
the installed skill.

See [`evidence_plane.md`](chalxius/references/evidence_plane.md),
[`paper_input_contracts.md`](chalxius/references/paper_input_contracts.md), and
[`paper_continuation_contract.md`](chalxius/references/paper_continuation_contract.md)
for exact schemas and failure behavior.

## Attack reports and CHX reports

These are deliberately separate:

- The **Attack report** records successful counterexamples and other productive
  challenges, then proposes reusable future routing rules. New governed V5
  tasks produce a report even when it is explicitly zero. Proposals remain
  inactive until the user/Operator approves, edits, rejects, or disables them.
- The **CHX architecture report** contains only failures caused or materially
  amplified by Chalxius architecture. A run with no qualifying issue stays
  silent. CHX issues are repair inputs for Chalxius and are never learned as
  mathematical attack rules.

The general route includes hidden-conjunct splitting. Philosophy-only routes
add plain-language replacement, burden/strongest-charitable-objection/
independent-failure-surface attacks, and quantifier–modal–scope–exception
equivalence checks. Exact frozen domain metadata—not keywords—controls whether
the philosophy set is available.

## Reader interface

`export-reader-html` atomically replaces exactly:

```text
PROJECT/visualizations/knowledge-map.html
```

Reader revision 20 provides:

- hash6 plus role/plane canvas identities, with full exact material in the detail panel;
- MathJax rendering in summaries and formal detail;
- one center per theme, concentric topic orbits, and shared-node placement in overlap regions;
- simultaneous local attraction and repulsion, even when topic orbits are disabled;
- radial and angular memory springs that preserve the initial layered circular composition;
- pinned selected/path/topic anchors during local settlement;
- draggable and resizable cards, pan/zoom, undo/redo, filters, search, and complete-chain expansion;
- a deterministic offline single file with no fetch, watcher, storage writeback, or graph mutation.

Reader Finalize fails closed if any included node lacks summary, intuition,
importance, reasoning, formal detail, or provenance. A successful export proves
presentation readiness only.

## Rebuild the public demos

The two guided packets and all three HTML pages are deterministic:

```sh
python3 examples/build_case_demos.py
python3 examples/validate_public_examples.py
```

To create a content-free public topology from your own private Reader packet and
project run:

```sh
python3 examples/anonymize_reader_topology.py \
  --reader-packet /private/path/reader-packet.json \
  --project-root /private/path/project \
  --output examples/reader-packets/my-anonymized-topology.json
```

Without `--key-file`, the script generates and discards an ephemeral 256-bit
key. It fails if the output is inside the source project, if a source identifier
or source text survives, or if any node content field is not a 64-character
hash. Supplying a private key file enables repeatable mapping, but that key must
never be published.

## v0.6.5: Integrated Research Continuity

This release keeps the ordinary-language `auto`/`deep` goal intake and cautious
BF-1–BF-3 boundary from 0.6.4 while making research continuity explicit across
Paper, Research, Evidence, release, and runtime transitions. Philosophy alone
may preserve an argumentative stance. Mathematics preserves its exact target
and can separately retain a typed weaker theorem, special case, counterexample,
or obstruction without misreporting it as resolution.

Large projects now use resumable, content-addressed Paper-continuation state and
one release capsule reused by Candidate, neutral verifier, Certification, and
Gateway. Evidence association planning is durable even when exact PDF/Paper/
Fact checks fail before an ordinary request exists, so status and retry can find
the failure without guessing from a title or DOI.

Release engineering has the same continuity rule. Public commands, standalone
entrypoints, and persistent-state writers must have exact executable coverage or
an explicit bounded/replace/retire disposition. Protected cutover consumes one
strict, single-read, snapshot-revisioned receipt; byte-identical runtime content
can inherit the audit after moving from a candidate directory to the installed
alias, while any content, manifest, project, provenance, or mode drift fails
closed. Administrative 2–4 minute goals are telemetry, never correctness
cutoffs.

PHX is now a host-global, project-independent route reference. It records
reusable architecture proposals and measured tradeoffs, including performance
routes synthesized from CHX, but records no implementation authority. Search,
evaluation, and reporting are read-only; adopting a route into the active
architecture requires a separate, informed user consultation.

The field mechanisms CHX-001 through CHX-109 are explicitly disclosed and
resolved in this prospective package. Their public identities are bound to the
ordered ledger lineage documented in
[`KNOWN_LIMITATIONS.md`](chalxius/KNOWN_LIMITATIONS.md); private ledgers are not
shipped. The upgrade performs no Fact migration, backfill, reclassification,
forced redo, or authority inheritance. See [`RELEASE.md`](RELEASE.md) and
[`v5_release_traceability.md`](chalxius/references/v5_release_traceability.md).

## Scope and acknowledgements

- Software validation establishes package and workflow properties, not a mathematical theorem.
- A copied paper, successful computation, audit receipt, Reader page, or Evidence object is not an admitted Fact.
- Private QA material, original content from the anonymized showcase, credentials, and user-specific learning profiles are excluded from the public package.

Chalxius acknowledges the authors of **Danus: Orchestrating Mathematical
Reasoning Agents with Fact-Graph Memory** (Liu et al., arXiv:2607.06447v2),
whose public design informed the fact-graph layout, and **Matt Pocock** for the
public `/grill-me` requirements-interview design that informed Reader
requirements work. Neither is a runtime dependency. See
[`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md).

Licensed under Apache-2.0. Third-party notices and vendored component licenses
are included in the skill directory.
