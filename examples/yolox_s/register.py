import argparse
import os
import requests


def send_post_request(url, payload={}, headers={}, timeout=60000):
    return requests.post(url, json=payload, headers=headers, timeout=timeout).json()


def main():

    parser = argparse.ArgumentParser(description="NXS Example")
    parser.add_argument("--nxs_url", type=str, default="http://localhost:8080/api")
    parser.add_argument("--nxs_api_key", type=str, default="nexus3_123")
    parser.add_argument("--model_url", type=str)
    args = parser.parse_args()

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
                "fps": 89.815,  # FPS measured on T4 GPU
                "latencyE2e": {
                    "mean": 11.134,  # in ms
                    "std": 0.240,  # in ms
                    "min": 10.878,  # in ms
                    "max": 14.531,  # in ms
                },
                "gpuMemUsage": 789.000,  # in MB
            }
        ],
        "useGpu": True,
        "batching": True,
        "crossRequestsBatching": True,
        "url": args.model_url,
        "preprocUrl": "https://raw.githubusercontent.com/microsoft/nxs/main/examples/yolox_s/yolox_preprocessing.py",
        "postprocUrl": "https://raw.githubusercontent.com/microsoft/nxs/main/examples/yolox_s/yolox_postprocessing.py",
        "transfromUrl": "",
    }

    # register the model
    MODEL_REGISTRATION_API = f"{args.nxs_url}/v2/models/register"
    model_registration_result = send_post_request(
        MODEL_REGISTRATION_API, model_desc, {"x-api-key": args.nxs_api_key}
    )

    model_uuid = model_registration_result["modelUuid"]
    # register the pipeline
    PIPELINE_REGISTRATION_API = f"{args.nxs_url}/v2/pipelines/register"

    pipeline_desc = {
        "userName": "nxs-admin",
        "pipelineGroups": [{"colocatedModelUuids": [model_uuid]}],
        "name": "Yolox-s",
        "accuracy": "40.5% mAP@0.5:0.95",
        "params": "9M",
        "flops": "26.8G",
        "input_type": "image",
        "description": "Object detector Yolox-s that takes an image and returns locations of 80 classes in COCO dataset.",
        "is_public": True,
    }

    pipeline_registration_result = send_post_request(
        PIPELINE_REGISTRATION_API, pipeline_desc, {"x-api-key": args.nxs_api_key}
    )

    print("PIPELINE_UUID: {}".format(pipeline_registration_result["pipelineUuid"]))


if __name__ == "__main__":
    main()
