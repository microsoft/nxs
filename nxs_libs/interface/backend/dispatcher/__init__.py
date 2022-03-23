from abc import ABC, abstractmethod
import json
import pickle
from typing import Dict, List
from enum import Enum
from nxs_types import DataModel

from nxs_types.infer import NxsInferRequest


class BackendDispatcherType(str, Enum):
    BASIC = "basic"
    BASIC_SLA = "basic_sla"


class BackendDispatcherExceptionInvalidType(Exception):
    pass


class DispatcherResult(DataModel):
    to_schedule: List[NxsInferRequest] = []
    to_delay: List[NxsInferRequest] = []
    to_drop: List[NxsInferRequest] = []


class BackendDispatcher(ABC):
    def __init__(self, extra_params={}) -> None:
        super().__init__()
        self.extra_params = extra_params

    @abstractmethod
    def dispatch(self, requests: List[NxsInferRequest]) -> DispatcherResult:
        raise NotImplementedError

    @abstractmethod
    def update_stats(self, stats: Dict = {}) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_stats_from_global_dispatcher(self, stats: Dict = {}) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_stats_to_global_dispatcher(self) -> Dict:
        raise NotImplementedError


class BackendBasicDispatcher(BackendDispatcher):
    def __init__(self, extra_params={}) -> None:
        super().__init__(extra_params=extra_params)

    def dispatch(self, requests: List[NxsInferRequest]) -> DispatcherResult:
        return DispatcherResult(to_schedule=requests)

    def update_stats(self, stats: Dict = {}) -> None:
        self.last_stats = stats

    def update_stats_from_global_dispatcher(self, stats: Dict = {}) -> None:
        pass

    def report_stats_to_global_dispatcher(self) -> Dict:
        try:
            last_stats = self.last_stats
        except:
            last_stats = {}

        return last_stats


class BackendBasicSlaDispatcher(BackendDispatcher):
    def __init__(self, extra_params={}) -> None:
        super().__init__(extra_params=extra_params)
        self.input_process = extra_params["input_process"]

    def dispatch(self, requests: List[NxsInferRequest]) -> DispatcherResult:
        sla_requests: List[NxsInferRequest] = []
        slas: List[float] = []
        nonsla_requests: List[NxsInferRequest] = []

        for request in requests:
            try:
                # extra_params = json.loads(request.extra_params)
                extra_params = pickle.loads(request.extra_params)
                assert isinstance(extra_params, Dict)
            except:
                extra_params = {}

            if "sla" in extra_params:
                sla = 0
                try:
                    sla = float(extra_params.get("sla", 0))
                except:
                    sla = 0

                if sla > 0:
                    sla_requests.append(request)
                    slas.append(sla)
                else:
                    # treat invalid requests as non-sla requests
                    nonsla_requests.append(request)
            else:
                nonsla_requests.append(request)

        # sort sla-requests based on sla-requirements
        zipped_lists = zip(slas, sla_requests)
        sorted_pairs = sorted(zipped_lists)
        tuples = zip(*sorted_pairs)
        slas, sla_requests = tuples

        # schedule sla_requests first
        to_schedule = []
        to_schedule.extend(sla_requests)
        to_schedule.extend(nonsla_requests)

        return DispatcherResult(to_schedule=to_schedule)

    def update_stats(self, stats: Dict = {}) -> None:
        self.last_stats = stats

    def update_stats_from_global_dispatcher(self, stats: Dict = {}) -> None:
        pass

    def report_stats_to_global_dispatcher(self) -> Dict:
        try:
            last_stats = self.last_stats
        except:
            last_stats = {}

        return last_stats


class BackendDispatcherFactory:
    @staticmethod
    def create_dispatcher(type: BackendDispatcherType, **kwargs) -> BackendDispatcher:
        if type == BackendDispatcherType.BASIC:
            return BackendBasicDispatcher(**kwargs)

        raise BackendDispatcherExceptionInvalidType
