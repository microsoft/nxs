import time
from typing import List
from nxs_libs.simple_key_value_db import NxsSimpleKeyValueDb
from nxs_libs.db import NxsDb
from nxs_types.backend import BackendInfo, BackendStat


class NxsBackendRuntime:
    def __init__(self, backend_info: BackendInfo, last_alive_ts=None) -> None:
        self.backend_info = backend_info

        self.last_alive_ts = time.time() if last_alive_ts is None else last_alive_ts

        self._has_gpu = False
        if self.backend_info.state.gpu_info is not None:
            self._has_gpu = True

        print(self.backend_info)

    def get_backend_name(self) -> str:
        return self.backend_info.backend_name

    def get_runtime_info(self) -> BackendInfo:
        # return a copy
        return BackendInfo(**(self.backend_info.dict()))

    def has_gpu(self):
        return self._has_gpu

    def update_info_from_heartbeat(self, new_stat: BackendStat):
        self.backend_info.state = new_stat
        self.last_alive_ts = time.time()

    def get_last_alive_ts(self) -> float:
        return self.last_alive_ts

    def update_entry_in_db(self, db: NxsSimpleKeyValueDb):
        db.set_value(
            NxsBackendRuntime.get_topic_name(self.backend_info.backend_name),
            self.get_runtime_info(),
        )
        db.set_value(
            NxsBackendRuntime.get_last_ts_alive_topic_name(
                self.backend_info.backend_name
            ),
            self.last_alive_ts,
        )

    def remove(self, db: NxsSimpleKeyValueDb):
        db.delete_key(NxsBackendRuntime.get_topic_name(self.backend_info.backend_name))

    @staticmethod
    def get_topic_name(backend_name):
        return f"backend_{backend_name}"

    @staticmethod
    def get_last_ts_alive_topic_name(backend_name):
        return f"{NxsBackendRuntime.get_topic_name(backend_name)}_ts"

    @classmethod
    def get_data_from_db(cls, backend_name: str, db: NxsSimpleKeyValueDb):
        backend_info: NxsBackendRuntime = db.get_value(
            NxsBackendRuntime.get_topic_name(backend_name)
        )

        if backend_info is not None:
            last_ts_alive = db.get_value(
                NxsBackendRuntime.get_last_ts_alive_topic_name(backend_name)
            )
            return cls(backend_info, last_ts_alive)

        return None
