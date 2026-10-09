from types import SimpleNamespace

from cydra_web2.identity_diff import identity_differentials


def test_cross_identity_difference_is_triage_candidate_not_finding():
    observations = [
        SimpleNamespace(endpoint_id="GET /profile", identity_id="alice", status_code=200, body_sha256="a", body_length=20),
        SimpleNamespace(endpoint_id="GET /profile", identity_id="bob", status_code=200, body_sha256="b", body_length=24),
    ]

    result = identity_differentials(observations)

    assert len(result) == 1
    assert result[0]["response_differs_between_identities"] is True
    assert result[0]["classification"] == "differential_candidate"
    assert result[0]["finding_asserted"] is False
    assert set(result[0]["identities"]) == {"alice", "bob"}


def test_same_response_across_identities_is_not_candidate():
    observations = [
        SimpleNamespace(endpoint_id="GET /public", identity_id="alice", status_code=200, body_sha256="same", body_length=12),
        SimpleNamespace(endpoint_id="GET /public", identity_id="bob", status_code=200, body_sha256="same", body_length=12),
    ]

    result = identity_differentials(observations)

    assert len(result) == 1
    assert result[0]["response_differs_between_identities"] is False
    assert result[0]["classification"] == "no_observed_difference"


def test_single_identity_observation_is_not_cross_identity_candidate():
    observations = [
        SimpleNamespace(endpoint_id="GET /profile", identity_id="alice", status_code=200, body_sha256="a", body_length=20),
    ]

    assert identity_differentials(observations) == []


def test_differentials_keep_multiple_observations_per_identity():
    observations = [
        SimpleNamespace(endpoint_id="GET /items", identity_id="alice", status_code=200, body_sha256="a", body_length=20),
        SimpleNamespace(endpoint_id="GET /items", identity_id="alice", status_code=200, body_sha256="a", body_length=20),
        SimpleNamespace(endpoint_id="GET /items", identity_id="bob", status_code=403, body_sha256="b", body_length=8),
    ]

    result = identity_differentials(observations)

    assert result[0]["identities"]["alice"]["observation_count"] == 2
    assert result[0]["identities"]["bob"]["status_codes"] == [403]
    assert result[0]["response_differs_between_identities"] is True
