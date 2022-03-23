from pydantic import Field
from enum import Enum
from typing import Dict, List, Optional

from nxs_types import DataModel
from nxs_types.model import NxsPipelineInfo


class SchedulingRequest(DataModel):
    pipeline_info: NxsPipelineInfo
    session_uuid: str
    requested_fps: float


class NxsSchedulingRequest(DataModel):
    pipeline_info: NxsPipelineInfo
    session_uuid: str
    requested_fps: float


class NxsSchedulingPerComponentModelPlan(DataModel):
    model_uuid: str
    batch_size: int
    extra_info: str = "{}"


class NxsSchedulingPerCompositorymodelPlan(DataModel):
    model_uuid: str
    session_uuid_list: List[str]
    component_model_plans: List[NxsSchedulingPerComponentModelPlan]
    extra_info: str = "{}"


class NxsSchedulingPerBackendPlan(DataModel):
    backend_name: str
    compository_model_plans: List[NxsSchedulingPerCompositorymodelPlan]
    duty_cyles: List[float] = []
    extra_info: str = "{}"


class NxsUnschedulingPerCompositoryPlan(DataModel):
    model_uuid: str
    session_uuid_list: List[str]
    extra_info: str = "{}"


class NxsUnschedulingPerBackendPlan(DataModel):
    backend_name: str
    compository_model_plans: List[NxsUnschedulingPerCompositoryPlan]


class NxsSchedulingPlan(DataModel):
    scheduling: List[NxsSchedulingPerBackendPlan]
    unscheduling: List[NxsUnschedulingPerBackendPlan]
