import copy
import datetime
import time
from datetime import timezone
from typing import Any, Dict, List

from configs import GLOBAL_QUEUE_NAMES, MONGODB_STATS_COLLECTION_NAME
from nxs_libs.db import NxsDbQueryConfig, NxsDbSortType
from nxs_libs.queue import NxsQueueType
from nxs_libs.simple_key_value_db import NxsSimpleKeyValueDbType
from nxs_types.log import NxsBackendCmodelThroughputLog, NxsBackendThroughputLog
from nxs_types.nxs_args import NxsBackendMonitorArgs
from nxs_utils.nxs_helper import (
    create_db_from_args,
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

        self.last_num_reqs_dict: Dict[str, int] = {}
        self.total_reqs = 0
        self.merge_data_ts = time.time()
        self.last_sync_db_ts = time.time()

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
        try:
            db = create_db_from_args(args, args.db_type)
            results = db.query(
                MONGODB_STATS_COLLECTION_NAME,
                {},
                NxsDbQueryConfig(
                    sort_list=[("utc_ts", NxsDbSortType.DESCENDING)], limit=1
                ),
            )
            if results:
                self.total_reqs = results[0]["lifetime_reqs"]
                self.last_num_reqs_dict = results[0]["stats"]
        except Exception as ex:
            print(ex)
            self.total_reqs = 0
            self.last_num_reqs_dict = {}

        log_cache = []

        while True:
            logs: List[NxsBackendThroughputLog] = self.logs_puller.pull()

            self._process_logs(logs)

            stored_logs = self._get_stored_logs()

            self.kv_store.set_value(
                GLOBAL_QUEUE_NAMES.BACKEND_MONITOR_LOGS, stored_logs
            )

            try:
                if time.time() - self.merge_data_ts >= 60:
                    _current_last_num_reqs_dict: Dict[str, int] = {}

                    extra_num_reqs = 0
                    for backend_log in stored_logs:
                        for model_log in backend_log.model_logs:
                            model_uuid = model_log.model_uuid
                            model_num_reqs = model_log.total_reqs

                            merged_key = f"{backend_log.backend_name}_{model_uuid}"
                            _current_last_num_reqs_dict[merged_key] = model_num_reqs

                            prev_num_reqs = self.last_num_reqs_dict.get(merged_key, 0)
                            extra_num_reqs += max(0, model_num_reqs - prev_num_reqs)

                    self.total_reqs += extra_num_reqs
                    self.last_num_reqs_dict = _current_last_num_reqs_dict
                    self.merge_data_ts = time.time()

                    log_cache.append(
                        {
                            "interval_reqs": extra_num_reqs,
                            "interval_stats": copy.deepcopy(
                                _current_last_num_reqs_dict
                            ),
                        }
                    )

                if (
                    time.time() - self.last_sync_db_ts
                    > self.args.store_db_interval_secs
                ):

                    if len(log_cache) > 0:
                        interval_reqs = 0
                        _stats = {}
                        for log in log_cache:
                            interval_reqs += log["interval_reqs"]
                            for key in log["interval_stats"]:
                                _stats[key] = log["interval_stats"][key]

                        dt = datetime.datetime.now(timezone.utc)
                        utc_time = dt.replace(tzinfo=timezone.utc)
                        utc_timestamp = utc_time.timestamp()

                        db = create_db_from_args(args, args.db_type)
                        db.insert(
                            MONGODB_STATS_COLLECTION_NAME,
                            {
                                args.db_shard_key: args.db_shard_value,
                                "utc_ts": utc_timestamp,
                                "lifetime_reqs": self.total_reqs,
                                "interval_reqs": interval_reqs,
                                "stats": _stats,
                            },
                        )
                        db.close()

                        log_cache.clear()

                    self.last_sync_db_ts = time.time()

            except Exception as ex:
                print(ex)

            time.sleep(self.args.polling_interval_secs)


if __name__ == "__main__":
    from main_processes.backend_monitor.args import parse_args

    args = parse_args()

    monitor = NxsBasicBackendMonitor(args)
    monitor.run()
