from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from cydra_web2.adapter import HttpAdapter, IdentitySession, TargetConfig
from cydra_web2.bola_probe import run_read_only_bola_probe


OUT = Path(os.environ.get("CYDRA_BOLA_OUT", "artifacts/bola-read-only-probe/report.json"))


def _headers(name: str) -> dict[str, str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        raise ValueError(f"{name} secret is required")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must contain a JSON object of request headers") from exc
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{name} must contain a non-empty JSON object of request headers")
    if any(not isinstance(key, str) or not key.strip() or not isinstance(item, str) for key, item in value.items()):
        raise ValueError(f"{name} must contain string header names and values")
    return {key.strip(): item for key, item in value.items()}


def main() -> int:
    target_url = os.environ.get("CYDRA_BOLA_TARGET_URL", "").strip()
    path = os.environ.get("CYDRA_BOLA_RESOURCE_PATH", "").strip()
    marker = os.environ.get("CYDRA_BOLA_RESOURCE_MARKER", "")
    owner_confirmed = os.environ.get("CYDRA_BOLA_OWNER_CONTROL_CONFIRMED", "").lower() == "true"
    report = None
    try:
        parsed = urlsplit(target_url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("target URL must be an absolute HTTPS origin or base URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("target URL must not contain credentials, query parameters, or a fragment")
        if not path.startswith("/") or "\r" in path or "\n" in path:
            raise ValueError("resource path must begin with / and contain no line breaks")
        if not owner_confirmed:
            raise PermissionError("owner-control confirmation is required")

        target = TargetConfig.from_url(target_url)
        identities = (
            IdentitySession("owner", _headers("CYDRA_BOLA_OWNER_HEADERS_JSON")),
            IdentitySession("comparison", _headers("CYDRA_BOLA_COMPARISON_HEADERS_JSON")),
        )
        adapter = HttpAdapter(target, identities)
        report = run_read_only_bola_probe(
            adapter,
            path=path,
            resource_marker=marker,
            owner_identity="owner",
            comparison_identity="comparison",
            owner_control_confirmed=owner_confirmed,
            runs=2,
        )
        report["target_origin"] = f"{parsed.scheme.lower()}://{parsed.netloc}"
        exit_code = 0
    except Exception as exc:
        # Do not serialize exception messages, request headers, response bodies,
        # cookies, or the marker: these can contain credentials or target data.
        report = {
            "title": "CYDRA read-only BOLA differential probe",
            "status": "inconclusive",
            "target_origin": (
                f"{urlsplit(target_url).scheme.lower()}://{urlsplit(target_url).netloc}"
                if urlsplit(target_url).hostname else None
            ),
            "failure_type": type(exc).__name__,
            "rationale": "Probe did not complete. Check workflow inputs, the two operator-supplied identity header secrets, target scope, and connectivity.",
            "limitations": [
                "No vulnerability conclusion can be drawn from an incomplete probe.",
                "Sensitive headers, response bodies, and resource marker values are not written to the report.",
            ],
        }
        exit_code = 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"CYDRA read-only BOLA probe: status={report['status']} output={OUT}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
