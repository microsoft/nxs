from typing import Tuple, List
from nxs_types.model import *


def get_pre_post_processing(
    model_type: W4ModelType,
) -> Tuple[ModelPreprocessing, ModelPostprocessing]:
    pre = ModelPreprocessing.RAW
    post = ModelPostprocessing.RAW

    if model_type == W4ModelType.CLASSIFIER:
        post = ModelPostprocessing.W4_CLASSIFIER_V1
    elif model_type == W4ModelType.DETECTOR:
        post = ModelPostprocessing.W4_DETECTOR_V1

    return (pre, post)


def get_model_inputs(
    model_type: W4ModelType, image_size: int, batch_size: int = -1
) -> List[ModelInput]:
    if model_type == W4ModelType.CLASSIFIER:
        return _get_w4_classifier_inputs(image_size, batch_size)
    elif model_type == W4ModelType.DETECTOR:
        return _get_w4_detector_inputs(image_size, batch_size)


def _get_w4_classifier_inputs(
    image_size: int, batch_size: int = -1
) -> List[ModelInput]:
    return [
        ModelInput(
            name="input",
            shape=[batch_size, image_size, image_size, 3],
            dtype=TensorType.FLOAT32,
            dclass=InputClass.IMAGE,
            norm=InputNorm(use_nchw=False),
        )
    ]


def _get_w4_detector_inputs(image_size: int, batch_size: int = -1) -> List[ModelInput]:
    return [
        ModelInput(
            name="input",
            shape=[batch_size, 3, image_size, image_size],
            dtype=TensorType.FLOAT32,
            dclass=InputClass.IMAGE,
            norm=InputNorm(use_nchw=True, std_r=255.0, std_g=255.0, std_b=255.0),
        )
    ]
