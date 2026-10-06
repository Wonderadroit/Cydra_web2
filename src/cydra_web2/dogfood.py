from dataclasses import dataclass
from .adapter import HttpAdapter,TargetConfig,IdentitySession
from .campaign_runner import CampaignOutcome,CampaignRunner
from .model import TargetModel

@dataclass(frozen=True)
class DogfoodConfig:
    target:TargetConfig
    identities:tuple[IdentitySession,...]
    max_experiments:int=25

class DogfoodRunner:
    """Fail-closed entry point for an explicitly scoped Web2 dogfood campaign."""
    def __init__(self,model:TargetModel,config:DogfoodConfig):
        if model.target.rstrip("/") != config.target.base_url.rstrip("/"):
            raise ValueError("model target and execution target must match")
        if not config.identities:
            raise ValueError("dogfood requires at least one explicit identity binding")
        ids=[x.identity_id for x in config.identities]
        if len(ids)!=len(set(ids)):
            raise ValueError("identity bindings must be unique")
        self.model=model
        self.config=config
        self.adapter=HttpAdapter(config.target,config.identities)
        self.runner=CampaignRunner(__import__("cydra_web2.engine",fromlist=["ResearchEngine"]).ResearchEngine(model,self.adapter))
    def run(self)->CampaignOutcome:
        experiments=self.runner.engine.plan_authorization_frontier()
        return self.runner.run(experiments)
