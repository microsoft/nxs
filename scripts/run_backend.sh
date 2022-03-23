#!/bin/bash

export PYTHONPATH=/app
export LD_LIBRARY_PATH=/usr/local/cuda-11.3/lib64
python3 main_processes/backend/main.py --backend_name $MY_POD_NAME \
--mongodb_uri $COSMOSDB_URL     \
--mongodb_db_name $COSMOSDB_NAME \
--db_use_shard_key true     \
--storage_azure_blobstore_conn_str $BLOBSTORE_CONN_STR \
--storage_azure_blobstore_container_name $BLOBSTORE_CONTAINER \
--job_queue_type redis     \
--job_redis_queue_address $REDIS_ADDRESS \
--job_redis_queue_port $REDIS_PORT \
--job_redis_queue_password $REDIS_PASSWORD \
--job_redis_queue_use_ssl $REDIS_USE_SSL \
--tmp_dir $TMP_DIR