from dataclasses import dataclass
import json

@dataclass(frozen=True)
class CampaignCheckpoint:
    target:str
    experiment_ids:tuple[str,...]
    completed_ids:tuple[str,...]=()
    candidate_ids:tuple[str,...]=()

    def __post_init__(self):
        if not self.target:
            raise ValueError("checkpoint target is required")
        if len(set(self.experiment_ids)) != len(self.experiment_ids):
            raise ValueError("checkpoint experiment ids must be unique")
        if not set(self.completed_ids).issubset(self.experiment_ids):
            raise ValueError("completed experiment is outside checkpoint plan")
        if not set(self.candidate_ids).issubset(self.completed_ids):
            raise ValueError("candidate experiment must already be completed")

    def dumps(self)->str:
        return json.dumps({
            "target":self.target,
            "experiment_ids":list(self.experiment_ids),
            "completed_ids":list(self.completed_ids),
            "candidate_ids":list(self.candidate_ids),
        },sort_keys=True,separators=(",",":"))

    @classmethod
    def loads(cls,data:str):
        x=json.loads(data)
        return cls(x["target"],tuple(x["experiment_ids"]),tuple(x.get("completed_ids",())),tuple(x.get("candidate_ids",())))

    def remaining(self)->tuple[str,...]:
        done=set(self.completed_ids)
        return tuple(x for x in self.experiment_ids if x not in done)
