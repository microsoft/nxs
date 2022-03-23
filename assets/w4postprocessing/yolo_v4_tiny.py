import cv2
import numpy as np
from typing import Dict, Tuple
from nxs_types.model import NxsModel


def nms_cpu(boxes, confs, nms_thresh=0.5, min_mode=False):
    # print(boxes.shape)
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1) * (y2 - y1)
    order = confs.argsort()[::-1]

    keep = []
    while order.size > 0:
        idx_self = order[0]
        idx_other = order[1:]

        keep.append(idx_self)

        xx1 = np.maximum(x1[idx_self], x1[idx_other])
        yy1 = np.maximum(y1[idx_self], y1[idx_other])
        xx2 = np.minimum(x2[idx_self], x2[idx_other])
        yy2 = np.minimum(y2[idx_self], y2[idx_other])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h

        if min_mode:
            over = inter / np.minimum(areas[order[0]], areas[order[1:]])
        else:
            over = inter / (areas[order[0]] + areas[order[1:]] - inter)

        inds = np.where(over <= nms_thresh)[0]
        order = order[inds + 1]

    return np.array(keep)


def post_processing(conf_thresh, nms_thresh, box_array, confs):
    # box_array: [batch, num, 1, 4]
    # confs: [batch, num, num_classes]
    num_classes = confs.shape[2]

    # [batch, num, 4]
    box_array = box_array[:, :, 0]

    # [batch, num, num_classes] --> [batch, num]
    max_conf = np.max(confs, axis=2)
    max_id = np.argmax(confs, axis=2)

    bboxes_batch = []
    for i in range(box_array.shape[0]):

        argwhere = max_conf[i] > conf_thresh
        l_box_array = box_array[i, argwhere, :]
        l_max_conf = max_conf[i, argwhere]
        l_max_id = max_id[i, argwhere]

        bboxes = []
        # nms for each class
        for j in range(num_classes):

            cls_argwhere = l_max_id == j
            ll_box_array = l_box_array[cls_argwhere, :]
            ll_max_conf = l_max_conf[cls_argwhere]
            ll_max_id = l_max_id[cls_argwhere]

            keep = nms_cpu(ll_box_array, ll_max_conf, nms_thresh)

            if keep.size > 0:
                ll_box_array = ll_box_array[keep, :]
                ll_max_conf = ll_max_conf[keep]
                ll_max_id = ll_max_id[keep]

                for k in range(ll_box_array.shape[0]):
                    bboxes.append(
                        [
                            ll_box_array[k, 0],
                            ll_box_array[k, 1],
                            ll_box_array[k, 2],
                            ll_box_array[k, 3],
                            ll_max_conf[k],
                            ll_max_conf[k],
                            ll_max_id[k],
                        ]
                    )

        bboxes_batch.append(bboxes)

    return bboxes_batch[0]


def postprocessing(
    data, postproc_params, component_model: NxsModel, metadata: Dict = {}
):

    score_thresh = postproc_params.get("score_thresh", 0.4)
    nms_thresh = postproc_params.get("nms_thresh", 0.6)
    classes = component_model.model_desc.class_names

    confs = data["confs"]
    boxes = data["boxes"]

    if len(confs.shape) == 2:
        confs = np.expand_dims(confs, axis=0)
    if len(boxes.shape) == 3:
        boxes = np.expand_dims(boxes, axis=0)

    results = post_processing(score_thresh, nms_thresh, boxes, confs)

    object_list = []
    for box_info in results:
        rel_left, rel_top, rel_right, rel_bottom, score, _, classId = box_info

        top = int(rel_top * metadata["original_height"])
        left = int(rel_left * metadata["original_width"])
        right = int(rel_right * metadata["original_width"])
        bottom = int(rel_bottom * metadata["original_height"])

        class_name = f"class_{classId}"
        if len(classes) > classId:
            class_name = classes[classId]

        # classid is yolo class index, convert it to ssd_class_id (or coco_class_id)
        object_list.append(
            {
                "class_name": class_name,
                "class_id": int(classId),
                "score": float(score),
                #'rel_bbox'   : [float(rel_top), float(rel_left), float(rel_right), float(rel_bottom)],
                "rel_bbox": {
                    "left": float(rel_left),
                    "top": float(rel_top),
                    "right": float(rel_right),
                    "bottom": float(rel_bottom),
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
