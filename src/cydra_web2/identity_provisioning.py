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
    "x": ("continue with x", "twitter"),
    "facebook": ("facebook",),
    "wallet": ("wallet", "connect wallet", "phantom", "metamask", "solana"),
    "email": ("email", "e-mail", "password", "sign up", "create account", "register"),
}


def classify_auth_options(items: list[dict], target_url: str) -> dict:
    """Classify observed login links/buttons and decide the safe next action."""
    target = urlsplit(target_url)
    methods = set()
    observations = []
    for item in items:
        label = re.sub(r"\s+", " ", str(item.get("label", "")).strip().lower())
        href = str(item.get("href", "")).strip()
        resolved = urlsplit(urljoin(target_url, href)) if href else None
        text = f"{label} {resolved.hostname.lower() if resolved and resolved.hostname else ''}"
        matches = [name for name, needles in PROVIDERS.items() if any(n in text for n in needles)]
        if not matches:
            continue
        methods.update(matches)
        observations.append({
            "label": label[:120],
            "method_candidates": sorted(matches),
            "same_target_origin": bool(
                resolved and resolved.scheme == target.scheme and resolved.netloc == target.netloc
            ),
        })
    methods = sorted(methods)
    return {
        "target_origin": f"{target.scheme}://{target.netloc}",
        "methods": methods,
        "observations": observations,
        "autonomous_account_creation_supported": False,
        "next_action": (
            "operator_sign_in_required" if any(x in methods for x in ("google", "discord", "x", "facebook", "wallet"))
            else "inspect_registration_form" if "email" in methods
            else "no_supported_auth_method_detected"
        ),
        "reason": "Discovery is read-only. External identity verification and account creation must use authorized provider flows.",
    }
