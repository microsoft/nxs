from typing import Dict, Tuple
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


def _example_wh_to_size(target_size, cfg):
    w, h = target_size
    target_sz = np.array([w, h])

    wc_z = target_sz[0] + cfg.context_amount * sum(target_sz)
    hc_z = target_sz[1] + cfg.context_amount * sum(target_sz)
    s_z = round(np.sqrt(wc_z * hc_z))
    return s_z


def _search_wh_to_size(target_size, cfg):
    w, h = target_size
    target_sz = np.array([w, h])

    wc_x = target_sz[0] + cfg.context_amount * sum(target_sz)
    hc_x = target_sz[1] + cfg.context_amount * sum(target_sz)
    s_x = np.sqrt(wc_x * hc_x)
    scale_x = cfg.exemplar_size / s_x
    d_search = (cfg.search_size - cfg.exemplar_size) / 2
    pad = d_search / scale_x
    s_x = s_x + 2 * pad

    return s_x, scale_x


# create global vars
cfg = Config()
anchors, window = tracking_init(cfg)


def preprocessing(
    decoded_inputs_dict,
    preproc_params,
    component_model: NxsModel,
    metadata: Dict = {},
) -> Tuple[Dict, bool]:

    # init_img = decoded_inputs_dict["examplar_img"]
    examplar_img = decoded_inputs_dict["examplar_img"]
    cur_img = decoded_inputs_dict["img"]
    # init_bbox = decoded_inputs_dict["init_bbox"]
    prev_bbox = decoded_inputs_dict["prev_bbox"]

    # x, y, w, h = [
    #     init_bbox[0],
    #     init_bbox[1],
    #     init_bbox[2] - init_bbox[0],
    #     init_bbox[3] - init_bbox[1],
    # ]
    # target_pos1 = np.array([x + w / 2, y + h / 2])
    # target_size1 = np.array([w, h])

    # example1_size_ = _example_wh_to_size(target_size1, cfg)
    # processed_example1 = preprocess(
    #     init_img, target_pos1, example1_size_, cfg.exemplar_size
    # )

    x, y, w, h = [
        prev_bbox[0],
        prev_bbox[1],
        prev_bbox[2] - prev_bbox[0],
        prev_bbox[3] - prev_bbox[1],
    ]
    target_pos1 = np.array([x + w / 2, y + h / 2])
    target_size1 = np.array([w, h])

    search1_size_, search1_scale = _search_wh_to_size(target_size1, cfg)
    processed_search1 = preprocess(
        cur_img, target_pos1, round(search1_size_), cfg.search_size
    )

    metadata["target_size1"] = target_size1
    metadata["target_pos1"] = target_pos1
    metadata["search1_scale"] = search1_scale
    metadata["cur_img"] = cur_img

    return {
        "Placeholder": [processed_search1.astype(np.float32)],
        "Placeholder_1": [examplar_img.astype(np.float32)],
    }, False
