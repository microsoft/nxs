from typing import Dict
import numpy as np
import math
import cv2

from nxs_types.model import NxsModel


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class Config:
    search_size = 255
    exemplar_size = 127
    base_size = 8
    stride = 8
    score_size = (search_size - exemplar_size) // stride + base_size + 1

    penalty_k = 0.04
    window_influence = 0.4
    lr = 1.0
    windowing = "cosine"
    context_amount = 0.5

    # Anchors.
    anchor = AttrDict(
        {
            "stride": 8,
            "ratios": [0.33, 0.5, 1, 2, 3],
            "scales": [8],
            "num_anchors": 5,
        }
    )


def generate_anchors(cfg):
    anchors = np.zeros((cfg.num_anchors, 4), dtype=np.float32)

    size = cfg.stride * cfg.stride
    count = 0
    for r in cfg.ratios:

        ws = int(math.sqrt(size * 1.0 / r))
        hs = int(ws * r)

        for s in cfg.scales:

            w = ws * s
            h = hs * s
            anchors[count] = 0.5 * np.array([-w, -h, w, h])
            count += 1

    return anchors


def prepare_anchors(anchor, cfg):
    x1, y1, x2, y2 = anchor[:, 0], anchor[:, 1], anchor[:, 2], anchor[:, 3]
    anchor = np.stack([(x1 + x2) * 0.5, (y1 + y2) * 0.5, x2 - x1, y2 - y1], 1)

    total_stride = cfg.stride
    anchor_num = anchor.shape[0]

    anchor = np.tile(anchor, cfg.score_size * cfg.score_size).reshape((-1, 4))
    b = -(cfg.score_size // 2) * total_stride
    xx, yy = np.meshgrid(
        [b + total_stride * dx for dx in range(cfg.score_size)],
        [b + total_stride * dy for dy in range(cfg.score_size)],
    )
    xx, yy = (
        np.tile(xx.flatten(), (anchor_num, 1)).flatten(),
        np.tile(yy.flatten(), (anchor_num, 1)).flatten(),
    )
    anchor[:, 0], anchor[:, 1] = xx.astype(np.float32), yy.astype(np.float32)
    return anchor


def init_anchors(cfg):
    anchors = generate_anchors(cfg.anchor)
    anchors = prepare_anchors(anchors, cfg)
    return anchors


def tracking_init(cfg):
    anchors = init_anchors(cfg)
    window = np.outer(np.hanning(cfg.score_size), np.hanning(cfg.score_size))
    window = np.tile(window.flatten(), cfg.anchor.num_anchors)
    return anchors, window


def _create_polygon(loc, size):
    loc = np.array(
        [
            [loc[0] - size[0] // 2, loc[1] - size[1] // 2],
            [loc[0] - size[0] // 2, loc[1] + size[1] // 2],
            [loc[0] + size[0] // 2, loc[1] + size[1] // 2],
            [loc[0] + size[0] // 2, loc[1] - size[1] // 2],
        ],
        dtype=np.int32,
    )
    loc = loc.reshape(-1, 1, 2)
    return loc


def softmax(x):
    adjusted_x = x - np.amax(x, axis=-1, keepdims=-1)
    numerator = np.exp(adjusted_x)
    denominator = np.sum(numerator, axis=-1, keepdims=-1)
    return numerator / denominator


def update_bounding_box(
    image,
    scores,
    bboxes,
    anchors,
    window,
    target_pos,
    target_size,
    search_scale,
    cfg,
):
    bboxes = np.transpose(bboxes, [3, 1, 2, 0]).reshape(4, -1)
    scores = softmax(np.transpose(scores, [3, 1, 2, 0]).reshape(2, -1).T)[:, 1]

    bboxes[0, :] = bboxes[0, :] * anchors[:, 2] + anchors[:, 0]
    bboxes[1, :] = bboxes[1, :] * anchors[:, 3] + anchors[:, 1]
    bboxes[2, :] = np.exp(bboxes[2, :]) * anchors[:, 2]
    bboxes[3, :] = np.exp(bboxes[3, :]) * anchors[:, 3]

    def change(r):
        return np.maximum(r, 1.0 / r)

    def sz(w, h):
        pad = (w + h) * 0.5
        sz2 = (w + pad) * (h + pad)
        return np.sqrt(sz2)

    def sz_wh(wh):
        pad = (wh[0] + wh[1]) * 0.5
        sz2 = (wh[0] + pad) * (wh[1] + pad)
        return np.sqrt(sz2)

    # size penalty
    target_sz_in_crop = target_size * search_scale

    s_c = change(sz(bboxes[2, :], bboxes[3, :]) / (sz_wh(target_sz_in_crop)))
    r_c = change(
        (target_sz_in_crop[0] / target_sz_in_crop[1])
        / (bboxes[2, :] / bboxes[3, :])
    )

    penalty = np.exp(-(r_c * s_c - 1) * cfg.penalty_k)
    pscore = penalty * scores

    # cos window (motion model)
    pscore = (
        pscore * (1 - cfg.window_influence) + window * cfg.window_influence
    )
    best_pscore_id = np.argmax(pscore)

    pred_in_crop = bboxes[:, best_pscore_id] / search_scale
    lr = penalty[best_pscore_id] * scores[best_pscore_id] * cfg.lr
    # print(lr, pred_in_crop)
    res_x = pred_in_crop[0] + target_pos[0]
    res_y = pred_in_crop[1] + target_pos[1]

    res_w = target_size[0] * (1 - lr) + pred_in_crop[2] * lr
    res_h = target_size[1] * (1 - lr) + pred_in_crop[3] * lr

    target_pos = np.array([res_x, res_y])
    target_size = np.array([res_w, res_h])

    h, w, _ = image.shape if len(image.shape) == 3 else image[0].shape

    target_pos[0] = max(0, min(w, target_pos[0]))
    target_pos[1] = max(0, min(h, target_pos[1]))
    target_size[0] = max(10, min(w, target_size[0]))
    target_size[1] = max(10, min(h, target_size[1]))

    return target_pos, target_size, np.max(pscore)


# create global vars
cfg = Config()
anchors, window = tracking_init(cfg)


def postprocessing(
    data, postproc_params, component_model: NxsModel, metadata: Dict = {}
):
    bbox = data["BBox/Head/conv2d_1/BiasAdd"]
    score = data["Score/Head/conv2d_1/BiasAdd"]

    cur_img = metadata.pop("cur_img")
    h, w = cur_img.shape[:2]
    target_pos1 = metadata.pop("target_pos1")
    target_size1 = metadata.pop("target_size1")
    search1_scale = metadata.pop("search1_scale")

    target_pos1, target_size1, best_score1 = update_bounding_box(
        cur_img,
        np.expand_dims(score, axis=0),
        np.expand_dims(np.array(bbox), axis=0),
        anchors,
        window,
        target_pos1,
        target_size1,
        search1_scale,
        cfg,
    )

    polygon = _create_polygon(target_pos1, target_size1)
    polygon = polygon.reshape((-1, 2))

    left, top, right, bottom = (
        polygon[0][0],
        polygon[0][1],
        polygon[2][0],
        polygon[2][1],
    )

    left = max(0, left)
    top = max(0, top)
    right = max(0, right)
    bottom = max(0, bottom)

    return {
        "detections": [
            {
                "class_name": "track",
                "class_id": int(0),
                "score": float(best_score1),
                "rel_bbox": {
                    "left": float(left) / w,
                    "top": float(top) / h,
                    "right": float(right) / w,
                    "bottom": float(bottom) / h,
                },
                "bbox": {
                    "left": left,
                    "top": top,
                    "right": right,
                    "bottom": bottom,
                },
            }
        ]
    }
