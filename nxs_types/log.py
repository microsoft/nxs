import numpy as np
from enum import Enum
from typing import Dict, List, Optional
from nxs_types import DataModel
from nxs_types.backend import NxsBackendType
from nxs_types.scheduling_data import (
    NxsSchedulingPerBackendPlan,
    NxsSchedulingRequest,
    NxsUnschedulingPerBackendPlan,
)


class NxsBackendCmodelThroughputLog(DataModel):
    # backend_name: str
    model_uuid: str
    total_reqs: int
    fps: float
    latency_mean: float = 0
    latency_min: float = 0
    latency_max: float = 0
    extra: Dict[str, str] = {}


class NxsBackendThroughputLog(DataModel):
    backend_name: str
    backend_type: NxsBackendType
    model_logs: List[NxsBackendCmodelThroughputLog] = []


class SimplifiedNxsSchedulingRequest(DataModel):
    pipeline_uuid: str
    session_uuid: str = "global"
    cmodel_uuid_list: List[str] = []
    requested_fps: float = 0


class SimplifiedNxsSchedulingPerBackendPlan(DataModel):
    backend_name: str
    cmodel_uuid_list: List[str] = []


class NxsSchedulerLog(DataModel):
    scheduling_requests: List[SimplifiedNxsSchedulingRequest] = []
    scheduling_plans: List[SimplifiedNxsSchedulingPerBackendPlan] = []
