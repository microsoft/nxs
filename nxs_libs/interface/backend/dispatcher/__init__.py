import pickle
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List
from enum import Enum
from nxs_types import DataModel

from nxs_types.infer import NxsInferRequest


class BackendDispatcherType(str, Enum):
    BASIC = "basic"
    BASIC_SLA = "basic_sla"
    BASIC_MONITORING = "basic_monitoring"


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

    @abstractmethod
    def get_stats_summary(self) -> Dict:
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

    def get_stats_summary(self) -> Dict:
        return {}


class BackendBasicMonitoringDispatcher(BackendBasicDispatcher):
    def __init__(self, extra_params={}, max_cache_size: int = 30) -> None:
        super().__init__(extra_params)
        self.max_cache_size = max_cache_size
        self.states_cache: List = []
        self.total_processed_reqs = 0

    def dispatch(self, requests: List[NxsInferRequest]) -> DispatcherResult:
        return DispatcherResult(to_schedule=requests)

    def update_stats(self, stats: Dict = {}) -> None:
        self.last_stats = stats

        self.total_processed_reqs += stats.get("num_reqs", 0)

        if len(self.states_cache) > self.max_cache_size:
            self.states_cache.pop(0)

        self.states_cache.append(stats)

    def update_stats_from_global_dispatcher(self, stats: Dict = {}) -> None:
        pass

    def report_stats_to_global_dispatcher(self) -> Dict:
        return {}

    def get_stats_summary(self) -> Dict:
        output_processes = {}

        for stats in self.states_cache:
            output_pid = stats["output_pid"]
            if output_pid not in output_processes:
                output_processes[output_pid] = []

            output_processes[output_pid].append(stats)

        fps = 0
        latency_stats = []
        for pid in output_processes:
            fps += np.mean([stats["fps"] for stats in output_processes[pid]])
            latency_stats.extend([stats["latency"] for stats in output_processes[pid]])

        latency = {
            "mean": np.mean([stats["mean"] for stats in latency_stats]),
            "min": np.mean([stats["min"] for stats in latency_stats]),
            "max": np.mean([stats["max"] for stats in latency_stats]),
        }

        response = {
            "total_reqs": self.total_processed_reqs,
            "fps": fps,
            "latency": latency,
        }

        return response


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

    def get_stats_summary(self) -> Dict:
        return {}


class BackendDispatcherFactory:
    @staticmethod
    def create_dispatcher(type: BackendDispatcherType, **kwargs) -> BackendDispatcher:
        if type == BackendDispatcherType.BASIC:
            return BackendBasicDispatcher(**kwargs)
        elif type == BackendDispatcherType.BASIC_MONITORING:
            return BackendBasicMonitoringDispatcher(**kwargs)

        raise BackendDispatcherExceptionInvalidType
