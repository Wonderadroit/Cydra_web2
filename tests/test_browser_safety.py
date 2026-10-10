from cydra_web2.browser_safety import safe_observed_url, same_origin


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
