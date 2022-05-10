from typing import Dict, List, Optional
from nxs_types import DataModel


class BasicResponse(DataModel):
    is_successful: bool = True


class FrontendModelPipelineWorkloadReport(DataModel):
    pipeline_uuid: str
    session_uuid: str
    fps: float
    metadata: str = "{}"


class FrontendWorkloadReport(DataModel):
    frontend_name: str
    workload_reports: List[FrontendModelPipelineWorkloadReport] = []
    metadata: str = "{}"


class FrontendTask(DataModel):
    pipeline_uuid: str
    session_uuid: Optional[str] = None


class TaskSummary(DataModel):
    pipeline_uuid: str
    session_uuid: str
    task_uuid: str
    start_ts: float = 0
    end_ts: float = 0
    e2e_latency: float = 0
    extra_data: str = "{}"


class ColocatedModel:
    atomic_model_uuids: List[str]


class RegisterCompositeModelRequest(DataModel):
    colocated_models: List[ColocatedModel]
