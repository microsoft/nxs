#!/bin/bash

STORE_PATH="/app/tmp"
DB_STORE_PATH="${STORE_PATH}/db"

if [ -z "$REDIS_PASSWD" ]
then
    REDIS_PASSWD="nxs_123456"
fi

if [ -z "$API_KEY" ]
then
    API_KEY="nxs_123456"
fi

if [ -z "$ENABLE_API_V1" ]
then
    ENABLE_API_V1="false"
fi

echo "requirepass $REDIS_PASSWD" >> /app/redis-6.2.6/redis.conf

mkdir -p $DB_STORE_PATH
mongod --dbpath $DB_STORE_PATH &

#wait until mongodb is successfully started
while ! mongo --eval "db.version()" > /dev/null 2>&1; do sleep 0.1; done

echo "MongoDB was successfully launched!"

#run redis
redis-server /app/redis-6.2.6/redis.conf &

#wait until redis is successfully started
PONG=`redis-cli -a $REDIS_PASSWD ping | grep PONG`
while [ -z "$PONG" ]; do
    sleep 1
    PONG=`redis-cli -a $REDIS_PASSWD ping | grep PONG`
done

echo "Redis was successfully launched!"

# Run nxs processes
mkdir -p /app/tmp/local/models
mkdir -p /app/tmp/local/preprocessing
mkdir -p /app/tmp/local/postprocessing
mkdir -p /app/tmp/local/transforming

export PYTHONPATH=/app
export LD_LIBRARY_PATH=/usr/local/cuda-11.3/lib64

MONGODB_URI="mongodb://localhost:27017"
MONGODB_DB_NAME="NXS"
TMP_DIR="./tmp"

# Run scheduler
python3 main_processes/scheduler/main.py \
--mongodb_uri $MONGODB_URI     \
--mongodb_db_name $MONGODB_DB_NAME \
--db_use_shard_key true     \
--storage_type local_storage \
--job_queue_type redis \
--job_redis_queue_address localhost \
--job_redis_queue_port 6379 \
--job_redis_queue_password $REDIS_PASSWD \
--job_redis_queue_use_ssl false &

sleep 1

# Run workload manager
python3 main_processes/workload_manager/main.py     \
--mongodb_uri $MONGODB_URI     \
--mongodb_db_name $MONGODB_DB_NAME \
--db_use_shard_key true     \
--storage_type local_storage \
--job_queue_type redis     \
--job_redis_queue_address localhost \
--job_redis_queue_port 6379 \
--job_redis_queue_password $REDIS_PASSWD \
--job_redis_queue_use_ssl false \
--enable_instant_scheduling true \
--model_timeout_secs 180 &

# Run gpu backend
python3 main_processes/backend/main.py --backend_name backend \
--mongodb_uri $MONGODB_URI     \
--mongodb_db_name $MONGODB_DB_NAME \
--db_use_shard_key true     \
--storage_type local_storage \
--job_queue_type redis     \
--job_redis_queue_address localhost \
--job_redis_queue_port 6379 \
--job_redis_queue_password $REDIS_PASSWD \
--job_redis_queue_use_ssl false \
--tmp_dir $TMP_DIR &

# Run api server
python3 main_processes/frontend/app.py --frontend_name frontend --port 80 \
--mongodb_uri $MONGODB_URI     \
--mongodb_db_name $MONGODB_DB_NAME \
--db_use_shard_key true \
--storage_type local_storage \
--job_queue_type redis     \
--job_redis_queue_address localhost \
--job_redis_queue_port 6379 \
--job_redis_queue_password $REDIS_PASSWD \
--job_redis_queue_use_ssl false \
--tmp_dir $TMP_DIR \
--api_key $API_KEY \
--enable_v1_api $ENABLE_API_V1