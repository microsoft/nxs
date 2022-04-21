import time
import numpy as np
from typing import Dict, List, Tuple
from nxs_libs.interface.workload_manager import (
    NxsBaseWorkloadManagerPolicy,
)
from nxs_types.frontend import FrontendModelPipelineWorkloadReport
from nxs_types.message import (
    NxsMsgPinWorkload,
    NxsMsgType,
    NxsMsgReportInputWorkloads,
    NxsMsgUnpinWorkload,
)
from nxs_types.nxs_args import NxsWorkloadManagerArgs


class FrontendWorkloads:
    def __init__(self, frontend: str, model_timeout_secs: float) -> None:
        self.frontend = frontend
        self.model_timeout_secs = model_timeout_secs

        self.uuid2throughput: Dict[str, List[float]] = {}
        self.uuid2timestamps: Dict[str, List[float]] = {}
        # self.uuid2pipelineuuid: Dict[str, str] = {}
        # self.uuid2sessionuuid: Dict[str, str] = {}

    def add_workload(self, workload: FrontendModelPipelineWorkloadReport):
        uuid = f"{workload.pipeline_uuid}_{workload.session_uuid}"
        if uuid not in self.uuid2throughput:
            self.uuid2throughput[uuid] = []
            self.uuid2timestamps[uuid] = []
            # self.uuid2pipelineuuid[uuid] = workload.pipeline_uuid
            # self.uuid2sessionuuid[uuid] = workload.session_uuid

        self.uuid2throughput[uuid].append(workload.fps)
        self.uuid2timestamps[uuid].append(time.time())

    def _remove_expired(self, uuid: str):
        timestamps = self.uuid2timestamps.get(uuid, [])

        for idx in range(len(timestamps)):
            elapsed = time.time() - timestamps[0]
            # print(idx, elapsed, self.model_timeout_secs)
            if elapsed < self.model_timeout_secs:
                break

            self.uuid2throughput[uuid].pop(0)
            self.uuid2timestamps[uuid].pop(0)

        if not self.uuid2throughput[uuid]:
            self.uuid2throughput.pop(uuid)
            self.uuid2timestamps.pop(uuid)
            # self.uuid2pipelineuuid.pop(uuid)
            # self.uuid2sessionuuid.pop(uuid)

            # print(f"Removed workload {uuid} from frontend {self.frontend}")

    def remove_expired(self):
        for uuid in list(self.uuid2throughput.keys()):
            self._remove_expired(uuid)

    def get_workloads(self) -> Dict[str, float]:
        data = {}

        self.remove_expired()

        for uuid in self.uuid2throughput:
            fps = np.sum(self.uuid2throughput[uuid])
            if fps > 0:
                duration = max(1, time.time() - self.uuid2timestamps[uuid][0])
                data[uuid] = float(fps) / duration

        return data


class NxsSimpleWorkloadManagerPolicy(NxsBaseWorkloadManagerPolicy):
    def __init__(self, args: NxsWorkloadManagerArgs) -> None:
        super().__init__(args)
        # self.frontend2workloads:Dict[str, FrontendWorkloads] = {}
        self.uuid2throughput: Dict[str, List[float]] = {}
        self.uuid2timestamps: Dict[str, List[float]] = {}

        self.pinned_workloads: Dict[str, float] = {}

        self.t0 = time.time()

    def add_workload(self, workload: FrontendModelPipelineWorkloadReport) -> bool:
        is_new_workload = False

        uuid = f"{workload.pipeline_uuid}_{workload.session_uuid}"
        if uuid not in self.uuid2throughput:
            self.uuid2throughput[uuid] = []
            self.uuid2timestamps[uuid] = []
            # self.uuid2pipelineuuid[uuid] = workload.pipeline_uuid
            # self.uuid2sessionuuid[uuid] = workload.session_uuid

            is_new_workload = True

            self._log(f"Added new workload {uuid}")

        self.uuid2throughput[uuid].append(workload.fps)
        self.uuid2timestamps[uuid].append(time.time())

        return is_new_workload

    def _remove_expired(self, uuid: str):
        timestamps = self.uuid2timestamps.get(uuid, [])

        for idx in range(len(timestamps)):
            elapsed = time.time() - timestamps[0]
            # print(idx, elapsed, self.model_timeout_secs)
            if elapsed < self.args.model_timeout_secs:
                break

            self.uuid2throughput[uuid].pop(0)
            self.uuid2timestamps[uuid].pop(0)

        if not self.uuid2throughput[uuid]:
            self.uuid2throughput.pop(uuid)
            self.uuid2timestamps.pop(uuid)
            # self.uuid2pipelineuuid.pop(uuid)
            # self.uuid2sessionuuid.pop(uuid)

            # print(f"Removed workload {uuid}")
            self._log(f"Removed workload {uuid}")

    def remove_expired(self):
        for uuid in list(self.uuid2throughput.keys()):
            self._remove_expired(uuid)

    def get_workloads(self) -> Dict[str, float]:
        data = {}

        self.remove_expired()

        for uuid in self.uuid2throughput:
            fps = np.sum(self.uuid2throughput[uuid])
            if fps > 0:
                duration = max(1, time.time() - self.uuid2timestamps[uuid][0])
                data[uuid] = float(fps) / duration

        return data

    def generate_scheduling_msgs(
        self,
    ) -> List[FrontendModelPipelineWorkloadReport]:
        workloads_dict = {}
        msgs = []

        frontend_workloads_dict = self.get_workloads()
        for uuid in frontend_workloads_dict:
            if uuid not in workloads_dict:
                workloads_dict[uuid] = 0
            workloads_dict[uuid] += frontend_workloads_dict[uuid]

        # process pinned_workloads
        for uuid in self.pinned_workloads:
            if uuid not in workloads_dict:
                workloads_dict[uuid] = 0
            workloads_dict[uuid] += self.pinned_workloads[uuid]

        for uuid in workloads_dict:
            # print(uuid)
            pipeline_uuid, session_uuid = uuid.split("_")
            msg = FrontendModelPipelineWorkloadReport(
                pipeline_uuid=pipeline_uuid,
                session_uuid=session_uuid,
                fps=workloads_dict[uuid],
            )
            msgs.append(msg)

        return msgs

    def process_msgs(
        self, msgs: List[NxsMsgReportInputWorkloads]
    ) -> Tuple[bool, List[FrontendModelPipelineWorkloadReport]]:
        to_schedule = False
        scheduling_msgs = []

        for msg in msgs:
            # print(msg)
            if msg.type == NxsMsgType.REGISTER_WORKLOADS:
                # frontend_name = msg.data.frontend_name

                for workload in msg.data.workload_reports:
                    if (
                        self.add_workload(workload)
                        and self.args.enable_instant_scheduling
                    ):
                        to_schedule = True
            elif msg.type == NxsMsgType.PIN_WORKLOADS:
                pin_msg: NxsMsgPinWorkload = msg
                uuid = f"{pin_msg.pipeline_uuid}_{pin_msg.session_uuid}"
                self.pinned_workloads[uuid] = pin_msg.fps
                to_schedule = True
                self._log(
                    f"Pinning workload - pipeline_uuid: {pin_msg.pipeline_uuid} - session_uuid: {pin_msg.session_uuid} - fps: {pin_msg.fps}"
                )
            elif msg.type == NxsMsgType.UNPIN_WORKLOADS:
                unpin_msg: NxsMsgUnpinWorkload = msg
                uuid = f"{unpin_msg.pipeline_uuid}_{unpin_msg.session_uuid}"
                if uuid in self.pinned_workloads:
                    self.pinned_workloads.pop(uuid)
                    self._log(
                        f"Unpinning workload - pipeline_uuid: {unpin_msg.pipeline_uuid} - session_uuid: {unpin_msg.session_uuid}"
                    )

        if time.time() - self.t0 > self.args.report_workloads_interval:
            to_schedule = True

        if to_schedule:
            # generate scheduling data
            scheduling_msgs = self.generate_scheduling_msgs()
            # print(scheduling_msgs)
            self.t0 = time.time()

        return to_schedule, scheduling_msgs
