from abc import ABC, abstractmethod
from typing import Dict, List
from enum import Enum
from nxs_libs.queue import NxsQueuePusherFactory, NxsQueueType


class BackendOutputInterfaceType(str, Enum):
    MULTIPROCESSING_SHARED_LIST = "mt_shared_list"
    MULTIPROCESSING_QUEUE = "mt_queue"
    REDIS = "redis"


class BackendOutputInterfaceExceptionInvalidType(Exception):
    pass


class BackendOutputInterface(ABC):
    def __init__(self) -> None:
        super().__init__()

    def put_batch(self, topic: str, batch: List, external_data: Dict = {}) -> None:
        raise NotImplementedError

    def get_num_buffered_items(self, topic: str):
        raise NotImplementedError


class BackendOutputToRedisQueue(BackendOutputInterface):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.queue = NxsQueuePusherFactory.create_queue_pusher(
            type=NxsQueueType.REDIS, **kwargs
        )

    def put_batch(self, topic: str, batch: List, external_data: Dict = {}) -> None:
        for item in batch:
            self.queue.push(topic, item)

    def get_num_buffered_items(self, topic: str):
        # FIXME: should aggregate #num_items in redis cluster
        raise NotImplementedError


class BackendOutputToMultiprocessingList(BackendOutputInterface):
    def __init__(self, mp_shared_list) -> None:
        super().__init__()
        self.mp_shared_list = mp_shared_list

    def put_batch(self, topic: str, batch: List, external_data: Dict = {}) -> None:
        for item in batch:
            self.mp_shared_list.append(item)

    def get_num_buffered_items(self, topic: str):
        return len(self.mp_shared_list)


class BackendOutputToMultiprocessingQueue(BackendOutputInterface):
    def __init__(self, mp_queue) -> None:
        super().__init__()
        self.mp_queue = mp_queue

    def put_batch(self, topic: str, batch: List, external_data: Dict = {}) -> None:
        for item in batch:
            self.mp_queue.put(item)

    def get_num_buffered_items(self, topic: str):
        return self.mp_queue.qsize()


class BackendOutputInterfaceFactory:
    @staticmethod
    def create_input_interface(
        type: BackendOutputInterfaceType, **kwargs
    ) -> BackendOutputInterface:
        if type == BackendOutputInterfaceType.MULTIPROCESSING_SHARED_LIST:
            return BackendOutputToMultiprocessingList(**kwargs)
        elif type == BackendOutputInterfaceType.MULTIPROCESSING_QUEUE:
            return BackendOutputToMultiprocessingQueue(**kwargs)
        elif type == BackendOutputInterfaceType.REDIS:
            return BackendOutputToRedisQueue(**kwargs)

        raise BackendOutputInterfaceExceptionInvalidType
