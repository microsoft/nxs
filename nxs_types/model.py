from pydantic import Field
from enum import Enum
from typing import Dict, List, Optional

from nxs_types import DataModel


class Framework(str, Enum):
    ONNX = "onnx"
    TVM = "tvm"
    BATCHED_TVM = "batched_tvm"
    TF_PB = "tf_pb"


class TensorType(str, Enum):
    UINT8 = "uint8"
    FLOAT16 = "float16"
    FLOAT32 = "float32"
    INT32 = "int32"
    INT64 = "int64"


class InputClass(str, Enum):
    IMAGE = "image"
    TENSOR = "tensor"
    TEXT = "text"


class ModelType(str, Enum):
    SINGLE = "single"
    COMPOSITE = "composite"


class ModelPreprocessing(str, Enum):
    RAW = "raw"


class ModelPostprocessing(str, Enum):
    RAW = "raw"
    W4_CLASSIFIER_V1 = "w4_classifier_v1"
    W4_DETECTOR_V1 = "w4_detector_v1"


class W4ModelType(str, Enum):
    CLASSIFIER = "classifier"
    DETECTOR = "detector"


class ModelStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class PipelineOutputType(str, Enum):
    CLASSIFICATION = "classification"
    DETECTION = "detection"
    OCR = "ocr"
    EMBEDDING = "embedding"
    CUSTOM = "custom"


class LatencyMeasurement(DataModel):
    mean: float
    std: float
    min: float
    max: float


class ProfileUnit(DataModel):
    batch_size: int
    fps: float
    latency_e2e: LatencyMeasurement
    gpu_mem_usage: float


class InputNorm(DataModel):
    use_nchw: Optional[bool] = True
    use_rgb: Optional[bool] = True
    mean_r: Optional[float] = 0
    mean_g: Optional[float] = 0
    mean_b: Optional[float] = 0
    std_r: Optional[float] = 1.0
    std_g: Optional[float] = 1.0
    std_b: Optional[float] = 1.0
    extra_params: Optional[str] = "{}"


class ModelInput(DataModel):
    name: str
    shape: List[int]
    dtype: TensorType = TensorType.FLOAT32
    dclass: Optional[InputClass] = InputClass.IMAGE
    norm: Optional[InputNorm] = None


class ModelOutput(DataModel):
    name: str
    shape: Optional[List[int]] = []
    dtype: Optional[TensorType] = TensorType.FLOAT32


class ModelDescription(DataModel):
    inputs: List[ModelInput]
    outputs: List[ModelOutput]
    class_names: List[str] = []

    preprocessing_name: str
    postprocessing_name: str
    transforming_name: str = "none"

    extra_preprocessing_metadata: Optional[str] = "{}"
    extra_postprocessing_metadata: Optional[str] = "{}"
    extra_transforming_metadata: Optional[str] = "{}"


class NxsBaseModel(DataModel):
    user_name: str
    model_name: str
    framework: Framework
    model_desc: ModelDescription
    profile: List[ProfileUnit]
    use_gpu: bool = False
    batching: bool = True
    cross_requests_batching: bool = True
    is_public: bool = False


class NxsModel(NxsBaseModel):
    model_uuid: str
    model_status: ModelStatus = ModelStatus.VALID
    created_timestamp: Optional[float] = None
    created_time: Optional[str] = ""
    model_type: ModelType = ModelType.SINGLE
    collocated_model_uuids: List[str] = []
    num_request_pullers: Optional[int] = 1
    num_preprocessors: Optional[int] = 1
    num_postprocessors: Optional[int] = 1


class NxsModelRegistrationRequest(NxsBaseModel):
    url: str = ""
    preproc_url: str = ""
    postproc_url: str = ""
    transfrom_url: str = ""
    predefined_model_uuid: Optional[str] = ""
    num_request_pullers: Optional[int] = 1
    num_preprocessors: Optional[int] = 1
    num_postprocessors: Optional[int] = 1


class NxsColocatedModels(DataModel):
    colocated_model_uuids: List[str]


class PipelineExtraParamDescription(DataModel):
    param: str
    desc: str


class NxsPipelineRegistrationRequest(DataModel):
    user_name: str
    pipeline_groups: List[NxsColocatedModels]
    predefined_pipeline_uuid: Optional[str] = ""
    is_public: bool = False
    name: str = "N/A"
    accuracy: str = "N/A"
    params: str = "N/A"
    flops: str = "N/A"
    input_type: str = "N/A"
    description: str = "N/A"
    output_type: PipelineOutputType = PipelineOutputType.CUSTOM
    preproc_params: List[PipelineExtraParamDescription] = []
    postproc_params: List[PipelineExtraParamDescription] = []
    transform_params: List[PipelineExtraParamDescription] = []


class NxsPipelineDescription(DataModel):
    pipeline_uuid: str
    name: str = ""
    accuracy: str = "N/A"
    params: str = "N/A"
    flops: str = "N/A"
    input_type: str = "N/A"
    description: str = "N/A"
    output_type: PipelineOutputType = PipelineOutputType.CUSTOM
    preproc_params: List[PipelineExtraParamDescription] = []
    postproc_params: List[PipelineExtraParamDescription] = []
    transform_params: List[PipelineExtraParamDescription] = []


class NxsPipelineRegistrationResponse(DataModel):
    pipeline_uuid: str


class NxsW4ModelRegistrationRequest(DataModel):
    user_name: str
    model_name: str

    blobstore_account_name: str
    blobstore_container_name: str
    blobstore_sas_token: str
    blobstore_path: str

    # model_type: W4ModelType
    # use_gpu: bool = True


class NxsPipeline(DataModel):
    user_name: str
    pipeline_uuid: str
    pipeline: List[str]
    is_public: bool = False


class NxsModelRegistrationResponse(DataModel):
    # pipeline_uuid: str
    model_uuid: str


###### MODEL_RUNTIME ######
class NxsCompositoryModel(DataModel):
    main_model: NxsModel
    component_models: List[NxsModel] = []


class NxsPipelineInfo(NxsPipeline):
    models: List[NxsCompositoryModel]


class NxsPipelineRuntimeInfo(NxsPipelineInfo):
    last_alive_ts: float
