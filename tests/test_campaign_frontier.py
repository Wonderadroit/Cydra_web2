from types import SimpleNamespace
from cydra_web2.campaign_runner import CampaignRunner
from cydra_web2.engine import ResearchEngine
from cydra_web2.model import Endpoint, Identity, Resource, TargetModel

class ControlledOwnershipTarget:
    def request(self, *, method, path, identity_id=None, **kwargs):
        return SimpleNamespace(
            url=path, final_url=path, method=method, identity_id=identity_id,
            status_code=200, headers={}, body='{"id":"record-1","owner":"alice"}',
            body_sha256="a" * 64,
        )


def test_campaign_resolves_ownership_then_rebuilds_authorization_frontier():
    model = TargetModel("https://controlled.authorized")
    model.add_identity(Identity("alice", "owner", True))
    model.add_identity(Identity("bob", "comparison", True))
    model.add_resource(Resource("record-1", "record", None, "record-1"))
    model.add_endpoint(Endpoint("records", "GET", "/records/{id}", ("record-1",), "read"))
    engine = ResearchEngine(model, ControlledOwnershipTarget())
    outcome = CampaignRunner(engine).run_research()
    assert outcome.ownership_resolved == 0
    assert model.resources["record-1"].owner_id is None
    assert not any(s.experiment_id.startswith("auth:") for s in outcome.states)
    assert any(s.experiment_id.startswith("ownership:") for s in outcome.states)
