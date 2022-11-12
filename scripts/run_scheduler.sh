#!/bin/bash

# apt update -y
# apt install redis -y
# redis-cli -h $REDIS_ADDRESS -a $REDIS_PASSWORD CONFIG SET requirepass "$REDIS_PASSWORD"

if [ -z "$ENABLE_AUTO_SCALING" ]
then
    ENABLE_AUTO_SCALING="false"
fi

KUBECONFIG_FILE="/mnt/secrets-store/AksKubeConfig"
if [ -f "$KUBECONFIG_FILE" ]; then
    mkdir -p /root/.kube
    cp -f $KUBECONFIG_FILE /root/.kube/config
    kubectl get pods
else
    # do not enable autoscaling if we cannot access AksKubeConfig
    ENABLE_AUTO_SCALING="false"
fi


export PYTHONPATH=/app
python3 main_processes/scheduler/main.py \
--mongodb_uri $COSMOSDB_URL     \
--mongodb_db_name $COSMOSDB_NAME \
--db_use_shard_key true     \
--storage_azure_blobstore_conn_str $BLOBSTORE_CONN_STR \
--storage_azure_blobstore_container_name $BLOBSTORE_CONTAINER \
--job_queue_type redis \
--job_redis_queue_address $REDIS_ADDRESS \
--job_redis_queue_port $REDIS_PORT \
--job_redis_queue_password $REDIS_PASSWORD \
--job_redis_queue_use_ssl $REDIS_USE_SSL \
--tmp_dir $TMP_DIR --enable_autoscaling $ENABLE_AUTO_SCALING