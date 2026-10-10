"""Read-only assessment of target-supported account/authentication options.

This module discovers UI affordances; it does not create third-party accounts, bypass
CAPTCHAs, or submit credentials. Provider verification remains user-controlled.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

PROVIDERS = {
    "google": ("google",),
    "discord": ("discord",),
    "x": ("continue with x", "twitter", "x.com"),
    "facebook": ("facebook",),
    "wallet": ("wallet", "connect wallet", "phantom", "metamask", "solana"),
    "registration": ("sign up", "create account", "register", "registration"),
    "email": ("email", "e-mail", "password", "email address"),
}


def classify_auth_options(items: list[dict], target_url: str) -> dict:
    """Classify observed login links/controls and decide the safe next action."""
    target = urlsplit(target_url)
    target_port = target.port or (443 if target.scheme.lower() == "https" else 80)
    methods = set()
    observations = []
    for item in items:
        label = re.sub(r"\\s+", " ", str(item.get("label", "")).strip().lower())
        placeholder = str(item.get("placeholder", "")).strip().lower()
        control_type = str(item.get("type", "")).strip().lower()
        name = str(item.get("name", "")).strip().lower()
        href = str(item.get("href", "")).strip()
        resolved = urlsplit(urljoin(target_url, href)) if href else None
        text = f"{label} {placeholder} {name} {control_type} {resolved.hostname.lower() if resolved and resolved.hostname else ''} {resolved.path.lower() if resolved else ''}"
        matches = [provider for provider, needles in PROVIDERS.items() if any(n in text for n in needles)]
        if control_type == "email":
            matches.append("email")
        matches = sorted(set(matches))
        if not matches:
            continue
        methods.update(matches)
        same_origin = False
        destination_origin = None
        destination_path = None
        if resolved and resolved.scheme in {"http", "https"} and resolved.hostname:
            port = resolved.port or (443 if resolved.scheme.lower() == "https" else 80)
            same_origin = (
                resolved.scheme.lower() == target.scheme.lower()
                and resolved.hostname.lower().rstrip(".") == (target.hostname or "").lower().rstrip(".")
                and port == target_port
            )
            destination_origin = f"{resolved.scheme.lower()}://{resolved.hostname.lower()}"
            if port not in (80 if resolved.scheme.lower() == "http" else 443,):
                destination_origin += f":{port}"
            destination_path = resolved.path or "/"
        observations.append({
            "label": label[:120],
            "type": control_type[:40],
            "method_candidates": matches,
            "same_target_origin": same_origin,
            "destination_origin": destination_origin,
            "destination_path": destination_path,
        })
    methods = sorted(methods)
    has_provider = any(x in methods for x in ("google", "discord", "x", "facebook", "wallet"))
    has_registration = "registration" in methods
    return {
        "target_origin": f"{target.scheme}://{target.netloc}",
        "methods": methods,
        "registration_surface_detected": has_registration,
        "observations": observations,
        "autonomous_account_creation_supported": False,
        "next_action": (
            "operator_sign_in_required" if has_provider
            else "inspect_registration_form" if has_registration or "email" in methods
            else "no_supported_auth_method_detected"
        ),
        "reason": "Discovery is read-only. External identity verification and account creation must use authorized provider flows.",
    }
