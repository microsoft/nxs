import os
import argparse
import requests


def send_file_request(url, binary_file, params, headers={}, timeout=60000):
    files = {"file": binary_file}
    return requests.post(
        url, files=files, params=params, headers=headers, timeout=timeout
    ).json()


def main():
    parser = argparse.ArgumentParser(description="NXS Example")
    parser.add_argument("--nxs_url", type=str, default="http://localhost:8080")
    parser.add_argument("--nxs_api_key", type=str, default="nexus3_123")
    parser.add_argument("--image_path", type=str)
    parser.add_argument("--pipeline_uuid", type=str)
    args = parser.parse_args()

    SYNC_INFER_IMAGE_API = f"{args.nxs_url}/api/v2/tasks/images/infer-from-file"

    if args.image_path.startswith("http"):
        image_bin = requests.get(args.image_path, allow_redirects=True).content
    else:
        image_bin = open(args.image_path, "rb").read()

    infer_desc = {"pipeline_uuid": args.pipeline_uuid}
    result = send_file_request(
        SYNC_INFER_IMAGE_API, image_bin, infer_desc, {"x-api-key": args.nxs_api_key}
    )

    assert result["status"] == "COMPLETED"

    for det in result["detections"]:
        print(
            "ClassName: {} - Score: {:.3f} - Coordinates: {}".format(
                det["className"], det["score"], det["bbox"]
            )
        )


if __name__ == "__main__":
    main()
