import os

import cv2
from apps.vehicle_counting.app_types.app_request import (
    InDbTrackingAppRequest,
    RequestStatus,
)
from apps.vehicle_counting.worker.utils import *
from nxs_libs.db import NxsDbFactory, NxsDbType
from nxs_libs.storage import NxsStorageFactory, NxsStorageType

DB_TASKS_COLLECTION_NAME = "tasks"
DB_COUNTS_COLLECTION_NAME = "counts"
DB_LOGS_COLLECTION_NAME = "logs"
STORAGE_LOGS_DIR_PATH = "logs"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Vehicle Counting App")
    parser.add_argument("--video_uuid", type=str)
    parser.add_argument("--nxs_url", type=str)
    parser.add_argument("--nxs_api_key", type=str)
    parser.add_argument(
        "--object_detector_uuid",
        type=str,
        default="bbff897256c9431eb19a2ad311749b39",
    )
    parser.add_argument(
        "--tracker_uuid",
        type=str,
        default="451ffc2ee1594fe2a6ace17fca5117ab",
    )
    parser.add_argument("--blobstore_conn_str", type=str)
    parser.add_argument("--blobstore_container", type=str)
    parser.add_argument("--cosmosdb_conn_str", type=str)
    parser.add_argument("--cosmosdb_db_name", type=str)
    parser.add_argument(
        "--debug", default=False, type=lambda x: (str(x).lower() == "true")
    )
    parser.add_argument("--storage_usage_percentage_thresh", type=float, default=80.0)
    parser.add_argument("--inference_retries", type=int, default=90)
    args = parser.parse_args()

    args.video_uuid = os.environ["VIDEO_UUID"]
    args.nxs_url = os.environ["NXS_URL"]
    args.nxs_api_key = os.environ["NXS_API_KEY"]
    args.blobstore_conn_str = os.environ["BLOBSTORE_CONN_STR"]
    args.blobstore_container = os.environ["BLOBSTORE_CONTAINER"]
    args.cosmosdb_conn_str = os.environ["COSMOSDB_URL"]
    args.cosmosdb_db_name = os.environ["COSMOSDB_NAME"]
    try:
        args.storage_usage_percentage_thresh = float(
            os.environ.get("STORAGE_USAGE_PERCENTAGE_THRESH", "80.0")
        )
    except:
        args.storage_usage_percentage_thresh = 80.0
    try:
        args.inference_retries = int(os.environ.get("INFERENCE_RETRIES", "90"))
    except:
        args.inference_retries = 90

    has_error: bool = False
    error_str: str = ""

    try:
        db_client = NxsDbFactory.create_db(
            NxsDbType.MONGODB,
            uri=args.cosmosdb_conn_str,
            db_name=args.cosmosdb_db_name,
        )

        db_client.update(
            DB_TASKS_COLLECTION_NAME,
            {
                "video_uuid": args.video_uuid,
                "zone": "global",
            },
            {"status": RequestStatus.RUNNING},
        )

        video_info = InDbTrackingAppRequest(
            **db_client.query(
                DB_TASKS_COLLECTION_NAME, {"video_uuid": args.video_uuid}
            )[0]
        )
        if video_info.skip_frames is None:
            video_info.skip_frames = 3
        if video_info.count_interval_secs is None:
            video_info.count_interval_secs = 900  # 15 mins

        INFER_URL = f"{args.nxs_url}/api/v2/tasks/tensors/infer"
        OBJECT_DETECTOR_UUID = args.object_detector_uuid
        TRACKER_UUID = args.tracker_uuid

        cap = cv2.VideoCapture(video_info.video_url)
        frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        frame_rate = int(round(cap.get(cv2.CAP_PROP_FPS)))
        cap.release()

        rois = []
        lines = []

        for region in video_info.regions:
            points = []
            for p in region.roi.points:
                points.append(
                    NxsPoint(
                        int(p.x * frame_width),
                        int(p.y * frame_height),
                    )
                )
            rois.append(NxsRoi(points=points))

            line = region.line
            lines.append(
                NxsLine(
                    p0=NxsPoint(
                        x=int(line.p0.x * frame_width),
                        y=int(line.p0.y * frame_height),
                    ),
                    p1=NxsPoint(
                        x=int(line.p1.x * frame_width),
                        y=int(line.p1.y * frame_height),
                    ),
                )
            )

        if ".m3u8" not in video_info.video_url:
            from apps.vehicle_counting.worker.online_worker import (
                OnlineVehicleTrackingApp,
            )

            app = OnlineVehicleTrackingApp(
                video_uuid=video_info.video_uuid,
                frame_width=frame_width,
                frame_height=frame_height,
                frame_rate=frame_rate,
                nxs_infer_url=INFER_URL,
                nxs_api_key=args.nxs_api_key,
                detector_uuid=OBJECT_DETECTOR_UUID,
                tracker_uuid=TRACKER_UUID,
                video_url=video_info.video_url,
                rois=rois,
                lines=lines,
                tracking_classes=video_info.tracking_classes,
                visualize=False,
                collect_logs=args.debug,
                skip_frame=video_info.skip_frames,
                blobstore_conn_str=args.blobstore_conn_str,
                blobstore_container_name=args.blobstore_container,
                cosmosdb_conn_str=args.cosmosdb_conn_str,
                cosmosdb_db_name=args.cosmosdb_db_name,
                counting_report_interval_secs=video_info.count_interval_secs,
                job_duration=video_info.job_duration,
                disk_usage_percentage_thresh=args.storage_usage_percentage_thresh,
            )
        else:
            from apps.vehicle_counting.worker.offline_worker import (
                OfflineVehicleTrackingApp,
            )

            app = OfflineVehicleTrackingApp(
                video_uuid=video_info.video_uuid,
                frame_width=frame_width,
                frame_height=frame_height,
                frame_rate=frame_rate,
                nxs_infer_url=INFER_URL,
                nxs_api_key=args.nxs_api_key,
                detector_uuid=OBJECT_DETECTOR_UUID,
                tracker_uuid=TRACKER_UUID,
                video_url=video_info.video_url,
                rois=rois,
                lines=lines,
                tracking_classes=video_info.tracking_classes,
                visualize=False,
                collect_logs=args.debug,
                skip_frame=video_info.skip_frames,
                blobstore_conn_str=args.blobstore_conn_str,
                blobstore_container_name=args.blobstore_container,
                cosmosdb_conn_str=args.cosmosdb_conn_str,
                cosmosdb_db_name=args.cosmosdb_db_name,
                counting_report_interval_secs=video_info.count_interval_secs,
                job_duration=video_info.job_duration,
                inference_retries=args.inference_retries,
            )

        app.run_tracking()

        db_client = NxsDbFactory.create_db(
            NxsDbType.MONGODB,
            uri=args.cosmosdb_conn_str,
            db_name=args.cosmosdb_db_name,
        )

        if app.job_completed:
            db_client.update(
                DB_TASKS_COLLECTION_NAME,
                {
                    "video_uuid": args.video_uuid,
                    "zone": "global",
                },
                {"status": RequestStatus.COMPLETED, "error": ""},
            )
        else:
            db_client.update(
                DB_TASKS_COLLECTION_NAME,
                {
                    "video_uuid": args.video_uuid,
                    "zone": "global",
                },
                {"status": RequestStatus.FAILED, "error": "stream ended"},
            )
    except Exception as e:
        has_error = True
        error_str = str(e)

    if has_error:
        for _ in range(60):
            try:
                db_client = NxsDbFactory.create_db(
                    NxsDbType.MONGODB,
                    uri=args.cosmosdb_conn_str,
                    db_name=args.cosmosdb_db_name,
                )

                db_client.update(
                    DB_TASKS_COLLECTION_NAME,
                    {
                        "video_uuid": args.video_uuid,
                        "zone": "global",
                    },
                    {"status": RequestStatus.FAILED, "error": error_str},
                )

                break
            except Exception as e:
                time.sleep(30)

    # upload logs
    log_file = f"{args.video_uuid}.txt"
    if os.path.exists(log_file):
        storage_client = NxsStorageFactory.create_storage(
            NxsStorageType.AzureBlobstorage,
            connection_str=args.blobstore_conn_str,
            container_name=args.blobstore_container,
        )

        storage_client.upload(log_file, STORAGE_LOGS_DIR_PATH, True)

    # signal api server to terminate this job
    nxsapp_api_key = os.environ["API_KEY"]
    headers = {"x-api-key": nxsapp_api_key}

    while True:
        try:
            requests.post(
                "http://nxsapp-api-svc.nxsapp/video/terminate",
                params={"video_uuid": args.video_uuid},
                headers=headers,
            )
            break
        except Exception as e:
            time.sleep(5)


if __name__ == "__main__":
    main()
