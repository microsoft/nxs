import copy
import json
import time
from lru import LRU
from configs import GLOBAL_QUEUE_NAMES
from nxs_libs.interface.scheduling_policy.simple_policy_v2 import (
    SimpleSchedulingPolicyv2,
)
from nxs_libs.queue import NxsQueuePuller, NxsQueuePusher
from nxs_libs.simple_key_value_db import (
    NxsSimpleKeyValueDb,
    NxsSimpleKeyValueDbFactory,
    NxsSimpleKeyValueDbType,
)
from nxs_libs.db import NxsDb, NxsDbFactory, NxsDbType
from nxs_libs.object.backend_runtime import NxsBackendRuntime
from nxs_libs.object.pipeline_runtime import NxsPipelineRuntime
from nxs_libs.interface.scheduling_policy import BaseSchedulingPolicy
from nxs_types.backend import BackendInfo
from nxs_types.model import (
    NxsCompositoryModel,
    NxsModel,
    NxsPipelineInfo,
)
from nxs_types.nxs_args import NxsSchedulerArgs
from nxs_types.message import *
from nxs_types.scheduling_data import NxsSchedulingRequest
from nxs_libs.queue import (
    NxsQueuePuller,
    NxsQueuePullerFactory,
    NxsQueuePusher,
    NxsQueuePusherFactory,
    NxsQueueType,
)
from nxs_utils.nxs_helper import (
    create_db_from_args,
    create_queue_puller_from_args,
    create_queue_pusher_from_args,
    create_simple_key_value_db_from_args,
)


class NxsSchedulerProcess:
    PIPELINE_CACHE_SIZE = 10

    BACKEND_ROOT_TOPIC = "backends"
    MODEL_ROOT_TOPIC = "models"

    def __init__(
        self,
        args: NxsSchedulerArgs,
        queue_puller: NxsQueuePuller,
        queue_pusher: NxsQueuePusher,
        state_db: NxsSimpleKeyValueDb,
        main_db: NxsDb,
        scheduling_policy: BaseSchedulingPolicy,
    ) -> None:
        self.args = args
        self.queue_puller = queue_puller
        self.queue_pusher = queue_pusher
        self.state_db = state_db
        self.main_db = main_db
        self.scheduling_policy = scheduling_policy

        self.queue_pusher.create_topic(GLOBAL_QUEUE_NAMES.SCHEDULER)

        self.backends: dict[str, NxsBackendRuntime] = {}
        self.cpu_backends: dict[str, NxsBackendRuntime] = {}
        self.gpu_backends: dict[str, NxsBackendRuntime] = {}

        self.pipeline_info_cache = LRU(self.PIPELINE_CACHE_SIZE)
        self.compository_model_info_cache = LRU(self.PIPELINE_CACHE_SIZE * 5)

        self.last_requests: List[NxsSchedulingRequest] = []

    def _get_pipeline_info(self, pipeline_uuid) -> NxsPipelineRuntime:
        if self.pipeline_info_cache.has_key(pipeline_uuid):
            print(f"Retrieved pipeline {pipeline_uuid} from cache")
            return self.pipeline_info_cache[pipeline_uuid]

        pipeline = NxsPipelineRuntime.get_from_db(pipeline_uuid, self.main_db)
        if pipeline:
            self.pipeline_info_cache[pipeline_uuid] = pipeline
            print(f"Inserted pipeline {pipeline_uuid} to cache")

        for atomic_model in pipeline.pipeline.models:
            self.compository_model_info_cache[
                atomic_model.main_model.model_uuid
            ] = atomic_model

        return pipeline

    def _get_compository_model_info(
        self, compository_model_uuid: str
    ) -> NxsCompositoryModel:
        if self.compository_model_info_cache.has_key(compository_model_uuid):
            return self.compository_model_info_cache[compository_model_uuid]

        return None

    def _update_backend_name_list_in_db(self):
        print("_update_backend_name_list_in_db called")
        backend_names = list(self.backends.keys())
        print(backend_names)
        self.state_db.set_value(self.BACKEND_ROOT_TOPIC, backend_names)

    def run(self):
        check_expired_backend_t0 = time.time()

        self.restore_scheduler_states()

        while True:
            msgs = self.queue_puller.pull()
            for msg in msgs:
                # print(msg)
                if msg.type == NxsMsgType.REGISTER_BACKEND:
                    self.process_register_backend(msg)
                if msg.type == NxsMsgType.REGISTER_WORKLOADS:
                    print(msg)
                    self.process_register_workloads(msg)
                if msg.type == NxsMsgType.REPORT_HEARTBEAT:
                    self.process_heartbeat_msg(msg)
                if msg.type == NxsMsgType.REPORT_BACKEND_STATS:
                    self.process_backend_stats(msg)

            if (
                time.time() - check_expired_backend_t0
                > self.args.backend_timeout_secs / 3
            ):
                print("Running check_expired_backend ...")
                if self.has_expired_backends():
                    # reschedule because one or more backends left the system
                    self.reschedule_workloads()
                check_expired_backend_t0 = time.time()

            if not msgs:
                time.sleep(0.1)

    def process_backend_stats(self, msg: NxsMsgBackendStatsReport):
        stats = {}
        try:
            stats = json.loads(msg.data_in_json_str)
        except:
            pass

        self.scheduling_policy.update_backend_runtime_stats(msg.backend_name, stats)

    def restore_scheduler_states(self):
        backend_names = self.state_db.get_value(self.BACKEND_ROOT_TOPIC)
        if backend_names:
            for backend_name in backend_names:
                self._restore_backend_from_state_db(backend_name)

    def _restore_backend_from_state_db(self, backend_name) -> NxsBackendRuntime:
        backend = NxsBackendRuntime.get_data_from_db(backend_name, self.state_db)
        if backend:
            self.backends[backend_name] = backend
            if backend.has_gpu():
                self.gpu_backends[backend_name] = backend
            else:
                self.cpu_backends[backend_name] = backend

            print(f"Restored backend: {backend.get_runtime_info()}")

    def process_register_backend(self, msg: NxsMsgRegisterBackend):
        backend_name = msg.backend_name
        if backend_name in self.backends:
            # backend could be just restarted - resend DEPLOY_MODEL requests
            self.send_heartbeat_interval(backend_name)
            self.deploy_models_on_single_backend(backend_name)
            return

        self.add_new_backend(msg)
        self.send_heartbeat_interval(backend_name)

        self._update_backend_name_list_in_db()

    def deploy_models_on_single_backend(self, backend_name):
        # single_models = self.get_single_models_on_backend(backend_name)
        # for single_model in single_models:
        #    self.queue_producer.push(backend_name, NxsMsgAllocateModel(model_uuid=single_model.model_uuid))
        pass

    def add_new_backend(self, msg: NxsMsgRegisterBackend):
        backend_name = msg.backend_name

        backend_info = BackendInfo(backend_name=backend_name, state=msg.backend_stat)

        backend = NxsBackendRuntime(backend_info, time.time())

        self.backends[backend_name] = backend
        if not backend.has_gpu():
            self.cpu_backends[backend_name] = backend
        else:
            self.gpu_backends[backend_name] = backend

        backend.update_entry_in_db(self.state_db)

    def send_heartbeat_interval(self, backend_name: str):
        # send back heartbeat interval
        hb_interval_data = NxsMsgChangeHeartbeatInterval(
            interval=self.args.heartbeat_interval
        )
        self.queue_pusher.push(backend_name, hb_interval_data)

    def process_register_workloads(self, msg: NxsMsgRegisterWorkloads):
        scheduling_requests: List[NxsSchedulingRequest] = []

        for wl in msg.workloads:
            pipeline_uuid = wl.pipeline_uuid
            pipeline_rt_info = self._get_pipeline_info(pipeline_uuid)
            scheduling_requests.append(
                NxsSchedulingRequest(
                    pipeline_info=pipeline_rt_info.get_pipeline_info(),
                    session_uuid=wl.session_uuid,
                    requested_fps=wl.fps,
                )
            )

        self.schedule_workloads(scheduling_requests)

    def reschedule_workloads(self):
        return self.schedule_workloads(self.last_requests)

    def schedule_workloads(self, scheduling_requests: List[NxsSchedulingRequest]):
        # clone and store scheduling_requests
        _scheduling_requests: List[NxsSchedulingRequest] = []
        for request in scheduling_requests:
            _scheduling_requests.append(self._clone_nxs_scheduling_request(request))

        final_plan = self.scheduling_policy.schedule(
            scheduling_requests,
            [
                self.backends[backend_name].get_runtime_info()
                for backend_name in self.backends.keys()
            ],
        )
        scheduling_plans = final_plan.scheduling
        unscheduling_plans = final_plan.unscheduling

        # send out plans to backend
        for plan in unscheduling_plans:
            msg = NxsMsgUnschedulePlans(plan=plan)
            backend_name = plan.backend_name
            self.queue_pusher.push(backend_name, msg)

        for plan in scheduling_plans:
            msg = NxsMsgSchedulePlans(plan=plan)
            backend_name = plan.backend_name
            self.queue_pusher.push(backend_name, msg)

        self.last_requests = _scheduling_requests

    def _clone_nxs_scheduling_request(
        self, request: NxsSchedulingRequest
    ) -> NxsSchedulingRequest:
        return NxsSchedulingRequest(
            pipeline_info=NxsPipelineInfo(
                user_name=request.pipeline_info.user_name,
                pipeline_uuid=request.pipeline_info.pipeline_uuid,
                pipeline=copy.deepcopy(request.pipeline_info.pipeline),
                is_public=request.pipeline_info.is_public,
                models=[
                    self._clone_nxs_compository_model(cmodel)
                    for cmodel in request.pipeline_info.models
                ],
            ),
            session_uuid=request.session_uuid,
            requested_fps=request.requested_fps,
        )

    def _clone_nxs_compository_model(
        self, model: NxsCompositoryModel
    ) -> NxsCompositoryModel:
        return NxsCompositoryModel(
            main_model=NxsModel(**(model.main_model.dict())),
            component_models=[
                NxsModel(**(component_model.dict()))
                for component_model in model.component_models
            ],
        )

    def process_heartbeat_msg(self, msg: NxsMsgReportHeartbeat):
        if msg.backend_name not in self.backends:
            # ask backend to re-register
            return

        backend = self.backends[msg.backend_name]
        backend.update_info_from_heartbeat(msg.backend_stat)
        backend.update_entry_in_db(self.state_db)

    def has_expired_backends(self) -> bool:
        has_expired = False

        current_ts = time.time()

        expired_backend_names = []
        expired_backends = []

        for backend_name in self.backends:
            backend = self.backends[backend_name]

            if (
                current_ts - backend.get_last_alive_ts()
                > self.args.backend_timeout_secs
            ):
                expired_backend_names.append(backend_name)
                expired_backends.append(backend)

        if not expired_backend_names:
            return False

        for backend_name in expired_backend_names:
            backend = self.backends.pop(backend_name)
            self.cpu_backends.pop(backend_name, None)
            self.gpu_backends.pop(backend_name, None)
            backend.remove(self.state_db)
            print(f"Backend {backend_name} has been removed from system!")

            has_expired = True

        self._update_backend_name_list_in_db()

        return has_expired


if __name__ == "__main__":
    from args import parse_args

    args = parse_args()

    queue_puller = create_queue_puller_from_args(
        args, NxsQueueType.REDIS, GLOBAL_QUEUE_NAMES.SCHEDULER
    )
    queue_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)

    main_db = create_db_from_args(args, args.db_type)

    state_db = create_simple_key_value_db_from_args(args, NxsSimpleKeyValueDbType.REDIS)

    policy = SimpleSchedulingPolicyv2()

    scheduler = NxsSchedulerProcess(
        args, queue_puller, queue_pusher, state_db, main_db, policy
    )
    scheduler.run()
