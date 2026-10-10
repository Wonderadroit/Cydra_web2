# CYDRA Web2

A fresh, standalone Web2 security research engine for authorized bug-bounty testing.

**LLMs propose. Tools test. Evidence decides.**

Initial frontier: horizontal authorization, function-level authorization, workflow/state differentials, and request/object/identity differentials.

This repository is intentionally independent from the Solidity research system.

Execution is allowlisted by target configuration. Redirects stay inside the allowlist. Credentials are operator-supplied. Transport/capability failures are never security evidence.

Research loop:

TARGET -> OBSERVE -> MODEL -> HYPOTHESIZE -> DIFFERENTIATE -> EXECUTE -> EVIDENCE -> REPLAY -> IMPACT

A green regression means the research engine works. It does not mean a target is secure and does not count as a bounty finding.


## QA reports for mixed audiences

CYDRA's browser QA workflows publish PDF reports designed for product owners as well as QA engineers. The PDF starts with a plain-language result and summary, then provides detailed checks, environment information, and limitations. JSON and Markdown artifacts remain available for technical review.

- [How to read a CYDRA QA report](docs/QA_REPORT_GUIDE.md)
- A passing check is not a guarantee that the entire application is bug-free or secure.
- Seeded-defect benchmarks validate known scenarios; they are not customer findings.
- Inconclusive runs must be resolved and rerun, not presented as confirmed defects.
