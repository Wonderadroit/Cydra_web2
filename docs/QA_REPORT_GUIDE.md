# Understanding a CYDRA QA report

CYDRA produces a PDF for people who need the conclusion quickly and keeps technical detail available for the people fixing the software.

## Start here if you are not technical

- **Overall result**: a short assessment of the checks that actually ran.
- **Passed**: the specific expected behavior happened.
- **Failed**: an assertion observed behavior that contradicted the test expectation. A person still needs to confirm whether this is a product defect.
- **Inconclusive**: the test could not decide reliably, for example because the browser or environment did not become ready. It is not a confirmed bug.
- **Limitations and scope**: explains what was and was not tested.

A passing run does not mean the entire product is bug-free or secure.

## Start here if you are a developer or QA engineer

Use the detailed results, timestamps, environment, screenshots, and the companion JSON/Markdown artifacts. The JSON is the machine-readable source of record. Reproduce a failure before filing it, and include the actual-versus-expected behavior, steps, and impact in a defect ticket.

## Understanding the seeded-defect benchmark

A seeded-defect benchmark deliberately introduces known bugs into sample pages to check whether assertions detect them. When a mutant is marked **DETECTED (expected)**, that is a successful benchmark outcome, not a failing CI run. It validates the benchmark cases only; it is not evidence that CYDRA found a defect in a customer application.

## Report generation

The browser QA workflows install the optional reporting extra and generate `report.pdf` beside `report.json`, `report.md`, and screenshots. To render an existing JSON report locally:

```bash
python -m pip install -e ".[report]"
python scripts/qa_report_pdf.py --input path/to/report.json --output report.pdf
```

Only test applications and environments you own or have explicit permission to assess.
