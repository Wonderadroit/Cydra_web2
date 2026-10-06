from dataclasses import dataclass
from .model import TargetModel, Observation
from .workflow_graph import Transition
from .evidence import response_contains_marker

@dataclass(frozen=True)
class ControlProvenance:
    identity_id:str
    transition_id:str
    resource_id:str
    observation_id:str
    control_kind:str
    rationale:str
    def __post_init__(self):
        if self.control_kind not in {"creation","write"}:
            raise ValueError("control provenance must be creation or write")

def establish_control(model:TargetModel, transition:Transition, observation:Observation, resource_id:str, response_body:str, control_kind:str="creation")->ControlProvenance:
    if transition.identity_id != observation.identity_id:
        raise ValueError("control evidence identity mismatch")
    if transition.method.upper() not in {"POST","PUT","PATCH","DELETE"}:
        raise ValueError("control provenance requires a write-capable transition")
    if resource_id not in model.resources:
        raise ValueError("control provenance references unknown resource")
    if not 200 <= observation.status_code < 300:
        raise ValueError("control provenance requires a successful write response")
    resource=model.resources[resource_id]
    if resource.identifier is None or not response_contains_marker(response_body,resource.identifier):
        raise ValueError("control provenance requires the modeled resource marker")
    if resource_id not in transition.produces:
        raise ValueError("transition does not causally produce the modeled resource")
    return ControlProvenance(observation.identity_id,transition.id,resource_id,observation.id,control_kind,"write transition produced the modeled resource and returned its exact identifier")

def apply_control_ownership(model:TargetModel, provenance:ControlProvenance):
    if provenance.identity_id not in model.identities:
        raise ValueError("control provenance references unknown identity")
    resource=model.resources.get(provenance.resource_id)
    if resource is None:
        raise ValueError("control provenance references unknown resource")
    if resource.owner_id is not None and resource.owner_id != provenance.identity_id:
        raise ValueError("conflicting ownership control")
    model.resources[resource.id]=type(resource)(resource.id,resource.label,provenance.identity_id,resource.identifier,provenance.observation_id)
    return model
