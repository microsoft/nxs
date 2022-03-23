from abc import ABC, abstractmethod
from typing import Dict, List
from enum import Enum


class NxsSipleKeyValueExceptionInvalidDbType(Exception):
    pass


class NxsSimpleKeyValueDbType(str, Enum):
    REDIS = "redis"


class NxsSimpleKeyValueDb(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def set_value(self, key: str, value, extra_params: dict = {}):
        raise NotImplementedError

    @abstractmethod
    def get_value(self, key: str, extra_params: dict = {}):
        raise NotImplementedError

    @abstractmethod
    def delete_key(self, key: str, extra_params: dict = {}):
        raise NotImplementedError


class NxsSimpleKeyValueDbFactory:
    @staticmethod
    def create_simple_kv_db(type: NxsSimpleKeyValueDbType, **kwargs):
        if type == NxsSimpleKeyValueDbType.REDIS:
            from nxs_libs.simple_key_value_db.nxs_redis_kv_db import (
                NxsRedisSimpleKeyValueDb,
            )

            return NxsRedisSimpleKeyValueDb(**kwargs)

        raise NxsSipleKeyValueExceptionInvalidDbType
