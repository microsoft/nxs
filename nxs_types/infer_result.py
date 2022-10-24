from enum import Enum
from typing import Dict, List, Optional

import numpy as np

from nxs_types import DataModel
from nxs_types.infer import NxsInferStatus


class NxsInferResultType(str, Enum):
    CLASSIFICATION = "classification"
    DETECTION = "detection"
    OCR = "ocr"
    CUSTOM = "custom"
    EMBEDDING = "embedding"
    SPEECH_TRANSCRIPTION = "speech_transcription"


class NxsInferDetectorBBoxLocation(DataModel):
    left: int
    top: int
    right: int
    bottom: int


class NxsInferDetectorRelBBoxLocation(DataModel):
    left: float
    top: float
    right: float
    bottom: float


class NxsInferDetectorResult(DataModel):
    class_name: str
    class_id: int
    score: float
    bbox: NxsInferDetectorBBoxLocation
    rel_bbox: NxsInferDetectorRelBBoxLocation


class NxsInferClassificationResult(DataModel):
    probabilities: Dict[str, float]
    best_score: float
    predicted_class_id: int
    predicted_class_name: str


class NxsPoint(DataModel):
    x: float
    y: float


class OcrCharResult(DataModel):
    text: str
    score: float
    bbox: List[NxsPoint] = []
    rbbox: List[NxsPoint] = []


class OcrWordResult(DataModel):
    text: str
    score: float
    bbox: List[NxsPoint] = []
    rbbox: List[NxsPoint] = []
    chars: List[OcrCharResult] = []


class NxsInferOcrResult(DataModel):
    text: str
    score: float
    line_bbox: List[NxsPoint]
    line_rbbox: List[NxsPoint]
    words: List[OcrWordResult] = []


class NxsInferEmbeddingResult(DataModel):
    embedding: List[float]
    length: int


class NxsInferSpeechTranscriptionSegment(DataModel):
    segment_id: int
    seek: float
    start: float
    end: float
    text: str
    avg_logprob: float = 0
    no_speech_prob: float = 0


class NxsInferSpeechTranscriptionResult(DataModel):
    text: str
    language: str = "en"
    segments: List[NxsInferSpeechTranscriptionSegment] = []


class NxsInferResult(DataModel):
    type: NxsInferResultType
    status: NxsInferStatus = NxsInferStatus.PENDING
    task_uuid: str
    error_msgs: List[str] = []
    detections: List[NxsInferDetectorResult] = []
    classification: Optional[NxsInferClassificationResult] = None
    ocr: Optional[List[NxsInferOcrResult]] = []
    embedding: Optional[NxsInferEmbeddingResult]
    speech_transcription: Optional[NxsInferSpeechTranscriptionResult]
    custom: str = ""
    e2e_latency: float = 0


class NxsInferResultWithMetadata(NxsInferResult):
    metadata: Optional[bytes] = None
