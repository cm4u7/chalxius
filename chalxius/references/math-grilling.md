# Chalxius Learner: mathematics teaching and testing

Apply this reference only after explicit academic-learning intent has activated
Chalxius Learner—for example, the user asks to be taught, questioned, grilled,
tested, prepared for an exam, or tracked for mastery. A mathematical paper,
research project, proof, or graph does not activate it by itself. Ordinary
mathematical research, proof construction, proof audit, and Fact admission stay
on the Chalxius research surface with Learner off.

Once activated, use this mode for papers, books, lecture notes, proofs, theories,
and mathematical research projects that the user wants to learn or be tested on.

For paper reading, read and apply
[paper-reading-modes.md](paper-reading-modes.md). Its teaching/testing boundary
takes precedence over the testing-oriented question and hint rules below.

## Build the concept tree

Ground questions in the actual source. Cite a theorem, page, section, equation, or
repository location when available; never invent a locator. Organize the tree in
this dependency order:

1. **Purpose and scope**: identify the problem, claimed result, excluded cases,
   and the user's intended level of mastery.
2. **Objects and notation**: reconstruct definitions, types, domains, conventions,
   and quantifiers from memory.
3. **Assumptions**: state each hypothesis and identify where it is used.
4. **Mechanism**: explain the structural idea, not merely the sequence of symbols.
5. **Proof route**: derive the main dependencies, key formulas, cancellations,
   estimates, and boundary cases.
6. **Stress tests**: construct examples, counterexamples, limiting cases, and
   consequences of weakening an assumption.
7. **Transfer and research judgment**: apply the result to a new setting,
   distinguish proved claims from heuristics or experiments, and locate open
   questions.

Resolve prerequisites before testing downstream claims.

When an active learning session already has a fact graph, use its admitted target closure
as the mathematical dependency spine and keep rejected candidates as stress-test
or counterexample nodes. Apply
[fact-graph-grilling.md](fact-graph-grilling.md) to choose the next blocking
prerequisite and to keep truth status separate from learner mastery.

## Teach unfamiliar nodes

In teaching mode, explain one dependency block before asking for retrieval. Give
the exact statement and assumptions, unpack its notation, show the mechanism or a
detailed derivation, walk through the proof in its actual logical order, connect
it to its prerequisites and downstream role, and name common confusions and
scope boundaries. Match the explanation to the user's actual reading position.
Discuss whether each proof step is justified and compare concerns against the
existing fact graph without treating classroom discussion as fact admission.
Record exposure as `taught-unchecked`, never as mastery.

## Choose forcing questions in testing mode

Prefer questions that require production rather than recognition:

- State a definition with its domain, codomain, quantifiers, and conventions.
- Reconstruct a key formula and justify every term.
- Predict the next proof step before rereading it.
- Identify the exact step that uses a hypothesis.
- Explain why a cancellation or estimate holds.
- Give the smallest example and a counterexample when a hypothesis is removed.
- Compare two nearby concepts that are easy to conflate.
- Explain the theorem as a short, speakable proof map.
- Transfer the mechanism to a perturbed or unfamiliar case.

Do not accept jargon as evidence of understanding. Ask for the map between words,
formulas, and logical dependencies.

## Diagnose answers in testing mode

Classify the answer internally as correct, partial, misconception, unsupported, or
unknown. Respond with a precise correction and remain on the branch when needed.
Distinguish:

- a missing detail from a broken logical step,
- a notation slip from a conceptual error,
- a theorem from an intuition or conjecture,
- local validity from global scope,
- remembering a statement from being able to derive or use it.

## Apply the hint ladder in testing mode

Give only one new level per turn unless the user asks for the solution:

1. **Orientation**: name the relevant definition, invariant, or viewpoint.
2. **Constraint**: reveal the key identity, dependency, or diagnostic
   counterexample.
3. **Scaffold**: outline the proof skeleton with one crucial gap left to fill.
4. **Derivation**: show the complete reasoning, then ask the user to reproduce the
   decisive step without looking.

## Require evidence of mastery

Do not declare mastery until the user can:

- state the result and assumptions accurately;
- reconstruct the central mechanism or proof route;
- explain why the important assumptions are needed;
- handle at least one example, edge case, or counterexample;
- state the scope boundary and what remains unproved;
- transfer the idea or connect it to the active research project.

For advisor-facing preparation, end with a linear, speakable route containing the
core formulas, likely objections, and honest scope limits.
