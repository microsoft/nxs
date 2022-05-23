import pickle
import time
from typing import Any, Dict
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

    def _recreate_client(self):
        try:
            self._client = init_redis_client(
                self._address, self._port, self._password, self._is_using_ssl
            )
        except:
            pass

    def _set_with_retry(self, key: str, data: Any, expiration_duration_secs: int = 0):
        while True:
            try:
                self._client.set(key, data)

                if expiration_duration_secs > 0:
                    self._client.expire(key, expiration_duration_secs)

                break
            except:
                time.sleep(0.01)
                self._recreate_client()

    def _get_with_retry(self, key: str):
        while True:
            try:
                data = self._client.get(key)
                return data
            except:
                time.sleep(0.01)
                self._recreate_client()

    def _delete_with_retry(self, key: str):
        while True:
            try:
                self._client.delete(key)
                break
            except:
                time.sleep(0.01)
                self._recreate_client()

    def set_value(self, key: str, value, extra_params: dict = {}):
        # self._client.set(key, pickle.dumps(value))
        self._set_with_retry(key, pickle.dumps(value))

    def get_value(self, key: str, extra_params: dict = {}):
        # data = self._client.get(key)
        data = self._get_with_retry(key)

        if data:
            data = pickle.loads(data)

        return data

    def delete_key(self, key: str, extra_params: dict = {}):
        # self._client.delete(key)
        self._delete_with_retry(key)
