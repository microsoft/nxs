import cv2
import numpy as np
from typing import Dict, Tuple
from nxs_types.model import NxsModel


def preprocessing(
    decoded_inputs_dict, preproc_params, component_model: NxsModel, metadata: Dict = {}
) -> Tuple[Dict, bool]:
    model_w = component_model.model_desc.inputs[0].shape[3]
    model_h = component_model.model_desc.inputs[0].shape[2]

    original_img = decoded_inputs_dict["input"]

    img = cv2.resize(original_img, (model_w, model_h))
    img = np.array(img).astype(np.float32)
    img /= 255.0
    img = np.transpose(img, (2, 0, 1))
    decoded_inputs_dict["input"] = [img]

    # add original size into metadata to be used in postprocessing step
    metadata["original_width"] = original_img.shape[1]
    metadata["original_height"] = original_img.shape[0]

    return decoded_inputs_dict, False
