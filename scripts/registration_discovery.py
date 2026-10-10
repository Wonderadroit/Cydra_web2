from __future__ import annotations

"""Discover public registration/authentication navigation without submitting forms.

This is a read-only reconnaissance step: it never clicks controls, fills fields,
submits forms, or attempts to bypass CAPTCHA/verification. It records rendered
controls because modern SPA login pages often expose no ordinary HTML links.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

REGISTER_WORDS = re.compile(r"register|sign[ -]?up|create account|join now|new account|create user", re.I)
AUTH_WORDS = re.compile(r"sign[ -]?in|log[ -]?in|auth|account|identity|continue with|google|discord|wallet", re.I)
SENSITIVE = re.compile(r"password|secret|token|email|phone|otp|code|captcha", re.I)


def _origin_key(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    return (parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port or default_port)


def _safe_observed_url(url: str) -> str:
    """Remove userinfo, query strings, and fragments from persisted observed URLs."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{host}:{port}" if port is not None else host
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, "", ""))


def _safe_label(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()[:100]
    if SENSITIVE.search(value):
        return "[redacted-sensitive-label]"
    return value


def discover(base_url: str, output: Path) -> dict:
    parsed = urlparse(base_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("target URL must be an absolute HTTPS URL without embedded credentials")
    from playwright.sync_api import sync_playwright

    origin = f"https://{parsed.hostname.lower()}" + (f":{parsed.port}" if parsed.port else "")
    target_origin = _origin_key(base_url)
    report = {
        "target_origin": origin,
        "visited": [],
        "registration_candidates": [],
        "forms": [],
        "rendered_controls": [],
        "blocked_external_links": [],
        "limitations": [
            "Read-only discovery does not click controls or submit forms.",
            "A JavaScript-only button may require a separate operator-reviewed navigation step.",
        ],
    }
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
            if _origin_key(normalized) != target_origin:
                report["blocked_external_links"].append(_safe_observed_url(normalized))
                continue
            seen.add(normalized)
            try:
                response = page.goto(normalized, wait_until="domcontentloaded", timeout=20000)
                try:
                    page.wait_for_load_state("networkidle", timeout=2500)
                except Exception:
                    pass
                page.wait_for_timeout(1200)
                if _origin_key(page.url) != target_origin:
                    report["blocked_external_links"].append(_safe_observed_url(page.url))
                    continue

                title = page.title()
                controls = page.locator(
                    "a[href], button, input[type=button], input[type=submit], "
                    "[role=button], [role=link], [data-testid]"
                ).evaluate_all("""els => els.map(e => {
                    const text = (e.innerText || e.getAttribute('aria-label') ||
                                  e.getAttribute('title') || e.getAttribute('placeholder') ||
                                  e.value || '').trim().slice(0, 100);
                    return {
                      tag: e.tagName.toLowerCase(),
                      role: e.getAttribute('role') || '',
                      text,
                      href: e.href || e.getAttribute('href') || '',
                      type: (e.type || '').toLowerCase(),
                      test_id: e.getAttribute('data-testid') || ''
                    };
                })""")
                safe_controls = []
                for control in controls:
                    label = _safe_label(control.get("text", ""))
                    href = control.get("href", "")
                    item = {
                        "tag": control.get("tag", ""),
                        "role": control.get("role", ""),
                        "label": label,
                        "type": control.get("type", ""),
                    }
                    if control.get("test_id"):
                        item["test_id"] = _safe_label(control["test_id"])
                    if href:
                        safe_href = _safe_observed_url(href) if urlparse(href).scheme in {"http", "https"} else ""
                        item["href"] = safe_href
                        if _origin_key(href) != target_origin:
                            report["blocked_external_links"].append(safe_href)
                        elif REGISTER_WORDS.search(label + " " + href):
                            report["registration_candidates"].append({"url": safe_href, "label": label or "registration link"})
                            if href not in seen and href not in queue:
                                queue.append(href)
                    if label or href or item.get("test_id"):
                        safe_controls.append(item)
                report["rendered_controls"].append({
                    "page": _safe_observed_url(normalized),
                    "controls": safe_controls[:100],
                })

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
                report["visited"].append({
                    "url": _safe_observed_url(normalized),
                    "status": response.status if response else None,
                    "title": title,
                })
                for form in forms:
                    action = form["action"]
                    if _origin_key(action) != target_origin:
                        report["blocked_external_links"].append(_safe_observed_url(action))
                        continue
                    labels = " ".join(f["label"] for f in form["fields"])
                    if REGISTER_WORDS.search(normalized + " " + title + " " + labels):
                        safe_fields = []
                        for field in form["fields"]:
                            item = dict(field)
                            if SENSITIVE.search(item["name"] + " " + item["label"]):
                                item["name"] = "[redacted-sensitive-field]"
                                item["label"] = "[redacted-sensitive-field]"
                            safe_fields.append(item)
                        report["forms"].append({
                            "page": _safe_observed_url(normalized),
                            "action": _safe_observed_url(action),
                            "method": form["method"],
                            "fields": safe_fields,
                        })
            except Exception as exc:
                report["visited"].append({"url": _safe_observed_url(normalized), "error": type(exc).__name__})
        browser.close()

    report["registration_candidates"] = list({
        (x["url"], x["label"]): x for x in report["registration_candidates"]
    }.values())
    report["blocked_external_links"] = sorted(set(x for x in report["blocked_external_links"] if x))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--output", default="artifacts/registration-discovery.json")
    args = parser.parse_args()
    report = discover(args.target_url, Path(args.output))
    print(json.dumps({
        "visited_count": len(report["visited"]),
        "registration_candidates": report["registration_candidates"],
        "form_count": len(report["forms"]),
        "rendered_control_count": sum(len(x["controls"]) for x in report["rendered_controls"]),
        "blocked_external_link_count": len(report["blocked_external_links"]),
    }, indent=2))
    print("Read-only discovery: no controls clicked, no forms submitted, no account created.")


if __name__ == "__main__":
    main()
