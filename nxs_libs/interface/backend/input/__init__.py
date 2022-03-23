from abc import ABC, abstractmethod
from typing import Dict, List
from enum import Enum
from nxs_libs.queue import NxsQueuePullerFactory, NxsQueueType

from nxs_libs.queue.nxs_redis_queue import NxsRedisQueuePuller


class BackendInputInterfaceType(str, Enum):
    MULTIPROCESSING_SHARED_LIST = "mt_shared_list"
    MULTIPROCESSING_QUEUE = "mt_queue"
    REDIS = "redis"


class BackendInputInterfaceExceptionInvalidType(Exception):
    pass


class BackendInputInterface(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def get_batch(self, external_data: Dict = {}) -> List:
        raise NotImplementedError

    def close_and_get_remains(self, external_data: Dict = {}):
        raise NotImplementedError

    @abstractmethod
    def set_buf_size(self, size: int):
        raise NotImplementedError

    @abstractmethod
    def get_num_buffered_items(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def set_num_partitions(self, num_partitions: int):
        raise NotImplementedError


class BackendInputFromRedisQueue(BackendInputInterface):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.queue = NxsQueuePullerFactory.create_queue_puller(
            type=NxsQueueType.REDIS, **kwargs
        )

    def get_batch(self, external_data: Dict = {}) -> List:
        return self.queue.pull()

    def close_and_get_remains(self, external_data: Dict = {}):
        return self.queue.pull_buffered_and_close()

    def set_buf_size(self, size: int):
        self.queue.set_buf_size(size)

    def get_num_buffered_items(self) -> int:
        pass

    def set_num_partitions(self, num_partitions: int):
        self.queue.set_num_partitions(num_partitions)


class BackendInputFromMultiprocessingSharedList(BackendInputInterface):
    def __init__(self, mp_shared_list) -> None:
        super().__init__()
        self.mp_shared_list = mp_shared_list

    def get_batch(self, external_data: Dict = {}) -> List:
        if not self.mp_shared_list:
            return []

        batch = []

        # for _ in range(len(self.mp_shared_list)):
        #    batch.append(self.mp_shared_list.pop(0))

        queue_len = min(len(self.mp_shared_list), external_data.get("max_items", 9999))
        for _ in range(queue_len):
            try:
                data = self.mp_shared_list.pop(0)
                batch.append(data)
            except:
                break

        return batch

    def close_and_get_remains(self, external_data: Dict = {}):
        return self.get_batch()

    def set_buf_size(self, size: int):
        pass

    def get_num_buffered_items(self) -> int:
        return len(self.mp_shared_list)

    def set_num_partitions(self, num_partitions: int):
        pass


class BackendInputFromMultiprocessingQueue(BackendInputInterface):
    def __init__(self, mp_queue) -> None:
        super().__init__()
        self.mp_queue = mp_queue

    def get_batch(self, external_data: Dict = {}) -> List:

        if self.mp_queue.empty():
            return []

        batch = []

        queue_len = min(self.mp_queue.qsize(), external_data.get("max_items", 32))
        try:
            for _ in range(queue_len):
                data = self.mp_queue.get(block=True, timeout=0.01)
                batch.append(data)
        except:
            pass

        return batch

    def close_and_get_remains(self, external_data: Dict = {}):
        return self.get_batch()

    def set_buf_size(self, size: int):
        pass

    def get_num_buffered_items(self) -> int:
        return self.mp_queue.qsize()

    def set_num_partitions(self, num_partitions: int):
        pass


class BackendInputInterfaceFactory:
    @staticmethod
    def create_input_interface(
        type: BackendInputInterfaceType, **kwargs
    ) -> BackendInputInterface:
        if type == BackendInputInterfaceType.MULTIPROCESSING_SHARED_LIST:
            return BackendInputFromMultiprocessingSharedList(**kwargs)
        if type == BackendInputInterfaceType.MULTIPROCESSING_QUEUE:
            return BackendInputFromMultiprocessingQueue(**kwargs)
        elif type == BackendInputInterfaceType.REDIS:
            return BackendInputFromRedisQueue(**kwargs)

        raise BackendInputInterfaceExceptionInvalidType
