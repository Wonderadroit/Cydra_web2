# Web2 architecture

## Security-research objective

The system is optimized for discovering reproducible security boundary violations, not for maximizing scan coverage or passing internal benchmarks.

## Research graph

Target -> observations -> behavior model -> identities/resources/endpoints -> security boundary -> hypothesis -> differential experiment -> execution -> evidence -> replay -> impact -> report.

## Experiment families

1. **Identity differentials** — owner vs non-owner, role A vs role B, authenticated vs anonymous.
2. **Object differentials** — substitute identifiers while holding the request constant.
3. **Request differentials** — method, parameter, header, and body changes.
4. **Workflow differentials** — perform the same state transition under different identities or states.
5. **State-transition reasoning** — compare preconditions and postconditions rather than treating endpoints as isolated calls.

## Evidence rules

A successful HTTP status alone is never a finding. Strong authorization evidence requires either:
- identical successful owner/comparison response fingerprints, or
- a successful comparison response containing the modeled protected-resource identifier.

Server errors and transport failures are anomalies/capability failures, never security evidence.

A candidate must survive independent replay before it can pass the causal gate. Impact is assessed separately from exploitability.

## Reuse from Cydra_wonder

We retain useful principles: provenance, explicit models, fail-closed execution, differential testing, causal verification, and evidence-first reasoning.

We do **not** depend on the Solidity controller, compiler/Foundry stack, synthetic maturity loop, or Web2 capability-repair loop.

## Success criterion

A green regression validates the engine. The actual end state is a reproducible contradiction on an authorized target that survives replay and can be turned into a report with concrete impact.


## Deep-research milestones

The next layer makes the engine reason about the target before spending requests:

6. **Hypothesis frontier** — turn modeled boundaries into explicit, deduplicated claims with provenance.
7. **Authorization matrix** — enumerate owner/subject/resource/endpoint cells instead of testing one guessed path.
8. **Semantic response normalization** — compare meaning while discounting known volatile fields; raw responses remain available for proof.
9. **State/workflow graph** — represent prerequisites, produced state, multi-step reachability, and cross-identity transitions.
10. **Invariant layer** — express confidentiality, ownership, authorization, integrity, and workflow expectations independently of endpoints.
11. **Experiment queue** — prioritize explicit boundary hypotheses rather than blindly crawling or fuzzing.
12. **Evidence provenance ledger** — retain deterministic input/output fingerprints and parent lineage for every research phase.
13. **OpenAPI/frontend route ingestion** — use developer-declared and client-observed routes as model inputs, never as proof of vulnerability.
14. **Cache-boundary differential** — detect identity-insensitive cache behavior as a hypothesis requiring causal validation.
15. **Scope/request budget guard** — fail closed on hosts, schemes, and request budgets.
16. **Campaign integration** — produce a finite, inspectable research plan from the target model.

These are generic research capabilities, not target-specific detectors. A candidate still requires differential evidence, replay, and concrete impact before reporting.

## Operating principle

The engine should spend its effort where the model predicts a meaningful security-boundary contradiction. Discovery increases understanding; hypotheses select experiments; execution creates observations; evidence decides; replay establishes causality; impact determines reportability.
