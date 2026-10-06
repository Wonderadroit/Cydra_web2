from dataclasses import dataclass
from enum import Enum

class ExperimentStage(str,Enum):
    PLANNED="planned"; VALIDATED="validated"; EXECUTED="executed"; OBSERVED="observed"; CAUSAL="causal"; REJECTED="rejected"

@dataclass(frozen=True)
class ExperimentState:
    experiment_id:str
    stage:ExperimentStage
    reason:str

def advance(state,stage,reason):
    order=[ExperimentStage.PLANNED,ExperimentStage.VALIDATED,ExperimentStage.EXECUTED,ExperimentStage.OBSERVED,ExperimentStage.CAUSAL]
    if state.stage is ExperimentStage.REJECTED: raise ValueError("rejected experiment cannot advance")
    if stage in order and order.index(stage)<order.index(state.stage): raise ValueError("experiment stage cannot move backward")
    return ExperimentState(state.experiment_id,stage,reason)
