import pickle
from typing import Dict
from nxs_libs.simple_key_value_db import NxsSimpleKeyValueDb
from nxs_utils.nxs_helper import init_redis_client


class NxsRedisSimpleKeyValueDb(NxsSimpleKeyValueDb):
    def __init__(
        self, address: str, port: int, password: str, is_using_ssl: bool, **kwargs
    ) -> None:
        super().__init__()

        self._address = address
        self._port = port
        self._password = password
        self._is_using_ssl = is_using_ssl

        self._client = init_redis_client(
            self._address, self._port, self._password, self._is_using_ssl
        )

    def set_value(self, key: str, value, extra_params: dict = {}):
        self._client.set(key, pickle.dumps(value))

    def get_value(self, key: str, extra_params: dict = {}):
        data = self._client.get(key)

        if data:
            data = pickle.loads(data)

        return data

    def delete_key(self, key: str, extra_params: dict = {}):
        self._client.delete(key)
