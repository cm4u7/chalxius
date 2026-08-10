## Chalxius and Grill Me intent routing

- Route a graph request to the implementation the user names. `Chalxius` or
  `$chalxius` selects Chalxius. `Danus`, `Danus skill`,
  `run-multi-agent-mathgraph`, `Chalk`, Chalk MathGraph, or
  `mathgraph-chalk-version` selects the corresponding predecessor lineage. If
  the user asks only for a math/research graph without naming an
  implementation, ask one short clarification question; do not silently
  rewrite the request as Chalxius or as a predecessor.
- `$chalxius` defaults to `auto`. Use `fast` or `deep` only when the user
  explicitly chooses it. A mode change affects future work units only, and
  every mode keeps the same Fact Graph admission requirements.
- Call the internal nontruth academic learning plane **Chalxius Learner（内部 Grill 学习器）**.
  Start it only when the user explicitly asks to be
  taught, questioned, grilled or tested, to learn a paper, train for a
  qualifying examination, record mastery, or schedule review. Ordinary
  research, paper audit, system capability testing, and Fact admission do not
  start it. 普通研究、论文审计、系统能力测试或 Fact 准入不得自动启动它。
- Call the separate `$grill-me` capability **Grill Me Code（外部编程辅助）**.
  Start it only for explicit programming grilling,
  Socratic requirements clarification, design challenge, pair debugging, or a
  similar programming-assistance request. Ordinary implementation, debugging,
  and code review do not start it automatically. 普通编码、实现、调试或代码审查任务不得自动启动它。
- When teaching is genuinely requested, Chalxius Learner may read a frozen
  Fact, Paper/Audit, or Blackboard snapshot and may write only nontruth learning
  records. Without a persistent-learning request, keep learning state in the
  current session. Grill Me Code must not mount or write Fact, Paper, Audit,
  Blackboard, or Learning Graph state and cannot certify research.
- In an already active Learner session, route one bounded read-only oral
  follow-up through the Learner fast path: read only the directly relevant
  learning rule and mathematical source slice, and skip project audit, mode,
  attack-report, PHX-search, new-CHX-ledger, and full-reference administration.
  A local `N` prefix has this meaning only when the current teaching context
  already defines it. Any mutation, persistent record, fresh verification,
  Research, Fact, or architecture action restores the applicable full workflow.
- In a mixed research-programming task, the user-selected research graph system
  owns research explanation, graph construction, audit, and Fact admission.
  Grill Me Code may assist requirements, interfaces, implementation, debugging,
  and tests only when the user requests that assistance. Neither system may
  treat the other system's notes as admitted Facts.
- If the user says only “grill me”, route academic teaching/testing context to
  Chalxius Learner and programming/API/software/debugging context to Grill Me
  Code. If the context still does not decide the route, ask one short question
  and do not start both; 不同时启动二者。
