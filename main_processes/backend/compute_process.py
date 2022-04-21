import logging
import os
import time
import json
import copy
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List
from configs import BACKEND_INTERNAL_CONFIG, NXS_BACKEND_CONFIG, NXS_CONFIG
from nxs_types.infer import NxsInferRequestMetadata
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.model import NxsModel
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan
from nxs_libs.interface.backend.input import (
    BackendInputInterface,
    BackendInputInterfaceFactory,
)
from nxs_libs.interface.backend.output import (
    BackendOutputInterfaceFactory,
)
from nxs_utils.logging import NxsLogLevel, setup_logger, write_log


class BackendComputeProcess(ABC):
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        model_path: str,
        use_gpu: bool,
        transforming_fn_path: str,
        input_interface_args_list: List[Dict],
        output_interface_args: Dict,
        allow_infer_flag,
        stop_flags,
        next_process_stop_flag,
        extra_params: Dict = {},
    ) -> None:
        self.args = args
        self.component_model = component_model
        self.component_model_plan = component_model_plan
        self.model_path = model_path
        self.use_gpu = use_gpu
        self.input_interface_args_list = input_interface_args_list
        self.output_interface_args = output_interface_args
        self.allow_infer_flag = allow_infer_flag
        self.stop_flags = stop_flags
        self.next_process_stop_flag = next_process_stop_flag
        self.extra_params = extra_params
        self.transforming_fn_path = transforming_fn_path

        self.log_prefix = "{}_COMPUTE".format(component_model.model_uuid)
        # self.log_level = os.environ.get(NXS_CONFIG.LOG_LEVEL, NxsLogLevel.INFO)
        self.next_topic_name = "{}_OUTPUT".format(component_model.model_uuid)

        self.input_tensor_names = [
            input.name for input in self.component_model.model_desc.inputs
        ]
        self.output_tensor_names = [
            output.name for output in self.component_model.model_desc.outputs
        ]

        self.max_batch_size = self.component_model_plan.batch_size
        self.batching = self.component_model.batching
        self.cross_requests_batching = self.component_model.cross_requests_batching

        self.supported_batch_sizes = []
        for profile_unit in self.component_model.profile:
            if profile_unit.batch_size <= self.max_batch_size:
                self.supported_batch_sizes.append(profile_unit.batch_size)
        self.supported_batch_sizes.sort()

        self.p = None
        self.transform_fn = None
        self.transform_extra_params = {
            "max_batch_size": self.max_batch_size,
            "supported_batch_sizes": self.supported_batch_sizes,
        }

        setup_logger()

    # def _log(self, message):
    #     write_log(self.log_prefix, message, self.log_level)

    def _log(self, message, log_level=logging.INFO):
        logging.log(log_level, f"{self.log_prefix} - {message}")

    def run(self):
        from multiprocessing import Process

        self.p = Process(target=self._run, args=())
        self.p.start()

    def read_queue_thr(
        self, tid: int, queue: BackendInputInterface, stop_flag, buffer: List
    ):
        while not self.local_stop_flags[tid]:
            batch = queue.get_batch()
            if not batch:
                time.sleep(0.001)
                continue
            buffer.extend(batch)

        # read all remaining
        while queue.get_num_buffered_items() > 0:
            buffer.extend(queue.get_batch())

    def _run(self):
        self._load_model()

        self.inputs: List[BackendInputInterface] = []
        for input_interface_args in self.input_interface_args_list:
            input = BackendInputInterfaceFactory.create_input_interface(
                **input_interface_args
            )
            self.inputs.append(input)

        self.output = BackendOutputInterfaceFactory.create_input_interface(
            **self.output_interface_args
        )

        if self.component_model.model_desc.transforming_name.lower() not in [
            None,
            "",
            "none",
        ]:
            self._load_transforming_fn()

        tt0 = time.time()
        normal_batching_infer_count = 0
        time_to_sleep = 0

        import threading

        self.local_stop_flags = [False for _ in range(len(self.stop_flags))]

        queue_buffer = []
        read_data_threads: List[threading.Thread] = []
        for tid in range(len(self.stop_flags)):
            read_data_thr = threading.Thread(
                target=self.read_queue_thr,
                args=(
                    tid,
                    self.inputs[tid],
                    self.stop_flags[tid],
                    queue_buffer,
                ),
            )
            read_data_thr.start()
            read_data_threads.append(read_data_thr)

        to_exit = False
        while True:
            if self.allow_infer_flag is not None:
                stop_flag_enabled = True
                for stop_flag in self.stop_flags:
                    if not stop_flag.value:
                        stop_flag_enabled = False
                        break
                if not stop_flag_enabled and not self.allow_infer_flag.value:
                    # if stop_flag was triggered, need to execute all batched requests and exit
                    # time.sleep(0.001)
                    print("pausing inference")
                    time.sleep(1)
                    continue

            # if not self.stop_flag.value:
            #     batches = self.input.get_batch()
            # else:
            #     batches = self.input.close_and_get_remains()
            #     to_exit = True

            all_stop_flags_set = True

            for stop_flag_idx, stop_flag in enumerate(self.stop_flags):
                if stop_flag.value:
                    self.local_stop_flags[stop_flag_idx] = True
                    read_data_threads[stop_flag_idx].join()
                else:
                    all_stop_flags_set = False
                    break

            if all_stop_flags_set:
                to_exit = True

            # for batch_data in batches:
            has_data = False
            for _ in range(len(queue_buffer)):
                batch_data = queue_buffer.pop(0)
                batch, batch_metadata = batch_data

                for metadata in batch_metadata:
                    self.request_entering(metadata["extra"])

                # final results will be stored in output_dict
                # output_dict = {}
                output_list = []

                if self.batching:
                    if self.transform_fn is None:
                        self._process_normal_batchable(
                            batch, batch_metadata, output_list
                        )
                    else:
                        # need to run transformer
                        self._process_unbatchable(batch, batch_metadata, output_list)
                else:
                    self._process_unbatchable(batch, batch_metadata, output_list)

                has_data = True

                # NOTE: some multi-stages models need original/intermediate inputs for latter steps, forward if needed
                # for key in batch_metadata[0].get(NXS_BACKEND_CONFIG.FORWARD_INPUTS, []):
                #    output_dict[key] = batch[key]

                for metadata in batch_metadata:
                    self.request_exiting(metadata["extra"])

                normal_batching_infer_count += len(output_list)

                for item in output_list:
                    self.output.put_batch(self.next_topic_name, [item])

            if time.time() - tt0 > 5:
                if normal_batching_infer_count > 0:
                    fps = normal_batching_infer_count / (time.time() - tt0)
                    # print(
                    #     "compute", "fps", fps, "time_to_sleep", time_to_sleep
                    # )
                    self._log(f"FPS: {fps} - NumberOfSleepTimes: {time_to_sleep}")

                normal_batching_infer_count = 0
                time_to_sleep = 0
                tt0 = time.time()

            if to_exit:
                break

            if not has_data:
                time_to_sleep += 1
                time.sleep(0.001)

        self.next_process_stop_flag.value = True

        self._log("Exiting...")

    def _process_normal_batchable(self, batch, batch_metadata, output_buffer: List):
        feed_dict = {}
        for tensor_name in self.input_tensor_names:
            feed_dict[tensor_name] = np.array(batch[tensor_name])

        outputs = self._infer(feed_dict, self.output_tensor_names)

        for idx in range(len(outputs[0])):
            single_output_dict = {}

            for output_tensor_name, output in zip(self.output_tensor_names, outputs):
                single_output_dict[output_tensor_name] = output[idx]

            # NOTE: FORWARD_INPUTS should be done in preprocessing step and stored in metadata
            # metadata = batch_metadata[idx]
            # for key in metadata.get(NXS_BACKEND_CONFIG.FORWARD_INPUTS, []):
            #     single_output_dict[key] = batch[key][idx]

            output_buffer.append((single_output_dict, batch_metadata[idx]))

    def _process_unbatchable(self, batch, batch_metadata, output_buffer: List):
        if batch_metadata[0].get(BACKEND_INTERNAL_CONFIG.TASK_SKIP_COMPUTE, False):
            results = batch_metadata[0][
                BACKEND_INTERNAL_CONFIG.TASK_SKIP_COMPUTE_RESULT
            ]

            for key in batch_metadata[0].get(NXS_BACKEND_CONFIG.FORWARD_INPUTS, []):
                results[key][0] = batch[key][0]

            output_buffer.append((results, batch_metadata[0]))
        else:
            if self.transform_fn is None:
                feed_dict = {}
                for tensor_name in self.input_tensor_names:
                    feed_dict[tensor_name] = np.array(batch[tensor_name])

                outputs = self._infer(feed_dict, self.output_tensor_names)

                for idx in range(len(outputs[0])):
                    single_output_dict = {}

                    for output_tensor_name, output in zip(
                        self.output_tensor_names, outputs
                    ):
                        single_output_dict[output_tensor_name] = output[idx]

                    # NOTE: FORWARD_INPUTS should be done in preprocessing step and stored in metadata
                    # metadata = batch_metadata[idx]
                    # for key in metadata.get(
                    #     NXS_BACKEND_CONFIG.FORWARD_INPUTS, []
                    # ):
                    #     single_output_dict[key] = batch[key][idx]

                    output_buffer.append((single_output_dict, batch_metadata[idx]))
            else:
                # need to process each request independently
                metadata = batch_metadata[0]

                # transform batch to single item
                for key in batch:
                    batch[key] = batch[key][0]

                transformer_args = copy.deepcopy(self.transform_extra_params)

                user_metadata: NxsInferRequestMetadata = metadata[
                    NXS_BACKEND_CONFIG.USER_METADATA
                ]
                user_defined_transform_params = {}
                try:
                    user_defined_transform_params = json.loads(
                        user_metadata.extra_transform_params
                    )
                except:
                    self._log("Failed to read user defined preproc_params")

                for key in user_defined_transform_params:
                    transformer_args[key] = user_defined_transform_params[key]

                # transform a single item into a dict of list of inputs
                transformed_batch_list = self.transform_fn(
                    batch,
                    transformer_args,
                    self.component_model,
                    metadata,
                )

                all_outputs = {}
                for new_batch_dict in transformed_batch_list:
                    # run inference
                    outputs = self._infer(new_batch_dict, self.output_tensor_names)

                    for output_tensor_name, output in zip(
                        self.output_tensor_names, outputs
                    ):
                        if output_tensor_name not in all_outputs:
                            all_outputs[output_tensor_name] = []
                        all_outputs[output_tensor_name].extend(output)

                # NOTE: FORWARD_INPUTS should be done in preprocessing step and stored in metadata
                # for key in metadata.get(
                #     NXS_BACKEND_CONFIG.FORWARD_INPUTS, []
                # ):
                #     all_outputs[key] = batch[key][0]

                output_buffer.append((all_outputs, metadata))

    def _load_transforming_fn(self):
        import importlib

        module_name = "nxs_transform_fn"
        spec = importlib.util.spec_from_file_location(
            module_name, self.transforming_fn_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.transform_fn = module.transform

        # load extra params if available
        try:
            transform_extra_params = json.loads(
                self.component_model.model_desc.extra_transforming_metadata
            )
            for key in transform_extra_params:
                self.transform_extra_params = transform_extra_params[key]
        except:
            pass

        self._log(f"Loaded transforming_fn from {self.transforming_fn_path}")

    def stop(self):
        self.p.join()

    @abstractmethod
    def _load_model(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _infer(self, feed_dict: Dict, output_tensor_names: List[str]) -> List:
        raise NotImplementedError

    @abstractmethod
    def request_entering(self, extra_metadata: Dict):
        raise NotImplementedError

    @abstractmethod
    def request_exiting(self, extra_metadata: Dict):
        raise NotImplementedError
