import cv2
import numpy as np
from typing import Dict, Tuple
from nxs_types.model import NxsModel


def letterbox(
    im,
    new_shape=(640, 640),
    color=(114, 114, 114),
    auto=True,
    scaleFill=False,
    scaleup=True,
    stride=32,
):
    # Resize and pad image while meeting stride-multiple constraints
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:  # only scale down, do not scale up (for better val mAP)
        r = min(r, 1.0)

    # Compute padding
    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = (
        new_shape[1] - new_unpad[0],
        new_shape[0] - new_unpad[1],
    )  # wh padding
    if auto:  # minimum rectangle
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)  # wh padding
    elif scaleFill:  # stretch
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = (
            new_shape[1] / shape[1],
            new_shape[0] / shape[0],
        )  # width, height ratios

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(
        im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
    )  # add border
    return im, ratio, (dw, dh)


def preprocessing(
    decoded_inputs_dict,
    preproc_params,
    component_model: NxsModel,
    metadata: Dict = {},
) -> Tuple[Dict, bool]:
    model_w = component_model.model_desc.inputs[0].shape[3]
    model_h = component_model.model_desc.inputs[0].shape[2]

    original_img = decoded_inputs_dict["images"]

    img, ratio, (dw, dh) = letterbox(
        original_img, new_shape=(model_w, model_h), stride=64, auto=False
    )
    img = img.astype(np.float32)
    img /= 255.0
    img = img[:, :, ::-1]
    img = np.transpose(img, (2, 0, 1))
    decoded_inputs_dict["images"] = [img]

    # add original size into metadata to be used in postprocessing step
    metadata["original_width"] = original_img.shape[1]
    metadata["original_height"] = original_img.shape[0]

    return decoded_inputs_dict, False
