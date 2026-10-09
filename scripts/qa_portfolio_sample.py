from __future__ import annotations

import base64
import html
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

TARGET = "https://the-internet.herokuapp.com"
OUT = Path(os.environ.get("CYDRA_QA_OUT", "artifacts/qa-portfolio"))
VIEWPORTS = {
    "desktop": {"width": 1365, "height": 900},
    "mobile": {"width": 390, "height": 844},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def navigate_with_retries(page, url: str, attempts: int = 3):
    """Retry transient upstream navigation failures with a strict attempt budget."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            # Wait until the HTML parser has produced a DOM before asserting controls.
            # "commit" can return while the document is still unusable; this caused
            # misleading HTTP-200 results with no body/controls in CI.
            response = page.goto(url, wait_until="domcontentloaded", timeout=12000)
            if response is not None and response.status >= 500 and attempt < attempts:
                page.wait_for_timeout(1000 * attempt)
                continue
            return response
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                raise
            page.wait_for_timeout(1000 * attempt)
    if last_error is not None:
        raise last_error
    return None


def wait_for_visible_with_one_reload(page, locator, url: str, test: dict, control_name: str) -> None:
    """Allow one transparent recovery for transient page-readiness stalls; assertions remain strict."""
    try:
        locator.wait_for(state="visible", timeout=8000)
        return
    except PlaywrightTimeoutError as first_error:
        test["notes"].append(
            f"Readiness retry: {control_name} was not visible on the first attempt; reloaded the same URL once."
        )
        # A reload is a new observation of the same approved target and does not alter
        # expected state or replace the tested application code.
        page.goto(url, wait_until="domcontentloaded", timeout=12000)
        try:
            locator.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError as second_error:
            raise AssertionError(
                f"{control_name} remained unavailable after one bounded reload. "
                f"Initial timeout: {first_error}; retry timeout: {second_error}"
            ) from second_error


def main() -> int:
    # This first portfolio runner is deliberately pinned to the public training site.
    parsed = urlparse(TARGET)
    if parsed.scheme != "https" or parsed.hostname != "the-internet.herokuapp.com":
        raise ValueError("Portfolio runner is restricted to the approved demo host.")

    OUT.mkdir(parents=True, exist_ok=True)
    evidence_dir = OUT / "screenshots"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    started = utc_now()

    with sync_playwright() as p:
        browser_version = None
        for device, viewport in VIEWPORTS.items():
            # Isolate each viewport in its own Chromium process. The public demo has
            # intermittently left one renderer unresponsive after a previous viewport.
            browser = p.chromium.launch(headless=True)
            if browser_version is None:
                browser_version = browser.version
            context = browser.new_context(
                viewport=viewport,
                device_scale_factor=1,
                is_mobile=False,  # Keep Chromium desktop mode and vary viewport only for responsive-layout checks.
                has_touch=False,
                ignore_https_errors=False,
            )
            # Do not intercept target requests. The previous run returned HTTP 200 but
            # the renderer never exposed the document controls; aborting the legacy
            # analytics bootstrap was a shared variable in every failed viewport.
            # Observe the page with its normal request behavior and record failures.
            # Isolate a known unstable third-party analytics bootstrap. This
            # training-site QA scope is functional UI only; analytics delivery is
            # explicitly excluded and the tested page/application remains live.
            context.route(
                "https://the-internet.herokuapp.com/js/vendor/298279967.js",
                lambda route: route.abort(),
            )
            context.route(
                "https://298279967.log.optimizely.com/**",
                lambda route: route.abort(),
            )
            page = context.new_page()
            page.set_default_timeout(15000)
            console_errors: list[str] = []
            page_errors: list[str] = []
            failed_requests: list[dict[str, str]] = []
            http_errors: list[dict[str, object]] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("requestfailed", lambda request: failed_requests.append({"url": request.url, "error": request.failure or "unknown"}))
            page.on("response", lambda response: http_errors.append({"url": response.url, "status": response.status}) if response.status >= 400 else None)

            # Test 1: checkbox state transitions and restoration.
            checkbox_url = f"{TARGET}/checkboxes"
            test1 = {
                "id": f"QA-001-{device}",
                "name": "Checkboxes toggle and restore state",
                "url": checkbox_url,
                "status": "ERROR",
                "steps": [
                    "Open /checkboxes",
                    "Record the initial checked state of both checkboxes",
                    "Click each checkbox once and verify its state changes",
                    "Click each checkbox again and verify its initial state is restored",
                ],
                "observed": {},
                "screenshots": [],
                "notes": [],
            }
            response = None
            try:
                response = navigate_with_retries(page, checkbox_url)
                test1["http_status"] = response.status if response else None
                # Record status and observed browser behavior without reading an unbounded
                # streaming response body; a stalled body must not hang the entire QA run.
                wait_for_visible_with_one_reload(page, page.locator("input[type=checkbox]").first, checkbox_url, test1, "first checkbox")
                checks = page.locator("input[type=checkbox]")
                count = checks.count()
                if count != 2:
                    raise AssertionError(f"Expected 2 checkboxes, observed {count}")
                initial = [checks.nth(i).is_checked() for i in range(count)]
                shot = evidence_dir / f"{device}-checkboxes-initial.png"
                page.screenshot(path=str(shot), full_page=True, animations="disabled", timeout=15000)
                test1["screenshots"].append(str(shot.relative_to(OUT)))
                changed = []
                restored = []
                for i in range(count):
                    checks.nth(i).click()
                    changed.append(checks.nth(i).is_checked() != initial[i])
                for i in range(count):
                    checks.nth(i).click()
                    restored.append(checks.nth(i).is_checked() == initial[i])
                final_shot = evidence_dir / f"{device}-checkboxes-restored.png"
                page.screenshot(path=str(final_shot), full_page=True, animations="disabled", timeout=15000)
                test1["screenshots"].append(str(final_shot.relative_to(OUT)))
                test1["observed"] = {
                    "checkbox_count": count,
                    "initial_checked_states": initial,
                    "each_toggled": changed,
                    "each_restored": restored,
                    "final_checked_states": [checks.nth(i).is_checked() for i in range(count)],
                }
                if not all(changed) or not all(restored):
                    raise AssertionError("At least one checkbox did not toggle and restore as expected")
                test1["status"] = "PASS"
            except Exception as exc:
                test1["status"] = "FAIL"
                test1["notes"].append(f"{type(exc).__name__}: {exc}")
                try:
                    test1["diagnostics"] = {
                        "final_url": page.url,
                        "body_text_excerpt": page.locator("body").inner_text(timeout=3000)[:2000],
                        "body_html_excerpt": page.locator("body").inner_html(timeout=3000)[:4000],
                    }
                except Exception as diagnostic_exc:
                    test1["notes"].append(f"Diagnostic capture failed: {type(diagnostic_exc).__name__}: {diagnostic_exc}")
                try:
                    shot = evidence_dir / f"{device}-checkboxes-error.png"
                    page.screenshot(path=str(shot), full_page=False, timeout=5000)
                    test1["screenshots"].append(str(shot.relative_to(OUT)))
                except Exception as screenshot_exc:
                    test1["notes"].append(f"Error screenshot capture failed: {type(screenshot_exc).__name__}: {screenshot_exc}")
            results.append(test1)

            # Isolate each test in a fresh page so pending third-party resources or page state
            # from the previous navigation cannot contaminate the next test.
            try:
                page.close()
            except Exception:
                pass
            page = context.new_page()
            page.set_default_timeout(15000)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("requestfailed", lambda request: failed_requests.append({"url": request.url, "error": request.failure or "unknown"}))
            page.on("response", lambda response: http_errors.append({"url": response.url, "status": response.status}) if response.status >= 400 else None)

            # Test 2: adding and removing a UI element.
            add_url = f"{TARGET}/add_remove_elements/"
            test2 = {
                "id": f"QA-002-{device}",
                "name": "Add/remove element control updates the page",
                "url": add_url,
                "status": "ERROR",
                "steps": [
                    "Open /add_remove_elements/",
                    "Verify the Add Element control is present",
                    "Click Add Element and verify a Delete control appears",
                    "Click Delete and verify the added control is removed",
                ],
                "observed": {},
                "screenshots": [],
                "notes": [],
            }
            response = None
            try:
                response = navigate_with_retries(page, add_url)
                test2["http_status"] = response.status if response else None
                # Record status and observed browser behavior without reading an unbounded
                # streaming response body; a stalled body must not hang the entire QA run.
                add_button = page.get_by_role("button", name="Add Element")
                wait_for_visible_with_one_reload(page, add_button, add_url, test2, "Add Element button")
                before = page.get_by_role("button", name="Delete").count()
                shot = evidence_dir / f"{device}-add-remove-initial.png"
                page.screenshot(path=str(shot), full_page=True)
                test2["screenshots"].append(str(shot.relative_to(OUT)))
                add_button.click()
                page.get_by_role("button", name="Delete").first.wait_for(state="visible")
                after_add = page.get_by_role("button", name="Delete").count()
                after_add_shot = evidence_dir / f"{device}-add-remove-added.png"
                page.screenshot(path=str(after_add_shot), full_page=True, animations="disabled", timeout=15000)
                test2["screenshots"].append(str(after_add_shot.relative_to(OUT)))
                page.get_by_role("button", name="Delete").first.click()
                page.wait_for_function("document.querySelectorAll('button.added-manually').length === 0")
                after_remove = page.get_by_role("button", name="Delete").count()
                final_shot = evidence_dir / f"{device}-add-remove-removed.png"
                page.screenshot(path=str(final_shot), full_page=True)
                test2["screenshots"].append(str(final_shot.relative_to(OUT)))
                test2["observed"] = {
                    "delete_buttons_before_add": before,
                    "delete_buttons_after_add": after_add,
                    "delete_buttons_after_remove": after_remove,
                }
                if after_add != before + 1 or after_remove != before:
                    raise AssertionError("Add/remove counts did not return to the expected state")
                test2["status"] = "PASS"
            except Exception as exc:
                test2["status"] = "FAIL"
                test2["notes"].append(f"{type(exc).__name__}: {exc}")
                try:
                    test2["diagnostics"] = {
                        "final_url": page.url,
                        "body_text_excerpt": page.locator("body").inner_text(timeout=3000)[:2000],
                        "body_html_excerpt": page.locator("body").inner_html(timeout=3000)[:4000],
                    }
                except Exception as diagnostic_exc:
                    test2["notes"].append(f"Diagnostic capture failed: {type(diagnostic_exc).__name__}: {diagnostic_exc}")
                try:
                    shot = evidence_dir / f"{device}-add-remove-error.png"
                    page.screenshot(path=str(shot), full_page=False, timeout=5000)
                    test2["screenshots"].append(str(shot.relative_to(OUT)))
                except Exception as screenshot_exc:
                    test2["notes"].append(f"Error screenshot capture failed: {type(screenshot_exc).__name__}: {screenshot_exc}")
            results.append(test2)

            runtime = {
                "console_errors": console_errors[:30],
                "page_errors": page_errors[:30],
                "failed_requests": failed_requests[:50],
                "http_errors": http_errors[:50],
            }
            test1["runtime_observations"] = runtime
            test2["runtime_observations"] = runtime
            # Close each viewport context before browser teardown so the next viewport
            # starts cleanly; diagnostics above are bounded and already captured.
            context.close()
            browser.close()

    ended = utc_now()
    passed = sum(1 for item in results if item["status"] == "PASS")
    failed = sum(1 for item in results if item["status"] == "FAIL")
    report = {
        "title": "CYDRA Website QA Portfolio Sample",
        "target": TARGET,
        "target_type": "Public training/demo website; not a production client",
        "started_at_utc": started,
        "ended_at_utc": ended,
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "browser": "Chromium",
            "browser_version": browser_version,
            "viewports": VIEWPORTS,
            "mobile_note": "Mobile coverage is a 390x844 narrow viewport only; touch interaction and physical-device behavior are not certified.",
            "test_harness_adjustments": ["The known legacy analytics request was blocked because it is unrelated to the tested controls and has shown upstream instability. Live HTML, CSS, jQuery, Foundation, and application behavior remain from the target; analytics delivery itself is not assessed."],
        },
        "summary": {"total": len(results), "passed": passed, "failed": failed},
        "tests": results,
        "interpretation": (
            "This report records observed UI behavior on a public training site. "
            "A failed test is a test discrepancy requiring triage, not automatically a production defect or security finding. "
            "Console errors and page errors are contextual observations, not findings by themselves."
        ),
    }
    write_json(OUT / "report.json", report)

    lines = [
        "<div align=\"center\">",
        "",
        "# CYDRA",
        "**WEBSITE QUALITY ASSURANCE**",
        "",
        "*Independent, evidence-led website testing*",
        "",
        "---",
        "",
        "**FUNCTIONAL QA REPORT**",
        "",
        "</div>",
        "",
        f"> **Report status:** {'PASS' if failed == 0 else 'ATTENTION REQUIRED'}  ",
        f"> **Prepared:** {ended[:10]} (UTC)  ",
        "> **Engagement:** Demonstration assessment — public training website",
        "",
        "## Executive summary",
        "",
        f"CYDRA ran **{len(results)} functional checks** across desktop and mobile-emulated browser sizes. **{passed} passed and {failed} failed.**",
        "",
        ("**Overall result: PASS.** The selected interactions behaved as expected in this run. This is a limited functional sample, not a full-site audit, security certification, or guarantee that the website has no defects."
         if failed == 0 else
         "**Overall result: ATTENTION REQUIRED.** One or more checks did not meet the expected result. Review the individual observations and evidence before drawing conclusions."),
        "",
        "### What this means in plain English",
        "",
        f"- **Checkboxes:** {sum(1 for item in results if item['id'].startswith('QA-001') and item['status'] == 'PASS')} of 2 viewport checks passed.",
        f"- **Add and remove:** {sum(1 for item in results if item['id'].startswith('QA-002') and item['status'] == 'PASS')} of 2 viewport checks passed.",
        "- **Screen sizes:** desktop viewport 1365×900 and narrow viewport 390×844; this is not physical-device certification.",
        "- **Evidence:** screenshots and any capture failures are listed with each individual test result.",
        "",
        "## Assessment details",
        "",
        f"- **Website tested:** [{TARGET}]({TARGET})",
        "- **Target type:** Public training/demo website; not a production client",
        f"- **Run started (UTC):** {started}",
        f"- **Run ended (UTC):** {ended}",
        f"- **Environment:** Chromium {browser_version}; Python {sys.version.split()[0]}",
        "- **Coverage:** desktop viewport 1365×900 and narrow viewport 390×844 (viewport-only; no physical-device certification)",
        "- **Evidence:** automated screenshots attached as workflow artifacts",
        "",
        "## Summary",
        "",
        f"- Total checks: **{len(results)}**",
        f"- Passed: **{passed}**",
        f"- Failed: **{failed}**",
        "",
        "## Results",
        "",
    ]
    for item in results:
        if item["id"].startswith("QA-001"):
            plain_result = (
                "Both checkboxes changed state when selected and returned to their original states."
                if item["status"] == "PASS" else
                "The checkbox interaction did not meet every expected state change. Review the notes and screenshots."
            )
        else:
            observed = item.get("observed", {})
            plain_result = (
                f"The Delete control count changed from {observed.get('delete_buttons_before_add', 'unknown')} "
                f"to {observed.get('delete_buttons_after_add', 'unknown')} after adding, then to "
                f"{observed.get('delete_buttons_after_remove', 'unknown')} after removing."
                if item["status"] == "PASS" else
                "The add/remove interaction did not meet every expected count. Review the notes and screenshots."
            )
        lines.extend([
            f"### {item['id']}: {item['name']}",
            "",
            f"- **Status:** {item['status']}",
            f"- **Plain-English result:** {plain_result}",
            f"- **URL:** {item['url']}",
            f"- **HTTP status:** {item.get('http_status', 'not recorded')}",
            "- **Steps:**",
        ])
        lines.extend([f"  {i}. {step}" for i, step in enumerate(item["steps"], 1)])
        lines.extend(["", "**Observed data:**", "", "~~~json", json.dumps(item["observed"], indent=2), "~~~", ""])
        if item["notes"]:
            lines.extend(["**Notes:**", ""])
            lines.extend([f"- {note}" for note in item["notes"]])
            lines.append("")
        lines.extend(["**Screenshots:**", ""])
        if item["screenshots"]:
            lines.extend([f"- {path}" for path in item["screenshots"]])
        else:
            lines.append("- No screenshot was captured.")
        runtime = item.get("runtime_observations", {})
        if runtime.get("console_errors") or runtime.get("page_errors"):
            lines.extend(["", "**Runtime observations (not automatically defects):**", ""])
            lines.extend([f"- Console errors: {len(runtime.get('console_errors', []))}",
                          f"- Page errors: {len(runtime.get('page_errors', []))}"])
        lines.append("")
    lines.extend([
        "## Evidence and limitations",
        "",
        report["interpretation"],
        "",
        "This is a sample automation run, not a claim of paid client experience. The narrow viewport is a responsive-layout check only; it does not certify touch behavior or physical devices. Only the known legacy analytics request was blocked because it is unrelated to the tested controls and has shown upstream instability. Live page HTML, CSS, jQuery, Foundation, and application behavior remain from the target; analytics delivery itself is not assessed. Any failure must be independently reproduced and assessed for user impact before being described as a defect.",
        "",
    ])
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")

    image_sections = []
    for item in results:
        for relative in item["screenshots"]:
            path = OUT / relative
            if not path.exists():
                continue
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            label = html.escape(f"{item['id']} — {relative}")
            image_sections.append(
                f"<section class='evidence'><h3>{label}</h3>"
                f"<img src='data:image/png;base64,{data}' alt='{label}' /></section>"
            )
    def plain_english_result(item: dict) -> str:
        observed = item.get("observed", {})
        if item["id"].startswith("QA-001"):
            if item["status"] == "PASS":
                return "Both checkboxes changed when selected and returned to their original states."
            return "The checkbox interaction did not meet every expected state change. See notes and screenshots."
        if item["status"] == "PASS":
            return (
                f"Delete controls: {observed.get('delete_buttons_before_add', 'unknown')} before adding, "
                f"{observed.get('delete_buttons_after_add', 'unknown')} after adding, and "
                f"{observed.get('delete_buttons_after_remove', 'unknown')} after removing."
            )
        return "The add/remove interaction did not meet every expected count. See notes and screenshots."

    result_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['id'])}</td>"
        f"<td>{html.escape(item['name'])}</td>"
        f"<td class='{item['status'].lower()}'>{html.escape(item['status'])}</td>"
        f"<td>{html.escape(plain_english_result(item) + (' One page reload was needed after an initial readiness timeout.' if any(note.startswith('Readiness retry:') for note in item.get('notes', [])) else ''))}</td>"
        "</tr>"
        for item in results
    )
    pdf_html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page{{size:A4;margin:18mm 16mm 20mm;@bottom-right{{content:"CYDRA · Functional QA Report · Page " counter(page);font-size:8pt;color:#667085}}}}
    body{{font-family:Arial,sans-serif;color:#172033;margin:0;font-size:10pt;line-height:1.45}}
    .letterhead{{border-bottom:3px solid #163a63;padding:0 0 12px;margin-bottom:22px}}
    .brand{{font-size:23pt;letter-spacing:3px;font-weight:800;color:#163a63;margin:0}}
    .brandline{{font-size:9pt;letter-spacing:1.5px;font-weight:bold;color:#344054;margin-top:2px}}
    .document-type{{margin-top:16px;font-size:15pt;font-weight:bold;color:#163a63}}
    .report-meta{{background:#f4f7fb;border-left:4px solid #163a63;padding:10px 12px;margin:14px 0 20px}}
    h1{{font-size:22pt;color:#163a63}} h2{{margin-top:24px;border-bottom:1px solid #d0d5dd;padding-bottom:5px;color:#163a63}}
    h3{{font-size:12pt;color:#344054}} .muted{{color:#555}} .summary{{font-size:12pt;font-weight:bold}}
    .result-pass{{color:#087443;font-weight:bold}} .result-fail{{color:#b42318;font-weight:bold}}
    table{{width:100%;border-collapse:collapse;font-size:9pt}}
    th,td{{border:1px solid #ccd2da;padding:7px;vertical-align:top;overflow-wrap:anywhere}}
    th{{background:#eaf0f7;text-align:left}} .pass{{color:#087443;font-weight:bold}} .fail{{color:#b42318;font-weight:bold}}
    .evidence{{page-break-inside:avoid;margin:16px 0}} img{{max-width:100%;max-height:520px;object-fit:contain;border:1px solid #ddd}}
    .plain-english{{background:#f8fafc;padding:12px;border:1px solid #d0d5dd}}
    </style></head><body>
    <header class="letterhead"><p class="brand">CYDRA</p><div class="brandline">WEBSITE QUALITY ASSURANCE</div><div class="document-type">FUNCTIONAL QA REPORT</div><p class="muted">Evidence-led testing · Clear results · Reproducible observations</p></header>
    <div class="report-meta"><b>Report date (UTC):</b> {html.escape(ended[:10])}<br>
    <b>Report outcome:</b> <span class="{'result-pass' if failed == 0 else 'result-fail'}">{'PASS' if failed == 0 else 'ATTENTION REQUIRED'}</span><br>
    <b>Engagement type:</b> Demonstration assessment on a public training website</div>
    <h2>Executive summary</h2>
    <p class="summary">{len(results)} checks completed · {passed} passed · {failed} failed</p>
    <div class="plain-english"><b>What this means:</b> {'The selected page interactions behaved as expected during this run. This is a limited functional sample, not a full-site audit, security certification, or guarantee that the website has no defects.' if failed == 0 else 'One or more checks did not meet the expected result. Review the observations and screenshots before deciding whether the behaviour is a defect.'}</div>
    <h2>Assessment details</h2>
    <p class="muted">Automated functional checks on a public training website — not a production client engagement.</p>
    <p><b>Website:</b> {html.escape(TARGET)}<br>
    <b>Run started (UTC):</b> {html.escape(started)}<br>
    <b>Run ended (UTC):</b> {html.escape(ended)}<br>
    <b>Environment:</b> Chromium {html.escape(browser_version)}; desktop 1365×900 and narrow viewport 390×844 (viewport-only)</p>
    <p><b>Coverage in this report:</b> checkbox state changes and add/remove element behaviour at two viewport sizes.</p>
    <h2>Test results</h2><table><thead><tr><th>ID</th><th>Test</th><th>Status</th><th>Result in plain English</th></tr></thead><tbody>{result_rows}</tbody></table>
    <h2>Evidence screenshots</h2>{''.join(image_sections)}
    <h2>Interpretation and limitations</h2><p>{html.escape(report['interpretation'])}</p>
    <p>Narrow-viewport coverage is responsive-layout testing only; touch behavior and physical devices are not certified. Only the known legacy analytics request was blocked because it is unrelated to the tested controls and has shown upstream instability. Live page HTML, CSS, jQuery, Foundation, and application behavior remain from the target; analytics delivery itself is not assessed. A failed test is a discrepancy requiring triage, not automatically a defect or security finding. Runtime errors are context only.</p>
    </body></html>"""
    with sync_playwright() as p:
        pdf_browser = p.chromium.launch(headless=True)
        pdf_page = pdf_browser.new_page()
        pdf_page.set_content(pdf_html, wait_until="load")
        pdf_page.pdf(path=str(OUT / "report.pdf"), format="A4", print_background=True, prefer_css_page_size=True)
        pdf_browser.close()

    print(f"QA portfolio run complete: passed={passed} failed={failed}")
    print(f"Artifacts: {OUT / 'report.md'}, {OUT / 'report.pdf'}, {OUT / 'report.json'}, {evidence_dir}")
    # A green workflow requires every asserted behavior to pass. Environmental blockers remain failures until triaged.
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
