from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from cydra_web2.adapter import TargetConfig

API_PATH = re.compile(r"^/(?:api(?:/|$)|graphql(?:/|$)|rpc(?:/|$)|v[0-9]+(?:/|$))", re.I)


def safe_url_parts(raw_url: str) -> tuple[str, str] | None:
    """Return origin and path only; never persist query strings or fragments."""
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    return origin, parsed.path or "/"


def is_api_path(path: str) -> bool:
    return API_PATH.match(path) is not None


def classify_origin_scope(origin: str, allowed_hosts: set[str]) -> dict:
    """Classify an observed origin without treating discovery as authorization."""
    try:
        parts = safe_url_parts(origin)
        parsed = urlsplit(origin)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        # Accessing .port validates malformed/out-of-range port values.
        _ = parsed.port
    except (TypeError, ValueError):
        parts = None
        parsed = None
        hostname = ""
    approved = {host.lower().rstrip(".") for host in allowed_hosts if host.strip()}
    if parts is None or parsed is None or parsed.scheme.lower() != "https":
        return {"origin": origin, "hostname": hostname or None, "classification": "blocked", "reason": "origin is not a valid HTTPS URL"}
    if hostname not in approved:
        return {"origin": origin, "hostname": hostname, "classification": "unapproved", "reason": "host is not in the explicit allowlist; observation does not grant scope"}
    return {"origin": origin, "hostname": hostname, "classification": "approved", "reason": "hostname exactly matches the explicit allowlist"}


def summarize_api_origins(requests: list[dict], target_host: str) -> dict:
    api_requests = [item for item in requests if is_api_path(item.get("path", ""))]
    external_origins = sorted({
        item["origin"] for item in api_requests
        if item.get("hostname") and item["hostname"].lower() != target_host.lower()
    })
    return {
        "api_requests": api_requests,
        "candidate_service_origins": external_origins,
        "same_origin_api_requests": [
            item for item in api_requests
            if item.get("hostname", "").lower() == target_host.lower()
        ],
    }


def main() -> int:
    target_url = os.environ.get("CYDRA_TARGET_URL", "").strip()
    if not target_url:
        raise ValueError("CYDRA_TARGET_URL is required")
    target = TargetConfig.from_url(target_url)
    parsed_target = urlsplit(target.base_url)
    if parsed_target.scheme.lower() != "https":
        raise ValueError("Passive browser origin discovery requires an HTTPS target")
    target_host = (parsed_target.hostname or "").lower()
    seed_path = os.environ.get("CYDRA_DISCOVERY_SEED_PATH", "/").strip() or "/"
    if not seed_path.startswith("/") or "://" in seed_path:
        raise ValueError("CYDRA_DISCOVERY_SEED_PATH must be a root-relative path")
    wait_ms = int(os.environ.get("CYDRA_BROWSER_WAIT_MS", "3000"))
    if not 0 <= wait_ms <= 10000:
        raise ValueError("CYDRA_BROWSER_WAIT_MS must be between 0 and 10000")
    page_url = urljoin(target.base_url + "/", seed_path.lstrip("/"))

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

    requests: list[dict] = []
    responses: list[dict] = []
    navigation_status = None
    navigation_error = None
    final_url = None
    page_title = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1365, "height": 900})
        page = context.new_page()
        page.set_default_timeout(10000)

        def on_request(request):
            parts = safe_url_parts(request.url)
            if parts is None:
                return
            origin, path = parts
            hostname = (urlsplit(origin).hostname or "").lower()
            if not is_api_path(path):
                return
            requests.append({
                "origin": origin,
                "hostname": hostname,
                "path": path,
                "method": request.method.upper(),
                "resource_type": request.resource_type,
                "first_party": hostname == target_host,
            })

        def on_response(response):
            parts = safe_url_parts(response.url)
            if parts is None:
                return
            origin, path = parts
            if not is_api_path(path):
                return
            hostname = (urlsplit(origin).hostname or "").lower()
            responses.append({
                "origin": origin,
                "hostname": hostname,
                "path": path,
                "method": response.request.method.upper(),
                "status_code": response.status,
                "content_type": response.headers.get("content-type", "").split(";", 1)[0],
                "first_party": hostname == target_host,
            })

        page.on("request", on_request)
        page.on("response", on_response)
        try:
            response = page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            navigation_status = response.status if response is not None else None
            if wait_ms:
                page.wait_for_timeout(wait_ms)
            final_url = page.url
            try:
                page_title = page.title()
            except Exception:
                page_title = None
        except PlaywrightTimeoutError as exc:
            navigation_error = f"navigation_timeout: {type(exc).__name__}"
            try:
                final_url = page.url
            except Exception:
                final_url = None
        except Exception as exc:
            navigation_error = f"navigation_error: {type(exc).__name__}"
            try:
                final_url = page.url
            except Exception:
                final_url = None
        finally:
            context.close()
            browser.close()

    # Collapse duplicate request events without discarding distinct methods,
    # origins, paths, resource types, or response statuses.
    request_keys = {}
    for item in requests:
        key = (item["origin"], item["path"], item["method"], item["resource_type"], item["first_party"])
        request_keys[key] = request_keys.get(key, 0) + 1
    request_rows = [
        {"origin": origin, "hostname": (urlsplit(origin).hostname or "").lower(), "path": path,
         "method": method, "resource_type": resource_type, "first_party": first_party, "count": count}
        for (origin, path, method, resource_type, first_party), count in sorted(request_keys.items())
    ]
    response_rows = sorted(responses, key=lambda item: (item["origin"], item["path"], item["method"], item["status_code"]))
    summary = summarize_api_origins(request_rows, target_host)
    # The target hostname is the only implicit allowlist entry. Additional
    # hosts must be explicitly supplied by the operator as hostnames, not URLs.
    configured_hosts = {
        host.strip().lower().rstrip(".")
        for host in os.environ.get("CYDRA_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    if any("/" in host or ":" in host or "@" in host for host in configured_hosts):
        raise ValueError("CYDRA_ALLOWED_HOSTS must contain hostnames only, comma-separated")
    allowed_hosts = configured_hosts | {target_host}
    origin_scope = [
        classify_origin_scope(origin, allowed_hosts)
        for origin in sorted({item["origin"] for item in summary["api_requests"]})
    ]
    output = {
        "target": target.base_url,
        "mode": "anonymous-passive-browser-origin-observation",
        "seed_url": page_url,
        "navigation_status": navigation_status,
        "navigation_error": navigation_error,
        "final_url": final_url,
        "page_title": page_title,
        "api_requests": summary["api_requests"],
        "api_responses": response_rows,
        "candidate_service_origins": summary["candidate_service_origins"],
        "origin_scope_classification": origin_scope,
        "explicit_allowed_hosts": sorted(allowed_hosts),
        "same_origin_api_requests": summary["same_origin_api_requests"],
        "limitations": [
            "This workflow observes browser-generated requests only; it does not replay, fuzz, or mutate API requests.",
            "Candidate service origins are observations, not proof of endpoint ownership or authorization.",
            "Origin scope classification is informational for the report; active requests must still pass the runtime target allowlist.",
            "Request query strings, fragments, headers, cookies, and bodies are not written to the artifact.",
            "Anonymous browser observations cannot establish user-resource ownership or prove an authorization flaw.",
        ],
        "next_step": (
            "Review the observed API-like origins against the in-scope host list and bundle-derived routes before any active testing."
            if summary["candidate_service_origins"]
            else "No cross-origin API-like requests were observed; verify the normal UI flow and any documented service-origin configuration before drawing conclusions."
        ),
    }
    output_path = Path(os.environ.get("CYDRA_ARTIFACT", "artifacts/public-browser-origin.json"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(
        "CYDRA passive browser origin observation complete: "
        f"api_requests={len(summary['api_requests'])} "
        f"api_responses={len(response_rows)} "
        f"candidate_service_origins={len(summary['candidate_service_origins'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())