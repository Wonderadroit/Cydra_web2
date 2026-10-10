from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(os.environ.get("CYDRA_QA_BENCHMARK_OUT", "artifacts/qa-mutation-benchmark"))
CASES = {
    "checkbox_toggle": {
        "good": """<!doctype html><html><body><input id="flag" type="checkbox"></body></html>""",
        "mutant": """<!doctype html><html><body><input id="flag" type="checkbox" disabled></body></html>""",
        "description": "Checkbox must change state when activated.",
    },
    "add_element": {
        "good": """<!doctype html><html><body><button id="add">Add</button><ul id="items"></ul><script>document.querySelector('#add').addEventListener('click',()=>{const li=document.createElement('li');li.textContent='item';document.querySelector('#items').appendChild(li)});</script></body></html>""",
        "mutant": """<!doctype html><html><body><button id="add">Add</button><ul id="items"></ul></body></html>""",
        "description": "Add action must create one visible item.",
    },
    "delete_element": {
        "good": """<!doctype html><html><body><button id="delete">Delete</button><script>document.querySelector('#delete').addEventListener('click',()=>document.querySelector('#delete').remove());</script></body></html>""",
        "mutant": """<!doctype html><html><body><button id="delete">Delete</button></body></html>""",
        "description": "Delete action must remove its target element.",
    },
    "required_validation": {
        "good": """<!doctype html><html><body><form id="form"><input id="email" type="email" required><button>Submit</button></form></body></html>""",
        "mutant": """<!doctype html><html><body><form id="form"><input id="email" type="email"><button>Submit</button></form></body></html>""",
        "description": "An empty required email field must fail native form validation.",
    },
}


def assert_contract(page, case_name: str) -> None:
    if case_name == "checkbox_toggle":
        control = page.locator("#flag")
        before = control.is_checked()
        control.click(timeout=1000)
        after = control.is_checked()
        assert after != before, f"checkbox state did not change (before={before}, after={after})"
    elif case_name == "add_element":
        before = page.locator("#items li").count()
        page.locator("#add").click(timeout=1000)
        after = page.locator("#items li").count()
        assert after == before + 1, f"expected one added item, before={before}, after={after}"
    elif case_name == "delete_element":
        page.locator("#delete").click(timeout=1000)
        assert page.locator("#delete").count() == 0, "delete action left its target in the DOM"
    elif case_name == "required_validation":
        valid = page.locator("#form").evaluate("(form) => form.checkValidity()")
        assert valid is False, "empty required email form unexpectedly passed validation"
    else:
        raise ValueError(f"unknown case: {case_name}")


def run_variant(playwright, case_name: str, variant: str, html: str) -> dict:
    browser = playwright.chromium.launch(headless=True, args=["--disable-gpu", "--disable-dev-shm-usage"])
    page = None
    result = {"case": case_name, "variant": variant, "expected": "PASS" if variant == "good" else "DETECTED"}
    try:
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.set_content(html, wait_until="domcontentloaded", timeout=3000)
        assert_contract(page, case_name)
        result.update({"observed": "PASS", "assertion": "contract satisfied"})
    except Exception as exc:
        result.update({"observed": "FAIL", "assertion": f"{type(exc).__name__}: {str(exc)[:500]}"})
    finally:
        if page is not None:
            try:
                OUT.mkdir(parents=True, exist_ok=True)
                shot = OUT / f"{case_name}-{variant}.png"
                page.screenshot(path=str(shot), full_page=True, timeout=2000, animations="disabled")
                result["screenshot"] = str(shot)
            except Exception as exc:
                result["screenshot_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        browser.close()
    if variant == "good":
        result["benchmark_pass"] = result["observed"] == "PASS"
    else:
        # A seeded defect is detected only when the same contract fails on the mutant.
        result["benchmark_pass"] = result["observed"] == "FAIL"
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    results = []
    with sync_playwright() as playwright:
        for case_name, case in CASES.items():
            results.append(run_variant(playwright, case_name, "good", case["good"]))
            results.append(run_variant(playwright, case_name, "mutant", case["mutant"]))
    passed = sum(bool(item["benchmark_pass"]) for item in results)
    failed = len(results) - passed
    report = {
        "title": "CYDRA seeded-defect detection benchmark",
        "started_at_utc": started,
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"platform": platform.platform(), "python": sys.version.split()[0], "browser": "Chromium"},
        "method": "For each contract, the same executable assertion is run against a known-good fixture and a deliberately defective mutant. Good fixtures must pass; mutants must fail the assertion.",
        "summary": {"total_variants": len(results), "passed_expectations": passed, "failed_expectations": failed,
                    "good_fixtures": len(CASES), "seeded_mutants": len(CASES),
                    "mutants_detected": sum(item["variant"] == "mutant" and item["observed"] == "FAIL" for item in results)},
        "cases": [{"name": name, "description": case["description"]} for name, case in CASES.items()],
        "results": results,
        "limitations": [
            "This is a controlled benchmark of the browser assertion harness, not proof of autonomous AI-generated test discovery.",
            "Mutants are deliberately seeded and known in advance; results must not be described as real customer defects.",
            "A passing benchmark validates these four contracts only."
        ]
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# CYDRA Seeded-Defect Detection Benchmark", "",
        f"**Result:** {'PASS' if failed == 0 else 'FAIL'}",
        f"**Expected outcomes:** {passed}/{len(results)}",
        f"**Seeded mutants detected:** {report['summary']['mutants_detected']}/{len(CASES)}", "",
        report["method"], "", "## Results", "",
        "| Contract | Variant | Observed | Benchmark | Assertion |",
        "|---|---|---|---|---|"
    ]
    for item in results:
        lines.append(f"| {item['case']} | {item['variant']} | {item['observed']} | {'PASS' if item['benchmark_pass'] else 'FAIL'} | {item['assertion'].replace('|', '\\|')} |")
    lines += ["", "## Limitations", *[f"- {item}" for item in report["limitations"]], ""]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
