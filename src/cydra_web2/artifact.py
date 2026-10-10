from dataclasses import asdict
import json
from .redaction import redact

def campaign_artifact(*,target,model,hypotheses,experiments,evidence,replays,assessment=None):
    return {
      "target":target,
      "model":{"identities":len(model.identities),"resources":len(model.resources),"endpoints":len(model.endpoints),"observations":len(model.observations)},
      "hypotheses":[asdict(x) for x in hypotheses],
      "experiments":[getattr(x,"id",None) for x in experiments],
      "evidence":[asdict(x) for x in evidence],
      "replays":[getattr(x,"experiment",None).id if getattr(x,"experiment",None) else None for x in replays],
      "assessment":asdict(assessment) if assessment else None,
    }

def resource_provenance(model):
    """Return resource candidates with source observation and endpoint lineage."""
    observations = {item.id: item for item in model.observations}
    records = []
    for resource in sorted(model.resources.values(), key=lambda item: item.id):
        source = observations.get(resource.source_observation)
        linked_endpoints = sorted(
            endpoint.id for endpoint in model.endpoints.values()
            if resource.id in endpoint.resource_ids
        )
        records.append({
            "id": resource.id,
            "label": resource.label,
            "identifier": resource.identifier,
            "owner_id": resource.owner_id,
            "source_observation_id": resource.source_observation,
            "source_endpoint_id": source.endpoint_id if source else None,
            "source_status_code": source.status_code if source else None,
            "source_field_path": resource.source_field_path,
            "linked_endpoint_ids": linked_endpoints,
        })
    return records


def ownership_next_experiments(model):
    """Describe the safe prerequisite experiment for resources with unknown owners."""
    observations = {item.id: item for item in model.observations}
    experiments = []
    for resource in sorted(model.resources.values(), key=lambda item: item.id):
        if resource.owner_id is not None:
            continue
        source = observations.get(resource.source_observation)
        experiments.append({
            "id": f"establish-owner:{resource.id}",
            "kind": "ownership_establishment",
            "resource_id": resource.id,
            "source_observation_id": resource.source_observation,
            "source_endpoint_id": source.endpoint_id if source else None,
            "source_field_path": resource.source_field_path,
            "status": "blocked",
            "blocked_reason": "Anonymous discovery has no authenticated identities and cannot prove resource ownership or authorization boundaries.",
            "required_capabilities": [
                "target-authorized test identity with a known owner context",
                "second target-authorized identity if cross-identity comparison is in scope",
            ],
            "procedure": [
                "Use the normal authorized application flow to identify which test identity owns this resource.",
                "Record the authenticated identity, source request, response, resource identifier, and field path as evidence.",
                "Only if scope permits, compare the same read-only request using a second authorized identity and preserve both responses.",
            ],
            "safety_gate": "Do not claim IDOR or attempt cross-account access until ownership and scope are established.",
        })
    return experiments

def dumps_artifact(data)->str:
    return json.dumps(redact(data),sort_keys=True,indent=2,default=str)
