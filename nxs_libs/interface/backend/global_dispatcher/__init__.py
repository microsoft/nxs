import json
from abc import ABC, abstractmethod
from typing import List, Dict

from nxs_types.message import NxsMsgBackendStatsReport


class MiniDispatcherInputData:
    def __init__(self, cmodel_uuid: str, mini_dispatcher_data: List[Dict]) -> None:
        self.cmodel_uuid = cmodel_uuid
        self.mini_dispatcher_data = mini_dispatcher_data


class MiniDispatcherUpdateData:
    def __init__(self, cmodel_uuid: str, data: Dict) -> None:
        self.cmodel_uuid = cmodel_uuid
        self.data = data


class GlobalDispatcher(ABC):
    def __init__(self, extra_params={}) -> None:
        self.extra_params = extra_params

    @abstractmethod
    def update_minidispatcher_stats(self, stats: MiniDispatcherInputData) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate_minidispatcher_updates(self) -> List[MiniDispatcherUpdateData]:
        raise NotImplementedError

    @abstractmethod
    def generate_backend_stats_report_in_json_str(self) -> NxsMsgBackendStatsReport:
        raise NotImplementedError


class BasicGlobalDispatcher(GlobalDispatcher):
    def __init__(self, extra_params={}) -> None:
        super().__init__(extra_params=extra_params)

        self.last_stats_dict = {}

    def update_minidispatcher_stats(self, stats: MiniDispatcherInputData) -> None:
        self.last_stats_dict[stats.cmodel_uuid] = stats.mini_dispatcher_data

    def generate_minidispatcher_updates(self) -> List[MiniDispatcherUpdateData]:
        return []

    def generate_backend_stats_report_in_json_str(self) -> str:
        return json.dumps({})
