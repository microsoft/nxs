import logging
import os
import pickle
import time
import json
import cv2
import copy
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List
from configs import BACKEND_INTERNAL_CONFIG, NXS_BACKEND_CONFIG, NXS_CONFIG
from nxs_libs.interface.backend.input import (
    BackendInputInterfaceFactory,
)
from nxs_libs.interface.backend.output import (
    BackendOutputInterfaceFactory,
)
from nxs_types.infer import (
    NxsInferInputType,
    NxsInferRequest,
    NxsInferRequestMetadata,
)
from nxs_types.infer_result import NxsInferStatus
from nxs_types.model import (
    ModelInput,
    NxsModel,
)
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan
from nxs_utils.logging import NxsLogLevel, setup_logger, write_log


class BackendPreprocessingProcess:
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        pid: int,
        preprocessing_fn_path: str,
        input_interface_args: Dict,
        output_interface_args: Dict,
        error_shortcut_interface_args: Dict,
        stop_flag,
        next_process_stop_flag,
        extra_params: Dict = {},
    ) -> None:
        self.component_model = component_model
        self.component_model_plan = component_model_plan
        self.input_interface_args = input_interface_args
        self.output_interface_args = output_interface_args
        self.error_shortcut_interface_args = error_shortcut_interface_args
        self.stop_flag = stop_flag
        self.next_process_stop_flag = next_process_stop_flag
        self.extra_params = extra_params
        self.preprocessing_fn_path = preprocessing_fn_path
        self.pid = pid

        self.p = None
        self.preproc_fn = None
        self.preproc_extra_params = {}

        try:
            self.preproc_extra_params = json.loads(
                self.component_model.model_desc.extra_preprocessing_metadata
            )
        except:
            pass

        self.log_prefix = "{}_PREPROCESSOR_{}".format(component_model.model_uuid, pid)
        # self.log_level = os.environ.get(NXS_CONFIG.LOG_LEVEL, NxsLogLevel.INFO)

        self.next_topic_name = "{}_BATCHER".format(component_model.model_uuid)

        setup_logger()

    # def _log(self, message):
    #     write_log(self.log_prefix, message, self.log_level)

    def _log(self, message, log_level=logging.INFO):
        logging.log(log_level, f"{self.log_prefix} - {message}")

    def run(self):
        from multiprocessing import Process

        self.p = Process(target=self._run, args=())
        self.p.start()

    def _run(self):
        # print(f"Preprocessor {self.pid} is created...")
        # load pre-processing fn
        self._load_preprocessing_fn()

        max_batch_size = self.component_model_plan.batch_size
        cross_requests_batching = self.component_model.cross_requests_batching

        supported_batch_sizes: List[int] = []
        for profile_unit in self.component_model.profile:
            if profile_unit.batch_size > max_batch_size:
                continue
            supported_batch_sizes.append(profile_unit.batch_size)
        supported_batch_sizes.sort(reverse=True)
        supported_batch_sizes = np.array(supported_batch_sizes, dtype=np.int32)

        self.input = BackendInputInterfaceFactory.create_input_interface(
            **self.input_interface_args
        )
        self.output = BackendOutputInterfaceFactory.create_input_interface(
            **self.output_interface_args
        )
        self.error_output = BackendOutputInterfaceFactory.create_input_interface(
            **self.error_shortcut_interface_args
        )

        # input_name -> shape
        self.input_name_2_input_desc: Dict[str, ModelInput] = {}
        for input in self.component_model.model_desc.inputs:
            self.input_name_2_input_desc[input.name] = input

        to_exit = False
        tt0 = time.time()

        requests_count = 0

        current_batch = []
        current_metadata_batch = []

        while True:
            requests = []
            if not self.stop_flag.value:
                requests = self.input.get_batch(
                    external_data={"max_items": max_batch_size}
                )
            else:
                requests = self.input.close_and_get_remains()
                to_exit = True

            for request in requests:
                data: NxsInferRequest = request

                carry_over_extras = {}
                if data.carry_over_extras is not None:
                    try:
                        carry_over_extras = pickle.loads(data.carry_over_extras)
                    except:
                        carry_over_extras = {}

                metadata = {"extra": carry_over_extras}
                # metadata["extra"][self.component_model.model_uuid] = {}
                # if "preprocessing_t0" not in metadata["extra"]:
                #     metadata["extra"]["preprocessing_t0"] = time.time()

                self.request_entering(metadata["extra"])

                user_metadata = NxsInferRequestMetadata(
                    task_uuid=data.task_uuid,
                    session_uuid=data.session_uuid,
                    extra_preproc_params="{}",
                    extra_transforming_metadata=data.extra_transform_params,
                    extra_postproc_params=data.extra_postproc_params,
                    exec_pipelines=data.exec_pipelines,
                )
                metadata[NXS_BACKEND_CONFIG.USER_METADATA] = user_metadata

                decoded_inputs_dict: Dict = {}

                metadata[BACKEND_INTERNAL_CONFIG.TASK_STATUS] = data.status
                if (
                    metadata[BACKEND_INTERNAL_CONFIG.TASK_STATUS]
                    == NxsInferStatus.PENDING
                ):
                    metadata[
                        BACKEND_INTERNAL_CONFIG.TASK_STATUS
                    ] = NxsInferStatus.PROCESSING

                # print(carry_over_extras)

                if data.status == NxsInferStatus.FAILED:
                    metadata[
                        BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS
                    ] = carry_over_extras.get(
                        BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                    )
                    self.error_output.put_batch("error", [(None, metadata)])
                    continue

                has_error = False
                for request_input in data.inputs:
                    try:
                        if request_input.type == NxsInferInputType.ENCODED_IMAGE:
                            nparr = np.frombuffer(request_input.data, np.uint8)
                            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            assert img is not None
                            decoded_inputs_dict[request_input.name] = img
                        elif request_input.type == NxsInferInputType.PICKLED_DATA:
                            decoded_inputs_dict[request_input.name] = pickle.loads(
                                request_input.data
                            )
                    except Exception as ex:
                        metadata[
                            BACKEND_INTERNAL_CONFIG.TASK_STATUS
                        ] = NxsInferStatus.FAILED
                        error_msgs = metadata.get(
                            BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                        )
                        error_msgs.append(
                            f"{self.component_model.model_uuid}: Failed to decode input '{request_input.name}'"
                        )
                        metadata[BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS] = error_msgs
                        has_error = True

                if has_error:
                    # send to output
                    self.error_output.put_batch("error", [(None, metadata)])
                    continue

                # for input_name in self.input_name_2_input_desc.keys():
                #     if input_name not in decoded_inputs_dict:
                #         shape = copy.deepcopy(
                #             self.input_name_2_input_desc[input_name].shape
                #         )
                #         dtype = self.input_name_2_input_desc[input_name].dtype

                #         for idx in range(len(shape)):
                #             if shape[idx] <= 0:
                #                 shape[idx] = 1

                #         if dtype == TensorType.FLOAT32:
                #             decoded_inputs_dict[input_name] = np.zeros(
                #                 shape=shape
                #             ).astype(np.float32)
                #         elif dtype == TensorType.UINT8:
                #             decoded_inputs_dict[input_name] = np.zeros(
                #                 shape=shape
                #             ).astype(np.uint8)
                #         elif dtype == TensorType.INT32:
                #             decoded_inputs_dict[input_name] = np.zeros(
                #                 shape=shape
                #             ).astype(np.int32)
                #         elif dtype == TensorType.INT64:
                #             decoded_inputs_dict[input_name] = np.zeros(
                #                 shape=shape
                #             ).astype(np.int64)

                preproc_params = copy.copy(self.preproc_extra_params)
                user_defined_preproc_params = {}

                try:
                    user_defined_preproc_params = json.loads(data.extra_preproc_params)
                except:
                    self._log("Failed to read user defined preproc_params")

                for key in user_defined_preproc_params:
                    preproc_params[key] = user_defined_preproc_params[key]

                if not has_error:
                    try:
                        preprocessed_data, skip_compute_step = self.preproc_fn(
                            decoded_inputs_dict,
                            preproc_params,
                            self.component_model,
                            metadata,
                        )
                    except Exception as ex:
                        print(ex)
                        has_error = True
                        metadata[
                            BACKEND_INTERNAL_CONFIG.TASK_STATUS
                        ] = NxsInferStatus.FAILED
                        error_msgs = metadata.get(
                            BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                        )
                        error_msgs.append(
                            f"{self.component_model.model_uuid}: Preproc failed with exception '{str(ex)}'"
                        )
                        metadata[BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS] = error_msgs
                else:
                    preprocessed_data = decoded_inputs_dict
                    skip_compute_step = False

                # self._log(metadata)

                if has_error:
                    # send to output
                    self.error_output.put_batch("error", [(None, metadata)])
                    continue

                metadata[BACKEND_INTERNAL_CONFIG.TASK_SKIP_COMPUTE] = skip_compute_step
                if skip_compute_step:
                    # some multi-stages models do not need to trigger compute step, forward preprocessed_data directly to output
                    # NOTE: preprocessed_data must have all outputs in this case
                    metadata[
                        BACKEND_INTERNAL_CONFIG.TASK_SKIP_COMPUTE_RESULT
                    ] = preprocessed_data

                user_metadata.extra_preproc_params = json.dumps(preproc_params)

                current_batch.append(preprocessed_data)
                current_metadata_batch.append(metadata)

                requests_count += 1

            # send-out batches, no need to wait
            while len(current_batch) > 0:
                if not cross_requests_batching:
                    chosen_bs = 1
                elif len(current_batch) >= max_batch_size:
                    chosen_bs = max_batch_size
                else:
                    tmp = supported_batch_sizes <= len(current_batch)
                    tmp = tmp.astype(np.int32)
                    tmp = supported_batch_sizes * tmp
                    chosen_bs = np.max(tmp)

                batches = []
                metadatas = []

                for _ in range(chosen_bs):
                    batches.append(current_batch.pop(0))
                    metadatas.append(current_metadata_batch.pop(0))

                transformed_batch = {}
                for item in batches:
                    for tensor_name in item:
                        if not tensor_name in transformed_batch.keys():
                            transformed_batch[tensor_name] = []
                        transformed_batch[tensor_name].extend(item[tensor_name])

                for metadata in metadatas:
                    self.request_exiting(metadata["extra"])

                self.output.put_batch(
                    self.next_topic_name,
                    [(transformed_batch, metadatas)],
                )

            if time.time() - tt0 > 5:
                if requests_count > 0:
                    fps = requests_count / (time.time() - tt0)
                    # print(f"preprocessor_{self.pid}", "fps", fps)
                    self._log(f"FPS: {fps}")
                requests_count = 0
                tt0 = time.time()

            if to_exit:
                break

            if not requests:
                time.sleep(0.01)

        # trigger next process to stop
        self.next_process_stop_flag.value = True

        self._log("Exiting...")

    def _load_preprocessing_fn(self):
        import importlib

        module_name = "nxs_preproc_fn"
        spec = importlib.util.spec_from_file_location(
            module_name, self.preprocessing_fn_path
        )
        preproc_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preproc_module)

        self.preproc_fn = preproc_module.preprocessing

        # load extra params if available
        try:
            self.preproc_extra_params = json.loads(
                self.component_model.model_desc.extra_preprocessing_metadata
            )
        except:
            pass

        self._log(f"Loaded preprocessing fn from {self.preprocessing_fn_path}")

    def stop(self):
        self.stop_flag.value = True
        self.p.join()

    def request_entering(self, extra_metadata: Dict):
        if "preprocessing_t0" not in extra_metadata:
            extra_metadata["preprocessing_t0"] = time.time()

        extra_metadata[self.component_model.model_uuid] = {}
        extra_metadata[self.component_model.model_uuid][
            "preprocessing_t0"
        ] = time.time()

    def request_exiting(self, extra_metadata: Dict):
        preprocessing_t0 = extra_metadata[self.component_model.model_uuid].pop(
            "preprocessing_t0"
        )
        extra_metadata[self.component_model.model_uuid]["preprocessing_lat"] = (
            time.time() - preprocessing_t0
        )
