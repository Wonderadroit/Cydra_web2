from cydra_web2.identity_provisioning import classify_auth_options


def test_classifies_oauth_wallet_and_registration_without_claiming_account_created():
    result = classify_auth_options([
        {"label": "Continue with Google", "href": "/oauth/google"},
        {"label": "Connect Wallet", "href": "#wallet"},
        {"label": "Create account with email", "href": "/register"},
    ], "https://app.example.test")
    assert result["methods"] == ["email", "google", "registration", "wallet"]
    assert result["registration_surface_detected"] is True
    assert result["next_action"] == "operator_sign_in_required"
    assert result["autonomous_account_creation_supported"] is False


def test_unknown_auth_surface_fails_closed():
    result = classify_auth_options([{"label": "Play now", "href": "/play"}], "https://app.example.test")
    assert result["methods"] == []
    assert result["next_action"] == "no_supported_auth_method_detected"


def test_label_whitespace_is_normalized_before_classification():
    result = classify_auth_options([
        {"label": "  Continue   with\n Google  ", "href": "/oauth/google"},
    ], "https://app.example.test")
    assert result["methods"] == ["google"]
    assert result["observations"][0]["label"] == "continue with google"


def test_visible_text_normalization_collapses_real_whitespace():
    from cydra_web2.identity_provisioning import normalize_visible_text

    assert normalize_visible_text("  Inventory\n   Items\t  2  ") == "inventory items 2"
