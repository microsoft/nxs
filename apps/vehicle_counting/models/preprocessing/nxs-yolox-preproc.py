import cv2
import numpy as np
from typing import Dict, Tuple
from nxs_types.model import NxsModel


def preproc(img, input_size, swap=(2, 0, 1)):
    if len(img.shape) == 3:
        padded_img = (
            np.ones((input_size[0], input_size[1], 3), dtype=np.uint8) * 114
        )
    else:
        padded_img = np.ones(input_size, dtype=np.uint8) * 114

    r = min(input_size[0] / img.shape[0], input_size[1] / img.shape[1])
    resized_img = cv2.resize(
        img,
        (int(img.shape[1] * r), int(img.shape[0] * r)),
        interpolation=cv2.INTER_LINEAR,
    ).astype(np.uint8)
    padded_img[: int(img.shape[0] * r), : int(img.shape[1] * r)] = resized_img

    padded_img = padded_img.transpose(swap).astype(np.float32)
    # padded_img = np.ascontiguousarray(padded_img, dtype=np.float32)
    return padded_img, r


def preprocessing(
    decoded_inputs_dict,
    preproc_params,
    component_model: NxsModel,
    metadata: Dict = {},
) -> Tuple[Dict, bool]:
    model_w = component_model.model_desc.inputs[0].shape[3]
    model_h = component_model.model_desc.inputs[0].shape[2]

    original_img = decoded_inputs_dict["images"]
    img, ratio = preproc(original_img, [model_h, model_w])

    metadata["original_width"] = original_img.shape[1]
    metadata["original_height"] = original_img.shape[0]
    metadata["ratio"] = ratio

    decoded_inputs_dict["images"] = [img]

    return decoded_inputs_dict, False
