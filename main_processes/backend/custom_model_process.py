import copy
import json
import logging
import os
import pickle
import time
from abc import ABC, abstractmethod
from re import L
from typing import Dict, List

import cv2
import numpy as np
from configs import BACKEND_INTERNAL_CONFIG, NXS_BACKEND_CONFIG, NXS_CONFIG
from nxs_libs.interface.backend.input import BackendInputInterfaceFactory
from nxs_libs.interface.backend.output import BackendOutputInterfaceFactory
from nxs_libs.interface.model import NxsBaseCustomModel
from nxs_types.infer import NxsInferInputType, NxsInferRequest, NxsInferRequestMetadata
from nxs_types.infer_result import NxsInferStatus
from nxs_types.model import ModelInput, NxsModel
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan
from nxs_utils.logging import NxsLogLevel, setup_logger, write_log


class BackendCustomModelProcess:
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        model_def_path: str,
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
        self.model_def_path = model_def_path

        self.p = None
        # self.init_fn = None
        # self.infer_fn = None
        self.model_instance = None
        self.preproc_extra_params = {}
        self.postproc_extra_params = {}

        self.log_prefix = "{}_E2E".format(component_model.model_uuid)
        self.next_topic_name = "{}_OUTPUT".format(component_model.model_uuid)

        setup_logger()

    def _log(self, message, log_level=logging.INFO):
        logging.log(log_level, f"{self.log_prefix} - {message}")

    def run(self):
        from multiprocessing import Process

        self.p = Process(target=self._run, args=())
        self.p.start()

    def _run(self):
        try:
            self.model_instance: NxsBaseCustomModel = self._create_model_instance()
            self.model_instance.init(self.component_model)
        except Exception as e:
            self.model_instance = None
            print(e)

        cross_requests_batching = self.component_model.cross_requests_batching
        max_batch_size = self.component_model_plan.batch_size
        min_batch_size = 9999999999999
        supported_batch_sizes: List[int] = []
        for profile_unit in self.component_model.profile:
            if profile_unit.batch_size > max_batch_size:
                continue
            if min_batch_size > profile_unit.batch_size:
                min_batch_size = profile_unit.batch_size
            supported_batch_sizes.append(profile_unit.batch_size)
        supported_batch_sizes.sort(reverse=True)
        supported_batch_sizes = np.array(supported_batch_sizes, dtype=np.int32)

        self.input = BackendInputInterfaceFactory.create_input_interface(
            **self.input_interface_args
        )
        self.output = BackendOutputInterfaceFactory.create_input_interface(
            **self.output_interface_args
        )

        to_exit = False
        tt0 = time.time()

        requests_count = 0
        errors_count = 0
        current_batch = []
        current_metadata_batch = []
        current_preproc_params_batch = []
        current_postproc_params_batch = []

        # initialize the model
        # self.model_dict: Dict = self.init_fn(self.component_model)

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

                metadata = {"extra": {}}
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

                metadata[BACKEND_INTERNAL_CONFIG.TASK_STATUS] = data.status
                if (
                    metadata[BACKEND_INTERNAL_CONFIG.TASK_STATUS]
                    == NxsInferStatus.PENDING
                ):
                    metadata[
                        BACKEND_INTERNAL_CONFIG.TASK_STATUS
                    ] = NxsInferStatus.PROCESSING

                inputs_dict = {}
                has_error = False
                for request_input in data.inputs:
                    try:
                        if request_input.type == NxsInferInputType.ENCODED_IMAGE:
                            inputs_dict[request_input.name] = request_input.data
                        elif request_input.type == NxsInferInputType.PICKLED_DATA:
                            inputs_dict[request_input.name] = pickle.loads(
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

                if has_error:
                    # send to output
                    self.output.put_batch("error", [(None, metadata)])
                    requests_count += 1
                    errors_count += 1
                    continue

                preproc_params = copy.copy(self.preproc_extra_params)

                try:
                    user_defined_preproc_params = json.loads(data.extra_preproc_params)
                    for key in user_defined_preproc_params:
                        preproc_params[key] = user_defined_preproc_params[key]
                except:
                    self._log("Failed to read user defined preproc_params")

                postproc_params = copy.copy(self.postproc_extra_params)
                try:
                    user_defined_postproc_params = json.loads(
                        user_metadata.extra_postproc_params
                    )
                    for key in user_defined_postproc_params:
                        postproc_params[key] = user_defined_postproc_params[key]
                except:
                    self._log("Failed to read user defined preproc_params")

                current_batch.append(inputs_dict)
                current_metadata_batch.append(metadata)
                current_preproc_params_batch.append(preproc_params)
                current_postproc_params_batch.append(postproc_params)

                requests_count += 1

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
                preprocs = []
                postprocs = []

                for _ in range(chosen_bs):
                    batches.append(current_batch.pop(0))
                    metadatas.append(current_metadata_batch.pop(0))
                    preprocs.append(current_preproc_params_batch.pop(0))
                    postprocs.append(current_postproc_params_batch.pop(0))

                try:
                    # infer_outputs = self.infer_fn(
                    #     self.model_dict, batches, preprocs, postprocs, metadatas
                    # )
                    infer_outputs = self.model_instance.infer(
                        batches, preprocs, postprocs, metadatas
                    )
                except Exception as e:
                    infer_outputs = []
                    for i in range(len(batches)):
                        infer_outputs.append({})
                        metadata = metadatas[i]
                        metadata[
                            BACKEND_INTERNAL_CONFIG.TASK_STATUS
                        ] = NxsInferStatus.FAILED
                        error_msgs = metadata.get(
                            BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                        )
                        error_msgs.append(
                            f"{self.component_model.model_uuid}: Failed to run batch: {str(e)}"
                        )
                        metadata[BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS] = error_msgs

                for infer_output, metadata in zip(infer_outputs, metadatas):
                    self.output.put_batch(
                        self.next_topic_name, [(infer_output, metadata)]
                    )

            if time.time() - tt0 > 5:
                if requests_count > 0:
                    fps = requests_count / (time.time() - tt0)
                    self._log(f"FPS: {fps}")

                errors_count = 0
                requests_count = 0
                tt0 = time.time()

            if to_exit:
                break

            if not requests:
                time.sleep(0.001)

        # trigger next process to stop
        self.next_process_stop_flag.value = True

        if self.model_instance is not None:
            self.model_instance.cleanup()

        self._log("Exiting...")

    def request_entering(self, extra_metadata: Dict):
        if self.component_model.model_uuid not in extra_metadata:
            extra_metadata[self.component_model.model_uuid] = {}

        if "input_t0" not in extra_metadata:
            extra_metadata["input_t0"] = time.time()

        extra_metadata[self.component_model.model_uuid] = {}
        extra_metadata[self.component_model.model_uuid]["input_t0"] = time.time()

        if "preprocessing_t0" not in extra_metadata:
            extra_metadata["preprocessing_t0"] = time.time()

        extra_metadata[self.component_model.model_uuid] = {}
        extra_metadata[self.component_model.model_uuid][
            "preprocessing_t0"
        ] = time.time()

    def request_exiting(self, extra_metadata: Dict):
        input_t0 = extra_metadata[self.component_model.model_uuid].pop("input_t0")
        extra_metadata[self.component_model.model_uuid]["input_lat"] = (
            time.time() - input_t0
        )

    def _create_model_instance(self, **kwargs) -> NxsBaseCustomModel:
        import importlib
        import inspect

        module_name = "nxs_custom_model"
        module_path = "nxs_custom_model.py"
        class_name = "NxsCustomModel"
        spec = importlib.util.spec_from_file_location(
            module_name, os.path.join(self.model_def_path, module_path)
        )
        _module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_module)

        model_inst = None
        clsmembers = inspect.getmembers(_module, inspect.isclass)
        for clsmember in clsmembers:
            name, cls_def = clsmember
            if name == class_name:
                model_inst = cls_def(**kwargs)

        assert model_inst is not None

        return model_inst

    def stop(self):
        self.stop_flag.value = True
        self.p.join()

    def terminate(self):
        try:
            self.p.terminate()
        except:
            pass
