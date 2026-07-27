## Chalxius 与 Grill Me 按需路由

- 当用户提到 `MathGraph`、`math graph`、“数学图谱”、`Chalk`、Chalk 版 MathGraph、`mathgraph-chalk-version`、`Danus skill`、`Danus 技能` 或“Danus 的 skill”时，一律将其理解为 `$chalxius`。旧 `run-multi-agent-mathgraph`、`mathgraph-chalk-version` 和协调器仅是已退役的回滚谱系，不得作为活跃路由。
- `$chalxius` 默认使用 `auto`。只有用户明确选择“快速/fast”或“深度思考/deep”时才使用相应模式；模式切换只影响未来工作单元，Fact Graph 准入要求在所有模式中保持一致。
- 将 Chalxius 内部的非真值学术学习平面称为 **Chalxius Learner（内部 Grill 学习器）**。只有用户明确要求教他、向他提问、拷问或测试他、测验、论文学习、资格考试训练、掌握度记录或间隔复习时才启动。普通研究、论文审计、系统能力测试或 Fact 准入不得自动启动它。
- 将独立 `$grill-me` 称为 **Grill Me Code（外部编程辅助）**。只有用户明确要求编程拷问、苏格拉底式需求澄清、设计挑战、结对调试或类似程序辅助时才启动。普通编码、实现、调试或代码审查任务不得自动启动它。
- Chalxius Learner 可在确有教学需要时只读挂载冻结的 Fact、Paper/Audit 与 Blackboard 快照，并且只写 nontruth 学习记录；没有持久学习证据请求时只维持会话内状态。Grill Me Code 不得挂载或写入 Fact、Paper、Audit、Blackboard 或 Learning Graph，也不得承担研究认证。
- 混合研究—编程任务中，研究解释、图构建、审计和 Fact 准入归 `$chalxius`；程序需求、接口、实现、调试和测试可在用户要求相应辅助时交给 `$grill-me`。二者均不得把另一方的笔记自动视为已准入事实。
- 若用户只说 “grill me” 而语境不明确：教我、考我、论文学习等学术学习语境路由到 Chalxius Learner；代码、API、软件架构、调试等编程语境路由到 Grill Me Code；仍无法判断时，先问一个简短澄清问题，不同时启动二者。
