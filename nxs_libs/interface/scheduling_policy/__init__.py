from typing import Dict, List, Tuple
from abc import ABC, abstractmethod
from nxs_types.backend import BackendInfo
from nxs_types.scheduling_data import NxsSchedulingPlan, NxsSchedulingRequest


class BaseSchedulingPolicy(ABC):
    def __init__(self) -> None:
        super().__init__()

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
