from cydra_web2.ingestion import ingest_schema
from cydra_web2.model import TargetModel
from cydra_web2.schema import SchemaEndpoint


def test_schema_ingestion_adds_routes_without_ownership_guessing():
    model = TargetModel("https://authorized.example")
    result = ingest_schema(model, (SchemaEndpoint("GET", "/api/users/{id}", "getUser", ("id",)),))
    assert result.endpoints_added == 1
    endpoint = model.endpoints["GET /api/users/{id}"]
    assert endpoint.resource_ids == ()
    assert endpoint.action == "getUser"


def test_schema_ingestion_is_idempotent():
    model = TargetModel("https://authorized.example")
    endpoint = SchemaEndpoint("GET", "/api/users/{id}")
    assert ingest_schema(model, (endpoint,)).endpoints_added == 1
    assert ingest_schema(model, (endpoint,)).endpoints_added == 0
