# Invariant Fact Graph admission contract

The canonical contract is defined once in `scripts/mathgraph/modes.py`, hashed
with canonical JSON, written into unified project governance, and bound into
every new V4 round, assignment contract, task card, and execution profile. Its
hash is independent of reasoning mode.

Admission requires all of the following:

1. exact content addressing of statement, proof, direct predecessors, source
   evidence, task card, and submission or bundle;
2. active admitted statement-only predecessors, never proof-only dependencies
   or candidate-on-candidate chains;
3. source and applicability fidelity, including hypotheses, witness mapping,
   formula glyphs, status, conventions, quantifiers, and transports;
4. authorized immutable artifacts and independent replay for load-bearing
   computation;
5. one atomic internal mini-DAG and all-or-none visibility for dependent facts;
6. a different fresh verifier with only the frozen packet or bundle capability;
7. exact binding among review, candidate bytes, verification package, gateway
   acceptance, and stored fact;
8. cascade revocation plus clean current graph and workflow audit.

Execution profiles may add exploration. They cannot remove, relabel, or satisfy
an admission gate. `fast` therefore means low-cost exploration, not low-assurance
truth. Unsatisfied gates yield a candidate or explicit blocker.

Imported Danus facts preserve their prior admitted status and exact provenance
as historical inputs. Modifying one creates a new candidate. Every new fact,
including one derived from an imported fact, uses this contract.

Learning nodes, Paper/Audit nodes, Blackboard nodes, pulse readiness,
interpretation lint, expert prose, reader packets, and generated reader HTML
are never direct Fact premises.
