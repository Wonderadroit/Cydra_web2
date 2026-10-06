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
