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

from playwright.sync_api import sync_playwright

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
        browser = p.chromium.launch(headless=True)
        browser_version = browser.version
        for device, viewport in VIEWPORTS.items():
            context = browser.new_context(
                viewport=viewport,
                device_scale_factor=1,
                is_mobile=(device == "mobile"),
                has_touch=(device == "mobile"),
                ignore_https_errors=False,
            )
            # Remove only the legacy analytics <script> element from the two HTML
            # documents under test. Returning the original document with that non-functional
            # bootstrap tag removed avoids a parser-blocking third-party script in CI while
            # preserving the application's own scripts, markup, styles, and tested controls.
            import re

            def remove_legacy_analytics(route):
                response = route.fetch()
                body = response.text()
                body = re.sub(
                    r"""<script\s+src=["']/js/vendor/298279967\.js["']\s*>\s*</script>""",
                    "",
                    body,
                    count=1,
                    flags=re.IGNORECASE,
                )
                route.fulfill(response=response, body=body)

            # Retry transient target-side 5xx responses for assets and documents. A
            # single 503 on the legacy jQuery bundle makes the demo's inline Add Element
            # handler fail with "$ is not defined"; retrying the same request preserves the
            # real page and behavior rather than mocking application code. Persistent 5xx
            # responses still reach the browser and remain visible as test failures.
            def retry_transient_server_errors(route):
                response = route.fetch()
                for _ in range(2):
                    if response.status < 500:
                        break
                    response = route.fetch()
                route.fulfill(response=response)

            # Register the host-wide retry first; the specific HTML rewrites below take
            # precedence and remain limited to removing the legacy analytics bootstrap.
            context.route("https://the-internet.herokuapp.com/**", retry_transient_server_errors)
            context.route("https://the-internet.herokuapp.com/checkboxes", remove_legacy_analytics)
            context.route("https://the-internet.herokuapp.com/add_remove_elements/**", remove_legacy_analytics)
            context.route("https://298279967.log.optimizely.com/**", lambda route: route.abort())
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
                response = page.goto(checkbox_url, wait_until="domcontentloaded", timeout=45000)
                test1["http_status"] = response.status if response else None
                if response:
                    try:
                        test1["response_html_excerpt"] = response.text()[:3000]
                    except Exception as body_exc:
                        test1["notes"].append(f"Response-body capture failed: {type(body_exc).__name__}: {body_exc}")
                page.locator("input[type=checkbox]").first.wait_for(state="visible")
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
                        "title": page.title(),
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
                response = page.goto(add_url, wait_until="domcontentloaded", timeout=45000)
                test2["http_status"] = response.status if response else None
                if response:
                    try:
                        test2["response_html_excerpt"] = response.text()[:3000]
                    except Exception as body_exc:
                        test2["notes"].append(f"Response-body capture failed: {type(body_exc).__name__}: {body_exc}")
                add_button = page.get_by_role("button", name="Add Element")
                add_button.wait_for(state="visible")
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
                        "title": page.title(),
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
            "mobile_note": "Mobile is a 390x844 browser viewport with touch emulation, not a physical-device certification.",
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
        "# CYDRA Website QA Portfolio Sample",
        "",
        f"- **Target:** [{TARGET}]({TARGET})",
        "- **Target type:** Public training/demo website; not a production client",
        f"- **Run started (UTC):** {started}",
        f"- **Run ended (UTC):** {ended}",
        f"- **Environment:** Chromium {browser_version}; Python {sys.version.split()[0]}",
        "- **Coverage:** desktop viewport 1365×900 and mobile-emulated viewport 390×844",
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
        lines.extend([
            f"### {item['id']}: {item['name']}",
            "",
            f"- **Status:** {item['status']}",
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
        "This is a sample automation run, not a claim of paid client experience. Mobile coverage uses viewport and touch emulation; it does not replace testing on physical devices. Any failure must be independently reproduced and assessed for user impact before being described as a defect.",
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
    result_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['id'])}</td>"
        f"<td>{html.escape(item['name'])}</td>"
        f"<td class='{item['status'].lower()}'>{html.escape(item['status'])}</td>"
        f"<td>{html.escape(json.dumps(item['observed'], sort_keys=True))}</td>"
        "</tr>"
        for item in results
    )
    pdf_html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
    body{{font-family:Arial,sans-serif;color:#172033;margin:28px;font-size:10pt}}
    h1{{font-size:24pt}} h2{{margin-top:24px;border-bottom:1px solid #ddd;padding-bottom:5px}}
    .muted{{color:#555}} table{{width:100%;border-collapse:collapse;font-size:9pt}}
    th,td{{border:1px solid #ccd2da;padding:7px;vertical-align:top;overflow-wrap:anywhere}}
    th{{background:#f0f3f7}} .pass{{color:#087443;font-weight:bold}} .fail{{color:#b42318;font-weight:bold}}
    .evidence{{page-break-inside:avoid;margin:16px 0}} img{{max-width:100%;max-height:570px;object-fit:contain;border:1px solid #ddd}}
    </style></head><body>
    <h1>CYDRA Website QA Portfolio Sample</h1>
    <p class="muted">Automated functional checks on a public training website — not a production client engagement.</p>
    <p><b>Target:</b> {html.escape(TARGET)}<br>
    <b>Run started (UTC):</b> {html.escape(started)}<br>
    <b>Run ended (UTC):</b> {html.escape(ended)}<br>
    <b>Environment:</b> Chromium {html.escape(browser_version)}; desktop 1365×900 and mobile-emulated 390×844</p>
    <h2>Summary</h2><p>Total: {len(results)} · Passed: {passed} · Failed: {failed}</p>
    <h2>Test results</h2><table><thead><tr><th>ID</th><th>Test</th><th>Status</th><th>Observed data</th></tr></thead><tbody>{result_rows}</tbody></table>
    <h2>Evidence screenshots</h2>{''.join(image_sections)}
    <h2>Interpretation and limitations</h2><p>{html.escape(report['interpretation'])}</p>
    <p>Mobile coverage uses viewport and touch emulation, not a physical-device certification. A failed test is a discrepancy requiring triage, not automatically a defect or security finding. Runtime errors are context only.</p>
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
