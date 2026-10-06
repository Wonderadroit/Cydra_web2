from cydra_web2.artifact import dumps_artifact
from cydra_web2.redaction import redact


def test_redaction_recurses_through_nested_payloads():
    value = {"Authorization": "Bearer super-secret", "nested": [{"api_key": "key-secret", "safe": "ok"}]}
    assert redact(value) == {"Authorization": "[REDACTED]", "nested": [{"api_key": "[REDACTED]", "safe": "ok"}]}


def test_artifact_serialization_never_emits_known_secret_values():
    payload = {"headers": {"Authorization": "Bearer super-secret", "Cookie": "session=secret-cookie"}, "safe": "visible"}
    output = dumps_artifact(payload)
    assert "super-secret" not in output
    assert "secret-cookie" not in output
    assert "[REDACTED]" in output
    assert "visible" in output
