from __future__ import annotations

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
ALL_VIEWPORTS = {"desktop": {"width": 1365, "height": 900}, "mobile": {"width": 390, "height": 844}}
requested = os.environ.get("CYDRA_QA_VIEWPORT", "all").strip().lower()
if requested not in {"all", *ALL_VIEWPORTS}:
    raise ValueError("CYDRA_QA_VIEWPORT must be 'all', 'desktop', or 'mobile'.")
VIEWPORTS = ALL_VIEWPORTS if requested == "all" else {requested: ALL_VIEWPORTS[requested]}
TELEMETRY_SUFFIXES = ("optimizely.com",)

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")

def attach_diagnostics(page, obs):
    page.on("console", lambda msg: obs["console_errors"].append(msg.text[:500]) if msg.type == "error" and len(obs["console_errors"]) < 30 else None)
    page.on("pageerror", lambda error: obs["page_errors"].append(str(error)[:500]) if len(obs["page_errors"]) < 30 else None)
    page.on("requestfailed", lambda req: obs["failed_requests"].append({"url": req.url.split("?")[0], "error": req.failure or "unknown"}) if len(obs["failed_requests"]) < 50 else None)
    page.on("response", lambda res: obs["http_errors"].append({"url": res.url.split("?")[0], "status": res.status}) if res.status >= 400 and len(obs["http_errors"]) < 50 else None)

def bounded_diagnostics(page, test, prefix):
    diag = {"final_url": (page.url or "")[:500], "is_closed": page.is_closed()}
    try:
        diag["document_state"] = page.locator("html").get_attribute("data-diagnostic-ready", timeout=1500)
        diag["body_present"] = page.locator("body").count() > 0
        diag["body_text_excerpt"] = page.locator("body").inner_text(timeout=2000)[:1500]
    except Exception as exc:
        diag["renderer_diagnostic_error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
    try:
        shot = OUT / "screenshots" / f"{prefix}-error.png"
        page.screenshot(path=str(shot), full_page=False, timeout=3000, animations="disabled")
        test["screenshots"].append(str(shot.relative_to(OUT)))
    except Exception as exc:
        diag["screenshot_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    test["diagnostics"] = diag

def run_test(playwright, device, viewport, kind):
    url = f"{TARGET}/checkboxes" if kind == "checkboxes" else f"{TARGET}/add_remove_elements/"
    test = {"id": f"{'QA-001' if kind == 'checkboxes' else 'QA-002'}-{device}",
            "name": "Checkboxes toggle and restore state" if kind == "checkboxes" else "Add/remove element control updates the page",
            "url": url, "status": "FAIL", "steps": [], "observed": {}, "screenshots": [], "notes": []}
    obs = {"console_errors": [], "page_errors": [], "failed_requests": [], "http_errors": [], "blocked_telemetry_requests": 0}
    browser = context = page = None
    try:
        # A fresh browser process for every functional test, not just a new page/context.
        browser = playwright.chromium.launch(headless=True)
        test["browser_version"] = browser.version
        context = browser.new_context(viewport=viewport, device_scale_factor=1, is_mobile=False, has_touch=False, ignore_https_errors=False)
        def route_request(route):
            host = (urlparse(route.request.url).hostname or "").lower()
            if any(host == suffix or host.endswith("." + suffix) for suffix in TELEMETRY_SUFFIXES):
                obs["blocked_telemetry_requests"] += 1
                route.abort()
            else:
                route.continue_()
        context.route("**/*", route_request)
        page = context.new_page()
        page.set_default_timeout(5000)
        attach_diagnostics(page, obs)
        response = page.goto(url, wait_until="commit", timeout=15000)
        # Commit proves the main response arrived; avoid waiting on third-party resources for DOMContentLoaded.
        page.locator("body").wait_for(state="attached", timeout=5000)
        test["http_status"] = response.status if response else None
        if response and response.status >= 400:
            raise AssertionError(f"Navigation returned HTTP {response.status}")
        if kind == "checkboxes":
            controls = page.locator('input[type="checkbox"]')
            controls.first.wait_for(state="visible", timeout=6000)
            count = controls.count()
            if count != 2:
                raise AssertionError(f"Expected 2 checkboxes, observed {count}")
            initial = [controls.nth(i).is_checked() for i in range(count)]
            changed, restored = [], []
            for i in range(count):
                controls.nth(i).click(timeout=3000)
                changed.append(controls.nth(i).is_checked() != initial[i])
            for i in range(count):
                controls.nth(i).click(timeout=3000)
                restored.append(controls.nth(i).is_checked() == initial[i])
            test["steps"] = ["Open /checkboxes", "Record initial checkbox states", "Toggle both checkboxes", "Verify restoration"]
            test["observed"] = {"checkbox_count": count, "initial_checked_states": initial, "each_toggled": changed,
                                "each_restored": restored, "final_checked_states": [controls.nth(i).is_checked() for i in range(count)]}
            if not all(changed) or not all(restored):
                raise AssertionError("At least one checkbox failed to toggle and restore")
        else:
            add = page.get_by_role("button", name="Add Element")
            add.wait_for(state="visible", timeout=6000)
            before = page.get_by_role("button", name="Delete").count()
            add.click(timeout=3000)
            delete = page.get_by_role("button", name="Delete").first
            delete.wait_for(state="visible", timeout=3000)
            after_add = page.get_by_role("button", name="Delete").count()
            delete.click(timeout=3000)
            page.wait_for_function("document.querySelectorAll('button.added-manually').length === 0", timeout=3000)
            after_remove = page.get_by_role("button", name="Delete").count()
            test["steps"] = ["Open /add_remove_elements/", "Verify Add Element", "Add and verify Delete", "Delete and verify removal"]
            test["observed"] = {"delete_buttons_before_add": before, "delete_buttons_after_add": after_add, "delete_buttons_after_remove": after_remove}
            if after_add != before + 1 or after_remove != before:
                raise AssertionError("Add/remove counts did not return to expected state")
        shot = OUT / "screenshots" / f"{device}-{kind}-pass.png"
        page.screenshot(path=str(shot), full_page=True, timeout=5000, animations="disabled")
        test["screenshots"].append(str(shot.relative_to(OUT)))
        test["status"] = "PASS"
    except Exception as exc:
        test["notes"].append(f"{type(exc).__name__}: {str(exc)[:1200]}")
        if page is not None and not page.is_closed():
            bounded_diagnostics(page, test, f"{device}-{kind}")
    finally:
        test["runtime_observations"] = obs
        for obj in (context, browser):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
    return test

def main():
    parsed = urlparse(TARGET)
    if parsed.scheme != "https" or parsed.hostname != "the-internet.herokuapp.com":
        raise ValueError("Portfolio runner is restricted to the approved demo host.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "screenshots").mkdir(parents=True, exist_ok=True)
    results, started, browser_version = [], utc_now(), None
    with sync_playwright() as playwright:
        for device, viewport in VIEWPORTS.items():
            for kind in ("checkboxes", "add_remove"):
                result = run_test(playwright, device, viewport, kind)
                browser_version = result.get("browser_version", browser_version)
                results.append(result)
    ended = utc_now()
    passed = sum(item["status"] == "PASS" for item in results)
    failed = sum(item["status"] == "FAIL" for item in results)
    report = {"title": "CYDRA Website Quality Assurance", "target": TARGET,
              "target_type": "Public training/demo website; not a production client",
              "started_at_utc": started, "ended_at_utc": ended,
              "environment": {"platform": platform.platform(), "python": sys.version.split()[0],
                              "browser": "Chromium", "browser_version": browser_version, "viewports": VIEWPORTS,
                              "mobile_note": "390x844 narrow viewport only; physical-device and touch certification are not claimed.",
                              "test_harness_adjustments": ["Every check runs in a new Chromium process, context, and page.",
                                  "Known Optimizely telemetry is blocked to isolate third-party analytics; first-party target requests are untouched.",
                                  "Navigation and renderer diagnostics use bounded timeouts."]},
              "summary": {"total": len(results), "passed": passed, "failed": failed}, "tests": results,
              "interpretation": "A failed test is a test discrepancy, not automatically a production defect. Telemetry isolation is not proof telemetry caused prior failures."}
    write_json(OUT / "report.json", report)
    lines = ["# CYDRA Website Quality Assurance", "", f"Result: {'PASS' if failed == 0 else 'ATTENTION REQUIRED'}",
             f"Prepared: {ended}", f"Target: {TARGET}", "", f"Checks: {len(results)} total; {passed} passed; {failed} failed.", "",
             "Each check uses a separate Chromium process. Known Optimizely telemetry is blocked for functional isolation. Narrow-viewport sample only; not physical-device certification.", ""]
    for item in results:
        lines += [f"## {item['id']}: {item['name']}", f"Status: {item['status']}", f"URL: {item['url']}",
                  f"HTTP: {item.get('http_status')}", "", "Observed JSON:", json.dumps(item.get("observed", {}), indent=2), "",
                  "Notes:", *[f"- {note}" for note in item["notes"]], "", "Runtime observations:",
                  json.dumps(item.get("runtime_observations", {}), indent=2)[:6000], ""]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
