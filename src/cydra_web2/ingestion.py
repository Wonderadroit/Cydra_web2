from __future__ import annotations
from dataclasses import dataclass
from .model import Endpoint, Observation, Resource, TargetModel
from .schema import SchemaEndpoint

@dataclass(frozen=True)
class ModelIngestionResult:
    endpoints_added: int
    resources_added: int
    observations_added: int


def ingest_schema(model: TargetModel, endpoints: tuple[SchemaEndpoint, ...]) -> ModelIngestionResult:
    """Add schema knowledge without guessing ownership or authorization."""
    before = len(model.endpoints)
    for item in endpoints:
        endpoint_id = f"{item.method} {item.path}"
        if endpoint_id not in model.endpoints:
            model.add_endpoint(Endpoint(endpoint_id, item.method, item.path, (), item.operation_id))
    return ModelIngestionResult(len(model.endpoints) - before, 0, 0)


def ingest_discovery(result, model: TargetModel | None = None) -> ModelIngestionResult:
    """Normalize a discovery result into a model; never infer resource ownership."""
    target_model = model or result.model
    before_e, before_r, before_o = len(target_model.endpoints), len(target_model.resources), len(target_model.observations)
    for observation in result.observations:
        if not any(existing.id == observation.id for existing in target_model.observations):
            target_model.add_observation(observation)
    return ModelIngestionResult(
        len(target_model.endpoints) - before_e,
        len(target_model.resources) - before_r,
        len(target_model.observations) - before_o,
    )
