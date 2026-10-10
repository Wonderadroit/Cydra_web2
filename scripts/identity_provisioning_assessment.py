"""Read-only browser assessment of a target's sign-in/registration affordances."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from cydra_web2.identity_provisioning import classify_auth_options


def main() -> None:
    target_url = os.environ.get("CYDRA_TARGET_URL", "https://app.aurory.io").strip()
    auth_url = os.environ.get("CYDRA_AUTH_URL", target_url).strip()
    parsed = urlsplit(target_url)
    auth = urlsplit(auth_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("CYDRA_TARGET_URL must be an explicit HTTPS URL")
    if auth.scheme != "https" or not auth.hostname:
        raise ValueError("CYDRA_AUTH_URL must be an explicit HTTPS URL")
    if auth.hostname != parsed.hostname and os.environ.get("CYDRA_ALLOW_EXTERNAL_AUTH_ORIGIN") != "1":
        raise ValueError("Authentication URL is cross-origin; set CYDRA_ALLOW_EXTERNAL_AUTH_ORIGIN=1 only after scope review")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(auth_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        items = page.locator("a,button,[role=button],input[type=submit]").evaluate_all(
            """els => els.map(el => ({
                label: (el.innerText || el.getAttribute('aria-label') ||
                        el.getAttribute('title') || el.value || '').trim().slice(0, 120),
                href: el.getAttribute('href') || ''
            })).filter(x => x.label || x.href).slice(0, 150)"""
        )
        title = page.title()[:200]
        browser.close()

    result = classify_auth_options(items, auth_url)
    result.update({
        "target_url": target_url,
        "auth_url": auth_url,
        "page_title": title,
        "observation_count": len(items),
        "account_created": False,
        "mode": "read_only_discovery",
    })
    out = Path(os.environ.get("CYDRA_IDENTITY_REPORT", "artifacts/identity-provisioning-assessment.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
