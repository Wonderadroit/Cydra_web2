from scripts.browser_public_origin_discovery import classify_origin_scope


def test_target_host_is_approved_only_by_exact_hostname():
    assert classify_origin_scope("https://app.example/api", {"app.example"})["classification"] == "approved"
    assert classify_origin_scope("https://app.example.evil.test/api", {"app.example"})["classification"] == "unapproved"


def test_observed_external_host_is_not_implicitly_approved():
    result = classify_origin_scope("https://api.example/api", {"app.example"})
    assert result["classification"] == "unapproved"
    assert "does not grant scope" in result["reason"]


def test_non_https_origin_is_blocked_even_if_hostname_is_listed():
    result = classify_origin_scope("http://app.example/api", {"app.example"})
    assert result["classification"] == "blocked"


def test_explicitly_approved_external_host_is_approved():
    assert classify_origin_scope("https://api.example/v1/items", {"app.example", "api.example"})["classification"] == "approved"
