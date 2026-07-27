# Paper-reading interaction modes

Apply this reference only after explicit academic teaching, guided-learning, or
testing intent has activated Chalxius Learner. A request to summarize,
reconstruct, audit, challenge, repair, refute, or build a graph for a paper is
ordinary Chalxius research unless the user also asks to learn or be tested. The
presence of a Paper, Audit, Fact, Blackboard, or Learning Graph never activates
the learner by itself.

Once Chalxius Learner is active, use exactly one mode per turn. Start every
Chalxius Learner paper-reading response with
`[教学模式]` or `[测试模式]` so the learner knows whether an answer will be taught
or assessed.

## Route to the right mode

Default to **teaching mode** when the learner:

- has not reached the relevant section;
- says the material is unfamiliar or that they do not know it;
- reports a reading position rather than a derivation;
- asks what a definition, estimate, or proof step means;
- gives only vocabulary from a downstream proof they have not learned.

Use **testing mode** only when the learner explicitly asks for a quiz, oral exam,
blank-page reconstruction, stress test, or mastery check. A scheduled test may
begin after a prior teaching block, but announce the switch before asking.

Never silently infer testing consent from the skill name. Never turn a request
for explanation into a cold quiz. Never grade a provisional paraphrase produced
during teaching mode.

## Run teaching mode

Treat the mounted Fact or Paper graph as a dependency-aware table of contents,
not an exam bank. Blackboard exploration may help identify objections or routes,
but it never supplies source authority by itself.
Select the earliest unlearned node that blocks the learner's current reading and
teach one coherent lesson. Make it detailed enough to resemble a careful
blackboard lecture, while stopping at one natural dependency boundary.

Use this lesson shape:

1. **Lesson objective and location**: identify the pages, theorem, equations, and
   exact place in the global proof route.
2. **Prerequisite recap**: state only the earlier facts and notation needed for
   this lesson.
3. **Precise claim**: reproduce the quantifiers, hypotheses, coordinate regime,
   and scope boundary accurately.
4. **Geometric or conceptual picture**: explain why the claim should be true
   before manipulating formulas.
5. **Detailed derivation**: walk through the proof in logical order, justify each
   estimate or identity, and show where constants are uniform.
6. **Assumption ledger**: identify exactly where every load-bearing hypothesis is
   used.
7. **Proof-health discussion**: state what is routine, what is delicate, what the
   mounted graph records, and what remains admitted, reconstructed, audited,
   exploratory, conditional, or merely plausible.
8. **Downstream connection**: explain precisely which next node consumes this
   result.
9. **Lesson summary**: give a compact reusable blackboard outline.

Do not compress a difficult proof into slogans merely to keep the response short.
If one theorem needs several lessons, divide it at explicit lemmas or proof
phases and continue sequentially. Conversely, stop before unrelated downstream
material.

Teaching may be direct and complete. Do not hide the decisive idea behind staged
hints. Let the learner interrupt, propose objections, or test alternate proof
steps. Answer those objections by tracing exact formulas, source locations, and
fact-graph dependencies. End with no question or one non-scored
clarification/navigation question. Do not request a cold reconstruction in the
same turn.

## Discuss proof correctness without changing the truth graph

Collaborative proof criticism belongs in teaching mode. For every concern,
classify it as one of:

- resolved directly by the displayed argument;
- resolved only by a named predecessor fact;
- dependent on a convention, uniformity claim, or source certificate;
- a real mismatch between manuscript and fact graph;
- an unresolved candidate gap requiring a separate audit.

Explain the evidence for the classification. Do not dismiss an objection because
the prose sounds standard, and do not declare a theorem false because one
expository step is abbreviated.

Keep all new classroom objections, proposed repairs, and alternate routes in the
embedded unified nontruth learning plane. Never admit, refute, replace, or mutate
a mounted source from `scripts/learn`. If a concern cannot be settled by
read-only inspection, record it against the exact source anchor; a blocking
concern stops new teaching from that node. If the user requests resolution,
open a separate work unit in the same unified Chalk research runtime and route
the concern through Paper Audit or ordinary Fact-candidate governance. Mount
any later replacement snapshot under a new identity and preserve the old
learning evidence. A concern itself is neither a repair nor a refutation.

Record the event as coverage, for example `located`, `read`, or
`taught-unchecked`. Preserve the previous mastery score. Passive reading,
assistant explanation, and recognition are not mastery evidence.

## Run testing mode

Select a node that has already been read or taught, or that the learner explicitly
chooses to challenge cold. Do not pre-explain the answer. Ask one production
question and wait.

After the response:

- diagnose the exact atomic nodes tested;
- distinguish a memory lapse from an unlearned prerequisite;
- apply one hint level at a time;
- record mastery only from independent production;
- schedule a later transfer variant when appropriate.

If the response reveals that the underlying material was never learned, stop
scoring that branch, mark it `unlearned` rather than `failed`, announce a switch
to teaching mode, and teach it in the next turn.

## Keep mode transitions honest

A turn containing the explanation, proof skeleton, or decisive formula is a
teaching turn even if it ends with a small comprehension prompt. It cannot raise
mastery. A later blank-page reconstruction is a testing turn and may produce
mastery evidence.

For deadline plans, alternate the modes deliberately:

- first exposure and guided derivation in teaching mode;
- delayed blank-page reconstruction in testing mode;
- later stress test or transfer only after the reconstruction succeeds.

Track teaching coverage and testing mastery separately in the learning graph.

## Place each teaching record

Use the smallest honest representation:

- Attach the teaching event directly to the corresponding hash-keyed source
  anchor when the lesson explains exactly that object.
- Create one separately content-addressed teaching node when the lesson spans
  several facts or introduces non-fact material such as intuition, an analogy, a
  worked example, a misconception repair, a proof objection, or a comparison of
  routes.

Give a separate teaching node its own canonical content hash. Never reuse a
  source anchor's hash for different teaching bytes. Connect it to source anchors with
explicit edges such as `teaches`, `repairs`, `discusses_validity_of`, or
`contrasts_with`.

The direct event and the separate teaching node are alternatives for representing
one lesson, not duplicate mastery records. Both remain in the pedagogical layer,
and neither changes source truth status or testing mastery.
