# CYDRA read-only BOLA probe

This workflow performs a bounded, read-only differential check for Broken Object Level Authorization (BOLA/IDOR) against one explicitly supplied test object.

## Before running

1. Use only an application you own or are explicitly authorized to test.
2. Create or select a non-public test object whose exclusive owner is the first test account.
3. Configure the GitHub Actions environment named `live-dogfood` with two secrets:
   - `CYDRA_BOLA_OWNER_HEADERS_JSON`: JSON object containing the owner account's request headers.
   - `CYDRA_BOLA_COMPARISON_HEADERS_JSON`: JSON object containing the second authorized account's request headers.
4. Each secret must contain a non-empty JSON object with string header names and values. For example, a value may contain a `Cookie` header or an `Authorization` header. Never commit credentials or paste them into workflow inputs.
5. Dispatch **CYDRA read-only BOLA probe** with the target HTTPS base URL, exact same-origin resource path, and object-specific marker. Confirm both authorization and exclusive owner control.

## What it does

- Sends exactly two rounds of `GET` requests to the one supplied path: owner identity first, comparison identity second.
- Rejects non-HTTPS targets and cross-origin resource paths.
- Checks the owner's successful baseline and whether the comparison identity's response contains the exact resource marker.
- Does not send `POST`, `PUT`, `PATCH`, or `DELETE` requests.
- Produces a sanitized JSON report with statuses, marker-presence booleans, response-fingerprint equality, and a bounded verdict. Response bodies, cookies, header values, and marker values are not written to the report.

## Interpreting the result

- `candidate`: repeated responses from the second identity contained the modeled marker. Review the ownership assertion, expected access policy, and impact before reporting.
- `no_cross_identity_disclosure_observed`: the second identity did not receive the marker in these trials. This does not prove the target is secure.
- `inconclusive`: the owner baseline was not established, results were unstable, configuration was invalid, or transport failed.

This is a narrow single-object experiment, not a general scanner. An HTTP status alone is never proof of BOLA. A seeded/local benchmark is not a real customer or bounty finding.
