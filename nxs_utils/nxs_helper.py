import time

from nxs_libs.db import *
from nxs_libs.queue import *
from nxs_libs.simple_key_value_db import *
from nxs_libs.storage import *
from nxs_types.nxs_args import NxsBaseArgs


def init_redis_client(address: str, port: int, password: str, is_using_ssl=False):
    if not is_using_ssl:
        client = None
        try:
            from rediscluster import RedisCluster

            redis_startup_nodes = [{"host": f"{address}", "port": f"{port}"}]
            client = RedisCluster(
                startup_nodes=redis_startup_nodes,
                decode_responses=False,
                password=password,
            )
        except:
            import redis

            client = redis.StrictRedis(
                host=f"{address}",
                port=port,
                password=password,
                ssl=is_using_ssl,
                ssl_cert_reqs="none",
                socket_timeout=10,
                socket_connect_timeout=10,
            )

        # try to ping
        # while True:
        #     try:
        #         client.ping()
        #         break
        #     except:
        #         print("Redis server is not available ...")
        #         time.sleep(1)

        return client
    else:
        import redis

        return redis.StrictRedis(
            host=f"{address}",
            port=port,
            password=password,
            ssl=is_using_ssl,
            ssl_cert_reqs="none",
            socket_timeout=10,
            socket_connect_timeout=10,
        )

    return None


def create_db_from_args(args: NxsBaseArgs, type: NxsDbType) -> NxsDb:
    if type == NxsDbType.MONGODB:
        return NxsDbFactory.create_db(
            NxsDbType.MONGODB,
            uri=args.mongodb_uri,
            db_name=args.mongodb_db_name,
        )
    elif type == NxsDbType.REDIS:
        return NxsDbFactory.create_db(
            NxsDbType.REDIS,
            address=args.job_redis_queue_address,
            port=args.job_redis_queue_port,
            password=args.job_redis_queue_password,
            is_using_ssl=args.job_redis_queue_use_ssl,
        )

    raise NxsDbInvalidDbType


def create_storage_from_args(args: NxsBaseArgs, type: NxsStorageType) -> NxsStorage:
    if type == NxsStorageType.LocalStorage:
        return NxsStorageFactory.create_storage(NxsStorageType.LocalStorage)
    elif type == NxsStorageType.AzureBlobstorage:
        return NxsStorageFactory.create_storage(
            NxsStorageType.AzureBlobstorage,
            connection_str=args.storage_azure_blobstore_conn_str,
            container_name=args.storage_azure_blobstore_container_name,
        )

    raise NxsStorageExceptionInvalidStorageType


def create_simple_key_value_db_from_args(
    args: NxsBaseArgs, type: NxsSimpleKeyValueDbType
) -> NxsSimpleKeyValueDb:
    if type == NxsSimpleKeyValueDbType.REDIS:
        return NxsSimpleKeyValueDbFactory.create_simple_kv_db(
            NxsSimpleKeyValueDbType.REDIS,
            address=args.job_redis_queue_address,
            port=args.job_redis_queue_port,
            password=args.job_redis_queue_password,
            is_using_ssl=args.job_redis_queue_use_ssl,
        )

    raise NxsSipleKeyValueExceptionInvalidDbType


def create_queue_pusher_from_args(
    args: NxsBaseArgs, type: NxsQueueType
) -> NxsQueuePusher:
    if type == NxsQueueType.REDIS:
        return NxsQueuePusherFactory.create_queue_pusher(
            NxsQueueType.REDIS,
            address=args.job_redis_queue_address,
            port=args.job_redis_queue_port,
            password=args.job_redis_queue_password,
            is_using_ssl=args.job_redis_queue_use_ssl,
        )
    elif type == NxsQueueType.AZURE_QUEUE:
        return NxsQueuePusherFactory.create_queue_pusher(
            NxsQueueType.AZURE_QUEUE,
            conn_str=args.job_azure_queue_conn_str,
        )

    raise NxsQueueExceptionInvalidQueueType


def create_queue_puller_from_args(
    args: NxsBaseArgs, type: NxsQueueType, topic
) -> NxsQueuePuller:
    if type == NxsQueueType.REDIS:
        return NxsQueuePullerFactory.create_queue_puller(
            NxsQueueType.REDIS,
            address=args.job_redis_queue_address,
            port=args.job_redis_queue_port,
            password=args.job_redis_queue_password,
            is_using_ssl=args.job_redis_queue_use_ssl,
            topic=topic,
        )
    elif type == NxsQueueType.AZURE_QUEUE:
        return NxsQueuePullerFactory.create_queue_puller(
            NxsQueueType.AZURE_QUEUE,
            conn_str=args.job_azure_queue_conn_str,
            queue_name=topic,
        )

    raise NxsQueueExceptionInvalidQueueType
