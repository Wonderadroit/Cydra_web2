from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright


LOGIN_MARKERS = (
    "sign in",
    "log in",
    "login",
    "authenticate",
    "unauthorized",
    "session expired",
)

AUTH_KEYWORDS = (
    "auth",
    "session",
    "sess",
    "token",
    "sid",
    "jwt",
    "user",
    "account",
)

STATIC_TYPES = {"document", "stylesheet", "image", "font", "media", "manifest", "texttrack"}


def _fernet() -> Fernet:
    key = os.environ.get("CYDRA_AUTH_ENCRYPTION_KEY", "").strip()
    if not key:
        raise ValueError("CYDRA_AUTH_ENCRYPTION_KEY is required")
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise ValueError("CYDRA_AUTH_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_state(state_path: Path, output_path: Path) -> None:
    output_path.write_bytes(_fernet().encrypt(state_path.read_bytes()))


def decrypt_state(bundle_path: Path, output_path: Path) -> None:
    plaintext = _fernet().decrypt(bundle_path.read_bytes())
    json.loads(plaintext.decode("utf-8"))
    output_path.write_bytes(plaintext)


def _login_surface(text: str) -> bool:
    body = (text or "").lower()
    return any(marker in body for marker in LOGIN_MARKERS)


def _auth_names(names: list[str]) -> list[str]:
    return sorted({name for name in names if any(k in name.lower() for k in AUTH_KEYWORDS)})


def _verification_paths(target: str) -> list[str]:
    raw = os.environ.get("CYDRA_AUTH_VERIFY_PATHS", "").strip()
    if not raw:
        return ["/"]
    result = []
    for item in raw.split(","):
        path = item.strip()
        if not path:
            continue
        if not path.startswith("/"):
            path = "/" + path
        result.append(path)
    return result or ["/"]


def _self_test() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Set-Cookie", "cydra_test=authenticated; HttpOnly")
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<title>CYDRA auth smoke</title><h1>authenticated</h1>")
            elif self.path == "/protected":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"authenticated":true}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *_args):
            pass

    key = Fernet.generate_key().decode()
    os.environ["CYDRA_AUTH_ENCRYPTION_KEY"] = key
    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port

    import threading
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        state = tmp_path / "state.json"
        bundle = tmp_path / "state.enc"
        restored = tmp_path / "restored.json"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
            assert page.title() == "CYDRA auth smoke"
            assert not _login_surface(page.locator("body").inner_text())
            context.storage_state(path=state, indexed_db=True)
            context.close()

            restored_context = browser.new_context(storage_state=str(state))
            cookies = restored_context.cookies()
            assert any(c["name"] == "cydra_test" and c["value"] == "authenticated" for c in cookies)
            restored_context.close()
            browser.close()

        encrypt_state(state, bundle)
        decrypt_state(bundle, restored)
        assert json.loads(restored.read_text()) == json.loads(state.read_text())

    server.shutdown()
    print("browser-auth self-test: PASS (storage state + encryption + restore + auth checks)")


def _bootstrap() -> None:
    target = os.environ.get("CYDRA_TARGET_URL", "").strip()
    auth_url = os.environ.get("CYDRA_AUTH_URL", "").strip() or target
    identity = os.environ.get("CYDRA_AUTH_IDENTITY", "").strip()
    wait_seconds = int(os.environ.get("CYDRA_AUTH_WAIT_SECONDS", "900"))
    if not target:
        raise ValueError("CYDRA_TARGET_URL is required")
    if not auth_url:
        raise ValueError("CYDRA_AUTH_URL or CYDRA_TARGET_URL is required")
    if not identity:
        raise ValueError("CYDRA_AUTH_IDENTITY is required")
    _fernet()

    out = Path("artifacts/browser-auth")
    out.mkdir(parents=True, exist_ok=True)
    state = out / f"{identity}.json"
    bundle = out / f"{identity}.encrypted"

    header_name = "X-Bug-Bounty"
    header_value = os.environ.get("CYDRA_BUG_BOUNTY_HEADER", "").strip()

    profile_dir = Path(tempfile.mkdtemp(prefix="cydra-chrome-profile-"))
    chrome_candidates = [
        os.environ.get("CYDRA_CHROME_BINARY", "").strip(),
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    chrome_binary = next((x for x in chrome_candidates if x and Path(x).exists()), None)
    if not chrome_binary:
        raise RuntimeError("No supported Chrome/Chromium binary found")

    chrome = subprocess.Popen(
        [
            chrome_binary,
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
            auth_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print("INTERACTIVE AUTHENTICATION READY")
        print("A normal browser process is open directly on the authentication page.")
        print("Complete the site's normal sign-in/authentication flow in the remote browser.")
        print(f"Target: {target}")
        print(f"Authentication page: {auth_url}")
        print(f"Identity: {identity}")
        print(f"Waiting up to {wait_seconds} seconds before verification.")
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            time.sleep(5)
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=15)
        except subprocess.TimeoutExpired:
            chrome.kill()

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=True,
                viewport={"width": 1440, "height": 900},
            )
            if header_value:
                context.set_extra_http_headers({header_name: header_value})

            page = context.pages[0] if context.pages else context.new_page()
            observed_api_requests = []
            observed_api_responses = []

            def record_request(request):
                try:
                    if request.resource_type in STATIC_TYPES:
                        return
                    parsed = urlparse(request.url)
                    target_origin = urlparse(target)
                    if parsed.scheme == target_origin.scheme and parsed.netloc == target_origin.netloc:
                        observed_api_requests.append({
                            "method": request.method,
                            "url": request.url.split("?", 1)[0],
                            "resource_type": request.resource_type,
                        })
                except Exception:
                    pass

            def record_response(response):
                try:
                    request = response.request
                    if request.resource_type in STATIC_TYPES:
                        return
                    parsed = urlparse(response.url)
                    target_origin = urlparse(target)
                    if parsed.scheme == target_origin.scheme and parsed.netloc == target_origin.netloc:
                        observed_api_responses.append({
                            "status": response.status,
                            "url": response.url.split("?", 1)[0],
                            "resource_type": request.resource_type,
                        })
                except Exception:
                    pass

            page.on("request", record_request)
            page.on("response", record_response)

            # Re-enter the configured authentication URL using the persisted
            # profile. This lets SSO/FusionAuth complete any pending redirect
            # and, importantly, gives the verifier a fresh application request
            # rather than relying on stale cookies alone.
            try:
                page.goto(auth_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2500)
            except Exception as exc:
                print(f"AUTH VERIFICATION: auth_url navigation warning: {type(exc).__name__}: {exc}")

            verification_paths = _verification_paths(target)
            route_checks = []
            for path in verification_paths:
                url = target.rstrip("/") + path
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    body = page.locator("body").inner_text(timeout=5000)
                    route_checks.append({
                        "path": path,
                        "status": response.status if response else None,
                        "final_url": page.url,
                        "login_surface": _login_surface(body),
                        "title": page.title(),
                    })
                    page.wait_for_timeout(1200)
                except Exception as exc:
                    route_checks.append({
                        "path": path,
                        "error": type(exc).__name__,
                    })

            cookies = context.cookies()
            cookie_names = sorted({x["name"] for x in cookies})
            auth_cookies = _auth_names(cookie_names)

            try:
                storage = page.evaluate(
                    "() => ({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})"
                )
                storage_keys = sorted(set(storage["local"] + storage["session"]))
            except Exception:
                storage_keys = []
            auth_storage = _auth_names(storage_keys)

            try:
                body = page.locator("body").inner_text(timeout=3000)
            except Exception:
                body = ""
            signed_in_ui = not _login_surface(body) and any(
                marker in body.lower()
                for marker in ("sign out", "log out", "logout", "disconnect", "my account")
            )

            target_responses = [
                x for x in observed_api_responses
                if 200 <= x.get("status", 0) < 300 and x.get("resource_type") in {"xhr", "fetch"}
            ]
            route_ok = any(
                x.get("status", 0) < 400 and not x.get("login_surface", True)
                for x in route_checks
            )
            # A real application session needs at least one application-level
            # signal. Cookies/storage are supporting evidence; a provider cookie
            # by itself is never enough. A successful XHR/fetch observed while
            # loading the configured verification route is the strongest generic
            # signal because it does not assume an API hostname or endpoint shape.
            application_signal = bool(target_responses or route_ok or signed_in_ui)
            confirmed = bool(application_signal and (auth_cookies or auth_storage or signed_in_ui))

            evidence = {
                "confirmed": confirmed,
                "url": page.url,
                "title": page.title(),
                "auth_cookie_names": auth_cookies,
                "auth_storage_keys": auth_storage,
                "signed_in_ui": signed_in_ui,
                "verification_paths": verification_paths,
                "route_checks": route_checks,
                "observed_api_requests": observed_api_requests[-50:],
                "observed_api_responses": observed_api_responses[-50:],
                "successful_application_requests": target_responses[-20:],
            }
            print("AUTHENTICATION EVIDENCE: " + json.dumps(evidence, sort_keys=True))

            if not confirmed:
                context.close()
                raise RuntimeError(
                    "AUTHENTICATION_NOT_CONFIRMED: no application-level authenticated signal was proven; "
                    "encrypted state was not created. Check the remote browser sign-in and "
                    "CYDRA_AUTH_VERIFY_PATHS."
                )

            context.storage_state(path=state, indexed_db=True)
            context.close()
    finally:
        subprocess.run(["rm", "-rf", str(profile_dir)], check=True)

    encrypt_state(state, bundle)
    state.unlink()
    print(f"Encrypted authentication state created for identity '{identity}'.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--bootstrap", action="store_true")
    args = parser.parse_args()
    if args.self_test == args.bootstrap:
        raise SystemExit("choose exactly one of --self-test or --bootstrap")
    if args.self_test:
        _self_test()
    else:
        _bootstrap()


if __name__ == "__main__":
    main()
