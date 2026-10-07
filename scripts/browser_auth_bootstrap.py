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
    identity = os.environ.get("CYDRA_AUTH_IDENTITY", "").strip()
    wait_seconds = int(os.environ.get("CYDRA_AUTH_WAIT_SECONDS", "900"))
    if not target:
        raise ValueError("CYDRA_TARGET_URL is required")
    if not identity:
        raise ValueError("CYDRA_AUTH_IDENTITY is required")
    _fernet()

    out = Path("artifacts/browser-auth")
    out.mkdir(parents=True, exist_ok=True)
    state = out / f"{identity}.json"
    bundle = out / f"{identity}.encrypted"

    header_name = "X-Bug-Bounty"
    header_value = os.environ.get("CYDRA_BUG_BOUNTY_HEADER", "").strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel=os.environ.get("CYDRA_BROWSER_CHANNEL", "chrome"),
            headless=False,
            args=["--start-maximized"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        if header_value:
            context.set_extra_http_headers({header_name: header_value})
        page = context.new_page()
        page.goto(target, wait_until="domcontentloaded")
        print("INTERACTIVE AUTHENTICATION READY")
        print("Use the remote browser shown by the workflow to sign in normally.")
        print(f"Target: {target}")
        print(f"Identity: {identity}")
        print(f"Waiting up to {wait_seconds} seconds before capturing browser state.")
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            time.sleep(5)

        context.storage_state(path=state, indexed_db=True)
        browser.close()

    # Never print or upload the plaintext state.
    encrypt_state(state, bundle)
    state.unlink()
    print(f"Encrypted authentication state created for identity '{identity}'.")
    print(f"Artifact file: {bundle}")


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
