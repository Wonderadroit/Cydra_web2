from types import SimpleNamespace

from cydra_web2.discovery import _ids, discover
from cydra_web2.model import TargetModel


def test_documentation_examples_and_fixtures_do_not_become_resource_candidates():
    payload = {
        "docs": [{"id": "documented-user-1"}],
        "documentation": {"items": [{"uuid": "documented-item-1"}]},
        "examples": [{"id": "example-user-1"}],
        "sampleData": {"records": [{"id": "sample-record-1"}]},
        "fixtures": [{"uuid": "fixture-item-1"}],
        "tutorial": {"users": [{"id": "tutorial-user-1"}]},
        "items": [{"uuid": "live-candidate-1"}],
    }

    candidates = {(key, value) for key, value, _ in _ids(payload)}

    assert candidates == {("uuid", "live-candidate-1")}


def test_duplicate_resource_identifiers_are_modeled_once_and_linked_to_each_source_endpoint():
    class Adapter:
        def request(self, *, method, path, identity_id=None):
            body = (
                '{"items":[{"id":"same-resource"},{"id":"same-resource"}]}'
                if path == "/first"
                else '{"items":[{"id":"same-resource"}]}'
            )
            return SimpleNamespace(
                identity_id=identity_id,
                status_code=200,
                body=body,
                headers={"Content-Type": "application/json"},
            )

    model = TargetModel("https://authorized.example")
    result = discover(
        Adapter(),
        model,
        seeds=("/first", "/second"),
        max_paths=2,
    )

    assert len(result.resource_ids) == 1
    assert len(model.resources) == 1
    resource_id = result.resource_ids[0]
    assert model.endpoints["GET /first"].resource_ids == (resource_id,)
    assert model.endpoints["GET /second"].resource_ids == (resource_id,)
    resource = model.resources[resource_id]
    assert resource.owner_id is None
    assert resource.source_observation == model.observations[0].id
