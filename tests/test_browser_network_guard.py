from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

from cydra_web2.browser_safety import browser_request_allowed, safe_observed_url


class _Handler(BaseHTTPRequestHandler):
    second_port = 0
    requests_seen: list[tuple[str, str]] = []

    def do_GET(self):
        type(self).requests_seen.append(("GET", self.path))
        if self.path == "/":
            body = b"""<!doctype html><script>
            fetch('/mutate', {method: 'POST'}).catch(() => {});
            fetch('http://127.0.0.1:PORT/cross-origin', {mode: 'no-cors'}).catch(() => {});
            </script><p>local guard test</p>""".replace(b"PORT", str(type(self).second_port).encode())
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        type(self).requests_seen.append(("POST", self.path))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args):
        pass


@pytest.mark.browser
def test_playwright_context_blocks_mutations_and_cross_origin_before_send():
    _Handler.requests_seen = []
    first = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    second = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    first_thread = threading.Thread(target=first.serve_forever, daemon=True)
    second_thread = threading.Thread(target=second.serve_forever, daemon=True)
    first_thread.start()
    second_thread.start()
    _Handler.second_port = second.server_port
    target = f"http://127.0.0.1:{first.server_port}"
    external = f"http://127.0.0.1:{second.server_port}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(service_workers="block")
            blocked = {"cross_origin": 0, "mutating": 0}

            def guard(route):
                request = route.request
                if not browser_request_allowed(request.url, request.method, target):
                    if safe_observed_url(request.url, target) is None:
                        blocked["cross_origin"] += 1
                    else:
                        blocked["mutating"] += 1
                    route.abort("blockedbyclient")
                    return
                route.continue_()

            context.route("**/*", guard)
            page = context.new_page()
            page.goto(target, wait_until="domcontentloaded")
            page.wait_for_timeout(300)
            assert ("GET", "/") in _Handler.requests_seen
            assert ("POST", "/mutate") not in _Handler.requests_seen
            assert not any(path == "/cross-origin" for method, path in _Handler.requests_seen)
            assert blocked["mutating"] >= 1
            assert blocked["cross_origin"] >= 1
            context.close()
            browser.close()
    finally:
        first.shutdown()
        second.shutdown()
        first.server_close()
        second.server_close()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)
