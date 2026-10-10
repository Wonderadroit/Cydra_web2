from __future__ import annotations

"""Discover a site's public registration surface without submitting forms.

This deliberately does not create accounts, bypass CAPTCHA/verification, or submit
credentials. It produces a sanitized map for deciding whether a target supports
legitimate automated test-account provisioning.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse



REGISTER_WORDS = re.compile(r"register|sign[ -]?up|create account|join now|new account", re.I)
SENSITIVE = re.compile(r"password|secret|token|email|phone|otp|code|captcha", re.I)


def discover(base_url: str, output: Path) -> dict:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("target URL must be an absolute HTTPS URL")
    # Keep module import and non-browser guard tests usable in minimal CI jobs.
    # The browser dependency is required only after the target passes validation.
    from playwright.sync_api import sync_playwright

    origin = f"{parsed.scheme}://{parsed.netloc}"
    report = {"target_origin": origin, "visited": [], "registration_candidates": [], "forms": [], "blocked_external_links": []}
    queue = [base_url]
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        while queue and len(seen) < 12:
            url = queue.pop(0)
            normalized = url.split("#", 1)[0]
            if normalized in seen:
                continue
            if urlparse(normalized).netloc != parsed.netloc:
                report["blocked_external_links"].append(normalized)
                continue
            seen.add(normalized)
            try:
                response = page.goto(normalized, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(500)
                title = page.title()
                links = page.locator("a[href]").evaluate_all("""els => els.map(a => ({
                    text: (a.innerText || a.getAttribute('aria-label') || '').trim().slice(0,100),
                    href: a.href
                }))""")
                forms = page.locator("form").evaluate_all("""forms => forms.map(f => ({
                    action: f.action || location.href,
                    method: (f.method || 'get').toUpperCase(),
                    fields: Array.from(f.querySelectorAll('input,select,textarea,button')).map(e => ({
                        tag: e.tagName.toLowerCase(),
                        type: (e.type || '').toLowerCase(),
                        name: e.name || '',
                        label: (e.labels && Array.from(e.labels).map(x => x.innerText).join(' ')) ||
                               e.getAttribute('aria-label') || e.placeholder || '',
                        required: !!e.required
                    }))
                }))""")
                entry = {"url": normalized, "status": response.status if response else None, "title": title}
                report["visited"].append(entry)
                for link in links:
                    if REGISTER_WORDS.search(link["text"]):
                        candidate = {"url": link["href"], "label": link["text"]}
                        if urlparse(link["href"]).netloc == parsed.netloc:
                            report["registration_candidates"].append(candidate)
                            if link["href"] not in seen and link["href"] not in queue:
                                queue.append(link["href"])
                        else:
                            report["blocked_external_links"].append(link["href"])
                for form in forms:
                    if REGISTER_WORDS.search(normalized + " " + title + " " + " ".join(f["label"] for f in form["fields"])):
                        safe_fields = []
                        for field in form["fields"]:
                            item = dict(field)
                            # Never record input values; sensitive labels are kept as field types only.
                            if SENSITIVE.search(item["name"] + " " + item["label"]):
                                item["label"] = "[redacted-sensitive-field]"
                            safe_fields.append(item)
                        report["forms"].append({"page": normalized, "action": form["action"], "method": form["method"], "fields": safe_fields})
            except Exception as exc:
                report["visited"].append({"url": normalized, "error": type(exc).__name__})
        browser.close()
    report["registration_candidates"] = list({(x["url"], x["label"]): x for x in report["registration_candidates"]}.values())
    report["blocked_external_links"] = sorted(set(report["blocked_external_links"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--output", default="artifacts/registration-discovery.json")
    args = parser.parse_args()
    report = discover(args.target_url, Path(args.output))
    print(json.dumps({"visited_count": len(report["visited"]), "registration_candidates": report["registration_candidates"], "form_count": len(report["forms"]), "blocked_external_link_count": len(report["blocked_external_links"])}, indent=2))
    print("No forms submitted; no account was created.")


if __name__ == "__main__":
    main()
