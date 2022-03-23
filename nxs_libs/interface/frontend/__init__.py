from abc import ABC, abstractmethod
from typing import Dict, List
from nxs_types.frontend import TaskSummary


class FrontendTaskSummaryProcessor(ABC):
    def __init__(self, extra_parms: Dict = {}) -> None:
        super().__init__()
        self.extra_parms = extra_parms

    @abstractmethod
    def pre_task_processing(self, task_summary: TaskSummary):
        raise NotImplementedError

    @abstractmethod
    def post_task_processing(self, task_summary: TaskSummary):
        raise NotImplementedError

    @abstractmethod
    def process_summaries(self, task_summaries: List[TaskSummary]) -> Dict:
        pass
