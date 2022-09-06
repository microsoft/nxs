import json
import pickle
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import requests
from nxs_types.infer import (
    NxsInferInput,
    NxsInferInputType,
    NxsInferStatus,
    NxsTensorsInferRequest,
)
from nxs_types.infer_result import (
    NxsInferDetectorBBoxLocation,
    NxsInferDetectorResult,
    NxsInferResult,
)
from shapely.geometry import Point, Polygon


def send_post_bytes_request(url, payload: bytes, headers={}, timeout=60000):
    return requests.post(url, data=payload, headers=headers, timeout=timeout)


def run_detector(
    infer_url: str,
    model_uuid: str,
    img: np.ndarray,
    api_key: str = "",
    num_retries: int = 5,
    logging_fn: Any = None,
) -> NxsInferResult:
    payload = pickle.dumps(
        NxsTensorsInferRequest(
            pipeline_uuid=model_uuid,
            session_uuid="global",
            inputs=[
                NxsInferInput(
                    name="images",
                    type=NxsInferInputType.ENCODED_IMAGE,
                    data=cv2.imencode(".jpg", img)[1].tostring(),
                )
            ],
        )
    )

    headers = {}
    if api_key != "":
        headers["x-api-key"] = api_key

    for retry in range(num_retries):
        try:
            r = send_post_bytes_request(infer_url, payload, headers)
            infer_result = NxsInferResult(**(json.loads(r.content)))
            if infer_result.status == NxsInferStatus.FAILED:
                raise ValueError(infer_result.error_msgs[0])
            return infer_result
        except Exception as e:
            if logging_fn != None:
                logging_fn("[RUN_DETECTOR]: {}".format(str(e)))

            if retry == num_retries - 1:
                raise e

            time.sleep(0.1 * (retry + 1))


def run_tracker(
    infer_url: str,
    model_uuid: str,
    template: np.ndarray,
    img: np.ndarray,
    prev_bbox: NxsInferDetectorBBoxLocation,
    api_key: str = "",
    num_retries: int = 5,
    logging_fn: Any = None,
) -> NxsInferResult:
    payload = pickle.dumps(
        NxsTensorsInferRequest(
            pipeline_uuid=model_uuid,
            session_uuid="global",
            inputs=[
                NxsInferInput(
                    name="img",
                    type=NxsInferInputType.ENCODED_IMAGE,
                    data=cv2.imencode(".jpg", img)[1].tostring(),
                ),
                NxsInferInput(
                    name="examplar_img",
                    type=NxsInferInputType.ENCODED_IMAGE,
                    data=cv2.imencode(".jpg", template)[1].tostring(),
                ),
                NxsInferInput(
                    name="prev_bbox",
                    type=NxsInferInputType.PICKLED_DATA,
                    data=pickle.dumps(
                        [
                            prev_bbox.left,
                            prev_bbox.top,
                            prev_bbox.right,
                            prev_bbox.bottom,
                        ]
                    ),
                ),
            ],
        )
    )

    headers = {}
    if api_key != "":
        headers["x-api-key"] = api_key

    for retry in range(num_retries):
        try:
            r = send_post_bytes_request(infer_url, payload, headers)
            infer_result = NxsInferResult(**(json.loads(r.content)))
            if infer_result.status == NxsInferStatus.FAILED:
                raise ValueError(infer_result.error_msgs[0])
            return infer_result
        except Exception as e:
            if logging_fn != None:
                logging_fn("[RUN_TRACKER]: {}".format(str(e)))

            if retry == num_retries - 1:
                raise e

            time.sleep(0.1 * (retry + 1))


def _example_wh_to_size(target_size, context_amount=0.5):
    w, h = target_size
    target_sz = np.array([w, h])

    wc_z = target_sz[0] + context_amount * sum(target_sz)
    hc_z = target_sz[1] + context_amount * sum(target_sz)
    s_z = round(np.sqrt(wc_z * hc_z))
    return s_z


def preprocess(image, center, crop_size, output_size):
    image_size = image.shape
    c = (crop_size + 1) / 2
    context_xmin = round(center[0] - c)
    context_xmax = context_xmin + crop_size - 1
    context_ymin = round(center[1] - c)
    context_ymax = context_ymin + crop_size - 1
    left_pad = int(max(0.0, -context_xmin))
    top_pad = int(max(0.0, -context_ymin))
    right_pad = int(max(0.0, context_xmax - image_size[1] + 1))
    bottom_pad = int(max(0.0, context_ymax - image_size[0] + 1))

    context_xmin = context_xmin + left_pad
    context_xmax = context_xmax + left_pad
    context_ymin = context_ymin + top_pad
    context_ymax = context_ymax + top_pad

    avg_chans = np.mean(image, (0, 1))

    r, c, k = image.shape
    if any([top_pad, bottom_pad, left_pad, right_pad]):
        padded_im = np.zeros(
            (r + top_pad + bottom_pad, c + left_pad + right_pad, k), np.uint8
        )
        padded_im[top_pad : top_pad + r, left_pad : left_pad + c, :] = image
        if top_pad:
            padded_im[0:top_pad, left_pad : left_pad + c, :] = avg_chans
        if bottom_pad:
            padded_im[r + top_pad :, left_pad : left_pad + c, :] = avg_chans
        if left_pad:
            padded_im[:, 0:left_pad, :] = avg_chans
        if right_pad:
            padded_im[:, c + left_pad :, :] = avg_chans
        im_patch_original = padded_im[
            int(context_ymin) : int(context_ymax + 1),
            int(context_xmin) : int(context_xmax + 1),
            :,
        ]
    else:
        im_patch_original = image[
            int(context_ymin) : int(context_ymax + 1),
            int(context_xmin) : int(context_xmax + 1),
            :,
        ]
    if not np.array_equal(output_size, crop_size):
        im_patch = cv2.resize(im_patch_original, (output_size, output_size))
    else:
        im_patch = im_patch_original

    # im_patch = np.expand_dims(im_patch, 0)
    return im_patch


def preprocess_examplar(img, init_box):
    x, y, w, h = [
        init_box[0],
        init_box[1],
        init_box[2] - init_box[0],
        init_box[3] - init_box[1],
    ]
    template_pos = np.array([x + w / 2, y + h / 2])
    template_size = np.array([w, h])

    examplar_size_ = _example_wh_to_size(template_size)
    return preprocess(img, template_pos, examplar_size_, 127)


def compute_iou(
    bbox1: NxsInferDetectorBBoxLocation,
    bbox2: NxsInferDetectorBBoxLocation,
) -> float:
    x11, y11, x12, y12 = bbox1.left, bbox1.top, bbox1.right, bbox1.bottom
    x21, y21, x22, y22 = bbox2.left, bbox2.top, bbox2.right, bbox2.bottom

    xA = max(x11, x21)
    yA = max(y11, y21)
    xB = min(x12, x22)
    yB = min(y12, y22)

    interArea = max(0, xB - xA + 1e-9) * max(0, yB - yA + 1e-9)

    boxAArea = (x12 - x11) * (y12 - y11)
    boxBArea = (x22 - x21) * (y22 - y21)

    return interArea / (boxAArea + boxBArea - interArea)


def compute_area(bbox: NxsInferDetectorBBoxLocation) -> float:
    x11, y11, x12, y12 = bbox.left, bbox.top, bbox.right, bbox.bottom
    return (x12 - x11) * (y12 - y11)


@dataclass
class NxsPoint:
    x: int
    y: int


@dataclass
class NxsRoi:
    points: List[NxsPoint]

    def to_ndarray(self) -> np.ndarray:
        return np.array([[p.x, p.y] for p in self.points])


@dataclass
class NxsLine:
    p0: NxsPoint
    p1: NxsPoint


@dataclass
class NxsTrack:
    id: int
    class_name: str
    is_active: bool
    is_counted: bool
    start_frame_idx: int
    last_frame_idx: int
    templates: List[np.ndarray]
    dets: List[NxsInferDetectorResult]
    track: List[NxsInferDetectorBBoxLocation]
    track_scores: List[float]
    roi_idx: int
