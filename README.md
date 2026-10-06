# CYDRA Web2

A fresh, standalone Web2 security research engine for authorized bug-bounty testing.

**LLMs propose. Tools test. Evidence decides.**

Initial frontier: horizontal authorization, function-level authorization, workflow/state differentials, and request/object/identity differentials.

This repository is intentionally independent from the Solidity research system.

Execution is allowlisted by target configuration. Redirects stay inside the allowlist. Credentials are operator-supplied. Transport/capability failures are never security evidence.

Research loop:

TARGET -> OBSERVE -> MODEL -> HYPOTHESIZE -> DIFFERENTIATE -> EXECUTE -> EVIDENCE -> REPLAY -> IMPACT

A green regression means the research engine works. It does not mean a target is secure and does not count as a bounty finding.
