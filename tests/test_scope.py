from cydra_web2.scope import check_scope


def test_scope_accepts_exact_allowlisted_host():
    result = check_scope("https://app.aurory.io/profile", {"app.aurory.io"})
    assert result.allowed


def test_scope_rejects_hostname_prefix_confusion():
    result = check_scope("https://app.aurory.io.attacker.invalid/profile", {"app.aurory.io"})
    assert not result.allowed
    assert result.reason == "host outside allowlist"


def test_scope_rejects_unlisted_subdomain():
    result = check_scope("https://api.app.aurory.io/v1/profile", {"app.aurory.io"})
    assert not result.allowed


def test_scope_rejects_non_https_live_request():
    result = check_scope("http://app.aurory.io/profile", {"app.aurory.io"})
    assert not result.allowed
    assert result.reason == "scheme outside allowlist"
