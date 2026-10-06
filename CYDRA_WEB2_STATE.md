# CYDRA Web2 Mission State

## Mission
Produce one real, authorized Web2 hypothesis-evidence chain on one target surface and, if the target exposes a genuine security-boundary violation, carry it through replay, impact, human validation, and runnable PoC.

## Binary success condition
DONE only when a real authorized target produces a reproducible security-boundary violation with:
1. two-context execution of the same surface,
2. structured observations for both contexts,
3. a falsifiable hypothesis derived from the observed delta,
4. an executable test of that hypothesis,
5. causal evidence,
6. replay stability,
7. demonstrated non-NONE impact,
8. human validation,
9. runnable reproduction/PoC.

A green regression is not mission completion.

## Current phase
LIVE DOGFOOD — first authorized target.

## Current milestone
Establish the first real target hypothesis-evidence chain.

## Next single action
Run CYDRA against one explicitly authorized Web2 target/surface using configured identities and inspect the resulting artifact for the first missing capability or candidate boundary.

## Done when
The artifact contains the complete chain defined above, or the target has been exhausted under the current capability set and a concrete generic capability gap is recorded.

## Attempt counter
Current action attempts: 0
Maximum attempts before diagnosis: 3

## Hard loop rule
Three failed attempts at the same action trigger a diagnosis action. Do not repeat the same repair blindly.

## Phase rule
Make it work first. Make it good later. No refactoring unless it blocks the current milestone.

## Do NOT work on
- unrelated discovery expansion
- generic template libraries
- heuristic tuning without target evidence
- EVM/Web3 adapter work
- UI
- benchmark expansion
- documentation polish
- target-specific hacks
- tests unrelated to the current mission
- cleanup of historical branches unless it blocks execution

## Scope rule
Any useful observation outside the current milestone goes under Later. It does not become active work automatically.

## Mission-change rule
Only the human may change the Mission or binary success condition. CYDRA may propose a change, but must stop and record the proposal.

## Later
- broader target coverage
- richer workflow discovery
- GraphQL-specific execution
- browser execution
- generalized template/materialization improvements
- additional vulnerability classes
- performance optimization
