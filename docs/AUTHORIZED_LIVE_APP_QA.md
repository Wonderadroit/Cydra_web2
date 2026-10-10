# Authorized live-application QA

## Purpose

The **CYDRA authorized live-app QA** workflow performs a small, read-only browser smoke check against one operator-supplied public HTTPS page. It creates JSON and Markdown evidence plus a customer-readable PDF.

## Before running

1. Confirm that you own the application or have explicit permission to test it.
2. Open **Actions → CYDRA authorized live-app QA → Run workflow**.
3. Enter the exact HTTPS URL in scope and check the authorization confirmation.
4. Download the `cydra-live-app-qa` artifact and inspect `report.pdf`, `report.md`, and `report.json`.

## What it checks

- Public HTTPS URL validation and basic DNS address checks.
- One top-level page load, final URL, HTTP response status, title, document readiness, and readable body text.
- Counts and a small sample of same-origin links and interactive elements; it does not click or submit them.
- Browser console errors, uncaught page errors, failed requests, HTTP error responses, and a screenshot where available.

## Safety and limits

- One supplied page only; no crawling, form submission, authentication, fuzzing, exploit payloads, or state-changing interactions.
- Local, private, link-local, and reserved IP addresses are rejected on URL validation and browser requests.
- DNS checks are best-effort safeguards, not an SSRF-proof network boundary. Use only targets you are authorized to test and never put credentials in the URL.
- Third-party resource failures and console errors are observations, not confirmed application defects.
- HTTP error responses and empty page content are reported as failed checks for human review, not automatically as confirmed bugs.
- A timeout or execution issue is **INCONCLUSIVE**, not PASS and not a product defect.
- One passing page does not establish application-wide QA coverage or security.

## Result interpretation

- **PASS** — the page returned a non-error response and exposed a title and readable body text.
- **FAIL** — a defined page-level expectation failed; reproduce and review before reporting a defect.
- **INCONCLUSIVE** — target validation or execution prevented a reliable verdict; resolve the blocker and rerun.

This workflow is a first live-target QA milestone, not a full application test suite or a substitute for a test plan.
