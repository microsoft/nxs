from enum import Enum
from typing import List

from nxs_types import DataModel
from nxs_types.backend import BackendStat
from nxs_types.frontend import (
    FrontendModelPipelineWorkloadReport,
    FrontendWorkloadReport,
)
from nxs_types.scheduling_data import (
    NxsSchedulingPerBackendPlan,
    NxsUnschedulingPerBackendPlan,
)


class NxsMsgType(int, Enum):
    REPORT_HEARTBEAT = 0
    REGISTER_BACKEND = 1
    REGISTER_WORKLOAD = 2
    REGISTER_WORKLOADS = 3
    SCALE_MINIMUM_BACKENDS = 4
    REPORT_IN_WORKLOAD = 5
    REPORT_OUT_WORKLOAD = 6
    CHANGE_HEARTBEAT_INTERVAL = 7
    REQUEST_REREGISTER_BACKEND = 8
    SCHEDULE_PLAN = 9
    UNSCHEDULE_PLAN = 10
    REPORT_BACKEND_STATS = 11
    PIN_WORKLOADS = 12
    UNPIN_WORKLOADS = 13


class NxsMsgReportInputWorkloads(DataModel):
    type: NxsMsgType = NxsMsgType.REGISTER_WORKLOADS
    data: FrontendWorkloadReport


class NxsMsgRegisterWorkloads(DataModel):
    type: NxsMsgType = NxsMsgType.REGISTER_WORKLOADS
    workloads: List[FrontendModelPipelineWorkloadReport]


class NxsMsgPinWorkload(DataModel):
    type: NxsMsgType = NxsMsgType.PIN_WORKLOADS
    pipeline_uuid: str
    session_uuid: str
    fps: float


class NxsMsgUnpinWorkload(DataModel):
    type: NxsMsgType = NxsMsgType.UNPIN_WORKLOADS
    pipeline_uuid: str
    session_uuid: str


class NxsMsgRegisterBackend(DataModel):
    type: NxsMsgType = NxsMsgType.REGISTER_BACKEND
    backend_name: str
    backend_stat: BackendStat = None


class NxsMsgRequestRegisterBackend(DataModel):
    type: NxsMsgType = NxsMsgType.REQUEST_REREGISTER_BACKEND


class NxsMsgReportHeartbeat(DataModel):
    type: NxsMsgType = NxsMsgType.REPORT_HEARTBEAT
    backend_name: str
    backend_stat: BackendStat = None


class NxsMsgChangeHeartbeatInterval(DataModel):
    type: NxsMsgType = NxsMsgType.CHANGE_HEARTBEAT_INTERVAL
    interval: int = 3


class NxsMsgSchedulePlans(DataModel):
    type: NxsMsgType = NxsMsgType.SCHEDULE_PLAN
    plan: NxsSchedulingPerBackendPlan


class NxsMsgUnschedulePlans(DataModel):
    type: NxsMsgType = NxsMsgType.UNSCHEDULE_PLAN
    plan: NxsUnschedulingPerBackendPlan


class NxsMsgBackendStatsReport(DataModel):
    type: NxsMsgType = NxsMsgType.REPORT_BACKEND_STATS
    backend_name: str
    data_in_json_str: str = "{}"
