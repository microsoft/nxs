import cv2
import numpy as np
from typing import Dict, Tuple
from nxs_types.model import NxsModel


def scale_coords(img1_shape, coords, img0_shape, ratio_pad=None):
    # Rescale coords (xyxy) from img1_shape to img0_shape
    if ratio_pad is None:  # calculate from img0_shape
        gain = min(
            img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1]
        )  # gain  = old / new
        pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (
            img1_shape[0] - img0_shape[0] * gain
        ) / 2  # wh padding
    else:
        gain = ratio_pad[0][0]
        pad = ratio_pad[1]

    coords[0] -= pad[0]  # x padding
    coords[2] -= pad[0]  # x padding
    coords[1] -= pad[1]  # y padding
    coords[3] -= pad[1]  # y padding
    coords[:4] /= gain
    clip_coords(coords, img0_shape)
    return coords


def clip_coords(boxes, shape):
    # Clip bounding xyxy bounding boxes to image shape (height, width)
    boxes[0] = boxes[0].clip(0, shape[1])  # x1, x2
    boxes[2] = boxes[2].clip(0, shape[1])  # x1, x2
    boxes[1] = boxes[1].clip(0, shape[0])  # y1, y2
    boxes[3] = boxes[3].clip(0, shape[0])  # y1, y2


def postprocessing(
    data, postproc_params, component_model: NxsModel, metadata: Dict = {}
):
    score_thresh = postproc_params.get("score_thresh", 0.25)
    # nms_thresh = postproc_params.get("nms_thresh", 0.45)
    classes = component_model.model_desc.class_names

    model_w = component_model.model_desc.inputs[0].shape[3]
    model_h = component_model.model_desc.inputs[0].shape[2]

    img_w = metadata["original_width"]
    img_h = metadata["original_height"]

    dets = data["output"]

    object_list = []
    for det in dets:
        # make sure this works with both fp16/fp32 models
        det = np.array(det).astype(np.float32)
        score = det[4]

        if score < score_thresh:
            continue

        class_idx = int(det[5])

        box = scale_coords([model_h, model_w], det[:4], [img_h, img_w]).round()

        rleft = box[0] / img_w
        rright = box[2] / img_w
        rtop = box[1] / img_h
        rbottom = box[3] / img_h
        left, top, right, bottom = np.array(box, dtype=np.int32)

        class_name = f"class_{class_idx}"
        if len(classes) > class_idx:
            class_name = classes[class_idx]

        # classid is yolo class index, convert it to ssd_class_id (or coco_class_id)
        object_list.append(
            {
                "class_name": class_name,
                "class_id": int(class_idx),
                "score": float(score),
                #'rel_bbox'   : [float(rel_top), float(rel_left), float(rel_right), float(rel_bottom)],
                "rel_bbox": {
                    "left": rleft,
                    "top": rtop,
                    "right": rright,
                    "bottom": rbottom,
                },
                #'bbox' : [top, left, right, bottom],
                "bbox": {
                    "left": left,
                    "top": top,
                    "right": right,
                    "bottom": bottom,
                },
            }
        )

    return {"detections": object_list}
