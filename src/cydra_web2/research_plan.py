from dataclasses import dataclass
from .differential import DifferentialExperiment
from .hypothesis import Hypothesis

@dataclass(frozen=True)
class PlannedExperiment:
    hypothesis:Hypothesis
    experiment:DifferentialExperiment
