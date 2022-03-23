import numpy as np
from enum import Enum
from typing import List, Optional
from nxs_types import DataModel


class NxsInferInputType(str, Enum):
    NUMPY_TENSOR = "NUMPY_TENSOR"
    ENCODED_IMAGE = "ENCODED_IMAGE"
    PICKLED_DATA = "PICKLED_DATA"


class NxsInferStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class NxsInferInputBase(DataModel):
    pipeline_uuid: str
    session_uuid: str = "global"


class NxsInferImageInputFromUrl(NxsInferInputBase):
    url: str


class NxsInferBatchImageInputFromUrl(NxsInferInputBase):
    urls: List[str]


class NxsInferImageInputFromAzureBlobstore(NxsInferInputBase):
    blobstore_account_name: str
    blobstore_container_name: str
    blobstore_sas_token: str
    blobstore_path: str


class NxsInferBatchImageInputFromAzureBlobstore(NxsInferInputBase):
    blobstore_account_name: str
    blobstore_container_name: str
    blobstore_sas_token: str
    blobstore_paths: List[str]


class NxsInferTextInput(NxsInferInputBase):
    text: str


class NxsInferInput(DataModel):
    name: str
    type: NxsInferInputType
    data: bytes  # tensor should be pickled


class NxsInferRequestMetadata(DataModel):
    task_uuid: str
    session_uuid: str
    extra_preproc_params: Optional[str] = "{}"
    extra_transform_params: Optional[str] = "{}"
    extra_postproc_params: Optional[str] = "{}"
    exec_pipelines: List[str] = []

    # extra_params: Optional[str] = "{}" # used to sync between input/compute/output processes
    extra_params: Optional[bytes] = None
    carry_over_extras: Optional[
        bytes
    ] = None  # used to carry logs over multiple processing stages


class NxsInferRequest(NxsInferRequestMetadata):
    inputs: List[NxsInferInput]
    # extra_params: str = "{}"
    status: NxsInferStatus = NxsInferStatus.PENDING


class NxsTensorsInferRequest(DataModel):
    pipeline_uuid: str
    session_uuid: str = "global"
    extra_preproc_params: Optional[str] = "{}"
    extra_transform_params: Optional[str] = "{}"
    extra_postproc_params: Optional[str] = "{}"
    inputs: List[NxsInferInput]
