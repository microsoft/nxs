from typing import Dict, List
from nxs_libs.interface.frontend import FrontendTaskSummaryProcessor
from nxs_types.frontend import TaskSummary, FrontendWorkloadReport


class SimpleFrontendTaskSummaryProcessor(FrontendTaskSummaryProcessor):
    def __init__(self, extra_parms: Dict = {}) -> None:
        super().__init__(extra_parms)

    def pre_task_processing(self, task_summary: TaskSummary):
        pass

    def post_task_processing(self, task_summary: TaskSummary):
        pass

    def process_summaries(self, task_summaries: List[TaskSummary]) -> Dict:
        return {}
