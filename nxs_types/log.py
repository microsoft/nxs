import numpy as np
from enum import Enum
from typing import Dict, List, Optional
from nxs_types import DataModel
from nxs_types.backend import NxsBackendType


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
