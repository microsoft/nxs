import copy
import logging
import multiprocessing
import os
import shutil
import zipfile
from multiprocessing import Process, Value
from multiprocessing.managers import SyncManager
from threading import Lock, Thread

import GPUtil
from configs import *
from lru import LRU
from main_processes.backend.batcher_process import BackendBatcherProcess
from main_processes.backend.compute_process_onnx import BackendComputeProcessOnnx
from main_processes.backend.input_process import BackendInputProcess
from main_processes.backend.input_process_basic import BackendBasicInputProcess
from main_processes.backend.output_process import (
    BackendBasicOutputProcess,
    BackendOutputProcess,
)
from main_processes.backend.preprocessing_process import BackendPreprocessingProcess
from nxs_libs.interface.backend.dispatcher import BackendDispatcherType
from nxs_libs.interface.backend.global_dispatcher import (
    BasicGlobalDispatcher,
    MiniDispatcherInputData,
    MiniDispatcherUpdateData,
)
from nxs_libs.interface.backend.input import BackendInputInterfaceType
from nxs_libs.storage_cache import NxsBaseStorageCache, NxsLocalStorageCache
from nxs_types.backend import GpuInfo, NxsBackendType
from nxs_types.log import NxsBackendThroughputLog
from nxs_types.message import *
from nxs_types.model import Framework, NxsCompositoryModel, NxsModel
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.scheduling_data import (
    NxsSchedulingPerComponentModelPlan,
    NxsSchedulingPerCompositorymodelPlan,
    NxsUnschedulingPerCompositoryPlan,
)
from nxs_utils.common import create_dir_if_needed, delete_and_create_dir
from nxs_utils.logging import setup_logger
from nxs_utils.nxs_helper import *


class InferRuntimeInfo:
    def __init__(
        self,
        cmodel: NxsCompositoryModel,
        cmodel_plan: NxsSchedulingPerCompositorymodelPlan,
        session_uuids: List[str],
        processes: List,
        stop_flags: List[Value],
        infer_flags: List[Value],
        shared_queues: List,
    ) -> None:
        self.cmodel = cmodel
        self.cmodel_plan = cmodel_plan
        self.session_uuids = session_uuids
        self.processes = processes
        self.stop_flags = stop_flags
        self.infer_flags = infer_flags
        self.shared_list = shared_queues


class NxsBackendBaseProcess(ABC):
    MAX_CMODEL_INFO_CACHE_SIZE = 50

    def __init__(
        self,
        args: NxsBackendArgs,
        queue_puller: NxsQueuePuller,
        queue_pusher: NxsQueuePusher,
        main_db: NxsDb,
        model_store_cache: NxsBaseStorageCache,
        storage: NxsStorage,
    ) -> None:
        self.args = args
        self.backend_name = args.backend_name
        self.queue_puller = queue_puller
        self.queue_pusher = queue_pusher
        self.main_db = main_db
        self.model_info_cache = LRU(self.MAX_CMODEL_INFO_CACHE_SIZE)
        self.model_store_cache = model_store_cache
        self.storage = storage

        self.use_gpu = True
        if self._get_gpu_info() is None:
            self.use_gpu = False

        try:
            self.queue_pusher.update_config({"num_partitions": 1})
        except:
            pass
        self.queue_pusher.create_topic(self.backend_name)

        self.heartbeat_interval = 10
        self.heartbeat_thread = None
        self.heartbeat_thread_stop_flag = False

        # store a map from cmodel_uuid -> infer_process (input, compute, output)
        self.infer_runtime_map: Dict[str, InferRuntimeInfo] = {}

        # setup global dispatcher
        self.global_dispatcher = BasicGlobalDispatcher(
            self._generate_global_dispatcher_params()
        )
        self.global_dispatcher_period_secs = 3  # trigger global dispacher every N secs
        self.global_dispatcher_report_to_scheduler_period_secs = 10
        self.global_dispatcher_stop_flag: bool = False
        self.global_dispatcher_lock = Lock()
        self.global_dispatcher_thr = Thread(
            target=self.global_dispatcher_thread, args=()
        )
        self.global_dispatcher_thr.start()

        # self.log_prefix = f"BACKEND_{self.backend_name}"
        self.log_prefix = "BACKEND_MAIN"
        setup_logger()

        self._register_backend()

    @abstractmethod
    def _generate_global_dispatcher_params(self) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def _get_backend_stat_metadata(self) -> str:
        return "{}"

    def _log(self, message, log_level=logging.INFO):
        logging.log(log_level, f"{self.log_prefix} - {message}")

    def _get_backend_stat(self) -> BackendStat:
        return BackendStat(
            gpu_info=self._get_gpu_info(),
            extra_data=self._get_backend_stat_metadata(),
        )

    def _get_gpu_info(self) -> GpuInfo:
        try:
            gpu = GPUtil.getGPUs()[0]  # only support single gpu container
            return GpuInfo(
                gpu_name=gpu.name,
                gpu_total_mem=gpu.memoryTotal,
                gpu_available_mem=gpu.memoryFree,
            )
        except:
            return None

    def heartbeat_thread_fn(self):
        t0 = time.time()
        last_alive_ts = time.time()
        while not self.heartbeat_thread_stop_flag:
            if time.time() - t0 > self.heartbeat_interval:
                data = NxsMsgReportHeartbeat(
                    backend_name=self.backend_name,
                    backend_stat=self._get_backend_stat(),
                )
                self.queue_pusher.push(GLOBAL_QUEUE_NAMES.SCHEDULER, data)
                t0 = time.time()

            if time.time() - last_alive_ts > 30 * 60:
                self._log("Heartbeat thread is still alive...")
                last_alive_ts = time.time()

            time.sleep(0.1)

    def _process_change_heartbeat_interval(
        self, request: NxsMsgChangeHeartbeatInterval
    ):
        self.heartbeat_interval = request.interval
        if self.heartbeat_thread is not None:
            # need to stop this thread first
            self.heartbeat_thread_stop_flag = True
            self._log("Stopping heartbeat thread...")
            self.heartbeat_thread.join()
            self._log("Heartbeat thread was stopped...")
            self.heartbeat_thread = None
            self.heartbeat_thread_stop_flag = False

        self.heartbeat_thread = Thread(target=self.heartbeat_thread_fn, args=())
        self.heartbeat_thread.start()

    def _register_backend(self):
        request = NxsMsgRegisterBackend(
            backend_name=self.backend_name,
            backend_stat=self._get_backend_stat(),
        )
        self.queue_pusher.push(GLOBAL_QUEUE_NAMES.SCHEDULER, request)

    def run(self):
        from multiprocessing import Manager, Process, Value

        last_alive_ts = time.time()

        with Manager() as manager:
            while True:
                msgs = self.queue_puller.pull()
                for msg in msgs:
                    # print(msg)
                    if msg.type == NxsMsgType.CHANGE_HEARTBEAT_INTERVAL:
                        self._process_change_heartbeat_interval(msg)
                    elif msg.type == NxsMsgType.REQUEST_REREGISTER_BACKEND:
                        self._register_backend()
                        # remove all models
                        for key in list(self.infer_runtime_map.keys()):
                            model_uuid = self.infer_runtime_map[
                                key
                            ].cmodel_plan.model_uuid
                            unschedule_plan = NxsUnschedulingPerBackendPlan(
                                backend_name=self.backend_name,
                                compository_model_plans=[
                                    NxsUnschedulingPerCompositoryPlan(
                                        model_uuid=self.infer_runtime_map[
                                            key
                                        ].cmodel_plan.model_uuid,
                                        session_uuid_list=copy.deepcopy(
                                            self.infer_runtime_map[
                                                key
                                            ].cmodel_plan.session_uuid_list
                                        ),
                                    )
                                ],
                            )
                            self._process_unscheduling_plan(unschedule_plan, manager)
                            print(f"Removed model {model_uuid}")
                    elif msg.type == NxsMsgType.SCHEDULE_PLAN:
                        self.global_dispatcher_lock.acquire()
                        # self._process_scheduling_plan(msg.plan, manager)
                        self._process_scheduling_plan_v2(msg.plan, manager)
                        self.global_dispatcher_lock.release()
                    elif msg.type == NxsMsgType.UNSCHEDULE_PLAN:
                        self.global_dispatcher_lock.acquire()
                        self._process_unscheduling_plan(msg.plan, manager)
                        self.global_dispatcher_lock.release()

                if time.time() - last_alive_ts > 30 * 60:
                    self._log("Main process is still alive...")
                    last_alive_ts = time.time()

                if not msgs:
                    time.sleep(0.1)

    def global_dispatcher_thread(self):
        t0 = time.time()
        t1 = time.time()

        upload_logs_t0 = time.time()

        log_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)

        while not self.global_dispatcher_stop_flag:
            if time.time() - t0 < self.global_dispatcher_period_secs:
                time.sleep(0.1)
                continue

            self.global_dispatcher_lock.acquire()

            try:
                for cmodel_uuid in self.infer_runtime_map:
                    infer_rt = self.infer_runtime_map[cmodel_uuid]
                    input_process: BackendInputProcess = infer_rt.processes[0]

                    mini_dispatcher_data = []
                    for _ in range(
                        len(input_process.global_dispatcher_output_shared_list)
                    ):
                        mini_dispatcher_data.append(
                            input_process.global_dispatcher_output_shared_list.pop(0)
                        )

                    self.global_dispatcher.update_minidispatcher_stats(
                        MiniDispatcherInputData(cmodel_uuid, mini_dispatcher_data)
                    )

                output_data = self.global_dispatcher.generate_minidispatcher_updates()

                for data in output_data:
                    cmodel_uuid = data.cmodel_uuid
                    infer_rt = self.infer_runtime_map[cmodel_uuid]
                    input_process: BackendInputProcess = infer_rt.processes[0]
                    input_process.global_dispatcher_input_shared_list.append(data.data)
            except Exception as e:
                self._log(f"GLOBAL_DISPATCHER_EXCEPTION: {str(e)}")

            self.global_dispatcher_lock.release()

            # report stats to scheduler if needed
            if (
                time.time() - t1
                > self.global_dispatcher_report_to_scheduler_period_secs
            ):
                backend_report = (
                    self.global_dispatcher.generate_backend_stats_report_in_json_str()
                )
                self.queue_pusher.push(
                    GLOBAL_QUEUE_NAMES.SCHEDULER,
                    NxsMsgBackendStatsReport(
                        backend_name=self.backend_name,
                        data_in_json_str=backend_report,
                    ),
                )
                t1 = time.time()

            # update log
            if time.time() - upload_logs_t0 >= 5:
                logs = []
                try:
                    logs = self.global_dispatcher.generate_backend_monitoring_log()
                except Exception as e:
                    print(e)

                try:
                    log_pusher.push(
                        GLOBAL_QUEUE_NAMES.BACKEND_LOGS,
                        NxsBackendThroughputLog(
                            backend_name=self.backend_name,
                            backend_type=NxsBackendType.GPU
                            if self.use_gpu
                            else NxsBackendType.CPU,
                            model_logs=logs,
                        ),
                    )
                except Exception as e:
                    print(e)
                upload_logs_t0 = time.time()

            t0 = time.time()

    def _process_unscheduling_plan(
        self, plan: NxsUnschedulingPerBackendPlan, mp_manager: SyncManager
    ):
        for cmodel_plan in plan.compository_model_plans:
            cmodel_uuid = cmodel_plan.model_uuid

            if cmodel_uuid not in self.infer_runtime_map:
                continue

            first_input_process: BackendInputProcess = self.infer_runtime_map[
                cmodel_uuid
            ].processes[0]
            for to_undeploy_session_uuid in cmodel_plan.session_uuid_list:
                first_input_process.remove_session_uuid(to_undeploy_session_uuid)

            if first_input_process.input_interface_args_dict:
                continue

            infer_runtime = self.infer_runtime_map[cmodel_uuid]
            infer_runtime.stop_flags[0].value = True

            # wait few seconds to process all pending requests
            time.sleep(3)

            self._log(f"Stopping processes - model {cmodel_uuid}")
            for pid, process in enumerate(infer_runtime.processes):
                # process.stop()
                process.terminate()
            self._log(f"Stopped processes - model {cmodel_uuid}")

            for component_model in self.infer_runtime_map[
                cmodel_uuid
            ].cmodel.component_models:
                dir_abs_path = os.path.dirname(os.path.realpath(__file__))
                component_model_dir_path = os.path.join(
                    dir_abs_path, component_model.model_uuid
                )
                # print(f"to_delete_folder: {component_model_dir_path}")
                self._log(f"to_delete_folder: {component_model_dir_path}")
                shutil.rmtree(component_model_dir_path)

            self.global_dispatcher.remove_state(cmodel_uuid)

            self.infer_runtime_map.pop(cmodel_uuid)
            # print(f"Stopped model {cmodel_uuid}")
            self._log(f"Stopped model {cmodel_uuid}")

    def _process_scheduling_plan(
        self, plan: NxsSchedulingPerBackendPlan, mp_manager: SyncManager
    ):
        for cmodel_plan, duty_cycle in zip(
            plan.compository_model_plans, plan.duty_cyles
        ):
            if cmodel_plan.model_uuid in self.infer_runtime_map:
                # model is running
                first_input_process: BackendInputProcess = self.infer_runtime_map[
                    cmodel_plan.model_uuid
                ].processes[0]
                for session_uuid in cmodel_plan.session_uuid_list:
                    if session_uuid in first_input_process.input_interface_args_dict:
                        continue

                    existing_session_uuid = list(
                        first_input_process.input_interface_args_dict.keys()
                    )[0]
                    input_interface_args = copy.deepcopy(
                        first_input_process.input_interface_args_dict[
                            existing_session_uuid
                        ]
                    )
                    input_interface_args["session_uuid"] = session_uuid
                    first_input_process.add_session(input_interface_args)

                continue

            self._log(f"Deploying cmodel {cmodel_plan.model_uuid} ...")

            cmodel = self._get_compository_model_from_plan(cmodel_plan)

            component_model_paths = []
            component_preprocessing_paths = []
            component_transforming_paths = []
            component_postprocessing_paths = []
            component_processes = []

            # download model from cache
            self._log(
                f"Downloading models and processing functions for cmodel {cmodel_plan.model_uuid} ..."
            )
            for component_model in cmodel.component_models:
                dir_abs_path = os.path.dirname(os.path.realpath(__file__))
                component_model_dir_path = os.path.join(
                    dir_abs_path, component_model.model_uuid
                )
                create_dir_if_needed(component_model_dir_path)

                cached_component_model_path = self.model_store_cache.get_model_path(
                    component_model.model_uuid
                )

                is_zip_file = zipfile.is_zipfile(cached_component_model_path)

                # extract the zip file to model dir path
                if is_zip_file:
                    shutil.unpack_archive(
                        cached_component_model_path,
                        component_model_dir_path,
                        format="zip",
                    )

                # copy cached model into new location
                if component_model.framework == Framework.ONNX:
                    component_model_path = os.path.join(
                        component_model_dir_path, f"model.onnx"
                    )
                elif component_model.framework == Framework.TVM:
                    component_model_path = os.path.join(
                        component_model_dir_path, f"model.so"
                    )
                elif component_model.framework == Framework.BATCHED_TVM:
                    # component_model_path = os.path.join(
                    #     component_model_dir_path, f"model.zip"
                    # )
                    component_model_path = component_model_dir_path
                elif component_model.framework == Framework.TF_PB:
                    component_model_path = os.path.join(
                        component_model_dir_path, f"model.pb"
                    )
                else:
                    # should not go here
                    component_model_path = os.path.join(
                        component_model_dir_path, f"model.onnx"
                    )

                if not is_zip_file:
                    shutil.copy(cached_component_model_path, component_model_path)

                # TODO: we should also cache these preprocess/postprocess/transform-ing
                # print(
                #     f"preprocessing/{component_model.model_desc.preprocessing_name}.py"
                # )
                preproc_data = self.storage.download(
                    f"preprocessing/{component_model.model_desc.preprocessing_name}.py"
                )
                # print(
                #     f"postprocessing/{component_model.model_desc.postprocessing_name}.py"
                # )
                postproc_data = self.storage.download(
                    f"postprocessing/{component_model.model_desc.postprocessing_name}.py"
                )

                preproc_path = os.path.join(
                    component_model_dir_path, "preprocessing.py"
                )
                with open(preproc_path, "wb") as f:
                    f.write(preproc_data)

                postproc_path = os.path.join(
                    component_model_dir_path, "postprocessing.py"
                )
                with open(postproc_path, "wb") as f:
                    f.write(postproc_data)

                transform_path = ""
                if (
                    component_model.model_desc.transforming_name is not None
                    and component_model.model_desc.transforming_name.lower()
                    not in [
                        "",
                        "none",
                    ]
                ):
                    # print(
                    #     f"transforming/{component_model.model_desc.transforming_name}.py"
                    # )
                    transforming_data = self.storage.download(
                        f"transforming/{component_model.model_desc.transforming_name}.py"
                    )
                    transform_path = os.path.join(
                        component_model_dir_path, "transforming.py"
                    )
                    with open(transform_path, "wb") as f:
                        f.write(transforming_data)

                component_model_paths.append(component_model_path)
                component_preprocessing_paths.append(preproc_path)
                component_postprocessing_paths.append(postproc_path)
                component_transforming_paths.append(transform_path)

            self._log(
                f"Downloaded models and processing functions for cmodel {cmodel_plan.model_uuid}"
            )

            shared_queues = []
            stop_flags = []
            allow_inference_flags = []

            # launch processes to run component models
            dispatcher_update_shared_list = mp_manager.list()
            global_dispatcher_input_shared_list = mp_manager.list()
            global_dispatcher_output_shared_list = mp_manager.list()

            self._log(f"Creating processes for cmodel {cmodel_plan.model_uuid} ...")

            for idx in range(len(cmodel.component_models)):
                component_model = cmodel.component_models[idx]
                component_model_plan = cmodel_plan.component_model_plans[idx]

                # create shared_output_queue as shortcut for failed requests
                shared_output_queue = multiprocessing.Queue()

                # create input_inf for input_process
                if idx == 0:
                    input_process_input_interface_args = {
                        "type": BackendInputInterfaceType.REDIS,
                        "address": self.args.job_redis_queue_address,
                        "port": self.args.job_redis_queue_port,
                        "password": self.args.job_redis_queue_password,
                        "is_using_ssl": self.args.job_redis_queue_use_ssl,
                        "topic": component_model.model_uuid,
                    }
                    input_interface_args_dict = {}
                    for session_uuid in cmodel_plan.session_uuid_list:
                        _input_process_input_interface_args = copy.deepcopy(
                            input_process_input_interface_args
                        )
                        # FIXME: find better way to set session_uuid input for queue
                        _input_process_input_interface_args[
                            "session_uuid"
                        ] = session_uuid
                        input_interface_args_dict[
                            session_uuid
                        ] = _input_process_input_interface_args
                else:
                    input_process_input_interface_args = {
                        "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                        "mp_queue": shared_queues[-1],
                    }
                    input_interface_args_dict = {
                        "global": input_process_input_interface_args
                    }

                # create output_inf for input_process
                # shared_list = mp_manager.list()
                # shared_queues.append(shared_list)
                shared_queue = multiprocessing.Queue()
                shared_queues.append(shared_queue)
                input_process_output_interface_args = {
                    "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                    "mp_queue": shared_queues[-1],
                }

                # create dispatcher for input_process
                if idx == 0:
                    dispatcher_args = {"type": BackendDispatcherType.BASIC_MONITORING}
                else:
                    dispatcher_args = None

                if idx == 0:
                    stop_input_flag = Value("i", False)
                    stop_flags.append(stop_input_flag)
                else:
                    stop_input_flag = stop_flags[-1]

                stop_preprocessors_flag = Value("i", False)
                stop_flags.append(stop_preprocessors_flag)

                input_process = BackendBasicInputProcess(
                    args=self.args,
                    component_model=component_model,
                    component_model_plan=component_model_plan,
                    preprocessing_fn_path=component_preprocessing_paths[idx],
                    input_interface_args_dict=input_interface_args_dict,
                    output_interface_args=input_process_output_interface_args,
                    dispatcher_args=dispatcher_args,
                    stop_flag=stop_input_flag,
                    next_process_stop_flag=stop_preprocessors_flag,
                    dispatcher_update_shared_list=dispatcher_update_shared_list
                    if idx == 0
                    else None,
                    global_dispatcher_input_shared_list=global_dispatcher_input_shared_list
                    if idx == 0
                    else None,
                    global_dispatcher_output_shared_list=global_dispatcher_output_shared_list
                    if idx == 0
                    else None,
                    process_update_shared_list=mp_manager.list(),
                )

                # create preprocessors
                preprocessors_process_input_interface_args = {
                    "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                    "mp_queue": shared_queues[-1],
                }

                # shared_list = mp_manager.list()
                # shared_queues.append(shared_list)

                # shared_queue = multiprocessing.Queue()
                # shared_queues.append(shared_queue)
                # preprocessors_process_output_interface_args = {
                #     "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                #     "mp_queue": shared_queues[-1],
                # }

                # stop_batcher_flag = Value("i", False)
                # stop_flags.append(stop_batcher_flag)

                # stop_compute_flag = Value("i", False)
                # stop_flags.append(stop_compute_flag)

                stop_compute_flags = []
                compute_input_queues = []

                preprocessor_processes = []
                for pid in range(component_model.num_preprocessors):
                    shared_queue = multiprocessing.Queue()
                    shared_queues.append(shared_queue)
                    preprocessors_process_output_interface_args = {
                        "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                        "mp_queue": shared_queues[-1],
                    }
                    error_output_interface_args = {
                        "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                        "mp_queue": shared_output_queue,
                    }

                    stop_compute_flag = Value("i", False)
                    stop_flags.append(stop_compute_flag)

                    p = BackendPreprocessingProcess(
                        args=None,
                        component_model=component_model,
                        component_model_plan=component_model_plan,
                        pid=pid,
                        preprocessing_fn_path=component_preprocessing_paths[idx],
                        input_interface_args=preprocessors_process_input_interface_args,
                        output_interface_args=preprocessors_process_output_interface_args,
                        error_shortcut_interface_args=error_output_interface_args,
                        stop_flag=stop_preprocessors_flag,
                        # next_process_stop_flag=stop_batcher_flag,
                        next_process_stop_flag=stop_compute_flag,
                    )
                    preprocessor_processes.append(p)

                    stop_compute_flags.append(stop_compute_flag)
                    compute_input_queues.append(shared_queue)

                # create batcher
                # batcher_process_input_interface_args = {
                #     "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                #     "mp_queue": shared_queues[-1],
                # }

                # # shared_list = mp_manager.list()
                # # shared_queues.append(shared_list)
                # shared_queue = multiprocessing.Queue()
                # shared_queues.append(shared_queue)
                # batcher_process_output_interface_args = {
                #     "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                #     "mp_queue": shared_queues[-1],
                # }

                # stop_compute_flag = Value("i", False)
                # stop_flags.append(stop_compute_flag)

                # batcher_process = BackendBatcherProcess(
                #     args=None,
                #     component_model=component_model,
                #     component_model_plan=component_model_plan,
                #     input_interface_args=batcher_process_input_interface_args,
                #     output_interface_args=batcher_process_output_interface_args,
                #     stop_flag=stop_batcher_flag,
                #     next_process_stop_flag=stop_compute_flag,
                # )

                # create input_inf for compute_process
                # compute_process_input_interface_args = {
                #     "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                #     "mp_queue": shared_queues[-1],
                # }

                compute_process_input_interface_args_list = []
                for compute_input_queue in compute_input_queues:
                    compute_process_input_interface_args = {
                        "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                        "mp_queue": compute_input_queue,
                    }
                    compute_process_input_interface_args_list.append(
                        compute_process_input_interface_args
                    )

                # create output_inf for compute_process
                # shared_list = mp_manager.list()
                # shared_queues.append(shared_list)

                shared_queues.append(shared_output_queue)
                compute_process_output_interface_args = {
                    "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                    "mp_queue": shared_output_queue,
                }

                backend_compute_process_cls = BackendComputeProcessOnnx
                if component_model.framework == Framework.TVM:
                    from main_processes.backend.compute_process_tvm import (
                        BackendComputeProcessTvm,
                    )

                    backend_compute_process_cls = BackendComputeProcessTvm
                if component_model.framework == Framework.BATCHED_TVM:
                    from main_processes.backend.compute_process_batched_tvm import (
                        BackendComputeProcessBatchedTvm,
                    )

                    backend_compute_process_cls = BackendComputeProcessBatchedTvm
                elif component_model.framework == Framework.TF_PB:
                    from main_processes.backend.compute_process_tf import (
                        BackendComputeProcessTfv1,
                    )

                    backend_compute_process_cls = BackendComputeProcessTfv1

                allow_inference_flag = Value("i", True)
                allow_inference_flags.append(allow_inference_flag)

                stop_output_flag = Value("i", False)
                stop_flags.append(stop_output_flag)

                compute_process = backend_compute_process_cls(
                    args=None,
                    component_model=component_model,
                    component_model_plan=component_model_plan,
                    model_path=component_model_paths[idx],
                    use_gpu=self.use_gpu,
                    transforming_fn_path=component_transforming_paths[idx],
                    input_interface_args_list=compute_process_input_interface_args_list,
                    output_interface_args=compute_process_output_interface_args,
                    allow_infer_flag=allow_inference_flag,
                    stop_flags=stop_compute_flags,
                    next_process_stop_flag=stop_output_flag,
                )

                # create input_inf for output_process
                output_process_input_interface_args = {
                    "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                    "mp_queue": shared_output_queue,
                }

                # create output_inf for output_process
                if idx < len(cmodel.component_models) - 1:
                    # there are latter steps to forward outputs to
                    # shared_list = mp_manager.list()
                    # shared_queues.append(shared_list)
                    shared_queue = multiprocessing.Queue()
                    shared_queues.append(shared_queue)
                    output_process_output_interface_args = {
                        "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                        "mp_queue": shared_queues[-1],
                    }
                else:
                    # end of this pipeline
                    output_process_output_interface_args = {
                        "type": BackendInputInterfaceType.REDIS,
                        "address": self.args.job_redis_queue_address,
                        "port": self.args.job_redis_queue_port,
                        "password": self.args.job_redis_queue_password,
                        "is_using_ssl": self.args.job_redis_queue_use_ssl,
                    }

                next_process_stop_flag = None
                if idx < len(cmodel.component_models) - 1:
                    next_process_stop_flag = Value("i", False)
                    stop_flags.append(next_process_stop_flag)

                output_processes = []
                for pid in range(component_model.num_postprocessors):
                    output_process = BackendBasicOutputProcess(
                        args=None,
                        component_model=component_model,
                        component_model_plan=component_model_plan,
                        pid=pid,
                        postprocessing_fn_path=component_postprocessing_paths[idx],
                        input_interface_args=output_process_input_interface_args,
                        output_interface_args=output_process_output_interface_args,
                        stop_flag=stop_output_flag,
                        next_process_stop_flag=next_process_stop_flag,
                        dispatcher_update_shared_list=None
                        if idx < len(cmodel.component_models) - 1
                        else dispatcher_update_shared_list,
                    )
                    output_processes.append(output_process)

                component_processes.append(input_process)
                for p in preprocessor_processes:
                    component_processes.append(p)
                # component_processes.append(batcher_process)
                component_processes.append(compute_process)
                # component_processes.append(output_process)
                for p in output_processes:
                    component_processes.append(p)

            self._log(f"Created processes for cmodel {cmodel_plan.model_uuid}")

            self._log(f"Lauching processes for cmodel {cmodel_plan.model_uuid} ...")
            # start all processes
            for p in component_processes:
                p.run()
            self._log(f"Launched processes for cmodel {cmodel_plan.model_uuid}")

            infer_runtime_info = InferRuntimeInfo(
                cmodel,
                cmodel_plan,
                cmodel_plan.session_uuid_list,
                component_processes,
                stop_flags,
                allow_inference_flags,
                shared_queues,
            )
            self.infer_runtime_map[cmodel.main_model.model_uuid] = infer_runtime_info

            self._log(f"Deployed cmodel {cmodel_plan.model_uuid}")

    def _process_scheduling_plan_v2(
        self, plan: NxsSchedulingPerBackendPlan, mp_manager: SyncManager
    ):
        for cmodel_plan, duty_cycle in zip(
            plan.compository_model_plans, plan.duty_cyles
        ):
            self._deploy_compository_model_plan(mp_manager, cmodel_plan, duty_cycle)

    def _deploy_compository_model_plan(
        self,
        mp_manager: SyncManager,
        cmodel_plan: NxsSchedulingPerCompositorymodelPlan,
        duty_cycle: float,
    ):
        if cmodel_plan.model_uuid in self.infer_runtime_map:
            # model is running
            first_input_process: BackendInputProcess = self.infer_runtime_map[
                cmodel_plan.model_uuid
            ].processes[0]

            # update session list if needed
            for session_uuid in cmodel_plan.session_uuid_list:
                if session_uuid in first_input_process.input_interface_args_dict:
                    continue

                existing_session_uuid = list(
                    first_input_process.input_interface_args_dict.keys()
                )[0]
                input_interface_args = copy.deepcopy(
                    first_input_process.input_interface_args_dict[existing_session_uuid]
                )
                input_interface_args["session_uuid"] = session_uuid
                first_input_process.add_session(input_interface_args)

            return

        cmodel = self._get_compository_model_from_plan(cmodel_plan)

        component_model_paths = []
        component_preprocessing_paths = []
        component_transforming_paths = []
        component_postprocessing_paths = []
        component_processes = []

        # download model from cache
        self._log(
            f"Downloading models and processing functions for cmodel {cmodel_plan.model_uuid} ..."
        )

        for component_model in cmodel.component_models:
            if not component_model.is_custom_model:
                (
                    component_model_path,
                    preproc_path,
                    postproc_path,
                    transform_path,
                ) = self._download_pipelined_component_model(component_model)
            else:
                (
                    component_model_path,
                    preproc_path,
                    postproc_path,
                    transform_path,
                ) = self._download_arbitrary_component_model(component_model)

            component_model_paths.append(component_model_path)
            component_preprocessing_paths.append(preproc_path)
            component_postprocessing_paths.append(postproc_path)
            component_transforming_paths.append(transform_path)

            if component_model.is_custom_model and component_model_path == "":
                # could not unzip arbitrary model:
                # TODO: report back to scheduler
                return

        self._log(
            f"Downloaded models and processing functions for cmodel {cmodel_plan.model_uuid}"
        )

        shared_queues = []
        stop_flags = []
        allow_inference_flags = []

        # launch processes to run component models
        dispatcher_update_shared_list = mp_manager.list()
        global_dispatcher_input_shared_list = mp_manager.list()
        global_dispatcher_output_shared_list = mp_manager.list()

        self._log(f"Creating processes for cmodel {cmodel_plan.model_uuid} ...")

        for model_idx in range(len(cmodel.component_models)):
            component_model = cmodel.component_models[model_idx]
            component_model_plan = cmodel_plan.component_model_plans[model_idx]

            if not component_model.is_custom_model:
                self._deploy_pipelined_component_model(
                    mp_manager,
                    model_idx,
                    len(cmodel.component_models),
                    component_model,
                    component_model_plan,
                    cmodel_plan.session_uuid_list,
                    shared_queues,
                    stop_flags,
                    allow_inference_flags,
                    component_model_paths,
                    component_preprocessing_paths,
                    component_postprocessing_paths,
                    component_transforming_paths,
                    component_processes,
                    dispatcher_update_shared_list,
                    global_dispatcher_input_shared_list,
                    global_dispatcher_output_shared_list,
                )
            else:
                self._deploy_arbitrary_component_model(
                    mp_manager,
                    model_idx,
                    len(cmodel.component_models),
                    component_model,
                    component_model_plan,
                    cmodel_plan.session_uuid_list,
                    shared_queues,
                    stop_flags,
                    allow_inference_flags,
                    component_model_paths,
                    component_preprocessing_paths,
                    component_postprocessing_paths,
                    component_transforming_paths,
                    component_processes,
                    dispatcher_update_shared_list,
                    global_dispatcher_input_shared_list,
                    global_dispatcher_output_shared_list,
                )

        self._log(f"Lauching processes for cmodel {cmodel_plan.model_uuid} ...")
        # start all processes
        for p in component_processes:
            p.run()
        self._log(f"Launched processes for cmodel {cmodel_plan.model_uuid}")

        infer_runtime_info = InferRuntimeInfo(
            cmodel,
            cmodel_plan,
            cmodel_plan.session_uuid_list,
            component_processes,
            stop_flags,
            allow_inference_flags,
            shared_queues,
        )
        self.infer_runtime_map[cmodel.main_model.model_uuid] = infer_runtime_info

        self._log(f"Deployed cmodel {cmodel_plan.model_uuid}")

    def _deploy_pipelined_component_model(
        self,
        mp_manager: SyncManager,
        model_idx: int,
        num_component_models: int,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        session_uuid_list: List[str],
        shared_queues: List,
        stop_flags: List,
        allow_inference_flags: List,
        component_model_paths: List,
        component_preprocessing_paths: List,
        component_postprocessing_paths: List,
        component_transforming_paths: List,
        component_processes: List,
        dispatcher_update_shared_list,
        global_dispatcher_input_shared_list,
        global_dispatcher_output_shared_list,
    ):
        # create shared_output_queue as shortcut for failed requests
        shared_output_queue = multiprocessing.Queue()

        # create input_inf for input_process
        input_process = self._deploy_input_process(
            mp_manager,
            model_idx,
            component_model,
            component_model_plan,
            session_uuid_list,
            shared_queues,
            stop_flags,
            component_preprocessing_paths,
            dispatcher_update_shared_list,
            global_dispatcher_input_shared_list,
            global_dispatcher_output_shared_list,
        )

        (
            preprocessor_processes,
            compute_input_queues,
            stop_compute_flags,
        ) = self._deploy_pipelined_preproc_process(
            component_model,
            component_model_plan,
            shared_queues,
            stop_flags,
            shared_output_queue,
            component_preprocessing_paths[model_idx],
        )

        compute_process = self._deploy_pipelined_compute_process(
            component_model,
            component_model_plan,
            shared_queues,
            stop_flags,
            shared_output_queue,
            compute_input_queues,
            stop_compute_flags,
            allow_inference_flags,
            component_model_paths[model_idx],
            component_transforming_paths[model_idx],
        )

        output_processes = self._deploy_output_process(
            model_idx,
            num_component_models,
            component_model,
            component_model_plan,
            shared_queues,
            stop_flags,
            shared_output_queue,
            dispatcher_update_shared_list,
            component_postprocessing_paths[model_idx],
        )

        component_processes.append(input_process)
        for p in preprocessor_processes:
            component_processes.append(p)
        # component_processes.append(batcher_process)
        component_processes.append(compute_process)
        # component_processes.append(output_process)
        for p in output_processes:
            component_processes.append(p)

        return component_processes

    def _deploy_arbitrary_component_model(
        self,
        mp_manager: SyncManager,
        model_idx: int,
        num_component_models: int,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        session_uuid_list: List[str],
        shared_queues: List,
        stop_flags: List,
        allow_inference_flags: List,
        component_model_paths: List,
        component_preprocessing_paths: List,
        component_postprocessing_paths: List,
        component_transforming_paths: List,
        component_processes: List,
        dispatcher_update_shared_list,
        global_dispatcher_input_shared_list,
        global_dispatcher_output_shared_list,
    ):
        # create shared_output_queue as shortcut for failed requests
        shared_output_queue = multiprocessing.Queue()

        # create input_inf for input_process
        input_process = self._deploy_input_process(
            mp_manager,
            model_idx,
            component_model,
            component_model_plan,
            session_uuid_list,
            shared_queues,
            stop_flags,
            component_preprocessing_paths,
            dispatcher_update_shared_list,
            global_dispatcher_input_shared_list,
            global_dispatcher_output_shared_list,
        )

        model_process = self._deploy_arbitrary_model_process(
            component_model,
            component_model_plan,
            shared_queues,
            stop_flags,
            shared_output_queue,
            component_model_paths[model_idx],
        )

        output_processes = self._deploy_output_process(
            model_idx,
            num_component_models,
            component_model,
            component_model_plan,
            shared_queues,
            stop_flags,
            shared_output_queue,
            dispatcher_update_shared_list,
            component_postprocessing_paths[model_idx],
        )

        component_processes.append(input_process)
        component_processes.append(model_process)
        for p in output_processes:
            component_processes.append(p)

        return component_processes

    def _deploy_input_process(
        self,
        mp_manager: SyncManager,
        model_idx: int,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        session_uuid_list: List[str],
        shared_queues: List,
        stop_flags: List,
        component_preprocessing_paths: List,
        dispatcher_update_shared_list: List,
        global_dispatcher_input_shared_list: List,
        global_dispatcher_output_shared_list: List,
    ):
        # create input_inf for input_process
        if model_idx == 0:
            input_process_input_interface_args = {
                "type": BackendInputInterfaceType.REDIS,
                "address": self.args.job_redis_queue_address,
                "port": self.args.job_redis_queue_port,
                "password": self.args.job_redis_queue_password,
                "is_using_ssl": self.args.job_redis_queue_use_ssl,
                "topic": component_model.model_uuid,
            }
            input_interface_args_dict = {}
            for session_uuid in session_uuid_list:
                _input_process_input_interface_args = copy.deepcopy(
                    input_process_input_interface_args
                )
                # FIXME: find better way to set session_uuid input for queue
                _input_process_input_interface_args["session_uuid"] = session_uuid
                input_interface_args_dict[
                    session_uuid
                ] = _input_process_input_interface_args
        else:
            input_process_input_interface_args = {
                "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                "mp_queue": shared_queues[-1],
            }
            input_interface_args_dict = {"global": input_process_input_interface_args}

        # create output_inf for input_process
        shared_queue = multiprocessing.Queue()
        shared_queues.append(shared_queue)
        input_process_output_interface_args = {
            "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
            "mp_queue": shared_queues[-1],
        }

        # create dispatcher for input_process
        if model_idx == 0:
            dispatcher_args = {"type": BackendDispatcherType.BASIC_MONITORING}
        else:
            dispatcher_args = None

        if model_idx == 0:
            stop_input_flag = Value("i", False)
            stop_flags.append(stop_input_flag)
        else:
            stop_input_flag = stop_flags[-1]

        stop_preprocessors_flag = Value("i", False)
        stop_flags.append(stop_preprocessors_flag)

        input_process = BackendBasicInputProcess(
            args=self.args,
            component_model=component_model,
            component_model_plan=component_model_plan,
            preprocessing_fn_path=component_preprocessing_paths[model_idx],
            input_interface_args_dict=input_interface_args_dict,
            output_interface_args=input_process_output_interface_args,
            dispatcher_args=dispatcher_args,
            stop_flag=stop_input_flag,
            next_process_stop_flag=stop_preprocessors_flag,
            dispatcher_update_shared_list=dispatcher_update_shared_list
            if model_idx == 0
            else None,
            global_dispatcher_input_shared_list=global_dispatcher_input_shared_list
            if model_idx == 0
            else None,
            global_dispatcher_output_shared_list=global_dispatcher_output_shared_list
            if model_idx == 0
            else None,
            process_update_shared_list=mp_manager.list(),
        )

        return input_process

    def _deploy_pipelined_preproc_process(
        self,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        shared_queues: List,
        stop_flags: List,
        shared_output_queue,
        preprocessing_fn_path,
    ):
        stop_preprocessors_flag = stop_flags[-1]

        # create preprocessors
        preprocessors_process_input_interface_args = {
            "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
            "mp_queue": shared_queues[-1],
        }

        stop_compute_flags = []
        compute_input_queues = []

        preprocessor_processes = []
        for pid in range(component_model.num_preprocessors):
            shared_queue = multiprocessing.Queue()
            shared_queues.append(shared_queue)
            preprocessors_process_output_interface_args = {
                "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                "mp_queue": shared_queues[-1],
            }
            error_output_interface_args = {
                "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                "mp_queue": shared_output_queue,
            }

            stop_compute_flag = Value("i", False)
            stop_flags.append(stop_compute_flag)

            p = BackendPreprocessingProcess(
                args=None,
                component_model=component_model,
                component_model_plan=component_model_plan,
                pid=pid,
                preprocessing_fn_path=preprocessing_fn_path,
                input_interface_args=preprocessors_process_input_interface_args,
                output_interface_args=preprocessors_process_output_interface_args,
                error_shortcut_interface_args=error_output_interface_args,
                stop_flag=stop_preprocessors_flag,
                next_process_stop_flag=stop_compute_flag,
            )
            preprocessor_processes.append(p)

            stop_compute_flags.append(stop_compute_flag)
            compute_input_queues.append(shared_queue)

        return preprocessor_processes, compute_input_queues, stop_compute_flags

    def _deploy_pipelined_compute_process(
        self,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        shared_queues: List,
        stop_flags: List,
        shared_output_queue,
        compute_input_queues: List,
        stop_compute_flags: List,
        allow_inference_flags: List,
        model_path: str,
        transform_path: str,
    ):
        compute_process_input_interface_args_list = []
        for compute_input_queue in compute_input_queues:
            compute_process_input_interface_args = {
                "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                "mp_queue": compute_input_queue,
            }
            compute_process_input_interface_args_list.append(
                compute_process_input_interface_args
            )

        shared_queues.append(shared_output_queue)
        compute_process_output_interface_args = {
            "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
            "mp_queue": shared_output_queue,
        }

        backend_compute_process_cls = self._get_compute_process_cls(
            component_model.framework
        )

        allow_inference_flag = Value("i", True)
        allow_inference_flags.append(allow_inference_flag)

        stop_output_flag = Value("i", False)
        stop_flags.append(stop_output_flag)

        compute_process = backend_compute_process_cls(
            args=None,
            component_model=component_model,
            component_model_plan=component_model_plan,
            model_path=model_path,
            use_gpu=self.use_gpu,
            transforming_fn_path=transform_path,
            input_interface_args_list=compute_process_input_interface_args_list,
            output_interface_args=compute_process_output_interface_args,
            allow_infer_flag=allow_inference_flag,
            stop_flags=stop_compute_flags,
            next_process_stop_flag=stop_output_flag,
        )

        return compute_process

    def _deploy_arbitrary_model_process(
        self,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        shared_queues: List,
        stop_flags: List,
        shared_output_queue,
        model_dir_path: str,
    ):
        stop_arbitrary_model_flag = stop_flags[-1]

        # create input_inf for output_process
        process_input_interface_args = {
            "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
            "mp_queue": shared_queues[-1],
        }

        shared_queues.append(shared_output_queue)
        process_output_interface_args = {
            "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
            "mp_queue": shared_output_queue,
        }

        stop_output_flag = Value("i", False)
        stop_flags.append(stop_output_flag)

        from main_processes.backend.custom_model_process import (
            BackendCustomModelProcess,
        )

        _process = BackendCustomModelProcess(
            args=None,
            component_model=component_model,
            component_model_plan=component_model_plan,
            model_def_path=model_dir_path,
            input_interface_args=process_input_interface_args,
            output_interface_args=process_output_interface_args,
            stop_flag=stop_arbitrary_model_flag,
            next_process_stop_flag=stop_output_flag,
        )

        return _process

    def _deploy_output_process(
        self,
        model_idx: int,
        num_component_models: int,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        shared_queues: List,
        stop_flags: List,
        shared_output_queue,
        dispatcher_update_shared_list: List,
        postproc_path: str,
    ):
        stop_output_flag = stop_flags[-1]

        # create input_inf for output_process
        output_process_input_interface_args = {
            "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
            "mp_queue": shared_output_queue,
        }

        # create output_inf for output_process
        if model_idx < num_component_models - 1:
            shared_queue = multiprocessing.Queue()
            shared_queues.append(shared_queue)
            output_process_output_interface_args = {
                "type": BackendInputInterfaceType.MULTIPROCESSING_QUEUE,
                "mp_queue": shared_queues[-1],
            }
        else:
            # end of this pipeline
            output_process_output_interface_args = {
                "type": BackendInputInterfaceType.REDIS,
                "address": self.args.job_redis_queue_address,
                "port": self.args.job_redis_queue_port,
                "password": self.args.job_redis_queue_password,
                "is_using_ssl": self.args.job_redis_queue_use_ssl,
            }

        next_process_stop_flag = None
        if model_idx < num_component_models - 1:
            next_process_stop_flag = Value("i", False)
            stop_flags.append(next_process_stop_flag)

        output_processes = []
        for pid in range(component_model.num_postprocessors):
            output_process = BackendBasicOutputProcess(
                args=None,
                component_model=component_model,
                component_model_plan=component_model_plan,
                pid=pid,
                postprocessing_fn_path=postproc_path,
                input_interface_args=output_process_input_interface_args,
                output_interface_args=output_process_output_interface_args,
                stop_flag=stop_output_flag,
                next_process_stop_flag=next_process_stop_flag,
                dispatcher_update_shared_list=None
                if model_idx < num_component_models - 1
                else dispatcher_update_shared_list,
            )
            output_processes.append(output_process)

        return output_processes

    def _get_compute_process_cls(self, framework: Framework):
        backend_compute_process_cls = BackendComputeProcessOnnx
        if framework == Framework.TVM:
            from main_processes.backend.compute_process_tvm import (
                BackendComputeProcessTvm,
            )

            backend_compute_process_cls = BackendComputeProcessTvm
        if framework == Framework.BATCHED_TVM:
            from main_processes.backend.compute_process_batched_tvm import (
                BackendComputeProcessBatchedTvm,
            )

            backend_compute_process_cls = BackendComputeProcessBatchedTvm
        elif framework == Framework.TF_PB:
            from main_processes.backend.compute_process_tf import (
                BackendComputeProcessTfv1,
            )

            backend_compute_process_cls = BackendComputeProcessTfv1

        return backend_compute_process_cls

    def _download_pipelined_component_model(self, component_model: NxsModel):
        dir_abs_path = os.path.dirname(os.path.realpath(__file__))
        component_model_dir_path = os.path.join(
            dir_abs_path, component_model.model_uuid
        )
        create_dir_if_needed(component_model_dir_path)

        cached_component_model_path = self.model_store_cache.get_model_path(
            component_model.model_uuid
        )

        is_zip_file = zipfile.is_zipfile(cached_component_model_path)

        # extract the zip file to model dir path
        if is_zip_file:
            shutil.unpack_archive(
                cached_component_model_path,
                component_model_dir_path,
                format="zip",
            )

        # copy cached model into new location
        component_model_path = os.path.join(component_model_dir_path, f"model.onnx")
        if component_model.framework == Framework.ONNX:
            component_model_path = os.path.join(component_model_dir_path, f"model.onnx")
        elif component_model.framework == Framework.TVM:
            component_model_path = os.path.join(component_model_dir_path, f"model.so")
        elif component_model.framework == Framework.BATCHED_TVM:
            component_model_path = component_model_dir_path
        elif component_model.framework == Framework.TF_PB:
            component_model_path = os.path.join(component_model_dir_path, f"model.pb")

        if not is_zip_file:
            shutil.copy(cached_component_model_path, component_model_path)

        preproc_data = self.storage.download(
            f"preprocessing/{component_model.model_desc.preprocessing_name}.py"
        )
        postproc_data = self.storage.download(
            f"postprocessing/{component_model.model_desc.postprocessing_name}.py"
        )

        preproc_path = os.path.join(component_model_dir_path, "preprocessing.py")
        with open(preproc_path, "wb") as f:
            f.write(preproc_data)

        postproc_path = os.path.join(component_model_dir_path, "postprocessing.py")
        with open(postproc_path, "wb") as f:
            f.write(postproc_data)

        transform_path = ""
        if (
            component_model.model_desc.transforming_name is not None
            and component_model.model_desc.transforming_name.lower()
            not in [
                "",
                "none",
            ]
        ):
            transforming_data = self.storage.download(
                f"transforming/{component_model.model_desc.transforming_name}.py"
            )
            transform_path = os.path.join(component_model_dir_path, "transforming.py")
            with open(transform_path, "wb") as f:
                f.write(transforming_data)

        return component_model_path, preproc_path, postproc_path, transform_path

    def _download_arbitrary_component_model(self, component_model: NxsModel):
        dir_abs_path = os.path.dirname(os.path.realpath(__file__))
        component_model_dir_path = os.path.join(
            dir_abs_path, component_model.model_uuid
        )
        create_dir_if_needed(component_model_dir_path)

        cached_component_model_path = self.model_store_cache.get_model_path(
            component_model.model_uuid
        )

        is_zip_file = zipfile.is_zipfile(cached_component_model_path)

        # extract the zip file to model dir path
        if is_zip_file:
            shutil.unpack_archive(
                cached_component_model_path,
                component_model_dir_path,
                format="zip",
            )
        else:
            # arbitrary model should be in zip format
            component_model_dir_path = ""
            logging.critical(
                f"{component_model.model_uuid}: Arbitrary model should be in zip format."
            )

        preproc_path = ""
        postproc_path = ""
        transform_path = ""

        return component_model_dir_path, preproc_path, postproc_path, transform_path

    def _get_compository_model_from_plan(
        self, cmodel_plan: NxsSchedulingPerCompositorymodelPlan
    ) -> NxsCompositoryModel:
        cmodel_uuid = cmodel_plan.model_uuid

        if self.model_info_cache.has_key(cmodel_uuid):
            return self.model_info_cache[cmodel_uuid]

        model_info = self.main_db.query(
            MONGODB_MODELS_COLLECTION_NAME, {"model_uuid": cmodel_uuid}
        )[0]
        main_model = NxsModel(**model_info)

        component_models = []
        for component_model_plan in cmodel_plan.component_model_plans:
            model_info = self.main_db.query(
                MONGODB_MODELS_COLLECTION_NAME,
                {"model_uuid": component_model_plan.model_uuid},
            )[0]
            model = NxsModel(**model_info)
            component_models.append(model)

        cmodel = NxsCompositoryModel(
            main_model=main_model, component_models=component_models
        )

        self.model_info_cache[cmodel_uuid] = cmodel

        return cmodel


class NxsBackendProcess(NxsBackendBaseProcess):
    def __init__(
        self,
        args: NxsBackendArgs,
        queue_puller: NxsQueuePuller,
        queue_pusher: NxsQueuePusher,
        main_db: NxsDb,
        model_store_cache: NxsBaseStorageCache,
        model_store: NxsStorage,
    ) -> None:
        super().__init__(
            args,
            queue_puller,
            queue_pusher,
            main_db,
            model_store_cache,
            model_store,
        )

    def _get_backend_stat_metadata(self) -> str:
        return "{}"

    def _generate_global_dispatcher_params(self) -> Dict:
        return {"backend_process": self}


if __name__ == "__main__":
    from main_processes.backend.args import parse_args

    args = parse_args()

    queue_puller = create_queue_puller_from_args(
        args, NxsQueueType.REDIS, args.backend_name
    )
    queue_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)

    main_db = create_db_from_args(args, args.db_type)

    model_store = create_storage_from_args(args, args.storage_type)

    # NOTE: model cache has to be big enough to store all running models (e.g., 50 models)
    model_store_cache = NxsLocalStorageCache(model_store, max_cache_size=50)

    backend = NxsBackendProcess(
        args,
        queue_puller,
        queue_pusher,
        main_db,
        model_store_cache,
        model_store,
    )
    backend.run()
