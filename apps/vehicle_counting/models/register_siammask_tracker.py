import os
import argparse
import requests

parser = argparse.ArgumentParser(description="Nxs")
parser.add_argument("--model_url", type=str, required=True)
args = parser.parse_args()


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

PREDEFINED_PIPELINE_UUID = "451ffc2ee1594fe2a6ace17fca5117ab"

model_desc = {
    "userName": "nxs-admin",
    "modelName": "siammask_tracker",
    "framework": "tf_pb",
    "modelDesc": {
        "inputs": [
            {
                "name": "Placeholder",
                "shape": [-1, 255, 255, 3],
                "dtype": "float32",
                "dclass": "image",
            },
            {
                "name": "Placeholder_1",
                "shape": [-1, 127, 127, 3],
                "dtype": "float32",
                "dclass": "image",
            },
        ],
        "outputs": [
            {"name": "BBox/Head/conv2d_1/BiasAdd"},
            {"name": "Score/Head/conv2d_1/BiasAdd"},
        ],
        "classNames": [],
        "preprocessingName": "siammask_tracker",
        "postprocessingName": "siammask_tracker",
        "transformingName": "none",
        "extraPreprocessingMetadata": "{}",
        "extraPostprocessingMetadata": "{}",
        "extraTransformingMetadata": "{}",
    },
    "profile": [
        {
            "batch_size": 1,
            "fps": 57.41400179741806,
            "latency_e2e": {
                "mean": 17.316359043121338,
                "std": 0.27735395488881326,
                "min": 16.564607620239258,
                "max": 18.275976181030273,
            },
            "gpu_mem_usage": 7243,
        },
        {
            "batch_size": 2,
            "fps": 76.02464789128096,
            "latency_e2e": {
                "mean": 26.197772979736328,
                "std": 0.3466678865422864,
                "min": 24.014711380004883,
                "max": 27.266979217529297,
            },
            "gpu_mem_usage": 7243,
        },
        {
            "batch_size": 3,
            "fps": 79.39839786125735,
            "latency_e2e": {
                "mean": 37.58207702636719,
                "std": 0.6225778490789502,
                "min": 33.39385986328125,
                "max": 39.5054817199707,
            },
            "gpu_mem_usage": 7243,
        },
        {
            "batch_size": 4,
            "fps": 83.66077233741039,
            "latency_e2e": {
                "mean": 47.69277048110962,
                "std": 0.5757736131315614,
                "min": 42.754411697387695,
                "max": 49.13139343261719,
            },
            "gpu_mem_usage": 7243,
        },
        {
            "batch_size": 5,
            "fps": 85.59441370937498,
            "latency_e2e": {
                "mean": 58.29380655288696,
                "std": 0.8772577995445024,
                "min": 51.75471305847168,
                "max": 65.18745422363281,
            },
            "gpu_mem_usage": 7243,
        },
        {
            "batch_size": 6,
            "fps": 88.4006871822751,
            "latency_e2e": {
                "mean": 67.7487530708313,
                "std": 0.9032202338298063,
                "min": 62.17670440673828,
                "max": 69.87667083740234,
            },
            "gpu_mem_usage": 7243,
        },
        {
            "batch_size": 7,
            "fps": 89.05677325130569,
            "latency_e2e": {
                "mean": 78.4804162979126,
                "std": 1.1840163978767573,
                "min": 72.19862937927246,
                "max": 81.28762245178223,
            },
            "gpu_mem_usage": 7243,
        },
        {
            "batch_size": 8,
            "fps": 93.81186134477865,
            "latency_e2e": {
                "mean": 85.15189790725708,
                "std": 1.5028153355717901,
                "min": 77.61240005493164,
                "max": 89.2629623413086,
            },
            "gpu_mem_usage": 7243,
        },
    ],
    "useGpu": True,
    "batching": True,
    "crossRequestsBatching": True,
    "url": args.model_url,
    "preprocUrl": "https://raw.githubusercontent.com/microsoft/nxs/main/apps/vehicle_counting/models/preprocessing/siammask_tracker_nostate_preproc.py",
    "postprocUrl": "https://raw.githubusercontent.com/microsoft/nxs/main/apps/vehicle_counting/models/postprocessing/siammask_tracker_nostate_postproc.py",
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
    "name": "Siammask-Tracker-Stateless",
    "accuracy": "60.9% VOT-2018",
    "params": "",
    "flops": "",
    "input_type": "tensor",
    "description": "This tracker takes an object template image, a previous location of that object, an image to localize the current location of the object.",
    "is_public": True,
}

pipeline_registration_result = send_post_request(
    PIPELINE_REGISTRATION_API, pipeline_desc, {"x-api-key": NXS_API_KEY}
)
print(pipeline_registration_result)
