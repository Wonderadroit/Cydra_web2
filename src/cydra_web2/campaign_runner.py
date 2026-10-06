from dataclasses import dataclass
import hashlib
from .boundary import BoundaryAssessment, assess_boundary
from .engine import ResearchEngine
from .experiment_state import ExperimentState, ExperimentStage, advance
from .observation import observation_from_response
from .differential import OwnershipExperiment
from .ownership import resolve_experiment_ownership
from .verification import verify_replay

@dataclass(frozen=True)
class CampaignOutcome:
    executed: int
    candidates: int
    assessment: BoundaryAssessment | None
    stopped: bool
    states: tuple[ExperimentState, ...] = ()
    ownership_resolved: int = 0

class CampaignRunner:
    """Run evidence-driven research, resolving model prerequisites before authorization tests."""
    def __init__(self, engine: ResearchEngine, max_experiments: int = 25):
        if max_experiments < 1:
            raise ValueError("max_experiments must be positive")
        self.engine = engine
        self.max_experiments = max_experiments

    def _ownership_observation(self, experiment: OwnershipExperiment, response):
        return observation_from_response(
            observation_id=f"{experiment.id}:observation",
            endpoint_id=experiment.endpoint_id,
            identity_id=experiment.identity_id,
            response=response,
            request_fingerprint=hashlib.sha256(
                f"{experiment.identity_id}|{experiment.endpoint_id}|{experiment.path}".encode()
            ).hexdigest(),
        )

    def run_research(self):
        """Advance the model frontier: ownership evidence first, authorization second."""
        executed = 0
        candidates = 0
        states = []
        ownership_resolved = 0

        ownership_experiments = self.engine.planner.plan_ownership(self.engine.model)
        for experiment in ownership_experiments:
            if executed >= self.max_experiments:
                break
            executed += 1
            state = ExperimentState(experiment.id, ExperimentStage.PLANNED, "ownership prerequisite selected from frontier")
            state = advance(state, ExperimentStage.VALIDATED, "identity, endpoint, identifier and scope are modelled")
            endpoint = self.engine.model.endpoints.get(experiment.endpoint_id)\n            if endpoint is None:\n                states.append(advance(state, ExperimentStage.REJECTED, "ownership endpoint disappeared from model"))\n                continue\n            response = self.engine.adapter.request(method=endpoint.method, path=experiment.path, identity_id=experiment.identity_id)
            state = advance(state, ExperimentStage.EXECUTED, "ownership request completed")
            observation = self._ownership_observation(experiment, response)
            self.engine.model.add_observation(observation)
            state = advance(state, ExperimentStage.OBSERVED, "ownership response recorded as attributable observation")
            try:
                resolve_experiment_ownership(self.engine.model, experiment, observation, response.body)
            except ValueError:
                states.append(advance(state, ExperimentStage.REJECTED, "response did not establish ownership; model remains unresolved"))
                continue
            ownership_resolved += 1
            states.append(state)

        if executed >= self.max_experiments:
            return CampaignOutcome(executed, candidates, None, False, tuple(states), ownership_resolved)

        # Rebuild the executable frontier after model mutation; do not use stale plans.
        planned = self.engine.plan_research()
        experiments = tuple(item.experiment for item in planned)
        remaining = max(0, self.max_experiments - executed)
        auth_outcome = self.run(experiments[:remaining])
        return CampaignOutcome(
            executed + auth_outcome.executed,
            auth_outcome.candidates,
            auth_outcome.assessment,
            auth_outcome.stopped,
            tuple(states) + auth_outcome.states,
            ownership_resolved,
        )

    def run(self, experiments):
        executed = 0
        candidates = 0
        states = []
        for experiment in experiments:
            if executed >= self.max_experiments:
                break
            executed += 1
            state = ExperimentState(experiment.id, ExperimentStage.PLANNED, "selected from bounded campaign")
            state = advance(state, ExperimentStage.VALIDATED, "execution scope and model planning already passed")
            first = self.engine.execute(experiment)
            state = advance(state, ExperimentStage.EXECUTED, "owner/comparison requests completed")
            state = advance(state, ExperimentStage.OBSERVED, "differential evidence classified")
            states.append(state)
            if not first.evidence.finding_candidate:
                continue
            candidates += 1
            replay = self.engine.replay(experiment, 2)
            verification = self.engine.causal_gate(replay)
            assessment = assess_boundary(tuple(r.evidence for r in replay), verify_replay(replay))
            if assessment.reportable:
                states[-1] = advance(states[-1], ExperimentStage.CAUSAL, "replay established stable non-NONE impact")
                return CampaignOutcome(executed, candidates, assessment, True, tuple(states))
        return CampaignOutcome(executed, candidates, None, False, tuple(states))
