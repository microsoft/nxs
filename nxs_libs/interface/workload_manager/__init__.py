import time
from typing import Dict, List, Tuple
from abc import ABC, abstractmethod

from configs import GLOBAL_QUEUE_NAMES
from nxs_types.nxs_args import NxsWorkloadManagerArgs
from nxs_libs.queue import NxsQueuePuller, NxsQueuePusher

from nxs_types.frontend import (
    FrontendWorkloadReport,
    FrontendModelPipelineWorkloadReport,
)
from nxs_types.message import (
    NxsMsgType,
    NxsMsgReportInputWorkloads,
    NxsMsgRegisterWorkloads,
)


class NxsBaseWorkloadManagerPolicy(ABC):
    def __init__(self, args: NxsWorkloadManagerArgs) -> None:
        super().__init__()
        self.args = args

    @abstractmethod
    def process_msgs(
        self, msgs: List[NxsMsgReportInputWorkloads]
    ) -> Tuple[bool, List[FrontendModelPipelineWorkloadReport]]:
        raise NotImplementedError


class NxsWorkloadManager:
    def __init__(
        self,
        args: NxsWorkloadManagerArgs,
        queue_puller: NxsQueuePuller,
        queue_pusher: NxsQueuePusher,
        policy: NxsBaseWorkloadManagerPolicy,
    ) -> None:
        self.args = args
        self.queue_puller = queue_puller
        self.queue_pusher = queue_pusher
        self.policy = policy

        self.queue_pusher.create_topic(GLOBAL_QUEUE_NAMES.WORKLOAD_MANAGER)

    def send_workloads_to_scheduler(
        self, scheduling_msgs: List[FrontendModelPipelineWorkloadReport]
    ):
        self.queue_pusher.push(
            GLOBAL_QUEUE_NAMES.SCHEDULER,
            NxsMsgRegisterWorkloads(workloads=scheduling_msgs),
        )

    def run(self):
        while True:
            msgs = self.queue_puller.pull()

            to_schedule, scheduling_msgs = self.policy.process_msgs(msgs)

            if to_schedule:
                self.send_workloads_to_scheduler(scheduling_msgs)

            if not msgs:
                time.sleep(0.1)
