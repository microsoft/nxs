#!/bin/bash

if [ -z "$ENABLE_API_V1" ]
then
    ENABLE_API_V1="false"
fi

export PYTHONPATH=/app
python3 main_processes/frontend/app.py --frontend_name $MY_POD_NAME --port $API_SERVER_PORT \
--mongodb_uri $COSMOSDB_URL     \
--mongodb_db_name $COSMOSDB_NAME \
--db_use_shard_key true \
--storage_azure_blobstore_conn_str $BLOBSTORE_CONN_STR \
--storage_azure_blobstore_container_name $BLOBSTORE_CONTAINER \
--job_queue_type redis \
--job_redis_queue_address $REDIS_ADDRESS \
--job_redis_queue_port $REDIS_PORT \
--job_redis_queue_password $REDIS_PASSWORD \
--job_redis_queue_use_ssl $REDIS_USE_SSL \
--tmp_dir $TMP_DIR \
--api_key $API_KEY \
--enable_v1_api $ENABLE_API_V1