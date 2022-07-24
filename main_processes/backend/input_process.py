import json
import logging
import pickle
import time
from abc import ABC, abstractmethod
from typing import Dict

import numpy as np
import requests
from configs import GLOBAL_QUEUE_NAMES, NXS_CONFIG
from nxs_libs.interface.backend.dispatcher import (
    BackendDispatcherFactory,
    BackendDispatcherType,
)
from nxs_libs.interface.backend.input import (
    BackendInputInterface,
    BackendInputInterfaceFactory,
)
from nxs_libs.interface.backend.output import BackendOutputInterfaceFactory
from nxs_libs.queue import NxsQueuePusherFactory, NxsQueueType
from nxs_types.infer import NxsInferRequest
from nxs_types.log import NxsBackendCmodelThroughputLog
from nxs_types.model import ModelInput, NxsModel
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan
from nxs_utils.logging import NxsLogLevel, setup_logger, write_log
from nxs_utils.nxs_helper import create_queue_pusher_from_args


class BackendInternalInputProcess(ABC):
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        preprocessing_fn_path: str,
        input_interface_args_dict: Dict[str, Dict],
        output_interface_args: Dict,
        dispatcher_args: Dict,
        stop_flag,
        next_process_stop_flag,
        dispatcher_update_shared_list=None,
        global_dispatcher_input_shared_list=None,
        global_dispatcher_output_shared_list=None,
        process_update_shared_list=None,
        extra_params: Dict = {},
    ) -> None:
        self.args = args
        self.component_model = component_model
        self.component_model_plan = component_model_plan
        self.input_interface_args_dict = input_interface_args_dict
        self.output_interface_args = output_interface_args
        self.dispatcher_args = dispatcher_args
        self.stop_flag = stop_flag
        self.next_process_stop_flag = next_process_stop_flag
        self.dispatcher_update_shared_list = dispatcher_update_shared_list
        self.global_dispatcher_input_shared_list = global_dispatcher_input_shared_list
        self.global_dispatcher_output_shared_list = global_dispatcher_output_shared_list
        self.process_update_shared_list = process_update_shared_list
        self.extra_params = extra_params
        self.preprocessing_fn_path = preprocessing_fn_path

        self.p = None
        self.preproc_fn = None
        self.preproc_extra_params = {}

        try:
            self.preproc_extra_params = json.loads(
                self.component_model.model_desc.extra_preprocessing_metadata
            )
        except:
            pass

        self.log_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)

        self.log_prefix = "{}_INPUT".format(component_model.model_uuid)
        # self.log_level = os.environ.get(NXS_CONFIG.LOG_LEVEL, NxsLogLevel.INFO)

        self.next_topic_name = "{}_PREPROCESSOR".format(component_model.model_uuid)

        setup_logger()

    def add_session(self, input_interface_args):
        session_uuid = input_interface_args["session_uuid"]

        if session_uuid in self.input_interface_args_dict:
            return

        self.process_update_shared_list.append(("ADD_SESSION", input_interface_args))
        self.input_interface_args_dict[session_uuid] = input_interface_args

    def remove_session_uuid(self, session_uuid):
        if session_uuid in self.input_interface_args_dict:
            self.process_update_shared_list.append(("REMOVE_SESSION", session_uuid))
            self.input_interface_args_dict.pop(session_uuid)

    # def _log(self, message):
    #     write_log(self.log_prefix, message, self.log_level)

    def _log(self, message, log_level=logging.INFO):
        logging.log(log_level, f"{self.log_prefix} - {message}")

    def run(self):
        from multiprocessing import Process

        self.p = Process(target=self._run, args=())
        self.p.start()

    def _run(self):
        self.input_dict: Dict[str, BackendInputInterface] = {}
        for session_uuid in self.input_interface_args_dict:
            self.input_dict[
                session_uuid
            ] = BackendInputInterfaceFactory.create_input_interface(
                **(self.input_interface_args_dict[session_uuid])
            )
            self.input_dict[session_uuid].set_num_partitions(1)

        self.output = BackendOutputInterfaceFactory.create_input_interface(
            **self.output_interface_args
        )

        # input_name -> shape
        self.input_name_2_input_desc: Dict[str, ModelInput] = {}
        for input in self.component_model.model_desc.inputs:
            self.input_name_2_input_desc[input.name] = input

        max_batch_size = self.component_model_plan.batch_size
        max_latency = 1  # in secs

        for profile_unit in self.component_model.profile:
            if profile_unit.batch_size == max_batch_size:
                max_latency = profile_unit.latency_e2e.max / 1000.0  # in secs
                break

        # set max buffer size for input interface
        max_queue_size = max(1, int(1.0 / max_latency * max_batch_size))

        for session_uuid in self.input_dict:
            self.input_dict[session_uuid].set_buf_size(max_queue_size)

        # setup dispatcher
        self.max_batch_size = max_batch_size
        self.max_latency = max_latency
        if self.dispatcher_args is not None:
            extra_params = self.dispatcher_args.get("extra_params", {})
            extra_params["input_process"] = self
            self.dispatcher_args["extra_params"] = extra_params
            self.dispatcher = BackendDispatcherFactory.create_dispatcher(
                **self.dispatcher_args
            )
        else:
            # use best-effort dispatcher
            dispatcher_args = {
                "type": BackendDispatcherType.BASIC,
                "extra_params": {"input_process": self},
            }
            self.dispatcher = BackendDispatcherFactory.create_dispatcher(
                **dispatcher_args
            )

        waiting_t0 = time.time()

        current_batch = []
        current_metadata_batch = []

        dispatcher_update_t0 = time.time()
        process_update_t0 = time.time()

        self.process_update_period_secs = 1
        self.dispatcher_update_period_secs = 1

        delaying_batches = []

        to_exit = False
        tt0 = time.time()
        requests_count = 0

        while True:
            cur_ts = time.time()

            incoming_batches = []
            incoming_batches.extend(delaying_batches)
            delaying_batches = []

            if cur_ts - process_update_t0 > self.process_update_period_secs:
                # use this to add/remove sessions or to control other stuff
                cmds = []
                for _ in range(len(self.process_update_shared_list)):
                    cmds.append(self.process_update_shared_list.pop(0))

                for cmd, cmd_args in cmds:
                    if cmd == "REMOVE_SESSION":
                        session_uuid = cmd_args

                        if session_uuid in self.input_dict:
                            incoming_batches.extend(
                                self.input_dict[session_uuid].close_and_get_remains()
                            )
                            self.input_dict.pop(session_uuid)
                            self._log("Removed session {}".format(session_uuid))
                    elif cmd == "ADD_SESSION":
                        input_args = cmd_args
                        session_uuid = input_args["session_uuid"]
                        if session_uuid not in self.input_dict:
                            self.input_dict[
                                session_uuid
                            ] = BackendInputInterfaceFactory.create_input_interface(
                                **input_args
                            )
                            self._log("Added session {}".format(session_uuid))
                    else:
                        print(cmd, cmd_args)

                process_update_t0 = time.time()

            if cur_ts - dispatcher_update_t0 > self.dispatcher_update_period_secs:
                # update states from global scheduler
                if self.global_dispatcher_input_shared_list is not None:
                    stats_list = []
                    for _ in range(len(self.global_dispatcher_input_shared_list)):
                        stats = self.global_dispatcher_input_shared_list.pop(0)
                        if isinstance(stats, Dict):
                            stats_list.append(stats)

                    for stats in stats_list:
                        self.dispatcher.update_stats_from_global_dispatcher(stats)

                # update states from output process
                if self.dispatcher_update_shared_list is not None:
                    stats_list = []
                    for _ in range(len(self.dispatcher_update_shared_list)):
                        stats = self.dispatcher_update_shared_list.pop(0)
                        if isinstance(stats, Dict):
                            stats_list.append(stats)

                    for stats in stats_list:
                        self.dispatcher.update_stats(stats)

                    # self.global_dispatcher_output_shared_list.append(
                    #     self.dispatcher.report_stats_to_global_dispatcher()
                    # )

                    summary_log = self.dispatcher.get_stats_summary()
                    tp_log = NxsBackendCmodelThroughputLog(
                        # backend_name=self.args.backend_name,
                        model_uuid=self.component_model.model_uuid,
                        total_reqs=summary_log["total_reqs"],
                        fps=summary_log["fps"],
                        latency_mean=summary_log["latency"]["mean"],
                        latency_min=summary_log["latency"]["min"],
                        latency_max=summary_log["latency"]["max"],
                    )

                    self.global_dispatcher_output_shared_list.append(tp_log)

                    # self.log_pusher.push(GLOBAL_QUEUE_NAMES.BACKEND_LOGS, tp_log)

                dispatcher_update_t0 = time.time()

            # check if there are too many requests queuing in preprocessing processes
            if (
                self.output.get_num_buffered_items(self.next_topic_name)
                >= max_queue_size
            ):
                time.sleep(max_latency / 2)

            new_requests = []
            if self.stop_flag.value:
                for session_uuid in self.input_dict:
                    new_requests = self.input_dict[session_uuid].close_and_get_remains()
                    incoming_batches.extend(new_requests)
                to_exit = True
            else:
                for session_uuid in self.input_dict:
                    new_requests = self.input_dict[session_uuid].get_batch()
                    incoming_batches.extend(new_requests)

            for request in new_requests:
                data: NxsInferRequest = request

                carry_over_extras = {}
                if data.carry_over_extras is not None:
                    try:
                        carry_over_extras = pickle.loads(data.carry_over_extras)
                    except:
                        carry_over_extras = {}

                self.request_entering(carry_over_extras)

                data.carry_over_extras = pickle.dumps(carry_over_extras)

            # trigger dispatcher to rearrange execution orders
            dispatching_result = self.dispatcher.dispatch(incoming_batches)

            # add delayed requests into delaying_batches
            delaying_batches.extend(dispatching_result.to_delay)

            # TODO: dropping requests is not supported yet - we should forward these requests directly to output process

            requests_count += len(dispatching_result.to_schedule)

            if dispatching_result.to_schedule:
                for request in dispatching_result.to_schedule:
                    data: NxsInferRequest = request
                    carry_over_extras = pickle.loads(data.carry_over_extras)
                    self.request_exiting(carry_over_extras)
                    data.carry_over_extras = pickle.dumps(carry_over_extras)

                self.output.put_batch(
                    self.next_topic_name, dispatching_result.to_schedule
                )

            if time.time() - tt0 > 5:
                if requests_count > 0:
                    fps = requests_count / (time.time() - tt0)
                    # print("input", "fps", fps)
                    self._log(f"FPS: {fps}")
                requests_count = 0

                # summary_log = self.dispatcher.get_stats_summary()
                # tp_log = NxsBackendThroughputLog(
                #     backend_name=self.args.backend_name,
                #     model_uuid=self.component_model.model_uuid,
                #     total_reqs=summary_log["total_reqs"],
                #     fps=summary_log["fps"],
                #     latency_mean=summary_log["latency"]["mean"],
                #     latency_min=summary_log["latency"]["min"],
                #     latency_max=summary_log["latency"]["max"],
                # )

                # self.log_pusher.push(GLOBAL_QUEUE_NAMES.BACKEND_LOGS, tp_log)

                tt0 = time.time()

            if to_exit:
                break

            if not incoming_batches:
                time.sleep(0.0025)

        # trigger next process to stop
        self.next_process_stop_flag.value = True

        self._log("Exiting...")

    def stop(self):
        self.stop_flag.value = True
        self.p.join()

    @abstractmethod
    def request_entering(self, extra_metadata: Dict):
        raise NotImplementedError

    @abstractmethod
    def request_exiting(self, extra_metadata: Dict):
        raise NotImplementedError
