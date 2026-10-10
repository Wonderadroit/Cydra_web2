from cydra_web2.adapter import TargetConfig, HttpAdapter, _NoRedirect
import urllib.request


def test_target_config_requires_absolute_url():
    try:
        TargetConfig.from_url("/relative")
    except ValueError:
        pass
    else:
        raise AssertionError("relative target must be rejected")


def test_adapter_starts_without_credentials():
    assert HttpAdapter(TargetConfig.from_url("https://authorized.example")).identities == {}


def test_identity_bound_requests_do_not_follow_redirects():
    handler = _NoRedirect()
    request = urllib.request.Request("https://authorized.example/private")
    result = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {"Location": "https://outside.example/collect"},
        "https://outside.example/collect",
    )
    assert result is None
