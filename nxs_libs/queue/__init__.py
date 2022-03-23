from abc import ABC, abstractmethod
from typing import Dict, List
from enum import Enum


class NxsQueueExceptionInvalidQueueType(Exception):
    pass


class NxsQueueExceptionNotFoundTopic(Exception):
    pass


class NxsQueueExceptionFailedToCreateTopic(Exception):
    pass


class NxsQueueExceptionInternalError(Exception):
    pass


class NxsQueueType(str, Enum):
    REDIS = "redis"
    AZURE_QUEUE = "azure_queue"


class NxsQueuePuller(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def pull(self) -> List:
        raise NotImplementedError

    @abstractmethod
    def pull_buffered_and_close(self) -> List:
        raise NotImplementedError

    @abstractmethod
    def set_buf_size(self, size: int):
        raise NotImplementedError

    @abstractmethod
    def get_num_buffered_items(self):
        raise NotImplementedError

    @abstractmethod
    def set_num_partitions(self, num_partitions: int):
        raise NotImplementedError


class NxsQueuePusher(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def create_topic(self, topic: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def push(self, topic: str, data) -> None:
        raise NotImplementedError

    @abstractmethod
    def push_to_session(self, topic: str, session_uuid: str, data) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_topic(self, topic: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_config(self, config: dict = {}) -> None:
        raise NotImplementedError


class NxsQueuePullerFactory:
    @staticmethod
    def create_queue_puller(type: NxsQueueType, **kwargs) -> NxsQueuePuller:
        if type == NxsQueueType.REDIS:
            from nxs_libs.queue.nxs_redis_queue import (
                NxsRedisQueuePuller,
            )

            return NxsRedisQueuePuller(**kwargs)
        elif type == NxsQueueType.AZURE_QUEUE:
            from nxs_libs.queue.nxs_azure_queue import (
                NxsAzureQueuePuller,
            )

            return NxsAzureQueuePuller(**kwargs)

        raise NxsQueueExceptionInvalidQueueType


class NxsQueuePusherFactory:
    @staticmethod
    def create_queue_pusher(type: NxsQueueType, **kwargs) -> NxsQueuePusher:
        if type == NxsQueueType.REDIS:
            from nxs_libs.queue.nxs_redis_queue import (
                NxsRedisQueuePusher,
            )

            return NxsRedisQueuePusher(**kwargs)
        elif type == NxsQueueType.AZURE_QUEUE:
            from nxs_libs.queue.nxs_azure_queue import (
                NxsAzureQueuePusher,
            )

            return NxsAzureQueuePusher(**kwargs)

        raise NxsQueueExceptionInvalidQueueType
