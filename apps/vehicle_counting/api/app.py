import os
from typing import List
import uvicorn
from fastapi import Depends, FastAPI, Security
from fastapi import HTTPException, status
from fastapi.security import (
    APIKeyHeader,
)


import argparse
import uuid
from nxs_libs.db import (
    NxsDbFactory,
    NxsDbQueryConfig,
    NxsDbSortType,
    NxsDbType,
)

from apps.vehicle_counting.app_types.app_request import (
    InDbTrackingAppRequest,
    RequestStatus,
    TrackingAppRequest,
    TrackingAppResponse,
    TrackingAppStatus,
    TrackingCountPerClass,
    TrackingCountPerRoi,
    TrackingCountResult,
    VisualizationResult,
)

import subprocess
import yaml
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import (
    ResourceTypes,
    AccountSasPermissions,
    generate_account_sas,
)


def generate_uuid() -> str:
    return str(uuid.uuid4()).replace("-", "")


parser = argparse.ArgumentParser(description="Vehicle Counting App API")
parser.add_argument("--port", type=int, default=80)
parser.add_argument("--blobstore_conn_str", type=str, default="")
parser.add_argument("--blobstore_container", type=str, default="")
parser.add_argument("--cosmosdb_conn_str", type=str, default="")
parser.add_argument("--cosmosdb_db_name", type=str, default="")
parser.add_argument("--api_key", type=str, default="")
parser.add_argument("--worker_container", type=str, default="")
args = parser.parse_args()

args.blobstore_conn_str = os.environ["BLOBSTORE_CONN_STR"]
args.blobstore_container = os.environ["BLOBSTORE_CONTAINER"]
args.cosmosdb_conn_str = os.environ["COSMOSDB_URL"]
args.cosmosdb_db_name = os.environ["COSMOSDB_NAME"]
args.api_key = os.environ["API_KEY"]
args.worker_container = os.environ["WORKER_CONTAINER"]


DB_TASKS_COLLECTION_NAME = "tasks"
DB_COUNTS_COLLECTION_NAME = "counts"
DB_LOGS_COLLECTION_NAME = "logs"
STORAGE_LOGS_DIR_PATH = "logs"

app = FastAPI(
    title="NXS Vehicle Counting Frontend",
    version="0.1.0",
    contact={"name": "Loc Huynh", "email": "lohuynh@microsoft.com"},
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


@app.get("/")
def root():
    return {}


async def check_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header != args.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="wrong api key",
        )

    return True


@app.post("/video", response_model=TrackingAppResponse)
def submit_video(
    request: TrackingAppRequest, authenticated: bool = Depends(check_api_key)
):
    video_uuid = generate_uuid()

    if len(request.regions) < 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Need at least one region to count vehicles.",
        )

    if request.count_interval_secs is not None and request.count_interval_secs < 30:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "count_interval_secs should be at least 30.",
        )

    db_client = NxsDbFactory.create_db(
        NxsDbType.MONGODB,
        uri=args.cosmosdb_conn_str,
        db_name=args.cosmosdb_db_name,
    )

    # indb_request = request.dict()
    # indb_request["video_uuid"] = video_uuid
    # indb_request["zone"] = "global"

    indb_request = InDbTrackingAppRequest(
        video_uuid=video_uuid, **request.dict()
    ).dict()
    indb_request["zone"] = "global"

    db_client.insert(DB_TASKS_COLLECTION_NAME, indb_request)

    # '''
    cur_dir_abs_path = os.path.dirname(os.path.realpath(__file__))
    yaml_path = os.path.join(cur_dir_abs_path, f"yaml/app_job.yaml")
    yaml_data = yaml.safe_load(open(yaml_path))
    yaml_data["metadata"]["name"] = f"{video_uuid}"
    yaml_data["spec"]["template"]["spec"]["containers"][0][
        "image"
    ] = args.worker_container
    yaml_data["spec"]["template"]["spec"]["containers"][0]["env"][0][
        "value"
    ] = video_uuid
    if request.debug:
        yaml_data["spec"]["template"]["spec"]["containers"][0]["env"][1][
            "value"
        ] = "true"

    yaml_dir_path = os.path.join(cur_dir_abs_path, "yaml/jobs")
    if not os.path.exists(yaml_dir_path):
        os.makedirs(yaml_dir_path)

    output_yaml_path = os.path.join(yaml_dir_path, f"{video_uuid}.yaml")

    with open(output_yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    subprocess.run(["kubectl", "apply", "-f", output_yaml_path])

    os.remove(output_yaml_path)
    # '''

    return TrackingAppResponse(video_uuid=video_uuid)


@app.post("/video/terminate")
def terminate_job(video_uuid: str, authenticated: bool = Depends(check_api_key)):
    db_client = NxsDbFactory.create_db(
        NxsDbType.MONGODB,
        uri=args.cosmosdb_conn_str,
        db_name=args.cosmosdb_db_name,
    )
    results = db_client.query(
        DB_TASKS_COLLECTION_NAME,
        {"zone": "global", "video_uuid": video_uuid},
        NxsDbQueryConfig(projection_list=["status"]),
    )
    if not results:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "non-existing video.",
        )

    if results[0]["status"] in [RequestStatus.PENDING, RequestStatus.RUNNING]:
        subprocess.run(["kubectl", "delete", "job", video_uuid])
        db_client.update(
            DB_TASKS_COLLECTION_NAME,
            {
                "video_uuid": video_uuid,
                "zone": "global",
            },
            {"status": RequestStatus.STOPPED},
        )

    return status.HTTP_200_OK


@app.get("/video", response_model=List[str])
def get_videos(status: RequestStatus, authenticated: bool = Depends(check_api_key)):
    db_client = NxsDbFactory.create_db(
        NxsDbType.MONGODB,
        uri=args.cosmosdb_conn_str,
        db_name=args.cosmosdb_db_name,
    )

    results = db_client.query(
        DB_TASKS_COLLECTION_NAME,
        {"zone": "global", "status": status},
        NxsDbQueryConfig(projection_list=["video_uuid"]),
    )

    return [r["video_uuid"] for r in results]


@app.get("/video/status", response_model=TrackingAppStatus)
def get_video_status(video_uuid: str, authenticated: bool = Depends(check_api_key)):
    db_client = NxsDbFactory.create_db(
        NxsDbType.MONGODB,
        uri=args.cosmosdb_conn_str,
        db_name=args.cosmosdb_db_name,
    )

    results = db_client.query(
        DB_TASKS_COLLECTION_NAME,
        {"zone": "global", "video_uuid": video_uuid},
        NxsDbQueryConfig(projection_list=["status", "error"]),
    )
    if not results:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "non-existing video.",
        )

    app_status = results[0]["status"]
    error = results[0].get("error", "")

    return TrackingAppStatus(status=app_status, error=error)


@app.get("/video/counts", response_model=List[TrackingCountResult])
def get_counts(
    video_uuid: str,
    last_ts: float = 0,
    authenticated: bool = Depends(check_api_key),
):
    db_client = NxsDbFactory.create_db(
        NxsDbType.MONGODB,
        uri=args.cosmosdb_conn_str,
        db_name=args.cosmosdb_db_name,
    )

    if last_ts > 0:
        query_results = db_client.query(
            DB_COUNTS_COLLECTION_NAME,
            {"video_uuid": video_uuid, "timestamp": {"$gt": last_ts * 1000}},
        )
    else:
        query_results = db_client.query(
            DB_COUNTS_COLLECTION_NAME,
            {"video_uuid": video_uuid},
            NxsDbQueryConfig(
                sort_list=[("timestamp", NxsDbSortType.DESCENDING)], limit=1
            ),
        )

    results: List[TrackingCountResult] = []

    for r in query_results:
        tracking_result = TrackingCountResult(
            timestamp=r["timestamp"] / 1000.0,
            counts=[],
            segment_starting_utc_time=r["starting_utc_time"],
            segment_starting_utc_timestamp=r["starting_utc_ts"],
            segment_ending_utc_time=r["ending_utc_time"],
            segment_ending_utc_timestamp=r["ending_utc_ts"],
        )

        counts = r["counts"]
        for roi_idx, roi_result in enumerate(counts):
            tracking_result_per_roi = TrackingCountPerRoi(roi_idx=roi_idx, counts=[])
            for class_name in roi_result:
                tracking_result_per_roi.counts.append(
                    TrackingCountPerClass(
                        class_name=class_name, count=roi_result[class_name]
                    )
                )
            tracking_result.counts.append(tracking_result_per_roi)

        results.append(tracking_result)

    return results


@app.get("/video/visualizations", response_model=VisualizationResult)
def get_visualization(
    video_uuid: str,
    timestamp_secs: int,
    authenticated: bool = Depends(check_api_key),
):
    db_client = NxsDbFactory.create_db(
        NxsDbType.MONGODB,
        uri=args.cosmosdb_conn_str,
        db_name=args.cosmosdb_db_name,
    )

    results = db_client.query(
        DB_TASKS_COLLECTION_NAME,
        {"zone": "global", "video_uuid": video_uuid},
    )

    if not results:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Non-existing video.",
        )

    if not results[0]["debug"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Video was not run in debug mode.",
        )

    results = db_client.query(
        "logs",
        {
            "zone": "global",
            "video_uuid": video_uuid,
            "start_ts": {"$gt": timestamp_secs * 1000.0},
        },
        NxsDbQueryConfig(limit=1),
    )
    if not results:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Could not find any visualization frames. Please try different timestamp!!!",
        )

    result = results[0]
    log_id = result["log_id"]
    start_ts = result["start_ts"] / 1000.0
    end_ts = result["end_ts"] / 1000.0
    num_logs = result["num_logs"]

    blob_service_client = BlobServiceClient.from_connection_string(
        args.blobstore_conn_str
    )
    sas_token = generate_account_sas(
        blob_service_client.account_name,
        account_key=blob_service_client.credential.account_key,
        resource_types=ResourceTypes(container=True, object=True),
        # permission=AccountSasPermissions(read=True, list=True),
        permission=AccountSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=24),
    )

    urls = []
    for idx in range(num_logs):
        path = f"logs/{video_uuid}_{log_id}_{idx}.jpg"
        sas_url = generate_blobstore_sas_url(
            blob_service_client.account_name,
            args.blobstore_container,
            path,
            sas_token,
        )
        urls.append(sas_url)

    return VisualizationResult(from_ts=start_ts, to_ts=end_ts, visualized_frames=urls)


def generate_blobstore_sas_url(account_name, container_name, blob_path, sas_token):
    return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_path}?{sas_token}"


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=args.port, reload=False)
