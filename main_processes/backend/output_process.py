import copy
import json
import logging
import os
import pickle
import time
from abc import ABC, abstractmethod
from typing import Dict, List

import cv2
import numpy as np
from configs import BACKEND_INTERNAL_CONFIG, NXS_BACKEND_CONFIG, NXS_CONFIG
from nxs_libs.interface.backend.input import BackendInputInterfaceFactory
from nxs_libs.interface.backend.output import BackendOutputInterfaceFactory
from nxs_types.infer import (
    NxsInferInput,
    NxsInferInputType,
    NxsInferRequest,
    NxsInferRequestMetadata,
)
from nxs_types.infer_result import (
    NxsInferClassificationResult,
    NxsInferDetectorResult,
    NxsInferEmbeddingResult,
    NxsInferOcrResult,
    NxsInferResult,
    NxsInferResultType,
    NxsInferResultWithMetadata,
    NxsInferStatus,
)
from nxs_types.model import NxsModel
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan
from nxs_utils.logging import NxsLogLevel, setup_logger, write_log


class LogMetadata:
    def __init__(self, req_metadata: NxsInferRequestMetadata, extra: Dict = {}) -> None:
        self.metadata = req_metadata
        self.extra = extra


class BackendOutputProcess(ABC):
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        pid: int,
        postprocessing_fn_path: str,
        input_interface_args: Dict,
        output_interface_args: Dict,
        stop_flag,
        next_process_stop_flag,
        dispatcher_update_shared_list=None,
        extra_params: Dict = {},
    ) -> None:

        self.component_model = component_model
        self.component_model_plan = component_model_plan
        self.input_interface_args = input_interface_args
        self.output_interface_args = output_interface_args
        self.stop_flag = stop_flag
        self.next_process_stop_flag = next_process_stop_flag
        self.extra_params = extra_params
        self.postprocessing_fn_path = postprocessing_fn_path
        self.dispatcher_update_shared_list = dispatcher_update_shared_list
        self.pid = pid

        self.p = None
        self.postproc_fn = None
        self.postproc_extra_params = {}

        self.metadata_list: List[LogMetadata] = []
        self.metadata_processing_period_secs = 1

        try:
            self.postproc_extra_params = json.loads(
                self.component_model.model_desc.extra_postprocessing_metadata
            )
        except:
            pass

        self.log_prefix = "{}_OUTPUT_{}".format(component_model.model_uuid, pid)
        # self.log_level = os.environ.get(NXS_CONFIG.LOG_LEVEL, NxsLogLevel.INFO)

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

        # load post-processing fn
        if not self.component_model.is_arbitrary_model:
            self._load_postprocessing_fn()

        self.input = BackendInputInterfaceFactory.create_input_interface(
            **self.input_interface_args
        )
        self.output = BackendOutputInterfaceFactory.create_input_interface(
            **self.output_interface_args
        )

        self.metadata_processing_t0 = time.time()

        requests_count = 0
        tt0 = time.time()
        to_exit = False
        while True:
            incoming_batches = []

            if self.stop_flag.value:
                incoming_batches = self.input.close_and_get_remains()
                to_exit = True
            else:
                incoming_batches = self.input.get_batch()

            for batch in incoming_batches:
                data, metadata = batch

                if (
                    metadata.get(
                        BACKEND_INTERNAL_CONFIG.TASK_STATUS,
                        NxsInferStatus.PROCESSING,
                    )
                    == NxsInferStatus.FAILED
                ):
                    user_metadata: NxsInferRequestMetadata = metadata[
                        NXS_BACKEND_CONFIG.USER_METADATA
                    ]
                    extras = metadata.get("extra", {})
                    extras[BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS] = metadata.get(
                        BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                    )
                    user_metadata.carry_over_extras = pickle.dumps(extras)

                    # do not need to do anything, forward to next
                    if self.next_process_stop_flag is not None:
                        # create new inference request
                        new_request = NxsInferRequest(
                            **(user_metadata.dict()),
                            inputs=[],
                            status=NxsInferStatus.FAILED,
                        )

                        self.output.put_batch("error", [new_request])
                    else:
                        result = NxsInferResultWithMetadata(
                            type=NxsInferResultType.CUSTOM,
                            task_uuid=user_metadata.task_uuid,
                            status=NxsInferStatus.FAILED,
                            error_msgs=metadata.get(
                                BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                            ),
                            custom="{}",
                        )
                        next_topic = user_metadata.exec_pipelines[-1]
                        self.output.put_batch(next_topic, [result])

                    continue

                self.request_entering(metadata["extra"])

                postproc_params = copy.copy(self.postproc_extra_params)
                user_defined_postproc_params = {}

                user_metadata: NxsInferRequestMetadata = metadata[
                    NXS_BACKEND_CONFIG.USER_METADATA
                ]
                try:
                    user_defined_postproc_params = json.loads(
                        user_metadata.extra_postproc_params
                    )
                except:
                    self._log("Failed to read user defined preproc_params")

                for key in user_defined_postproc_params:
                    postproc_params[key] = user_defined_postproc_params[key]

                result = {}
                try:
                    if self.postproc_fn is not None:
                        result = self.postproc_fn(
                            data, postproc_params, self.component_model, metadata
                        )
                    else:
                        if data is not None:
                            result = data
                except Exception as ex:
                    metadata[
                        BACKEND_INTERNAL_CONFIG.TASK_STATUS
                    ] = NxsInferStatus.FAILED
                    error_msgs = metadata.get(
                        BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                    )
                    error_msgs.append(
                        f"{self.component_model.model_uuid}: postproc failed with exception '{str(ex)}'"
                    )
                    metadata[BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS] = error_msgs

                self.request_exiting(metadata["extra"])

                # print(result)
                # print(metadata)

                if self.next_process_stop_flag is not None:
                    # still have latter stage to process
                    # FIXME
                    next_topic = "tmp_next"

                    # add extra into metadata
                    carry_over_extras = {}
                    if user_metadata.carry_over_extras is not None:
                        try:
                            carry_over_extras = pickle.loads(
                                user_metadata.carry_over_extras
                            )
                        except:
                            carry_over_extras = {}

                    for key in metadata["extra"]:
                        carry_over_extras[key] = metadata["extra"][key]

                    carry_over_extras[
                        BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS
                    ] = metadata.get(BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, [])

                    user_metadata.carry_over_extras = pickle.dumps(carry_over_extras)

                    # create new inference request
                    new_request = NxsInferRequest(
                        **(user_metadata.dict()),
                        inputs=[
                            NxsInferInput(
                                name=key,
                                type=NxsInferInputType.PICKLED_DATA,
                                data=pickle.dumps(result[key]),
                            )
                            for key in result
                        ],
                        status=metadata[BACKEND_INTERNAL_CONFIG.TASK_STATUS],
                    )

                    self.output.put_batch(next_topic, [new_request])
                else:
                    # send data outside
                    status = metadata.get(
                        BACKEND_INTERNAL_CONFIG.TASK_STATUS,
                        NxsInferStatus.PROCESSING,
                    )
                    next_topic = user_metadata.exec_pipelines.pop(0)

                    if (
                        status != NxsInferStatus.FAILED
                        and len(user_metadata.exec_pipelines) > 0
                    ):
                        # create new inference request
                        new_request = NxsInferRequest(
                            **(user_metadata.dict()),
                            inputs=[
                                NxsInferInput(
                                    name=key,
                                    type=NxsInferInputType.PICKLED_DATA,
                                    data=pickle.dumps(result[key]),
                                )
                                for key in result
                            ],
                        )

                        # FIXME: How to add session_uuid to this???
                        next_topic = f"{next_topic}_{new_request.session_uuid}"
                        self.output.put_batch(next_topic, [new_request])
                    else:
                        try:
                            if isinstance(result, Dict):
                                if "detections" in result:
                                    result = NxsInferResultWithMetadata(
                                        type=NxsInferResultType.DETECTION,
                                        task_uuid=user_metadata.task_uuid,
                                        status=status,
                                        error_msgs=metadata.get(
                                            BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS,
                                            [],
                                        ),
                                        detections=[
                                            NxsInferDetectorResult(**det)
                                            for det in result["detections"]
                                        ],
                                    )
                                elif "classification" in result:
                                    result = NxsInferResultWithMetadata(
                                        type=NxsInferResultType.CLASSIFICATION,
                                        task_uuid=user_metadata.task_uuid,
                                        status=status,
                                        error_msgs=metadata.get(
                                            BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS,
                                            [],
                                        ),
                                        classification=NxsInferClassificationResult(
                                            **result["classification"]
                                        ),
                                    )
                                elif "ocr" in result:
                                    result = NxsInferResultWithMetadata(
                                        type=NxsInferResultType.OCR,
                                        task_uuid=user_metadata.task_uuid,
                                        status=status,
                                        error_msgs=metadata.get(
                                            BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS,
                                            [],
                                        ),
                                        ocr=[
                                            NxsInferOcrResult(**r)
                                            for r in result["ocr"]
                                        ],
                                    )
                                elif "embedding" in result:
                                    result = NxsInferResultWithMetadata(
                                        type=NxsInferResultType.EMBEDDING,
                                        task_uuid=user_metadata.task_uuid,
                                        status=status,
                                        error_msgs=metadata.get(
                                            BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS,
                                            [],
                                        ),
                                        embedding=NxsInferEmbeddingResult(
                                            embedding=result["embedding"],
                                            length=len(result["embedding"]),
                                        ),
                                    )

                            if not isinstance(result, NxsInferResult):
                                result = NxsInferResultWithMetadata(
                                    type=NxsInferResultType.CUSTOM,
                                    task_uuid=user_metadata.task_uuid,
                                    status=status,
                                    error_msgs=metadata.get(
                                        BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS,
                                        [],
                                    ),
                                    custom=json.dumps(result),
                                )
                        except Exception as ex:
                            metadata[
                                BACKEND_INTERNAL_CONFIG.TASK_STATUS
                            ] = NxsInferStatus.FAILED
                            error_msgs = metadata.get(
                                BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS, []
                            )
                            error_msgs.append(
                                f"{self.component_model.model_uuid}: postproc output is not in correct format with exception '{str(ex)}'"
                            )
                            metadata[
                                BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS
                            ] = error_msgs

                            result = NxsInferResultWithMetadata(
                                type=NxsInferResultType.CUSTOM,
                                task_uuid=user_metadata.task_uuid,
                                status=status,
                                error_msgs=metadata.get(
                                    BACKEND_INTERNAL_CONFIG.TASK_ERROR_MSGS,
                                    [],
                                ),
                                custom=json.dumps({}),
                            )

                        output_metadata = self.generate_output_metadata(
                            metadata["extra"]
                        )
                        result.metadata = pickle.dumps(output_metadata)

                        if not user_metadata.exec_pipelines:
                            # we are sending out result
                            if status != NxsInferStatus.FAILED:
                                result.status = NxsInferStatus.COMPLETED

                            self.output.put_batch(next_topic, [result])
                        else:
                            # do not need to forward FAILED task to next computation step, jutst forward to last topic
                            next_topic = user_metadata.exec_pipelines[-1]
                            self.output.put_batch(next_topic, [result])

                self.metadata_list.append(LogMetadata(user_metadata, metadata["extra"]))

                requests_count += 1

            if (
                time.time() - self.metadata_processing_t0
                > self.metadata_processing_period_secs
            ):
                processed_data = self.process_metadata_list(
                    self.metadata_list,
                    time.time() - self.metadata_processing_t0,
                )
                self.metadata_list = []
                # forward this back to dispatcher
                if self.dispatcher_update_shared_list is not None:
                    # print(processed_data)
                    self.dispatcher_update_shared_list.append(processed_data)
                self.metadata_processing_t0 = time.time()

            if time.time() - tt0 > 5:
                if requests_count > 0:
                    fps = requests_count / (time.time() - tt0)
                    # print(f"output_{self.pid}", "fps", fps)
                    self._log(f"FPS: {fps}")
                requests_count = 0
                tt0 = time.time()

            if to_exit:
                break

            if not incoming_batches:
                time.sleep(0.0025)

        if self.next_process_stop_flag is not None:
            self.next_process_stop_flag.value = True

        self._log("Exiting...")

    def _load_postprocessing_fn(self):
        import importlib

        module_name = "nxs_postproc_fn"
        spec = importlib.util.spec_from_file_location(
            module_name, self.postprocessing_fn_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.postproc_fn = module.postprocessing

        # load extra params if available
        try:
            self.postproc_extra_params = json.loads(
                self.component_model.model_desc.extra_postprocessing_metadata
            )
        except:
            pass

        self._log(f"Loaded postprocessing fn from {self.postprocessing_fn_path}")

    def stop(self):
        self.p.join()

    @abstractmethod
    def request_entering(self, extra_metadata: Dict):
        raise NotImplementedError

    @abstractmethod
    def request_exiting(self, extra_metadata: Dict):
        raise NotImplementedError

    @abstractmethod
    def process_metadata_list(
        self, metadata_list: List[LogMetadata], duration_secs: float
    ) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def generate_output_metadata(self, extra_metadata: Dict) -> Dict:
        raise NotImplementedError


class BackendBasicOutputProcess(BackendOutputProcess):
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        pid: int,
        postprocessing_fn_path: str,
        input_interface_args: Dict,
        output_interface_args: Dict,
        stop_flag,
        next_process_stop_flag,
        dispatcher_update_shared_list=None,
        extra_params: Dict = {},
    ) -> None:
        super().__init__(
            args,
            component_model,
            component_model_plan,
            pid,
            postprocessing_fn_path,
            input_interface_args,
            output_interface_args,
            stop_flag,
            next_process_stop_flag,
            dispatcher_update_shared_list,
            extra_params=extra_params,
        )

    def request_entering(self, extra_metadata: Dict):
        extra_metadata[self.component_model.model_uuid][
            "postprocessing_t0"
        ] = time.time()

    def request_exiting(self, extra_metadata: Dict):
        cur_ts = time.time()
        postprocessing_t0 = extra_metadata[self.component_model.model_uuid].pop(
            "postprocessing_t0"
        )
        extra_metadata[self.component_model.model_uuid]["postprocessing_lat"] = (
            cur_ts - postprocessing_t0
        )
        extra_metadata["postprocessing_t1"] = cur_ts

    def process_metadata_list(
        self, metadata_list: List[LogMetadata], duration_secs: float
    ) -> Dict:
        total_requests = len(metadata_list)
        fps = total_requests / duration_secs

        request_lats = []
        for request_log in metadata_list:
            input_t0 = request_log.extra["input_t0"]
            postprocessing_t1 = request_log.extra["postprocessing_t1"]
            e2e_lat = postprocessing_t1 - input_t0
            request_lats.append(e2e_lat)

        latency = {
            "mean": 0,
            "min": 0,
            "max": 0,
        }

        if request_lats:
            latency = {
                "mean": np.mean(request_lats),
                "min": np.min(request_lats),
                "max": np.max(request_lats),
            }

        return {
            "output_pid": self.pid,
            "duration": duration_secs,
            "num_reqs": total_requests,
            "fps": fps,
            "latency": latency,
        }

    # def process_metadata_list(self, metadata_list: List[LogMetadata], duration_secs: float) -> Dict:
    #     session_fps_dict = {}
    #     session_avg_latency_dict = {}

    #     for data in metadata_list:
    #         session_uuid = data.metadata.session_uuid

    #         if session_uuid not in session_fps_dict:
    #             session_fps_dict[session_uuid] = 0
    #             session_avg_latency_dict[session_uuid] = []

    #         session_fps_dict[session_uuid] += 1
    #         latency = data.extra["postprocessing_t1"] - data.extra["preprocessing_t0"]
    #         session_fps_dict[session_uuid].append(latency)

    #     # convert num_reqs into fps
    #     for session_uuid in session_fps_dict:
    #         session_fps_dict[session_uuid] /= duration_secs
    #         session_avg_latency_dict[session_uuid] = np.mean(session_avg_latency_dict[session_uuid])

    #     return {
    #         "session_fps_dict" : session_fps_dict,
    #         "session_avg_latency_dict" : session_avg_latency_dict
    #     }

    def generate_output_metadata(self, extra_metadata: Dict) -> Dict:
        preprocessing_t0 = extra_metadata.pop("preprocessing_t0")
        extra_metadata["e2e_lat"] = time.time() - preprocessing_t0
        return extra_metadata
