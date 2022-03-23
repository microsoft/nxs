import argparse


def get_common_parser():
    global args

    parser = argparse.ArgumentParser(description="Nxs")
    parser.add_argument("--db_type", type=str, default="mongodb")
    parser.add_argument("--mongodb_uri", type=str, default="")
    parser.add_argument("--mongodb_db_name", type=str, default="nxs")
    parser.add_argument(
        "--db_use_shard_key",
        default=False,
        type=lambda x: (str(x).lower() == "true"),
    )
    parser.add_argument("--db_shard_key", type=str, default="zone")
    parser.add_argument("--db_shard_value", type=str, default="global")

    parser.add_argument("--storage_type", type=str, default="azure_blob_storage")
    parser.add_argument("--storage_azure_blobstore_conn_str", type=str, default="")
    parser.add_argument(
        "--storage_azure_blobstore_container_name", type=str, default=""
    )

    parser.add_argument("--job_queue_type", type=str, default="azure_queue")
    parser.add_argument("--job_azure_queue_conn_str", type=str, default="")
    parser.add_argument("--job_azure_queue_name", type=str, default="")
    parser.add_argument("--job_redis_queue_address", type=str, default="")
    parser.add_argument("--job_redis_queue_port", type=int, default=6379)
    parser.add_argument("--job_redis_queue_password", type=str, default="")
    parser.add_argument(
        "--job_redis_queue_use_ssl",
        default=False,
        type=lambda x: (str(x).lower() == "true"),
    )

    parser.add_argument("--tmp_dir", type=str, default="./tmp")

    return parser
