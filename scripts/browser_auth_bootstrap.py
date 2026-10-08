from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright


def _fernet() -> Fernet:
    key = os.environ.get("CYDRA_AUTH_ENCRYPTION_KEY", "").strip()
    if not key:
        raise ValueError("CYDRA_AUTH_ENCRYPTION_KEY is required")
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise ValueError("CYDRA_AUTH_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_state(state_path: Path, output_path: Path) -> None:
    plaintext = state_path.read_bytes()
    token = _fernet().encrypt(plaintext)
    output_path.write_bytes(token)


def decrypt_state(bundle_path: Path, output_path: Path) -> None:
    plaintext = _fernet().decrypt(bundle_path.read_bytes())
    json.loads(plaintext.decode("utf-8"))
    output_path.write_bytes(plaintext)


def _self_test() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Set-Cookie", "cydra_test=authenticated; HttpOnly")
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<title>CYDRA auth smoke</title><h1>authenticated</h1>")
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
            context.storage_state(path=state, indexed_db=True)
            context.close()

            decrypt_context = browser.new_context(storage_state=str(state))
            cookies = decrypt_context.cookies()
            assert any(c["name"] == "cydra_test" and c["value"] == "authenticated" for c in cookies)
            decrypt_context.close()
            browser.close()

        encrypt_state(state, bundle)
        decrypt_state(bundle, restored)
        assert json.loads(restored.read_text()) == json.loads(state.read_text())

    server.shutdown()
    print("browser-auth self-test: PASS (storage state + encryption + restore)")


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

    # Phase 1: normal, non-automated browser. Do not attach Playwright/CDP here.
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
        print("Google authentication is completed before CYDRA attaches automation.")
        print(f"Target: {target}")
        print(f"Authentication page: {auth_url}")
        print(f"Identity: {identity}")
        print("Complete the site's normal sign-in/authentication flow in the remote browser.")
        print(f"Waiting up to {wait_seconds} seconds before capturing browser state.")
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            time.sleep(5)
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=15)
        except subprocess.TimeoutExpired:
            chrome.kill()

    # Phase 2: verify the resulting browser state before exporting it.
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile_dir), headless=True, viewport={"width": 1440, "height": 900})
        if header_value:
            context.set_extra_http_headers({header_name: header_value})
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(target, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        cookies = context.cookies()
        names = sorted({x["name"] for x in cookies})
        auth_names = [n for n in names if any(k in n.lower() for k in ("auth", "session", "sess", "token", "sid", "jwt", "user"))]
        try:
            storage = page.evaluate("() => ({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})")
            storage_keys = sorted(set(storage["local"] + storage["session"]))
        except Exception:
            storage_keys = []
        auth_storage = [n for n in storage_keys if any(k in n.lower() for k in ("auth", "session", "sess", "token", "sid", "jwt", "user", "account"))]
        base = target.rstrip("/")
        verification_paths = ("/profile", "/profile/inventory")
        route_checks = []
        for path in verification_paths:
            try:
                probe = context.request.get(base + path, timeout=15000, headers={header_name: header_value} if header_value else None)
                text_body = (probe.text() or "").lower()
                route_checks.append({
                    "path": path,
                    "status": probe.status,
                    "final_url": probe.url,
                    "login_surface": any(k in text_body for k in ("sign in to aurory", "log in to aurory", "sign in", "log in")),
                })
            except Exception as exc:
                route_checks.append({"path": path, "error": type(exc).__name__})

        # Provider cookies/storage are supporting evidence only. The decisive
        # signal is a successful read-only request to an application API surface.
        # Aurory's HTML profile routes can legitimately render the login shell even
        # when the browser has completed the FusionAuth flow, so HTML-only checks
        # falsely rejected real sessions.
        api_paths = (
            "/v1/me",
            "/v1/inventories",
            "/v1/avatars",
            "/v1/player-avatar-inventory",
            "/v1/player-matches",
            "/v1/notifications",
            "/v2/inventories",
            "/v2/players",
        )
        api_checks = []
        observed_api_requests = []

        def record_request(request):
            try:
                parsed = request.url.split("?", 1)[0]
                if any(parsed.endswith(path) or f"{path}/" in parsed for path in api_paths):
                    observed_api_requests.append({
                        "method": request.method,
                        "url": parsed,
                    })
            except Exception:
                pass

        page.on("request", record_request)
        try:
            page.reload(wait_until="networkidle", timeout=30000)
        except Exception:
            try:
                page.reload(wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
        page.wait_for_timeout(1500)

        for path in api_paths:
            try:
                probe = context.request.get(
                    base + path,
                    timeout=15000,
                    headers={header_name: header_value} if header_value else None,
                )
                text_body = (probe.text() or "").lower()
                login_surface = any(
                    k in text_body
                    for k in (
                        "sign in to aurory",
                        "log in to aurory",
                        "sign in",
                        "log in",
                        "unauthorized",
                    )
                )
                api_checks.append({
                    "path": path,
                    "status": probe.status,
                    "final_url": probe.url,
                    "login_surface": login_surface,
                })
            except Exception as exc:
                api_checks.append({"path": path, "error": type(exc).__name__})

        try:
            body = page.locator("body").inner_text(timeout=3000).lower()
        except Exception:
            body = ""
        signed_in_ui = any(k in body for k in ("sign out", "log out", "logout", "disconnect", "my account"))
        api_auth_ok = any(
            x.get("status", 0) in range(200, 300)
            and not x.get("login_surface", True)
            for x in api_checks
        )
        confirmed = bool(api_auth_ok and (auth_names or auth_storage or signed_in_ui))
        print("AUTHENTICATION EVIDENCE: " + json.dumps({
            "confirmed": confirmed,
            "url": page.url,
            "title": page.title(),
            "auth_cookie_names": auth_names,
            "auth_storage_keys": auth_storage,
            "signed_in_ui": signed_in_ui,
            "protected_route_ok": protected_route_ok,
            "route_checks": route_checks,
            "api_checks": api_checks,
            "observed_api_requests": observed_api_requests,
        }, sort_keys=True))
        if not confirmed:
            context.close()
            raise RuntimeError("AUTHENTICATION_NOT_CONFIRMED: application session was not proven on a protected in-scope route; encrypted state was not created")
        context.storage_state(path=state, indexed_db=True)
        context.close()

    encrypt_state(state, bundle)
    state.unlink()
    subprocess.run(["rm", "-rf", str(profile_dir)], check=True)
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
