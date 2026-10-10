import hashlib
from types import SimpleNamespace

from cydra_web2.evidence import classify_differential, response_contains_marker


def response(status, body):
    return SimpleNamespace(
        status_code=status,
        body=body,
        body_sha256=hashlib.sha256(body.encode()).hexdigest(),
    )


EXPERIMENT = SimpleNamespace(id="auth:record-1:bob")


def test_json_resource_marker_is_detected():
    assert response_contains_marker('{"record":{"id":"r123"}}', "r123")


def test_missing_marker_is_not_evidence():
    assert not response_contains_marker('{"record":{"id":"other"}}', "r123")


def test_identical_successful_generic_responses_do_not_prove_bola():
    generic = response(200, '{"message":"ok"}')
    evidence = classify_differential(EXPERIMENT, generic, generic, "private-record-123")
    assert evidence.finding_candidate is False
    assert evidence.data["response_fingerprints_equal"] is True
    assert evidence.data["owner_resource_marker_found"] is False
    assert evidence.data["comparison_resource_marker_found"] is False


def test_cross_identity_access_with_owner_bound_marker_is_candidate():
    owner = response(200, '{"record":{"id":"private-record-123","value":"secret"}}')
    other = response(200, '{"record":{"id":"private-record-123","value":"secret"}}')
    evidence = classify_differential(EXPERIMENT, owner, other, "private-record-123")
    assert evidence.finding_candidate is True
    assert evidence.data["owner_resource_marker_found"] is True
    assert evidence.data["comparison_resource_marker_found"] is True


def test_other_identity_response_without_protected_marker_is_not_candidate():
    owner = response(200, '{"record":{"id":"private-record-123"}}')
    other = response(200, '{"record":{"id":"different-record"}}')
    evidence = classify_differential(EXPERIMENT, owner, other, "private-record-123")
    assert evidence.finding_candidate is False


def test_owner_baseline_must_demonstrate_access_to_the_modeled_object():
    owner = response(200, '{"message":"ok"}')
    other = response(200, '{"record":{"id":"private-record-123"}}')
    evidence = classify_differential(EXPERIMENT, owner, other, "private-record-123")
    assert evidence.finding_candidate is False


def test_success_status_without_resource_marker_is_not_candidate():
    owner = response(200, '{"id":"private-record-123"}')
    other = response(200, '{"id":"private-record-123"}')
    evidence = classify_differential(EXPERIMENT, owner, other)
    assert evidence.finding_candidate is False

def test_marker_does_not_match_a_longer_identifier():
    assert not response_contains_marker('{"record":{"id":"record-123"}}', "record-12")


def test_non_json_marker_requires_token_boundaries():
    assert not response_contains_marker("record-123", "record-12")
    assert response_contains_marker("record record-12 found", "record-12")
