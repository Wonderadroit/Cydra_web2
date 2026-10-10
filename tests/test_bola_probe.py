import hashlib
import json
from types import SimpleNamespace

import pytest

from cydra_web2.bola_probe import run_read_only_bola_probe


MARKER = "owned-secret-marker-xyz"


def response(identity_id, status, body, method="GET"):
    return SimpleNamespace(
        identity_id=identity_id,
        status_code=status,
        body=body,
        body_sha256=hashlib.sha256(body.encode()).hexdigest(),
        method=method,
    )


class FakeAdapter:
    def __init__(self, mode):
        self.mode = mode
        self.calls = []

    def request(self, *, method, path, identity_id):
        self.calls.append((method, path, identity_id))
        if method != "GET":
            raise AssertionError("BOLA probe must be read-only")
        if identity_id == "owner":
            return response(identity_id, 200, '{"record":{"id":"42","secret":"owned-secret-marker-xyz"}}')
        if self.mode == "vulnerable":
            return response(identity_id, 200, '{"record":{"id":"42","secret":"owned-secret-marker-xyz"}}')
        if self.mode == "secure":
            return response(identity_id, 403, '{"error":"forbidden"}')
        return response(identity_id, 200, '{"message":"ok"}')


def probe(mode, **overrides):
    adapter = FakeAdapter(mode)
    options = {
        "path": "/records/42",
        "resource_marker": MARKER,
        "owner_identity": "owner",
        "comparison_identity": "other",
        "owner_control_confirmed": True,
        "runs": 2,
    }
    options.update(overrides)
    report = run_read_only_bola_probe(adapter, **options)
    return report, adapter


def test_vulnerable_cross_identity_read_is_a_replay_verified_candidate():
    report, adapter = probe("vulnerable")
    assert report["status"] == "candidate"
    assert len(report["observations"]) == 2
    assert all(item["candidate"] for item in report["observations"])
    assert len(adapter.calls) == 4
    assert {call[0] for call in adapter.calls} == {"GET"}


def test_secure_denial_is_not_a_finding():
    report, _ = probe("secure")
    assert report["status"] == "no_cross_identity_disclosure_observed"
    assert not any(item["candidate"] for item in report["observations"])


def test_identical_generic_success_is_inconclusive_not_bola():
    report, _ = probe("generic")
    assert report["status"] == "inconclusive"
    assert not any(item["candidate"] for item in report["observations"])


def test_operator_must_attest_owner_control_before_any_request():
    adapter = FakeAdapter("vulnerable")
    with pytest.raises(PermissionError, match="confirm owner control"):
        run_read_only_bola_probe(
            adapter,
            path="/records/42",
            resource_marker=MARKER,
            owner_identity="owner",
            comparison_identity="other",
            owner_control_confirmed=False,
        )
    assert adapter.calls == []


def test_probe_rejects_cross_origin_path():
    adapter = FakeAdapter("vulnerable")
    with pytest.raises(ValueError, match="another origin"):
        run_read_only_bola_probe(
            adapter,
            path="//attacker.example/records/42",
            resource_marker=MARKER,
            owner_identity="owner",
            comparison_identity="other",
            owner_control_confirmed=True,
        )
    assert adapter.calls == []


def test_report_never_contains_response_body_or_resource_marker():
    report, _ = probe("vulnerable")
    serialized = json.dumps(report)
    assert MARKER not in serialized
    assert "owner-only" not in serialized
    assert "secret" not in serialized

def test_report_redacts_query_values_from_path():
    report, _ = probe("vulnerable", path="/records/42?access_token=do-not-publish")
    serialized = json.dumps(report)
    assert report["path"] == "/records/42"
    assert report["query_parameters_present"] is True
    assert "do-not-publish" not in serialized


def test_probe_rejects_line_breaks_before_request():
    adapter = FakeAdapter("vulnerable")
    with pytest.raises(ValueError, match="line breaks"):
        run_read_only_bola_probe(
            adapter,
            path="/records/42\r\nX-Injected: true",
            resource_marker=MARKER,
            owner_identity="owner",
            comparison_identity="other",
            owner_control_confirmed=True,
        )
    assert adapter.calls == []
