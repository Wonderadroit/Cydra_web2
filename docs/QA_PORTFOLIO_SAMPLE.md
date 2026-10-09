# CYDRA QA portfolio sample

This workflow demonstrates browser-driven functional QA on the public training site https://the-internet.herokuapp.com. It is intentionally separate from CYDRA Web2's security-research workflow.

## Run

1. Open Actions → CYDRA QA portfolio sample.
2. Choose Run workflow.
3. Open the completed run and download the cydra-qa-portfolio-sample artifact.

The runner tests two UI behaviors in both desktop and mobile-emulated Chromium viewports:
- Checkbox toggling and state restoration.
- Add/remove element behavior.

## Artifacts

- report.md: readable report.
- report.pdf: shareable report with screenshots.
- report.json: machine-readable observations.
- screenshots/: browser screenshots at initial and post-interaction states.

## Evidence rules and limits

- This first sample runner is pinned to the public training host; it does not accept arbitrary targets.
- Mobile is viewport and touch emulation, not physical-device certification.
- A failed assertion is a discrepancy to triage, not automatically a defect.
- Browser console errors are context, not findings by themselves.
- The sample is not a paid client engagement and must not be represented as one.
- Generalizing to client sites requires a separate authorized-target configuration and explicit scope controls.
