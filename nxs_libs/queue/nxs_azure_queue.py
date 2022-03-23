import time
import pickle
import json
import numpy as np
from threading import Thread
from typing import Dict, List
from nxs_libs.queue import *

from azure.core import exceptions as AzureCoreException

from azure.storage.queue import (
    QueueClient,
)


class NxsAzureQueuePuller(NxsQueuePuller):
    def __init__(self, conn_str: str, queue_name: str, **kwargs) -> None:
        super().__init__()

        self._conn_str = conn_str
        self._session_uuid = ""
        if "session_uuid" in kwargs:
            self._session_uuid: str = kwargs["session_uuid"]
        self._queue_name = f"{queue_name}{self._session_uuid}"
        self._queue_client = QueueClient.from_connection_string(
            self._conn_str, self._queue_name
        )

    def pull(self) -> List:
        results = []

        # FIXME: Catch non-existing queue exception or any other exceptions
        messages = self._queue_client.receive_messages()

        for message in messages:
            data = json.loads(message.content)
            self._queue_client.delete_message(message)
            results.append(data)

        return results

    def pull_buffered_and_close(self) -> List:
        self._queue_client.close()
        return []

    def set_buf_size(self, size: int):
        pass

    def get_num_buffered_items(self):
        properties = self._queue_client.get_queue_properties()
        return properties.approximate_message_count

    def set_num_partitions(self, num_partitions: int):
        pass


class NxsAzureQueuePusher(NxsQueuePusher):
    def __init__(self, conn_str: str) -> None:
        super().__init__()
        self._conn_str = conn_str
        self._topic2client: Dict[str, QueueClient] = {}

    def create_topic(self, topic: str) -> None:
        if topic in self._topic2client:
            return

        client = QueueClient.from_connection_string(self._conn_str, topic)

        try:
            client.create_queue()
            self._topic2client[topic] = client
        except AzureCoreException.ResourceExistsError as e:
            # queue is already existed - no need to create
            self._topic2client[topic] = client
        except Exception as e:
            raise NxsQueueExceptionFailedToCreateTopic

    def push(self, topic: str, data) -> None:
        if topic not in self._topic2client:
            self.create_topic(topic)

        queue_client = self._topic2client[topic]
        queue_client.send_message(json.dumps(data))

    def push_to_session(self, topic: str, session_uuid: str, data) -> None:
        new_topic = f"{topic}{session_uuid}"
        return self.push(new_topic, data)

    def delete_topic(self, topic: str) -> None:
        pass

    def update_config(self, config: dict = {}):
        pass
