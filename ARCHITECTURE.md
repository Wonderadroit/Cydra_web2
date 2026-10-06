# Web2 architecture

## Why this repository is separate

The Web2 system has a different optimization target from the Solidity system. We do not want capability repair to become the measure of progress. This repository therefore owns the Web2 research loop.

## Reused principles

- explicit target scope and allowlisting
- provenance for observed data
- fail-closed execution
- differential experiments
- causal replay
- evidence before findings

## Intentionally not ported

The Solidity research controller, benchmark families, contract materialization, compiler/Foundry logic, and its capability-repair loop are not dependencies here.

## Current graph

Target -> observed responses -> behavior model -> security boundary -> differential experiment -> evidence -> replay -> impact gate.

## First milestone

Build a reliable identity/resource/endpoint differential engine before adding broad vulnerability families. A resource identifier can be observed, but ownership is never inferred merely because a field is named id/user_id/uuid. Ownership must enter the model from explicit operator/application evidence.

## Success criterion

The first real success is not a green test suite. It is a deterministic, reproducible security contradiction on an authorized target that survives replay and can be converted into a report with evidence.
