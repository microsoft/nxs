from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List
from typing import Tuple

from nxs_types.backend import BackendInfo
from nxs_types.scheduling_data import NxsSchedulingPlan
from nxs_types.scheduling_data import NxsSchedulingRequest


class BaseSchedulingPolicy(ABC):
    MAX_MODELS_PER_BACKEND = 5

    def __init__(self) -> None:
        super().__init__()

    def set_max_models(self, max_models: int):
        self.MAX_MODELS_PER_BACKEND = max_models

    @abstractmethod
    def schedule(
        self, requests: List[NxsSchedulingRequest], backends: List[BackendInfo]
    ) -> NxsSchedulingPlan:
        raise NotImplementedError

    @abstractmethod
    def get_states(self) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def set_states(self, states):
        raise NotImplementedError

    @abstractmethod
    def update_backend_runtime_stats(self, backend_name: str, backend_states: Dict):
        raise NotImplementedError
