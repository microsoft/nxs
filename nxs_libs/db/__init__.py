from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
from enum import Enum
from nxs_types import DataModel


class NxsDbType(str, Enum):
    MONGODB = "mongodb"
    REDIS = "redis"


class NxsDbSortType(int, Enum):
    DESCENDING = -1
    ASCENDING = 1


class NxsDbQueryConfig(DataModel):
    projection_list: List[str] = []
    sort_list: List[Tuple[str, NxsDbSortType]] = []
    skip: int = 0
    limit: int = None


class NxsDbExceptionMissingShardKey(Exception):
    pass


class NxsDbInvalidDbType(Exception):
    pass


class NxsDb(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def query(
        self,
        collection_name: str,
        query: Dict,
        query_config: NxsDbQueryConfig = NxsDbQueryConfig(),
        extra_params: Dict = {},
    ) -> List:
        raise NotImplementedError

    @abstractmethod
    def insert(self, collection_name: str, data: Dict, extra_params: Dict = {}) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        collection_name: str,
        query: Dict,
        new_data: Dict,
        insert_if_not_existed: bool = False,
        extra_params: Dict = {},
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(
        self, collection_name: str, query: Dict, extra_params: Dict = {}
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class NxsDbFactory:
    @staticmethod
    def create_db(type: NxsDbType, **kwargs) -> NxsDb:
        if type == NxsDbType.MONGODB:
            from nxs_libs.db.nxs_mongodb import NxsMongoDb

            return NxsMongoDb(**kwargs)
        elif type == NxsDbType.REDIS:
            from nxs_libs.db.nxs_redis import NxsSimpleRedisDB

            return NxsSimpleRedisDB(**kwargs)

        raise NxsDbInvalidDbType
