from cydra_web2.artifact import ownership_next_experiments, resource_provenance
from cydra_web2.model import Endpoint, Observation, Resource, TargetModel


def test_resource_report_preserves_source_provenance_and_endpoint_link():
    model = TargetModel("https://authorized.example")
    model.add_endpoint(Endpoint("GET /items", "GET", "/items"))
    observation = Observation("obs:source", "GET /items", None, 200, "a" * 64, 42, "GET:/items")
    model.add_observation(observation)
    resource = Resource("resource:r1", "uuid", None, "item-1", observation.id, "items[0].uuid")
    model.add_resource(resource)
    endpoint = model.endpoints["GET /items"]
    model.endpoints[endpoint.id] = Endpoint(endpoint.id, endpoint.method, endpoint.path, (resource.id,), endpoint.action)

    records = resource_provenance(model)
    assert records == [{
        "id": "resource:r1",
        "label": "uuid",
        "identifier": "item-1",
        "owner_id": None,
        "source_observation_id": "obs:source",
        "source_endpoint_id": "GET /items",
        "source_status_code": 200,
        "provenance_valid": True,
        "resource_status": "unverified_candidate",
        "provenance_failure": None,
        "source_field_path": "items[0].uuid",
        "linked_endpoint_ids": ["GET /items"],
    }]


def test_unknown_owner_produces_blocked_safe_next_experiment():
    model = TargetModel("https://authorized.example")
    model.add_endpoint(Endpoint("GET /items", "GET", "/items"))
    observation = Observation("obs:source", "GET /items", None, 200, "a" * 64, 42, "GET:/items")
    model.add_observation(observation)
    model.add_resource(Resource("resource:r1", "uuid", None, "item-1", observation.id, "items[0].uuid"))

    experiment, = ownership_next_experiments(model)
    assert experiment["status"] == "blocked"
    assert experiment["resource_id"] == "resource:r1"
    assert experiment["source_field_path"] == "items[0].uuid"
    assert "cannot prove resource ownership" in experiment["blocked_reason"]
    assert "Do not claim IDOR" in experiment["safety_gate"]
    assert len(experiment["required_capabilities"]) == 2

def test_empty_anonymous_model_reports_blocked_resource_state_acquisition():
    model = TargetModel("https://authorized.example")
    experiment, = ownership_next_experiments(model)
    assert experiment["id"] == "acquire-authenticated-resource-state"
    assert experiment["status"] == "blocked"
    assert experiment["resource_id"] is None
    assert "no authenticated identities" in experiment["blocked_reason"]
    assert "identity-bound evidence" in experiment["safety_gate"]
