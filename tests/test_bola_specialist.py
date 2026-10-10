"""Deterministic specialist benchmark for BOLA decision quality.

These tests exercise the complete planning -> differential -> replay pipeline
against controlled response fixtures. They validate engine behavior, not live
customer vulnerabilities or broad application coverage.
"""
import hashlib
from types import SimpleNamespace

from cydra_web2.campaign_runner import CampaignRunner
from cydra_web2.engine import ResearchEngine
from cydra_web2.model import Endpoint, Identity, Resource, TargetModel


RESOURCE_ID = "private-record-123"


def response(identity_id, status_code, body, method="GET", path="/records/private-record-123"):
    return SimpleNamespace(
        url=path,
        final_url=path,
        method=method,
        identity_id=identity_id,
        status_code=status_code,
        headers={},
        body=body,
        body_sha256=hashlib.sha256(body.encode()).hexdigest(),
    )


class ControlledBolaTarget:
    def __init__(self, mode):
        if mode not in {"vulnerable", "secure", "generic"}:
            raise ValueError(mode)
        self.mode = mode
        self.calls = []

    def request(self, *, method, path, identity_id=None, **kwargs):
        self.calls.append((method, path, identity_id))
        if identity_id == "alice":
            body = '{"record":{"id":"private-record-123","owner":"alice","secret":"owner-only"}}'
            return response(identity_id, 200, body, method, path)
        if self.mode == "vulnerable":
            body = '{"record":{"id":"private-record-123","owner":"alice","secret":"owner-only"}}'
            return response(identity_id, 200, body, method, path)
        if self.mode == "secure":
            return response(identity_id, 403, '{"error":"forbidden"}', method, path)
        # Deliberately identical 2xx boilerplate must not be mistaken for BOLA.
        return response(identity_id, 200, '{"message":"ok"}', method, path)


def run_case(mode):
    model = TargetModel("https://controlled.authorized")
    model.add_identity(Identity("alice", "owner test account", True))
    model.add_identity(Identity("bob", "comparison test account", True))
    model.add_resource(Resource("record-1", "record", "alice", RESOURCE_ID))
    model.add_endpoint(Endpoint("read-record", "GET", "/records/{id}", ("record-1",), "read"))
    target = ControlledBolaTarget(mode)
    engine = ResearchEngine(model, target)
    outcome = CampaignRunner(engine).run(engine.plan_authorization_frontier())
    return outcome, target


def test_seeded_bola_is_replay_verified_and_reportable():
    outcome, target = run_case("vulnerable")
    assert outcome.stopped is True
    assert outcome.candidates == 1
    assert outcome.assessment is not None and outcome.assessment.reportable is True
    assert outcome.assessment.replay_verified is True
    assert len(target.calls) == 6  # owner + comparison for initial test and two replays


def test_secure_cross_identity_denial_is_not_reported():
    outcome, _ = run_case("secure")
    assert outcome.candidates == 0
    assert outcome.assessment is None
    assert outcome.stopped is False


def test_identical_generic_success_responses_are_not_reported_as_bola():
    outcome, _ = run_case("generic")
    assert outcome.candidates == 0
    assert outcome.assessment is None
    assert outcome.stopped is False
