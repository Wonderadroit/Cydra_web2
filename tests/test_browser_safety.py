from cydra_web2.browser_safety import (
    browser_request_allowed,
    safe_observed_url,
    same_origin,
)


def test_same_origin_rejects_prefix_lookalikes_and_external_ports():
    target = "https://app.aurory.io"
    assert same_origin("https://app.aurory.io/profile", target)
    assert not same_origin("https://app.aurory.io.evil.test/profile", target)
    assert not same_origin("https://app.aurory.io@evil.test/profile", target)
    assert not same_origin("http://app.aurory.io/profile", target)
    assert not same_origin("https://app.aurory.io:8443/profile", target)


def test_same_origin_normalizes_host_case_and_default_ports():
    assert same_origin("https://APP.AURORY.IO/profile", "https://app.aurory.io")
    assert same_origin("https://app.aurory.io:443/profile", "https://app.aurory.io")


def test_safe_observed_url_drops_credentials_query_and_fragment():
    assert safe_observed_url(
        "https://user:pw@app.aurory.io/profile?access_token=secret#fragment",
        "https://app.aurory.io",
    ) == "https://app.aurory.io/profile"


def test_safe_observed_url_refuses_external_url():
    assert safe_observed_url("https://evil.test/?token=secret", "https://app.aurory.io") is None


def test_browser_request_policy_allows_only_same_origin_get_and_head():
    target = "https://app.aurory.io"
    assert browser_request_allowed(target + "/profile", "GET", target)
    assert browser_request_allowed(target + "/profile", "HEAD", target)
    for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
        assert not browser_request_allowed(target + "/profile", method, target)


def test_browser_request_policy_blocks_cross_origin_even_for_get():
    target = "https://app.aurory.io"
    assert not browser_request_allowed("https://cdn.aurory.io/app.js", "GET", target)
    assert not browser_request_allowed("https://evil.test/collect", "GET", target)
