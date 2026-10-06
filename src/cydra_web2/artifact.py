from dataclasses import asdict
import json

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

def dumps_artifact(data)->str:
    return json.dumps(data,sort_keys=True,indent=2,default=str)
