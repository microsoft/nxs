import os
import pickle
import time
import json
import cv2
import copy
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict
from configs import NXS_CONFIG
from nxs_libs.interface.backend.input import (
    BackendInputInterfaceFactory,
)
from nxs_libs.interface.backend.output import (
    BackendOutputInterfaceFactory,
)
from nxs_types.infer_result import NxsInferStatus
from nxs_types.model import (
    NxsModel,
)
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan
from nxs_utils.logging import NxsLogLevel, write_log


class BackendBatcherProcess:
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        input_interface_args: Dict,
        output_interface_args: Dict,
        stop_flag,
        next_process_stop_flag,
        extra_params: Dict = {},
    ) -> None:
        self.component_model = component_model
        self.component_model_plan = component_model_plan
        self.input_interface_args = input_interface_args
        self.output_interface_args = output_interface_args
        self.stop_flag = stop_flag
        self.next_process_stop_flag = next_process_stop_flag
        self.extra_params = extra_params

        self.p = None
        self.preproc_fn = None
        self.preproc_extra_params = {}

        try:
            self.preproc_extra_params = json.loads(
                self.component_model.model_desc.extra_preprocessing_metadata
            )
        except:
            pass

        self.log_prefix = "{}_BATCHER".format(component_model.model_uuid)
        self.log_level = os.environ.get(NXS_CONFIG.LOG_LEVEL, NxsLogLevel.INFO)

        self.next_topic_name = "{}_COMPUTE".format(component_model.model_uuid)

    def _log(self, message):
        write_log(self.log_prefix, message, self.log_level)

    def run(self):
        from multiprocessing import Process

        self.p = Process(target=self._run, args=())
        self.p.start()

    def _run(self):
        cross_requests_batching = self.component_model.cross_requests_batching

        max_latency = 1  # in secs

        max_batch_size = self.component_model_plan.batch_size
        for profile_unit in self.component_model.profile:
            if profile_unit.batch_size == max_batch_size:
                max_latency = profile_unit.latency_e2e.max / 1000.0  # in secs
                break

        self.input = BackendInputInterfaceFactory.create_input_interface(
            **self.input_interface_args
        )
        self.output = BackendOutputInterfaceFactory.create_input_interface(
            **self.output_interface_args
        )

        current_batch = []
        current_metadata_batch = []

        waiting_t0 = time.time()
        to_exit = False
        tt0 = time.time()

        requests_count = 0

        while True:
            items = []
            if not self.stop_flag.value:
                items = self.input.get_batch()
            else:
                items = self.input.close_and_get_remains()
                to_exit = True

            for item in items:
                preprocessed_data, metadata = item

                current_batch.append(preprocessed_data)
                current_metadata_batch.append(metadata)

                if len(current_batch) == 1:
                    waiting_t0 = time.time()

                if not cross_requests_batching or len(current_batch) >= max_batch_size:
                    requests_count += len(current_batch)

                    # transform batch to {key -> []}
                    transformed_batch = {}

                    for item in current_batch:
                        for tensor_name in item:
                            if not tensor_name in transformed_batch.keys():
                                transformed_batch[tensor_name] = []
                            transformed_batch[tensor_name].extend(item[tensor_name])

                    # for metadata in current_metadata_batch:
                    #     self.request_exiting(metadata["extra"])

                    self.output.put_batch(
                        self.next_topic_name,
                        [(transformed_batch, current_metadata_batch)],
                    )

                    current_batch = []
                    current_metadata_batch = []

            if current_batch and cross_requests_batching:
                # wait for a bit if the batch is not full
                if time.time() - waiting_t0 > max_latency / 2:
                    requests_count += len(current_batch)

                    # transform [{key -> item}] into {key -> [items]}
                    transformed_batch = {}

                    for item in current_batch:
                        for tensor_name in item:
                            if not tensor_name in transformed_batch.keys():
                                transformed_batch[tensor_name] = []
                            transformed_batch[tensor_name].extend(item[tensor_name])

                    for metadata in current_metadata_batch:
                        self.request_exiting(metadata["extra"])

                    self.output.put_batch(
                        self.next_topic_name,
                        [(transformed_batch, current_metadata_batch)],
                    )

                    current_batch = []
                    current_metadata_batch = []

            if time.time() - tt0 > 5:
                if requests_count > 0:
                    fps = requests_count / (time.time() - tt0)
                    print("batcher", "fps", fps)
                requests_count = 0
                tt0 = time.time()

            if to_exit:
                break

            if not items:
                time.sleep(0.01)

        # trigger next process to stop
        self.next_process_stop_flag.value = True

        self._log("Exiting...")

    def stop(self):
        self.stop_flag.value = True
        self.p.join()

    def request_exiting(self, extra_metadata: Dict):
        preprocessing_t0 = extra_metadata[self.component_model.model_uuid].pop(
            "preprocessing_t0"
        )
        extra_metadata[self.component_model.model_uuid]["preprocessing_lat"] = (
            time.time() - preprocessing_t0
        )
