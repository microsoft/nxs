import os
import requests

def send_get_request(url, payload={}, headers={}, timeout=60000):
    return requests.get(
        url=url, params=payload, headers=headers, timeout=timeout
    ).json()


def send_post_request(url, payload={}, headers={}, timeout=60000):
    return requests.post(url, json=payload, headers=headers, timeout=timeout).json()


def send_file_request(url, binary_file, params, headers={}, timeout=60000):
    files = {"file": binary_file}
    return requests.post(
        url, files=files, params=params, headers=headers, timeout=timeout
    ).json()


NXS_API_URL = "{}/api".format(os.environ["NXS_URL"])
NXS_API_KEY = os.environ["API_KEY"]

PREDEFINED_PIPELINE_UUID = "bbff897256c9431eb19a2ad311749b39"

model_desc = {
    "userName": "nxs-admin",
    "modelName": "yolox-s",
    "framework": "onnx",
    "modelDesc": {
        "inputs": [
            {
                "name": "images",
                "shape": [1, 3, 640, 640],
                "dtype": "float32",
                "dclass": "image",
            }
        ],
        "outputs": [{"name": "output"}],
        "classNames": [
            "person",
            "bicycle",
            "car",
            "motorcycle",
            "airplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light",
            "fire hydrant",
            "stop sign",
            "parking meter",
            "bench",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear",
            "zebra",
            "giraffe",
            "backpack",
            "umbrella",
            "handbag",
            "tie",
            "suitcase",
            "frisbee",
            "skis",
            "snowboard",
            "sports ball",
            "kite",
            "baseball bat",
            "baseball glove",
            "skateboard",
            "surfboard",
            "tennis racket",
            "bottle",
            "wine glass",
            "cup",
            "fork",
            "knife",
            "spoon",
            "bowl",
            "banana",
            "apple",
            "sandwich",
            "orange",
            "broccoli",
            "carrot",
            "hot dog",
            "pizza",
            "donut",
            "cake",
            "chair",
            "couch",
            "potted plant",
            "bed",
            "dining table",
            "toilet",
            "tv",
            "laptop",
            "mouse",
            "remote",
            "keyboard",
            "cell phone",
            "microwave",
            "oven",
            "toaster",
            "sink",
            "refrigerator",
            "book",
            "clock",
            "vase",
            "scissors",
            "teddy bear",
            "hair drier",
            "toothbrush",
        ],
        "preprocessingName": "test-yolox",
        "postprocessingName": "test-yolox",
        "transformingName": "none",
        "extraPreprocessingMetadata": "{}",
        "extraPostprocessingMetadata": "{}",
        "extraTransformingMetadata": "{}",
    },
    "profile": [
        {
            "batchSize": 1,
            "fps": 89.815,
            "latencyE2e": {"mean": 11.134, "std": 0.240, "min": 10.878, "max": 14.531},
            "gpuMemUsage": 789.000,
        }
    ],
    "useGpu": True,
    "batching": True,
    "crossRequestsBatching": True,
    "url": "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx",
    "preprocUrl": "https://raw.githubusercontent.com/microsoft/nxs/main/apps/vehicle_counting/models/preprocessing/nxs-yolox-preproc.py",
    "postprocUrl": "https://raw.githubusercontent.com/microsoft/nxs/main/apps/vehicle_counting/models/postprocessing/nxs-yolox-postproc.py",
    "transfromUrl": "",
}

# register the model
MODEL_REGISTRATION_API = f"{NXS_API_URL}/v2/models/register"
model_registration_result = send_post_request(
    MODEL_REGISTRATION_API, model_desc, {"x-api-key": NXS_API_KEY}
)
print(model_registration_result)

model_uuid = model_registration_result["modelUuid"]
# register the pipeline
PIPELINE_REGISTRATION_API = f"{NXS_API_URL}/v2/pipelines/register"

pipeline_desc = {
    "userName": "nxs-admin",
    "pipelineGroups": [{"colocatedModelUuids": [model_uuid]}],
    "predefined_pipeline_uuid": PREDEFINED_PIPELINE_UUID,
    "name": "Yolox-s",
    "accuracy": "40.5% mAP@0.5:0.95",
    "params": "9M",
    "flops": "26.8G",
    "input_type": "image",
    "description": "Object detector Yolox-s that takes an image and returns locations of 80 classes in COCO dataset.",
    "is_public": True,
}

pipeline_registration_result = send_post_request(
    PIPELINE_REGISTRATION_API, pipeline_desc, {"x-api-key": NXS_API_KEY}
)
print(pipeline_registration_result)
