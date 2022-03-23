from pydantic import Field
from enum import Enum
from typing import List, Optional
from nxs_types import DataModel

from nxs_libs.db import NxsDbType
from nxs_libs.storage import NxsStorageType
from nxs_libs.queue import NxsQueueType


class NxsBaseArgs(DataModel):
    # DB config
    db_type: NxsDbType = NxsDbType.MONGODB
    mongodb_uri: Optional[str]
    mongodb_db_name: Optional[str]
    db_use_shard_key: Optional[bool] = False
    db_shard_key: Optional[str] = "zone"
    db_shard_value: Optional[str] = "global"

    # Storage config
    storage_type: NxsStorageType = NxsStorageType.AzureBlobstorage
    storage_azure_blobstore_conn_str: Optional[str]
    storage_azure_blobstore_container_name: Optional[str]

    # Job Queue config
    job_queue_type: NxsQueueType = NxsQueueType.AZURE_QUEUE
    job_azure_queue_conn_str: Optional[str]
    job_azure_queue_name: Optional[str]
    job_redis_queue_address: Optional[str]
    job_redis_queue_port: Optional[int]
    job_redis_queue_password: Optional[str]
    job_redis_queue_use_ssl: Optional[bool]

    tmp_dir: str


class NxsApiArgs(NxsBaseArgs):
    frontend_name: str
    port: int
    workload_report_period_secs: float
    model_caching_timeout_secs: float = 30
    api_key: str = ""
    enable_benchmark_api: bool = False
    enable_v1_api: bool = False


class NxsSchedulerArgs(NxsBaseArgs):
    heartbeat_interval: float = 3
    model_timeout_secs: float = 180
    backend_timeout_secs: float = 30
    epoch_scheduling_interval_secs: float = 10
    enable_multi_models: bool = True
    enable_instant_scheduling: bool = True


class NxsBackendArgs(NxsBaseArgs):
    backend_name: str
    force_cpu: bool = False


class NxsWorkloadManagerArgs(NxsBaseArgs):
    model_timeout_secs: float
    report_workloads_interval: float
    enable_instant_scheduling: bool
