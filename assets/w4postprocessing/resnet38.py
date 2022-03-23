import numpy as np
from typing import Any, Dict, Tuple
from nxs_types.model import NxsModel


def postprocessing(
    data, postproc_params, component_model: NxsModel, metadata: Dict = {}
):
    probs = data["softmax"]

    result: Dict[str, Any] = {"probabilities": {}}

    for class_id, prob in enumerate(probs):
        class_name = f"class_{class_id}"
        if class_id < len(component_model.model_desc.class_names):
            class_name = component_model.model_desc.class_names[class_id]

        result["probabilities"][class_name] = prob

    best_class_id = np.argmax(probs)
    best_class_name = f"class_{best_class_id}"
    if best_class_id < len(component_model.model_desc.class_names):
        best_class_name = component_model.model_desc.class_names[best_class_id]

    result["predicted_class_id"] = best_class_id
    result["best_score"] = probs[best_class_id]
    result["predicted_class_name"] = best_class_name

    return {"classification": result}
