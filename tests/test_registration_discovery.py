from pathlib import Path
import importlib.util

MODULE = Path(__file__).parents[1] / "scripts" / "registration_discovery.py"
spec = importlib.util.spec_from_file_location("registration_discovery", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_registration_discovery_requires_https(tmp_path):
    try:
        module.discover("http://example.com", tmp_path / "report.json")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("HTTP targets must be rejected")


def test_registration_discovery_does_not_submit_forms():
    source = MODULE.read_text()
    assert ".click(" not in source
    assert ".fill(" not in source
    assert ".submit(" not in source
    assert "No forms submitted" in source



def test_registration_discovery_rejects_embedded_credentials(tmp_path):
    try:
        module.discover("https://user:secret@example.com", tmp_path / "report.json")
    except ValueError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("URLs with embedded credentials must be rejected")


def test_observed_urls_drop_query_and_fragment():
    observed = module._safe_observed_url("https://example.com/register?token=secret&next=%2Fhome#form")
    assert observed == "https://example.com/register"
    assert "secret" not in observed
    assert "#" not in observed



def test_observed_urls_drop_userinfo():
    observed = module._safe_observed_url("https://alice:secret@example.com:8443/register?token=secret")
    assert observed == "https://example.com:8443/register"
    assert "alice" not in observed
    assert "secret" not in observed



def test_origin_key_normalizes_default_https_port():
    assert module._origin_key("https://EXAMPLE.com/register") == module._origin_key("https://example.com:443/register")


def test_form_actions_are_origin_checked_and_failed_urls_sanitized():
    source = MODULE.read_text()
    assert 'action_origin = _origin_key(form["action"])' in source
    assert 'report["blocked_external_links"].append(_safe_observed_url(form["action"]))' in source
    assert 'report["visited"].append({"url": _safe_observed_url(normalized)' in source
