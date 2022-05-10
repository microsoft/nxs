from enum import Enum
from typing import List, Optional
from nxs_types import DataModel


class NxsBackendType(str, Enum):
    CPU = "cpu"
    GPU = "gpu"


class GpuInfo(DataModel):
    gpu_name: str
    gpu_total_mem: float
    gpu_available_mem: float


class BackendStat(DataModel):
    gpu_info: Optional[GpuInfo] = None
    extra_data: Optional[str] = "{}"


class BackendInfo(DataModel):
    backend_name: str
    state: BackendStat


class BackendCompositoryModelWorkloadReport(DataModel):
    compository_model_uuid: str
    session_uuid: str
    fps: str
    min_latency_ms: float
    avg_latency_ms: float
    max_latency_ms: float
    metadata: str = ""


class BackendOutWorkloadStateReport(DataModel):
    backend_name: str
    report: List[BackendCompositoryModelWorkloadReport] = []
