# 🧭 Chalxius

Chalxius is a source-bound research system for papers, proofs, computations,
philosophical arguments, reusable evidence, and graph-aware teaching. It keeps
exploration productive while making the transition to reusable Facts explicit,
reviewable, and verifier-gated.

**[🚀 Open the live Reader](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)** ·
[📦 Download v0.5.0](https://github.com/cm4u7/chalxius/releases/tag/v0.5.0) ·
[🏗️ Architecture](ARCHITECTURE.md) ·
[✅ Validation](VALIDATION.md) ·
[⚠️ Known limitations](chalxius/KNOWN_LIMITATIONS.md) ·
[📚 Use cases](USE_CASES.md)

> **Release boundary:** v0.5.0 is published with 17 known, unresolved CHX
> architecture issues from a private field run. Tests validate the software and
> package; they do not close those issues or certify any research result. See
> [Known architecture limitations](chalxius/KNOWN_LIMITATIONS.md).

## A research graph at working scale

[![Open the 175-node anonymized Chalxius Reader](docs/assets/anonymized-research-topology.png)](https://cm4u7.github.io/chalxius/cases/anonymized-research-topology.html)

The featured case preserves the real topology of a completed research run: **175
nodes, 364 edges, 17 targets, and 7 themes**. Its claims, formulas, names, paths,
source identifiers, and node text were removed. Every public node identifier and
content-bearing field is an opaque HMAC-SHA-256 value produced with a discarded
ephemeral key. The page demonstrates graph scale and interaction only; it has
`truth_effect="none"`.

Two smaller guided cases are also available:

- [Philosophy argument workflow](https://cm4u7.github.io/chalxius/cases/philosophy.html): source, interpretation, audit, correction, and authority separation.
- [Potential x-y interchange workflow](https://cm4u7.github.io/chalxius/cases/xy-swap-potential.html): computation, blockers, correction history, and guarded presentation. This is a potential application, not an author-confirmed result.

## What Chalxius does

| Capability | Outcome | Authority boundary |
|---|---|---|
| Paper Logic + Audit | Freeze exact paper versions, distinguish research drafts from external references, reconstruct nodewise arguments, review them independently, and keep corrections append-only | Source role is orthogonal to authority; Paper and Audit are never automatic Fact premises |
| Cross-project Evidence | Archive reviewed Paper Graphs with their PDF/version; explicitly import older or external Fact Graphs; query and mark stale evidence | Evidence is higher-trust nontruth; a verified bridge must still pass release, fresh verification, and gateway admission |
| Research + Blackboard | Accumulate attempts, insights, counterexamples, obstacles, typed questions, and alternative routes | Exploration remains nontruth and cannot silently overwrite a Fact |
| Campaigns | Scope a bounded family of related Research targets while Main keeps the four-factor frontier ordering | Campaigns plan work; they do not certify completion |
| Program–mathematics verification | Bind formulas, code, domains, representations, approximation budgets, checkpoints, outputs, and replay evidence | A successful computation supports only its exact bound claim |
| Adverse review | Run general attacks plus domain-gated philosophical attacks; produce a task-end Attack report and route-evolution proposals | Productive attacks remain Research; only the user/Operator may activate future routing rules |
| CHX architecture reporting | Keep one causal, hash-chained CHX ledger per new run and report architecture-caused or architecture-amplified failures | Silent when no qualifying issue exists; never mixed into attack routing or mathematical truth |
| V5 certification | Seal exact Research as a Candidate Release, obtain a fresh immutable Certification Decision, and admit through the Fact Gateway | The only truth path is `Research → Candidate Release → Certification Decision → Fact` |
| Reader | Export one offline HTML file with MathJax, hash6 canvas identities, topic orbits, stable radial-memory forces, drag/zoom, path expansion, and bilingual controls | Presentation only; no topology, source, or authority writeback |
| Chalxius Learner | Teach, question, test, and schedule review from frozen graph snapshots when explicitly requested | Learning records are nontruth and cannot mutate research authority |

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

- `chalxius-0.5.0-back-to-the-future-paper-continuation.tar.gz`
- `chalxius-0.5.0-back-to-the-future-paper-continuation.tar.gz.sha256`

Then run:

```sh
shasum -a 256 -c chalxius-0.5.0-back-to-the-future-paper-continuation.tar.gz.sha256
tar -xzf chalxius-0.5.0-back-to-the-future-paper-continuation.tar.gz
cd chalxius
shasum -a 256 -c MANIFEST.sha256
```

The unpacked [`chalxius/`](chalxius/) directory is the installable skill. A
replacement of an installed copy is a separate cutover decision; do not replace
the runtime beneath an already-frozen task card.

<a id="prompt-interface"></a>

## User prompt interface · 用户命令接口

You normally do **not** need to know any CLI command. Invoke the system by naming
`$chalxius` (most explicit) or `Chalxius`, then describe the object, action,
boundary, and desired output in ordinary Chinese or English.

```text
用 $chalxius + [模式] + [研究对象] + [要做的事] + [边界/交付物]
Use $chalxius + [mode] + [subject] + [action] + [boundaries/output]
```

For example:

```text
用 $chalxius 自动模式研究这篇论文，从已审查的 Paper Graph 继续，
逐节点绑定原文；把没有解决的证明义务留在 Research，最后给我 Attack report。
```

```text
Use $chalxius in deep mode to compare independent proof routes, replay the
load-bearing computation, and prepare only verifier-ready claims for release.
```

### Reasoning modes · 思考模式

| Say this | Effect |
|---|---|
| `用 Chalxius` / `Use $chalxius` | Starts in `auto`, the default |
| `快速模式` / `fast mode` | Narrow, low-cost exploration; evidence and Fact gates remain unchanged |
| `自动模式` / `auto mode` | Activates only the expensive capabilities indicated by the task |
| `深度思考` / `deep mode` | Broad source, route, computation, novelty, and specialist planning when applicable |
| `从现在切换到…` / `switch future work to…` | Changes future work units only; frozen rounds are not restarted |

### What to say for each feature · 各功能如何召唤

| You want | Natural-language command examples |
|---|---|
| Ordinary proof research | `用 Chalxius 研究这个命题，先列出目标闭包和缺失前提，再比较证明路线。`<br>`Use $chalxius to build the target closure and compare proof routes.` |
| Build and audit a Paper Graph | `用 Chalxius 对这篇论文建立 Paper Graph，逐节点绑定原文、定义、量词和依赖，再交给独立 paper auditor。` |
| Continue from a reviewed paper | `从这个已审查 Paper Graph 继续研究，不要退回只读论文；保持每个 Research 节点与 Paper target 的绑定。` |
| Archive paper Evidence | `把审查完成的 Paper Graph 连同论文版本和 PDF 保存到跨项目 Evidence 仓库。`<br>When a library is configured, a reviewed immutable freeze syncs automatically. |
| Import a non-paper Fact Graph as Evidence | `把 /path/to/fact_graph 作为非论文 Fact Graph 显式导入 Evidence；不要继承它的 Fact 权威。` |
| Bridge Evidence into the current project | `选择这些 Evidence 节点建立 verified bridge，列出所有 stale/correction 风险，再走新的 verifier 和 Fact Gateway。` |
| Correct a Paper/Evidence graph | `这个 Paper Graph 节点有误：追加修正、标记旧图 stale，并报告所有 bridge 和本地 Fact 的影响；不要静默重写。` |
| Program–mathematics attack | `对这段公式到代码的投影做数学-程序一致性攻击，检查截断阶数、表示、定义域、误差预算和独立重放。` |
| Lightweight Campaign | `为这组相关目标建立一个轻量 Campaign；Main 仍按四因子 frontier 排序，不把 Campaign 当完成证明。` |
| Adverse review | `对这个结论做 hostile/refute 审查；任务结束时给我成功或有价值的 Attack report 和规则进化建议，但不要自动采用。` |
| Philosophy-only attacks | `这是哲学论证。启用普通语言替换、举证责任、最强善意反驳、独立失败面，以及量词/模态/范围/例外等价性攻击。` |
| Approve or reject a route proposal | `采用 Attack report 中规则 R…，但把适用范围改成……` / `拒绝这个规则` / `停用规则 R…` |
| Prepare a certified Fact | `把这些 Research 封装为 Candidate Release，交给新的 verifier；只有完全一致的接受决定才能进入 Fact Gateway。` |
| Export the interactive Reader | `把当前图导出为单文件 Reader HTML；每个节点补齐摘要、直觉、重要性、推理路线和来源。` |
| Generate project background | `为这个项目生成（或刷新）PROJECT_BACKGROUND.md，并把它压成可检索索引。` |
| Teach or test you | `用 Chalxius Learner 根据这个冻结图教我/考我，一次一个问题，不要修改研究图。` |
| Diagnose Chalxius architecture | `读取这个 chx-ledger，修复其中由 Chalxius 架构造成或显著放大的问题，不要把它们加入攻击路由。` |

Chinese and English may be mixed freely. Paths, exact targets, source versions,
required outputs, and “do not …” boundaries can be written in the same ordinary
sentence; there is no separate prompt DSL.

### Default versus explicit behavior

Once `$chalxius` is invoked for a new governed V5 task:

- `auto` is selected unless you say `fast` or `deep`;
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
- starting Chalxius Learner, a Campaign, or a Reader export;
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
| Paper continuation | `paper-continuation-plan`, `paper-continuation-status`, `paper-continuation-dispose` |
| Cross-project Evidence | `evidence-library-status`, `evidence-query`, `evidence-sync-retry`, `evidence-import-fact-graph`, `evidence-bridge-prepare`, `evidence-bridge-check`, `evidence-mark`, `evidence-impact-report` |
| Blackboard | `blackboard-type-register`, `blackboard-space-create`, `blackboard-node-add`, `blackboard-edge-add`, `blackboard-show`, `blackboard-query`, `blackboard-snapshot`, `blackboard-snapshot-query`, `blackboard-reindex`, `blackboard-promote-node` |
| Campaign | `campaign-create`, `campaign-activate`, `campaign-update`, `campaign-status`, `campaign-target-add`, `campaign-target-archive`; scoped `frontier --campaign` and `plan-round --campaign` |
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

## v0.5.0: Back to the Future / Paper Continuation

This release preserves the V5 truth path and the bounded L1/L2 context recovery
from v0.4.4, then adds the cross-project Evidence plane, reviewed Paper Graph
auto-archival, explicit external Fact Graph import, verified bridges, append-only
correction impact, exact Paper continuation, public worker assurance contracts,
lightweight Campaign scoping, default task-end Attack reports, philosophy-gated
attack routes, and Reader revision 20.

The upgrade is prospective. It performs no project migration, backfill,
reclassification, forced redo, or authority inheritance. See
[`RELEASE.md`](RELEASE.md) and
[`v5_release_traceability.md`](chalxius/references/v5_release_traceability.md).
It is intentionally published before the 17 field-discovered architecture
issues in [`KNOWN_LIMITATIONS.md`](chalxius/KNOWN_LIMITATIONS.md) are closed.

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
