#!/bin/bash

export PYTHONPATH=/app

python3 apps/vehicle_counting/worker/worker.py \
--video_uuid $VIDEO_UUID \
--nxs_url $NXS_URL \
--nxs_api_key $NXS_API_KEY \
--blobstore_conn_str $VC_BLOBSTORE_CONN_STR \
--blobstore_container $VC_BLOBSTORE_CONTAINER_NAME \
--cosmosdb_conn_str $VC_COSMOSDB_CONN_STR \
--cosmosdb_db_name $VC_COSMOSDB_NAME \
--object_detector_uuid $VC_DETECTOR_UUID \
--tracker_uuid $VC_TRACKER_UUID \
--counting_report_interval_secs $VC_REPORT_INTERVAL_SECS \
--debug $DEBUG