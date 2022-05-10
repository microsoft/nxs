import time
from typing import Any, Dict, List
from configs import GLOBAL_QUEUE_NAMES
from nxs_libs.queue import NxsQueueType
from nxs_libs.simple_key_value_db import NxsSimpleKeyValueDbType
from nxs_types.log import NxsBackendCmodelThroughputLog, NxsBackendThroughputLog
from nxs_types.nxs_args import NxsBackendMonitorArgs
from nxs_utils.nxs_helper import (
    create_queue_puller_from_args,
    create_queue_pusher_from_args,
    create_simple_key_value_db_from_args,
)


class NxsBasicBackendMonitor:
    def __init__(self, args: NxsBackendMonitorArgs) -> None:
        self.args = args
        self.model_expiration_secs = 30
        self.logs_puller = create_queue_puller_from_args(
            args, NxsQueueType.REDIS, GLOBAL_QUEUE_NAMES.BACKEND_LOGS
        )
        self.logs_puller.set_buf_size(999)
        self.kv_store = create_simple_key_value_db_from_args(
            args, NxsSimpleKeyValueDbType.REDIS
        )

        self.logs_dict: Dict[str, Any] = {}
        self.logs_ts_dict: Dict[str, float] = {}

    def _process_logs(self, logs: List[NxsBackendThroughputLog]):
        ts = time.time()

        keys_to_remove = []
        for key in self.logs_dict:
            if ts - self.logs_ts_dict[key] > self.model_expiration_secs:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self.logs_dict.pop(key)
            self.logs_ts_dict.pop(key)

        for log in logs:
            key = log.backend_name
            self.logs_dict[key] = log
            self.logs_ts_dict[key] = ts

    def _get_stored_logs(self) -> List[NxsBackendThroughputLog]:
        logs: List[NxsBackendThroughputLog] = []

        for key in self.logs_dict:
            logs.append(self.logs_dict[key])

        return logs

    def run(self):
        while True:
            logs: List[NxsBackendThroughputLog] = self.logs_puller.pull()

            self._process_logs(logs)

            self.kv_store.set_value(
                GLOBAL_QUEUE_NAMES.BACKEND_MONITOR_LOGS, self._get_stored_logs()
            )

            time.sleep(self.args.polling_interval_secs)


if __name__ == "__main__":
    from main_processes.backend_monitor.args import parse_args

    args = parse_args()

    monitor = NxsBasicBackendMonitor(args)
    monitor.run()
