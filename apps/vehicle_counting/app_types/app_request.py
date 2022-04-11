from enum import Enum
from typing import List, Optional
from nxs_types import DataModel

class TrackableClass(str, Enum):
    CAR = "car"
    MOTORCYCLE = "motorcycle"
    BUS = "bus"
    TRUCK = "truck"

class RequestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"


class TrackingPoint(DataModel):
    x: float
    y: float


class TrackingRoi(DataModel):
    points: List[TrackingPoint]


class TrackingLine(DataModel):
    p0: TrackingPoint
    p1: TrackingPoint


class TrackingRegion(DataModel):
    roi: TrackingRoi
    line: TrackingLine


class TrackingAppRequest(DataModel):
    video_url: str
    regions: List[TrackingRegion]
    skip_frames: Optional[int] = 2
    tracking_classes: Optional[List[TrackableClass]] = [
        TrackableClass.CAR,
        #TrackableClass.MOTORCYCLE,
        TrackableClass.BUS,
        #TrackableClass.TRUCK,
    ]
    count_interval_secs: Optional[int] = 900
    debug: Optional[bool] = False


class TrackingAppResponse(DataModel):
    video_uuid: str


class InDbTrackingAppRequest(TrackingAppRequest):
    video_uuid: str
    status: RequestStatus = RequestStatus.PENDING


class TrackingCountPerClass(DataModel):
    class_name: str
    count: int


class TrackingCountPerRoi(DataModel):
    roi_idx: int
    counts: List[TrackingCountPerClass]


class TrackingCountResult(DataModel):
    timestamp: float
    counts: List[TrackingCountPerRoi]


class VisualizationResult(DataModel):
    from_ts: float
    to_ts: float
    visualized_frames: List[str]
