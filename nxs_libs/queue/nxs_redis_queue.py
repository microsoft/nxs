import pickle
import time
from threading import Thread
from typing import Any, Dict, List

import numpy as np
from nxs_libs.queue import NxsQueuePuller, NxsQueuePusher
from nxs_utils.logging import NxsLogLevel, write_log
from nxs_utils.nxs_helper import init_redis_client


class NxsRedisQueuePuller(NxsQueuePuller):
    def __init__(
        self,
        address: str,
        port: int,
        password: str,
        is_using_ssl: bool,
        topic: str,
        **kwargs,
    ) -> None:
        super().__init__()

        self._address = address
        self._port = port
        self._password = password
        self._is_using_ssl = is_using_ssl
        self._session_uuid = ""
        if "session_uuid" in kwargs:
            self._session_uuid: str = kwargs["session_uuid"]
        self._topic = (
            f"{topic}_{self._session_uuid}" if self._session_uuid != "" else topic
        )

        self._client = init_redis_client(
            self._address, self._port, self._password, self._is_using_ssl
        )

        self._log_level = NxsLogLevel.INFO
        self._logging_prefix = f"NxsRedisQueuePuller_{self._topic}"

        """
        The current design stores number of partitions the key has in "topic" key.
        Depending on number of partitions, real data will be spanned across multiple keys such as topic_0, topic_1, etc...        
        """
        self._check_num_partitions_period_secs = 3
        self._check_num_partitions_t0: float = time.time()
        self._num_partitions = self._get_topic_num_partitions()

        self._count = 0  # number of items returned to user
        self._buf_size = 1  # maximum size of shared data store
        self._buf = []  # this is used as shared data store for all reader threads

        self._max_timeout_secs = 1  # maximum timeout for each thread to read data
        self._check_topic_period_secs = 3

        # spawn threads to read data
        self._reader_threads: List[Thread] = []
        self._reader_thread_alive_flags: List[
            bool
        ] = []  # use this to control thread's liveliness

        # create reader threads
        for tid in range(self._num_partitions):
            t = Thread(target=self._reader_thread_fn, args=(tid,))
            self._reader_threads.append(t)
            self._reader_thread_alive_flags.append(True)
            t.start()

        # create monitoring thread
        self._monitor_thread = Thread(target=self._monitor_thread_fn, args=())
        self._monitor_thread_alive_flag = True
        self._monitor_thread.start()

    def _recreate_client(self):
        try:
            self._client = init_redis_client(
                self._address, self._port, self._password, self._is_using_ssl
            )
        except:
            pass

    def _set_with_retry(self, topic: str, data: Any, expiration_duration_secs: int = 0):
        while True:
            try:
                self._client.set(topic, data)

                if expiration_duration_secs > 0:
                    self._client.expire(topic, expiration_duration_secs)

                break
            except:
                time.sleep(0.01)
                self._recreate_client()

    def _push_with_retry(self, topic: str, data: Any, expiration_duration_secs: int):
        while True:
            try:
                self._client.rpush(topic, data)
                self._client.expire(topic, expiration_duration_secs)
                break
            except:
                time.sleep(0.01)
                self._recreate_client()

    def _get_with_retry(self, topic: str):
        while True:
            try:
                data = self._client.get(topic)
                return data
            except:
                time.sleep(0.01)
                self._recreate_client()

    def _reader_thread_fn(self, thread_id: int):
        topic = f"{self._topic}_{thread_id}"
        self._log(f"Read thread {thread_id} was created for topic {topic} !!!")
        # print(f"Read thread {thread_id} was created for topic {topic} !!!")

        # reader thread should use its own client
        client = init_redis_client(
            self._address, self._port, self._password, self._is_using_ssl
        )

        while self._reader_thread_alive_flags[thread_id]:
            # standby if buffer is full
            if len(self._buf) >= self._buf_size:
                time.sleep(0.001)
                continue

            try:
                data = client.blpop([topic], timeout=self._max_timeout_secs)
                if data is None:
                    time.sleep(0.001)
                    continue

                _, d = data
                d = pickle.loads(d)
                self._buf.append(d)
            except:
                time.sleep(0.01)
                client = init_redis_client(
                    self._address, self._port, self._password, self._is_using_ssl
                )

        self._log(
            f"Reader thread {thread_id} / {self._num_partitions} is being terminated!!!"
        )

    def _monitor_thread_fn(self):
        self._log("Monitoring thread was created!!!")

        while self._monitor_thread_alive_flag:
            if (
                time.time() - self._check_num_partitions_t0
                < self._check_num_partitions_period_secs
            ):
                time.sleep(0.1)
                continue

            try:
                num_partitions = self._get_topic_num_partitions()

                # scale # threads if needed
                delta = abs(num_partitions - self._num_partitions)
                for _ in range(delta):
                    if num_partitions > self._num_partitions:
                        self._add_reader_thread()
                    elif num_partitions < self._num_partitions:
                        self._remove_read_thread()

                self._num_partitions = num_partitions
                self._check_num_partitions_t0 = time.time()
            except:
                time.sleep(0.01)
                self._recreate_client()

        self._log("Monitoring thread is being terminated!!!")

    def _add_reader_thread(self):
        tid = len(self._reader_threads)
        t = Thread(target=self._reader_thread_fn, args=(tid,))
        self._reader_threads.append(t)
        self._reader_thread_alive_flags.append(True)
        t.start()

    def _remove_read_thread(self):
        t = self._reader_threads[-1]

        # trigger thread t to exit
        self._reader_thread_alive_flags[-1] = False
        t.join()

        self._reader_threads.pop(-1)
        self._reader_thread_alive_flags.pop(-1)

    def _get_topic_num_partitions(self) -> int:
        # data = self._client.get(self._topic)
        data = self._get_with_retry(self._topic)

        if not isinstance(data, type(None)):
            return pickle.loads(data)

        return 1

    def pull(self) -> List:
        results = []

        cur_buf_size = len(self._buf)
        for _ in range(cur_buf_size):
            data = self._buf.pop(0)
            results.append(data)

        return results

    def pull_buffered_and_close(self) -> List:
        # stop receiving data
        self._buf_size = 0

        # stop all threads
        self._monitor_thread_alive_flag = False
        for i in range(len(self._reader_thread_alive_flags)):
            self._reader_thread_alive_flags[i] = False

        self._monitor_thread.join()
        for t in self._reader_threads:
            t.join()

        return self.pull()

    def update_buf_size(self, new_buf_size: int):
        assert new_buf_size > 0, "new_buf_size should be larger than 0!!!"
        self._buf_size = new_buf_size

    def update_max_timeout(self, timeout_secs: float):
        assert timeout_secs >= 0.001, "timeout_secs should be at least 1ms!!!"
        self._max_timeout_secs = timeout_secs

    def update_check_num_partition_period(self, period_secs: float):
        assert period_secs >= 1, "period_secs should be at least 1 second!!!"
        self._check_num_partitions_period_secs = period_secs

    def change_log_level(self, level: NxsLogLevel):
        self._log_level = level

    def _log(self, log):
        write_log(self._logging_prefix, log, self._log_level)

    def set_buf_size(self, size: int):
        if size > 0:
            self.update_buf_size(size)

    def get_num_buffered_items(self):
        return len(self._buf)

    def set_num_partitions(self, num_partitions: int):
        # self._client.set(self._topic, pickle.dumps(num_partitions))
        self._set_with_retry(self._topic, pickle.dumps(num_partitions))


class NxsRedisQueuePusher(NxsQueuePusher):
    def __init__(
        self,
        address: str,
        port: int,
        password: str,
        is_using_ssl: bool,
        **kwargs,
    ) -> None:
        super().__init__()

        self._address = address
        self._port = port
        self._password = password
        self._is_using_ssl = is_using_ssl

        self._client = init_redis_client(
            self._address, self._port, self._password, self._is_using_ssl
        )

        self._log_level = NxsLogLevel.INFO
        self._logging_prefix = f"NxsRedisQueuePusher"

        self._topic2partitions: dict[str, int] = {}
        self._topic2partitionIdx: dict[str, int] = {}
        self._topic2timestamp: dict[str, float] = {}

        self._check_num_partitions_period_secs = 3
        self._new_topic_num_partitions = 1
        self._expiration_duration_secs: int = 3600

    def _recreate_client(self):
        try:
            self._client = init_redis_client(
                self._address, self._port, self._password, self._is_using_ssl
            )
        except:
            pass

    def _set_with_retry(self, topic: str, data: Any, expiration_duration_secs: int = 0):
        while True:
            try:
                self._client.set(topic, data)

                if expiration_duration_secs > 0:
                    self._client.expire(topic, expiration_duration_secs)

                break
            except:
                time.sleep(0.01)
                self._recreate_client()

    def _push_with_retry(self, topic: str, data: Any, expiration_duration_secs: int):
        while True:
            try:
                self._client.rpush(topic, data)
                self._client.expire(topic, expiration_duration_secs)
                break
            except:
                time.sleep(0.01)
                self._recreate_client()

    def _get_with_retry(self, topic: str):
        while True:
            try:
                data = self._client.get(topic)
                return data
            except:
                time.sleep(0.01)
                self._recreate_client()

    def create_topic(self, topic: str):
        # self._client.set(topic, pickle.dumps(self._new_topic_num_partitions))
        self._set_with_retry(topic, pickle.dumps(self._new_topic_num_partitions))
        self._topic2partitions[topic] = self._new_topic_num_partitions
        self._topic2timestamp[topic] = time.time()
        self._topic2partitionIdx[topic] = 0

    def push(self, topic: str, data):
        if (not topic in self._topic2timestamp) or (
            time.time() - self._topic2timestamp[topic]
            > self._check_num_partitions_period_secs
        ):
            num_partitions = self._get_topic_num_partitions(topic)
            self._topic2partitions[topic] = num_partitions
            self._topic2partitionIdx[topic] = 0
            self._topic2timestamp[topic] = time.time()

        # chosen_partition_idx = np.random.randint(self._topic2partitions[topic])
        chosen_partition_idx = self._topic2partitionIdx[topic]
        self._topic2partitionIdx[topic] = (
            self._topic2partitionIdx[topic] + 1
        ) % self._topic2partitions[topic]

        partitioned_topic = self._get_partitioned_topic_name(
            topic, chosen_partition_idx
        )

        # self._client.rpush(partitioned_topic, pickle.dumps(data))
        # self._client.expire(partitioned_topic, self._expiration_duration_secs)
        self._push_with_retry(
            partitioned_topic, pickle.dumps(data), self._expiration_duration_secs
        )

    def push_to_session(self, topic: str, session_uuid: str, data) -> None:
        new_topic = f"{topic}_{session_uuid}"
        return self.push(new_topic, data)

    def delete_topic(self, topic: str):
        pass

    def update_check_num_partition_period(self, period_secs: float):
        self._check_num_partitions_period_secs = period_secs

    def update_new_topic_num_partitions(self, num_partitions: int):
        assert num_partitions >= 1, "num_partitions should be larger than 0 !!!"
        self._new_topic_num_partitions = num_partitions

    def update_expiration_duration_secs(self, duration_secs: float):
        assert duration_secs >= 30, "duration_secs should be larger than 30 !!!"
        self._expiration_duration_secs = int(duration_secs)

    def _get_partitioned_topic_name(self, topic: str, partition_idx: int):
        return f"{topic}_{partition_idx}"

    def _get_topic_num_partitions(self, topic) -> int:
        # data = self._client.get(topic)
        data = self._get_with_retry(topic)

        if not isinstance(data, type(None)):
            return pickle.loads(data)

        return 1

    def _set_topic_num_partitions(self, topic: str, num_partitions: int):
        # self._client.set(topic, pickle.dumps(num_partitions))
        self._set_with_retry(topic, pickle.dumps(num_partitions))

    def update_config(self, config: dict = {}):
        if "num_partitions" in config:
            self._new_topic_num_partitions = config["num_partitions"]

    def _log(self, log):
        write_log(self._logging_prefix, log, self._log_level)
