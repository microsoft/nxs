import cv2
import numpy as np
from typing import Any, Dict, Tuple
from nxs_types.model import NxsModel


def preprocessing(
    decoded_inputs_dict: Dict[Any, Any],
    preproc_params: Dict[Any, Any],
    component_model: NxsModel,
    metadata: Dict = {},
) -> Tuple[Dict, bool]:
    model_w = component_model.model_desc.inputs[0].shape[2]
    model_h = component_model.model_desc.inputs[0].shape[1]

    original_img = decoded_inputs_dict["input"]

    img = cv2.resize(original_img, (model_w, model_h))
    img = np.array(img).astype(np.float32)

    results = {}
    results["input"] = [img]

    return results, False
